import { expect, test } from "bun:test"
import fs from "node:fs/promises"
import os from "node:os"
import path from "node:path"
import { Command } from "../../src/command"
import { Instance } from "../../src/project/instance"
import { Log } from "../../src/util/log"

Log.init({ print: false })

// A directory name may legally contain the sequences a replacement string
// treats as patterns, and `/init` has to name the directory it really has.
test.each(["prices$$", "a$&b", "x$'y"])(
  "/init names a project directory containing %s verbatim",
  async (name) => {
    const root = path.join(os.tmpdir(), `openscience-init-${name}`)
    await fs.rm(root, { recursive: true, force: true })
    await fs.mkdir(root, { recursive: true })
    try {
      await Instance.provide({
        directory: root,
        fn: async () => {
          const command = await Command.get("init")
          // The prompt is the only thing that tells the agent which directory
          // it is working in, so it has to carry the path through untouched.
          expect(command?.template).toContain(Instance.worktree)
        },
      })
    } finally {
      await fs.rm(root, { recursive: true, force: true })
    }
  },
  15_000,
)
