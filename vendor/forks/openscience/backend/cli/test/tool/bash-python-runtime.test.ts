import { expect, test } from "bun:test"
import fs from "node:fs/promises"
import path from "node:path"
import { BashTool } from "../../src/tool/bash"
import { PythonTool } from "../../src/tool/notebook"
import { Instance } from "../../src/project/instance"
import { SessionFilesystem } from "../../src/session/filesystem"
import { KernelEnvironmentMutation } from "../../src/science/kernel/environment-mutation"
import { executionSession, tmpdir } from "../fixture/fixture"

test("Bash uses the kernel project package overlay without ambient import paths or control-plane credentials", async () => {
  await using tmp = await tmpdir()
  await using ambient = await tmpdir()
  const prior = { PYTHONPATH: process.env.PYTHONPATH, MODAL_TOKEN_ID: process.env.MODAL_TOKEN_ID }
  try {
    process.env.PYTHONPATH = ambient.path
    process.env.MODAL_TOKEN_ID = "ak-isolated-runtime-boundary-test"
    await Bun.write(path.join(ambient.path, "unapproved_import.py"), "value = 'unapproved'\n")
    await Instance.provide({
      directory: tmp.path,
      fn: async () => {
        const session = await executionSession()
        const runtime = await KernelEnvironmentMutation.pythonSubprocessRuntime()
        const module = `approved_${crypto.randomUUID().replaceAll("-", "")}`
        const filepath = path.join(runtime.env.PYTHONPATH, `${module}.py`)
        await Bun.write(filepath, "value = 'approved-project-package'\n")
        try {
          const context = {
            sessionID: session.id,
            messageID: "msg_runtime",
            callID: "call_runtime",
            agent: "research",
            abort: AbortSignal.any([]),
            messages: [],
            metadata() {},
            async ask() {},
          }
          const code = `import ${module}, importlib.util, os; print(${module}.value); assert importlib.util.find_spec("unapproved_import") is None; assert os.getenv("MODAL_TOKEN_ID") is None`
          const result = await (
            await BashTool.init()
          ).execute({ command: `python3 -c '${code}'`, description: "Import approved project package" }, context)
          expect(result.metadata.exit, result.output).toBe(0)
          expect(result.output).toContain("approved-project-package")
          expect(result.metadata.execution_environment).toEqual({
            target: "local",
            cwd: await SessionFilesystem.workspace(session.id),
            profile: "python",
            python: { role: "selected_default", executable: runtime.binary },
          })
          // Arbitrary shell commands receive a selected default, not a claim
          // that Python ran or that its version was measured for this command.
          const shell = await (
            await BashTool.init()
          ).execute({ command: "printf ordinary-shell", description: "Run a non-Python command" }, context)
          expect(shell.metadata.exit, shell.output).toBe(0)
          expect(shell.metadata.execution_environment).toEqual(result.metadata.execution_environment)
          expect(shell.metadata.execution_environment.python?.version).toBeUndefined()
          // Kernels already support this package location; prove the repaired
          // shell agrees using the actual canonical Python tool too.
          const kernel = await (
            await PythonTool.init()
          ).execute(
            {
              action: "execute",
              code: `import ${module}; print(${module}.value)`,
              title: "Read same package",
              source: filepath,
              timeout: 10_000,
            },
            context,
          )
          expect(kernel.metadata.ok, kernel.output).toBe(true)
          expect(kernel.output).toContain("approved-project-package")
        } finally {
          await fs.rm(filepath, { force: true })
        }
      },
    })
  } finally {
    for (const [key, value] of Object.entries(prior)) {
      if (value === undefined) delete process.env[key]
      else process.env[key] = value
    }
  }
})
