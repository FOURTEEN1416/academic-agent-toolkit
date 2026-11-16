import { afterEach, describe, expect, test } from "bun:test"
import { chmod, mkdtemp, rm, writeFile } from "node:fs/promises"
import os from "node:os"
import path from "node:path"

const script = path.join(__dirname, "../../../../install")
const roots: string[] = []

afterEach(async () => {
  await Promise.all(roots.splice(0).map((root) => rm(root, { recursive: true, force: true })))
})

// The installer is driven with shims for the host probes it runs before any
// network access, so the guards can be exercised on every development host.
async function install(shims: Record<string, string>) {
  const root = await mkdtemp(path.join(os.tmpdir(), "openscience-install-script-"))
  roots.push(root)
  const bin = path.join(root, "bin")
  await Bun.write(path.join(bin, ".keep"), "")
  for (const [name, body] of Object.entries(shims)) {
    const file = path.join(bin, name)
    await writeFile(file, `#!/bin/sh\n${body}\n`)
    await chmod(file, 0o755)
  }
  const proc = Bun.spawn(["bash", script], {
    env: { ...process.env, HOME: path.join(root, "home"), PATH: `${bin}:${process.env.PATH ?? ""}` },
    stdout: "pipe",
    stderr: "pipe",
  })
  const [stdout, stderr, code] = await Promise.all([
    new Response(proc.stdout).text(),
    new Response(proc.stderr).text(),
    proc.exited,
  ])
  return { code, output: stdout + stderr }
}

const linuxArm64 = 'case "$1" in -m) echo aarch64 ;; *) echo Linux ;; esac'
const windowsX64 = 'case "$1" in -m) echo x86_64 ;; *) echo MINGW64_NT-10.0-22631 ;; esac'
type Cpuinfo = "avx2" | "legacy" | "unreadable"
// Every grep except the Windows CPU probe keeps the host implementation.
const cpuinfo = (state: Cpuinfo) => {
  const status = state === "avx2" ? 0 : state === "legacy" ? 1 : 2
  return `for arg in "$@"; do [ "$arg" = /proc/cpuinfo ] && exit ${status}; done; exec /usr/bin/grep "$@"`
}
// Answers the release lookup, then reports the asset the installer asked for
// instead of downloading it.
const release = `case "$*" in *api.github.com*) echo '"tag_name": "v9.9.9"'; exit 0 ;; esac; echo "requested $*" >&2; exit 22`
const windows = (cpu: Cpuinfo) => ({
  uname: windowsX64,
  grep: cpuinfo(cpu),
  curl: release,
  unzip: "exit 0",
  openscience: "echo 0.0.0",
})
// Stands in for the GitHub release lookup so a run that passes the guards
// stops at the version fetch instead of reaching the network.
const offline = "exit 22"

describe.skipIf(process.platform === "win32")("install script", () => {
  test("refuses Linux ARM64 kernels without 4 KB pages before downloading", async () => {
    const result = await install({ uname: linuxArm64, getconf: "echo 16384", curl: offline })
    expect(result.code).toBe(1)
    expect(result.output).toContain("page size 16384 is unsupported")
    expect(result.output).toContain("4 KB pages")
    expect(result.output).toContain("https://github.com/oven-sh/bun/issues/17627")
    expect(result.output).not.toContain("Failed to fetch version information")
  })

  test("continues on 4 KB pages and when getconf is unavailable", async () => {
    for (const getconf of ["echo 4096", "exit 127"]) {
      const result = await install({ uname: linuxArm64, getconf, curl: offline })
      expect(result.output).not.toContain("is unsupported")
      expect(result.output).toContain("Failed to fetch version information")
      expect(result.code).toBe(1)
    }
  })

  test("downloads the Windows baseline archive when the CPU lacks AVX2", async () => {
    const result = await install(windows("legacy"))
    expect(result.output).toContain("openscience-windows-x64-baseline.zip")
    expect(result.code).not.toBe(0)
  })

  test("downloads the Windows baseline archive when CPU flags are unreadable", async () => {
    const result = await install(windows("unreadable"))
    expect(result.output).toContain("openscience-windows-x64-baseline.zip")
    expect(result.code).not.toBe(0)
  })

  test("keeps the optimized Windows archive when the CPU reports AVX2", async () => {
    const result = await install(windows("avx2"))
    expect(result.output).toContain("openscience-windows-x64.zip")
    expect(result.output).not.toContain("baseline")
  })
})
