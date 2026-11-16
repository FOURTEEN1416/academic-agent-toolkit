import { expect, test } from "bun:test"
import { createHash } from "node:crypto"
import fs from "node:fs/promises"
import path from "node:path"
import { load, packageJson, serve } from "../../../../tooling/repo/candidate-registry"
import { tmpdir } from "../fixture/fixture"

async function pack(root: string, manifest: Record<string, unknown>) {
  const dir = path.join(root, "src", String(manifest.name).replace("/", "__"))
  await fs.mkdir(dir, { recursive: true })
  await Bun.write(path.join(dir, "package.json"), JSON.stringify(manifest, null, 2))
  await Bun.write(path.join(dir, "index.js"), `module.exports = ${JSON.stringify(manifest.name)}\n`)
  const out = path.join(root, "candidate")
  await fs.mkdir(out, { recursive: true })
  const proc = Bun.spawn(["npm", "pack", "--silent", "--pack-destination", out, dir], {
    stdout: "pipe",
    stderr: "pipe",
  })
  const [stdout, exit] = await Promise.all([new Response(proc.stdout).text(), proc.exited])
  if (exit !== 0) throw new Error(await new Response(proc.stderr).text())
  const file = stdout.trim().split("\n").pop()!
  const bytes = await Bun.file(path.join(out, file)).bytes()
  const integrity = `sha512-${createHash("sha512").update(bytes).digest("base64")}`
  return { name: String(manifest.name), version: String(manifest.version), file, integrity }
}

test("serves a packed candidate as a registry npm can install from, with the platform package chosen locally", async () => {
  if (!Bun.which("npm")) return
  await using tmp = await tmpdir()
  const version = "9.9.9-test.1"
  const platform = `${process.platform}-${process.arch}`
  const native = await pack(tmp.path, {
    name: `@synsci-test/native-${platform}`,
    version,
    os: [process.platform],
    cpu: [process.arch],
    bin: { "native-hello": "index.js" },
  })
  const other = await pack(tmp.path, {
    name: "@synsci-test/native-nowhere-x64",
    version,
    os: ["nowhere"],
    cpu: ["x64"],
  })
  const wrapper = await pack(tmp.path, {
    name: "@synsci-test/wrapper",
    version,
    optionalDependencies: { [native.name]: version, [other.name]: version },
  })
  const dir = path.join(tmp.path, "candidate")
  await Bun.write(
    path.join(dir, "manifest.json"),
    JSON.stringify({ schema: 1, source: "a".repeat(40), version, artifacts: [native, other, wrapper] }),
  )

  // The first tar entry is package.json; the reader stops there.
  expect(await packageJson(path.join(dir, wrapper.file))).toMatchObject({ name: wrapper.name, version })

  const loaded = await load(dir)
  expect([...loaded.entries.keys()].sort()).toEqual([native.name, other.name, wrapper.name].sort())
  const server = serve({ dir, port: 0, ...loaded })
  try {
    const base = `http://127.0.0.1:${server.port}`
    const packument = (await (await fetch(`${base}/${encodeURIComponent(wrapper.name)}`)).json()) as {
      "dist-tags": Record<string, string>
      versions: Record<string, { dist: { tarball: string; integrity: string }; optionalDependencies: object }>
    }
    expect(packument["dist-tags"].latest).toBe(version)
    const dist = packument.versions[version].dist
    expect(dist.integrity).toBe(wrapper.integrity)
    expect(dist.tarball).toBe(`${base}/${wrapper.name}/-/${wrapper.file}`)
    const tarball = await fetch(dist.tarball)
    expect(tarball.status).toBe(200)
    expect(
      createHash("sha512")
        .update(await tarball.bytes())
        .digest("base64"),
    ).toBe(wrapper.integrity.slice("sha512-".length))
    expect((await fetch(`${base}/${wrapper.name}/-/missing.tgz`)).status).toBe(404)

    const prefix = path.join(tmp.path, "prefix")
    const home = path.join(tmp.path, "home")
    await fs.mkdir(prefix, { recursive: true })
    await fs.mkdir(home, { recursive: true })
    const install = Bun.spawn(["npm", "install", "--prefix", prefix, `${wrapper.name}@${version}`], {
      env: {
        ...process.env,
        HOME: home,
        NPM_CONFIG_REGISTRY: `${base}/`,
        NPM_CONFIG_AUDIT: "false",
        NPM_CONFIG_FUND: "false",
        NPM_CONFIG_UPDATE_NOTIFIER: "false",
      },
      stdout: "pipe",
      stderr: "pipe",
    })
    const [stderr, exit] = await Promise.all([new Response(install.stderr).text(), install.exited])
    expect(exit, stderr).toBe(0)
    const installed = path.join(prefix, "node_modules", "@synsci-test")
    expect(await fs.readdir(installed).then((names) => names.sort())).toEqual([`native-${platform}`, "wrapper"].sort())
    expect(await Bun.file(path.join(installed, `native-${platform}`, "package.json")).json()).toMatchObject({ version })
  } finally {
    server.stop(true)
  }
})
