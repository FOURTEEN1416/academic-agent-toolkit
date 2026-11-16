import { expect, test } from "bun:test"
import path from "node:path"
import fs from "node:fs/promises"
import { Skill } from "../../src/skill"
import { Global } from "../../src/global"
import { Instance } from "../../src/project/instance"
import { ProjectTrust } from "../../src/project/trust"
import { tmpdir } from "../fixture/fixture"

const content = (name: string) => `---\nname: ${name}\ndescription: ${name} helper\n---\n\nbody\n`

async function install(namespace: string, name: string, entries: string[] | undefined) {
  const ns = path.join(Global.Path.data, "installed-skills", namespace)
  const dir = path.join(ns, "skills", name)
  await fs.mkdir(dir, { recursive: true })
  await Bun.write(path.join(dir, "SKILL.md"), content(name))
  if (entries) await Bun.write(path.join(ns, "openscience-skills.json"), JSON.stringify({ entries }))
  return { ns, dir }
}

test("the install manifest marks a listed skill as an entry and an unlisted one as not", async () => {
  const namespace = "openscience-entry-flag-probe"
  const a = await install(namespace, "flag-entry-skill", ["flag-entry-skill"])
  const b = await install(namespace, "flag-helper-skill", ["flag-entry-skill"])
  try {
    await using tmp = await tmpdir({ git: true })
    await Instance.provide({
      directory: tmp.path,
      fn: async () => {
        const status = await ProjectTrust.status(Instance.project)
        await ProjectTrust.update(Instance.project, { trusted: true, root: status.root })
        await Skill.invalidate()
        expect((await Skill.get("flag-entry-skill"))?.entry).toBe(true)
        // The manifest exists but omits this one, which is how a URL install
        // marks an internal helper as not a user-facing entry.
        expect((await Skill.get("flag-helper-skill"))?.entry).toBe(false)
      },
    })
  } finally {
    await fs.rm(a.ns, { recursive: true, force: true })
    await fs.rm(b.dir, { recursive: true, force: true }).catch(() => {})
  }
})
