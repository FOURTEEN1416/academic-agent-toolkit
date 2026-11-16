import { expect, test } from "bun:test"
import { Instance } from "../../src/project/instance"
import { Provider } from "../../src/provider/provider"
import { Session } from "../../src/session"
import { MessageV2 } from "../../src/session/message-v2"
import { SessionPrompt } from "../../src/session/prompt"
import { tmpdir, trustProject } from "../fixture/fixture"
import { STRESS_PROVIDER_ID, STRESS_PROVIDER_MODEL, stressProviderConfig } from "../fixture/stress-provider"

const MARKER = "RESTART_PAUSE_MAIN_REQUEST"
const encoder = new TextEncoder()

function chunk(delta: Record<string, unknown>, finish: string | null) {
  return `data: ${JSON.stringify({
    id: "chatcmpl-restart",
    object: "chat.completion.chunk",
    created: Math.floor(Date.now() / 1_000),
    model: STRESS_PROVIDER_MODEL,
    choices: [{ index: 0, delta, finish_reason: finish }],
    ...(finish ? { usage: { prompt_tokens: 12, completion_tokens: 3, total_tokens: 15 } } : {}),
  })}\n\n`
}

function sse(body: ReadableStream<Uint8Array> | string) {
  return new Response(body, { headers: { "content-type": "text/event-stream", "cache-control": "no-cache" } })
}

function immediate(text: string) {
  return sse(`${chunk({ role: "assistant", content: text }, null)}${chunk({}, "stop")}data: [DONE]\n\n`)
}

/** Streams the start of a bash tool call and then stalls: a turn mid-work
 * when the restart lands. */
function stalled(open: WritableStreamDefaultWriter<Uint8Array>[]) {
  const pipe = new TransformStream<Uint8Array, Uint8Array>()
  const writer = pipe.writable.getWriter()
  open.push(writer)
  void (async () => {
    await writer.write(encoder.encode(chunk({ role: "assistant", content: "Working on it. " }, null)))
    await writer.write(
      encoder.encode(
        chunk(
          {
            tool_calls: [{ index: 0, id: "call_paused", type: "function", function: { name: "bash", arguments: "" } }],
          },
          null,
        ),
      ),
    )
  })()
  return sse(pipe.readable)
}

async function pendingToolPart(sessionID: string, timeoutMs = 10_000): Promise<MessageV2.ToolPart> {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    for (const message of await Session.messages({ sessionID })) {
      for (const part of message.parts) {
        if (part.type === "tool" && part.state.status === "pending") return part
      }
    }
    await Bun.sleep(20)
  }
  throw new Error("the turn never reached a pending tool call")
}

test("a restart pauses a running turn under a named reason and the next boot continues it", async () => {
  const open: WritableStreamDefaultWriter<Uint8Array>[] = []
  let mainRequests = 0
  using server = Bun.serve({
    hostname: "127.0.0.1",
    port: 0,
    async fetch(request) {
      if (new URL(request.url).pathname !== "/v1/chat/completions") return new Response("not found", { status: 404 })
      const body = JSON.stringify(await request.json())
      if (!body.includes(MARKER)) return immediate("Title")
      // The first request stalls until the pause; the resumed turn answers at once.
      mainRequests += 1
      return mainRequests === 1 ? stalled(open) : immediate("Picked the task back up.")
    },
  })
  await using tmp = await tmpdir({
    git: true,
    config: stressProviderConfig(`http://127.0.0.1:${server.port}/v1`),
  })
  // The restart route has no project instance of its own. The pause is
  // requested from a continuation registered before any instance context
  // exists, so it runs with none, exactly as the route does.
  let signal!: () => void
  const request = new Promise<void>((resolve) => (signal = resolve))
  const outside = request.then(() => {
    expect(() => Instance.directory).toThrow()
    return SessionPrompt.pauseForRestart()
  })
  try {
    await Instance.provide({
      directory: tmp.path,
      init: async () => {
        await trustProject()
        await Provider.invalidate()
      },
      fn: async () => {
        const session = await Session.create({ title: "Restart pause" })
        const turn = SessionPrompt.prompt({
          sessionID: session.id,
          model: { providerID: STRESS_PROVIDER_ID, modelID: STRESS_PROVIDER_MODEL },
          agent: "research",
          delegation: false,
          system: MARKER,
          parts: [{ type: "text", text: "Write the analysis." }],
        })
        const pending = await pendingToolPart(session.id)

        // The person chose "Pause and restart" while this turn was streaming.
        signal()
        expect(await outside).toBe(1)
        const result = await turn
        if (result.info.role !== "assistant") throw new Error("the turn did not produce an assistant message")
        // Left unfinished on purpose: the shape resumeInterrupted looks for.
        expect(result.info.error).toBeUndefined()
        expect(result.info.time.completed).toBeUndefined()
        const parts = await MessageV2.parts(result.info.id)
        const closed = parts.find((part): part is MessageV2.ToolPart => part.type === "tool" && part.id === pending.id)
        if (!closed || closed.state.status !== "error")
          throw new Error(`pending call was not closed: ${JSON.stringify(closed)}`)
        expect(closed.state.error).toContain("Paused to install an update")
        expect(SessionPrompt.activeCount()).toBe(0)
        expect(SessionPrompt.interrupted(await Session.messages({ sessionID: session.id }))).toBe(true)

        // The next process boots and continues the turn where it stopped.
        expect(await SessionPrompt.resumeInterrupted()).toEqual([session.id])
        const deadline = Date.now() + 10_000
        while (Date.now() < deadline) {
          const last = (await Session.messages({ sessionID: session.id })).at(-1)
          if (last?.info.role === "assistant" && last.info.time.completed && !last.info.error) break
          await Bun.sleep(25)
        }
        const last = (await Session.messages({ sessionID: session.id })).at(-1)!
        if (last.info.role !== "assistant") throw new Error("the resumed turn did not answer")
        expect(last.info.time.completed).toBeDefined()
        expect(last.parts.some((part) => part.type === "text" && part.text.includes("Picked the task back up"))).toBe(
          true,
        )
        expect(mainRequests).toBe(2)
      },
    })
  } finally {
    for (const writer of open) await writer.close().catch(() => undefined)
  }
}, 30_000)
