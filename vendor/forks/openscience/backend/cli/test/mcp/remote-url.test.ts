import { expect, test } from "bun:test"
import path from "node:path"
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js"
import { WebStandardStreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/webStandardStreamableHttp.js"
import { Config } from "../../src/config/config"
import { McpRemoteUrl } from "../../src/mcp/remote-url"
import { tmpdir } from "../fixture/fixture"
import { spawn } from "../fixture/spawn"

function issue(url: string) {
  const result = Config.McpRemote.safeParse({ type: "remote", url })
  return result.success ? undefined : result.error.issues.map((item) => item.message).join("; ")
}

test("remote MCP endpoints require confidential transports and header-based credentials", () => {
  for (const url of [
    "https://mcp.example/tools",
    "http://127.0.0.1:4096/mcp",
    "http://localhost:4096/mcp",
    "https://mcp.exa.ai/mcp?tools=web_search_exa,web_fetch_exa,agent_run,web_search_advanced_exa",
    "https://mcp.example/mcp?max_tokens=4000&author=lab&design=compact",
  ]) {
    expect(issue(url)).toBeUndefined()
  }
  expect(issue("http://mcp.example/tools")).toContain("HTTPS")
  expect(issue("https://user:password@mcp.example/tools")).toContain("URL credentials")
  expect(issue("https://mcp.example/tools#token")).toContain("fragment")
  expect(issue("https://mcp.example/tools?tools=search#section")).toContain("fragment")
})

test("remote MCP endpoints refuse credential-named query parameters by name, never by value", () => {
  for (const name of [
    "api_key",
    "token",
    "Authorization",
    "apikey",
    "api-key",
    "apiKey",
    "exaApiKey",
    "X-Api-Key",
    "access_token",
    "accessToken",
    "client_secret",
    "password",
    "passwd",
    "auth",
    "sig",
    "X-Amz-Signature",
    "session",
    "credential",
    "bearer",
    "jwt",
    "key",
    "secret",
  ]) {
    const url = `https://mcp.example/mcp?tools=web_search&${name}=plaintext-value`
    const message = issue(url)
    expect(message, name).toContain(`"${name}"`)
    expect(message, name).toContain("header")
    expect(message, name).not.toContain("plaintext-value")
    expect(() => McpRemoteUrl.endpoint(url)).toThrow(`"${name}"`)
  }
})

test("a remote MCP URL with a tool selection is saved, loaded and connected unchanged", async () => {
  const query = "?tools=web_search_exa,web_fetch_exa"
  const requests: { search: string; key: string | null }[] = []
  using server = Bun.serve({
    hostname: "127.0.0.1",
    port: 0,
    async fetch(request) {
      requests.push({ search: new URL(request.url).search, key: request.headers.get("x-api-key") })
      const mcp = new McpServer({ name: "query-test", version: "1.0.0" })
      mcp.registerTool("web_search_exa", { description: "Search" }, async () => ({
        content: [{ type: "text", text: "ok" }],
      }))
      const transport = new WebStandardStreamableHTTPServerTransport({ enableJsonResponse: true })
      await mcp.connect(transport)
      return transport.handleRequest(request)
    },
  })
  const url = `http://127.0.0.1:${server.port}/mcp${query}`
  await using tmp = await tmpdir()
  const runner = path.join(tmp.path, "connect.ts")
  // A child process keeps this connection clear of transport mocks that other
  // files in this directory install with mock.module.
  await Bun.write(
    runner,
    `
import { Config } from ${JSON.stringify(new URL("../../src/config/config.ts", import.meta.url).href)}
import { MCP } from ${JSON.stringify(new URL("../../src/mcp/index.ts", import.meta.url).href)}
import { Instance } from ${JSON.stringify(new URL("../../src/project/instance.ts", import.meta.url).href)}

const result = await Instance.provide({
  directory: process.argv[2],
  fn: async () => {
    const url = process.argv[3]
    await Config.setMcp("exa", { type: "remote", url, headers: { "x-api-key": "header-secret" }, oauth: false }, "project")
    const saved = (await Config.get()).mcp?.exa
    await MCP.connect("exa")
    const detail = await MCP.inspect("exa")
    await MCP.disconnect("exa")
    return { saved, status: detail.status, tools: detail.tools.map((tool) => tool.name) }
  },
})
process.stdout.write(JSON.stringify(result))
process.exit(0)
`,
  )
  const proc = spawn([process.execPath, runner, tmp.path, url], { cwd: tmp.path, stdout: "pipe", stderr: "pipe" })
  const [output, error, exit] = await Promise.all([
    new Response(proc.stdout).text(),
    new Response(proc.stderr).text(),
    proc.exited,
  ])
  expect(exit, error).toBe(0)
  const result = JSON.parse(output)

  expect(result.saved).toMatchObject({ type: "remote", url })
  expect(result.status).toEqual({ status: "connected" })
  expect(result.tools).toEqual(["web_search_exa"])
  expect(requests.length).toBeGreaterThan(0)
  expect(requests.every((request) => request.search === query && request.key === "header-secret")).toBeTrue()
})

test("discovered OAuth URLs use HTTPS except for explicit loopback development", () => {
  expect(() => McpRemoteUrl.network("https://id.example/authorize?state=opaque")).not.toThrow()
  expect(() =>
    McpRemoteUrl.discovered("http://127.0.0.1:4321/token", "http://localhost:4096/mcp", "OAuth token URL"),
  ).not.toThrow()
  expect(() =>
    McpRemoteUrl.discovered("http://127.0.0.1:4321/token", "https://mcp.example/mcp", "OAuth token URL"),
  ).toThrow(/HTTPS/)
  expect(() =>
    McpRemoteUrl.discovered(
      "https://id.example/token",
      "https://mcp.exa.ai/mcp?tools=web_search_exa",
      "OAuth token URL",
    ),
  ).not.toThrow()
  expect(() => McpRemoteUrl.network("http://id.example/token")).toThrow(/HTTPS/)
  expect(() => McpRemoteUrl.network("https://client:secret@id.example/token")).toThrow(/credentials/)
})
