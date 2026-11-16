import { describe, expect, test } from "bun:test"
import fs from "node:fs/promises"
import path from "node:path"
import { BashTool } from "../../src/tool/bash"
import { Instance } from "../../src/project/instance"
import { SessionFilesystem } from "../../src/session/filesystem"
import { FileOutputReceipts } from "../../src/file/output-receipts"
import { executionSession, tmpdir } from "../fixture/fixture"

const quote = (value: string) => `'${value.replaceAll("'", "'\\''")}'`

describe("Bash filesystem output receipts", () => {
  test("observes real non-Git scratch and project writes with snapshots off, never deletions or printed paths", async () => {
    await using tmp = await tmpdir({ config: { snapshot: false } })
    await Instance.provide({
      directory: tmp.path,
      fn: async () => {
        const session = await executionSession()
        const workspace = await SessionFilesystem.workspace(session.id)
        await SessionFilesystem.grant({ sessionID: session.id, path: tmp.path, access: "write", scope: "session" })
        await Bun.write(path.join(workspace, "existing.json"), "old")
        await Bun.write(path.join(workspace, "deleted.csv"), "old")
        await Bun.write(path.join(workspace, "unchanged.py"), "old")
        const result = await (
          await BashTool.init()
        ).execute(
          {
            command: `printf new > created.py; printf changed > existing.json; rm deleted.csv; printf report > ${quote(path.join(tmp.path, "report.md"))}; printf '/not/a/real/output.csv\\n'`,
            description: "Write real outputs",
          },
          {
            sessionID: session.id,
            messageID: "msg_outputs",
            callID: "call_outputs",
            agent: "research",
            abort: AbortSignal.any([]),
            messages: [],
            metadata() {},
            async ask() {},
          },
        )
        expect(result.metadata.exit).toBe(0)
        expect(result.metadata.outputFilesSource).toBe("filesystem-observation")
        expect(result.metadata.outputFilesTruncated).toBe(false)
        expect(result.metadata.outputFiles).toEqual(
          expect.arrayContaining([
            expect.objectContaining({ path: path.join(workspace, "created.py"), change: "created", size: 3 }),
            expect.objectContaining({ path: path.join(workspace, "existing.json"), change: "modified", size: 7 }),
            expect.objectContaining({ path: path.join(tmp.path, "report.md"), change: "created", size: 6 }),
          ]),
        )
        expect(result.metadata.outputFiles.map((file) => file.path).toSorted()).toEqual(
          [
            path.join(workspace, "created.py"),
            path.join(workspace, "existing.json"),
            path.join(tmp.path, "report.md"),
          ].toSorted(),
        )
      },
    })
  })

  test("retains existing output receipts from a nonzero command without claiming command success", async () => {
    await using tmp = await tmpdir()
    await Instance.provide({
      directory: tmp.path,
      fn: async () => {
        const session = await executionSession()
        const workspace = await SessionFilesystem.workspace(session.id)
        const result = await (
          await BashTool.init()
        ).execute(
          { command: "printf partial > result; exit 7", description: "Fail after writing" },
          {
            sessionID: session.id,
            messageID: "msg_partial_outputs",
            agent: "research",
            abort: AbortSignal.any([]),
            messages: [],
            metadata() {},
            async ask() {},
          },
        )
        expect(result.metadata.exit).toBe(7)
        expect(result.metadata.outputFiles).toEqual([
          expect.objectContaining({ path: path.join(workspace, "result"), change: "created", size: 7 }),
        ])
      },
    })
  })

  test("skips indirect, private and dependency paths and does not infer creation from truncated baselines", async () => {
    await using tmp = await tmpdir()
    await using outside = await tmpdir()
    await fs.mkdir(path.join(tmp.path, "node_modules"))
    await fs.symlink(outside.path, path.join(tmp.path, "linked"))
    const privateRoot = path.join(tmp.path, "private")
    await fs.mkdir(privateRoot)
    const before = await FileOutputReceipts.observe({ roots: [tmp.path], unreadable: [privateRoot] })
    await Promise.all([
      Bun.write(path.join(tmp.path, "node_modules", "package.json"), "{}"),
      Bun.write(path.join(outside.path, "secret.csv"), "private"),
      Bun.write(path.join(privateRoot, "secret.csv"), "private"),
      Bun.write(path.join(tmp.path, "visible.csv"), "public"),
    ])
    expect(
      (await FileOutputReceipts.finish(before, { roots: [tmp.path], unreadable: [privateRoot] })).outputFiles,
    ).toEqual([expect.objectContaining({ path: path.join(tmp.path, "visible.csv") })])
    const incomplete = await FileOutputReceipts.observe({ roots: [tmp.path], limits: { entries: 0 } })
    await Bun.write(path.join(tmp.path, "later.csv"), "later")
    const result = await FileOutputReceipts.finish(incomplete, { roots: [tmp.path] })
    expect(result.outputFilesTruncated).toBe(true)
    expect(result.outputFiles).toEqual([])
    expect((await FileOutputReceipts.finish(before, { roots: [] })).outputFiles).toEqual([])
  })

  test("retains new scratch receipts when a separate project baseline is incomplete", async () => {
    await using tmp = await tmpdir()
    const project = path.join(tmp.path, "project")
    const scratch = path.join(tmp.path, "scratch")
    await fs.mkdir(path.join(project, "deep", "nested"), { recursive: true })
    await fs.mkdir(scratch)
    await Bun.write(path.join(project, "deep", "nested", "unobserved.csv"), "existing")
    await Bun.write(path.join(project, "known.csv"), "old")
    const before = await FileOutputReceipts.observe({ roots: [project, scratch], limits: { depth: 1 } })
    expect(before.truncated).toBe(true)
    await Bun.write(path.join(scratch, "answer.json"), "{}")
    await Bun.write(path.join(project, "new.csv"), "new")
    await Bun.write(path.join(project, "known.csv"), "modified")
    // The second observation sees every file. Previously unseen project files
    // remain uncertain; the fully observed scratch root is independently safe.
    const result = await FileOutputReceipts.finish(before, { roots: [project, scratch] })
    expect(result.outputFilesTruncated).toBe(true)
    expect(result.outputFiles).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ path: path.join(scratch, "answer.json"), change: "created" }),
        expect.objectContaining({ path: path.join(project, "known.csv"), change: "modified" }),
      ]),
    )
    expect(result.outputFiles).toHaveLength(2)
  })

  test("does not label an unobserved venv subtree new when its marker disappears", async () => {
    await using tmp = await tmpdir()
    const project = path.join(tmp.path, "project")
    const scratch = path.join(tmp.path, "scratch")
    const environment = path.join(project, "environment")
    await fs.mkdir(environment, { recursive: true })
    await fs.mkdir(scratch)
    await Bun.write(path.join(environment, "pyvenv.cfg"), "home = /fixture/python")
    await Bun.write(path.join(environment, "already-existed.csv"), "existing")
    const before = await FileOutputReceipts.observe({ roots: [project, scratch] })
    expect(before.truncated).toBe(false)
    await fs.unlink(path.join(environment, "pyvenv.cfg"))
    await Bun.write(path.join(project, "new.csv"), "new")
    await Bun.write(path.join(scratch, "answer.json"), "{}")
    const result = await FileOutputReceipts.finish(before, { roots: [project, scratch] })
    expect(result.outputFilesTruncated).toBe(false)
    expect(result.outputFiles.map((file) => file.path).toSorted()).toEqual(
      [path.join(project, "new.csv"), path.join(scratch, "answer.json")].toSorted(),
    )
    expect(result.outputFiles.every((file) => file.change === "created")).toBe(true)
  })
})
