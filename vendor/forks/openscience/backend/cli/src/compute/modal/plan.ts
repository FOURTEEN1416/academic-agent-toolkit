import path from "path"
import fs from "fs/promises"
import z from "zod"
import ignore from "ignore"
import { Filesystem } from "../../util/filesystem"
import type { ModalAdapter } from "./adapter"
import { ModalUpload } from "./upload"
import { ComputeSecrets } from "../secrets"

export namespace ModalPlan {
  const DENY = new Set([
    ".git",
    ".openscience",
    ".ssh",
    ".aws",
    ".azure",
    ".kube",
    ".gnupg",
    ".docker",
    ".huggingface",
    ".cache",
    ".conda",
    ".venv",
    "venv",
    ".tox",
    ".nox",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".ipynb_checkpoints",
    ".next",
    ".turbo",
    ".terraform",
    ".terraform.d",
    "dist",
    "build",
    "target",
  ])
  const DENY_PATH = /(^|\/)\.config\/(?:gcloud|gh|hub)(?:\/|$)/i
  const SECRET =
    /(^|\/)(?:\.env(?:\..*)?|\.modal\.toml|\.netrc|\.npmrc|\.pypirc|\.git-credentials|credentials(?:\.json)?|.*\.(?:pem|key|p12|pfx))$/i

  export const Schema = z.object({
    digest: z.string().length(64),
    provider: z.literal("modal"),
    purpose: z.string(),
    app: z.string(),
    environment: z.string().optional(),
    image: z.string(),
    packages: z.array(z.string()),
    package_lock: z
      .object({ digest: z.string().length(64), requirements: z.string().trim().min(1).max(100_000) })
      .strict()
      .optional(),
    secret_refs: ComputeSecrets.Ref.array(),
    gpu: z.string(),
    resources: z
      .object({
        cpus: z.number().optional(),
        gpus: z.number().optional(),
        memory_gb: z.number().optional(),
      })
      .optional(),
    timeout_minutes: z.number().positive(),
    network: z.enum(["unrestricted", "none"]),
    command: z.string(),
    cwd: z.string(),
    workspace_cwd: z.string(),
    uploads: z.array(
      z.object({
        path: z.string(),
        size: z.number().int().nonnegative(),
        sha256: z.string().length(64),
        named: z.boolean().optional(),
      }),
    ),
    upload_bytes: z.number().int().nonnegative(),
    outputs: z.string().array(),
    warning: z.string(),
  })
  export type Schema = z.infer<typeof Schema>

  export type Input = {
    purpose?: string
    command: string
    cwd: string
    workspaceCwd?: string
    image: string
    packages: string[]
    packageLock?: { digest: string; requirements: string }
    secretRefs?: ComputeSecrets.Ref[]
    gpu: string
    resources?: { cpus?: number; gpus?: number; memory_gb?: number }
    timeoutMinutes: number
    uploads: string[]
    deniedUploads?: "skip" | "error"
    excludeUploads?: readonly string[]
    outputs: string[]
    context: Pick<ModalAdapter.Context, "app" | "environment" | "network">
  }

  export type Prepared = { plan: Schema; files: ModalAdapter.File[] }

  export type StagingOptions = {
    /** Prefix used when upload globs are rooted above the selected cwd (SSH). */
    prefix?: string
    /** Explicit upload requests keep the normal fail-closed denied-path behavior. */
    denied?: "skip" | "error"
    /** Relative paths left out however the patterns match them: a study's
     * ledger files, which the study rewrites while a job waits for approval. */
    exclude?: readonly string[]
  }

  const posix = (value: string) => value.split(path.sep).join("/").replace(/^\.\//, "")

  function workspaceCwd(value: string | undefined) {
    const current = posix(value?.trim() || ".")
    if (path.posix.isAbsolute(current) || current.split("/").includes("..")) {
      throw new Error(`Modal working directory must stay inside the session workspace: ${value}`)
    }
    return current || "."
  }

  /** The tracking SDK a study writes under its cwd. It is OpenScience's own
   * generated Python, holds no state or secrets, and the run cannot import
   * openscience_track without it; the rest of `.openscience` stays denied. */
  const SDK_PREFIX = ".openscience/sdk/"
  /** Bookkeeping this side writes into a staged copy; never an upload, never
   * an error to have matched. */
  export const INTERNAL = new Set([".openscience/staged.json"])
  const internal = (relative: string) =>
    [...INTERNAL].some((marker) => relative === marker || relative.endsWith(`/${marker}`))

  function forbidden(file: string) {
    if (`${file}/`.startsWith(SDK_PREFIX)) return SECRET.test(file)
    const segments = file.split("/")
    return segments.some((part) => DENY.has(part)) || DENY_PATH.test(file) || SECRET.test(file)
  }

  /** A denied directory that lies on the way to the SDK is still walked, so
   * `.openscience/sdk` is reached while `.openscience/<anything else>` is not. */
  function leadsToSdk(directory: string) {
    return SDK_PREFIX.startsWith(`${directory}/`)
  }

  function uploadPatterns(patterns: string[], label: string) {
    return patterns.map((pattern) => {
      if (path.isAbsolute(pattern) || pattern.split(/[\\/]/).includes("..")) {
        throw new Error(`${label} upload pattern must stay inside the project: ${pattern}`)
      }
      const normalized = posix(pattern)
      return { pattern: normalized, glob: new Bun.Glob(normalized) }
    })
  }

  function requestsDirectory(pattern: string, glob: Bun.Glob, directory: string) {
    if (pattern === directory || pattern.startsWith(`${directory}/`)) return true
    return ["file", "file.txt", "file.py", "nested/file", "nested/file.txt", "nested/file.py"].some((probe) =>
      glob.match(`${directory}/${probe}`),
    )
  }

  async function ignored(root: string, files: string[]) {
    const git = Bun.which("git")
    const repository = await fs.stat(path.join(root, ".git")).then(
      () => true,
      () => false,
    )
    if (git && repository && files.length) {
      const proc = Bun.spawn([git, "-C", root, "check-ignore", "--no-index", "-z", "--stdin"], {
        stdin: new Blob([`${files.join("\0")}\0`]),
        stdout: "pipe",
        stderr: "ignore",
      })
      const [output, code] = await Promise.all([new Response(proc.stdout).text(), proc.exited])
      if (code === 0 || code === 1) return new Set(output.split("\0").filter(Boolean))
    }
    const [project, local] = await Promise.all([
      Bun.file(path.join(root, ".gitignore"))
        .text()
        .catch(() => ""),
      Bun.file(path.join(root, ".git", "info", "exclude"))
        .text()
        .catch(() => ""),
    ])
    const matcher = ignore().add(project).add(local)
    return new Set(files.filter((file) => matcher.ignores(file)))
  }

  export async function files(
    root: string,
    patterns: string[],
    label = "Modal",
    options: Pick<StagingOptions, "denied" | "exclude"> = {},
  ) {
    const project = await Filesystem.canonical(root)
    if (!project) throw new Error(`${label} project directory is unavailable: ${root}`)
    const files = new Map<string, Omit<ModalAdapter.File, "sha256"> & { snapshot: ModalUpload.Snapshot }>()
    const found = new Set<string>()
    const excluded = new Set((options.exclude ?? []).map(posix))
    for (const pattern of patterns) {
      if (path.isAbsolute(pattern) || pattern.split(/[\\/]/).includes("..")) {
        throw new Error(`${label} upload pattern must stay inside the project: ${pattern}`)
      }
      const scan = new Bun.Glob(pattern).scan({ cwd: project, dot: true, onlyFiles: true, followSymlinks: true })
      for await (const file of scan) {
        const relative = posix(file)
        if (excluded.has(relative) || internal(relative)) continue
        if (options.denied === "skip" && forbidden(relative)) continue
        found.add(relative)
        if (found.size > ModalUpload.COUNT_LIMIT) {
          throw new Error(`${label} uploads exceed the ${ModalUpload.COUNT_LIMIT}-file approval limit`)
        }
      }
    }
    const excludes = await ignored(project, [...found])
    for (const relative of found) {
      if (excludes.has(relative)) continue
      if (forbidden(relative)) {
        if (options.denied === "skip") continue
        throw new Error(`${label} upload policy denied: ${relative}`)
      }
      const canonical = await Filesystem.canonical(path.resolve(project, relative))
      if (!canonical || !Filesystem.contains(project, canonical)) {
        throw new Error(`${label} upload escaped the project: ${relative}`)
      }
      const resolved = posix(path.relative(project, canonical))
      const canonicalIgnored =
        resolved === relative ? excludes.has(resolved) : (await ignored(project, [resolved])).has(resolved)
      if (canonicalIgnored) continue
      if (forbidden(resolved)) {
        if (options.denied === "skip") continue
        throw new Error(`${label} upload policy denied: ${relative}`)
      }
      if (files.has(canonical)) continue
      const snapshot = await ModalUpload.inspect(canonical, label)
      files.set(canonical, {
        path: resolved,
        canonical,
        size: snapshot.size,
        snapshot,
      })
    }
    const candidates = [...files.values()].toSorted((a, b) => a.path.localeCompare(b.path))
    // An explicit list that matches nothing is a mistake, not a request for an
    // empty sandbox: the job would start and fail on its first open(). The
    // usual cause is a path given from the project root instead of the cwd.
    if (options.denied !== "skip" && patterns.length && !candidates.length) {
      throw new Error(
        `${label} uploads matched no files under the working directory (${patterns.join(", ")}). Upload paths are relative to cwd; name the files as they sit inside it. No compute job was dispatched.`,
      )
    }
    // A pattern with no glob character names one file: that file may be
    // large, and the approval shows it by path, size and hash.
    const named = new Set(patterns.filter((pattern) => !/[*?[\]{}]/.test(pattern)).map(posix))
    const bytes = ModalUpload.validate(candidates, label, { named })
    const result: ModalAdapter.File[] = []
    for (const file of candidates) {
      result.push({
        path: file.path,
        canonical: file.canonical,
        size: file.size,
        sha256: (await ModalUpload.hash(file.canonical, file.snapshot, label)).sha256,
        ...(named.has(file.path) ? { named: true } : {}),
      })
    }
    return { files: result, bytes }
  }

  /**
   * Build a bounded Project-files manifest for copying into Session scratch.
   * Unlike the ordinary upload resolver, this traversal never follows a
   * symbolic link. The returned files have already passed the same ignore,
   * denied-path, regular-file, count, byte, and content-stability checks used
   * by remote compute approval.
   */
  export async function stagingFiles(
    root: string,
    patterns: string[],
    label = "Compute staging",
    options: StagingOptions = {},
  ) {
    const project = await Filesystem.canonical(root)
    if (!project) throw new Error(`${label} project directory is unavailable: ${root}`)
    const globs = uploadPatterns(patterns, label)
    const excluded = new Set((options.exclude ?? []).map(posix))
    const prefix = posix(options.prefix?.trim() || "")
    if (path.posix.isAbsolute(prefix) || prefix.split("/").includes("..")) {
      throw new Error(`${label} prefix must stay inside the project: ${options.prefix}`)
    }

    const found: string[] = []
    const visit = async (directory: string, relative = ""): Promise<void> => {
      const entries = await fs.readdir(directory, { withFileTypes: true })
      for (const entry of entries) {
        const current = relative ? `${relative}/${entry.name}` : entry.name
        // Project snapshots contain ordinary files only. Do not traverse or
        // preserve links, sockets, devices, or other filesystem capabilities.
        if (entry.isSymbolicLink()) {
          const projected = prefix ? `${prefix}/${current}` : current
          if (
            options.denied === "error" &&
            globs.some(({ pattern, glob }) => glob.match(projected) || requestsDirectory(pattern, glob, projected))
          ) {
            throw new Error(`${label} input may not be staged through a symbolic link: ${projected}`)
          }
          continue
        }
        if (entry.isDirectory()) {
          if (forbidden(current) && !leadsToSdk(current)) {
            const projected = prefix ? `${prefix}/${current}` : current
            if (
              options.denied === "error" &&
              globs.some(({ pattern, glob }) => requestsDirectory(pattern, glob, projected))
            ) {
              throw new Error(`${label} upload policy denied: ${projected}`)
            }
            continue
          }
          await visit(path.join(directory, entry.name), current)
          continue
        }
        if (!entry.isFile()) continue
        if (excluded.has(current) || internal(current)) continue
        const projected = prefix ? `${prefix}/${current}` : current
        if (!globs.some(({ glob }) => glob.match(projected))) continue
        if (forbidden(current)) {
          if (options.denied === "error") throw new Error(`${label} upload policy denied: ${projected}`)
          continue
        }
        found.push(current)
      }
    }
    if (globs.length) await visit(project)

    const excludes = await ignored(project, found)
    const selected = found.filter((file) => !excludes.has(file))
    if (selected.length > ModalUpload.COUNT_LIMIT) {
      throw new Error(`${label} uploads exceed the ${ModalUpload.COUNT_LIMIT}-file approval limit`)
    }

    const candidates: Array<Omit<ModalAdapter.File, "sha256"> & { snapshot: ModalUpload.Snapshot }> = []
    for (const relative of selected) {
      const canonical = await Filesystem.canonical(path.resolve(project, relative))
      if (!canonical || !Filesystem.contains(project, canonical)) {
        throw new Error(`${label} upload escaped the project: ${relative}`)
      }
      const snapshot = await ModalUpload.inspect(canonical, label)
      candidates.push({
        path: relative,
        canonical,
        size: snapshot.size,
        snapshot,
      })
    }
    const ordered = candidates.toSorted((a, b) => a.path.localeCompare(b.path))
    // A staged folder is swept, not named: the implicit limit applies to all of it.
    const bytes = ModalUpload.validate(ordered, label, { named: new Set() })
    const files: ModalAdapter.File[] = []
    for (const file of ordered) {
      files.push({
        path: file.path,
        canonical: file.canonical,
        size: file.size,
        sha256: (await ModalUpload.hash(file.canonical, file.snapshot, label)).sha256,
      })
    }
    return { files, bytes }
  }

  export async function prepare(input: Input): Promise<Prepared> {
    const upload = await files(input.cwd, input.uploads, "Modal", {
      denied: input.deniedUploads,
      exclude: input.excludeUploads,
    })
    const value = {
      provider: "modal" as const,
      purpose: input.purpose?.trim() || "Research computation",
      app: input.context.app,
      environment: input.context.environment,
      image: input.image,
      packages: input.packages.toSorted(),
      package_lock: input.packageLock,
      secret_refs: [...new Set(input.secretRefs ?? [])].toSorted(),
      gpu: input.gpu,
      resources: input.resources,
      timeout_minutes: input.timeoutMinutes,
      network: input.context.network,
      command: input.command,
      cwd: input.cwd,
      workspace_cwd: workspaceCwd(input.workspaceCwd),
      uploads: upload.files.map((file) => ({
        path: file.path,
        size: file.size,
        sha256: file.sha256,
        ...(file.named ? { named: true } : {}),
      })),
      upload_bytes: upload.bytes,
      outputs: input.outputs.toSorted(),
      warning: "This run uses your Modal account and may incur charges until it exits, times out, or is cancelled.",
    }
    // The absolute cwd is a per-conversation scratch path. Bind the stable
    // workspace-relative cwd plus reviewed input paths and hashes so exact
    // project/global approvals can carry across isolated conversations.
    const digest = new Bun.CryptoHasher("sha256").update(JSON.stringify({ ...value, cwd: undefined })).digest("hex")
    return { plan: Schema.parse({ digest, ...value }), files: upload.files }
  }
}
