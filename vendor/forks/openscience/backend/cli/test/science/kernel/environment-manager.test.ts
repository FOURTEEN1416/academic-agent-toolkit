import { expect, test } from "bun:test"
import fs from "node:fs/promises"
import os from "node:os"
import path from "node:path"

const fixture = path.resolve(import.meta.dir, "../../fixture/managed-environment.ts")

async function executable(file: string, source: string) {
  await fs.mkdir(path.dirname(file), { recursive: true })
  await Bun.write(file, source)
  await fs.chmod(file, 0o755)
}

async function profile() {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "openscience-managed-environment-"))
  const data = path.join(root, "data")
  const conda = path.join(data, "conda")
  const pythonLog = path.join(root, "python-probes.log")
  const rLog = path.join(root, "r-probes.log")
  const prefixLog = path.join(root, "prefixes.log")
  const env = {
    ...process.env,
    OPENSCIENCE_TEST_HOME: root,
    OPENSCIENCE_TEST_MANAGED_ENVIRONMENTS: "1",
    OPENSCIENCE_DATA_DIR: data,
    OPENSCIENCE_CONFIG_DIR: path.join(root, "config"),
    XDG_CACHE_HOME: path.join(root, "cache"),
    XDG_STATE_HOME: path.join(root, "state"),
    OPENSCIENCE_PYTHON_PROBE_LOG: pythonLog,
    OPENSCIENCE_R_PROBE_LOG: rLog,
    OPENSCIENCE_PREFIX_LOG: prefixLog,
  }
  await executable(
    path.join(conda, "bin", process.platform === "win32" ? "micromamba.exe" : "micromamba"),
    `#!/usr/bin/env bun
import fs from "node:fs"
import path from "node:path"
const args = process.argv.slice(2)
const prefix = args[args.indexOf("-p") + 1]
fs.appendFileSync(process.env.OPENSCIENCE_PREFIX_LOG, prefix + "\\n")
fs.mkdirSync(path.join(prefix, "bin"), { recursive: true })
const language = path.basename(prefix) === "r" ? "r" : "python"
const binary = path.join(prefix, "bin", language === "r" ? "Rscript" : "python")
const log = language === "r" ? process.env.OPENSCIENCE_R_PROBE_LOG : process.env.OPENSCIENCE_PYTHON_PROBE_LOG
fs.writeFileSync(binary, "#!/bin/sh\\necho probe >> \\\"" + log + "\\\"\\necho ok\\n")
fs.chmodSync(binary, 0o755)
`,
  )
  await executable(
    path.join(conda, "envs", "python", "bin", "python"),
    `#!/bin/sh\necho probe >> "${pythonLog}"\necho '{"ok":true}'\n`,
  )
  return {
    root,
    data,
    conda,
    pythonLog,
    rLog,
    prefixLog,
    env,
    async dispose() {
      await fs.rm(root, { recursive: true, force: true })
    },
  }
}

async function run(mode: "runtime" | "bootstrap", env: NodeJS.ProcessEnv) {
  const proc = Bun.spawn([process.execPath, fixture, mode], { cwd: path.resolve(import.meta.dir, "../../.."), env })
  const [stdout, stderr, exit] = await Promise.all([
    new Response(proc.stdout).text(),
    new Response(proc.stderr).text(),
    proc.exited,
  ])
  expect(stderr).toBe("")
  expect(exit).toBe(0)
  return stdout
}

test("Python runtime neither provisions R nor re-probes a ready starter", async () => {
  const current = await profile()
  try {
    expect(await run("runtime", current.env)).toContain("runtime-ok")
    expect((await Bun.file(current.pythonLog).text()).trim().split("\n")).toHaveLength(1)
    expect(await Bun.file(current.rLog).exists()).toBe(false)
    expect(await Bun.file(current.prefixLog).exists()).toBe(false)
  } finally {
    await current.dispose()
  }
})

test("starter repair solves directly at the durable Conda prefix", async () => {
  const current = await profile()
  try {
    await executable(path.join(current.conda, "envs", "r", "bin", "Rscript"), "#!/bin/sh\nexit 1\n")
    expect(await run("bootstrap", current.env)).toContain("bootstrap-ok")
    expect((await Bun.file(current.prefixLog).text()).trim()).toBe(
      await fs.realpath(path.join(current.conda, "envs", "r")),
    )
    const r = Bun.spawn([path.join(current.conda, "envs", "r", "bin", "Rscript"), "-e", "cat('ok')"], {
      env: current.env,
    })
    expect(await r.exited).toBe(0)
    expect(await fs.readdir(path.join(current.conda, ".rollback"))).toEqual([])
  } finally {
    await current.dispose()
  }
})
