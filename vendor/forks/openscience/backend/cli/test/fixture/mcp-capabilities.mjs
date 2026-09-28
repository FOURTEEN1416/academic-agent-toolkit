import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js"
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js"

const server = new McpServer({ name: "capability-test", version: "1.0.0" })

server.registerTool(
  "echo",
  {
    description: "Echo a value",
  },
  async () => ({
    content: [{ type: "text", text: "ok" }],
  }),
)

server.registerResource(
  "guide",
  "memory://guide",
  {
    description: "Connector guide",
    mimeType: "text/plain",
  },
  async (uri) => ({
    contents: [{ uri: uri.href, text: "guide" }],
  }),
)

server.registerPrompt(
  "review",
  {
    description: "Review a result",
  },
  async () => ({
    messages: [{ role: "user", content: { type: "text", text: "review" } }],
  }),
)

await server.connect(new StdioServerTransport())
