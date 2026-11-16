import { Hono } from "hono"
import crypto from "node:crypto"
import { describeRoute, resolver, validator } from "hono-openapi"
import { streamSSE } from "hono/streaming"
import z from "zod"
import { BusEvent } from "@/bus/bus-event"
import { GlobalBus } from "@/bus/global"
import { Instance } from "../../project/instance"
import { Installation } from "@/installation"
import { Log } from "../../util/log"
import { lazy } from "@synsci/util/lazy"
import { Config } from "../../config/config"
import { errors } from "../error"
import { Project } from "@/project/project"
import { ManagedProject } from "@/project/managed"
import { SessionFilesystem } from "@/session/filesystem"
import { ServerIdentity } from "../identity"

const log = Log.create({ service: "server" })

export const GlobalDisposedEvent = BusEvent.define("global.disposed", z.object({}))

/** Upper bound on events buffered per SSE client before the oldest are dropped. */
const EVENT_QUEUE_LIMIT = 2000

type GlobalEvent = { directory?: string; payload: { type: string; properties?: unknown } }

/**
 * Part id of a streamed `message.part.updated` event, used to coalesce a full
 * queue. Scoped by directory because this stream multiplexes every project,
 * where the sibling `/event` carries one.
 */
function partID(event: GlobalEvent) {
  if (event.payload.type !== "message.part.updated") return
  const part = (event.payload.properties as { part?: { id?: unknown } } | undefined)?.part
  return typeof part?.id === "string" ? `${event.directory ?? ""}:${part.id}` : undefined
}

const ProjectName = z
  .string()
  .transform((name) => name.normalize("NFC").trim())
  .pipe(
    z
      .string()
      .min(1, "Project name is required")
      .max(100, "Project name must be 100 characters or fewer")
      .refine((name) => !/[\u0000-\u001f\u007f]/u.test(name), "Project name cannot contain control characters")
      .refine((name) => !name.includes("/") && !name.includes("\\"), "Project name cannot contain path separators")
      .transform((name) => name.replace(/[ \t]+/gu, " ")),
  )

const ProjectSource = z.object({
  path: z.string().trim().min(1),
  access: SessionFilesystem.Access.default("write"),
})

const ProjectCreate = z
  .object({
    name: ProjectName,
    sources: ProjectSource.array().max(10).default([]),
    operation_id: z.string().uuid().optional(),
  })
  .strict()

function projectFingerprint(input: z.infer<typeof ProjectCreate>) {
  return crypto
    .createHash("sha256")
    .update(JSON.stringify({ name: input.name, sources: input.sources }))
    .digest("hex")
}

export const GlobalRoutes = lazy(() =>
  new Hono()
    .get(
      "/health",
      describeRoute({
        summary: "Get health",
        description: "Get health information about the OpenScience server.",
        operationId: "global.health",
        responses: {
          200: {
            description: "Health information",
            content: {
              "application/json": {
                schema: resolver(
                  z.object({
                    healthy: z.literal(true),
                    version: z.string(),
                    sourceSha: z.string().nullable(),
                    sourceWorktreeHash: z.string().nullable(),
                    runId: z.string(),
                  }),
                ),
              },
            },
          },
        },
      }),
      async (c) => {
        return c.json({ healthy: true, version: Installation.VERSION, ...ServerIdentity.current })
      },
    )
    .post(
      "/project",
      describeRoute({
        summary: "Create project",
        description:
          "Create an app-managed project with an opaque identity and optional project-scoped access to source locations explicitly selected by the user. Source paths never become the project identity. Reusing an operation_id with the exact same draft safely replays its original result.",
        operationId: "global.project.create",
        responses: {
          201: {
            description: "Created project information",
            content: {
              "application/json": {
                schema: resolver(Project.Info),
              },
            },
          },
          200: {
            description: "Existing project information for a replayed operation",
            content: {
              "application/json": {
                schema: resolver(Project.Info),
              },
            },
          },
          409: { description: "Operation id was already bound to a different project draft" },
          ...errors(400),
        },
      }),
      validator("json", ProjectCreate),
      async (c) => {
        const input = c.req.valid("json")
        const checkpoint = async (created: Project.Info) => {
          await Instance.provide({
            directory: created.worktree,
            projectID: created.id,
            fn: async () => {
              await SessionFilesystem.seedProject({ projectID: created.id, grants: input.sources })
            },
          })
        }
        if (!input.operation_id) return c.json(await ManagedProject.create(input.name, checkpoint), 201)

        const result = await ManagedProject.createIdempotent({
          operationID: input.operation_id,
          fingerprint: projectFingerprint(input),
          name: input.name,
          checkpoint,
        })
        if (result.status === "conflict") {
          return c.json(
            {
              error: "project_operation_conflict",
              message: "This project operation is already bound to a different workspace choice.",
            },
            409,
          )
        }
        return c.json(result.project, result.status === "created" ? 201 : 200)
      },
    )
    .get(
      "/event",
      describeRoute({
        summary: "Get global events",
        description: "Subscribe to global events from the OpenScience system using server-sent events.",
        operationId: "global.event",
        responses: {
          200: {
            description: "Event stream",
            content: {
              "text/event-stream": {
                schema: resolver(
                  z
                    .object({
                      directory: z.string(),
                      payload: BusEvent.payloads(),
                    })
                    .meta({
                      ref: "GlobalEvent",
                    }),
                ),
              },
            },
          },
        },
      }),
      async (c) => {
        log.info("global event connected")
        return streamSSE(c, async (stream) => {
          const connected = (): GlobalEvent => ({ payload: { type: "server.connected", properties: {} } })

          // Send heartbeat every 30s to prevent WKWebView timeout (60s default)
          const heartbeat = setInterval(() => {
            push({ payload: { type: "server.heartbeat", properties: {} } })
          }, 30000)

          // The subscriber never awaits the socket. Events land in a bounded
          // per-connection queue drained by one writer loop, so a stalled
          // browser tab cannot grow this connection without bound: `emit`
          // discards the promise an async listener returns, so nothing else
          // here would ever apply backpressure.
          const queue: GlobalEvent[] = []
          const done = Promise.withResolvers<void>()
          const state = { closed: false, draining: false, overflowed: false }
          const cleanup = () => {
            if (state.closed) return
            state.closed = true
            clearInterval(heartbeat)
            GlobalBus.off("event", handler)
            done.resolve()
            log.info("global event disconnected")
          }
          const drain = async () => {
            if (state.draining) return
            state.draining = true
            try {
              for (;;) {
                const event = state.closed ? undefined : queue.shift()
                if (!event) break
                await stream.writeSSE({ data: JSON.stringify(event) })
                // One resync frame covers the losses since the client last
                // re-hydrated, so the next overflow has to raise its own.
                if (event.payload.type === "server.connected") state.overflowed = false
              }
            } catch (error) {
              log.debug("global event write failed", { error })
              cleanup()
            } finally {
              state.draining = false
            }
          }
          const push = (event: GlobalEvent) => {
            if (state.closed) return
            if (queue.length >= EVENT_QUEUE_LIMIT) {
              const part = partID(event)
              // Replace the newest queued update for the part, never an older
              // one, so the client still receives states in order.
              const index = part === undefined ? -1 : queue.findLastIndex((item) => partID(item) === part)
              if (index >= 0) {
                queue[index] = event
                return
              }
              // Drop a queued part update before anything else: the client
              // reconciles whole parts, whereas a dropped project, session or
              // permission event leaves it stale for good.
              const oldestPart = queue.findIndex((item) => partID(item) !== undefined)
              const victim =
                oldestPart >= 0 ? oldestPart : queue.findIndex((item) => item.payload.type !== "server.connected")
              queue.splice(victim >= 0 ? victim : 0, 1)
              if (!state.overflowed) {
                state.overflowed = true
                log.warn("global event queue overflow; dropping oldest events", { limit: EVENT_QUEUE_LIMIT })
                // Whatever was lost, the client re-hydrates on this frame
                // exactly as it does after a reconnect.
                queue.unshift(connected())
              }
            }
            queue.push(event)
            void drain()
          }
          const handler = (event: GlobalEvent) => push(event)

          push(connected())
          GlobalBus.on("event", handler)

          stream.onAbort(cleanup)
          await done.promise
        })
      },
    )
    .get(
      "/config",
      describeRoute({
        summary: "Get global configuration",
        description: "Retrieve the current global OpenScience configuration settings and preferences.",
        operationId: "global.config.get",
        responses: {
          200: {
            description: "Get global config info",
            content: {
              "application/json": {
                schema: resolver(Config.Info),
              },
            },
          },
        },
      }),
      async (c) => {
        return c.json(Config.redact(await Config.getGlobal()))
      },
    )
    .patch(
      "/config",
      describeRoute({
        summary: "Update global configuration",
        description: "Update global OpenScience configuration settings and preferences.",
        operationId: "global.config.update",
        responses: {
          200: {
            description: "Successfully updated global config",
            content: {
              "application/json": {
                schema: resolver(Config.Info),
              },
            },
          },
          ...errors(400),
        },
      }),
      validator("json", Config.Info),
      async (c) => {
        // Validated above, but written as sent: the schema's parsed form
        // expands scalars and fills defaults that must not land in the file.
        c.req.valid("json")
        const config = (await c.req.json()) as Config.Info
        const restored = Config.restore(config, await Config.getGlobal())
        const next = await Config.updateGlobal(restored)
        return c.json(Config.redact(next))
      },
    )
    .get(
      "/config/raw",
      describeRoute({
        summary: "Get raw global configuration",
        description: "Read the verbatim global config file for the advanced editor.",
        operationId: "global.configRawGet",
        responses: {
          200: {
            description: "Raw global config",
            content: {
              "application/json": {
                schema: resolver(z.object({ content: z.string(), path: z.string() })),
              },
            },
          },
        },
      }),
      async (c) => {
        return c.json(await Config.getGlobalRaw())
      },
    )
    .put(
      "/config/raw",
      describeRoute({
        summary: "Replace raw global configuration",
        description: "Overwrite the global config file verbatim (supports removing keys).",
        operationId: "global.configRawSet",
        responses: {
          200: {
            description: "Replaced global config",
            content: {
              "application/json": {
                schema: resolver(Config.Info),
              },
            },
          },
          ...errors(400),
        },
      }),
      validator("json", z.object({ content: z.string() })),
      async (c) => {
        const next = await Config.replaceGlobal(c.req.valid("json").content)
        return c.json(Config.redact(next))
      },
    )
    .post(
      "/config/unset",
      describeRoute({
        summary: "Unset a global config key",
        description: "Remove a key path from the global config (deep-merge cannot unset).",
        operationId: "global.configUnset",
        responses: {
          200: {
            description: "Updated global config",
            content: {
              "application/json": {
                schema: resolver(Config.Info),
              },
            },
          },
          ...errors(400),
        },
      }),
      validator("json", z.object({ path: z.array(z.string()).min(1) })),
      async (c) => {
        const result = await Config.unsetGlobal(c.req.valid("json").path)
        return c.json(result.config)
      },
    )
    .post(
      "/dispose",
      describeRoute({
        summary: "Dispose instance",
        description: "Clean up and dispose all OpenScience instances, releasing all resources.",
        operationId: "global.dispose",
        responses: {
          200: {
            description: "Global disposed",
            content: {
              "application/json": {
                schema: resolver(z.boolean()),
              },
            },
          },
        },
      }),
      async (c) => {
        await Instance.disposeAll()
        GlobalBus.emit("event", {
          directory: "global",
          payload: {
            type: GlobalDisposedEvent.type,
            properties: {},
          },
        })
        return c.json(true)
      },
    ),
)
