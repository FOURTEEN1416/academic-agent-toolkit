import { describe, expect, test } from "bun:test"
import fs from "node:fs/promises"
import path from "path"
import { GlobTool } from "../../src/tool/glob"
import { Instance } from "../../src/project/instance"
import { tmpdir } from "../fixture/fixture"

const ctx = {
  sessionID: "test",
  messageID: "",
  callID: "",
  agent: "research",
  abort: AbortSignal.any([]),
  messages: [],
  metadata: () => {},
  ask: async () => {},
}

describe("glob", () => {
  test("orders equal-mtime files deterministically, newest first", async () => {
    await using tmp = await tmpdir({
      init: async (dir) => {
        // One checkout gives every file the same mtime, so the comparator has
        // nothing to break the tie on and filesystem enumeration order leaks
        // into the result.
        for (const name of ["delta.ts", "alpha.ts", "charlie.ts", "bravo.ts"]) {
          await Bun.write(path.join(dir, name), "export {}\n")
        }
        // Pin one mtime across all four, so the ordering cannot come from the
        // clock even on a filesystem with coarse timestamp resolution.
        const shared = new Date(1_700_000_000_000)
        for (const name of ["delta.ts", "alpha.ts", "charlie.ts", "bravo.ts"]) {
          await fs.utimes(path.join(dir, name), shared, shared)
        }
      },
    })
    await Instance.provide({
      directory: tmp.path,
      fn: async () => {
        const run = async () => {
          const result = await (await GlobTool.init()).execute({ pattern: "*.ts" }, ctx)
          return result.output.split("\n")
        }
        const first = await run()
        const second = await run()
        const mtimes = await Promise.all(
          ["delta", "alpha", "charlie", "bravo"].map((n) =>
            Bun.file(path.join(tmp.path, `${n}.ts`))
              .stat()
              .then((s) => s.mtime.getTime()),
          ),
        )
        // The point of the fixture: the four files share an mtime, so the
        // comparator has nothing to order by and only the tiebreak can.
        expect(new Set(mtimes).size).toBe(1)
        // The comparator is newest-first on mtime, and the tiebreak is the path
        // ascending. With every mtime equal that is the whole ordering.
        const names = (list: string[]) => list.map((entry) => path.basename(entry))
        const expected = ["delta.ts", "charlie.ts", "bravo.ts", "alpha.ts"]
          .map((n) => path.join(tmp.path, n))
          .toSorted((a, b) => a.localeCompare(b))
          .map((entry) => path.basename(entry))
        expect(names(first)).toEqual(expected)
        expect(names(second)).toEqual(names(first))
      },
    })
  })

  test("still orders strictly newer files first", async () => {
    await using tmp = await tmpdir({
      init: async (dir) => {
        await Bun.write(path.join(dir, "older.ts"), "export {}\n")
        await Bun.write(path.join(dir, "newer.ts"), "export {}\n")
        const stale = new Date(Date.now() - 60_000)
        await fs.utimes(path.join(dir, "older.ts"), stale, stale)
      },
    })
    await Instance.provide({
      directory: tmp.path,
      fn: async () => {
        const result = await (await GlobTool.init()).execute({ pattern: "*.ts" }, ctx)
        const paths = result.output.split("\n")
        expect(paths[0]).toBe(path.join(tmp.path, "newer.ts"))
        expect(paths[1]).toBe(path.join(tmp.path, "older.ts"))
      },
    })
  })
})
