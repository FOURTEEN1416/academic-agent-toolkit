import { expect, test } from "bun:test"
import { Instance } from "../../src/project/instance"
import { Session } from "../../src/session"
import { SessionPrompt } from "../../src/session/prompt"
import { tmpdir, trustProject } from "../fixture/fixture"
import { STRESS_PROVIDER_ID, STRESS_PROVIDER_MODEL, stressProviderConfig } from "../fixture/stress-provider"

function provider() {
  const requests: unknown[] = []
  const server = Bun.serve({
    hostname: "127.0.0.1",
    port: 0,
    async fetch(request) {
      requests.push(await request.json())
      const chunk = (delta: Record<string, unknown>, finish: string | null) =>
        `data: ${JSON.stringify({
          id: "chatcmpl-arguments",
          object: "chat.completion.chunk",
          created: 1,
          model: STRESS_PROVIDER_MODEL,
          choices: [{ index: 0, delta, finish_reason: finish }],
        })}\n\n`
      return new Response(
        chunk({ role: "assistant", content: "ACKNOWLEDGED" }, null) + chunk({}, "stop") + "data: [DONE]\n\n",
        {
          headers: { "content-type": "text/event-stream" },
        },
      )
    },
  })
  const config = stressProviderConfig(`${server.url.origin}/v1`)
  return {
    server,
    requests,
    config: {
      ...config,
      agent: { title: { disable: true } },
      command: { verbatim: { template: "Explain: $ARGUMENTS" } },
    },
  }
}

function sent(body: unknown) {
  const messages = (body as { messages?: unknown }).messages
  if (!Array.isArray(messages)) return ""
  return messages
    .map((message) => (message as { content?: unknown }).content)
    .map((content) => (typeof content === "string" ? content : ""))
    .join("\n")
}

test("$ARGUMENTS reaches the model verbatim, including the dollar sequences a replacement string expands", async () => {
  const fixture = provider()
  using server = fixture.server
  await using tmp = await tmpdir({ git: true, config: fixture.config })
  await Instance.provide({
    directory: tmp.path,
    init: trustProject,
    fn: async () => {
      const session = await Session.create({})
      // $$ , $& and $' are replacement patterns, so a string replacement
      // rewrites them to $, $ARGUMENTS and the empty tail of the template.
      const verbatim = "$$alpha + beta$$ with $& and $' kept"
      const result = await SessionPrompt.command({
        sessionID: session.id,
        model: `${STRESS_PROVIDER_ID}/${STRESS_PROVIDER_MODEL}`,
        command: "verbatim",
        arguments: verbatim,
      })
      expect(result.info.role === "assistant" && result.info.error).toBeUndefined()
      expect(sent(fixture.requests[0])).toContain("Explain: " + verbatim)
    },
  })
}, 30_000)
