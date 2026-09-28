import { describe, expect, test } from "bun:test"
import { $ } from "bun"
import path from "node:path"
import { ArtifactFile } from "../../src/file/artifacts"
import { tmpdir } from "../fixture/fixture"

describe("ArtifactFile reproducibility", () => {
  test("audits git, environment locks, notebooks, and local artifacts", async () => {
    await using tmp = await tmpdir({
      git: true,
      init: async (directory) => {
        await Bun.write(path.join(directory, "README.md"), "# Reproducible study\n")
        await Bun.write(path.join(directory, "uv.lock"), "version = 1\n")
        await Bun.write(path.join(directory, "pyproject.toml"), '[project]\nname = "study"\n')
        await Bun.write(
          path.join(directory, "analysis.ipynb"),
          JSON.stringify({
            nbformat: 4,
            nbformat_minor: 5,
            metadata: {},
            cells: [{ cell_type: "code", metadata: {}, source: ["print('ok')"], outputs: [], execution_count: null }],
          }),
        )
        await Bun.write(path.join(directory, "results.csv"), "metric,value\naccuracy,0.95\n")
        await $`git add README.md uv.lock pyproject.toml analysis.ipynb results.csv`.cwd(directory).quiet()
        await $`git -c user.name=OpenScience -c user.email=test@openscience.local commit -m "reproducible baseline"`
          .cwd(directory)
          .quiet()
      },
    })
    const branch = (await $`git branch --show-current`.cwd(tmp.path).quiet().text()).trim()

    const audit = await ArtifactFile.audit(tmp.path)
    expect(audit.status).toBe("ready")
    expect(audit.score).toBeGreaterThanOrEqual(90)
    expect(audit.git).toMatchObject({ dirty: false, branch })
    expect(audit.lockfiles).toContain("uv.lock")
    expect(audit.environments).toContain("pyproject.toml")
    expect(audit.notebooks).toEqual({ total: 1, valid: 1, invalid: [] })
    expect(audit.artifacts).toMatchObject({ total: 3, nonempty: 3 })
  })

  test("reports actionable blockers for an unlocked invalid project", async () => {
    await using tmp = await tmpdir({
      init: async (directory) => {
        await Bun.write(path.join(directory, "broken.ipynb"), "{")
        await Bun.write(path.join(directory, "empty.csv"), "")
      },
    })

    const audit = await ArtifactFile.audit(tmp.path)
    expect(audit.status).toBe("blocked")
    expect(audit.notebooks.invalid).toEqual(["broken.ipynb"])
    expect(audit.checks.find((check) => check.id === "environment-lock")?.status).toBe("fail")
    expect(audit.checks.find((check) => check.id === "notebooks")?.status).toBe("fail")
  })

  test("does not mark an empty project as having complete artifacts", async () => {
    await using tmp = await tmpdir()

    const audit = await ArtifactFile.audit(tmp.path)
    expect(audit.artifacts).toMatchObject({ total: 0, nonempty: 0, bytes: 0 })
    expect(audit.checks.find((check) => check.id === "artifacts")?.status).toBe("warn")
  })

  test("creates a deterministic checksum manifest without escaping the project", async () => {
    await using tmp = await tmpdir({
      init: async (directory) => {
        await Bun.write(path.join(directory, "results", "table.csv"), "a,b\n1,2\n")
        await Bun.write(path.join(directory, "figure.svg"), "<svg></svg>")
      },
    })

    const manifest = await ArtifactFile.manifest(tmp.path)
    expect(manifest.format).toBe("openscience.artifact-manifest.v1")
    expect(manifest.artifacts.map((item) => item.path)).toEqual(["figure.svg", "results/table.csv"])
    expect(manifest.artifacts.every((item) => /^[a-f0-9]{64}$/.test(item.sha256))).toBe(true)
    expect(manifest.digest).toMatch(/^[a-f0-9]{64}$/)
  })
})
