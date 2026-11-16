import { afterEach, expect, test } from "bun:test"
import path from "node:path"
import { Experiments } from "../../src/experiments"
import { HarnessState } from "../../src/harness/state"
import { Instance } from "../../src/project/instance"
import { Session } from "../../src/session"
import { SessionPrompt } from "../../src/session/prompt"
import { tmpdir, trustProject } from "../fixture/fixture"
import { STRESS_PROVIDER_ID, STRESS_PROVIDER_MODEL, stressProviderConfig } from "../fixture/stress-provider"

afterEach(() => HarnessState.reset())

/** Answers every request with one line and keeps the messages it was sent. */
function provider() {
  const requests: Array<{ messages: Array<{ role: string; content: unknown }> }> = []
  const chunk = (delta: object, finish: string | null) =>
    `data: ${JSON.stringify({
      id: "chatcmpl-study",
      object: "chat.completion.chunk",
      created: 1,
      model: STRESS_PROVIDER_MODEL,
      choices: [{ index: 0, delta, finish_reason: finish }],
      ...(finish ? { usage: { prompt_tokens: 10, completion_tokens: 2, total_tokens: 12 } } : {}),
    })}\n\n`
  const instance = Bun.serve({
    hostname: "127.0.0.1",
    port: 0,
    async fetch(request) {
      requests.push(await request.json())
      return new Response(
        chunk({ role: "assistant", content: "Noted." }, null) + chunk({}, "stop") + "data: [DONE]\n\n",
        { headers: { "content-type": "text/event-stream" } },
      )
    },
  })
  return { requests, instance }
}

const carriers = (messages: Array<{ role: string; content: unknown }>) =>
  messages
    .filter((message) => message.role === "user")
    .map((message) => String(message.content))
    .filter((content) => content.includes('<system-reminder kind="status">'))

test("the study's state is appended when it changes, not when the model moves its own counts", async () => {
  const fixture = provider()
  try {
    await using tmp = await tmpdir({ git: true, config: stressProviderConfig(`${fixture.instance.url.origin}/v1`) })
    await Instance.provide({
      directory: tmp.path,
      init: trustProject,
      fn: async () => {
        const session = await Session.create({ workspace: "project" })
        const study = await Experiments.createStudy({
          sessionID: session.id,
          name: "Churn climb",
          purpose: "p",
          metric: "cv_roc_auc",
          direction: "maximize",
          root: path.join(tmp.path, "study"),
          concurrency: 2,
          budget: { maxRuns: 12 },
        })
        const turn = async (text: string) => {
          const before = fixture.requests.length
          await SessionPrompt.prompt({
            sessionID: session.id,
            model: { providerID: STRESS_PROVIDER_ID, modelID: STRESS_PROVIDER_MODEL },
            agent: "research",
            parts: [{ type: "text", text }],
          })
          // The title request quotes the prompt too and may land first; the
          // research request is the one under the research system prompt.
          const main = fixture.requests
            .slice(before)
            .filter((request) => JSON.stringify(request).includes(text))
            .find((request) => !JSON.stringify(request.messages[0]).includes("title generator"))!
          return carriers(main.messages)
        }

        // The first turn carries the study's state once, as a readable line
        // that names the study rather than its identifier.
        const first = await turn("Start the study.")
        expect(first).toHaveLength(1)
        expect(first[0]).toContain('Study "Churn climb" is running: maximize cv_roc_auc; baseline none; best none')
        expect(first[0]).not.toMatch(/^[^\n]*stu_/)

        // Queueing ideas changes the counts the model itself moves: nothing new.
        await Experiments.proposeIdeas(study.id, [
          { title: "a", description: "d", why: "w", ev: 0.1 },
          { title: "b", description: "d", why: "w", ev: 0.2 },
        ])
        const second = await turn("Continue.")
        expect(second).toHaveLength(1)

        // A change of state (the study paused) is worth a new line.
        await Experiments.updateStudy(study.id, { status: "paused" })
        const third = await turn("And now?")
        expect(third).toHaveLength(2)
        expect(third[1]).toContain('Study "Churn climb" is paused')
      },
    })
  } finally {
    fixture.instance.stop(true)
  }
})
