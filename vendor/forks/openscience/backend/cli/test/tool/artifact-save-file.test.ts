import { expect, test } from "bun:test"
import path from "node:path"
import { ArtifactStore } from "../../src/artifact/store"
import { Instance } from "../../src/project/instance"
import { ProvenanceEnvelope } from "../../src/science/provenance/envelope"
import { Provenance } from "../../src/science/provenance/store"
import { Experiments } from "../../src/experiments"
import { SessionFilesystem } from "../../src/session/filesystem"
import { ArtifactTool } from "../../src/tool/artifact"
import { executionSession, tmpdir } from "../fixture/fixture"
import { ManagedProject } from "../../src/project/managed"
import { Session } from "../../src/session"

const context = (sessionID: string) => ({
  sessionID,
  messageID: "msg_artifact_save_file",
  callID: "call_artifact_save_file",
  agent: "research",
  abort: new AbortController().signal,
  messages: [],
  metadata() {},
  async ask() {},
})

test.each(["\ufeff", "\ufeff" + "α".repeat(25_599) + "🧬ending"])(
  "artifact read_file preserves BOM bytes and advances exact UTF-8 offsets",
  async (content) => {
    await using tmp = await tmpdir({ git: true })
    await Instance.provide({
      directory: tmp.path,
      fn: async () => {
        const session = await executionSession()
        const tool = await ArtifactTool.init()
        const source = path.join(await SessionFilesystem.workspace(session.id), "bom.txt")
        await Bun.write(source, content)
        const saved = await tool.execute({ action: "save_file", path: source }, context(session.id))
        const handle = saved.metadata.savedArtifact as { id: string; versionID: string }
        const args = { action: "read_file" as const, artifact_id: handle.id, version_id: handle.versionID }
        const first = await tool.execute(args, context(session.id))
        if (typeof first.metadata.nextOffset === "number") {
          expect(first.metadata.nextOffset).toBeGreaterThan(0)
          const second = await tool.execute({ ...args, offset: first.metadata.nextOffset }, context(session.id))
          expect(first.output.split("\n\n[More content:")[0] + second.output).toBe(content)
          expect(second.metadata.nextOffset).toBeUndefined()
        } else expect(first.output).toBe(content)
      },
    })
  },
)

test("artifact save_file promotes a workspace result into immutable versions", async () => {
  await using tmp = await tmpdir({ git: true })
  await Instance.provide({
    directory: tmp.path,
    fn: async () => {
      const session = await executionSession()
      const tool = await ArtifactTool.init()
      const workspace = await SessionFilesystem.workspace(session.id)
      const target = path.join(workspace, "results", "titanic-report.md")
      await Bun.write(target, "# Titanic analysis\n\nFirst verified result.\n")

      const first = await tool.execute(
        { action: "save_file", path: "results/titanic-report.md", summary: "Titanic analysis report" },
        context(session.id),
      )
      await Bun.write(target, "# Titanic analysis\n\nImproved verified result.\n")
      const second = await tool.execute(
        { action: "save_file", path: "results/titanic-report.md", summary: "Titanic analysis report" },
        context(session.id),
      )
      const firstSaved = first.metadata.savedArtifact as { id: string }

      expect(first.title).toBe("Saved Result: Titanic analysis report")
      expect(first.metadata.savedArtifact).toMatchObject({
        version: 1,
        title: "Titanic analysis report",
        kind: "report",
        path: "results/titanic-report.md",
        mimeType: "text/markdown",
        preview: { kind: "text", data: "# Titanic analysis\n\nFirst verified result.\n" },
        sha256: expect.stringMatching(/^[a-f0-9]{64}$/),
      })
      expect(second.metadata.savedArtifact).toMatchObject({
        id: firstSaved.id,
        version: 2,
      })
      expect(await ArtifactStore.list(Instance.project.id)).toHaveLength(1)
      const detail = await ArtifactStore.get(Instance.project.id, firstSaved.id)
      expect(detail).toMatchObject({ versionCount: 2 })
      const scope = { projectID: Instance.project.id, directory: Instance.directory }
      for (const version of detail!.versions) {
        expect(await Provenance.find(scope, ArtifactStore.reviewTargetID(version.id, version.sha256))).toMatchObject({
          kind: "artifact",
          meta: { artifactID: firstSaved.id, versionID: version.id, sessionID: session.id },
        })
      }
    },
  })
})

test("large artifact text returns metadata without repeatedly hashing or paging a dataset into context", async () => {
  await using tmp = await tmpdir({ git: true })
  await Instance.provide({
    directory: tmp.path,
    fn: async () => {
      const session = await executionSession()
      const tool = await ArtifactTool.init()
      const source = path.join(await SessionFilesystem.workspace(session.id), "large.txt")
      await Bun.write(source, new Uint8Array(8 * 1024 * 1024 + 1).fill(65))
      const saved = await tool.execute({ action: "save_file", path: source }, context(session.id))
      const handle = saved.metadata.savedArtifact as { id: string; versionID: string }
      const read = await tool.execute(
        { action: "read_file", artifact_id: handle.id, version_id: handle.versionID },
        context(session.id),
      )
      expect(read.metadata).toMatchObject({ readStatus: "metadata_only", size: 8 * 1024 * 1024 + 1 })
      expect(read.metadata.nextOffset).toBeUndefined()
      expect(read.output).toContain("has not verified or read the blob bytes")
      expect(read.output.length).toBeLessThan(500)
    },
  })
})

test("artifact save_file never persists a blank display title", async () => {
  await using tmp = await tmpdir({ git: true })
  await Instance.provide({
    directory: tmp.path,
    fn: async () => {
      const session = await executionSession()
      const tool = await ArtifactTool.init()
      const workspace = await SessionFilesystem.workspace(session.id)
      await Bun.write(path.join(workspace, "result.csv"), "metric,value\naccuracy,0.91\n")

      const saved = await tool.execute({ action: "save_file", path: "result.csv", summary: "   " }, context(session.id))

      expect(saved.title).toBe("Saved Result: result.csv")
      expect(saved.metadata.savedArtifact).toMatchObject({
        title: "result.csv",
        kind: "dataset",
        mimeType: "text/csv",
        preview: { kind: "text", data: "metric,value\naccuracy,0.91\n" },
      })
    },
  })
})

test("artifact save_file binds the immutable result to its exact producing execution", async () => {
  await using tmp = await tmpdir({ git: true })
  await Instance.provide({
    directory: tmp.path,
    fn: async () => {
      const session = await executionSession()
      const tool = await ArtifactTool.init()
      const workspace = await SessionFilesystem.workspace(session.id)
      await Bun.write(path.join(workspace, "result.csv"), "metric,value\naccuracy,0.91\n")
      const scope = { projectID: Instance.project.id, directory: Instance.directory }
      const run = await Provenance.recordOwned(scope, {
        id: "run_artifact_save_file",
        kind: "run",
        label: "Python execution",
        tool: "python",
        sessionID: session.id,
        status: "ok",
        inputs: { code: "write_result()" },
        provenance: ProvenanceEnvelope.create({
          kind: "kernel",
          projectID: Instance.project.id,
          sessionID: session.id,
          runID: "run_artifact_save_file",
          code: "write_result()",
          status: "succeeded",
          outputs: [],
          createdAt: Date.now(),
          startedAt: Date.now(),
          completedAt: Date.now(),
        }),
        meta: { stdout: "saved result.csv", stderr: "", effort: "normal" },
      } as Parameters<typeof Provenance.record>[0])

      const response = await tool.execute(
        { action: "save_file", path: "result.csv", provenance_id: run.id },
        context(session.id),
      )
      const saved = response.metadata.savedArtifact as { id: string; versionID: string }
      expect(response.metadata.savedArtifact).toMatchObject({ provenanceID: run.id })
      const detail = await ArtifactStore.get(Instance.project.id, saved.id)
      expect(detail?.execution).toMatchObject({
        command: "python",
        code: "write_result()",
        status: "succeeded",
        stdout: "saved result.csv",
        effort: "normal",
        source: run.id,
        captureQuality: "exact",
      })
      const graph = await Provenance.project(scope)
      const target = ArtifactStore.reviewTargetID(saved.versionID, detail!.current.sha256)
      expect(graph.edges).toContainEqual({ from: run.id, to: target, relation: "produced" })
    },
  })
})

test("artifact save_file accepts a project-owned manually recorded run from the same session", async () => {
  await using tmp = await tmpdir({ git: true })
  await Instance.provide({
    directory: tmp.path,
    fn: async () => {
      const session = await executionSession()
      const tool = await ArtifactTool.init()
      const workspace = await SessionFilesystem.workspace(session.id)
      await Bun.write(path.join(workspace, "review.pdf"), "%PDF-1.5\nmanual result\n")
      const scope = { projectID: Instance.project.id, directory: Instance.directory }
      const run = await Provenance.recordOwned(scope, {
        kind: "run",
        label: "Compile review",
        tool: "tectonic, pdfinfo",
        meta: {
          sessionID: session.id,
          projectID: Instance.project.id,
          stdout: "review.pdf validated",
        },
      } as Parameters<typeof Provenance.record>[0])

      const response = await tool.execute(
        { action: "save_file", path: "review.pdf", provenance_id: run.id },
        context(session.id),
      )
      const saved = response.metadata.savedArtifact as { id: string; versionID: string }
      const detail = await ArtifactStore.get(Instance.project.id, saved.id)
      expect(detail?.execution).toMatchObject({
        command: "tectonic, pdfinfo",
        status: "unknown",
        stdout: "review.pdf validated",
        source: run.id,
        captureQuality: "declared",
      })
      expect((await Provenance.project(scope)).edges).toContainEqual({
        from: run.id,
        to: ArtifactStore.reviewTargetID(saved.versionID, detail!.current.sha256),
        relation: "produced",
      })
    },
  })
})

test("artifact save_file takes a study run of this session as provenance, and refuses another session's", async () => {
  await using tmp = await tmpdir({ git: true })
  await Instance.provide({
    directory: tmp.path,
    fn: async () => {
      const session = await executionSession()
      const tool = await ArtifactTool.init()
      const workspace = await SessionFilesystem.workspace(session.id)
      await Bun.write(path.join(workspace, "metrics.json"), '{"cv_roc_auc": 0.759}\n')
      const study = await Experiments.createStudy({
        sessionID: session.id,
        name: "Churn climb",
        purpose: "p",
        metric: "cv_roc_auc",
        direction: "maximize",
        root: path.join(tmp.path, "study"),
        budget: { maxRuns: 3 },
      })
      const run = await Experiments.createRun({
        name: "No-charges weaker shrinkage",
        source: "job",
        studyID: study.id,
        sessionID: session.id,
        jobID: "1f079335-e9b",
      })
      await Experiments.finishRun(run.id, "finished")

      // The run the model names is the run in its study store; the Result's
      // lineage now points at it.
      const response = await tool.execute(
        { action: "save_file", path: "metrics.json", provenance_id: run.id },
        context(session.id),
      )
      expect(response.title).toStartWith("Saved Result")
      const saved = response.metadata.savedArtifact as { id: string; versionID: string; provenanceID?: string }
      expect(saved.provenanceID).toBe(run.id)
      const scope = { projectID: Instance.project.id, directory: Instance.directory }
      const node = await Provenance.find(scope, run.id)
      expect(node).toMatchObject({ kind: "run", tool: "study", sessionID: session.id })
      const detail = await ArtifactStore.get(Instance.project.id, saved.id)
      expect((await Provenance.project(scope)).edges).toContainEqual({
        from: run.id,
        to: ArtifactStore.reviewTargetID(saved.versionID, detail!.current.sha256),
        relation: "produced",
      })

      // A run another session owns is not this session's provenance.
      const other = await Experiments.createStudy({
        sessionID: "ses_someone_else",
        name: "Other",
        purpose: "p",
        metric: "m",
        direction: "maximize",
        root: path.join(tmp.path, "other"),
        budget: { maxRuns: 1 },
      })
      const foreign = await Experiments.createRun({ name: "theirs", source: "job", studyID: other.id })
      const refused = await tool.execute(
        { action: "save_file", path: "metrics.json", provenance_id: foreign.id },
        context(session.id),
      )
      expect(refused.title).toBe("Invalid provenance")
    },
  })
})

test("artifact save_file reads a report the agent wrote under Project files from an isolated session", async () => {
  const project = await ManagedProject.create("Artifact from project files")
  await Instance.provide({
    directory: project.worktree,
    projectID: project.id,
    fn: async () => {
      const session = await Session.create({})
      try {
        // An isolated session has no grant for the project directory; the
        // read tool still treats it as internal, so saving from it must too.
        const workspace = await SessionFilesystem.workspace(session.id)
        expect(workspace).not.toBe(project.worktree)
        const report = path.join(project.worktree, "report", "main.pdf")
        await Bun.write(report, "%PDF-1.5\nproject report\n")
        const tool = await ArtifactTool.init()
        const saved = await tool.execute(
          { action: "save_file", path: report, summary: "Churn EDA report" },
          context(session.id),
        )
        expect(saved.title).toBe("Saved Result: Churn EDA report")
        expect(saved.metadata.savedArtifact).toMatchObject({ version: 1, kind: "report" })
      } finally {
        await Session.remove(session.id)
      }
    },
  })
})
