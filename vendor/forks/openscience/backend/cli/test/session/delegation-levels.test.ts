import { expect, test } from "bun:test"
import { Instance } from "../../src/project/instance"
import { Session } from "../../src/session"
import { SessionPrompt } from "../../src/session/prompt"
import { tmpdir, trustProject } from "../fixture/fixture"
import { STRESS_PROVIDER_ID, STRESS_PROVIDER_MODEL, stressProviderConfig } from "../fixture/stress-provider"

type Request = {
  messages: Array<{ role: string; content: unknown }>
  tools?: Array<{ function: { name: string } }>
}

/** Answers every request with one line and keeps what it was offered. */
function capture() {
  const requests: Request[] = []
  const chunk = (delta: object, finish: string | null) =>
    `data: ${JSON.stringify({
      id: "chatcmpl-levels",
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
      requests.push((await request.json()) as Request)
      return new Response(
        chunk({ role: "assistant", content: "Noted." }, null) + chunk({}, "stop") + "data: [DONE]\n\n",
        { headers: { "content-type": "text/event-stream" } },
      )
    },
  })
  return { requests, instance }
}

const system = (request: Request) =>
  request.messages
    .filter((message) => message.role === "system")
    .map((message) => (typeof message.content === "string" ? message.content : JSON.stringify(message.content)))
    .join("\n")

test("the composer's delegation levels reach the model: Off removes the Task tool, Auto and High keep it with their own posture", async () => {
  const fixture = capture()
  try {
    await using tmp = await tmpdir({ git: true, config: stressProviderConfig(`${fixture.instance.url.origin}/v1`) })
    await Instance.provide({
      directory: tmp.path,
      init: trustProject,
      fn: async () => {
        const run = async (level: "off" | "standard" | "high") => {
          const session = await Session.create({ workspace: "project" })
          const before = fixture.requests.length
          await SessionPrompt.prompt({
            sessionID: session.id,
            model: { providerID: STRESS_PROVIDER_ID, modelID: STRESS_PROVIDER_MODEL },
            agent: "research",
            delegation: level !== "off",
            delegationSettings: { level, autonomy: "balanced" },
            parts: [{ type: "text", text: "Say hello." }],
          })
          // The turn's own request carries the tool list; the title request
          // that follows it carries none.
          const request = fixture.requests.slice(before).findLast((item) => (item.tools ?? []).length > 0)!
          return { tools: (request.tools ?? []).map((tool) => tool.function.name), system: system(request) }
        }

        const off = await run("off")
        expect(off.tools).not.toContain("task")
        expect(off.system).toContain("Automatic delegation is off")

        const auto = await run("standard")
        expect(auto.tools).toContain("task")
        expect(auto.system).toContain("Delegation is Auto")
        expect(auto.system).not.toContain("Parallelize independent branches freely")

        const high = await run("high")
        expect(high.tools).toContain("task")
        expect(high.system).toContain("Delegation is High")
        expect(high.system).toContain("Parallelize independent branches freely")
      },
    })
  } finally {
    fixture.instance.stop(true)
  }
})
