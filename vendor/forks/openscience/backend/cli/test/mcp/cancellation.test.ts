import { expect, test } from "bun:test"
import fs from "node:fs/promises"
import { tmpdir } from "../fixture/fixture"
import { spawn } from "../fixture/spawn"

/** Stop a tool call that is already running on a real MCP server, aborting with
 * `reason`, and report what both ends saw. */
async function stopInFlightCall(reason: string) {
  await using tmp = await tmpdir()
  const runner = `${tmp.path}/cancellation.ts`
  const marker = `${tmp.path}/cancel.txt`
  const server = new URL("../fixture/mcp-cancellation.mjs", import.meta.url).pathname

  await Bun.write(
    `${tmp.path}/openscience.json`,
    JSON.stringify({
      mcp: {
        stop: {
          type: "local",
          command: [process.execPath, server],
          environment: { OPENSCIENCE_MCP_CANCEL_MARKER: marker },
          // Long enough that a request timeout can never be mistaken for the
          // abort these tests are asserting on.
          timeout: 30_000,
        },
      },
    }),
  )

  await Bun.write(
    runner,
    `
import fs from "node:fs/promises"
import { MCP } from ${JSON.stringify(new URL("../../src/mcp/index.ts", import.meta.url).href)}
import { Instance } from ${JSON.stringify(new URL("../../src/project/instance.ts", import.meta.url).href)}
import { ProjectTrust } from ${JSON.stringify(new URL("../../src/project/trust.ts", import.meta.url).href)}

const marker = process.argv[3]
const reason = process.argv[4]

async function waitFor(text, budget) {
  const deadline = Date.now() + budget
  while (Date.now() < deadline) {
    const seen = await fs.readFile(marker, "utf8").catch(() => "")
    if (seen.includes(text)) return seen
    await new Promise((resolve) => setTimeout(resolve, 20))
  }
  return await fs.readFile(marker, "utf8").catch(() => "")
}

const result = await Instance.provide({
  directory: process.argv[2],
  fn: async () => {
    const trust = await ProjectTrust.status(Instance.project)
    await ProjectTrust.update(Instance.project, { trusted: true, root: trust.root })

    const hang = (await MCP.tools())["stop_hang"]
    const controller = new AbortController()
    const call = Promise.resolve(
      hang.execute({}, { toolCallId: "call_stop", messages: [], abortSignal: controller.signal }),
    ).then(
      () => ({ outcome: "resolved" }),
      (error) => ({ outcome: "rejected", name: error?.name ?? null, message: String(error?.message ?? error) }),
    )

    // Abort only once the server holds the request, so the assertion is about
    // cancellation rather than a race with request delivery.
    await waitFor("started", 8_000)
    const stopped = Date.now()
    if (reason === "default") controller.abort()
    else if (reason === "error") controller.abort(new Error("Interrupted: MCP credentials changed"))
    else if (reason === "misleading-error") controller.abort(new Error("Request aborted after credentials changed"))
    else if (reason === "secret") controller.abort("Bearer mcp-server-secret")
    else controller.abort(reason)

    const outcome = await Promise.race([
      call,
      new Promise((resolve) => setTimeout(() => resolve({ outcome: "pending" }), 3_000)),
    ])
    const elapsed = Date.now() - stopped
    const observed = await waitFor("cancelled", 3_000)
    await MCP.disposeLocal().catch(() => {})
    return { outcome, elapsed, observed }
  },
})
process.stdout.write(JSON.stringify(result))
process.exit(0)
`,
  )

  const proc = spawn([process.execPath, runner, tmp.path, marker, reason], {
    cwd: tmp.path,
    stdout: "pipe",
    stderr: "pipe",
  })
  const [output, error, exit] = await Promise.all([
    new Response(proc.stdout).text(),
    new Response(proc.stderr).text(),
    proc.exited,
  ])
  expect(exit, error).toBe(0)
  return { ...JSON.parse(output), started: await fs.readFile(marker, "utf8") }
}

test("stopping a turn cancels the in-flight MCP request at the server", async () => {
  const result = await stopInFlightCall("openscience-session-stopped")

  // The server saw cancellation, not a request timeout: the cancellation
  // reached the remote peer instead of being abandoned locally.
  expect(result.started).toContain("started")
  expect(result.observed).toContain("cancelled MCP tool call cancelled")
  expect(result.outcome.outcome).toBe("rejected")
  expect(result.elapsed).toBeLessThan(3_000)

  // A stopped call reports cancellation, not the RequestTimeout the MCP SDK
  // raises for it, so callers that key on the name do not read Stop as failure.
  expect(result.outcome.name).toBe("AbortError")
  expect(result.outcome.message).not.toContain("timed out")
  expect(result.outcome.message).toMatch(/\baborted\b/i)
}, 30_000)

test("a plain Stop keeps the abort reason it was given", async () => {
  // Every production Stop path calls abort() with no reason, so the runtime
  // supplies the AbortError itself. That one is already right and is passed
  // through rather than rewrapped.
  const result = await stopInFlightCall("default")

  expect(result.outcome.outcome).toBe("rejected")
  expect(result.outcome.name).toBe("AbortError")
  expect(result.outcome.message).toMatch(/\baborted\b/i)
  expect(result.outcome.message).not.toContain("The MCP tool call was aborted:")
}, 30_000)

test("a turn aborted for an unrelated reason still reports cancellation", async () => {
  // Loop disposal and credential revocation abort with their own reason, whose
  // wording never mentions cancellation. The tool card reads that wording, so
  // the reason has to be carried without losing what happened.
  const result = await stopInFlightCall("error")

  expect(result.outcome.outcome).toBe("rejected")
  expect(result.outcome.name).toBe("AbortError")
  expect(result.outcome.message).toMatch(/\baborted\b/i)
  expect(result.outcome.message).toContain("MCP credentials changed")
}, 30_000)

test("an ordinary Error mentioning aborted is still classified as cancellation", async () => {
  const result = await stopInFlightCall("misleading-error")

  expect(result.outcome.outcome).toBe("rejected")
  expect(result.outcome.name).toBe("AbortError")
  expect(result.outcome.message).toContain("Request aborted after credentials changed")
}, 30_000)

test("the protocol cancellation does not disclose the local abort reason", async () => {
  const result = await stopInFlightCall("secret")

  expect(result.outcome.outcome).toBe("rejected")
  expect(result.outcome.name).toBe("AbortError")
  expect(result.observed).toContain("cancelled MCP tool call cancelled")
  expect(result.observed).not.toContain("mcp-server-secret")
}, 30_000)
