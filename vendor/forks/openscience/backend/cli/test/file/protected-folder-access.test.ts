import { afterEach, describe, expect, test } from "bun:test"
import fs from "node:fs/promises"
import os from "node:os"
import path from "node:path"
import { isProtectedFolderDenied, probeProtectedFolderAccess } from "../../src/file/protected-folder-access"

const roots: string[] = []

afterEach(async () => {
  await Promise.all(roots.splice(0).map((root) => fs.rm(root, { recursive: true, force: true })))
})

async function home() {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "openscience-folder-access-"))
  roots.push(root)
  return root
}

describe("protected folder access probe", () => {
  test("does not report a missing Desktop directory as a permission denial", async () => {
    expect(await probeProtectedFolderAccess({ platform: "darwin", home: await home() })).toEqual({ blocked: false })
  })

  test("does not report a readable empty Desktop directory as a permission denial", async () => {
    const root = await home()
    await fs.mkdir(path.join(root, "Desktop"))

    expect(await probeProtectedFolderAccess({ platform: "darwin", home: root })).toEqual({ blocked: false })
  })

  test("classifies only protected-folder permission errors as blocked", () => {
    expect(isProtectedFolderDenied({ code: "EACCES" })).toBeTrue()
    expect(isProtectedFolderDenied({ code: "EPERM" })).toBeTrue()
    expect(isProtectedFolderDenied({ code: "ENOENT" })).toBeFalse()
    expect(isProtectedFolderDenied({ code: "EIO" })).toBeFalse()
    expect(isProtectedFolderDenied(new Error("network unavailable"))).toBeFalse()
  })

  test("never reports the macOS permission state on another platform", async () => {
    expect(await probeProtectedFolderAccess({ platform: "linux", home: await home() })).toEqual({ blocked: false })
  })
})
