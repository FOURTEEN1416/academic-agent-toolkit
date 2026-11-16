import { describe, expect, test } from "bun:test"
import fs from "node:fs/promises"
import path from "node:path"
import { FileIdentity } from "../../src/file/identity"
import { SafeFileIO } from "../../src/file/safe-io"
import { SafeTrashIO } from "../../src/file/safe-trash-io"
import { FileTrash } from "../../src/file/trash"
import { tmpdir } from "../fixture/fixture"

describe("exact filesystem identities", () => {
  test("keeps adjacent uint64 file IDs distinct across JSON and approval comparisons", () => {
    const first = (1n << 64n) - 2n
    const second = first + 1n
    expect(Number(first)).toBe(Number(second))
    const left = { dev: FileIdentity.encode(42n), ino: FileIdentity.encode(first) }
    const right = JSON.parse(JSON.stringify({ dev: FileIdentity.encode(42n), ino: FileIdentity.encode(second) }))
    expect(left).toEqual({ dev: 42, ino: "18446744073709551614" })
    expect(right.ino).toBe("18446744073709551615")
    expect(FileIdentity.same(left, right)).toBe(false)
    expect(FileIdentity.same(left, JSON.parse(JSON.stringify(left)))).toBe(true)
  })

  test("accepts safe legacy numbers and equivalent canonical decimal IDs", () => {
    expect(FileIdentity.encode(BigInt(Number.MAX_SAFE_INTEGER))).toBe(Number.MAX_SAFE_INTEGER)
    expect(FileIdentity.encode(BigInt(Number.MAX_SAFE_INTEGER) + 1n)).toBe("9007199254740992")
    expect(FileIdentity.same({ dev: 0, ino: 42 }, { dev: "0", ino: "42" })).toBe(true)
    const identity = { dev: 42, ino: 43, size: 1, mode: 0o600, mtimeMs: 1, ctimeMs: 1, kind: "file" as const }
    const record = {
      id: "ftr_test",
      projectID: "project",
      originalPath: "/file",
      filename: "file",
      size: 1,
      mode: 0o600,
      state: "trash",
      trashedAt: 1,
      expiresAt: 2,
    }
    expect(FileTrash.Record.parse({ ...record, payloadIdentity: identity }).payloadIdentity).toEqual(identity)
    expect(
      FileTrash.Record.parse({ ...record, payloadIdentity: { ...identity, ino: "18446744073709551615" } })
        .payloadIdentity?.ino,
    ).toBe("18446744073709551615")
    expect(
      FileTrash.Record.safeParse({ ...record, payloadIdentity: { ...identity, ino: Number.MAX_SAFE_INTEGER + 1 } })
        .success,
    ).toBe(false)
  })

  test("rejects rounded numbers and malformed or out-of-range text instead of weakening identity", () => {
    for (const value of [
      Number.MAX_SAFE_INTEGER + 1,
      -1,
      1.5,
      NaN,
      Infinity,
      "",
      "abc",
      "01",
      "-1",
      "1.5",
      "18446744073709551616",
    ]) {
      expect(FileIdentity.Value.safeParse(value).success).toBe(false)
    }
    expect(() => FileIdentity.equal(Number.MAX_SAFE_INTEGER + 1, "9007199254740992")).toThrow()
    expect(() => FileIdentity.encode(-1n)).toThrow()
    expect(() => FileIdentity.encode(1n << 64n)).toThrow()
  })

  test("captures exact native path and handle identities and rejects a different approved inode", async () => {
    await using tmp = await tmpdir()
    const target = path.join(tmp.path, "identity.txt")
    await fs.writeFile(target, "original")
    const native = await fs.lstat(target, { bigint: true })
    const stat = await FileIdentity.lstat(target)
    const handle = await fs.open(target, "r")
    try {
      const opened = await FileIdentity.stat(handle)
      const fd = await FileIdentity.fstat(handle.fd)
      expect(FileIdentity.same(stat, opened)).toBe(true)
      expect(FileIdentity.same(stat, fd)).toBe(true)
    } finally {
      await handle.close()
    }
    expect(stat.dev).toBe(FileIdentity.encode(native.dev))
    expect(stat.ino).toBe(FileIdentity.encode(native.ino))
    expect(stat.size).toBe(8)
    expect(stat.mode).toBe(Number(native.mode))
    expect(stat.isFile()).toBe(true)
    expect(stat.isDirectory()).toBe(false)
    const approved = await SafeFileIO.read(target)
    const trash = await SafeTrashIO.inspect(target)
    expect(FileIdentity.same(approved, stat)).toBe(true)
    expect(FileIdentity.same(trash, stat)).toBe(true)
    await expect(
      SafeFileIO.write(target, "replacement", { ...approved, ino: FileIdentity.encode(native.ino + 1n) }),
    ).rejects.toThrow()
    expect(await fs.readFile(target, "utf8")).toBe("original")
    // Legacy safe numbers and canonical strings refer to the same actual file.
    await SafeFileIO.write(target, "replacement", { ...approved, dev: String(approved.dev), ino: String(approved.ino) })
    expect(await fs.readFile(target, "utf8")).toBe("replacement")
  })
})
