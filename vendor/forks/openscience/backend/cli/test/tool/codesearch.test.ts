import { afterEach, expect, test } from "bun:test"
import { CodeSearchTool } from "../../src/tool/codesearch"

const ctx = {
  sessionID: "test-session",
  messageID: "test-message",
  callID: "test-call",
  agent: "test-agent",
  abort: AbortSignal.any([]),
  messages: [],
  metadata: () => {},
  ask: async () => {},
}

const original = globalThis.fetch
afterEach(() => {
  globalThis.fetch = original
})

interface Request {
  url: string
  body: {
    method: string
    params: { name: string; arguments: { query: string; objective: string; numResults: number } }
  }
}

function reply(message: object) {
  const requests: Request[] = []
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    requests.push({ url: String(input), body: JSON.parse(String(init?.body)) })
    return new Response(`event: message\ndata: ${JSON.stringify({ ...message, jsonrpc: "2.0", id: 1 })}\n\n`, {
      headers: { "content-type": "text/event-stream" },
    })
  }) as typeof fetch
  return requests
}

async function search(args: Record<string, unknown>) {
  const tool = await CodeSearchTool.init()
  return tool.execute(args as Parameters<typeof tool.execute>[0], ctx)
}

test("calls Exa's web search with a code-steering objective and returns every text part", async () => {
  const requests = reply({
    result: {
      content: [
        { type: "text", text: "Title: pandas.DataFrame.loc\nURL: https://pandas.pydata.org/docs/loc.html" },
        { type: "text", text: "Title: Boolean indexing\nURL: https://pandas.pydata.org/docs/indexing.html" },
      ],
    },
  })
  const result = await search({ query: "pandas DataFrame filtering" })
  expect(requests).toHaveLength(1)
  expect(requests[0].url).toBe("https://mcp.exa.ai/mcp")
  expect(requests[0].body.method).toBe("tools/call")
  expect(requests[0].body.params.name).toBe("web_search_exa")
  expect(requests[0].body.params.arguments).toMatchObject({ query: "pandas DataFrame filtering", numResults: 5 })
  expect(requests[0].body.params.arguments.objective).toContain("documentation")
  expect(result.output).toContain("https://pandas.pydata.org/docs/loc.html")
  expect(result.output).toContain("https://pandas.pydata.org/docs/indexing.html")
})

test("a tool result flagged isError is a tool error carrying the server's text", async () => {
  reply({
    result: {
      content: [{ type: "text", text: "MCP error -32602: Tool get_code_context_exa not found" }],
      isError: true,
    },
  })
  await expect(search({ query: "React useState" })).rejects.toThrow("Tool get_code_context_exa not found")
})

test("a JSON-RPC error is a tool error carrying the server's message", async () => {
  reply({ error: { code: -32601, message: "Method not found" } })
  await expect(search({ query: "React useState" })).rejects.toThrow("(-32601): Method not found")
})

test("an empty result still reads as nothing found", async () => {
  reply({ result: { content: [] } })
  const result = await search({ query: "React useState" })
  expect(result.output).toContain("No code snippets or documentation found")
})

test("numResults is bounded to what the search returns", async () => {
  const requests = reply({ result: { content: [{ type: "text", text: "Title: x" }] } })
  await search({ query: "Express.js middleware", numResults: 10 })
  expect(requests[0].body.params.arguments.numResults).toBe(10)
  await expect(search({ query: "Express.js middleware", numResults: 11 })).rejects.toThrow()
})
