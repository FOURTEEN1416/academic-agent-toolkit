import { afterEach, expect, spyOn, test } from "bun:test"
import { resolveNetworkOptions, type NetworkOptions } from "../../src/cli/network"
import { Config } from "../../src/config/config"

const original = process.argv

afterEach(() => {
  process.argv = original
})

const args = (port: number, cors?: string | string[]): NetworkOptions => ({ port, cors: cors as string[] })

test("a port passed as --port=N beats the configured port", async () => {
  process.argv = ["node", "openscience", "--port=5555"]
  const config = spyOn(Config, "global").mockResolvedValue({ server: { port: 1234 } } as never)
  // yargs has already parsed the flag, so the argument says 5555 while the
  // detection that decides whether to prefer it only looks for the bare word.
  const resolved = await resolveNetworkOptions(args(5555))
  expect(resolved.port).toBe(5555)
  config.mockRestore()
})

test("a port passed as --port N beats the configured port", async () => {
  process.argv = ["node", "openscience", "--port", "5555"]
  const config = spyOn(Config, "global").mockResolvedValue({ server: { port: 1234 } } as never)
  const resolved = await resolveNetworkOptions(args(5555))
  expect(resolved.port).toBe(5555)
  config.mockRestore()
})

test("the configured port applies when no port was passed", async () => {
  process.argv = ["node", "openscience"]
  const config = spyOn(Config, "global").mockResolvedValue({ server: { port: 1234 } } as never)
  const resolved = await resolveNetworkOptions(args(0))
  expect(resolved.port).toBe(1234)
  config.mockRestore()
})

test("the parsed port applies when neither the command line nor the config sets one", async () => {
  process.argv = ["node", "openscience"]
  const config = spyOn(Config, "global").mockResolvedValue({} as never)
  const resolved = await resolveNetworkOptions(args(5555))
  expect(resolved.port).toBe(5555)
  config.mockRestore()
})

test("cors origins from the config and the command line are combined", async () => {
  process.argv = ["node", "openscience", "--port=5555"]
  const config = spyOn(Config, "global").mockResolvedValue({ server: { cors: ["https://from-config"] } } as never)
  const resolved = await resolveNetworkOptions(args(5555, "https://from-args"))
  expect(resolved.cors).toEqual(["https://from-config", "https://from-args"])
  config.mockRestore()
})
