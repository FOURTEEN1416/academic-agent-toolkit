import { afterAll, beforeAll, beforeEach, describe, expect, test } from "bun:test"
import fs from "node:fs/promises"
import path from "node:path"
import { OpenScience } from "../../src/openscience"
import { Project } from "../../src/project/project"
import { ProvenanceEnvelope } from "../../src/science/provenance/envelope"
import { Provenance, ProvenanceCorruptError } from "../../src/science/provenance/store"
import { Storage } from "../../src/storage/storage"
import { tmpdir } from "../fixture/fixture"

const filepath = Provenance.path_
const folder = path.dirname(filepath)
const name = path.basename(filepath)
const corrupt = `${filepath}.corrupt-${process.pid}`
let original: Uint8Array | undefined

async function clean() {
  await fs.mkdir(folder, { recursive: true })
  const files = await fs.readdir(folder)
  await Promise.all(
    files
      .filter(
        (file) =>
          file === name ||
          file.startsWith(`${name}.corrupt-${process.pid}`) ||
          (file.startsWith(`${name}.`) && file.endsWith(".tmp")),
      )
      .map((file) => fs.rm(path.join(folder, file), { force: true })),
  )
}

beforeAll(async () => {
  original = await Bun.file(filepath)
    .bytes()
    .catch(() => undefined)
})

beforeEach(clean)

afterAll(async () => {
  await clean()
  if (original) await Bun.write(filepath, original, { mode: 0o600 })
})

describe("Provenance persistence", () => {
  test("redacts known and patterned secrets before returning or writing a node", async () => {
    const known = `registered-provenance-${crypto.randomUUID()}`
    const token = `sk-provenance-${crypto.randomUUID().replaceAll("-", "")}`
    const bearer = `bearer-${crypto.randomUUID()}`
    const named = `named-${crypto.randomUUID()}`
    OpenScience.registerSecretValues([known])

    const node = await Provenance.record({
      kind: "run",
      label: `secret check ${known}`,
      tool: "notebook",
      inputs: {
        code: `API_KEY='${known}'\nclient = '${token}'`,
        args: ["--authorization", `Bearer ${bearer}`],
        env: { CUSTOM_TOKEN: named },
      },
      status: "error",
      meta: {
        stdout: known,
        stderr: token,
        result: `Authorization: Bearer ${bearer}`,
        error: `password=${named}`,
      },
    } as Parameters<typeof Provenance.record>[0])

    const returned = JSON.stringify(node)
    const persisted = await Bun.file(filepath).text()
    for (const secret of [known, token, bearer, named]) {
      expect(returned).not.toContain(secret)
      expect(persisted).not.toContain(secret)
    }
    expect(returned).toContain("[REDACTED]")
    expect(persisted).toContain("[REDACTED]")
  })

  test("reports corrupt state and refuses to overwrite it during a mutation", async () => {
    const bytes = '{"version":1,"nodes":{"old":'
    await fs.writeFile(filepath, bytes, { mode: 0o600 })

    await expect(Provenance.list()).rejects.toBeInstanceOf(ProvenanceCorruptError)
    expect(await Bun.file(filepath).text()).toBe(bytes)
    expect(await Bun.file(corrupt).exists()).toBe(false)

    await expect(
      Provenance.record({
        kind: "source",
        label: "must not replace history",
      }),
    ).rejects.toThrow(/backed up/)
    expect(await Bun.file(filepath).text()).toBe(bytes)
    expect(await Bun.file(corrupt).text()).toBe(bytes)
  })

  test("ignores an interrupted sibling temp file and atomically retains prior nodes", async () => {
    const first = await Provenance.record({
      kind: "source",
      label: "first durable node",
    })
    const partial = `${filepath}.${process.pid}.interrupted.tmp`
    const fragment = '{"version":1,"nodes":'
    await fs.writeFile(partial, fragment, { mode: 0o600 })

    const second = await Provenance.record({
      kind: "source",
      label: "second durable node",
    })
    const graph = JSON.parse(await Bun.file(filepath).text()) as {
      nodes: Record<string, unknown>
    }

    expect(Object.keys(graph.nodes).toSorted()).toEqual([first.id, second.id].toSorted())
    expect(await Bun.file(partial).text()).toBe(fragment)
    const temps = (await fs.readdir(folder)).filter(
      (file) => file.startsWith(`${name}.${process.pid}.`) && file.endsWith(".tmp"),
    )
    expect(temps).toEqual([path.basename(partial)])
  })

  test("uses project IDs across linked roots, isolated from other IDs and root relocation", async () => {
    const main = path.join(folder, "ownership-main")
    const sandbox = path.join(folder, "ownership-sandbox")
    const relocated = path.join(folder, "ownership-relocated")
    const first = await Provenance.record({
      id: "owned-main",
      kind: "source",
      label: "Main worktree source",
      meta: { projectID: "project-a", directory: main },
    })
    const second = await Provenance.record({
      id: "owned-sandbox",
      kind: "claim",
      label: "Linked worktree claim",
      meta: { projectID: "project-a", directory: sandbox },
    })
    const foreign = await Provenance.record({
      id: "owned-foreign",
      kind: "source",
      label: "Another project in the same root",
      meta: { projectID: "project-b", directory: main },
    })

    for (const directory of [main, sandbox, relocated]) {
      const graph = await Provenance.project({ projectID: "project-a", directory })
      expect(graph.nodes.map((node) => node.id).toSorted()).toEqual([first.id, second.id].toSorted())
      expect(graph.nodes.some((node) => node.id === foreign.id)).toBe(false)
    }
    expect(
      (await Provenance.project({ projectID: "project-b", directory: main })).nodes.map((node) => node.id),
    ).toEqual([foreign.id])
  })

  test("rejects explicit foreign owners across historical transitive edges", async () => {
    const directory = path.join(folder, "transitive-root")
    const recordedAt = "2026-01-01T00:00:00.000Z"
    await fs.writeFile(
      filepath,
      JSON.stringify({
        version: 1,
        nodes: {
          local: {
            id: "local",
            kind: "source",
            label: "Local source",
            recordedAt,
            meta: { projectID: "project-a", directory },
          },
          foreign: {
            id: "foreign",
            kind: "claim",
            label: "Foreign bridge",
            recordedAt,
            meta: { projectID: "project-b" },
          },
          unowned: {
            id: "unowned",
            kind: "claim",
            label: "Unowned transitive leaf",
            recordedAt,
          },
        },
        edges: [
          { from: "local", to: "foreign", relation: "supports" },
          { from: "foreign", to: "unowned", relation: "supports" },
        ],
      }),
      { mode: 0o600 },
    )

    const graph = await Provenance.query({ projectID: "project-a", directory }, "local")
    expect(graph.nodes.map((node) => node.id)).toEqual(["local"])
    expect(graph.edges).toEqual([])
    await expect(Provenance.link({ from: "local", to: "foreign", relation: "refutes" })).rejects.toThrow(
      "different projects",
    )
  })

  test("adopts a legacy directory node once without allowing owner theft or owner removal", async () => {
    const directory = path.join(folder, "legacy-root")
    const relocated = path.join(folder, "legacy-relocated")
    const legacy = await Provenance.record({
      id: "legacy-directory-node",
      kind: "source",
      label: "Legacy source",
      meta: { directory },
    })

    expect((await Provenance.project({ projectID: "project-a", directory })).nodes.map((node) => node.id)).toEqual([
      legacy.id,
    ])
    const owner = await Provenance.record({
      id: "legacy-owner",
      kind: "claim",
      label: "Owned claim",
      meta: { directory, projectID: "project-a" },
    })
    await Provenance.linkOwned(
      { projectID: "project-a", directory },
      { from: owner.id, to: legacy.id, relation: "supports" },
    )
    const adopted = await Provenance.get(legacy.id)
    expect(adopted?.meta).toMatchObject({ directory, projectID: "project-a" })
    expect(
      (await Provenance.project({ projectID: "project-a", directory: relocated })).nodes.map((node) => node.id),
    ).toEqual([legacy.id, owner.id])

    await expect(
      Provenance.record({
        id: legacy.id,
        kind: "source",
        label: legacy.label,
        meta: { directory, projectID: "project-b" },
      }),
    ).rejects.toThrow("belongs to another project")
    const preserved = await Provenance.record({
      id: legacy.id,
      kind: "source",
      label: legacy.label,
      meta: { directory },
    })
    expect(preserved.meta?.projectID).toBe("project-a")
  })

  test("adopts legacy project ownership without losing provenance identity or edges", async () => {
    await using tmp = await tmpdir()
    const legacy = new Bun.CryptoHasher("sha256").update(tmp.path).digest("hex").slice(0, 40)
    await Storage.write(["project", legacy], {
      id: legacy,
      worktree: tmp.path,
      sandboxes: [],
      time: { created: 1, updated: 1 },
    })
    const run = await Provenance.record({
      id: "legacy-owned-run",
      kind: "run",
      label: "Legacy kernel run",
      tool: "notebook",
      meta: {
        projectID: legacy,
        directory: tmp.path,
      },
      provenance: ProvenanceEnvelope.create({
        kind: "kernel",
        projectID: legacy,
        sessionID: "ses_legacy",
        runID: "run_legacy",
        cwd: tmp.path,
        status: "succeeded",
      }),
    } as Parameters<typeof Provenance.record>[0])
    const artifact = await Provenance.record({
      id: "legacy-owned-artifact",
      kind: "artifact",
      label: "Legacy result",
      artifactType: "dataset",
      path: path.join(tmp.path, "results.csv"),
      meta: {
        projectID: legacy,
        directory: tmp.path,
      },
    } as Parameters<typeof Provenance.record>[0])
    await Provenance.link({ from: run.id, to: artifact.id, relation: "produced" })
    const project = (await Project.fromDirectory(tmp.path)).project

    const graph = await Provenance.project({
      projectID: project.id,
      directory: tmp.path,
    })
    const migrated = await Provenance.get(run.id)

    expect(project.id).toStartWith("prj_")
    expect(graph.nodes.map((node) => node.id).toSorted()).toEqual([artifact.id, run.id].toSorted())
    expect(graph.edges).toEqual([{ from: run.id, to: artifact.id, relation: "produced" }])
    expect(migrated).toMatchObject({
      id: run.id,
      recordedAt: run.recordedAt,
      meta: {
        projectID: project.id,
        directory: tmp.path,
      },
      provenance: {
        identity: {
          project_id: {
            status: "available",
            value: project.id,
          },
        },
      },
    })
    expect((await Provenance.get(artifact.id))?.meta?.projectID).toBe(project.id)
  })
})
