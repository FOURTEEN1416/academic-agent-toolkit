import { describe, expect, test } from "bun:test"
import path from "path"
import { File } from "../../src/file"
import { Instance } from "../../src/project/instance"
import { tmpdir } from "../fixture/fixture"

describe("File.search", () => {
  test("returns the initial index and refreshes it after a file is added", async () => {
    await using tmp = await tmpdir({
      git: true,
      init: async (dir) => {
        await Bun.write(path.join(dir, "atlas.ts"), "export const atlas = true\n")
      },
    })

    await Instance.provide({
      directory: tmp.path,
      fn: async () => {
        try {
          expect(await File.search({ query: "atlas", dirs: false })).toEqual(["atlas.ts"])

          await File.write("fresh-result.ts", "export const fresh = true\n")

          // The first read stays responsive with the prior snapshot while it
          // starts one invalidation-driven refresh in the background.
          expect(await File.search({ query: "fresh", dirs: false })).toEqual([])

          for (let attempt = 0; attempt < 20; attempt++) {
            const result = await File.search({ query: "fresh", dirs: false })
            if (result.includes("fresh-result.ts")) return
            await Bun.sleep(5)
          }

          throw new Error("file-search index did not refresh after an add event")
        } finally {
          await Instance.dispose()
        }
      },
    })
  })

  test("browsing with nothing typed lists the top level first and keeps generated caches out unless named", async () => {
    await using tmp = await tmpdir({
      init: async (dir) => {
        await Bun.write(path.join(dir, "report.tex"), "\\documentclass{article}\n")
        await Bun.write(path.join(dir, "figures", "churn.png"), "png")
        await Bun.write(path.join(dir, "autoresearch_churn", "train.py"), "print(1)\n")
        await Bun.write(path.join(dir, "autoresearch_churn", "final_inputs", "test.csv"), "a,b\n")
        await Bun.write(path.join(dir, ".ruff_cache", "0.12.5", "cache.json"), "{}")
        await Bun.write(path.join(dir, "autoresearch_churn", "__pycache__", "train.pyc"), "x")
      },
    })
    await Instance.provide({
      directory: tmp.path,
      fn: async () => {
        try {
          // Folders before files at each depth, shallow before deep.
          const browse = await File.search({ query: "", dirs: true, limit: 20 })
          expect(browse.slice(0, 3)).toEqual(["autoresearch_churn/", "figures/", "report.tex"])
          expect(browse).toContain("autoresearch_churn/final_inputs/")
          expect(browse.indexOf("figures/churn.png")).toBeGreaterThan(browse.indexOf("report.tex"))
          expect(browse.some((item) => item.includes("__pycache__") || item.includes(".ruff_cache"))).toBe(false)
          // A query reaches the caches only when it names one.
          expect(await File.search({ query: "train", dirs: true })).not.toContain(
            "autoresearch_churn/__pycache__/train.pyc",
          )
          expect(await File.search({ query: "__pycache__", dirs: true })).toContain(
            "autoresearch_churn/__pycache__/train.pyc",
          )
          expect(await File.search({ query: "ruff", dirs: true })).toContain(".ruff_cache/0.12.5/cache.json")
        } finally {
          await Instance.dispose()
        }
      },
    })
  })
})
