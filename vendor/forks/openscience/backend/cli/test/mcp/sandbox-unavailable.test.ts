import { expect, test } from "bun:test"
import fs from "node:fs"
import path from "node:path"
import { tmpdir } from "../fixture/fixture"
import { spawn } from "../fixture/spawn"

test("a local MCP server is refused, not started, when the sandbox is on and no backend exists", async () => {
  await using tmp = await tmpdir()
  const empty = path.join(tmp.path, "empty-path")
  fs.mkdirSync(empty)
  const marker = path.join(tmp.path, "server-started")
  const server = path.join(tmp.path, "server.mjs")
  await Bun.write(server, `import fs from "node:fs"\nfs.writeFileSync(${JSON.stringify(marker)}, "started")\n`)
  await Bun.write(
    path.join(tmp.path, "openscience.json"),
    JSON.stringify({ mcp: { "local-search": { type: "local", command: [process.execPath, server] } } }),
  )
  const runner = path.join(tmp.path, "refuse.ts")
  await Bun.write(
    runner,
    `
import { MCP } from ${JSON.stringify(new URL("../../src/mcp/index.ts", import.meta.url).href)}
import { Instance } from ${JSON.stringify(new URL("../../src/project/instance.ts", import.meta.url).href)}
import { ProjectTrust } from ${JSON.stringify(new URL("../../src/project/trust.ts", import.meta.url).href)}

const detail = await Instance.provide({
  directory: process.argv[2],
  fn: async () => {
    const trust = await ProjectTrust.status(Instance.project)
    await ProjectTrust.update(Instance.project, { trusted: true, root: trust.root })
    return MCP.inspect("local-search")
  },
})
process.stdout.write(JSON.stringify(detail.status))
process.exit(0)
`,
  )

  // An empty PATH hides sandbox-exec and bwrap, which is the Windows situation.
  const proc = spawn([process.execPath, runner, tmp.path], {
    cwd: tmp.path,
    stdout: "pipe",
    stderr: "pipe",
    env: { PATH: empty },
  })
  const [output, error, exit] = await Promise.all([
    new Response(proc.stdout).text(),
    new Response(proc.stderr).text(),
    proc.exited,
  ])
  expect(exit, error).toBe(0)
  const status = JSON.parse(output)

  expect(status.status).toBe("failed")
  expect(status.error).toContain('OpenScience did not start local MCP server "local-search"')
  expect(status.error).toContain("Fallback behavior")
  expect(status.error).toContain("remote MCP URL")
  expect(status.error).not.toContain("WITHOUT isolation")
  expect(fs.existsSync(marker)).toBe(false)
})
