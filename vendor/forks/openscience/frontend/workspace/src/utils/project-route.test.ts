import { describe, expect, test } from "bun:test"
import { base64Encode } from "@synsci/util/encode"
import {
  looksLikeProjectSegment,
  projectAliasID,
  projectHref,
  projectScope,
  resolveProjectAlias,
  resolveProjectRoute,
} from "./project-route"

const sandbox = "/Users/aayam/research/alpha-feature"
const alpha = {
  id: "prj_alpha",
  worktree: "/Users/aayam/research/alpha",
  sandboxes: [sandbox],
}
const beta = {
  id: "prj_beta",
  worktree: "/Users/aayam/research/beta",
}
const projects = [alpha, beta]

describe("project routes", () => {
  test("uses opaque project IDs for main-worktree URLs", () => {
    expect(projectHref(alpha, alpha.worktree, "session-1")).toBe("/prj_alpha/session/session-1")
    expect(projectHref(alpha)).not.toContain("Users")
  })

  test("keeps linked worktrees addressable without serializing their path", () => {
    const href = projectHref(alpha, sandbox, "session-2")
    const segment = href.split("/")[1]
    const route = resolveProjectRoute(segment, projects)

    expect(href).toStartWith("/prj_alpha~")
    expect(href).not.toContain("alpha-feature")
    expect(route?.directory).toBe(sandbox)
    expect(route?.projectID).toBe("prj_alpha")
  })

  test("parses legacy base64-directory links and returns their canonical replacement", () => {
    const segment = base64Encode(sandbox)
    const route = resolveProjectRoute(segment, projects)

    expect(route?.legacy).toBe(true)
    expect(route?.directory).toBe(sandbox)
    expect(route?.segment).toStartWith("prj_alpha~")
  })

  test("scopes caches by project identity without leaking between projects", () => {
    expect(projectScope(projects, alpha.worktree)).toBe("prj_alpha")
    expect(projectScope(projects, beta.worktree)).toBe("prj_beta")
    expect(projectScope(projects, alpha.worktree)).not.toBe(projectScope(projects, beta.worktree))
  })

  test("does not reinterpret an unknown opaque project ID as base64", () => {
    expect(looksLikeProjectSegment("prj_missing")).toBe(true)
    expect(resolveProjectRoute("prj_missing", projects)).toBeUndefined()
  })

  test("replaces a removed legacy alias with its canonical opaque route", () => {
    const route = resolveProjectAlias("ng-removed-project", alpha)
    const hash = resolveProjectAlias("a".repeat(40), alpha)

    expect(projectAliasID("ng-removed-project")).toBe("ng-removed-project")
    expect(route?.legacy).toBe(true)
    expect(route?.directory).toBe(alpha.worktree)
    expect(route?.projectID).toBe("prj_alpha")
    expect(route?.segment).toBe("prj_alpha")
    expect(hash?.projectID).toBe("prj_alpha")
    expect(hash?.segment).toBe("prj_alpha")
  })

  test("leaves an unknown legacy alias unresolved after lookup", () => {
    expect(resolveProjectAlias("ng-missing-project", undefined)).toBeUndefined()
    expect(resolveProjectRoute("ng-missing-project", projects)).toBeUndefined()
  })
})
