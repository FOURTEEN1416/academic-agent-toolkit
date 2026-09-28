import { describe, expect, test } from "bun:test"
import { formatConnectorCommand, parseConnectorCommand } from "./connector-command"

describe("connector command input", () => {
  test("parses normal local MCP commands into argv", () => {
    expect(parseConnectorCommand("npx -y @modelcontextprotocol/server-filesystem .")).toEqual([
      "npx",
      "-y",
      "@modelcontextprotocol/server-filesystem",
      ".",
    ])
  })

  test("preserves quoted arguments without invoking a shell", () => {
    expect(parseConnectorCommand(`bun "/tmp/server with spaces.mjs" --name 'science tools'`)).toEqual([
      "bun",
      "/tmp/server with spaces.mjs",
      "--name",
      "science tools",
    ])
  })

  test("round-trips argv values with spaces, quotes, and empty arguments", () => {
    const command = ["bun", "/tmp/server with spaces.mjs", "--label", `say "hello"`, "line one\nline two", ""]
    expect(parseConnectorCommand(formatConnectorCommand(command))).toEqual(command)
  })

  test("rejects unfinished quoted and escaped commands", () => {
    expect(() => parseConnectorCommand(`bun "server.mjs`)).toThrow(/unclosed/)
    expect(() => parseConnectorCommand("bun server.mjs\\")).toThrow(/unfinished escape/)
  })
})
