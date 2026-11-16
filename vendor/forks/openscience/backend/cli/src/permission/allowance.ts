import type { JobBroker } from "@/compute/job-broker"
import { PermissionNext } from "./next"

/**
 * A standing approval for paid compute that is bounded by time rather than
 * bound to one plan. An exact-plan approval never recurs: the next job has a
 * different script or input hash and asks again, which left a session's
 * follow-up jobs waiting on prompts overnight. An allowance says "Modal jobs
 * here, up to N minutes of job time in total"; each job's timeout is the
 * ceiling on what it can bill, so the sum of dispatched timeouts is what the
 * allowance meters. When a job would exceed what is left, the prompt returns.
 */
export namespace ComputeAllowance {
  export const PATTERN = /^allowance:(\d+)$/

  export function pattern(minutes: number) {
    return `allowance:${Math.max(1, Math.round(minutes))}`
  }

  export function minutes(value: string): number | undefined {
    const match = PATTERN.exec(value)
    return match ? Number(match[1]) : undefined
  }

  /** The allowance offered beside one job: four of it, at least an hour, at
   * most eight, in whole hours. */
  export function propose(timeoutMinutes: number) {
    const hours = Math.ceil((timeoutMinutes * 4) / 60)
    return Math.min(480, Math.max(60, hours * 60))
  }

  export type Cover = { pattern: string; minutes: number; used: number; scope: "session" | "project" | "global" }

  /** Minutes of Modal job time already dispatched under one allowance. A
   * session allowance counts every Modal job of the session (the jobs
   * approved one by one before it count against it too, which errs toward
   * asking); a durable one counts the jobs created since it was granted. */
  export function used(
    grant: { scope: "session" | "project" | "global"; created?: number },
    jobs: readonly JobBroker.Job[],
    sessionID: string,
  ) {
    return jobs
      .filter((job) => job.modal && (grant.scope === "session" ? job.session_id === sessionID : true))
      .filter((job) => grant.scope === "session" || !grant.created || Date.parse(job.created_at) >= grant.created)
      .reduce((sum, job) => sum + (job.modal?.timeout_minutes ?? 0), 0)
  }

  /** The allowance that still covers a job of `timeoutMinutes`, when one does. */
  export async function cover(input: {
    sessionID: string
    timeoutMinutes: number
    jobs: readonly JobBroker.Job[]
  }): Promise<Cover | undefined> {
    const grants = await PermissionNext.allowances(input.sessionID, "modal")
    const covers = grants
      .map((grant) => {
        const total = minutes(grant.pattern)
        if (total === undefined) return undefined
        const spent = used(grant, input.jobs, input.sessionID)
        return { pattern: grant.pattern, minutes: total, used: spent, scope: grant.scope }
      })
      .filter((item): item is Cover => !!item && item.used + input.timeoutMinutes <= item.minutes)
    return covers.sort((a, b) => b.minutes - b.used - (a.minutes - a.used))[0]
  }

  export function describe(minutes: number) {
    if (minutes % 60 === 0) return `${minutes / 60} h`
    return `${minutes} min`
  }
}
