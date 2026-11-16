import { expect, test } from "bun:test"
import fs from "node:fs/promises"
import path from "node:path"
import { windowsReleaseNote } from "../../../../tooling/repo/release-notes"
import { tmpdir } from "../fixture/fixture"

const marker = `<!-- openscience-release-source:${"a".repeat(40)} -->`
const note = "The Windows desktop installer is unsigned while Microsoft Artifact Signing setup is incomplete."
const script = path.resolve(import.meta.dir, "../../../../tooling/repo/release-notes.ts")

test("signing disclosure is idempotent and preserves source and authored notes", () => {
  for (const newline of ["\n", "\r\n"]) {
    const body = ["## Changes", "- Preserve scientific outputs", "", marker, ""].join(newline)
    const unsigned = windowsReleaseNote(body, "false")
    expect(unsigned.startsWith(body)).toBe(true)
    expect(unsigned.split(marker)).toHaveLength(2)
    expect(unsigned.split(note)).toHaveLength(2)
    expect(windowsReleaseNote(unsigned, "false")).toBe(unsigned)
    expect(windowsReleaseNote(body, "true")).toBe(body)
    const signed = windowsReleaseNote(unsigned, "true")
    expect(signed).toContain(body)
    expect(signed).not.toContain(note)
    expect(windowsReleaseNote(signed, "true")).toBe(signed)
  }
  expect(() => windowsReleaseNote(marker, "")).toThrow("explicit")
  expect(() => windowsReleaseNote(marker, "unknown")).toThrow("explicit")
})

test("release note command updates only drafts, preserves provenance and removes temporary files", async () => {
  await using tmp = await tmpdir()
  const bin = path.join(tmp.path, "bin")
  const state = path.join(tmp.path, "release.json")
  const calls = path.join(tmp.path, "calls.jsonl")
  await fs.mkdir(bin)
  await Bun.write(
    path.join(bin, "gh"),
    `#!/usr/bin/env bun
const args = process.argv.slice(2)
const state = process.env.MOCK_RELEASE
const value = await Bun.file(state).json()
if (args[0] !== "release") process.exit(1)
if (args[1] === "view") process.stdout.write(JSON.stringify(value))
else if (args[1] === "edit") {
  const file = args[args.indexOf("--notes-file") + 1]
  const body = await Bun.file(file).text()
  await Bun.write(state, JSON.stringify({ ...value, body }))
  const log = Bun.file(process.env.MOCK_CALLS)
  const previous = await log.exists() ? await log.text() : ""
  await Bun.write(log, previous + JSON.stringify({ file, args }) + "\\n")
} else process.exit(1)
`,
  )
  await fs.chmod(path.join(bin, "gh"), 0o700)
  await Bun.write(state, JSON.stringify({ body: `Authored details\n${marker}\n`, isDraft: true }))
  const run = async (signing: string, tag = "v9.9.9") => {
    const child = Bun.spawn([process.execPath, script], {
      cwd: tmp.path,
      env: {
        ...process.env,
        PATH: `${bin}:${path.dirname(process.execPath)}:${process.env.PATH ?? ""}`,
        MOCK_RELEASE: state,
        MOCK_CALLS: calls,
        OPENSCIENCE_RELEASE_TAG: tag,
        OPENSCIENCE_WINDOWS_SIGNING: signing,
      },
      stdout: "pipe",
      stderr: "pipe",
    })
    const [code, stdout, stderr] = await Promise.all([
      child.exited,
      new Response(child.stdout).text(),
      new Response(child.stderr).text(),
    ])
    return { code, stdout, stderr }
  }
  expect((await run("false")).code).toBe(0)
  const changed = await Bun.file(state).json()
  expect(changed.body).toContain(note)
  expect(changed.body).toContain(marker)
  const log = await Bun.file(calls).text()
  const first = JSON.parse(log.trim()) as { file: string }
  expect(await Bun.file(first.file).exists()).toBe(false)
  expect((await run("false")).code).toBe(0)
  expect(await Bun.file(calls).text()).toBe(log)
  expect((await run("true")).code).toBe(0)
  expect((await Bun.file(state).json()).body).not.toContain(note)
  await Bun.write(state, JSON.stringify({ body: changed.body, isDraft: false }))
  const before = await Bun.file(calls).text()
  expect((await run("true")).code).not.toBe(0)
  expect((await run("invalid")).code).not.toBe(0)
  expect((await run("false", "latest")).code).not.toBe(0)
  expect(await Bun.file(calls).text()).toBe(before)
  expect((await Bun.file(state).json()).body).toBe(changed.body)
})
