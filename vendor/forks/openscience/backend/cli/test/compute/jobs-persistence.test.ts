import { expect, spyOn, test } from "bun:test"
import fs from "node:fs/promises"
import path from "node:path"
import { ComputeJobs } from "../../src/compute/jobs"
import { AtomicRename } from "../../src/util/atomic-rename"
import { tmpdir } from "../fixture/fixture"

async function fixture() {
  const tmp = await tmpdir()
  const root = path.join(tmp.path, "state")
  const filepath = path.join(root, "jobs.json")
  const original = JSON.stringify([
    ComputeJobs.Job.parse({
      id: "completed-job",
      name: "previous completed job",
      command: "true",
      target: { kind: "local" },
      target_label: "Local",
      scheduler: "none",
      status: "succeeded",
      created_at: new Date().toISOString(),
    }),
  ])
  await fs.mkdir(root)
  await fs.writeFile(filepath, original, { mode: 0o600 })
  const sibling = `${filepath}.interrupted.tmp`
  await fs.writeFile(sibling, "interrupted bytes", { mode: 0o600 })
  return { ...tmp, root, filepath, original, sibling, options: { root, workspace: tmp.path } }
}

test("retries transient Windows job-history sharing failures with the committed bytes continuously intact", async () => {
  await using data = await fixture()
  const rename = fs.rename.bind(fs)
  const replace = AtomicRename.replace
  // Exercise the actual Windows rename policy without changing process-wide
  // platform detection used by native ownership and filesystem leases.
  using policy = spyOn(AtomicRename, "replace").mockImplementation((source, destination) =>
    replace(source, destination, true),
  )
  const staged: string[] = []
  const codes = ["EPERM", "EACCES", "EBUSY"]
  using failures = spyOn(fs, "rename").mockImplementation(async (source, destination) => {
    if (String(destination) !== data.filepath) return rename(source, destination)
    staged.push(String(source))
    expect(await fs.readFile(destination, "utf8")).toBe(data.original)
    expect(JSON.parse(await fs.readFile(source, "utf8"))).toEqual([])
    const code = codes[staged.length - 1]
    if (code) throw Object.assign(new Error(`injected ${code}`), { code })
    return rename(source, destination)
  })

  expect(await ComputeJobs.clear(data.options)).toBe(1)
  expect(staged).toHaveLength(4)
  expect(new Set(staged).size).toBe(1)
  expect(await fs.readFile(data.filepath, "utf8")).toBe("[]")
  expect(await fs.readFile(data.sibling, "utf8")).toBe("interrupted bytes")
  expect((await fs.readdir(data.root)).sort()).toEqual(["jobs.json", path.basename(data.sibling)].sort())
})

test("bounds persistent Windows job-history locks, preserves the original, and cleans only its unpublished temp", async () => {
  await using data = await fixture()
  const rename = fs.rename.bind(fs)
  const replace = AtomicRename.replace
  using policy = spyOn(AtomicRename, "replace").mockImplementation((source, destination) =>
    replace(source, destination, true),
  )
  const failure = Object.assign(new Error("injected persistent EPERM"), { code: "EPERM" })
  const staged: string[] = []
  using failures = spyOn(fs, "rename").mockImplementation(async (source, destination) => {
    if (String(destination) !== data.filepath) return rename(source, destination)
    staged.push(String(source))
    expect(await fs.readFile(destination, "utf8")).toBe(data.original)
    expect(JSON.parse(await fs.readFile(source, "utf8"))).toEqual([])
    throw failure
  })

  const started = performance.now()
  await expect(ComputeJobs.clear(data.options)).rejects.toBe(failure)
  const elapsed = performance.now() - started
  expect(elapsed).toBeGreaterThanOrEqual(1_900)
  expect(elapsed).toBeLessThan(6_000)
  expect(staged.length).toBeGreaterThan(3)
  expect(new Set(staged).size).toBe(1)
  expect(await fs.readFile(data.filepath, "utf8")).toBe(data.original)
  expect(await fs.readFile(data.sibling, "utf8")).toBe("interrupted bytes")
  expect((await fs.readdir(data.root)).sort()).toEqual(["jobs.json", path.basename(data.sibling)].sort())
})

for (const [windows, code] of [
  [false, "EPERM"],
  [false, "EACCES"],
  [false, "EBUSY"],
  [true, "EIO"],
  [true, "ENOENT"],
] as const) {
  test(`does not retry ${code} job-history failures with Windows policy ${windows}`, async () => {
    await using data = await fixture()
    const rename = fs.rename.bind(fs)
    const replace = AtomicRename.replace
    using policy = spyOn(AtomicRename, "replace").mockImplementation((source, destination) =>
      replace(source, destination, windows),
    )
    const failure = Object.assign(new Error(`injected ${code}`), { code })
    let attempts = 0
    using failures = spyOn(fs, "rename").mockImplementation(async (source, destination) => {
      if (String(destination) !== data.filepath) return rename(source, destination)
      attempts++
      throw failure
    })

    await expect(ComputeJobs.clear(data.options)).rejects.toBe(failure)
    expect(attempts).toBe(1)
    expect(await fs.readFile(data.filepath, "utf8")).toBe(data.original)
    expect(await fs.readFile(data.sibling, "utf8")).toBe("interrupted bytes")
    expect((await fs.readdir(data.root)).sort()).toEqual(["jobs.json", path.basename(data.sibling)].sort())
  })
}
