import fs from "node:fs/promises"
import path from "node:path"
import { Filesystem } from "@/util/filesystem"

/** Bounded metadata observations, not process-exclusive write attribution.
 * Concurrent commands can change the same project. Never infer paths from
 * shell text or Git, read file contents, or report removed/indirect entries. */
export namespace FileOutputReceipts {
  export type File = {
    path: string
    name: string
    size: number
    modified: number
    change: "created" | "modified"
  }
  type Stamp = Omit<File, "change"> & { inode: number; changed: number }
  export type Observation = {
    roots: string[]
    complete: string[]
    skipped: string[]
    files: Map<string, Stamp>
    truncated: boolean
  }
  const excluded = new Set(["node_modules", "vendor", "dist", "build", "target", "__pycache__", "site-packages"])
  const defaults = { entries: 2048, depth: 12, milliseconds: 150, receipts: 128 }

  function roots(values: string[]) {
    return [...new Set(values.map((value) => path.resolve(value)))]
      .toSorted((a, b) => a.length - b.length || a.localeCompare(b))
      .filter((value, index, all) => !all.slice(0, index).some((parent) => Filesystem.contains(parent, value)))
  }

  export async function observe(input: {
    roots: string[]
    unreadable?: string[]
    limits?: Partial<typeof defaults>
  }): Promise<Observation> {
    const limits = { ...defaults, ...input.limits }
    const selected = roots(input.roots)
    const result: Observation = {
      roots: selected.slice(0, 16),
      complete: [],
      skipped: [],
      files: new Map(),
      truncated: selected.length > 16,
    }
    const started = performance.now()
    let entries = 0
    const exhausted = () => entries >= limits.entries || performance.now() - started >= limits.milliseconds
    const privatePath = (target: string) => input.unreadable?.some((root) => Filesystem.contains(root, target))
    const walk = async (directory: string, depth: number, incomplete: () => void): Promise<void> => {
      if (privatePath(directory)) {
        result.skipped.push(directory)
        return
      }
      if (exhausted() || depth > limits.depth) {
        incomplete()
        return
      }
      const canonical = await fs.realpath(directory).catch(() => undefined)
      if (canonical !== directory) {
        incomplete()
        return
      }
      // Venv names are user-chosen; recognize the layout without walking its
      // potentially enormous dependency tree.
      if (await Bun.file(path.join(directory, "pyvenv.cfg")).exists()) {
        result.skipped.push(directory)
        return
      }
      const handle = await fs.opendir(directory).catch(() => undefined)
      if (!handle) {
        incomplete()
        return
      }
      for await (const entry of handle) {
        if (exhausted()) {
          incomplete()
          return
        }
        entries++
        const full = path.join(directory, entry.name)
        if (entry.name.startsWith(".") || excluded.has(entry.name) || privatePath(full) || entry.isSymbolicLink()) {
          result.skipped.push(full)
          continue
        }
        if (entry.isDirectory()) {
          await walk(full, depth + 1, incomplete)
          continue
        }
        if (!entry.isFile()) {
          result.skipped.push(full)
          continue
        }
        const stat = await fs.lstat(full).catch(() => undefined)
        if (!stat?.isFile() || stat.isSymbolicLink()) {
          incomplete()
          continue
        }
        result.files.set(full, {
          path: full,
          name: entry.name,
          size: stat.size,
          modified: stat.mtimeMs,
          changed: stat.ctimeMs,
          inode: stat.ino,
        })
      }
    }
    for (const root of result.roots) {
      let complete = true
      await walk(root, 0, () => {
        complete = false
        result.truncated = true
      })
      if (complete) result.complete.push(root)
    }
    return result
  }

  export async function finish(before: Observation, input: Parameters<typeof observe>[0]) {
    const current = await observe({
      ...input,
      roots: input.roots.filter((root) => before.roots.some((allowed) => Filesystem.contains(allowed, root))),
    })
    const limit = input.limits?.receipts ?? defaults.receipts
    const files: File[] = []
    let truncated = before.truncated || current.truncated
    for (const [full, stamp] of current.files) {
      const prior = before.files.get(full)
      // Coverage belongs to each root. A large project must not invalidate a
      // fully observed scratch directory, while unseen files in that project
      // still cannot be called new after an incomplete baseline.
      if (
        !prior &&
        (!before.complete.some((root) => Filesystem.contains(root, full)) ||
          // A removed venv marker or changed indirect entry may expose a subtree
          // this baseline deliberately did not inspect. Its old files are not new.
          before.skipped.some((root) => Filesystem.contains(root, full)))
      )
        continue
      if (
        prior &&
        prior.size === stamp.size &&
        prior.modified === stamp.modified &&
        prior.changed === stamp.changed &&
        prior.inode === stamp.inode
      )
        continue
      if (files.length >= limit) {
        truncated = true
        break
      }
      if ((await fs.realpath(full).catch(() => undefined)) !== full) continue
      const exists = await fs.lstat(full).catch(() => undefined)
      if (!exists?.isFile() || exists.isSymbolicLink()) continue
      files.push({
        path: full,
        name: stamp.name,
        size: exists.size,
        modified: exists.mtimeMs,
        change: prior ? "modified" : "created",
      })
    }
    return { outputFiles: files, outputFilesTruncated: truncated, outputFilesSource: "filesystem-observation" as const }
  }
}
