import { describe, expect, test } from "bun:test"
import path from "path"
import { Storage } from "../../src/storage/storage"
import { tmpdir } from "../fixture/fixture"

// The marker only advances past a migration that completes, so a single throw
// freezes every migration appended after it, for good.
const diffs = Storage.MIGRATIONS[Storage.MIGRATIONS.length - 1]!

describe("storage migrations", () => {
  test("a damaged record does not fail the migration", async () => {
    await using tmp = await tmpdir()
    const sessions = path.join(tmp.path, "session", "prj_damaged")
    await Bun.write(path.join(sessions, "ses_truncated.json"), "")
    await Bun.write(
      path.join(sessions, "ses_healthy.json"),
      JSON.stringify({
        id: "ses_healthy",
        projectID: "prj_damaged",
        summary: { diffs: [{ additions: 3, deletions: 1 }] },
      }),
    )

    // A zero-length record is what an interrupted write leaves behind, and
    // Bun.file(...).json() throws on it.
    await expect(diffs(tmp.path)).resolves.toBeUndefined()

    // The healthy record is still migrated: one damaged file costs that file.
    expect(await Bun.file(path.join(tmp.path, "session_diff", "ses_healthy.json")).text()).toBeTruthy()
  })
})
