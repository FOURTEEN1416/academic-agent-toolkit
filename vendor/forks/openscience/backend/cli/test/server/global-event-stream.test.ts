import { describe, expect, test } from "bun:test"
import path from "path"
import { GlobalBus } from "../../src/bus/global"
import { Instance } from "../../src/project/instance"
import { Server } from "../../src/server/server"
import { MessageV2 } from "../../src/session/message-v2"
import { Log } from "../../src/util/log"

const projectRoot = path.join(__dirname, "../..")
Log.init({ print: false })

const PING = "test.global.event.stream.ping"
const CONNECTED = "server.connected"

type Frame = {
  directory?: string
  payload: { type: string; properties: { n?: number; part?: { text?: string } } }
}

async function frames(body: ReadableStream<Uint8Array>, until: (frame: Frame) => boolean, deadline = 10_000) {
  const reader = body.getReader()
  // A frame that never arrives must fail on its assertion rather than hang the
  // suite, so give the read loop its own bound.
  const timer = setTimeout(() => void reader.cancel().catch(() => undefined), deadline)
  const decoder = new TextDecoder()
  const result: Frame[] = []
  const pending = { text: "" }
  try {
    for (;;) {
      const chunk = await reader.read()
      if (chunk.done) return result
      pending.text += decoder.decode(chunk.value, { stream: true })
      const parts = pending.text.split("\n\n")
      pending.text = parts.pop() ?? ""
      for (const part of parts) {
        const data = part
          .split("\n")
          .filter((line) => line.startsWith("data: "))
          .map((line) => line.slice(6))
          .join("\n")
        if (!data) continue
        const frame = JSON.parse(data) as Frame
        result.push(frame)
        if (until(frame)) return result
      }
    }
  } finally {
    clearTimeout(timer)
    await reader.cancel().catch(() => undefined)
  }
}

function partUpdate(version: number, id: string) {
  return {
    directory: projectRoot,
    payload: {
      type: MessageV2.Event.PartUpdated.type,
      properties: {
        part: {
          id,
          sessionID: "ses_global_event_stream",
          messageID: "msg_global_event_stream",
          type: "text",
          text: String(version),
        },
        delta: String(version),
      },
    },
  }
}

describe("global.event", () => {
  test("a client that never reads its socket buffers a bounded number of events", async () => {
    await Instance.provide({
      directory: projectRoot,
      fn: async () => {
        const fetch = Server.internalFetch()
        const response = await fetch("http://openscience.internal/global/event")
        expect(response.status).toBe(200)
        expect(response.body).not.toBeNull()

        // Nothing reads the response body, so the socket is backpressured after
        // its first frame. The connection must buffer a bounded number of
        // events instead of retaining one pending write per emit forever.
        const total = 5000
        for (let n = 0; n < total; n++) {
          GlobalBus.emit("event", { directory: "global", payload: { type: PING, properties: { n } } })
        }

        const received = await frames(response.body!, (frame) => frame.payload.properties.n === total - 1, 5_000)
        const pings = received
          .filter((frame) => frame.payload.type === PING)
          .map((frame) => frame.payload.properties.n!)
        // Delivery keeps stream order, converges on the newest events, and the
        // bounded queue dropped the oldest rather than the newest ones.
        expect(pings.at(-1)).toBe(total - 1)
        expect(pings.every((n, index) => index === 0 || n > pings[index - 1]!)).toBe(true)
        expect(pings.length).toBeLessThan(total)
        expect(pings.length).toBeGreaterThan(1_000)

        // One frame opens the stream and one more announces the overflow. The
        // second leads the whole surviving backlog, so the client re-hydrates
        // before replaying it rather than over the top of it. Only the events
        // that escaped before backpressure precede it.
        const connected = received.filter((frame) => frame.payload.type === CONNECTED)
        expect(connected).toHaveLength(2)
        const replayed = received.slice(received.indexOf(connected[1]!)).filter((frame) => frame.payload.type === PING)
        expect(replayed.length).toBeGreaterThan(1_000)
        expect(replayed.at(-1)?.payload.properties.n).toBe(total - 1)
      },
    })
  })

  test("a full queue of coalescible updates alone never asks the client to re-hydrate", async () => {
    await Instance.provide({
      directory: projectRoot,
      fn: async () => {
        const fetch = Server.internalFetch()
        const response = await fetch("http://openscience.internal/global/event")
        expect(response.status).toBe(200)
        expect(response.body).not.toBeNull()

        // Every event names the same part in the same directory, so a full
        // queue only ever takes the replacement branch and never the eviction
        // branch. Replacement loses nothing, so there is nothing to announce.
        const total = 3000
        for (let version = 1; version <= total; version++) {
          GlobalBus.emit("event", partUpdate(version, "prt_global_coalesce"))
        }

        // Read to the deadline rather than to a known frame. A second connected
        // frame would land among the updates, where a reader that stops on
        // content might never look.
        const received = await frames(response.body!, () => false, 2_500)
        const versions = received
          .filter((frame) => frame.payload.type === MessageV2.Event.PartUpdated.type)
          .map((frame) => Number(frame.payload.properties.part!.text))
        // Fewer frames than publishes proves the queue filled and the
        // replacement branch actually ran; ending on the newest proves the
        // reader drained everything the connection had.
        expect(versions.length).toBeLessThan(total)
        expect(versions.at(-1)).toBe(total)
        expect(received.filter((frame) => frame.payload.type === CONNECTED)).toHaveLength(1)
      },
    })
  })

  test("an overflowing queue evicts part updates before anything else", async () => {
    await Instance.provide({
      directory: projectRoot,
      fn: async () => {
        const fetch = Server.internalFetch()
        const response = await fetch("http://openscience.internal/global/event")
        expect(response.status).toBe(200)
        expect(response.body).not.toBeNull()

        // The events the client can never rebuild are the OLDEST here, so
        // evicting the plain oldest would throw exactly them away. Only a queue
        // that prefers to sacrifice part updates keeps them all.
        const ping = (n: number) =>
          GlobalBus.emit("event", { directory: "global", payload: { type: PING, properties: { n } } })
        const total = 600
        for (let n = 0; n < 400; n++) ping(n)
        const parts = 1_900
        for (let n = 0; n < parts; n++) GlobalBus.emit("event", partUpdate(n, `prt_global_victim_${n}`))
        for (let n = 400; n < total; n++) ping(n)

        const received = await frames(response.body!, (frame) => frame.payload.properties.n === total - 1, 5_000)
        const pings = received
          .filter((frame) => frame.payload.type === PING)
          .map((frame) => frame.payload.properties.n!)
        const updates = received.filter((frame) => frame.payload.type === MessageV2.Event.PartUpdated.type)
        // Every non-part event survived, and part updates paid for them.
        expect(pings).toEqual(Array.from({ length: total }, (_, n) => n))
        expect(updates.length).toBeLessThan(parts)
      },
    })
  })

  test("a second overflow on one connection asks the client to resync again", async () => {
    await Instance.provide({
      directory: projectRoot,
      fn: async () => {
        const fetch = Server.internalFetch()
        const response = await fetch("http://openscience.internal/global/event")
        expect(response.status).toBe(200)
        expect(response.body).not.toBeNull()

        // One reader spans both overflows, because the second resync is only
        // due once the first frame has actually reached the client.
        const reader = response.body!.getReader()
        const decoder = new TextDecoder()
        const pending = { text: "" }
        let connected = 0
        const take = (chunk: ReadableStreamReadResult<Uint8Array>) => {
          pending.text += decoder.decode(chunk.value, { stream: true })
          const parts = pending.text.split("\n\n")
          pending.text = parts.pop() ?? ""
          for (const part of parts) {
            const data = part
              .split("\n")
              .filter((line) => line.startsWith("data: "))
              .map((line) => line.slice(6))
              .join("\n")
            if (!data) continue
            if ((JSON.parse(data) as Frame).payload.type === CONNECTED) connected++
          }
        }
        const waitFor = async (want: number) => {
          const deadline = Date.now() + 15_000
          while (connected < want && Date.now() < deadline) {
            const chunk = await reader.read()
            if (chunk.done) return false
            take(chunk)
          }
          return connected >= want
        }
        // Only pings can still arrive once the resync is counted, so racing the
        // read here and losing one to the timeout costs nothing.
        const settle = async () => {
          for (;;) {
            const chunk = await Promise.race([reader.read(), Bun.sleep(300).then(() => undefined)])
            if (!chunk || chunk.done) return
            take(chunk)
          }
        }
        const flood = (from: number) => {
          for (let n = from; n < from + 3000; n++)
            GlobalBus.emit("event", { directory: "global", payload: { type: PING, properties: { n } } })
        }

        flood(0)
        // The handshake frame plus the resync raised by the first overflow.
        expect(await waitFor(2)).toBe(true)
        // Empty the queue so the next overflow starts from a clean connection
        // that has already been told to re-hydrate.
        await settle()
        flood(3000)
        // A latch that never clears leaves the workspace stale until it
        // reloads, because the second loss raises no frame of its own.
        expect(await waitFor(3)).toBe(true)
        await reader.cancel().catch(() => undefined)
      },
    })
  }, 30_000)
})
