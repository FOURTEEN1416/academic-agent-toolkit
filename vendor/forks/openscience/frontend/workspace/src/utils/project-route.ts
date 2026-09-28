import { checksum } from "@synsci/util/encode"
import { decode64 } from "./base64"

export type ProjectRouteRecord = {
  id: string
  worktree: string
  sandboxes?: string[]
}

export type ProjectRoute = {
  project: ProjectRouteRecord
  projectID: string
  directory: string
  segment: string
  legacy: boolean
}

const WORKTREE_SEPARATOR = "~"

function workspace(project: ProjectRouteRecord, directory: string) {
  if (directory === project.worktree) return project.id
  return `${project.id}${WORKTREE_SEPARATOR}${checksum(directory) ?? "worktree"}`
}

export function projectSegment(project: ProjectRouteRecord, directory = project.worktree) {
  return workspace(project, directory)
}

export function projectPathname(segment: string, sessionID?: string) {
  const session = sessionID ? `/${encodeURIComponent(sessionID)}` : ""
  return `/${encodeURIComponent(segment)}/session${session}`
}

export function projectHref(project: ProjectRouteRecord, directory = project.worktree, sessionID?: string) {
  return projectPathname(projectSegment(project, directory), sessionID)
}

export function projectForDirectory(projects: readonly ProjectRouteRecord[], directory: string) {
  return projects.find((project) => project.worktree === directory || (project.sandboxes ?? []).includes(directory))
}

export function projectScope(projects: readonly ProjectRouteRecord[], directory: string) {
  const project = projectForDirectory(projects, directory)
  if (!project) return directory
  return projectSegment(project, directory)
}

export function looksLikeProjectSegment(segment: string) {
  const projectID = segment.split(WORKTREE_SEPARATOR, 1)[0]
  return (
    projectID === "global" ||
    projectID.startsWith("prj_") ||
    projectID.startsWith("ng-") ||
    /^[a-f0-9]{40}$/i.test(projectID)
  )
}

export function projectAliasID(segment: string | undefined) {
  if (!segment || !looksLikeProjectSegment(segment)) return
  return segment.split(WORKTREE_SEPARATOR, 1)[0]
}

export function resolveProjectAlias(
  segment: string | undefined,
  project: ProjectRouteRecord | undefined,
): ProjectRoute | undefined {
  const projectID = projectAliasID(segment)
  if (!segment || !projectID || !project) return

  const separator = segment.indexOf(WORKTREE_SEPARATOR)
  const token = separator === -1 ? undefined : segment.slice(separator + 1)
  const directories = [project.worktree, ...(project.sandboxes ?? [])]
  const alias = { ...project, id: projectID }
  const directory = token
    ? directories.find((candidate) => projectSegment(alias, candidate) === segment)
    : project.worktree
  if (!directory) return

  const canonical = projectSegment(project, directory)
  return {
    project,
    projectID: project.id,
    directory,
    segment: canonical,
    legacy: canonical !== segment,
  }
}

export function resolveProjectRoute(
  segment: string | undefined,
  projects: readonly ProjectRouteRecord[],
): ProjectRoute | undefined {
  if (!segment) return

  const separator = segment.indexOf(WORKTREE_SEPARATOR)
  const projectID = separator === -1 ? segment : segment.slice(0, separator)
  const token = separator === -1 ? undefined : segment.slice(separator + 1)
  const direct = projects.find((project) => project.id === projectID)

  if (direct) {
    const directories = [direct.worktree, ...(direct.sandboxes ?? [])]
    const directory = token
      ? directories.find((candidate) => projectSegment(direct, candidate) === segment)
      : direct.worktree
    if (!directory) return
    return {
      project: direct,
      projectID: direct.id,
      directory,
      segment,
      legacy: false,
    }
  }

  if (looksLikeProjectSegment(segment)) return

  const directory = decode64(segment)
  if (!directory) return
  const project = projectForDirectory(projects, directory)
  if (!project) return
  return {
    project,
    projectID: project.id,
    directory,
    segment: projectSegment(project, directory),
    legacy: true,
  }
}
