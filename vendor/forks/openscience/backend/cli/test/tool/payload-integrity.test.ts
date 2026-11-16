import { expect, test } from "bun:test"
import path from "node:path"
import { WriteTool } from "../../src/tool/write"
import { ReadTool } from "../../src/tool/read"
import { EditTool } from "../../src/tool/edit"
import { ApplyPatchTool } from "../../src/tool/apply_patch"
import { PayloadIntegrity } from "../../src/tool/payload-integrity"
import { MessageV2 } from "../../src/session/message-v2"
import { Instance } from "../../src/project/instance"
import { Session } from "../../src/session"
import { Provider } from "../../src/provider/provider"
import { FileTime } from "../../src/file/time"
import type { Tool } from "../../src/tool/tool"
import { tmpdir } from "../fixture/fixture"

const content = `# Complete research plan\n${"Measure λ and 🧬 exactly, retaining every sample identifier.\n".repeat(40)}`
const preview = PayloadIntegrity.legacyPreview(content)

async function fixture(run: (context: Tool.Context, record: typeof history) => Promise<void>) {
  await using tmp = await tmpdir({ config: { lsp: false, provider: { openai: { options: { apiKey: "test" } } } } })
  await Instance.provide({
    directory: tmp.path,
    fn: async () => {
      const session = await Session.create({ title: "Payload integrity" })
      try {
        await run(
          {
            sessionID: session.id,
            messageID: "current",
            agent: "research",
            abort: new AbortController().signal,
            messages: [],
            metadata: () => {},
            ask: async () => {},
          },
          history,
        )
      } finally {
        try {
          await Session.remove(session.id)
        } finally {
          await Instance.dispose()
        }
      }
    },
  })
}

function history(
  context: Tool.Context,
  tool: string,
  input: Record<string, unknown>,
  result: { title: string; output: string; metadata: Record<string, unknown> },
): MessageV2.WithParts {
  const id = `history-${context.messages.length}`
  return {
    info: {
      id,
      sessionID: context.sessionID,
      role: "assistant",
      parentID: "user",
      time: { created: 1, completed: 2 },
      modelID: "gpt-4o",
      providerID: "openai",
      mode: "research",
      agent: "research",
      path: { cwd: Instance.directory, root: Instance.worktree },
      cost: 0,
      tokens: { input: 0, output: 0, reasoning: 0, cache: { read: 0, write: 0 } },
    },
    parts: [
      {
        id: `part-${id}`,
        sessionID: context.sessionID,
        messageID: id,
        callID: `call-${id}`,
        type: "tool",
        tool,
        state: { status: "completed", input, ...result, time: { start: 1, end: 2, compacted: 3 } },
      },
    ],
  }
}

test("long write/read history stays exact, and copying its legacy preview cannot create or overwrite files", async () => {
  await fixture(async (context, record) => {
    const source = path.join(Instance.directory, "plan.md")
    const writer = await WriteTool.init()
    const args = { filePath: source, content }
    context.messages.push(record(context, "write", args, await writer.execute(args, context)))
    const reader = await ReadTool.init()
    const read = await reader.execute({ filePath: source }, context)
    expect(read.output).toContain("retaining every sample identifier")
    context.messages.push(record(context, "read", { filePath: source }, read))

    const model = await Provider.getModel("openai", "gpt-4o")
    const rendered = JSON.stringify(MessageV2.toModelMessages(context.messages, model))
    expect(rendered).toContain(JSON.stringify(content).slice(1, -1))
    expect(rendered).not.toContain("…[+")
    expect(context.messages[0].parts[0]).toMatchObject({ state: { input: args } })

    const asks: string[] = []
    context.ask = async (request) => {
      asks.push(request.permission)
    }
    const destination = path.join(Instance.directory, "copied.md")
    await expect(writer.execute({ filePath: destination, content: preview }, context)).rejects.toThrow(
      "shortened historical argument",
    )
    expect(await Bun.file(destination).exists()).toBe(false)
    await expect(writer.execute({ filePath: source, content: preview }, context)).rejects.toThrow("No action was taken")
    expect(await Bun.file(source).text()).toBe(content)
    expect(asks).toEqual([])
  })
})

test("edit refuses an embedded legacy preview before changing a file", async () => {
  await fixture(async (context, record) => {
    const target = path.join(Instance.directory, "report.md")
    const writer = await WriteTool.init()
    const args = { filePath: target, content }
    context.messages.push(record(context, "write", args, await writer.execute(args, context)))
    const editor = await EditTool.init()
    await expect(
      editor.execute({ filePath: target, oldString: content, newString: `# Replacement\n${preview}\n` }, context),
    ).rejects.toThrow("shortened historical argument")
    expect(await Bun.file(target).text()).toBe(content)
  })
})

test("patch refuses a copied preview before applying any file in the transaction", async () => {
  await fixture(async (context, record) => {
    context.messages.push(record(context, "write", { content }, { title: "source", output: "written", metadata: {} }))
    const patch = [
      "*** Begin Patch",
      `*** Add File: ${path.join(Instance.directory, "valid.md")}`,
      "+Complete content",
      `*** Add File: ${path.join(Instance.directory, "shortened.md")}`,
      ...preview.split("\n").map((line) => `+${line}`),
      "*** End Patch",
    ].join("\n")
    await expect((await ApplyPatchTool.init()).execute({ patchText: patch }, context)).rejects.toThrow(
      "shortened historical argument",
    )
    expect(await Bun.file(path.join(Instance.directory, "valid.md")).exists()).toBe(false)
    expect(await Bun.file(path.join(Instance.directory, "shortened.md")).exists()).toBe(false)
  })
})

test("literal marker documentation can be written, edited, and patched", async () => {
  await fixture(async (context, record) => {
    context.messages.push(record(context, "write", { content }, { title: "source", output: "written", metadata: {} }))
    const target = path.join(Instance.directory, "markers.md")
    const literal = "# Marker reference\n`…[+1988 chars]` is a literal example in this document.\n"
    await (await WriteTool.init()).execute({ filePath: target, content: literal }, context)
    expect(await Bun.file(target).text()).toBe(literal)
    await (
      await EditTool.init()
    ).execute({ filePath: target, oldString: "literal example", newString: "documented literal example" }, context)
    await (
      await ApplyPatchTool.init()
    ).execute(
      {
        patchText: `*** Begin Patch\n*** Update File: ${target}\n@@\n-# Marker reference\n+# Literal markers\n*** End Patch`,
      },
      context,
    )
    expect(await Bun.file(target).text()).toContain("`…[+1988 chars]` is a documented literal example")

    // A document may already quote even an exact historical preview. Preserve
    // that evidence while editing surrounding prose, including whole-file writes.
    const quoted = `# Historical evidence\n${preview}\nExplanation.\n`
    await Bun.write(target, quoted)
    FileTime.read(context.sessionID, target)
    await (
      await WriteTool.init()
    ).execute({ filePath: target, content: quoted.replace("Explanation", "Background") }, context)
    await (
      await EditTool.init()
    ).execute({ filePath: target, oldString: "Background", newString: "Verified background" }, context)
    await (
      await ApplyPatchTool.init()
    ).execute(
      {
        patchText: `*** Begin Patch\n*** Update File: ${target}\n@@\n-Verified background.\n+Verified context.\n*** End Patch`,
      },
      context,
    )
    expect(await Bun.file(target).text()).toBe(quoted.replace("Explanation", "Verified context"))
  })
})
