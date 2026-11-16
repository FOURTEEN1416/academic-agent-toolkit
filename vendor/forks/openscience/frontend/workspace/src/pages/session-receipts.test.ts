import { expect, test } from "bun:test"
import { sessionReceipts } from "./session-receipts"
import type { ProjectRequest } from "@/utils/openscience-fetch"

test("existing-file checks retain canonical outputs and omit deleted or ambiguous receipts", async () => {
  const calls: string[] = []
  const request = Object.assign(
    async (path: string, _init?: RequestInit, query?: Record<string, unknown>) => {
      calls.push(path)
      expect(query?.sessionID).toBe("session")
      return Response.json({ path: query?.path === "/project/alive.json" ? "/project/alive.json" : null })
    },
    { url: () => "" },
  ) as ProjectRequest
  expect(await sessionReceipts(request).files("session", ["/project/deleted.py", "/project/alive.json"])).toEqual([
    "/project/alive.json",
  ])
  expect(calls).toEqual(["/file/resolve", "/file/resolve"])
})

test("job details include a terminal durable job and never rewrite its dispatch receipt", async () => {
  const receipt = { id: "job", status: "queued" }
  const request = Object.assign(
    async (path: string) => {
      expect(path).toBe("/settings/compute/jobs")
      return Response.json([
        {
          id: "job",
          name: "Setup",
          status: "succeeded",
          command: "offline",
          exit_code: 0,
          lifecycle: { delivery: "none", resource: "closed", recoverable: false },
        },
      ])
    },
    { url: () => "" },
  ) as ProjectRequest
  const loader = sessionReceipts(request)
  expect(await loader.job("job")).toMatchObject({ status: "succeeded", exit_code: 0 })
  expect(await loader.job("removed")).toBeUndefined()
  expect(receipt.status).toBe("queued")
})

test("a failed receipt check reports failure instead of pretending unknown files exist", async () => {
  const request = Object.assign(async () => new Response("Unavailable", { status: 503 }), {
    url: () => "",
  }) as ProjectRequest
  await expect(sessionReceipts(request).files("session", ["/project/unknown"])).rejects.toThrow("could not be checked")
})
