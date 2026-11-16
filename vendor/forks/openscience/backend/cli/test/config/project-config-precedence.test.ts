import { expect, test } from "bun:test"
import fs from "fs/promises"
import path from "path"
import { Config } from "../../src/config/config"
import { Instance } from "../../src/project/instance"
import { tmpdir } from "../fixture/fixture"

async function write(dir: string, config: unknown) {
  await fs.mkdir(dir, { recursive: true })
  await Bun.write(path.join(dir, "openscience.json"), JSON.stringify(config))
}

test("a nested .openscience overrides the one above it", async () => {
  await using tmp = await tmpdir()
  // `up()` walks from the nearer directory to the farther one, and the merge is
  // later-wins, so walking the list as returned let the worktree-wide file
  // override the one written for this subtree.
  const worktree = path.join(tmp.path, "worktree")
  const nested = path.join(worktree, "src", "tool")
  // The worktree is discovered by walking up for .git, so the outer directory
  // has to look like a checkout for the two levels to be in one run.
  await fs.mkdir(path.join(worktree, ".git"), { recursive: true })
  await write(path.join(worktree, ".openscience"), {
    model: "model-from-the-worktree-root",
    theme: "root-theme",
  })
  await write(path.join(nested, ".openscience"), { model: "model-from-this-directory" })

  await Instance.provide({
    directory: nested,
    fn: async () => {
      const config = await Config.get()
      expect(config.model).toBe("model-from-this-directory")
      // A key only the outer file sets still comes through.
      expect(config.theme).toBe("root-theme")
    },
  })
})

test("with no nested .openscience the worktree-wide one applies", async () => {
  await using tmp = await tmpdir()
  const worktree = path.join(tmp.path, "worktree")
  const nested = path.join(worktree, "src", "tool")
  await fs.mkdir(path.join(worktree, ".git"), { recursive: true })
  await write(path.join(worktree, ".openscience"), { model: "model-from-the-worktree-root" })
  await fs.mkdir(nested, { recursive: true })

  await Instance.provide({
    directory: nested,
    fn: async () => {
      expect((await Config.get()).model).toBe("model-from-the-worktree-root")
    },
  })
})
