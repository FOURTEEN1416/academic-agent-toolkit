import { afterEach, describe, expect, test } from "bun:test"
import fs from "fs/promises"
import os from "os"
import path from "path"
import { ModalPlan } from "../../src/compute/modal/plan"
import { ModalUpload } from "../../src/compute/modal/upload"

const roots: string[] = []

afterEach(async () => {
  await Promise.all(roots.splice(0).map((root) => fs.rm(root, { recursive: true, force: true })))
})

async function project() {
  const root = await fs.realpath(await fs.mkdtemp(path.join(os.tmpdir(), "openscience-modal-plan-")))
  roots.push(root)
  await fs.mkdir(path.join(root, "src"), { recursive: true })
  await fs.writeFile(path.join(root, "src", "train.py"), "print('ready')\n")
  return root
}

function input(root: string) {
  return {
    purpose: "Fit the approved model and save evaluation metrics.",
    command: "python src/train.py",
    cwd: root,
    image: "python:3.12-slim",
    packages: ["scikit-learn==1.7.1", "numpy==2.3.2"],
    gpu: "T4",
    timeoutMinutes: 10,
    uploads: ["src/**/*.py"],
    outputs: ["outputs/**/*.csv"],
    context: { app: "openscience", network: "none" as const },
  }
}

describe("ModalPlan", () => {
  test("binds the exact files and governed run settings into one approval digest", async () => {
    const root = await project()
    const first = await ModalPlan.prepare(input(root))
    const second = await ModalPlan.prepare(input(root))

    expect(first.plan.digest).toBe(second.plan.digest)
    expect(first.plan.uploads).toEqual([
      {
        path: "src/train.py",
        size: 15,
        sha256: new Bun.CryptoHasher("sha256").update("print('ready')\n").digest("hex"),
      },
    ])
    expect(first.plan.network).toBe("none")
    expect(first.plan.purpose).toBe("Fit the approved model and save evaluation metrics.")
    expect(first.plan.packages).toEqual(["numpy==2.3.2", "scikit-learn==1.7.1"])
    expect(first.plan.warning).toContain("may incur charges")

    await fs.writeFile(path.join(root, "src", "train.py"), "print('changed')\n")
    expect((await ModalPlan.prepare(input(root))).plan.digest).not.toBe(first.plan.digest)
    expect((await ModalPlan.prepare({ ...input(root), packages: ["numpy==2.3.3"] })).plan.digest).not.toBe(
      first.plan.digest,
    )
    expect((await ModalPlan.prepare({ ...input(root), purpose: "Run a different experiment." })).plan.digest).not.toBe(
      first.plan.digest,
    )
  })

  test("accepts a project root reached through a symlink", async () => {
    const root = await project()
    const alias = `${root}-alias`
    roots.push(alias)
    await fs.symlink(root, alias)

    const prepared = await ModalPlan.prepare(input(alias))

    expect(prepared.plan.uploads.map((file) => file.path)).toEqual(["src/train.py"])
  })

  test("keeps exact approval stable across isolated conversation scratch roots", async () => {
    const firstRoot = await project()
    const secondRoot = await project()

    const first = await ModalPlan.prepare(input(firstRoot))
    const second = await ModalPlan.prepare(input(secondRoot))

    expect(first.plan.cwd).not.toBe(second.plan.cwd)
    expect(first.plan.workspace_cwd).toBe(".")
    expect(second.plan.workspace_cwd).toBe(".")
    expect(first.plan.digest).toBe(second.plan.digest)
  })

  test("denies secrets, control directories, and paths outside the project", async () => {
    const root = await project()
    await fs.writeFile(path.join(root, ".env"), "MODAL_TOKEN_SECRET=secret\n")
    await fs.writeFile(path.join(root, ".modal.toml"), "token_secret = 'secret'\n")

    await expect(ModalPlan.prepare({ ...input(root), uploads: [".env"] })).rejects.toThrow("Modal upload policy denied")
    await expect(ModalPlan.prepare({ ...input(root), uploads: [".modal.toml"] })).rejects.toThrow(
      "Modal upload policy denied",
    )
    await expect(ModalPlan.prepare({ ...input(root), uploads: ["../*"] })).rejects.toThrow(
      "must stay inside the project",
    )
  })

  test("default staging skips common credentials, environments, and generated caches", async () => {
    const root = await project()
    const files = [
      [".aws/credentials", "aws_secret_access_key=secret\n"],
      [".kube/config", "token: secret\n"],
      [".venv/lib/python/site.py", "generated\n"],
      [".cache/huggingface/token", "secret\n"],
      [".config/gcloud/application_default_credentials.json", "secret\n"],
      ["node_modules/library/index.js", "generated\n"],
      ["src/__pycache__/train.pyc", "generated\n"],
      [".npmrc", "//registry.example.org/:_authToken=secret\n"],
    ] as const
    await Promise.all(
      files.map(async ([relative, value]) => {
        const target = path.join(root, relative)
        await fs.mkdir(path.dirname(target), { recursive: true })
        await fs.writeFile(target, value)
      }),
    )

    const staged = await ModalPlan.stagingFiles(root, ["**/*"], "Modal staging", { denied: "skip" })

    expect(staged.files.map((file) => file.path)).toEqual(["src/train.py"])
  })

  test("explicit uploads into default-excluded paths still fail closed", async () => {
    const root = await project()
    await fs.mkdir(path.join(root, ".aws"), { recursive: true })
    await fs.writeFile(path.join(root, ".aws", "credentials"), "aws_secret_access_key=secret\n")

    await expect(ModalPlan.prepare({ ...input(root), uploads: [".aws/credentials"] })).rejects.toThrow(
      "Modal upload policy denied: .aws/credentials",
    )
    await expect(
      ModalPlan.stagingFiles(root, [".aws/credentials"], "Modal staging", { denied: "error" }),
    ).rejects.toThrow("Modal staging upload policy denied: .aws")
  })

  test("a symlink alias cannot disguise a denied credential file", async () => {
    const root = await project()
    await fs.writeFile(path.join(root, ".env"), "PRIVATE_TOKEN=secret\n")
    await fs.symlink(path.join(root, ".env"), path.join(root, "src", "settings.py"))

    await expect(ModalPlan.prepare({ ...input(root), uploads: ["src/**/*.py"] })).rejects.toThrow(
      "Modal upload policy denied",
    )
  })

  test("does not upload files excluded by the project's gitignore", async () => {
    const root = await project()
    await fs.writeFile(path.join(root, ".gitignore"), "src/private.py\n")
    await fs.writeFile(path.join(root, "src", "private.py"), "TOKEN = 'private'\n")

    const prepared = await ModalPlan.prepare({ ...input(root), uploads: ["src/**/*.py"] })

    expect(prepared.plan.uploads.map((file) => file.path)).toEqual(["src/train.py"])
  })

  test("honors nested gitignore files", async () => {
    const root = await project()
    const git = Bun.spawn(["git", "init", "-q"], { cwd: root, stdout: "ignore", stderr: "pipe" })
    if ((await git.exited) !== 0) throw new Error(await new Response(git.stderr).text())
    await fs.writeFile(path.join(root, "src", ".gitignore"), "private.py\n")
    await fs.writeFile(path.join(root, "src", "private.py"), "TOKEN = 'private'\n")

    const prepared = await ModalPlan.prepare({ ...input(root), uploads: ["src/**/*.py"] })

    expect(prepared.plan.uploads.map((file) => file.path)).toEqual(["src/train.py"])
  })

  test("a swept oversized input is rejected before it is read; a file named literally may be large", async () => {
    const root = await project()
    const large = path.join(root, "src", "large.bin")
    await fs.writeFile(large, "")
    await fs.truncate(large, ModalUpload.LIMIT + 1)
    {
      const reads: string[] = []
      using guard = ModalUpload.testing({
        read(file) {
          reads.push(file)
        },
      })
      // A glob sweeps the file up: the person never saw its size listed.
      await expect(ModalPlan.prepare({ ...input(root), uploads: ["src/*.bin"] })).rejects.toThrow(
        "Name it in uploads explicitly (no glob) to send a file up to 2 GiB",
      )
      expect(reads).toEqual([])
    }
    // Named by path, the checkpoint travels: the plan lists it as named, with
    // its size and hash, and the approval is of that file.
    const prepared = await ModalPlan.prepare({ ...input(root), uploads: ["src/large.bin", "src/*.py"] })
    expect(prepared.plan.uploads.find((file) => file.path === "src/large.bin")).toMatchObject({
      size: ModalUpload.LIMIT + 1,
      named: true,
    })
    expect(prepared.plan.uploads.find((file) => file.path === "src/train.py")?.named).toBeUndefined()
    expect(prepared.plan.upload_bytes).toBeGreaterThan(ModalUpload.LIMIT)
    // The hard ceiling for one file still holds, before any read.
    await fs.truncate(large, ModalUpload.NAMED_LIMIT + 1)
    const reads: string[] = []
    using guard = ModalUpload.testing({
      read(file) {
        reads.push(file)
      },
    })
    await expect(ModalPlan.prepare({ ...input(root), uploads: ["src/large.bin"] })).rejects.toThrow(
      "exceeds the 2 GiB limit for one file",
    )
    expect(reads).toEqual([])
  })

  test("rejects an oversized aggregate before hashing any sparse input", async () => {
    const root = await project()
    const size = 60 * 1024 * 1024
    await Promise.all([
      fs.writeFile(path.join(root, "src", "first.bin"), ""),
      fs.writeFile(path.join(root, "src", "second.bin"), ""),
    ])
    await Promise.all([
      fs.truncate(path.join(root, "src", "first.bin"), size),
      fs.truncate(path.join(root, "src", "second.bin"), size),
    ])
    const reads: string[] = []
    using guard = ModalUpload.testing({
      read(file) {
        reads.push(file)
      },
    })

    await expect(ModalPlan.prepare({ ...input(root), uploads: ["src/*.bin"] })).rejects.toThrow(
      "uploads exceed the 100 MiB approval limit",
    )
    expect(reads).toEqual([])
  })

  test("deduplicates overlapping patterns and canonical symlink aliases", async () => {
    const root = await project()
    await fs.symlink(path.join(root, "src", "train.py"), path.join(root, "src", "alias.py"))
    const reads: string[] = []
    using guard = ModalUpload.testing({
      read(file) {
        reads.push(file)
      },
    })

    const prepared = await ModalPlan.prepare({
      ...input(root),
      uploads: ["src/train.py", "src/**/*.py", "src/alias.py"],
    })

    expect(prepared.plan.uploads.map((file) => file.path)).toEqual(["src/train.py"])
    expect(prepared.plan.upload_bytes).toBe(15)
    expect(reads).toEqual([path.join(root, "src", "train.py")])
  })

  test("the study SDK under .openscience/sdk rides along while the rest of .openscience stays denied", async () => {
    const root = await project()
    await fs.mkdir(path.join(root, ".openscience", "sdk", "openscience_track"), { recursive: true })
    await fs.writeFile(path.join(root, ".openscience", "sdk", "openscience_track", "__init__.py"), "RUN = 1\n")
    await fs.mkdir(path.join(root, ".openscience", "state"), { recursive: true })
    await fs.writeFile(path.join(root, ".openscience", "state", "cursor.json"), "{}\n")

    // The default sweep of the cwd carries the SDK and skips the state.
    const swept = await ModalPlan.prepare({ ...input(root), uploads: ["**/*"], deniedUploads: "skip" })
    expect(swept.plan.uploads.map((file) => file.path)).toEqual([
      ".openscience/sdk/openscience_track/__init__.py",
      "src/train.py",
    ])
    // An explicit list may name the SDK, and still not the state.
    const explicit = await ModalPlan.prepare({ ...input(root), uploads: ["src/train.py", ".openscience/sdk/**/*"] })
    expect(explicit.plan.uploads.map((file) => file.path)).toEqual([
      ".openscience/sdk/openscience_track/__init__.py",
      "src/train.py",
    ])
    await expect(ModalPlan.prepare({ ...input(root), uploads: [".openscience/state/cursor.json"] })).rejects.toThrow(
      "Modal upload policy denied",
    )
  })

  test("excluded files stay out however the patterns match, and an explicit list that matches nothing is refused", async () => {
    const root = await project()
    await fs.writeFile(path.join(root, "ideas.md"), "# ideas\n")
    await fs.writeFile(path.join(root, "results.tsv"), "run\tmetric\n")
    const prepared = await ModalPlan.prepare({
      ...input(root),
      uploads: ["**/*"],
      deniedUploads: "skip",
      excludeUploads: ["ideas.md", "results.tsv"],
    })
    expect(prepared.plan.uploads.map((file) => file.path)).toEqual(["src/train.py"])
    // The ledger the study rewrites while a job waits for approval must not
    // move the approved digest.
    await fs.writeFile(path.join(root, "ideas.md"), "# ideas, revised\n")
    const again = await ModalPlan.prepare({
      ...input(root),
      uploads: ["**/*"],
      deniedUploads: "skip",
      excludeUploads: ["ideas.md", "results.tsv"],
    })
    expect(again.plan.digest).toBe(prepared.plan.digest)
    // Paths given from the project root for a cwd below it match nothing here;
    // the job would only fail on its first open(), so it is not dispatched.
    await expect(ModalPlan.prepare({ ...input(root), uploads: ["autoresearch_churn/train.py"] })).rejects.toThrow(
      /matched no files under the working directory.*relative to cwd/,
    )
  })
})
