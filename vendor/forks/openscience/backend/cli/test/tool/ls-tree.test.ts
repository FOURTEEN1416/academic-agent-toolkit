import { describe, expect, test } from "bun:test"
import path from "node:path"
import { Instance } from "../../src/project/instance"
import { Session } from "../../src/session"
import { SessionFilesystem } from "../../src/session/filesystem"
import { ListTool, renderTree } from "../../src/tool/ls"
import { tmpdir, trustProject } from "../fixture/fixture"

// The tree is model-facing text, so it must come out the same whichever
// separator ripgrep printed. On win32 that meant every file three or more
// directories deep was collected, counted, and then dropped from the output.
const expected = [
  "  a/",
  "    b/",
  "      c/",
  "        deep.txt",
  "  src/",
  "    lib/",
  "      two.txt",
  "    evidence.txt",
  "  root.txt",
  "",
].join("\n")

describe("list tree", () => {
  test.each(["/", "\\"])("renders the same tree for %j separated paths", (sep) => {
    const files = ["root.txt", "src/evidence.txt", "src/lib/two.txt", "a/b/c/deep.txt"].map((file) =>
      file.replaceAll("/", sep),
    )
    expect(renderTree(files)).toBe(expected)
  })

  test("renders a file three directories deep from the real listing", async () => {
    await using tmp = await tmpdir({ git: true })
    await Instance.provide({
      directory: tmp.path,
      init: trustProject,
      fn: async () => {
        const session = await Session.create({})
        const workspace = await SessionFilesystem.workspace(session.id)
        for (const [name, body] of [
          [path.join("a", "b", "c", "deep.txt"), "three levels deep"],
          [path.join("src", "lib", "two.txt"), "two levels deep"],
          ["root.txt", "root"],
        ] as const) {
          await Bun.write(path.join(workspace, name), body)
        }
        const output = (
          await (
            await ListTool.init()
          ).execute(
            {},
            {
              sessionID: session.id,
              messageID: "msg_list_tree",
              callID: "call_list_tree",
              agent: "research",
              abort: AbortSignal.any([]),
              messages: [],
              metadata: async () => {},
              ask: async () => {},
            },
          )
        ).output
        expect(output).toContain("        deep.txt")
        expect(output).toContain("      two.txt")
      },
    })
  }, 30_000)
})
