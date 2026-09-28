import crypto from "node:crypto"
import fs from "node:fs/promises"
import path from "node:path"
import z from "zod"
import { Global } from "@/global"
import { Storage } from "@/storage/storage"
import { Project } from "./project"

export namespace ManagedProject {
  export const Info = z.object({
    version: z.literal(1),
    projectID: z.string().startsWith("prj_"),
    directory: z.string(),
    time: z.object({
      created: z.number(),
    }),
  })
  export type Info = z.infer<typeof Info>

  async function rollback(directory: string) {
    const canonical = Project.canonicalize(directory)
    const projects = await Storage.list(["project"])
    const managed = await Storage.list(["managed_project"])
    const projectIDs = await Promise.all(
      projects.map(async (key) => {
        const project = await Storage.read<Project.Info>(key).catch(() => undefined)
        if (!project) return
        if (Project.canonicalize(project.worktree) !== canonical) return
        return key.at(-1)
      }),
    )
    const markerIDs = await Promise.all(
      managed.map(async (key) => {
        const marker = await Storage.read<unknown>(key)
          .then(Info.safeParse)
          .catch(() => undefined)
        if (!marker?.success) return
        if (Project.canonicalize(marker.data.directory) !== canonical) return
        return key.at(-1)
      }),
    )
    const ids = [...new Set([...projectIDs, ...markerIDs].filter((id): id is string => !!id))]
    const cleanup = await Promise.allSettled([
      ...ids.map((id) => Storage.remove(["managed_project", id])),
      ...ids.map((id) => Storage.remove(["project", id])),
      ...ids.map((id) => Storage.remove(["project_filesystem", id])),
      fs.rm(directory, { recursive: true, force: true }),
    ])
    const failures = cleanup.filter((result) => result.status === "rejected")
    if (failures.length === 0) return
    throw new AggregateError(
      failures.map((result) => result.reason),
      `Failed to roll back managed project ${directory}`,
    )
  }

  export async function create(name: string, checkpoint?: (project: Project.Info) => Promise<void>) {
    const parent = path.join(Global.Path.data, "projects")
    const directory = path.join(parent, crypto.randomUUID())
    await fs.mkdir(parent, { recursive: true })
    return fs
      .mkdir(directory)
      .then(async () => {
        const created = await Project.fromDirectory(directory)
        const project = await Project.update({
          projectID: created.project.id,
          name,
        })
        await checkpoint?.(project)
        await Storage.write<Info>(["managed_project", project.id], {
          version: 1,
          projectID: project.id,
          directory: await fs.realpath(directory),
          time: {
            created: Date.now(),
          },
        })
        return project
      })
      .catch(async (error) => {
        const cleanup = await rollback(directory).catch((failure) => failure)
        if (cleanup instanceof Error) throw new AggregateError([error, cleanup], "Managed project creation failed")
        throw error
      })
  }
}
