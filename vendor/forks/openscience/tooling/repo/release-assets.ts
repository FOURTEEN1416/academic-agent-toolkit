#!/usr/bin/env bun

import path from "path"
import os from "os"
import { mkdtemp, readdir } from "node:fs/promises"
import { $ } from "bun"
import { Script } from "@synsci/script"
import cli from "../../backend/cli/package.json"
import { NativeTargets, nativePackageName } from "../../backend/cli/script/native-targets"

async function sha256(file: string) {
  const bytes = await Bun.file(file).arrayBuffer()
  return new Bun.CryptoHasher("sha256").update(bytes).digest("hex")
}

const directory = path.resolve(process.argv[2] ?? "backend/cli/dist")
const files = (await readdir(directory))
  .filter(
    (file) =>
      file === "checksums.txt" ||
      (file.startsWith("openscience-") && (file.endsWith(".zip") || file.endsWith(".tar.gz"))),
  )
  .sort()
const expected = [
  "checksums.txt",
  ...NativeTargets.map((target) => {
    const name = nativePackageName(cli.name, target).replace(`${cli.name}-`, "openscience-")
    return `${name}${target.os === "linux" ? ".tar.gz" : ".zip"}`
  }),
].sort()
if (files.length !== expected.length || expected.some((file, index) => files[index] !== file)) {
  throw new Error(`Release assets must contain exactly: ${expected.join(", ")}`)
}

const tag = `v${Script.version}`

type Asset = { name: string; size: number; state: string }
async function assets(): Promise<Map<string, Asset>> {
  const listed = await $`gh release view ${tag} --json assets --jq '.assets[] | {name, size, state}'`.text()
  return new Map(
    listed
      .split(/\r?\n/)
      .map((item) => item.trim())
      .filter(Boolean)
      .map((line) => JSON.parse(line) as Asset)
      .map((asset) => [asset.name, asset]),
  )
}

async function verify(name: string, local: string) {
  const temp = await mkdtemp(path.join(os.tmpdir(), "openscience-release-asset-"))
  await $`gh release download ${tag} --pattern ${name} --dir ${temp}`
  const remote = path.join(temp, name)
  const [localHash, remoteHash] = await Promise.all([sha256(local), sha256(remote)])
  return localHash === remoteHash
}

// GitHub finalizes an upload after the request returns; a job that dies
// mid-upload can leave an asset that appears only later, and an asset the
// listing does not yet show answers a second upload with 422 "already exists".
// Every path ends in the same place: the bytes on the release equal ours.
const existing = await assets()
for (const name of files) {
  const local = path.join(directory, name)
  if (!existing.has(name)) {
    const result = await $`gh release upload ${tag} ${local}`.nothrow()
    if (result.exitCode === 0) {
      console.log(`uploaded immutable release asset ${name}`)
      continue
    }
    const stderr = result.stderr.toString()
    if (!stderr.includes("already exists")) throw new Error(`Uploading ${name} failed: ${stderr.trim()}`)
    console.log(`release asset ${name} appeared during the upload; verifying it instead`)
  }

  if (await verify(name, local)) {
    console.log(`verified immutable release asset ${name}`)
    continue
  }
  // A partial asset from a killed upload is the one thing safe to replace:
  // GitHub never marks it "uploaded" at the full size. Different complete
  // bytes are refused, as before.
  const remote = (await assets()).get(name)
  const size = Bun.file(local).size
  if (remote && remote.state === "uploaded" && remote.size === size) {
    throw new Error(`Draft release asset ${name} already exists with different bytes; refusing to clobber it`)
  }
  console.log(
    `release asset ${name} is incomplete (${remote?.state ?? "missing"}, ${remote?.size ?? 0} bytes); replacing it`,
  )
  await $`gh release delete-asset ${tag} ${name} --yes`
  await $`gh release upload ${tag} ${local}`
  if (!(await verify(name, local))) throw new Error(`Release asset ${name} did not verify after re-upload`)
  console.log(`uploaded immutable release asset ${name}`)
}
