import fs from "node:fs/promises"
import { Server } from "@modelcontextprotocol/sdk/server/index.js"
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js"
import { CallToolRequestSchema, ListToolsRequestSchema } from "@modelcontextprotocol/sdk/types.js"

const marker = process.env.OPENSCIENCE_MCP_CANCEL_MARKER
if (!marker) throw new Error("OPENSCIENCE_MCP_CANCEL_MARKER is required")

const server = new Server({ name: "cancellation-test", version: "1.0.0" }, { capabilities: { tools: {} } })

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "hang",
      description: "Runs until the caller cancels it",
      inputSchema: { type: "object", properties: {}, additionalProperties: false },
    },
  ],
}))

// The handler never settles on its own. Its only exit is extra.signal, which
// the server SDK aborts when the client sends notifications/cancelled, so the
// recorded reason is proof the cancellation crossed the protocol boundary.
server.setRequestHandler(CallToolRequestSchema, async (_request, extra) => {
  await fs.appendFile(marker, "started\n")
  await new Promise((resolve) => extra.signal.addEventListener("abort", resolve, { once: true }))
  await fs.appendFile(marker, `cancelled ${String(extra.signal.reason)}\n`)
  return { content: [{ type: "text", text: "cancelled" }] }
})

await server.connect(new StdioServerTransport())
