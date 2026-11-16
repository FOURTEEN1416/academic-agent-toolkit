import path from "node:path"
import { Instance } from "@/project/instance"
import { SessionFilesystem } from "@/session/filesystem"
import { Filesystem } from "@/util/filesystem"

/**
 * The path a tool row shows for a file. Project files read relative to the
 * project; a file in the session's scratch reads as `scratch/…` and a skill's
 * asset as `skill:<name>/…`, instead of the `../../workspaces/prj_…/ses_…/…`
 * and `../../.cache/openscience/bundled-skills/<hash>/…` that a plain relative
 * path produced. Anything else (a connected folder) shows its absolute path.
 */
export async function displayPath(filepath: string, sessionID?: string): Promise<string> {
  const worktree = Instance.worktree
  if (Filesystem.contains(worktree, filepath)) return path.relative(worktree, filepath) || "."
  const workspace = sessionID?.startsWith("ses_")
    ? await SessionFilesystem.workspace(sessionID).catch(() => undefined)
    : undefined
  if (workspace && Filesystem.contains(workspace, filepath)) {
    const relative = path.relative(workspace, filepath)
    return relative ? `scratch/${relative}` : "scratch"
  }
  const skill =
    filepath.match(/[\\/]bundled-skills[\\/][0-9a-f]+[\\/](.+)$/) ??
    filepath.match(/[\\/]skills[\\/](?:core|bundled|community|local)[\\/](.+)$/)
  if (skill) return `skill:${skill[1].split(path.sep).join("/")}`
  return filepath
}
