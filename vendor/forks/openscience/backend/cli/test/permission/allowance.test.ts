import { expect, test } from "bun:test"
import { ComputeAllowance } from "../../src/permission/allowance"
import { PermissionNext } from "../../src/permission/next"
import { Instance } from "../../src/project/instance"
import type { JobBroker } from "../../src/compute/job-broker"
import { tmpdir } from "../fixture/fixture"

const digest = (seed: string) => seed.padEnd(64, "0")

function modalJob(input: { session: string; minutes: number; created: number }): JobBroker.Job {
  return {
    id: `job_${Math.random().toString(36).slice(2, 8)}`,
    name: "job",
    command: "python train.py",
    target: { kind: "modal" },
    target_label: "Modal",
    scheduler: "none",
    status: "succeeded",
    created_at: new Date(input.created).toISOString(),
    session_id: input.session,
    modal: {
      app: "openscience",
      image: "python:3.12-slim",
      packages: [],
      secret_refs: [],
      gpu: "T4",
      network: "none",
      timeout_minutes: input.minutes,
      uploads: [],
      upload_bytes: 0,
      approval: digest("a"),
      sdk: "1",
    },
  } as JobBroker.Job
}

test("an allowance is proposed in whole hours: four of the job, at least one, at most eight", () => {
  expect(ComputeAllowance.propose(10)).toBe(60)
  expect(ComputeAllowance.propose(25)).toBe(120)
  expect(ComputeAllowance.propose(45)).toBe(180)
  expect(ComputeAllowance.propose(600)).toBe(480)
  expect(ComputeAllowance.pattern(240)).toBe("allowance:240")
  expect(ComputeAllowance.minutes("allowance:240")).toBe(240)
  expect(ComputeAllowance.minutes(digest("f"))).toBeUndefined()
  expect(ComputeAllowance.describe(120)).toBe("2 h")
  expect(ComputeAllowance.describe(90)).toBe("90 min")
})

test("a session allowance meters the session's Modal jobs; a durable one meters jobs since it was granted", () => {
  const now = Date.now()
  const jobs = [
    modalJob({ session: "ses_a", minutes: 25, created: now - 3_600_000 }),
    modalJob({ session: "ses_a", minutes: 25, created: now - 60_000 }),
    modalJob({ session: "ses_b", minutes: 40, created: now - 30_000 }),
  ]
  expect(ComputeAllowance.used({ scope: "session" }, jobs, "ses_a")).toBe(50)
  expect(ComputeAllowance.used({ scope: "session" }, jobs, "ses_b")).toBe(40)
  expect(ComputeAllowance.used({ scope: "project", created: now - 120_000 }, jobs, "ses_a")).toBe(65)
  expect(ComputeAllowance.used({ scope: "project", created: now - 7_200_000 }, jobs, "ses_a")).toBe(90)
})

test("a 'this session' reply to one Modal job grants the allowance beside it, and later jobs ask under it until it is spent", async () => {
  await using tmp = await tmpdir({ git: true })
  await Instance.provide({
    directory: tmp.path,
    fn: async () => {
      const ruleset = [{ permission: "modal", pattern: "*", action: "ask" as const }]
      // The first job asks on its exact plan and offers a four-hour allowance.
      const first = PermissionNext.ask({
        id: "permission_first",
        sessionID: "ses_a",
        permission: "modal",
        patterns: [digest("1")],
        always: [digest("1"), ComputeAllowance.pattern(240)],
        metadata: {},
        ruleset,
        mode: "approve",
      })
      expect((await PermissionNext.list()).map((item) => item.id)).toEqual(["permission_first"])
      await PermissionNext.reply({ requestID: "permission_first", reply: "session" })
      await first

      const grants = await PermissionNext.allowances("ses_a", "modal")
      expect(grants).toEqual([{ pattern: "allowance:240", scope: "session", created: undefined }])

      // 25 minutes dispatched so far: a 30-minute job fits, a 240-minute job does not.
      const jobs = [modalJob({ session: "ses_a", minutes: 25, created: Date.now() })]
      const fits = await ComputeAllowance.cover({ sessionID: "ses_a", timeoutMinutes: 30, jobs })
      expect(fits).toEqual({ pattern: "allowance:240", minutes: 240, used: 25, scope: "session" })
      expect(await ComputeAllowance.cover({ sessionID: "ses_a", timeoutMinutes: 240, jobs })).toBeUndefined()
      // Another session holds no allowance from this one.
      expect(await ComputeAllowance.cover({ sessionID: "ses_b", timeoutMinutes: 5, jobs })).toBeUndefined()

      // Asking under the allowance resolves without a prompt.
      await PermissionNext.ask({
        sessionID: "ses_a",
        permission: "modal",
        patterns: [fits!.pattern],
        always: [],
        metadata: {},
        ruleset,
        mode: "approve",
      })
      expect(await PermissionNext.list()).toEqual([])

      // A digest the allowance does not name still asks on its own.
      const other = PermissionNext.ask({
        id: "permission_other",
        sessionID: "ses_a",
        permission: "modal",
        patterns: [digest("2")],
        always: [digest("2")],
        metadata: {},
        ruleset,
        mode: "approve",
      })
      expect((await PermissionNext.list()).map((item) => item.id)).toEqual(["permission_other"])
      await PermissionNext.reply({ requestID: "permission_other", reply: "reject" })
      await expect(other).rejects.toBeInstanceOf(PermissionNext.RejectedError)
    },
  })
})

test("a 'this project' reply persists the allowance with its grant time, and the wildcard never authorizes paid compute", async () => {
  await using tmp = await tmpdir({ git: true })
  await Instance.provide({
    directory: tmp.path,
    fn: async () => {
      const before = Date.now()
      const ask = PermissionNext.ask({
        id: "permission_project",
        sessionID: "ses_a",
        permission: "modal",
        patterns: [digest("3")],
        always: [digest("3"), ComputeAllowance.pattern(120)],
        metadata: {},
        ruleset: [{ permission: "modal", pattern: "*", action: "ask" }],
        mode: "approve",
      })
      await PermissionNext.reply({ requestID: "permission_project", reply: "project" })
      await ask
      const grants = await PermissionNext.allowances("ses_other", "modal")
      expect(grants).toHaveLength(1)
      expect(grants[0]!.pattern).toBe("allowance:120")
      expect(grants[0]!.scope).toBe("project")
      expect(grants[0]!.created).toBeGreaterThanOrEqual(before)
      expect((await PermissionNext.standing()).map((entry) => entry.pattern).sort()).toEqual(
        [digest("3"), "allowance:120"].sort(),
      )

      // A configured blanket allow for Modal is not an approval of any plan.
      const blanket = PermissionNext.ask({
        id: "permission_blanket",
        sessionID: "ses_other",
        permission: "modal",
        patterns: [digest("4")],
        always: [],
        metadata: {},
        ruleset: [{ permission: "modal", pattern: "*", action: "allow" }],
        mode: "approve",
      })
      expect((await PermissionNext.list()).map((item) => item.id)).toEqual(["permission_blanket"])
      await PermissionNext.reply({ requestID: "permission_blanket", reply: "reject" })
      await expect(blanket).rejects.toBeInstanceOf(PermissionNext.RejectedError)
    },
  })
})
