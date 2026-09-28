import { isDeepStrictEqual } from "node:util"
import z from "zod"
import { Storage } from "../storage/storage"
import { Log } from "../util/log"

export namespace ProjectLegacy {
  const log = Log.create({ service: "project-legacy" })
  const Alias = z.object({
    id: z.string(),
    projectID: z.string(),
  })

  function legacy(id: string) {
    return id !== "global" && !id.startsWith("prj_")
  }

  /**
   * Return legacy selectors which resolve to a canonical opaque project.
   * `global` is deliberately excluded because it was shared by unrelated
   * folders and cannot be adopted safely without record-level directory data.
   */
  export async function ids(projectID: string) {
    const keys = await Storage.list(["project_alias"]).catch(() => [])
    const links = (
      await Promise.all(
        keys.map(async (key) => {
          const value = await Storage.read<unknown>(key).catch(() => undefined)
          const parsed = Alias.safeParse(value)
          if (!parsed.success) return
          return {
            key: key.at(-1)!,
            value: parsed.data,
          }
        }),
      )
    ).filter((item): item is { key: string; value: z.infer<typeof Alias> } => !!item)
    const result = new Set([projectID])

    while (true) {
      const size = result.size
      for (const link of links) {
        if (!result.has(link.value.projectID)) continue
        if (legacy(link.key)) result.add(link.key)
        if (legacy(link.value.id)) result.add(link.value.id)
      }
      if (result.size === size) break
    }
    result.delete(projectID)
    return [...result].toSorted()
  }

  /**
   * Lazily fold a project-keyed store into its canonical bucket. A divergent
   * target is never overwritten or deleted: the legacy record remains intact
   * for explicit recovery instead of silently losing history.
   */
  export async function adopt<T>(store: string, projectID: string, rewrite: (record: unknown, projectID: string) => T) {
    for (const legacyID of await ids(projectID)) {
      const keys = await Storage.list([store, legacyID]).catch(() => [])
      for (const source of keys) {
        const value = await Storage.read<unknown>(source).catch((error) => {
          if (Storage.NotFoundError.isInstance(error)) return
          throw error
        })
        if (value === undefined) continue
        const target = [store, projectID, ...source.slice(2)]
        const record = rewrite(value, projectID)
        const existing = await Storage.read<T>(target).catch((error) => {
          if (Storage.NotFoundError.isInstance(error)) return
          throw error
        })
        if (existing && !isDeepStrictEqual(existing, record)) {
          log.warn("preserving divergent legacy project record", {
            store,
            legacyID,
            projectID,
            key: source.slice(2).join("/"),
          })
          continue
        }
        if (!existing) await Storage.write(target, record)
        await Storage.remove(source)
      }
    }
  }
}
