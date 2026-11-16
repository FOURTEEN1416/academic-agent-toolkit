import { describe, expect, test } from "bun:test"
import { parseCodeReply } from "../../src/tool/codesearch"

const result = {
  jsonrpc: "2.0",
  id: 1,
  result: { content: [{ type: "text", text: "useEffect docs" }] },
}

describe("code search reply parsing", () => {
  test("reads an SSE frame", () => {
    expect(parseCodeReply(`data: ${JSON.stringify(result)}\n\n`, "text/event-stream")).toBe("useEffect docs")
  })

  test("reads a plain JSON body, which is the first type the request asks for", () => {
    expect(parseCodeReply(JSON.stringify(result), "application/json")).toBe("useEffect docs")
    expect(parseCodeReply(JSON.stringify(result), "application/json; charset=utf-8")).toBe("useEffect docs")
  })

  test("reads an SSE frame with no space after the colon", () => {
    // Legal per the SSE grammar, and the previous reader required the space.
    expect(parseCodeReply(`data:${JSON.stringify(result)}\n\n`, "text/event-stream")).toBe("useEffect docs")
  })

  test("a rejected call is an error, not an empty search", () => {
    const rejected = JSON.stringify({ jsonrpc: "2.0", id: 1, error: { code: -32602, message: "invalid params" } })
    expect(() => parseCodeReply(rejected, "application/json")).toThrow("invalid params")
    expect(() => parseCodeReply(`data: ${rejected}\n\n`, "text/event-stream")).toThrow("invalid params")
  })

  test("a reply that really carried no content is undefined", () => {
    expect(parseCodeReply("", "text/event-stream")).toBeUndefined()
    expect(parseCodeReply("data: [DONE]\n\n", "text/event-stream")).toBeUndefined()
    expect(
      parseCodeReply(JSON.stringify({ jsonrpc: "2.0", id: 1, result: { content: [] } }), "application/json"),
    ).toBeUndefined()
  })
})
