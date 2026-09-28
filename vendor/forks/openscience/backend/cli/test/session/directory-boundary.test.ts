import { $ } from "bun"
import { describe, expect, test } from "bun:test"
import fs from "fs/promises"
import path from "path"
import { Identifier } from "../../src/id/id"
import { Instance } from "../../src/project/instance"
import { NotebookRoutes } from "../../src/server/routes/notebook"
import { Session } from "../../src/session"
import { SessionPrompt } from "../../src/session/prompt"
import { tmpdir, trustProject } from "../fixture/fixture"

describe("session directory boundary", () => {
  test("keeps a session in its recorded git worktree", async () => {
    await using tmp = await tmpdir({ git: true })
    const suffix = Math.random().toString(36).slice(2)
    const linked = `${tmp.path}-boundary-${suffix}`
    const alias = `${tmp.path}-alias-${suffix}`
    await $`git worktree add ${linked} -b ${`boundary-${suffix}`}`.cwd(tmp.path).quiet()
    await fs.symlink(tmp.path, alias)
    await using _ = {
      [Symbol.asyncDispose]: async () => {
        await $`git worktree remove --force ${linked}`.cwd(tmp.path).quiet().nothrow()
        await fs.rm(linked, { recursive: true, force: true })
        await fs.rm(alias, { force: true })
      },
    }

    const state = {
      session: undefined as Session.Info | undefined,
      projectID: "",
    }
    await Instance.provide({
      directory: tmp.path,
      fn: async () => {
        await trustProject()
        state.session = await Session.create({ title: "root session" })
        state.projectID = Instance.project.id
      },
    })
    const session = state.session!
    const linkedPath = await fs.realpath(linked)
    const sentinel = path.join(linkedPath, "wrong-session-shell")

    await Instance.provide({
      directory: linkedPath,
      fn: async () => {
        expect(Instance.project.id).toBe(state.projectID)

        const read = Session.get(session.id)
        await expect(read).rejects.toBeInstanceOf(Session.DirectoryMismatchError)
        const error = await read.catch((value) => value)
        expect(Session.DirectoryMismatchError.isInstance(error)).toBe(true)
        if (Session.DirectoryMismatchError.isInstance(error)) {
          expect(error.toObject()).toEqual({
            name: "SessionDirectoryMismatchError",
            data: {
              sessionID: session.id,
              sessionDirectory: tmp.path,
              instanceDirectory: linkedPath,
            },
          })
        }

        const sessions = []
        for await (const item of Session.list()) sessions.push(item)
        expect(sessions).toEqual([])

        await expect(Session.messages({ sessionID: session.id })).rejects.toBeInstanceOf(Session.DirectoryMismatchError)
        await expect(
          Session.update(session.id, (draft) => {
            draft.title = "wrong worktree"
          }),
        ).rejects.toBeInstanceOf(Session.DirectoryMismatchError)
        await expect(
          Session.updatePart({
            id: Identifier.ascending("part"),
            messageID: Identifier.ascending("message"),
            sessionID: session.id,
            type: "text",
            text: "wrong worktree",
          }),
        ).rejects.toBeInstanceOf(Session.DirectoryMismatchError)
        await expect(Session.create({ parentID: session.id })).rejects.toBeInstanceOf(Session.DirectoryMismatchError)
        await expect(
          Session.createNext({
            id: session.id,
            directory: linkedPath,
          }),
        ).rejects.toBeInstanceOf(Session.DirectoryMismatchError)
        await expect(Session.remove(session.id)).rejects.toBeInstanceOf(Session.DirectoryMismatchError)
        await expect(
          SessionPrompt.shell({
            sessionID: session.id,
            agent: "build",
            command: `touch ${sentinel}`,
          }),
        ).rejects.toBeInstanceOf(Session.DirectoryMismatchError)
        expect(await Bun.file(sentinel).exists()).toBe(false)

        const response = await NotebookRoutes().request("/execute", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            sessionID: session.id,
            id: "analysis.ipynb",
            language: "python",
            code: "open('wrong-session-notebook', 'w').write('blocked')",
          }),
        })
        expect(response.status).toBe(409)
        expect(await response.json()).toEqual({
          name: "SessionDirectoryMismatchError",
          data: {
            sessionID: session.id,
            sessionDirectory: tmp.path,
            instanceDirectory: linkedPath,
          },
        })
        expect(await Bun.file(path.join(linkedPath, "wrong-session-notebook")).exists()).toBe(false)
      },
    })

    await Instance.provide({
      directory: alias,
      fn: async () => {
        expect(Instance.directory).toBe(tmp.path)
        expect((await Session.get(session.id)).title).toBe("root session")
        await Session.update(session.id, (draft) => {
          draft.title = "same worktree"
        })
        expect((await Session.get(session.id)).title).toBe("same worktree")

        const sessions = []
        for await (const item of Session.list()) sessions.push(item.id)
        expect(sessions).toContain(session.id)

        const response = await NotebookRoutes().request("/execute", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            sessionID: session.id,
            id: "analysis.ipynb",
            language: "python",
            code: "40 + 2",
          }),
        })
        expect(response.status).toBe(200)
        const result = (await response.json()) as {
          outputs: Array<{ data?: Record<string, string> }>
        }
        expect(result.outputs.some((output) => output.data?.["text/plain"] === "42")).toBe(true)

        await NotebookRoutes().request("/restart", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            sessionID: session.id,
            id: "analysis.ipynb",
            language: "python",
          }),
        })
        await Session.remove(session.id)
      },
    })
  }, 30_000)

  test("does not allow the recorded directory to be edited", async () => {
    await using tmp = await tmpdir()
    await Instance.provide({
      directory: tmp.path,
      fn: async () => {
        const session = await Session.create({})
        await expect(
          Session.update(session.id, (draft) => {
            draft.directory = path.dirname(tmp.path)
          }),
        ).rejects.toBeInstanceOf(Session.DirectoryImmutableError)
        expect((await Session.get(session.id)).directory).toBe(tmp.path)
        await Session.remove(session.id)
      },
    })
  })
})
