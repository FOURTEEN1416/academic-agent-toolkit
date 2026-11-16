import { expect, test } from "bun:test"
import path from "node:path"
import { Instance } from "../../src/project/instance"
import { SessionFilesystem } from "../../src/session/filesystem"
import { displayPath } from "../../src/tool/display-path"
import { executionSession, tmpdir } from "../fixture/fixture"

test("tool rows name project, scratch and skill files by where they live", async () => {
  await using tmp = await tmpdir({ git: true })
  await Instance.provide({
    directory: tmp.path,
    fn: async () => {
      const session = await executionSession()
      const workspace = await SessionFilesystem.workspace(session.id)
      expect(await displayPath(path.join(tmp.path, "figures", "a.png"), session.id)).toBe(path.join("figures", "a.png"))
      expect(await displayPath(path.join(workspace, "report-page-01.png"), session.id)).toBe(
        "scratch/report-page-01.png",
      )
      expect(
        await displayPath(
          "/Users/me/.cache/openscience/bundled-skills/f48e2c4a58f1/paper-writing/assets/x.tex",
          session.id,
        ),
      ).toBe("skill:paper-writing/assets/x.tex")
      expect(await displayPath("/repo/backend/cli/skills/core/figures/assets/figstyle.py", session.id)).toBe(
        "skill:figures/assets/figstyle.py",
      )
      expect(await displayPath("/Users/me/Documents/data.csv", session.id)).toBe("/Users/me/Documents/data.csv")
    },
  })
})
