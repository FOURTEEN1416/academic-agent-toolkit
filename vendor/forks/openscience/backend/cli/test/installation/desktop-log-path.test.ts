import { expect, test } from "bun:test"
import { existsSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs"
import os from "node:os"
import path from "node:path"
import { KEPT_RUNS, logsDirectory, rotateLogs } from "../../../../frontend/desktop/src/log-path.mjs"

const userData = path.join(path.sep, "scratch", "os-dev")

test("an installed app started normally keeps the platform's logs directory", () => {
  expect(logsDirectory({ packaged: true, relocated: false, userData })).toBeUndefined()
})

test("a shell run from source keeps its logs with its own data", () => {
  expect(logsDirectory({ packaged: false, relocated: false, userData })).toBe(path.join(userData, "logs"))
  expect(logsDirectory({ packaged: false, relocated: true, userData })).toBe(path.join(userData, "logs"))
})

test("a launch given its own user data directory does not write beside the installed app's log", () => {
  expect(logsDirectory({ packaged: true, relocated: true, userData })).toBe(path.join(userData, "logs"))
})

test("each start keeps the earlier runs' logs, newest first, and drops the oldest past the limit", () => {
  const logs = mkdtempSync(path.join(os.tmpdir(), "openscience-log-rotation-"))
  const output = path.join(logs, "openscience-sidecar.log")
  const prev = (index: number) =>
    path.join(logs, index === 1 ? "openscience-sidecar.prev.log" : `openscience-sidecar.prev.${index}.log`)
  // A first start has nothing to rotate.
  rotateLogs(output)
  expect(existsSync(prev(1))).toBe(false)
  for (let run = 1; run <= KEPT_RUNS + 2; run++) {
    rotateLogs(output)
    writeFileSync(output, `run ${run}`)
  }
  rotateLogs(output)
  const last = KEPT_RUNS + 2
  for (let index = 1; index <= KEPT_RUNS; index++)
    expect(readFileSync(prev(index), "utf8")).toBe(`run ${last - index + 1}`)
  expect(existsSync(prev(KEPT_RUNS + 1))).toBe(false)
  expect(existsSync(output)).toBe(false)
})
