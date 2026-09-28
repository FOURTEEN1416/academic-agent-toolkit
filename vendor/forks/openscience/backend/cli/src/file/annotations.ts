import path from "node:path"
import { ulid } from "ulid"
import z from "zod"
import { Instance } from "../project/instance"
import { ProjectLegacy } from "../project/legacy"
import { Storage } from "../storage/storage"

export namespace ArtifactAnnotation {
  export const Anchor = z.discriminatedUnion("kind", [
    z.object({
      kind: z.literal("artifact"),
      label: z.string().trim().max(500).optional(),
    }),
    z.object({
      kind: z.literal("text"),
      startLine: z.number().int().min(1),
      endLine: z.number().int().min(1),
      quote: z.string().max(10_000).optional(),
    }),
    z.object({
      kind: z.literal("notebook"),
      cellId: z.string().trim().min(1).max(500),
      line: z.number().int().min(1).optional(),
    }),
    z.object({
      kind: z.literal("molecule"),
      selection: z.string().trim().min(1).max(2_000),
      count: z.number().int().min(1).optional(),
    }),
    z.object({
      kind: z.literal("genome"),
      chromosome: z.string().trim().min(1).max(200),
      start: z.number().int().min(0),
      end: z.number().int().min(0),
    }),
  ])
  export type Anchor = z.infer<typeof Anchor>

  export const Message = z.object({
    id: z.string(),
    body: z.string(),
    author: z.string(),
    createdAt: z.number(),
  })
  export type Message = z.infer<typeof Message>

  export const Revision = z.object({
    version: z.number().int().positive(),
    event: z.enum(["created", "edited", "replied", "resolved", "reopened", "deleted"]),
    actor: z.string(),
    at: z.number(),
    status: z.enum(["open", "resolved"]),
    messages: Message.array(),
    deletedAt: z.number().optional(),
  })
  export type Revision = z.infer<typeof Revision>

  export const Info = z.object({
    id: z.string(),
    projectID: z.string(),
    path: z.string(),
    artifactHash: z.string().regex(/^[a-f0-9]{64}$/),
    anchor: Anchor,
    messages: Message.array(),
    status: z.enum(["open", "resolved"]),
    version: z.number().int().positive(),
    revisions: Revision.array(),
    createdAt: z.number(),
    updatedAt: z.number(),
    deletedAt: z.number().optional(),
  })
  export type Info = z.infer<typeof Info>
  const Legacy = Info.omit({ artifactHash: true, version: true, revisions: true, deletedAt: true })
  const Stored = z.object({ projectID: z.string() }).passthrough()

  export const Create = z.object({
    path: z.string().trim().min(1).max(10_000),
    body: z.string().trim().min(1).max(100_000),
    author: z.string().trim().min(1).max(200).optional(),
    anchor: Anchor.default({ kind: "artifact" }),
  })
  export type Create = z.infer<typeof Create>

  export const Update = z
    .object({
      status: z.enum(["open", "resolved"]).optional(),
      body: z.string().trim().min(1).max(100_000).optional(),
      reply: z.string().trim().min(1).max(100_000).optional(),
      author: z.string().trim().min(1).max(200).optional(),
    })
    .refine(
      (value) => value.status !== undefined || value.body !== undefined || value.reply !== undefined,
      "No annotation update supplied",
    )
  export type Update = z.infer<typeof Update>

  const prefix = () => ["artifact_annotation", Instance.project.id]
  const key = (id: string) => [...prefix(), id]

  async function migrate() {
    await ProjectLegacy.adopt("artifact_annotation", Instance.project.id, (value, projectID) => ({
      ...Stored.parse(value),
      projectID,
    }))
  }

  async function target(value: string) {
    const absolute = path.resolve(Instance.directory, value)
    if (!(await Instance.containsCanonicalPath(absolute))) {
      throw new Error(`Annotation target is outside the project: ${value}`)
    }
    return {
      absolute,
      relative: path.relative(Instance.directory, absolute).replaceAll("\\", "/"),
    }
  }

  async function digest(file: string) {
    const hasher = new Bun.CryptoHasher("sha256")
    const reader = Bun.file(file).stream().getReader()
    const feed = async (): Promise<void> => {
      const chunk = await reader.read()
      if (chunk.done) return
      hasher.update(chunk.value)
      return feed()
    }
    await feed()
    return hasher.digest("hex")
  }

  function hash(value: string) {
    const hasher = new Bun.CryptoHasher("sha256")
    hasher.update(value)
    return hasher.digest("hex")
  }

  function revision(record: Info, event: Revision["event"], actor: string, at: number): Revision {
    return {
      version: record.version,
      event,
      actor,
      at,
      status: record.status,
      messages: record.messages.map((message) => ({ ...message })),
      ...(record.deletedAt ? { deletedAt: record.deletedAt } : {}),
    }
  }

  async function read(id: string) {
    await migrate()
    const stored = await Storage.read<unknown>(key(id))
    const current = Info.safeParse(stored)
    if (current.success) return current.data
    const legacy = Legacy.parse(stored)
    const location = await target(legacy.path)
    const artifactHash = (await Bun.file(location.absolute).exists())
      ? await digest(location.absolute)
      : hash(`missing:${legacy.path}`)
    const record: Info = {
      ...legacy,
      artifactHash,
      version: 1,
      revisions: [],
    }
    record.revisions.push(revision(record, "created", record.messages[0]?.author ?? "You", record.createdAt))
    await Storage.write(key(id), record)
    return record
  }

  export async function list(filepath: string) {
    await migrate()
    const location = await target(filepath)
    const keys = await Storage.list(prefix())
    const records = await Promise.all(keys.map((item) => read(item.at(-1)!)))
    return records
      .filter((item) => item.path === location.relative && !item.deletedAt)
      .toSorted((a, b) => a.createdAt - b.createdAt)
  }

  export async function create(input: Create) {
    await migrate()
    const now = Date.now()
    const id = `ann_${ulid()}`
    const location = await target(input.path)
    if (!(await Bun.file(location.absolute).exists())) {
      throw new Error(`Annotation target does not exist: ${input.path}`)
    }
    const record: Info = {
      id,
      projectID: Instance.project.id,
      path: location.relative,
      artifactHash: await digest(location.absolute),
      anchor: input.anchor,
      messages: [
        {
          id: `msg_${ulid()}`,
          body: input.body,
          author: input.author ?? "You",
          createdAt: now,
        },
      ],
      status: "open",
      version: 1,
      revisions: [],
      createdAt: now,
      updatedAt: now,
    }
    record.revisions.push(revision(record, "created", input.author ?? "You", now))
    await Storage.write(key(id), record)
    return record
  }

  export async function update(id: string, input: Update) {
    await read(id)
    return Storage.update<Info>(key(id), (record) => {
      if (record.deletedAt) throw new Error(`Annotation ${id} has been deleted`)
      const now = Date.now()
      const actor = input.author ?? "You"
      const event: Revision["event"] = input.body
        ? "edited"
        : input.reply
          ? "replied"
          : input.status === "resolved"
            ? "resolved"
            : "reopened"
      if (input.status) record.status = input.status
      if (input.body && record.messages[0]) {
        record.messages[0].body = input.body
        record.messages[0].author = actor
      }
      if (input.reply) {
        record.messages.push({
          id: `msg_${ulid()}`,
          body: input.reply,
          author: actor,
          createdAt: now,
        })
      }
      record.version += 1
      record.updatedAt = now
      record.revisions.push(revision(record, event, actor, now))
    })
  }

  export async function remove(id: string) {
    await read(id)
    const record = await Storage.update<Info>(key(id), (record) => {
      if (record.deletedAt) return
      const now = Date.now()
      record.deletedAt = now
      record.updatedAt = now
      record.version += 1
      record.revisions.push(revision(record, "deleted", "You", now))
    })
    return { deleted: true as const, version: record.version }
  }

  export async function history(id: string) {
    return read(id)
  }
}
