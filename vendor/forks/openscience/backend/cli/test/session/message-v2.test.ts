import { describe, expect, test } from "bun:test"
import { Identifier } from "../../src/id/id"
import { SessionCompaction } from "../../src/session/compaction"
import { MessageV2 } from "../../src/session/message-v2"
import type { Provider } from "../../src/provider/provider"

const sessionID = "session"
const model: Provider.Model = {
  id: "test-model",
  providerID: "test",
  api: {
    id: "test-model",
    url: "https://example.com",
    npm: "@ai-sdk/openai",
  },
  name: "Test Model",
  capabilities: {
    temperature: true,
    reasoning: false,
    attachment: false,
    toolcall: true,
    input: {
      text: true,
      audio: false,
      image: false,
      video: false,
      pdf: false,
    },
    output: {
      text: true,
      audio: false,
      image: false,
      video: false,
      pdf: false,
    },
    interleaved: false,
  },
  cost: {
    input: 0,
    output: 0,
    cache: {
      read: 0,
      write: 0,
    },
  },
  limit: {
    context: 0,
    input: 0,
    output: 0,
  },
  status: "active",
  options: {},
  headers: {},
  release_date: "2026-01-01",
}

function userInfo(id: string): MessageV2.User {
  return {
    id,
    sessionID,
    role: "user",
    time: { created: 0 },
    agent: "user",
    model: { providerID: "test", modelID: "test" },
    tools: {},
    mode: "",
  } as unknown as MessageV2.User
}

function assistantInfo(
  id: string,
  parentID: string,
  error?: MessageV2.Assistant["error"],
  meta?: { providerID: string; modelID: string },
): MessageV2.Assistant {
  const infoModel = meta ?? { providerID: model.providerID, modelID: model.api.id }
  return {
    id,
    sessionID,
    role: "assistant",
    time: { created: 0 },
    error,
    parentID,
    modelID: infoModel.modelID,
    providerID: infoModel.providerID,
    mode: "",
    agent: "agent",
    path: { cwd: "/", root: "/" },
    cost: 0,
    tokens: {
      input: 0,
      output: 0,
      reasoning: 0,
      cache: { read: 0, write: 0 },
    },
  } as unknown as MessageV2.Assistant
}

function basePart(messageID: string, id: string) {
  return {
    id,
    sessionID,
    messageID,
  }
}

describe("session.message-v2.isContinuing", () => {
  test("tool-calls and unknown mean the agent will keep working", () => {
    expect(MessageV2.isContinuing("tool-calls")).toBe(true)
    expect(MessageV2.isContinuing("unknown")).toBe(true)
  })

  test("stop / length / other finish reasons are a completed turn", () => {
    expect(MessageV2.isContinuing("stop")).toBe(false)
    expect(MessageV2.isContinuing("length")).toBe(false)
    expect(MessageV2.isContinuing("content-filter")).toBe(false)
  })

  test("a missing finish reason is not a continuation", () => {
    expect(MessageV2.isContinuing(undefined)).toBe(false)
    expect(MessageV2.isContinuing("")).toBe(false)
  })
})

describe("session.message-v2.toModelMessage — media budgeting", () => {
  const imagePart = (id: string, name: string) => ({
    ...basePart("m-imgs", id),
    type: "file" as const,
    mime: "image/png",
    filename: name,
    url: `data:image/png;base64,${Buffer.from(name).toString("base64")}`,
  })
  const imagesInput = (): MessageV2.WithParts[] => [
    {
      info: userInfo("m-imgs"),
      parts: [imagePart("i1", "a.png"), imagePart("i2", "b.png"), imagePart("i3", "c.png")] as MessageV2.Part[],
    },
  ]

  test("keepRecentImages keeps only the last N images; older ones become placeholders", () => {
    const out = MessageV2.toModelMessages(imagesInput(), model, { keepRecentImages: 1 })
    const s = JSON.stringify(out)
    expect((s.match(/"type":"file"/g) ?? []).length).toBe(1) // only the newest image kept in full
    expect((s.match(/older image omitted/g) ?? []).length).toBe(2) // the two older ones stripped
  })

  test("the image window releases its older half at once, so a new figure does not rewrite an earlier message", () => {
    const names = ["a", "b", "c", "d", "e", "f"]
    const input = (count: number): MessageV2.WithParts[] => [
      {
        info: userInfo("m-imgs"),
        parts: names.slice(0, count).map((name, index) => imagePart(`i${index}`, `${name}.png`)) as MessageV2.Part[],
      },
    ]
    const kept = (count: number) =>
      names
        .slice(0, count)
        .filter((name) =>
          JSON.stringify(MessageV2.toModelMessages(input(count), model, { keepRecentImages: 4 })).includes(
            `"filename":"${name}.png"`,
          ),
        )
    // Four images fit. The fifth spills the window, which keeps its newest half.
    expect(kept(4)).toEqual(["a", "b", "c", "d"])
    expect(kept(5)).toEqual(["d", "e"])
    // The sixth joins without touching what the fifth settled: a, b, c stay
    // placeholders and d stays in full, so the request prefix is unchanged.
    expect(kept(6)).toEqual(["d", "e", "f"])
    expect(MessageV2.retainedImages(["1", "2", "3"], 0).size).toBe(0)
  })

  test("imageBytes bounds what one request carries; the newest image always travels and a lone giant is nudged instead", () => {
    // Three 3 MB figures were read in a row; a count window of 20 keeps all
    // of them, so the request body is what the gateway rejects.
    const big = (id: string, name: string) => ({
      ...basePart("m-imgs", id),
      type: "file" as const,
      mime: "image/png",
      filename: name,
      url: `data:image/png;base64,${Buffer.alloc(3 * 1024 * 1024, id.charCodeAt(0)).toString("base64")}`,
    })
    const input: MessageV2.WithParts[] = [
      {
        info: userInfo("m-imgs"),
        parts: [big("x", "x.png"), big("y", "y.png"), big("z", "z.png")] as MessageV2.Part[],
      },
    ]
    const direct = JSON.stringify(
      MessageV2.toModelMessages(input, model, { keepRecentImages: 20, imageBytes: 12 * 1024 * 1024 }),
    )
    expect((direct.match(/"type":"file"/g) ?? []).length).toBe(3)

    const capped = MessageV2.toModelMessages(input, model, { keepRecentImages: 20, imageBytes: 7 * 1024 * 1024 })
    const s = JSON.stringify(capped)
    // 9 MB over a 7 MB budget releases down to half: only the newest stays.
    expect((s.match(/"type":"file"/g) ?? []).length).toBe(1)
    expect(s).toContain('"filename":"z.png"')
    expect((s.match(/omitted to keep this request under the route's image limit/g) ?? []).length).toBe(2)
    expect(s).not.toContain("omitted to save context")

    // On the managed route a single 3 MB figure is over the per-image cap too:
    // it is replaced by the resize nudge rather than shipped to a certain 502.
    const managed = JSON.stringify(
      MessageV2.toModelMessages(input, model, {
        keepRecentImages: 20,
        imageBytes: SessionCompaction.IMAGE_BYTES_MANAGED,
      }),
    )
    expect(managed).not.toContain('"type":"file"')
    expect(managed).toContain("2 MB limit on this route")
    expect(managed).toContain("thumbnail((1400,1400))")

    // 12 over a budget of 10 releases down to half the budget, not just under it.
    expect(MessageV2.retainedImageBytes(["a", "b", "c"], () => 4, 10)).toEqual(new Set(["c"]))
    expect(MessageV2.retainedImageBytes(["a", "b", "c"], () => 2, 10)).toEqual(new Set(["a", "b", "c"]))
    expect(MessageV2.retainedImageBytes(["a"], () => 40, 10)).toEqual(new Set(["a"]))
    expect(MessageV2.retainedImageBytes(["a", "b"], () => 4, 0).size).toBe(0)
    expect(MessageV2.decodedBytes(`data:image/png;base64,${Buffer.alloc(300).toString("base64")}`)).toBe(300)
    expect(MessageV2.decodedBytes("https://example.com/x.png")).toBe(0)
  })

  test("toolOutputMaxChars cuts long tool results head-and-tail for a reduced-fidelity handoff", () => {
    const long = `${"A".repeat(2_500)}MIDDLE${"Z".repeat(2_500)}`
    const input: MessageV2.WithParts[] = [
      { info: userInfo("m-u"), parts: [{ ...basePart("m-u", "u1"), type: "text", text: "run" }] as MessageV2.Part[] },
      {
        info: assistantInfo("m-a", "m-u"),
        parts: [
          {
            ...basePart("m-a", "a1"),
            type: "tool",
            callID: "call-long",
            tool: "bash",
            state: {
              status: "completed",
              input: { command: "cat big.log" },
              output: long,
              title: "Bash",
              metadata: {},
              time: { start: 0, end: 1 },
            },
          },
        ] as MessageV2.Part[],
      },
    ]
    const full = JSON.stringify(MessageV2.toModelMessages(input, model))
    expect(full).toContain("MIDDLE")
    const reduced = JSON.stringify(MessageV2.toModelMessages(input, model, { toolOutputMaxChars: 2_000 }))
    expect(reduced).not.toContain("MIDDLE")
    expect(reduced).toContain("characters of this result omitted for the handoff")
    expect(reduced.length).toBeLessThan(full.length - 900)
    expect(MessageV2.capOutput("short", 2_000)).toBe("short")
    expect(MessageV2.capOutput("x".repeat(10), undefined)).toBe("x".repeat(10))
    expect(SessionCompaction.REDUCED_TOOL_OUTPUT_CHARS).toBe(2_000)
  })

  test("the image byte budget follows the route", () => {
    expect(SessionCompaction.imageBytes("managed")).toBe(2 * 1024 * 1024)
    expect(SessionCompaction.imageBytes("byok")).toBe(12 * 1024 * 1024)
    expect(SessionCompaction.imageBytes(undefined)).toBe(12 * 1024 * 1024)
  })

  test("stripMedia replaces every image with a placeholder (compaction summary path)", () => {
    const out = MessageV2.toModelMessages(imagesInput(), model, { stripMedia: true })
    const s = JSON.stringify(out)
    expect(s).not.toContain('"type":"file"')
    expect((s.match(/image omitted/g) ?? []).length).toBe(3)
    expect(s).not.toContain("Zm9v") // no base64 reaches the summarizer
  })

  test("no options → all images pass through unchanged (back-compat)", () => {
    const s = JSON.stringify(MessageV2.toModelMessages(imagesInput(), model))
    expect((s.match(/"type":"file"/g) ?? []).length).toBe(3)
    expect(s).not.toContain("image omitted")
  })

  test("ships byte-identical image content once even when it is attached twice", () => {
    const duplicate = imagePart("i2", "a.png")
    duplicate.url = imagePart("i1", "a.png").url
    const input: MessageV2.WithParts[] = [
      {
        info: userInfo("m-imgs"),
        parts: [imagePart("i1", "a.png"), duplicate] as MessageV2.Part[],
      },
    ]
    const serialized = JSON.stringify(MessageV2.toModelMessages(input, model, { keepRecentImages: 1 }))
    expect((serialized.match(/"type":"file"/g) ?? []).length).toBe(1)
    expect(serialized).toContain(MessageV2.DUPLICATE_IMAGE)
  })
})

describe("session.message-v2.toModelMessage — a compaction head rendered against its conversation", () => {
  const textPart = (messageID: string, id: string, text: string, synthetic?: boolean) =>
    ({ ...basePart(messageID, id), type: "text" as const, text, synthetic }) as MessageV2.Part
  const reasoningPart = (messageID: string, id: string, text: string) =>
    ({
      ...basePart(messageID, id),
      type: "reasoning" as const,
      text,
      time: { start: 0, end: 1 },
      metadata: { openai: { reasoningEncryptedContent: `enc-${id}` } },
    }) as MessageV2.Part
  const imagePart = (messageID: string, id: string, name: string) =>
    ({
      ...basePart(messageID, id),
      type: "file" as const,
      mime: "image/png",
      filename: name,
      url: `data:image/png;base64,${Buffer.from(name).toString("base64")}`,
    }) as MessageV2.Part
  const typed = (id: string, text: string): MessageV2.WithParts => ({
    info: { ...userInfo(id), internal: { type: "prompt", epoch: id } } as MessageV2.User,
    parts: [textPart(id, `${id}-t`, text)],
  })
  const reply = (id: string, parentID: string, text: string): MessageV2.WithParts => ({
    info: { ...assistantInfo(id, parentID), finish: "stop" } as MessageV2.Assistant,
    parts: [reasoningPart(id, `${id}-r`, `thinking about ${text}`), textPart(id, `${id}-x`, text)],
  })
  // Two typed requests with reasoning replies, a study update the runtime
  // wrote, then the compaction carrier: the shape of a long research session.
  const conversation = (): MessageV2.WithParts[] => [
    typed("u1", "Run the EDA."),
    reply("a1", "u1", "EDA done."),
    typed("u2", "Now train the model."),
    reply("a2", "u2", "Baseline trained."),
    {
      info: {
        ...userInfo("u3"),
        internal: { type: "continuation", kind: "harness", text: "Study update", epoch: "u2", transaction: "u3" },
      } as MessageV2.User,
      parts: [textPart("u3", "u3-t", "Study update: run 4 finished.", true)],
    },
    reply("a3", "u3", "Recorded run 4."),
    {
      info: { ...userInfo("cc"), internal: { type: "compaction", auto: true, epoch: "u2", transaction: "cc" } },
      parts: [{ ...basePart("cc", "cc-c"), type: "compaction", auto: true } as MessageV2.Part],
    },
  ]

  test("the head keeps the conversation's reasoning boundary, so its bytes are the cached prefix", () => {
    const all = conversation()
    const full = MessageV2.toModelMessages(all, model)
    // The tail starts at the newest request; everything before it is the head.
    const head = all.slice(0, 2)
    const rendered = MessageV2.toModelMessages(head, model, { conversation: all })
    expect(JSON.stringify(rendered)).toBe(JSON.stringify(full.slice(0, rendered.length)))
    expect(JSON.stringify(rendered)).not.toContain("thinking about")
    // Rendered on its own, the boundary moves to the head's newest request and
    // the reply behind it replays the reasoning the conversation never sent.
    expect(JSON.stringify(MessageV2.toModelMessages(head, model))).toContain("thinking about EDA")
  })

  test("a head that ends after a runtime carrier still renders every reply as an earlier turn", () => {
    const all = conversation()
    const full = MessageV2.toModelMessages(all, model)
    const head = all.slice(0, 6)
    const rendered = MessageV2.toModelMessages(head, model, { conversation: all })
    expect(JSON.stringify(rendered)).toBe(JSON.stringify(full.slice(0, rendered.length)))
    // Inside the conversation the boundary is u2, so a2 and a3 replay their
    // reasoning there and here alike; a1 does not.
    expect(JSON.stringify(rendered)).not.toContain("thinking about EDA")
    expect(JSON.stringify(rendered)).toContain("thinking about Baseline")
  })

  test("the image budget is the conversation's, so a head image the tail pushed out stays a placeholder", () => {
    const all: MessageV2.WithParts[] = [
      {
        info: typed("u1", "Plot it.").info,
        parts: [textPart("u1", "u1-t", "Plot it."), imagePart("u1", "u1-i", "old.png")],
      },
      reply("a1", "u1", "Plotted."),
      {
        info: typed("u2", "Again.").info,
        parts: [textPart("u2", "u2-t", "Again."), imagePart("u2", "u2-i", "new.png")],
      },
    ]
    const full = MessageV2.toModelMessages(all, model, { keepRecentImages: 1 })
    const rendered = MessageV2.toModelMessages(all.slice(0, 2), model, { keepRecentImages: 1, conversation: all })
    expect(JSON.stringify(rendered)).toBe(JSON.stringify(full.slice(0, rendered.length)))
    expect(JSON.stringify(rendered)).toContain("older image omitted")
  })

  test("without a conversation the head is rendered as before", () => {
    const all = conversation()
    const head = all.slice(0, 2)
    expect(JSON.stringify(MessageV2.toModelMessages(head, model, { conversation: head }))).toBe(
      JSON.stringify(MessageV2.toModelMessages(head, model)),
    )
  })
})

describe("session.message-v2.toModelMessage", () => {
  test("filters out messages with no parts", () => {
    const input: MessageV2.WithParts[] = [
      {
        info: userInfo("m-empty"),
        parts: [],
      },
      {
        info: userInfo("m-user"),
        parts: [
          {
            ...basePart("m-user", "p1"),
            type: "text",
            text: "hello",
          },
        ] as MessageV2.Part[],
      },
    ]

    expect(MessageV2.toModelMessages(input, model)).toStrictEqual([
      {
        role: "user",
        content: [{ type: "text", text: "hello" }],
      },
    ])
  })

  test("filters out messages with only ignored parts", () => {
    const messageID = "m-user"

    const input: MessageV2.WithParts[] = [
      {
        info: userInfo(messageID),
        parts: [
          {
            ...basePart(messageID, "p1"),
            type: "text",
            text: "ignored",
            ignored: true,
          },
        ] as MessageV2.Part[],
      },
    ]

    expect(MessageV2.toModelMessages(input, model)).toStrictEqual([])
  })

  test("drops ignored assistant text the same way it drops ignored user text", () => {
    // A slash-command notice pair (/status, /stop): the user line and the
    // assistant answer are both display-only and must not reach the model.
    const input: MessageV2.WithParts[] = [
      {
        info: userInfo("m-notice"),
        parts: [{ ...basePart("m-notice", "p1"), type: "text", text: "/status", ignored: true }] as MessageV2.Part[],
      },
      {
        info: assistantInfo("m-notice-reply", "m-notice"),
        parts: [
          { ...basePart("m-notice-reply", "a1"), type: "text", text: "### Session status", ignored: true },
        ] as MessageV2.Part[],
      },
    ]

    expect(MessageV2.toModelMessages(input, model)).toStrictEqual([])
  })

  test("includes synthetic text parts", () => {
    const messageID = "m-user"

    const input: MessageV2.WithParts[] = [
      {
        info: userInfo(messageID),
        parts: [
          {
            ...basePart(messageID, "p1"),
            type: "text",
            text: "hello",
            synthetic: true,
          },
        ] as MessageV2.Part[],
      },
      {
        info: assistantInfo("m-assistant", messageID),
        parts: [
          {
            ...basePart("m-assistant", "a1"),
            type: "text",
            text: "assistant",
            synthetic: true,
          },
        ] as MessageV2.Part[],
      },
    ]

    expect(MessageV2.toModelMessages(input, model)).toStrictEqual([
      {
        role: "user",
        content: [{ type: "text", text: "hello" }],
      },
      {
        role: "assistant",
        content: [{ type: "text", text: "assistant" }],
      },
    ])
  })

  test("converts user text/file parts and injects compaction/subtask prompts", () => {
    const messageID = "m-user"

    const input: MessageV2.WithParts[] = [
      {
        info: userInfo(messageID),
        parts: [
          {
            ...basePart(messageID, "p1"),
            type: "text",
            text: "hello",
          },
          {
            ...basePart(messageID, "p2"),
            type: "text",
            text: "ignored",
            ignored: true,
          },
          {
            ...basePart(messageID, "p3"),
            type: "file",
            mime: "image/png",
            filename: "img.png",
            url: "https://example.com/img.png",
          },
          {
            ...basePart(messageID, "p4"),
            type: "file",
            mime: "text/plain",
            filename: "note.txt",
            url: "https://example.com/note.txt",
          },
          {
            ...basePart(messageID, "p5"),
            type: "file",
            mime: "application/x-directory",
            filename: "dir",
            url: "https://example.com/dir",
          },
          {
            ...basePart(messageID, "p6"),
            type: "compaction",
            auto: true,
          },
          {
            ...basePart(messageID, "p7"),
            type: "subtask",
            prompt: "prompt",
            description: "desc",
            agent: "agent",
          },
        ] as MessageV2.Part[],
      },
    ]

    expect(MessageV2.toModelMessages(input, model)).toStrictEqual([
      {
        role: "user",
        content: [
          { type: "text", text: "hello" },
          {
            type: "file",
            mediaType: "image/png",
            filename: "img.png",
            data: "https://example.com/img.png",
          },
          { type: "text", text: "What did we do so far?" },
          { type: "text", text: "The following tool was executed by the user" },
        ],
      },
    ])
  })

  test("converts assistant tool completion into tool-call + tool-result messages with attachments", () => {
    const userID = "m-user"
    const assistantID = "m-assistant"

    const input: MessageV2.WithParts[] = [
      {
        info: userInfo(userID),
        parts: [
          {
            ...basePart(userID, "u1"),
            type: "text",
            text: "run tool",
          },
        ] as MessageV2.Part[],
      },
      {
        info: assistantInfo(assistantID, userID),
        parts: [
          {
            ...basePart(assistantID, "a1"),
            type: "text",
            text: "done",
            metadata: { openai: { assistant: "meta" } },
          },
          {
            ...basePart(assistantID, "a2"),
            type: "tool",
            callID: "call-1",
            tool: "bash",
            state: {
              status: "completed",
              input: { cmd: "ls" },
              output: "ok",
              title: "Bash",
              metadata: {},
              time: { start: 0, end: 1 },
              attachments: [
                {
                  ...basePart(assistantID, "file-1"),
                  type: "file",
                  mime: "image/png",
                  filename: "attachment.png",
                  url: "data:image/png;base64,Zm9v",
                },
              ],
            },
            metadata: { openai: { tool: "meta" } },
          },
        ] as MessageV2.Part[],
      },
    ]

    expect(MessageV2.toModelMessages(input, model)).toStrictEqual([
      {
        role: "user",
        content: [{ type: "text", text: "run tool" }],
      },
      {
        role: "assistant",
        content: [
          { type: "text", text: "done", providerOptions: { openai: { assistant: "meta" } } },
          {
            type: "tool-call",
            toolCallId: "call-1",
            toolName: "bash",
            input: { cmd: "ls" },
            providerExecuted: undefined,
            providerOptions: { openai: { tool: "meta" } },
          },
        ],
      },
      {
        role: "tool",
        content: [
          {
            type: "tool-result",
            toolCallId: "call-1",
            toolName: "bash",
            output: {
              type: "content",
              value: [
                { type: "text", text: "ok" },
                { type: "media", mediaType: "image/png", data: "Zm9v" },
              ],
            },
            providerOptions: { openai: { tool: "meta" } },
          },
        ],
      },
    ])
  })

  test("omits provider metadata when assistant model differs", () => {
    const userID = "m-user"
    const assistantID = "m-assistant"

    const input: MessageV2.WithParts[] = [
      {
        info: userInfo(userID),
        parts: [
          {
            ...basePart(userID, "u1"),
            type: "text",
            text: "run tool",
          },
        ] as MessageV2.Part[],
      },
      {
        info: assistantInfo(assistantID, userID, undefined, { providerID: "other", modelID: "other" }),
        parts: [
          {
            ...basePart(assistantID, "a1"),
            type: "text",
            text: "done",
            metadata: { openai: { assistant: "meta" } },
          },
          {
            ...basePart(assistantID, "a2"),
            type: "tool",
            callID: "call-1",
            tool: "bash",
            state: {
              status: "completed",
              input: { cmd: "ls" },
              output: "ok",
              title: "Bash",
              metadata: {},
              time: { start: 0, end: 1 },
            },
            metadata: { openai: { tool: "meta" } },
          },
        ] as MessageV2.Part[],
      },
    ]

    expect(MessageV2.toModelMessages(input, model)).toStrictEqual([
      {
        role: "user",
        content: [{ type: "text", text: "run tool" }],
      },
      {
        role: "assistant",
        content: [
          { type: "text", text: "done" },
          {
            type: "tool-call",
            toolCallId: "call-1",
            toolName: "bash",
            input: { cmd: "ls" },
            providerExecuted: undefined,
          },
        ],
      },
      {
        role: "tool",
        content: [
          {
            type: "tool-result",
            toolCallId: "call-1",
            toolName: "bash",
            output: { type: "text", value: "ok" },
          },
        ],
      },
    ])
  })

  test("replaces compacted tool output with a 1-line tool-aware summary", () => {
    const userID = "m-user"
    const assistantID = "m-assistant"

    const input: MessageV2.WithParts[] = [
      {
        info: userInfo(userID),
        parts: [
          {
            ...basePart(userID, "u1"),
            type: "text",
            text: "run tool",
          },
        ] as MessageV2.Part[],
      },
      {
        info: assistantInfo(assistantID, userID),
        parts: [
          {
            ...basePart(assistantID, "a1"),
            type: "tool",
            callID: "call-1",
            tool: "bash",
            state: {
              status: "completed",
              input: { cmd: "ls" },
              output: "this should be cleared",
              title: "Bash",
              metadata: {},
              time: { start: 0, end: 1, compacted: 1 },
            },
          },
        ] as MessageV2.Part[],
      },
    ]

    expect(MessageV2.toModelMessages(input, model)).toStrictEqual([
      {
        role: "user",
        content: [{ type: "text", text: "run tool" }],
      },
      {
        role: "assistant",
        content: [
          {
            type: "tool-call",
            toolCallId: "call-1",
            toolName: "bash",
            input: { cmd: "ls" },
            providerExecuted: undefined,
          },
        ],
      },
      {
        role: "tool",
        content: [
          {
            type: "tool-result",
            toolCallId: "call-1",
            toolName: "bash",
            output: { type: "text", value: "[bash] Bash → cleared (1 line)" },
          },
        ],
      },
    ])
  })

  test("converts assistant tool error into error-text tool result", () => {
    const userID = "m-user"
    const assistantID = "m-assistant"

    const input: MessageV2.WithParts[] = [
      {
        info: userInfo(userID),
        parts: [
          {
            ...basePart(userID, "u1"),
            type: "text",
            text: "run tool",
          },
        ] as MessageV2.Part[],
      },
      {
        info: assistantInfo(assistantID, userID),
        parts: [
          {
            ...basePart(assistantID, "a1"),
            type: "tool",
            callID: "call-1",
            tool: "bash",
            state: {
              status: "error",
              input: { cmd: "ls" },
              error: "nope",
              time: { start: 0, end: 1 },
              metadata: {},
            },
            metadata: { openai: { tool: "meta" } },
          },
        ] as MessageV2.Part[],
      },
    ]

    expect(MessageV2.toModelMessages(input, model)).toStrictEqual([
      {
        role: "user",
        content: [{ type: "text", text: "run tool" }],
      },
      {
        role: "assistant",
        content: [
          {
            type: "tool-call",
            toolCallId: "call-1",
            toolName: "bash",
            input: { cmd: "ls" },
            providerExecuted: undefined,
            providerOptions: { openai: { tool: "meta" } },
          },
        ],
      },
      {
        role: "tool",
        content: [
          {
            type: "tool-result",
            toolCallId: "call-1",
            toolName: "bash",
            output: { type: "error-text", value: "nope" },
            providerOptions: { openai: { tool: "meta" } },
          },
        ],
      },
    ])
  })

  test("filters assistant messages with non-abort errors", () => {
    const assistantID = "m-assistant"

    const input: MessageV2.WithParts[] = [
      {
        info: assistantInfo(
          assistantID,
          "m-parent",
          new MessageV2.APIError({ message: "boom", isRetryable: true }).toObject() as MessageV2.APIError,
        ),
        parts: [
          {
            ...basePart(assistantID, "a1"),
            type: "text",
            text: "should not render",
          },
        ] as MessageV2.Part[],
      },
    ]

    expect(MessageV2.toModelMessages(input, model)).toStrictEqual([])
  })

  test("includes aborted assistant messages only when they have non-step-start/reasoning content", () => {
    const assistantID1 = "m-assistant-1"
    const assistantID2 = "m-assistant-2"

    const aborted = new MessageV2.AbortedError({ message: "aborted" }).toObject() as MessageV2.Assistant["error"]

    const input: MessageV2.WithParts[] = [
      {
        info: assistantInfo(assistantID1, "m-parent", aborted),
        parts: [
          {
            ...basePart(assistantID1, "a1"),
            type: "reasoning",
            text: "thinking",
            time: { start: 0 },
          },
          {
            ...basePart(assistantID1, "a2"),
            type: "text",
            text: "partial answer",
          },
        ] as MessageV2.Part[],
      },
      {
        info: assistantInfo(assistantID2, "m-parent", aborted),
        parts: [
          {
            ...basePart(assistantID2, "b1"),
            type: "step-start",
          },
          {
            ...basePart(assistantID2, "b2"),
            type: "reasoning",
            text: "thinking",
            time: { start: 0 },
          },
        ] as MessageV2.Part[],
      },
    ]

    expect(MessageV2.toModelMessages(input, model)).toStrictEqual([
      {
        role: "assistant",
        content: [
          { type: "reasoning", text: "thinking", providerOptions: undefined },
          { type: "text", text: "partial answer" },
        ],
      },
    ])
  })

  test("splits assistant messages on step-start boundaries", () => {
    const assistantID = "m-assistant"

    const input: MessageV2.WithParts[] = [
      {
        info: assistantInfo(assistantID, "m-parent"),
        parts: [
          {
            ...basePart(assistantID, "p1"),
            type: "text",
            text: "first",
          },
          {
            ...basePart(assistantID, "p2"),
            type: "step-start",
          },
          {
            ...basePart(assistantID, "p3"),
            type: "text",
            text: "second",
          },
        ] as MessageV2.Part[],
      },
    ]

    expect(MessageV2.toModelMessages(input, model)).toStrictEqual([
      {
        role: "assistant",
        content: [{ type: "text", text: "first" }],
      },
      {
        role: "assistant",
        content: [{ type: "text", text: "second" }],
      },
    ])
  })

  test("drops messages that only contain step-start parts", () => {
    const assistantID = "m-assistant"

    const input: MessageV2.WithParts[] = [
      {
        info: assistantInfo(assistantID, "m-parent"),
        parts: [
          {
            ...basePart(assistantID, "p1"),
            type: "step-start",
          },
        ] as MessageV2.Part[],
      },
    ]

    expect(MessageV2.toModelMessages(input, model)).toStrictEqual([])
  })

  test("converts pending/running tool calls to error results to prevent dangling tool_use", () => {
    const userID = "m-user"
    const assistantID = "m-assistant"

    const input: MessageV2.WithParts[] = [
      {
        info: userInfo(userID),
        parts: [
          {
            ...basePart(userID, "u1"),
            type: "text",
            text: "run tool",
          },
        ] as MessageV2.Part[],
      },
      {
        info: assistantInfo(assistantID, userID),
        parts: [
          {
            ...basePart(assistantID, "a1"),
            type: "tool",
            callID: "call-pending",
            tool: "bash",
            state: {
              status: "pending",
              input: { cmd: "ls" },
              raw: "",
            },
          },
          {
            ...basePart(assistantID, "a2"),
            type: "tool",
            callID: "call-running",
            tool: "read",
            state: {
              status: "running",
              input: { path: "/tmp" },
              time: { start: 0 },
            },
          },
        ] as MessageV2.Part[],
      },
    ]

    const result = MessageV2.toModelMessages(input, model)

    expect(result).toStrictEqual([
      {
        role: "user",
        content: [{ type: "text", text: "run tool" }],
      },
      {
        role: "assistant",
        content: [
          {
            type: "tool-call",
            toolCallId: "call-pending",
            toolName: "bash",
            input: { cmd: "ls" },
            providerExecuted: undefined,
          },
          {
            type: "tool-call",
            toolCallId: "call-running",
            toolName: "read",
            input: { path: "/tmp" },
            providerExecuted: undefined,
          },
        ],
      },
      {
        role: "tool",
        content: [
          {
            type: "tool-result",
            toolCallId: "call-pending",
            toolName: "bash",
            output: { type: "error-text", value: "[Tool execution was interrupted]" },
          },
          {
            type: "tool-result",
            toolCallId: "call-running",
            toolName: "read",
            output: { type: "error-text", value: "[Tool execution was interrupted]" },
          },
        ],
      },
    ])
  })

  test("forwards one complete OpenRouter reasoning signature across tool turns", () => {
    const assistantID = "m-openrouter"
    const metadata = {
      openrouter: {
        reasoning_details: [
          {
            type: "reasoning.text",
            text: "Read both files.",
            format: "anthropic-claude-v1",
            index: 0,
            signature: "signed-thinking-block",
          },
        ],
      },
    }
    const openrouter = {
      ...model,
      id: "anthropic/claude-sonnet-4.6",
      providerID: "openrouter",
      api: { ...model.api, id: "anthropic/claude-sonnet-4.6" },
    }
    const input: MessageV2.WithParts[] = [
      {
        info: assistantInfo(assistantID, "m-user", undefined, {
          providerID: openrouter.providerID,
          modelID: openrouter.id,
        }),
        parts: [
          {
            ...basePart(assistantID, "reasoning"),
            type: "reasoning",
            text: "Read both files.",
            metadata: {
              openrouter: {
                reasoning_details: [
                  {
                    type: "reasoning.text",
                    text: "Read both files.",
                    format: "anthropic-claude-v1",
                    index: 0,
                  },
                ],
              },
            },
            time: { start: 0, end: 1 },
          },
          {
            ...basePart(assistantID, "read-a"),
            type: "tool",
            callID: "call-a",
            tool: "read",
            state: {
              status: "completed",
              input: { filePath: "a.md" },
              output: "a",
              title: "a.md",
              metadata: {},
              time: { start: 1, end: 2 },
            },
            metadata,
          },
          {
            ...basePart(assistantID, "read-b"),
            type: "tool",
            callID: "call-b",
            tool: "read",
            state: {
              status: "completed",
              input: { filePath: "b.csv" },
              output: "b",
              title: "b.csv",
              metadata: {},
              time: { start: 1, end: 2 },
            },
            metadata,
          },
        ] as MessageV2.Part[],
      },
    ]

    const result = MessageV2.toModelMessages(input, openrouter)
    const assistant = result.find((message) => message.role === "assistant")
    const options =
      assistant && Array.isArray(assistant.content)
        ? assistant.content.flatMap((part) =>
            "providerOptions" in part && part.providerOptions ? [part.providerOptions] : [],
          )
        : []

    expect(options).toStrictEqual([metadata])
    expect(JSON.stringify(result)).not.toContain('"format":"anthropic-claude-v1","index":0}}')
  })

  test("replays the encrypted reasoning of the turn in progress and nothing of earlier turns, without per-token summaries", () => {
    const openrouter = {
      ...model,
      id: "openai/gpt-6-astra",
      providerID: "openrouter",
      api: { ...model.api, id: "openai/gpt-6-astra", npm: "@openrouter/ai-sdk-provider" },
    }
    const encrypted = (id: string) => ({
      type: "reasoning.encrypted",
      id,
      data: `encrypted-${id}`,
      format: "openai-responses-v1",
      index: 0,
    })
    const summaries = ["**Planning", " the", " read**"].map((summary) => ({
      type: "reasoning.summary",
      summary,
      format: "openai-responses-v1",
      index: 0,
    }))
    const step = (assistantID: string, parentID: string, rs: string) => ({
      info: assistantInfo(assistantID, parentID, undefined, { providerID: "openrouter", modelID: openrouter.id }),
      parts: [
        {
          ...basePart(assistantID, `${assistantID}-reasoning`),
          type: "reasoning",
          text: "[REDACTED]Planning the read",
          metadata: { openrouter: { reasoning_details: [...summaries, encrypted(rs)] } },
          time: { start: 0, end: 1 },
        },
        {
          ...basePart(assistantID, `${assistantID}-tool`),
          type: "tool",
          callID: `${assistantID}-call`,
          tool: "read",
          state: {
            status: "completed",
            input: { filePath: "a.md" },
            output: "a",
            title: "a.md",
            metadata: {},
            time: { start: 1, end: 2 },
          },
          metadata: { openrouter: { reasoning_details: [...summaries, encrypted(rs)] } },
        },
      ] as MessageV2.Part[],
    })
    const input: MessageV2.WithParts[] = [
      {
        info: userInfo("u1"),
        parts: [{ ...basePart("u1", "u1-text"), type: "text", text: "First request" }] as MessageV2.Part[],
      },
      step("a1", "u1", "rs_old"),
      {
        info: userInfo("u2"),
        parts: [{ ...basePart("u2", "u2-text"), type: "text", text: "Second request" }] as MessageV2.Part[],
      },
      step("a2", "u2", "rs_now"),
      // A worker's result lands mid-work as a synthetic user message; it is not a turn.
      {
        info: userInfo("u3"),
        parts: [
          {
            ...basePart("u3", "u3-text"),
            type: "text",
            text: '<task id="ses_w" state="completed">done</task>',
            synthetic: true,
          },
        ] as MessageV2.Part[],
      },
      step("a3", "u3", "rs_after_worker"),
    ]
    const serialized = JSON.stringify(MessageV2.toModelMessages(input, openrouter))
    // The work since the person's last request keeps its encrypted items; the earlier turn's reasoning is gone.
    expect(serialized).toContain("encrypted-rs_now")
    expect(serialized).toContain("encrypted-rs_after_worker")
    expect(serialized).not.toContain("encrypted-rs_old")
    expect((serialized.match(/"type":"reasoning"/g) ?? []).length).toBe(2)
    // Per-token summary fragments never travel; the transcript still has them.
    expect(serialized).not.toContain("reasoning.summary")
    expect(MessageV2.replayableOpenRouterReplay({ openrouter: { reasoning_details: summaries } })).toEqual({
      openrouter: { reasoning_details: [] },
    })
    // Untouched when there is nothing to trim, so a signed Anthropic block stays byte-identical.
    const signed = { openrouter: { reasoning_details: [{ type: "reasoning.text", text: "t", signature: "s" }] } }
    expect(MessageV2.replayableOpenRouterReplay(signed)).toBe(signed)
  })

  test("does not replay an unsigned OpenRouter Anthropic reasoning detail", () => {
    const assistantID = "m-openrouter-unsigned"
    const openrouter = {
      ...model,
      id: "anthropic/claude-opus-4.8",
      providerID: "openrouter",
      api: { ...model.api, id: "anthropic/claude-opus-4.8" },
    }
    const input: MessageV2.WithParts[] = [
      {
        info: assistantInfo(assistantID, "m-user", undefined, {
          providerID: openrouter.providerID,
          modelID: openrouter.id,
        }),
        parts: [
          {
            ...basePart(assistantID, "reasoning"),
            type: "reasoning",
            text: "Answer concisely.",
            metadata: {
              openrouter: {
                reasoning_details: [
                  {
                    type: "reasoning.text",
                    text: "Answer concisely.",
                    format: "anthropic-claude-v1",
                    index: 0,
                  },
                ],
              },
            },
            time: { start: 0, end: 1 },
          },
          {
            ...basePart(assistantID, "answer"),
            type: "text",
            text: "The answer.",
          },
        ] as MessageV2.Part[],
      },
    ]

    const result = MessageV2.toModelMessages(input, openrouter)
    const assistant = result.find((message) => message.role === "assistant")
    const options =
      assistant && Array.isArray(assistant.content)
        ? assistant.content.flatMap((part) =>
            "providerOptions" in part && part.providerOptions ? [part.providerOptions] : [],
          )
        : []

    expect(options).toEqual([])
    expect(JSON.stringify(result)).not.toContain("reasoning_details")
    expect(JSON.stringify(result)).toContain("Answer concisely.")
  })
})

describe("session.message-v2.filterCompacted — verbatim tail (P3.2)", () => {
  async function* streamOf(msgs: MessageV2.WithParts[]) {
    for (const m of msgs) yield m
  }
  const mk = (
    id: string,
    role: "user" | "assistant",
    parts: MessageV2.Part[],
    extra: Record<string, unknown> = {},
  ): MessageV2.WithParts => ({
    info: {
      id,
      sessionID: "s",
      role,
      time: { created: 0 },
      ...(role === "user"
        ? { agent: "a", model: { providerID: "p", modelID: "m" } }
        : {
            parentID: "p",
            modelID: "m",
            providerID: "p",
            mode: "",
            agent: "a",
            cost: 0,
            tokens: { input: 0, output: 0, reasoning: 0, cache: { read: 0, write: 0 } },
          }),
      ...extra,
    } as unknown as MessageV2.WithParts["info"],
    parts: parts as unknown as MessageV2.Part[],
  })
  const txt = (mid: string, t: string) =>
    ({ id: `${mid}t`, sessionID: "s", messageID: mid, type: "text", text: t }) as unknown as MessageV2.Part
  const compactionCarrier = (id: string) =>
    mk(id, "user", [
      { id: `${id}c`, sessionID: "s", messageID: id, type: "compaction", auto: true } as unknown as MessageV2.Part,
    ])

  test("keeps the tail messages verbatim after the summary", async () => {
    // history: [old1 old2] [tail: u-tail a-tail] [compaction carrier] [summary(tailStartId=u-tail)] [continuation]
    // fixtures are NEWEST-first because MessageV2.stream (the real caller's input) yields newest-first.
    const msgs: MessageV2.WithParts[] = [
      mk("cont", "assistant", [txt("cont", "continuing")], { finish: "stop", parentID: "cc" }),
      mk("sum", "assistant", [txt("sum", "HANDOFF")], {
        summary: true,
        finish: "stop",
        parentID: "cc",
        tailStartId: "utail",
      }),
      compactionCarrier("cc"),
      mk("atail", "assistant", [txt("atail", "recent work")]),
      mk("utail", "user", [txt("utail", "current request")]),
      mk("old2", "assistant", [txt("old2", "old a")]),
      mk("old1", "user", [txt("old1", "old q")]),
    ]
    const out = await MessageV2.filterCompacted(streamOf(msgs))
    const ids = out.map((m) => m.info.id)
    expect(ids).not.toContain("old1")
    expect(ids).not.toContain("old2")
    // tail preserved verbatim, ordered after the summary
    expect(ids).toEqual(["cc", "sum", "utail", "atail", "cont"])
  })

  test("without tailStartId, behavior is unchanged (drops everything before the boundary)", async () => {
    // NEWEST-first, matching MessageV2.stream.
    const msgs: MessageV2.WithParts[] = [
      mk("cont", "assistant", [txt("cont", "go")], { finish: "stop", parentID: "cc" }),
      mk("sum", "assistant", [txt("sum", "HANDOFF")], { summary: true, finish: "stop", parentID: "cc" }),
      compactionCarrier("cc"),
      mk("old1", "user", [txt("old1", "old")]),
    ]
    const out = await MessageV2.filterCompacted(streamOf(msgs))
    expect(out.map((m) => m.info.id)).toEqual(["cc", "sum", "cont"])
  })

  test("an empty (failed-overflow) summary is NOT a boundary — history is preserved, not dropped", async () => {
    // A compaction whose own summary request overflowed: the summary message is left
    // marked summary:true + finish (here "compact") but carries NO text. It must not be
    // treated as a real compaction boundary — doing so would drop the entire history and
    // replace it with an empty summary (the P0 data-loss bug).
    const msgs: MessageV2.WithParts[] = [
      mk("sum", "assistant", [], { summary: true, finish: "compact", parentID: "cc" }),
      compactionCarrier("cc"),
      mk("a1", "assistant", [txt("a1", "real work")], { finish: "stop", parentID: "u1" }),
      mk("u1", "user", [txt("u1", "real request")]),
    ]
    const out = await MessageV2.filterCompacted(streamOf(msgs))
    const ids = out.map((m) => m.info.id)
    expect(ids).toContain("u1")
    expect(ids).toContain("a1")
  })

  test("a nonempty summary truncated by its output limit is not a compaction boundary", async () => {
    const msgs: MessageV2.WithParts[] = [
      mk("sum", "assistant", [txt("sum", "## Objective\n- incomplete")], {
        summary: true,
        finish: "length",
        parentID: "cc",
      }),
      compactionCarrier("cc"),
      mk("a1", "assistant", [txt("a1", "critical evidence")], { finish: "stop", parentID: "u1" }),
      mk("u1", "user", [txt("u1", "real request")]),
    ]

    const out = await MessageV2.filterCompacted(streamOf(msgs))
    expect(out.map((message) => message.info.id)).toEqual(["u1", "a1", "cc", "sum"])
  })

  test("a nonempty failed summary is not a compaction boundary", async () => {
    const msgs: MessageV2.WithParts[] = [
      mk("sum", "assistant", [txt("sum", "partial handoff")], {
        summary: true,
        finish: "stop",
        parentID: "cc",
        error: { name: "UnknownError", data: { message: "summary rejected" } },
      }),
      compactionCarrier("cc"),
      mk("a1", "assistant", [txt("a1", "critical evidence")], { finish: "stop", parentID: "u1" }),
      mk("u1", "user", [txt("u1", "real request")]),
    ]

    const out = await MessageV2.filterCompacted(streamOf(msgs))
    expect(out.map((message) => message.info.id)).toEqual(["u1", "a1", "cc", "sum"])
  })

  test("a missing tailStartId keeps the history in order with the summary as its recap, never dropping the newest request", async () => {
    // The summary references a tail anchor that is no longer in the stream (e.g. the tail
    // messages were reverted/migrated away). The tail was the only place the newest
    // request lived, since the summary never saw it: dropping everything before the
    // carrier would resume from a handoff about older work. Keep the history the scan
    // collected, chronological, with the summary and continuation after it.
    const msgs: MessageV2.WithParts[] = [
      mk("cont", "assistant", [txt("cont", "go")], { finish: "stop", parentID: "cc" }),
      mk("sum", "assistant", [txt("sum", "HANDOFF")], {
        summary: true,
        finish: "stop",
        parentID: "cc",
        tailStartId: "gone",
      }),
      compactionCarrier("cc"),
      mk("a2", "assistant", [txt("a2", "work on the newest request")], { finish: "tool-calls", parentID: "u2" }),
      mk("u2", "user", [txt("u2", "newest request")]),
      mk("old2", "assistant", [txt("old2", "old a")], { finish: "stop", parentID: "old1" }),
      mk("old1", "user", [txt("old1", "old q")]),
    ]
    const out = await MessageV2.filterCompacted(streamOf(msgs))
    expect(out.map((m) => m.info.id)).toEqual(["old1", "old2", "u2", "a2", "cc", "sum", "cont"])
  })

  test("a missing tailStartId is bounded by the previous compaction: history before that boundary stays dropped", async () => {
    const msgs: MessageV2.WithParts[] = [
      mk("cont", "assistant", [txt("cont", "go")], { finish: "stop", parentID: "cc2" }),
      mk("sum2", "assistant", [txt("sum2", "HANDOFF 2")], {
        summary: true,
        finish: "stop",
        parentID: "cc2",
        tailStartId: "gone",
      }),
      compactionCarrier("cc2"),
      mk("a2", "assistant", [txt("a2", "work on the newest request")], { finish: "tool-calls", parentID: "u2" }),
      mk("u2", "user", [txt("u2", "newest request")]),
      mk("sum1", "assistant", [txt("sum1", "HANDOFF 1")], { summary: true, finish: "stop", parentID: "cc1" }),
      compactionCarrier("cc1"),
      mk("old2", "assistant", [txt("old2", "old a")], { finish: "stop", parentID: "old1" }),
      mk("old1", "user", [txt("old1", "old q")]),
    ]
    const out = await MessageV2.filterCompacted(streamOf(msgs))
    expect(out.map((m) => m.info.id)).toEqual(["cc1", "sum1", "u2", "a2", "cc2", "sum2", "cont"])
  })

  test("a superseded unanswered request cannot pin every later compaction tail", () => {
    const id = () => Identifier.ascending("message")
    const earlier = Array.from({ length: 3 }, () => [id(), id()] as const)
    const orphan = id()
    const retry = id()
    const reply = id()
    const recent = Array.from({ length: 8 }, () => [id(), id()] as const)
    const messages = [
      ...earlier.flatMap(([user, assistant], index) => [
        mk(user, "user", [txt(user, `earlier request ${index}`)]),
        mk(assistant, "assistant", [txt(assistant, `earlier reply ${index}`)], {
          finish: "stop",
          parentID: user,
        }),
      ]),
      mk(orphan, "user", [txt(orphan, "request superseded before it received a direct reply")]),
      mk(retry, "user", [txt(retry, "retry of the request")]),
      mk(reply, "assistant", [txt(reply, "reply to the retry")], { finish: "stop", parentID: retry }),
      ...recent.flatMap(([user, assistant], index) => [
        mk(user, "user", [txt(user, `recent request ${index}`)]),
        mk(assistant, "assistant", [txt(assistant, `recent reply ${index}`)], {
          finish: "stop",
          parentID: user,
        }),
      ]),
    ]

    const selected = SessionCompaction.selectTail(messages, {
      tailTurns: SessionCompaction.TAIL_TURNS,
      tailTokens: SessionCompaction.TAIL_TOKENS_MAX,
    })
    expect(selected.tailStartId).not.toBe(orphan)
    expect(recent.some(([user]) => user === selected.tailStartId)).toBe(true)
  })

  test("keeps a queued unanswered span that begins at the first message", () => {
    const first = Identifier.ascending("message")
    const second = Identifier.ascending("message")
    const messages = [
      mk(first, "user", [txt(first, "first request still waiting for the same provider turn")]),
      mk(second, "user", [txt(second, "second queued request")]),
    ]
    expect(SessionCompaction.selectTail(messages, { tailTurns: 1, tailTokens: 1 })).toEqual({})
  })
})
