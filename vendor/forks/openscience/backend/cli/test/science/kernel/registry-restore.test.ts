import { expect, spyOn, test } from "bun:test"
import path from "path"
import { Global } from "../../../src/global"
import { Instance } from "../../../src/project/instance"
import { KernelRuntime, type KernelIdentity } from "../../../src/science/kernel/registry"
import type { KernelManager } from "../../../src/science/kernel/types"
import { Session } from "../../../src/session"
import { Storage } from "../../../src/storage/storage"
import { tmpdir } from "../../fixture/fixture"

// A restore never starts an interpreter, so the manager is only consulted for
// its presence. Registering it under a private language keeps the module-level
// registry out of the languages the real managers own.
const language = "restore-record-test"
const released: string[] = []
const manager: KernelManager = {
  language,
  async get() {
    throw new Error("a restore must not start an interpreter")
  },
  async release(sessionID) {
    released.push(sessionID)
  },
  async shutdownAll() {},
}

const record = (identity: KernelIdentity, executionCount: number) => ({
  version: 1 as const,
  identity,
  state: "stopped" as const,
  incarnation: 3,
  execution_count: executionCount,
  last_activity_at: 1_700_000_000_000,
  ownership_id: null,
  process: null,
})

test("one unreadable registry record does not abort the whole restore", async () => {
  KernelRuntime.register(manager)
  await using tmp = await tmpdir({ git: true })
  await Instance.provide({
    directory: tmp.path,
    fn: async () => {
      const session = await Session.create({})
      const projectID = Instance.project.id
      const readable: KernelIdentity = {
        projectID,
        sessionID: session.id,
        name: "readable",
        language,
      }
      const unreadable: KernelIdentity = {
        projectID,
        sessionID: session.id,
        name: "unreadable",
        language,
      }
      await Storage.write(["kernel_registry", projectID, session.id, "readable"], record(readable, 7))
      await Storage.write(["kernel_registry", projectID, session.id, "unreadable"], record(unreadable, 9))

      await Bun.write(
        path.join(Global.Path.data, "storage", "kernel_registry", projectID, session.id, "unreadable.json"),
        "{truncated",
      )
      await KernelRuntime.restoreSession(projectID)

      expect(KernelRuntime.status(readable).execution_count).toBe(7)
    },
  })
}, 30_000)

test("a genuine read failure that is not a missing record still surfaces", async () => {
  KernelRuntime.register(manager)
  await using tmp = await tmpdir({ git: true })
  await Instance.provide({
    directory: tmp.path,
    fn: async () => {
      const session = await Session.create({})
      const projectID = Instance.project.id
      await Storage.write(
        ["kernel_registry", projectID, session.id, "permission"],
        record({ projectID, sessionID: session.id, name: "permission", language }, 1),
      )

      // Storage I/O failures remain actionable; only missing or malformed records are skipped.
      const reads = spyOn(Storage, "read").mockImplementation(async () => {
        throw new Error("EIO: i/o error, read")
      })
      try {
        await expect(KernelRuntime.restoreSession(projectID)).rejects.toThrow("EIO")
      } finally {
        reads.mockRestore()
      }
    },
  })
}, 30_000)
