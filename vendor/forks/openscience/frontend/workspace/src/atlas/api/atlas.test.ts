import { describe, expect, test } from "bun:test"
import type { ProjectRequest } from "@/utils/openscience-fetch"
import { createAtlasAPI } from "./atlas"

describe("Atlas project request shapes", () => {
  test("keeps resolve and init on the bound project root", async () => {
    const calls: Array<{ path: string; init?: RequestInit }> = []
    const request = Object.assign(
      async (path: string, init?: RequestInit) => {
        calls.push({ path, init })
        return Response.json({ project_id: "atlas_project" })
      },
      { url: (path: string) => path },
    ) as ProjectRequest
    const atlas = createAtlasAPI(request)

    await atlas.resolveProject()
    await atlas.initProject()

    expect(calls.map((call) => call.path)).toEqual(["/api/atlas/project", "/api/atlas/project/init"])
    expect(calls.every((call) => !call.path.includes("directory="))).toBeTrue()
  })

  test("passes the opaque project ID when staging a node", async () => {
    const bodies: unknown[] = []
    const request = Object.assign(
      async (_path: string, init?: RequestInit) => {
        bodies.push(JSON.parse(String(init?.body)))
        return Response.json({})
      },
      { url: (path: string) => path },
    ) as ProjectRequest
    const atlas = createAtlasAPI(request)

    await atlas.createNode({
      title: "Compare baselines",
      parentID: "node_parent",
      projectID: "prj_alpha",
    })

    expect(bodies).toEqual([
      {
        title: "Compare baselines",
        projectID: "prj_alpha",
        parent_id: "node_parent",
      },
    ])
  })
})
