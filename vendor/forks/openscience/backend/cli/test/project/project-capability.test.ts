import { describe, expect, test } from "bun:test"
import fs from "fs/promises"
import path from "path"
import { Project } from "../../src/project/project"
import { Storage } from "../../src/storage/storage"
import { tmpdir } from "../fixture/fixture"
import { Instance } from "../../src/project/instance"
import { Session } from "../../src/session"
import { Server } from "../../src/server/server"
import { Log } from "../../src/util/log"

Log.init({ print: false })

describe("project capability resolution", () => {
  test("resolves a persisted opaque id without a caller directory", async () => {
    await using tmp = await tmpdir()
    const created = await Project.fromDirectory(tmp.path)

    expect(created.project.id).toStartWith("prj_")

    const selected = await Project.resolve(created.project.id)
    expect(selected.project.id).toBe(created.project.id)
    expect(selected.directory).toBe(tmp.path)
  })

  test("canonicalizes a symlink alias within the selected project", async () => {
    await using tmp = await tmpdir()
    const created = await Project.fromDirectory(tmp.path)
    const link = path.join(path.dirname(tmp.path), `${path.basename(tmp.path)}-alias`)
    await fs.symlink(tmp.path, link)

    const selected = await Project.resolve(created.project.id, link)
    expect(selected.directory).toBe(tmp.path)

    await fs.rm(link, { force: true })
  })

  test("rejects a directory from another project", async () => {
    await using first = await tmpdir()
    await using second = await tmpdir()
    const project = await Project.fromDirectory(first.path)
    await Project.fromDirectory(second.path)

    await expect(Project.resolve(project.project.id, second.path)).rejects.toBeInstanceOf(Project.MismatchError)

    const response = await Server.internalFetch()(
      `http://openscience.internal/project/current?directory=${encodeURIComponent(second.path)}`,
      {
        headers: {
          "x-openscience-project": project.project.id,
        },
      },
    )
    expect(response.status).toBe(409)
    expect(await response.json()).toMatchObject({
      name: "ProjectMismatchError",
      data: {
        projectID: project.project.id,
      },
    })
  })

  test("distinguishes unknown and stale selectors", async () => {
    const unknownID = `prj_unknown_${crypto.randomUUID()}`
    await expect(Project.resolve(unknownID)).rejects.toBeInstanceOf(Project.UnknownError)

    const unknown = await Server.internalFetch()("http://openscience.internal/project/current", {
      headers: {
        "x-openscience-project": unknownID,
      },
    })
    expect(unknown.status).toBe(404)
    expect(await unknown.json()).toEqual({
      name: "ProjectUnknownError",
      data: {
        projectID: unknownID,
      },
    })

    await using tmp = await tmpdir()
    const created = await Project.fromDirectory(tmp.path)
    await fs.rm(tmp.path, { recursive: true, force: true })

    await expect(Project.resolve(created.project.id)).rejects.toBeInstanceOf(Project.StaleError)
    const stale = await Server.internalFetch()("http://openscience.internal/project/current", {
      headers: {
        "x-openscience-project": created.project.id,
      },
    })
    expect(stale.status).toBe(410)
    expect(await stale.json()).toMatchObject({
      name: "ProjectStaleError",
      data: {
        projectID: created.project.id,
        reason: "missing_directory",
      },
    })
  })

  test("keeps a removed legacy project id as an alias after migration", async () => {
    await using tmp = await tmpdir()
    const legacyID = `ng-capability-${crypto.randomUUID()}`
    await Storage.write(["project", legacyID], {
      id: legacyID,
      worktree: tmp.path,
      sandboxes: [],
      time: {
        created: 1,
        updated: 1,
      },
    })

    const created = await Project.fromDirectory(tmp.path)
    const selected = await Project.resolve(legacyID)

    expect(created.project.id).not.toBe(legacyID)
    expect(selected.project.id).toBe(created.project.id)
    expect(selected.alias).toBe(legacyID)
  })

  test("keeps session reads isolated by selected project id", async () => {
    await using first = await tmpdir()
    await using second = await tmpdir()
    const source = await Instance.provide({
      directory: first.path,
      fn: async () => ({
        projectID: Instance.project.id,
        session: await Session.create({}),
      }),
    })
    const target = await Instance.provide({
      directory: second.path,
      fn: async () => Instance.project.id,
    })

    const fetch = Server.internalFetch()
    const allowed = await fetch(`http://openscience.internal/session/${source.session.id}`, {
      headers: {
        "x-openscience-project": source.projectID,
      },
    })
    const denied = await fetch(`http://openscience.internal/session/${source.session.id}`, {
      headers: {
        "x-openscience-project": target,
      },
    })

    expect(allowed.status).toBe(200)
    expect(denied.status).toBe(404)
  })
})
