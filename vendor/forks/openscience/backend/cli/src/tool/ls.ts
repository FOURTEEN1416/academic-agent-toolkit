import z from "zod"
import { Tool } from "./tool"
import { displayPath } from "./display-path"
import * as path from "path"
import DESCRIPTION from "./ls.txt"
import { Ripgrep } from "../file/ripgrep"
import { assertExternalDirectory, isAuthorizedPath, sessionToolDirectory } from "./external-directory"

const IGNORE_PATTERNS = [
  "node_modules/",
  "__pycache__/",
  ".git/",
  "dist/",
  "build/",
  "target/",
  "vendor/",
  "bin/",
  "obj/",
  ".idea/",
  ".vscode/",
  ".zig-cache/",
  "zig-out",
  ".coverage",
  "coverage/",
  "vendor/",
  "tmp/",
  "temp/",
  ".cache/",
  "cache/",
  "logs/",
  ".venv/",
  "venv/",
  "env/",
]

const LIMIT = 100

/** The tree is text for the model, so it is cut on both separators and always
 *  rendered with `/`. ripgrep prints the host separator, and a POSIX-only split
 *  put every nested Windows file under one key that `path.dirname` could never
 *  reach, so `list` reported only the root-level files. */
export function renderTree(files: string[]) {
  const parent = (dir: string) => {
    const at = dir.lastIndexOf("/")
    return at < 0 ? "" : dir.slice(0, at)
  }
  const base = (dir: string) => dir.slice(parent(dir).length === 0 ? 0 : parent(dir).length + 1)
  const dirs = new Set<string>([""])
  const filesByDir = new Map<string, string[]>()
  for (const file of files) {
    const parts = file.split(/[/\\]/)
    const name = parts.pop()
    if (name === undefined) continue
    let dir = ""
    for (const part of parts) {
      dir = dir === "" ? part : `${dir}/${part}`
      dirs.add(dir)
    }
    if (!filesByDir.has(dir)) filesByDir.set(dir, [])
    filesByDir.get(dir)!.push(name)
  }
  const render = (dir: string, depth: number): string => {
    let output = dir === "" ? "" : `${"  ".repeat(depth)}${base(dir)}/\n`
    const children = Array.from(dirs)
      .filter((child) => child !== dir && parent(child) === dir)
      .sort()
    for (const child of children) output += render(child, depth + 1)
    for (const name of (filesByDir.get(dir) ?? []).sort()) output += `${"  ".repeat(depth + 1)}${name}\n`
    return output
  }
  return render("", 0)
}

export const ListTool = Tool.define("list", {
  description: DESCRIPTION,
  parameters: z.object({
    path: z.string().describe("The absolute path to the directory to list (must be absolute, not relative)").optional(),
    ignore: z.array(z.string()).describe("List of glob patterns to ignore").optional(),
  }),
  async execute(params, ctx) {
    let searchPath = path.resolve(await sessionToolDirectory(ctx), params.path || ".")
    const retained = isAuthorizedPath(ctx.extra?.["fileAuthorization"]) ? ctx.extra?.["fileAuthorization"] : undefined
    if (retained && retained.path !== searchPath) {
      throw new Error("Retained directory authorization does not match the requested path")
    }
    using owned = retained ? undefined : await assertExternalDirectory(ctx, searchPath, { kind: "directory" })
    const authorized = retained ?? owned
    searchPath = authorized?.path ?? searchPath

    if (!retained) {
      await ctx.ask({
        permission: "list",
        patterns: [searchPath],
        always: ["*"],
        metadata: {
          path: searchPath,
        },
      })
    }

    searchPath = (await authorized?.revalidate()) ?? searchPath

    const ignoreGlobs = IGNORE_PATTERNS.map((p) => `!${p}*`).concat(params.ignore?.map((p) => `!${p}`) || [])
    const files = []
    for await (const file of Ripgrep.files({ cwd: searchPath, glob: ignoreGlobs, signal: ctx.abort })) {
      files.push(file)
      if (files.length >= LIMIT) break
    }

    const output = `${searchPath}/\n` + renderTree(files)

    return {
      title: await displayPath(searchPath, ctx.sessionID),
      metadata: {
        count: files.length,
        truncated: files.length >= LIMIT,
      },
      output,
    }
  },
})
