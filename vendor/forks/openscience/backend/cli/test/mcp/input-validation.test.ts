import { describe, expect, test } from "bun:test"
import type { JSONSchema7 } from "ai"
import { MCP } from "../../src/mcp"

describe("MCP input validation", () => {
  const published: JSONSchema7 = {
    type: "object",
    properties: {
      query: { type: "string" },
    },
    required: ["query"],
    additionalProperties: false,
  }
  const schema = MCP.inputSchema("lookup", published)

  test("rejects interrupted provider calls before remote execution", async () => {
    const result = await schema.validate?.({})
    expect(result?.success).toBe(false)
    if (!result || result.success) throw new Error("Incomplete MCP input unexpectedly passed validation")
    expect(result.error.message).toBe(
      "The lookup MCP tool received invalid arguments or incomplete input. No action was taken. Retry with all required fields.",
    )
  })

  test("accepts input matching the published MCP schema", async () => {
    expect(await schema.validate?.({ query: "CERBench" })).toEqual({
      success: true,
      value: { query: "CERBench" },
    })
  })

  test("shared schemas report the name of the tool that received invalid input", async () => {
    const other = MCP.inputSchema("search", structuredClone(published))
    const result = await other.validate?.({})
    expect(result?.success).toBe(false)
    if (!result || result.success) throw new Error("Incomplete MCP input unexpectedly passed validation")
    expect(result.error.message).toBe(
      "The search MCP tool received invalid arguments or incomplete input. No action was taken. Retry with all required fields.",
    )
  })

  test("a changed schema takes effect without changing an earlier tool definition", async () => {
    const updated = MCP.inputSchema("lookup", {
      ...published,
      properties: { query: { type: "integer" } },
    })
    expect((await updated.validate?.({ query: "CERBench" }))?.success).toBe(false)
    expect(await updated.validate?.({ query: 42 })).toEqual({ success: true, value: { query: 42 } })
    expect((await schema.validate?.({ query: "CERBench" }))?.success).toBe(true)
    expect((await schema.validate?.({ query: 42 }))?.success).toBe(false)
  })

  test("reuses the validator when the same tool schema is converted again", () => {
    // MCP.tools() converts every connected tool again on each agent step, each
    // time with a freshly spread schema object. AJV caches compiled schemas by
    // object identity and never evicts them, so compiling per call retains one
    // validator per tool per step for the life of the process.
    const published = (): JSONSchema7 => ({
      type: "object",
      properties: Object.fromEntries(
        Array.from({ length: 12 }, (_, i) => [`field${i}`, { type: "string", minLength: 1 }]),
      ),
      required: ["field0"],
      additionalProperties: false,
    })
    MCP.inputSchema("lookup", published())
    Bun.gc(true)
    const before = process.memoryUsage().heapUsed
    for (let step = 0; step < 2000; step++) MCP.inputSchema("lookup", published())
    Bun.gc(true)
    const retained = process.memoryUsage().heapUsed - before
    // Compiling each time keeps several KB per call (over 10 MB here); reuse
    // keeps nothing beyond the one validator compiled above.
    expect(retained).toBeLessThan(2 * 1024 * 1024)
  })
})
