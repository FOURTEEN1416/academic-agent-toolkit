import { describe, expect, test } from "bun:test"
import path from "node:path"
import { OpenScience } from "../../src/openscience"
import { Instance } from "../../src/project/instance"
import { Provider } from "../../src/provider/provider"
import { SessionFilesystem } from "../../src/session/filesystem"
import { ImageRoute } from "../../src/tool/image-route"
import {
  GenerateImageTool,
  SCHEMATIC_GUIDELINES,
  framedPrompt,
  extractGeneratedImage,
  extractGeneratedImageURL,
  generatedImageAttachments,
  readBoundedImageResponse,
} from "../../src/tool/generate-image"
import type { Tool } from "../../src/tool/tool"
import { executionSession, tmpdir } from "../fixture/fixture"

const PIXEL = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
  "base64",
)

function context(session: { id: string }, id: string, asks?: Parameters<Tool.Context["ask"]>[0][]): Tool.Context {
  return {
    sessionID: session.id,
    messageID: `msg_${id}`,
    callID: `call_${id}`,
    agent: "research",
    abort: new AbortController().signal,
    messages: [],
    metadata() {},
    async ask(input) {
      asks?.push(input)
    },
  }
}

describe("generate_image response parsing", () => {
  test("Ace renders through the managed gateway's image endpoint, one reference at a time", async () => {
    const requests: Array<{ url: string; authorization: string | null; body: Record<string, unknown> }> = []
    const gateway = Bun.serve({
      port: 0,
      async fetch(request) {
        const url = new URL(request.url)
        if (url.pathname.endsWith("/model-catalog")) return Response.json({ models: [] })
        if (!url.pathname.endsWith("/images")) return Response.json({})
        requests.push({
          url: url.pathname,
          authorization: request.headers.get("authorization"),
          body: (await request.json()) as Record<string, unknown>,
        })
        return Response.json({
          data: [{ b64_json: PIXEL.toString("base64"), media_type: "image/png" }],
          usage: { cost: 0.13 },
        })
      },
    })
    const base = process.env["OPENSCIENCE_API_BASE"]
    process.env["OPENSCIENCE_API_BASE"] = gateway.url.origin
    try {
      await using tmp = await tmpdir({ git: true, config: { billing: { llm: "managed" } } })
      await OpenScience.saveSession({
        api_key: "osk_fixture_image",
        user_id: "fixture",
        organization_id: "org_image",
        workspace_locked: true,
      })
      await Instance.provide({
        directory: tmp.path,
        init: async () => Provider.invalidate(),
        fn: async () => {
          expect((await Provider.getProvider("openrouter"))?.source).toBe("managed")
          const session = await executionSession()
          const workspace = await SessionFilesystem.workspace(session.id)
          const asks: Parameters<Tool.Context["ask"]>[0][] = []
          const tool = await GenerateImageTool.init()
          const input = tool.parameters.parse({
            prompt: "A precise monochrome benchmark schematic",
            output_path: "figures/benchmark.png",
            input_path: "/dev/null",
            model: "meta-llama/llama-3.3-70b-instruct",
            aspect_ratio: "16:9",
            image_size: "2K",
          })
          expect(input).not.toHaveProperty("model")
          const result = await tool.execute(input, context(session, "ace", asks))

          expect(requests).toHaveLength(1)
          // The managed envelope: OpenRouter's image API shape, `resolution`
          // for the size, funded by the Wallet behind the account key.
          expect(requests[0]).toMatchObject({
            url: "/api/llm/proxy/openrouter/v1/images",
            authorization: "Bearer osk_fixture_image",
            body: {
              model: "google/gemini-3-pro-image",
              prompt: "A precise monochrome benchmark schematic",
              n: 1,
              output_format: "png",
              aspect_ratio: "16:9",
              resolution: "2K",
            },
          })
          expect(requests[0]?.body).not.toHaveProperty("image_size")
          expect(asks.map((request) => request.permission)).toEqual(["generate_image", "edit"])
          expect(asks[0]?.metadata).toMatchObject({ model: "google/gemini-3-pro-image", route: "ace" })
          expect(await Bun.file(path.join(workspace, "figures", "benchmark.png")).arrayBuffer()).toEqual(
            PIXEL.buffer.slice(PIXEL.byteOffset, PIXEL.byteOffset + PIXEL.byteLength),
          )
          expect(result).toMatchObject({
            title: "figures/benchmark.png",
            output: expect.stringContaining("via Ace"),
            metadata: {
              route: "ace",
              model: "google/gemini-3-pro-image",
              mime: "image/png",
              size: PIXEL.byteLength,
              attachment: "inline",
            },
          })
          expect(result.attachments).toHaveLength(1)

          await Bun.write(path.join(workspace, "input.png"), PIXEL)
          await tool.execute(
            {
              prompt: "Preserve the source and improve its contrast",
              output_path: "figures/benchmark-edited.png",
              input_path: "input.png",
            },
            context(session, "ace_edit"),
          )
          expect(requests).toHaveLength(2)
          expect(requests[1]?.body).toMatchObject({
            input_references: [
              { type: "image_url", image_url: { url: expect.stringContaining("data:image/png;base64,") } },
            ],
          })
          // Ace's envelope takes one image; the tool says so before spending.
          await Bun.write(path.join(workspace, "style.png"), PIXEL)
          await expect(
            tool.execute(
              {
                prompt: "Restyle",
                output_path: "figures/benchmark-restyled.png",
                input_path: "input.png",
                reference_paths: ["style.png"],
              },
              context(session, "ace_two"),
            ),
          ).rejects.toThrow("Ace accepts one reference image per request")
          expect(requests).toHaveLength(2)
        },
      })
    } finally {
      if (base === undefined) delete process.env["OPENSCIENCE_API_BASE"]
      if (base !== undefined) process.env["OPENSCIENCE_API_BASE"] = base
      await OpenScience.clearSession()
      gateway.stop(true)
    }
  })

  test("a transient gateway failure is retried once, and an HTML error page is never echoed", async () => {
    let calls = 0
    const gateway = Bun.serve({
      port: 0,
      async fetch(request) {
        const url = new URL(request.url)
        if (url.pathname.endsWith("/model-catalog")) return Response.json({ models: [] })
        if (!url.pathname.endsWith("/images")) return Response.json({})
        calls += 1
        // The proxy in front of the image model answers with Cloudflare's page while it restarts.
        if (calls <= 2) {
          return new Response(
            "<!DOCTYPE html><html><head><title>openrouter.ai | 502: Bad gateway</title></head><body>…</body></html>",
            { status: 502, headers: { "content-type": "text/html" } },
          )
        }
        return Response.json({ data: [{ b64_json: PIXEL.toString("base64"), media_type: "image/png" }] })
      },
    })
    const base = process.env["OPENSCIENCE_API_BASE"]
    process.env["OPENSCIENCE_API_BASE"] = gateway.url.origin
    try {
      await using tmp = await tmpdir({ git: true, config: { billing: { llm: "managed" } } })
      await OpenScience.saveSession({
        api_key: "osk_fixture_image",
        user_id: "fixture",
        organization_id: "org_image",
        workspace_locked: true,
      })
      await Instance.provide({
        directory: tmp.path,
        init: async () => Provider.invalidate(),
        fn: async () => {
          const session = await executionSession()
          const tool = await GenerateImageTool.init()
          // Two 502s in a row: the tool retries once, then reports plainly.
          const failed = tool.execute(
            { prompt: "A benchmark schematic", output_path: "figures/first.png" },
            context(session, "ace_502"),
          )
          await expect(failed).rejects.toThrow(
            /Ace's image service did not answer \(HTTP 502, openrouter\.ai \| 502: Bad gateway\)/,
          )
          await expect(failed).rejects.not.toThrow(/DOCTYPE|<html/)
          expect(calls).toBe(2)
          // One 502 then success: the retry delivers the image.
          calls = 1
          const result = await tool.execute(
            { prompt: "A benchmark schematic", output_path: "figures/second.png" },
            context(session, "ace_retry"),
          )
          expect(calls).toBe(3)
          expect(result.metadata).toMatchObject({ route: "ace", size: PIXEL.byteLength })
        },
      })
    } finally {
      if (base === undefined) delete process.env["OPENSCIENCE_API_BASE"]
      if (base !== undefined) process.env["OPENSCIENCE_API_BASE"] = base
      await OpenScience.clearSession()
      gateway.stop(true)
    }
  }, 30_000)

  test("a schematic or illustration is framed by publication standards; an edit stays bare", () => {
    const framed = framedPrompt("Pipeline: Data -> Model -> Eval", "schematic")
    expect(framed.startsWith(SCHEMATIC_GUIDELINES)).toBe(true)
    expect(framed).toContain("Okabe-Ito")
    expect(framed).toContain("DO NOT ADD FIGURE NUMBERS")
    expect(framed.endsWith("DIAGRAM REQUEST:\nPipeline: Data -> Model -> Eval")).toBe(true)
    expect(framedPrompt("A helix", "illustration")).toContain("scientific illustration for a research publication")
    expect(framedPrompt("Widen the margins", "edit")).toBe("Widen the margins")
    expect(framedPrompt("A cat", undefined)).toBe("A cat")
  })

  test("a personal OpenRouter key is not an image route", async () => {
    const requests = { value: 0 }
    const server = Bun.serve({
      port: 0,
      fetch() {
        requests.value++
        return Response.json({ data: [{ b64_json: PIXEL.toString("base64") }] })
      },
    })
    try {
      await using tmp = await tmpdir({
        git: true,
        config: {
          provider: {
            openrouter: {
              options: { apiKey: "sk-or-personal-key", baseURL: `http://127.0.0.1:${server.port}/v1` },
            },
          },
        },
      })
      await Instance.provide({
        directory: tmp.path,
        init: async () => Provider.invalidate(),
        fn: async () => {
          expect(await Provider.getProvider("openrouter")).toBeDefined()
          expect(await ImageRoute.resolve()).toBeUndefined()
          expect(await ImageRoute.line()).toContain("unavailable")
          const session = await executionSession()
          const tool = await GenerateImageTool.init()
          await expect(
            tool.execute({ prompt: "A benchmark schematic", output_path: "figure.png" }, context(session, "personal")),
          ).rejects.toThrow("Turn on Ace, or connect a Gemini or OpenAI key")
          expect(requests.value).toBe(0)
        },
      })
    } finally {
      server.stop(true)
    }
  })

  test("renders with GPT Image 2 through the user's own OpenAI key, edits as multipart", async () => {
    const requests: Array<{
      url: string
      authorization: string | null
      json?: Record<string, unknown>
      form?: Record<string, string | { name: string; type: string; size: number }[]>
    }> = []
    const server = Bun.serve({
      port: 0,
      async fetch(request) {
        const url = new URL(request.url).pathname
        const authorization = request.headers.get("authorization")
        if (request.headers.get("content-type")?.startsWith("multipart/form-data")) {
          const data = await request.formData()
          const form: Record<string, string | { name: string; type: string; size: number }[]> = {}
          for (const [key, value] of data.entries()) {
            if (typeof value === "string") {
              form[key] = value
              continue
            }
            const file = value as File
            const files = (form[key] ?? []) as { name: string; type: string; size: number }[]
            files.push({ name: file.name, type: file.type, size: file.size })
            form[key] = files
          }
          requests.push({ url, authorization, form })
        } else {
          requests.push({ url, authorization, json: (await request.json()) as Record<string, unknown> })
        }
        return Response.json({
          data: [{ b64_json: PIXEL.toString("base64") }],
          usage: { input_tokens: 12, output_tokens: 1056 },
        })
      },
    })
    try {
      await using tmp = await tmpdir({
        git: true,
        config: {
          provider: {
            openai: {
              options: { apiKey: "sk-openai-local-image", baseURL: `http://127.0.0.1:${server.port}/v1` },
            },
          },
        },
      })
      await Instance.provide({
        directory: tmp.path,
        init: async () => Provider.invalidate(),
        fn: async () => {
          const session = await executionSession()
          const workspace = await SessionFilesystem.workspace(session.id)
          const tool = await GenerateImageTool.init()
          const result = await tool.execute(
            { prompt: "A benchmark schematic", output_path: "figures/openai.webp", aspect_ratio: "16:9" },
            context(session, "openai"),
          )
          expect(requests[0]).toMatchObject({
            url: "/v1/images/generations",
            authorization: "Bearer sk-openai-local-image",
            json: {
              model: "gpt-image-2",
              prompt: "A benchmark schematic",
              n: 1,
              size: "1536x864",
              quality: "medium",
              output_format: "webp",
            },
          })
          expect(result.metadata).toMatchObject({ route: "openai", model: "gpt-image-2" })
          expect(result.output).toContain("via your OpenAI key")

          await Bun.write(path.join(workspace, "draft.png"), PIXEL)
          await Bun.write(path.join(workspace, "style.png"), PIXEL)
          await tool.execute(
            {
              prompt: "Keep the layout, match the reference palette",
              output_path: "figures/openai-edited.png",
              input_path: "draft.png",
              reference_paths: ["style.png"],
              image_size: "2K",
            },
            context(session, "openai_edit"),
          )
          expect(requests[1]).toMatchObject({
            url: "/v1/images/edits",
            authorization: "Bearer sk-openai-local-image",
            form: {
              model: "gpt-image-2",
              prompt: "Keep the layout, match the reference palette",
              n: "1",
              size: "2048x2048",
              quality: "high",
              output_format: "png",
              "image[]": [
                { name: "reference-1.png", type: "image/png", size: PIXEL.byteLength },
                { name: "reference-2.png", type: "image/png", size: PIXEL.byteLength },
              ],
            },
          })
        },
      })
    } finally {
      server.stop(true)
    }
  })

  test("prefers a connected Gemini key and pins the stable image-only model", async () => {
    const image = Buffer.from(
      "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
      "base64",
    )
    const requests: Array<{ url: string; key: string | null; body: Record<string, unknown> }> = []
    const server = Bun.serve({
      port: 0,
      async fetch(request) {
        requests.push({
          url: new URL(request.url).pathname,
          key: request.headers.get("x-goog-api-key"),
          body: (await request.json()) as Record<string, unknown>,
        })
        return Response.json({
          candidates: [
            { content: { parts: [{ inlineData: { mimeType: "image/png", data: image.toString("base64") } }] } },
          ],
        })
      },
    })
    try {
      await using tmp = await tmpdir({
        git: true,
        config: {
          provider: {
            google: {
              options: {
                apiKey: "gemini-local-image-route",
                baseURL: `http://127.0.0.1:${server.port}/v1beta`,
              },
            },
          },
        },
      })
      await Instance.provide({
        directory: tmp.path,
        init: async () => Provider.invalidate(),
        fn: async () => {
          const session = await executionSession()
          const tool = await GenerateImageTool.init()
          const result = await tool.execute(
            { prompt: "A precise benchmark diagram", output_path: "gemini.png" },
            {
              sessionID: session.id,
              messageID: "msg_gemini_image",
              callID: "call_gemini_image",
              agent: "research",
              abort: new AbortController().signal,
              messages: [],
              metadata() {},
              async ask() {},
            },
          )
          expect(requests).toHaveLength(1)
          expect(requests[0]).toMatchObject({
            url: "/v1beta/models/gemini-3-pro-image:generateContent",
            key: "gemini-local-image-route",
            body: {
              contents: [{ role: "user", parts: [{ text: "A precise benchmark diagram" }] }],
              generationConfig: { responseModalities: ["IMAGE"] },
            },
          })
          expect(result.metadata).toMatchObject({
            model: "gemini-3-pro-image",
            route: "gemini",
          })

          await tool.execute(
            { prompt: "A wide benchmark diagram", output_path: "gemini-wide.png", aspect_ratio: "16:9" },
            {
              sessionID: session.id,
              messageID: "msg_gemini_wide_image",
              callID: "call_gemini_wide_image",
              agent: "research",
              abort: new AbortController().signal,
              messages: [],
              metadata() {},
              async ask() {},
            },
          )
          expect(requests[1]?.body).toMatchObject({
            generationConfig: {
              responseModalities: ["IMAGE"],
              imageConfig: { aspectRatio: "16:9" },
            },
          })

          // Reference figures ride along as extra image parts, and the print
          // resolution is a first-class request field.
          const workspace = await SessionFilesystem.workspace(session.id)
          await Bun.write(path.join(workspace, "reference-a.png"), image)
          await Bun.write(path.join(workspace, "reference-b.png"), image)
          await tool.execute(
            {
              prompt: "A method overview in the style of the references",
              output_path: "gemini-styled.png",
              image_size: "2K",
              reference_paths: ["reference-a.png", "reference-b.png"],
            },
            {
              sessionID: session.id,
              messageID: "msg_gemini_styled_image",
              callID: "call_gemini_styled_image",
              agent: "research",
              abort: new AbortController().signal,
              messages: [],
              metadata() {},
              async ask() {},
            },
          )
          const styled = requests[2]?.body as {
            contents: Array<{ parts: unknown[] }>
            generationConfig: { imageConfig?: { imageSize?: string } }
          }
          expect(styled.contents[0]?.parts).toHaveLength(3)
          expect(styled.generationConfig.imageConfig).toEqual({ imageSize: "2K" })
          await expect(
            tool.execute(
              { prompt: "x", output_path: "gemini-bad.png", reference_paths: ["notes.txt"] },
              {
                sessionID: session.id,
                messageID: "msg_gemini_bad_reference",
                callID: "call_gemini_bad_reference",
                agent: "research",
                abort: new AbortController().signal,
                messages: [],
                metadata() {},
                async ask() {},
              },
            ),
          ).rejects.toThrow("reference_paths must name existing image files")
        },
      })
    } finally {
      server.stop(true)
    }
  })

  test("rejects unsupported external image paths before requesting filesystem approval", async () => {
    await using tmp = await tmpdir({ git: true })
    await Instance.provide({
      directory: tmp.path,
      init: async () => Provider.invalidate(),
      fn: async () => {
        const session = await executionSession()
        const tool = await GenerateImageTool.init()
        const asks: Parameters<Tool.Context["ask"]>[0][] = []
        const ctx: Tool.Context = {
          sessionID: session.id,
          messageID: "msg_invalid_image_paths",
          callID: "call_invalid_image_paths",
          agent: "research",
          abort: new AbortController().signal,
          messages: [],
          metadata() {},
          async ask(input) {
            asks.push(input)
          },
        }

        await expect(tool.execute({ prompt: "figure", output_path: "/tmp/not-an-image.txt" }, ctx)).rejects.toThrow(
          "output_path must end in",
        )
        await expect(
          tool.execute(
            {
              prompt: "figure",
              output_path: "figure.png",
              input_path: "/tmp/not-an-image",
            },
            ctx,
          ),
        ).rejects.toThrow("input_path must be an existing")
        expect(asks).toHaveLength(0)
      },
    })
  })

  test("rejects a retired product token before contacting an image host", async () => {
    const requests = { value: 0 }
    const server = Bun.serve({
      port: 0,
      fetch() {
        requests.value++
        return Response.json({ data: [] })
      },
    })
    try {
      await using tmp = await tmpdir({
        git: true,
        config: {
          enabled_providers: ["openrouter"],
          provider: {
            openrouter: {
              options: {
                apiKey: "thk_managed-image-route",
                baseURL: `http://127.0.0.1:${server.port}/v1`,
              },
            },
          },
        },
      })
      await Instance.provide({
        directory: tmp.path,
        init: async () => Provider.invalidate(),
        fn: async () => {
          expect(await Provider.getProvider("google")).toBeUndefined()
          expect(await Provider.getProvider("openrouter")).toBeUndefined()
          const session = await executionSession()
          const tool = await GenerateImageTool.init()
          await expect(
            tool.execute(
              {
                prompt: "A benchmark schematic",
                output_path: "figure.png",
              },
              {
                sessionID: session.id,
                messageID: "msg_managed_image",
                callID: "call_managed_image",
                agent: "research",
                abort: new AbortController().signal,
                messages: [],
                metadata() {},
                async ask() {},
              },
            ),
          ).rejects.toThrow("Turn on Ace, or connect a Gemini or OpenAI key")
          expect(requests.value).toBe(0)
        },
      })
    } finally {
      server.stop(true)
    }
  })

  test("rejects GIF output before constructing an unsupported OpenRouter request", async () => {
    await using tmp = await tmpdir({ git: true })
    await Instance.provide({
      directory: tmp.path,
      init: async () => Provider.invalidate(),
      fn: async () => {
        const session = await executionSession()
        const tool = await GenerateImageTool.init()
        await expect(
          tool.execute(
            {
              prompt: "A benchmark schematic",
              output_path: "figure.gif",
            },
            {
              sessionID: session.id,
              messageID: "msg_gif_image",
              callID: "call_gif_image",
              agent: "research",
              abort: new AbortController().signal,
              messages: [],
              metadata() {},
              async ask() {},
            },
          ),
        ).rejects.toThrow("output_path must end in .png, .jpg, .jpeg, or .webp")
      },
    })
  })

  test("extracts the dedicated OpenRouter Image API response", () => {
    const bytes = Buffer.from("dedicated-image-bytes")
    const image = extractGeneratedImage({
      data: [{ b64_json: bytes.toString("base64"), media_type: "image/png" }],
    })

    expect(image.mime).toBe("image/png")
    expect(image.bytes).toEqual(bytes)
  })

  test("extracts the OpenRouter images response used by Nano Banana", () => {
    const bytes = Buffer.from("image-bytes")
    const image = extractGeneratedImage({
      choices: [
        {
          message: {
            images: [{ image_url: { url: `data:image/png;base64,${bytes.toString("base64")}` } }],
          },
        },
      ],
    })

    expect(image.mime).toBe("image/png")
    expect(image.bytes).toEqual(bytes)
  })

  test("extracts image parts from multimodal content", () => {
    const bytes = Buffer.from("webp-bytes")
    const image = extractGeneratedImage({
      choices: [
        {
          message: {
            content: [{ type: "image", image_url: `data:image/webp;base64,${bytes.toString("base64")}` }],
          },
        },
      ],
    })

    expect(image.mime).toBe("image/webp")
    expect(image.bytes).toEqual(bytes)
  })

  test("extracts a downloadable image URL from the OpenRouter server tool response", () => {
    expect(
      extractGeneratedImageURL({
        choices: [
          {
            message: {
              content: [{ type: "text", text: '{"status":"ok","imageUrl":"https://images.example/test.png"}' }],
            },
          },
        ],
      }),
    ).toBe("https://images.example/test.png")
  })

  test("rejects a response with no generated image", () => {
    expect(() =>
      extractGeneratedImage({ choices: [{ message: { content: [{ type: "text", text: "no image" }] } }] }),
    ).toThrow("without returning image bytes")
  })

  test("streams successful response bodies within an explicit byte ceiling", async () => {
    const response = new Response(
      new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(Buffer.from("first"))
          controller.enqueue(Buffer.from("second"))
          controller.close()
        },
      }),
    )

    expect((await readBoundedImageResponse(response, 11)).toString()).toBe("firstsecond")
  })

  test("cancels a streamed response as soon as its real body exceeds the ceiling", async () => {
    const cancelled = { value: false }
    const response = new Response(
      new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(Buffer.from("1234"))
          controller.enqueue(Buffer.from("5678"))
        },
        cancel() {
          cancelled.value = true
        },
      }),
      { headers: { "content-length": "4" } },
    )

    await expect(readBoundedImageResponse(response, 6)).rejects.toThrow("6-byte safety limit")
    expect(cancelled.value).toBe(true)
  })

  test("rejects an oversized declared response before accumulating its body", async () => {
    const cancelled = { value: false }
    const response = new Response(
      new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(Buffer.from("small"))
        },
        cancel() {
          cancelled.value = true
        },
      }),
      { headers: { "content-length": "100" } },
    )

    await expect(readBoundedImageResponse(response, 10)).rejects.toThrow("10-byte safety limit")
    expect(cancelled.value).toBe(true)
  })

  test("keeps large generated images artifact-only instead of embedding a huge data URL", () => {
    const attachments = generatedImageAttachments({
      bytes: Buffer.alloc(8 * 1024 * 1024 + 1),
      mime: "image/png",
      filepath: "/workspace/large.png",
      sessionID: "ses_test",
      messageID: "msg_test",
    })

    expect(attachments).toEqual([])
  })

  test("retains an inline attachment for a small generated image", () => {
    const attachments = generatedImageAttachments({
      bytes: Buffer.from("small image"),
      mime: "image/png",
      filepath: "/workspace/small.png",
      sessionID: "ses_test",
      messageID: "msg_test",
    })

    expect(attachments).toHaveLength(1)
    expect(attachments[0]?.filename).toBe("small.png")
    expect(attachments[0]?.url).toBe(`data:image/png;base64,${Buffer.from("small image").toString("base64")}`)
  })
})
