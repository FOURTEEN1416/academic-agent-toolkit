import { describe, expect, test } from "bun:test"
import { uninstallDirectories } from "../../src/cli/cmd/uninstall"

const kept = (args: Parameters<typeof uninstallDirectories>[0]) =>
  Object.fromEntries(uninstallDirectories(args).map((entry) => [entry.label, entry.keep]))

describe("uninstall retention", () => {
  test("keeps configuration and user data by default", () => {
    expect(kept({ purge: false })).toEqual({
      Data: true,
      Cache: false,
      Config: true,
      State: false,
    })
  })

  test("purge explicitly removes configuration and user data", () => {
    expect(kept({ purge: true })).toEqual({
      Data: false,
      Cache: false,
      Config: false,
      State: false,
    })
  })

  test("retention flags can preserve selected roots during a purge", () => {
    expect(kept({ purge: true, keepData: true })).toEqual({
      Data: true,
      Cache: false,
      Config: false,
      State: false,
    })
    expect(kept({ purge: true, keepConfig: true })).toEqual({
      Data: false,
      Cache: false,
      Config: true,
      State: false,
    })
  })
})
