import { expect, spyOn, test } from "bun:test"
import fs from "node:fs/promises"
import { Instance } from "../../src/project/instance"
import { ScienceFetchTool, ScienceSearchTool } from "../../src/tool/science"
import { SessionFilesystem } from "../../src/session/filesystem"
import { arxiv } from "../../src/science/connectors/literature/arxiv"
import { request, withHttpTestPolicy } from "../../src/science/connectors/http"
import { executionSession, tmpdir } from "../fixture/fixture"

async function within<T>(promise: Promise<T>, ms = 1500) {
  const expired = Promise.withResolvers<never>()
  const timer = setTimeout(() => expired.reject(new Error("Cancelled connector remained queued")), ms)
  return Promise.race([promise, expired.promise]).finally(() => clearTimeout(timer))
}

for (const operation of ["fetch", "search"] as const) {
  test(`science ${operation} rejects a successful late connector result after cancellation without saving files`, async () => {
    await using tmp = await tmpdir({ config: { lsp: false, formatter: false } })
    const entered = Promise.withResolvers<void>()
    const release = Promise.withResolvers<void>()
    const connector =
      operation === "fetch"
        ? spyOn(arxiv, "fetch").mockImplementation(async () => {
            entered.resolve()
            await release.promise
            return { title: "Fixture", abstract: "x".repeat(60000) }
          })
        : spyOn(arxiv, "search").mockImplementation(async () => {
            entered.resolve()
            await release.promise
            return [{ id: "fixture", title: "Late search result" }]
          })
    try {
      await Instance.provide({
        directory: tmp.path,
        fn: async () => {
          const session = await executionSession()
          const workspace = await SessionFilesystem.workspace(session.id)
          const before = await fs.readdir(workspace)
          const abort = new AbortController()
          const context = {
            sessionID: session.id,
            messageID: "",
            callID: "",
            agent: "research",
            abort: abort.signal,
            messages: [],
            metadata: () => {},
            ask: async () => {},
          }
          const pending =
            operation === "fetch"
              ? (await ScienceFetchTool.init()).execute({ db: "arxiv", id: "offline-cancellation-fixture" }, context)
              : (await ScienceSearchTool.init()).execute({ db: "arxiv", query: "offline fixture", limit: 1 }, context)
          const stopped = pending.catch((error: unknown) => error)
          await within(entered.promise)
          abort.abort()
          release.resolve()
          expect(await within(stopped)).toBeInstanceOf(DOMException)
          expect(await fs.readdir(workspace)).toEqual(before)
          await Instance.dispose()
        },
      })
    } finally {
      connector.mockRestore()
      release.resolve()
    }
  })
}

for (const stop of ["abort", "revoke"] as const) {
  test(`science spill rechecks ${stop} immediately before saving`, async () => {
    await using tmp = await tmpdir({ config: { lsp: false, formatter: false } })
    const connector = spyOn(arxiv, "fetch").mockResolvedValue({ title: "Fixture", abstract: "x".repeat(60000) })
    try {
      await Instance.provide({
        directory: tmp.path,
        fn: async () => {
          const session = await executionSession()
          const workspace = await SessionFilesystem.workspace(session.id)
          const before = await fs.readdir(workspace)
          const abort = new AbortController()
          const bind = SessionFilesystem.bindAuthorization
          const barrier = spyOn(SessionFilesystem, "bindAuthorization").mockImplementation(async (input) => {
            const binding = await bind(input)
            if (stop === "abort") abort.abort()
            else await SessionFilesystem.revoke(session.id, binding.grantID)
            return binding
          })
          try {
            const tool = await ScienceFetchTool.init()
            await expect(
              tool.execute(
                { db: "arxiv", id: "precommit-fixture" },
                {
                  sessionID: session.id,
                  messageID: "",
                  callID: "",
                  agent: "research",
                  abort: abort.signal,
                  messages: [],
                  metadata: () => {},
                  ask: async () => {},
                },
              ),
            ).rejects.toBeInstanceOf(stop === "abort" ? DOMException : SessionFilesystem.DeniedError)
            expect(await fs.readdir(workspace)).toEqual(before)
          } finally {
            barrier.mockRestore()
            await Instance.dispose()
          }
        },
      })
    } finally {
      connector.mockRestore()
    }
  })
}

test("aborted concurrency waiters leave the queue without taking the next request's slot", async () => {
  const entered = Promise.withResolvers<void>()
  const release = Promise.withResolvers<void>()
  const calls: string[] = []
  await withHttpTestPolicy(
    {
      resolveAddresses: async () => ["93.184.216.34"],
      transport: async (url) => {
        calls.push(String(url))
        if (calls.length === 1) {
          entered.resolve()
          await release.promise
        }
        return Response.json({ ok: true })
      },
    },
    async () => {
      const options = { cacheTtl: 0, retries: 0, rateLimit: { maxConcurrent: 1 } }
      const first = request("https://export.arxiv.org/cancel-first", options)
      await within(entered.promise)
      const abort = new AbortController()
      const cancelled = request("https://export.arxiv.org/cancel-second", { ...options, signal: abort.signal }).catch(
        (error: unknown) => error,
      )
      const next = request("https://export.arxiv.org/cancel-third", options)
      try {
        // Give both requests a chance to enter the occupied queue.
        await Bun.sleep(20)
        abort.abort()
        expect(await within(cancelled)).toBeInstanceOf(DOMException)
        expect(calls).toHaveLength(1)
        release.resolve()
        await within(Promise.all([first, next]))
        expect(calls.map((url) => new URL(url).pathname)).toEqual(["/cancel-first", "/cancel-third"])
      } finally {
        abort.abort()
        release.resolve()
        await Promise.allSettled([first, next, cancelled])
      }
    },
  )
})

test("cancelled pacing reservations reject promptly and add no delay for later requests", async () => {
  const calls: string[] = []
  await withHttpTestPolicy(
    {
      resolveAddresses: async () => ["93.184.216.34"],
      transport: async (url) => {
        calls.push(String(url))
        return Response.json({ ok: true })
      },
    },
    async () => {
      const options = { cacheTtl: 0, retries: 0, rateLimit: { minIntervalMs: 300 } }
      await request("https://export.arxiv.org/pace-first", options)
      const controllers = Array.from({ length: 8 }, () => new AbortController())
      const cancelled = controllers.map((abort, index) =>
        request(`https://export.arxiv.org/pace-cancel-${index}`, { ...options, signal: abort.signal }).catch(
          (error: unknown) => error,
        ),
      )
      const nextController = new AbortController()
      const next = request("https://export.arxiv.org/pace-next", { ...options, signal: nextController.signal })
      try {
        await Bun.sleep(20)
        for (const controller of controllers) controller.abort()
        for (const result of await within(Promise.all(cancelled))) expect(result).toBeInstanceOf(DOMException)
        await within(next)
        expect(calls.map((url) => new URL(url).pathname)).toEqual(["/pace-first", "/pace-next"])
      } finally {
        for (const controller of controllers) controller.abort()
        nextController.abort()
        await Promise.allSettled([...cancelled, next])
      }
    },
  )
})

test("abort interrupts retry backoff without sending a retry", async () => {
  const entered = Promise.withResolvers<void>()
  let calls = 0
  await withHttpTestPolicy(
    {
      resolveAddresses: async () => ["93.184.216.34"],
      transport: async () => {
        calls++
        entered.resolve()
        return new Response("busy", { status: 429, headers: { "retry-after": "5" } })
      },
    },
    async () => {
      const abort = new AbortController()
      const pending = request("https://export.arxiv.org/backoff-cancel", {
        cacheTtl: 0,
        retries: 1,
        signal: abort.signal,
      }).catch((error: unknown) => error)
      await within(entered.promise)
      await Bun.sleep(20)
      abort.abort()
      expect(await within(pending)).toBeInstanceOf(DOMException)
      expect(calls).toBe(1)
    },
  )
})
