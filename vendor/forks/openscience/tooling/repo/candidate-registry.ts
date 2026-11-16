#!/usr/bin/env bun
/**
 * Serve a packed npm candidate as a registry on localhost.
 *
 * The release rehearsal used to stage every candidate on npmjs.org and then
 * wait for the registry to commit fifteen uploads before a single install
 * could run; on a slow day that wait was an hour, and it was the whole
 * critical path. The rehearsal now installs from the tarballs it just built:
 * this process answers packument and tarball requests for the packages in the
 * candidate manifest and proxies everything else to registry.npmjs.org, so
 * `npm install --global @synsci/openscience@<candidate>` runs the real
 * resolver, the real optional-dependency platform selection and the real
 * integrity check without a network round trip to a queue we do not control.
 *
 *   candidate-registry.ts serve --dir <artifact dir> [--port 4873] [--ready <file>]
 *   candidate-registry.ts inspect --dir <artifact dir>
 */
import path from "node:path"
import { createHash } from "node:crypto"
import { createReadStream } from "node:fs"
import { createGunzip } from "node:zlib"

type Artifact = { name: string; version: string; integrity: string; file: string }
type Manifest = { schema: number; source: string; version: string; artifacts: Artifact[] }
type Entry = Artifact & { file: string; pkg: Record<string, unknown>; shasum: string; size: number }

const UPSTREAM = "https://registry.npmjs.org"

function argument(name: string, fallback?: string) {
  const index = process.argv.indexOf(`--${name}`)
  if (index === -1 || index + 1 >= process.argv.length) return fallback
  return process.argv[index + 1]
}

function text(header: Buffer, start: number, length: number) {
  const slice = header.subarray(start, start + length)
  const end = slice.indexOf(0)
  return slice.subarray(0, end === -1 ? slice.length : end).toString("utf8")
}

/**
 * Read `package/package.json` out of an npm tarball without inflating the
 * whole archive: npm writes package.json as the first entry, so this stops
 * after a few kilobytes even for a 100 MB native binary package.
 */
export async function packageJson(file: string): Promise<Record<string, unknown>> {
  const stream = createReadStream(file).pipe(createGunzip())
  let pending = Buffer.alloc(0)
  let skip = 0
  let collect: { size: number; chunks: Buffer[]; have: number } | undefined
  for await (const piece of stream) {
    let chunk = Buffer.isBuffer(piece) ? piece : Buffer.from(piece)
    while (chunk.length) {
      if (skip > 0) {
        const take = Math.min(skip, chunk.length)
        skip -= take
        chunk = chunk.subarray(take)
        continue
      }
      if (collect) {
        const take = Math.min(collect.size - collect.have, chunk.length)
        collect.chunks.push(chunk.subarray(0, take))
        collect.have += take
        chunk = chunk.subarray(take)
        if (collect.have === collect.size) {
          return JSON.parse(Buffer.concat(collect.chunks).toString("utf8")) as Record<string, unknown>
        }
        continue
      }
      pending = pending.length ? Buffer.concat([pending, chunk]) : chunk
      chunk = Buffer.alloc(0)
      while (pending.length >= 512) {
        const header = pending.subarray(0, 512)
        pending = pending.subarray(512)
        if (header.every((byte) => byte === 0)) throw new Error(`${file} has no package/package.json`)
        const prefix = text(header, 345, 155)
        const name = text(header, 0, 100)
        const full = prefix ? `${prefix}/${name}` : name
        const size = parseInt(text(header, 124, 12).trim() || "0", 8)
        const type = header[156]
        const padded = Math.ceil(size / 512) * 512
        const regular = type === 0x30 || type === 0
        if (regular && full === "package/package.json") {
          collect = { size, chunks: [], have: 0 }
          if (pending.length) {
            chunk = pending
            pending = Buffer.alloc(0)
          }
          break
        }
        if (pending.length >= padded) {
          pending = pending.subarray(padded)
          continue
        }
        skip = padded - pending.length
        pending = Buffer.alloc(0)
      }
    }
  }
  throw new Error(`${file} has no package/package.json`)
}

async function shasum(file: string) {
  const hash = createHash("sha1")
  for await (const chunk of createReadStream(file)) hash.update(chunk as Buffer)
  return hash.digest("hex")
}

export async function load(dir: string): Promise<{ manifest: Manifest; entries: Map<string, Entry> }> {
  const manifest = (await Bun.file(path.join(dir, "manifest.json")).json()) as Manifest
  if (manifest.schema !== 1) throw new Error(`Unsupported candidate manifest schema ${manifest.schema}`)
  const entries = new Map<string, Entry>()
  for (const artifact of manifest.artifacts) {
    const file = path.resolve(dir, artifact.file)
    const info = Bun.file(file)
    if (!(await info.exists())) throw new Error(`Candidate tarball is missing: ${file}`)
    const pkg = await packageJson(file)
    if (pkg.name !== artifact.name || pkg.version !== artifact.version) {
      throw new Error(`${file} contains ${pkg.name}@${pkg.version}, manifest says ${artifact.name}@${artifact.version}`)
    }
    entries.set(artifact.name, { ...artifact, file, pkg, shasum: await shasum(file), size: info.size })
  }
  return { manifest, entries }
}

function packument(entry: Entry, base: string, tag: string) {
  const now = new Date().toISOString()
  const dist = {
    tarball: `${base}/${entry.name}/-/${path.basename(entry.file)}`,
    integrity: entry.integrity,
    shasum: entry.shasum,
    unpackedSize: undefined,
  }
  const version = { ...entry.pkg, _id: `${entry.name}@${entry.version}`, dist }
  return {
    _id: entry.name,
    name: entry.name,
    "dist-tags": { latest: entry.version, test: entry.version, [tag]: entry.version },
    versions: { [entry.version]: version },
    time: { created: now, modified: now, [entry.version]: now },
    modified: now,
  }
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } })
}

/** `@scope/name` arrives as one encoded segment or as two plain ones. */
function route(pathname: string) {
  const segments = pathname
    .split("/")
    .filter(Boolean)
    .map((segment) => decodeURIComponent(segment))
  if (!segments.length) return { name: "", rest: [] as string[] }
  if (segments[0].startsWith("@") && !segments[0].includes("/")) {
    return { name: segments.slice(0, 2).join("/"), rest: segments.slice(2) }
  }
  return { name: segments[0], rest: segments.slice(1) }
}

/**
 * npm rewrites tarball hosts that match the default registry to the configured
 * one but keeps the scheme, so an upstream `https://registry.npmjs.org/...`
 * would become `https://127.0.0.1:<port>/...` and fail the TLS handshake.
 * Rewriting the packument here makes npm fetch the tarball from this process,
 * which proxies it.
 */
async function proxy(request: Request, url: URL, base: string) {
  const upstream = await fetch(`${UPSTREAM}${url.pathname}${url.search}`, {
    method: request.method,
    headers: {
      accept: request.headers.get("accept") ?? "*/*",
      "user-agent": request.headers.get("user-agent") ?? "openscience-candidate-registry",
      ...(request.headers.get("content-type") ? { "content-type": request.headers.get("content-type")! } : {}),
    },
    body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.arrayBuffer(),
    redirect: "follow",
  })
  const headers = new Headers()
  for (const name of ["content-type", "etag", "last-modified", "cache-control"]) {
    const value = upstream.headers.get(name)
    if (value) headers.set(name, value)
  }
  if ((upstream.headers.get("content-type") ?? "").includes("json")) {
    const body = (await upstream.text()).replaceAll(`${UPSTREAM}/`, `${base}/`)
    return new Response(body, { status: upstream.status, headers })
  }
  return new Response(upstream.body, { status: upstream.status, headers })
}

export function serve(input: { dir: string; port: number; manifest: Manifest; entries: Map<string, Entry> }) {
  const tag = `candidate-${input.manifest.version.replace(/[^0-9A-Za-z]+/g, "-")}-${input.manifest.source.slice(0, 12)}`
  const server = Bun.serve({
    port: input.port,
    hostname: "127.0.0.1",
    idleTimeout: 120,
    async fetch(request) {
      const response = await answer(request)
      const url = new URL(request.url)
      const origin = input.entries.has(route(url.pathname).name) ? "candidate" : "upstream"
      console.log(`${request.method} ${url.pathname} -> ${response.status} (${origin})`)
      return response
    },
  })
  async function answer(request: Request): Promise<Response> {
    {
      const url = new URL(request.url)
      const base = `http://127.0.0.1:${server.port}`
      if (url.pathname === "/-/ping") return json({})
      if (url.pathname === "/-/candidate") {
        return json({
          version: input.manifest.version,
          source: input.manifest.source,
          packages: [...input.entries.keys()],
        })
      }
      const { name, rest } = route(url.pathname)
      const entry = input.entries.get(name)
      if (!entry) return proxy(request, url, base)
      if (rest.length === 0) return json(packument(entry, base, tag))
      if (rest.length === 1 && rest[0] === entry.version) {
        return json(packument(entry, base, tag).versions[entry.version])
      }
      if (rest.length === 1 && ["latest", "test", tag].includes(rest[0])) {
        return json(packument(entry, base, tag).versions[entry.version])
      }
      if (rest.length === 2 && rest[0] === "-" && rest[1] === path.basename(entry.file)) {
        return new Response(Bun.file(entry.file), {
          headers: { "content-type": "application/octet-stream", "content-length": String(entry.size) },
        })
      }
      return json({ error: "Not found", name, path: url.pathname }, 404)
    }
  }
  return server
}

if (import.meta.main) {
  const command = process.argv[2]
  const dir = argument("dir")
  if (!dir || !["serve", "inspect"].includes(command ?? "")) {
    throw new Error("Usage: candidate-registry.ts <serve|inspect> --dir <artifact dir> [--port 4873] [--ready <file>]")
  }
  const loaded = await load(dir)
  if (command === "inspect") {
    for (const entry of loaded.entries.values()) {
      const pkg = entry.pkg as { os?: string[]; cpu?: string[]; libc?: string[]; optionalDependencies?: object }
      console.log(
        `${entry.name}@${entry.version}  ${(entry.size / 1e6).toFixed(1)} MB  ${[pkg.os, pkg.cpu, pkg.libc]
          .filter(Boolean)
          .map((list) => list!.join("|"))
          .join(
            " ",
          )}  ${pkg.optionalDependencies ? `${Object.keys(pkg.optionalDependencies).length} optional deps` : ""}`,
      )
    }
    process.exit(0)
  }
  const port = Number(argument("port", "4873"))
  const server = serve({ dir, port, ...loaded })
  console.log(
    `candidate registry for ${loaded.manifest.version} (${loaded.entries.size} packages) listening on http://127.0.0.1:${server.port}`,
  )
  const ready = argument("ready")
  if (ready) await Bun.write(ready, `http://127.0.0.1:${server.port}\n`)
}
