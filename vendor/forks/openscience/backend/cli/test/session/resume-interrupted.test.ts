import { expect, test } from "bun:test"
import { Identifier } from "../../src/id/id"
import { Instance } from "../../src/project/instance"
import { Session } from "../../src/session"
import { SessionPrompt } from "../../src/session/prompt"
import { tmpdir, trustProject } from "../fixture/fixture"
import { STRESS_PROVIDER_ID, STRESS_PROVIDER_MODEL, stressProviderConfig } from "../fixture/stress-provider"

/** Answers every request with one line. */
function provider() {
  let calls = 0
  const chunk = (delta: object, finish: string | null) =>
    `data: ${JSON.stringify({
      id: "chatcmpl-resume",
      object: "chat.completion.chunk",
      created: 1,
      model: STRESS_PROVIDER_MODEL,
      choices: [{ index: 0, delta, finish_reason: finish }],
      ...(finish ? { usage: { prompt_tokens: 10, completion_tokens: 2, total_tokens: 12 } } : {}),
    })}\n\n`
  const instance = Bun.serve({
    hostname: "127.0.0.1",
    port: 0,
    async fetch() {
      calls++
      return new Response(
        chunk({ role: "assistant", content: "Picked the work back up." }, null) +
          chunk({}, "stop") +
          "data: [DONE]\n\n",
        { headers: { "content-type": "text/event-stream" } },
      )
    },
  })
  return { instance, calls: () => calls }
}

/** A transcript the way a killed process leaves it: the user's prompt, then an
 * assistant message that never completed, its Task call still "running". */
async function interruptedTurn(sessionID: string, directory: string, worker: string, at: number) {
  const user = Identifier.ascending("message")
  await Session.updateMessage({
    id: user,
    sessionID,
    role: "user",
    time: { created: at },
    agent: "research",
    effort: "normal",
    model: { providerID: STRESS_PROVIDER_ID, modelID: STRESS_PROVIDER_MODEL },
  })
  await Session.updatePart({
    id: Identifier.ascending("part"),
    messageID: user,
    sessionID,
    type: "text",
    text: "Train the best churn model you can.",
  })
  const assistant = Identifier.ascending("message")
  await Session.updateMessage({
    id: assistant,
    sessionID,
    role: "assistant",
    parentID: user,
    mode: "research",
    agent: "research",
    path: { cwd: directory, root: directory },
    cost: 0,
    tokens: { input: 100, output: 10, reasoning: 0, cache: { read: 0, write: 0 } },
    modelID: STRESS_PROVIDER_MODEL,
    providerID: STRESS_PROVIDER_ID,
    time: { created: at + 1 },
  })
  await Session.updatePart({
    id: Identifier.ascending("part"),
    messageID: assistant,
    sessionID,
    type: "tool",
    tool: "task",
    callID: "call_review",
    state: {
      status: "running",
      input: { description: "Review churn evaluation", prompt: "Review train.py", subagent_type: "ml" },
      title: "Review churn evaluation",
      time: { start: at + 2 },
      metadata: { sessionId: worker },
    },
  })
  return { user, assistant }
}

test("a restart resumes the lead mid-turn, closes its orphaned Task call, and settles the worker it left behind", async () => {
  const fixture = provider()
  try {
    await using tmp = await tmpdir({ git: true, config: stressProviderConfig(`${fixture.instance.url.origin}/v1`) })
    await Instance.provide({
      directory: tmp.path,
      init: trustProject,
      fn: async () => {
        const now = Date.now()
        const lead = await Session.create({ workspace: "project" })
        const worker = await Session.create({ parentID: lead.id, title: "Review churn evaluation (@ml subagent)" })
        const turn = await interruptedTurn(lead.id, tmp.path, worker.id, now - 60_000)
        // The worker was mid-request too: an assistant message with nothing in it yet.
        await Session.updateMessage({
          id: Identifier.ascending("message"),
          sessionID: worker.id,
          role: "assistant",
          parentID: "msg_worker_user",
          mode: "ml",
          agent: "ml",
          path: { cwd: tmp.path, root: tmp.path },
          cost: 0,
          tokens: { input: 0, output: 0, reasoning: 0, cache: { read: 0, write: 0 } },
          modelID: STRESS_PROVIDER_MODEL,
          providerID: STRESS_PROVIDER_ID,
          time: { created: now - 30_000 },
        })
        // A session that finished long ago is not touched.
        const settled = await Session.create({ workspace: "project" })
        await interruptedTurn(settled.id, tmp.path, worker.id, now - 2 * 24 * 60 * 60_000)
        await Session.update(
          settled.id,
          (draft) => {
            draft.time.updated = now - 2 * 24 * 60 * 60_000
          },
          { touch: false },
        )

        const resumed = await SessionPrompt.resumeInterrupted(now)
        expect(resumed).toEqual([lead.id])

        // The worker's open message is closed with the reason; nobody re-runs it.
        const workerMessages = await Session.messages({ sessionID: worker.id })
        const workerLast = workerMessages.at(-1)!.info
        expect(workerLast.role === "assistant" && workerLast.time.completed).toBe(now)
        expect(workerLast.role === "assistant" && JSON.stringify(workerLast.error)).toContain("server restarted")

        // The lead's loop ran again: the Task call reads as interrupted, and
        // the model answered on top of that.
        await Bun.sleep(50)
        const deadline = Date.now() + 10_000
        while (Date.now() < deadline) {
          const messages = await Session.messages({ sessionID: lead.id })
          const last = messages.at(-1)!.info
          if (last.role === "assistant" && last.time.completed && last.id !== turn.assistant) break
          await Bun.sleep(50)
        }
        const messages = await Session.messages({ sessionID: lead.id })
        const interrupted = messages.find((message) => message.info.id === turn.assistant)!
        const task = interrupted.parts.find((part) => part.type === "tool")
        expect(task?.type === "tool" && task.state.status).toBe("error")
        expect(task?.type === "tool" && task.state.status === "error" && task.state.error).toContain("interrupted")
        expect(interrupted.info.role === "assistant" && interrupted.info.time.completed).toBeDefined()
        const last = messages.at(-1)!
        expect(last.info.role).toBe("assistant")
        expect(last.info.id).not.toBe(turn.assistant)
        expect(last.parts.some((part) => part.type === "text" && part.text.includes("Picked the work back up"))).toBe(
          true,
        )
        // One model call for the resumed turn (the title request is separate).
        expect(fixture.calls()).toBeGreaterThanOrEqual(1)

        // The old session was left alone.
        const old = await Session.messages({ sessionID: settled.id })
        expect(SessionPrompt.interrupted(old)).toBe(true)
      },
    })
  } finally {
    fixture.instance.stop(true)
  }
})
