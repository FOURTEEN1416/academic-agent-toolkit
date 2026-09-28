import { describe, expect, test } from "bun:test"
import fs from "node:fs/promises"
import path from "node:path"
import { Global } from "../../src/global"
import { Storage } from "../../src/storage/storage"
import { Log } from "../../src/util/log"

Log.init({ print: false })

describe("Storage interprocess mutation lock", () => {
  test("recovers a stale owner record interrupted before publication", async () => {
    const id = `lock-recovery-${crypto.randomUUID()}`
    const target = path.join(Global.Path.data, "storage", "lock-recovery", `${id}.json`)
    const lock = `${target}.lock`
    const old = new Date(Date.now() - 6_000)
    await fs.mkdir(path.dirname(target), { recursive: true })
    await fs.writeFile(lock, "")
    await fs.utimes(lock, old, old)

    try {
      await Storage.write(["lock-recovery", id], { status: "recovered" })

      expect(await Storage.read<{ status: string }>(["lock-recovery", id])).toEqual({ status: "recovered" })
      expect(await Bun.file(lock).exists()).toBe(false)
    } finally {
      await fs.rm(target, { force: true })
      await fs.rm(lock, { force: true })
      await fs.rm(`${lock}.coord`, { recursive: true, force: true })
    }
  })
})
