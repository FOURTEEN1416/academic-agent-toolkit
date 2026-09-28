import { describe, expect, test } from "bun:test"
import path from "node:path"
import { Instance } from "../../src/project/instance"
import { ProvenanceEnvelope } from "../../src/science/provenance/envelope"
import { Provenance } from "../../src/science/provenance/store"
import { FileRoutes } from "../../src/server/routes/file"
import { tmpdir } from "../fixture/fixture"

interface Lineage {
  runs: Array<Record<string, unknown>>
  messages: Array<{ sessionID: string; messageID: string }>
}

describe("/file/lineage", () => {
  test("returns producing runs and deduped messages for a project file", async () => {
    await using tmp = await tmpdir()
    await Instance.provide({
      directory: tmp.path,
      fn: async () => {
        const scope = { projectID: Instance.project.id, directory: Instance.directory }
        const session = "ses_lineage_primary"
        const other = "ses_lineage_other"
        const file = path.join(tmp.path, "results", "figure.png")
        await Bun.write(file, "png-bytes")
        const started = Date.now() - 1_000
        const completed = Date.now()
        const run = await Provenance.recordOwned(scope, {
          kind: "run",
          label: "python cell · agent",
          tool: "notebook",
          sessionID: session,
          status: "ok",
          inputs: { kernel: "agent", language: "python", code: "plot()" },
          provenance: ProvenanceEnvelope.create({
            kind: "kernel",
            projectID: Instance.project.id,
            sessionID: session,
            runID: "run-lineage-primary",
            code: "plot()",
            cwd: tmp.path,
            kernel: { id: "kernel-lineage", language: "python" },
            status: "succeeded",
            outputs: [
              ProvenanceEnvelope.output({
                kind: "artifact",
                label: "results/figure.png",
                path: "results/figure.png",
                content: "png-bytes",
                createdAt: completed,
              }),
            ],
            createdAt: started,
            startedAt: started,
            completedAt: completed,
          }),
          meta: { messageID: "msg_lineage", callID: "call_lineage", kernelName: "agent" },
        } as Parameters<typeof Provenance.record>[0])
        const artifact = await Provenance.recordOwned(scope, {
          kind: "artifact",
          label: "figure.png",
          artifactType: "figure",
          path: file,
          meta: { sessionID: session, messageID: "msg_lineage" },
        } as Parameters<typeof Provenance.record>[0])
        await Provenance.link({ from: run.id, to: artifact.id, relation: "produced" })
        const envelope = await Provenance.recordOwned(scope, {
          kind: "run",
          label: "python cell · rewrite",
          tool: "notebook",
          sessionID: other,
          status: "ok",
          provenance: ProvenanceEnvelope.create({
            kind: "kernel",
            projectID: Instance.project.id,
            sessionID: other,
            runID: "run-lineage-envelope",
            code: "save()",
            status: "succeeded",
            outputs: [
              ProvenanceEnvelope.output({
                kind: "artifact",
                label: "results/figure.png",
                path: "results/figure.png",
                content: "png-bytes-v2",
                createdAt: completed,
              }),
            ],
          }),
          meta: { messageID: "msg_envelope" },
        } as Parameters<typeof Provenance.record>[0])

        const app = FileRoutes()
        const response = await app.request(`/file/lineage?path=${encodeURIComponent("results/figure.png")}`)
        expect(response.status).toBe(200)
        const body = (await response.json()) as Lineage
        expect(body.runs).toHaveLength(2)
        expect(body.runs.find((item) => item.id === run.id)).toMatchObject({
          id: run.id,
          tool: "notebook",
          label: "python cell · agent",
          status: "ok",
          sessionID: session,
          messageID: "msg_lineage",
          callID: "call_lineage",
          code: "plot()",
          cwd: tmp.path,
          kernel: { language: "python", name: "agent" },
          startedAt: new Date(started).toISOString(),
          completedAt: new Date(completed).toISOString(),
        })
        expect(body.runs.find((item) => item.id === envelope.id)).toMatchObject({
          id: envelope.id,
          sessionID: other,
          messageID: "msg_envelope",
          code: "save()",
        })
        expect(body.messages).toHaveLength(2)
        expect(body.messages).toContainEqual({ sessionID: session, messageID: "msg_lineage" })
        expect(body.messages).toContainEqual({ sessionID: other, messageID: "msg_envelope" })

        const absolute = await app.request(`/file/lineage?path=${encodeURIComponent(file)}`)
        expect(((await absolute.json()) as Lineage).runs).toHaveLength(2)

        const filtered = await app.request(
          `/file/lineage?path=${encodeURIComponent("results/figure.png")}&sessionID=${session}`,
        )
        const scoped = (await filtered.json()) as Lineage
        expect(scoped.runs.map((item) => item.id)).toEqual([run.id])
        expect(scoped.messages).toEqual([{ sessionID: session, messageID: "msg_lineage" }])
      },
    })
  })

  test("returns empty lineage for an unrelated path", async () => {
    await using tmp = await tmpdir()
    await Instance.provide({
      directory: tmp.path,
      fn: async () => {
        const response = await FileRoutes().request(`/file/lineage?path=${encodeURIComponent("missing/nothing.csv")}`)
        expect(response.status).toBe(200)
        expect((await response.json()) as Lineage).toEqual({ runs: [], messages: [] })
      },
    })
  })
})
