import { describe, expect, test } from "bun:test"
import fs from "node:fs/promises"
import os from "node:os"
import path from "node:path"
import { readExport } from "../../src/cli/cmd/import"

async function fixture(content: string) {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), "openscience-import-"))
  const file = path.join(dir, "session.json")
  await Bun.write(file, content)
  return { dir, file }
}

const export_ = { info: { id: "ses_abc" }, messages: [] }

describe("openscience import input", () => {
  test("reads a well-formed export", async () => {
    const { dir, file } = await fixture(JSON.stringify(export_))
    try {
      const read = await readExport(file)
      expect(read.ok).toBe(true)
      if (read.ok) expect(read.data.info.id).toBe("ses_abc")
    } finally {
      await fs.rm(dir, { recursive: true, force: true })
    }
  })

  test("a malformed file is reported as unreadable, not as missing", async () => {
    const { dir, file } = await fixture("{ this is not json")
    try {
      const read = await readExport(file)
      expect(read.ok).toBe(false)
      // The file is right there, so "File not found" sends the user looking in
      // the wrong place for a path they just typed.
      if (!read.ok) {
        expect(read.message).not.toContain("File not found")
        expect(read.message).toContain("Failed to read session data")
      }
    } finally {
      await fs.rm(dir, { recursive: true, force: true })
    }
  })

  test("a missing file still says so", async () => {
    const read = await readExport(path.join(os.tmpdir(), "openscience-no-such-export.json"))
    expect(read.ok).toBe(false)
    if (!read.ok) expect(read.message).toContain("File not found")
  })

  test("valid JSON that is not a session export is rejected with a reason", async () => {
    const { dir, file } = await fixture(JSON.stringify({ hello: "world" }))
    try {
      const read = await readExport(file)
      expect(read.ok).toBe(false)
      if (!read.ok) expect(read.message).toContain("info and messages")
    } finally {
      await fs.rm(dir, { recursive: true, force: true })
    }
  })

  test("an empty file is rejected rather than imported as nothing", async () => {
    const { dir, file } = await fixture("")
    try {
      const read = await readExport(file)
      expect(read.ok).toBe(false)
      if (!read.ok) expect(read.message).toContain("Failed to read session data")
    } finally {
      await fs.rm(dir, { recursive: true, force: true })
    }
  })
})
