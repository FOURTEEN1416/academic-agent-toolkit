import { expect, test } from "bun:test"
import fs from "node:fs/promises"
import os from "node:os"
import path from "node:path"
import { webVersion } from "../../src/web/assets"

test("reads the embedded frontend release metadata", async () => {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), "openscience-web-metadata-"))
  const file = path.join(dir, "version.json")

  try {
    await Bun.write(file, JSON.stringify({ version: "2.0.2-test.43", channel: "test" }))
    await expect(webVersion({ "/version.json": file })).resolves.toEqual({
      version: "2.0.2-test.43",
      channel: "test",
    })
  } finally {
    await fs.rm(dir, { recursive: true, force: true })
  }
})

test("rejects missing or malformed frontend release metadata", async () => {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), "openscience-web-metadata-"))
  const file = path.join(dir, "version.json")

  try {
    await Bun.write(file, JSON.stringify({ version: "2.0.2-test.43" }))
    await expect(webVersion({ "/version.json": file })).resolves.toBeUndefined()
    await expect(webVersion({})).resolves.toBeUndefined()
  } finally {
    await fs.rm(dir, { recursive: true, force: true })
  }
})
