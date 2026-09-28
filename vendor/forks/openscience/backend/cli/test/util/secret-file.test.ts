import { expect, test } from "bun:test"
import fs from "fs/promises"
import os from "os"
import path from "path"
import { SecretFile } from "../../src/util/secret-file"

test("concurrent key creation returns one owner-only machine key", async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "openscience-secret-key-"))
  const filepath = path.join(root, "secret.key")
  try {
    const keys = await Promise.all(Array.from({ length: 12 }, () => SecretFile.key(filepath)))
    expect(new Set(keys.map((key) => key.toString("hex"))).size).toBe(1)
    expect(keys[0]?.byteLength).toBe(32)
    if (process.platform !== "win32") {
      expect((await fs.stat(filepath)).mode & 0o777).toBe(0o600)
    }
  } finally {
    await fs.rm(root, { recursive: true, force: true })
  }
})

test("an invalid existing key is never silently replaced", async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "openscience-secret-corrupt-"))
  const filepath = path.join(root, "secret.key")
  try {
    await fs.writeFile(filepath, "not-a-key")
    const old = new Date(Date.now() - 10_000)
    await fs.utimes(filepath, old, old)
    await expect(SecretFile.key(filepath)).rejects.toThrow(/refusing to replace/)
    expect(await Bun.file(filepath).text()).toBe("not-a-key")
  } finally {
    await fs.rm(root, { recursive: true, force: true })
  }
})
