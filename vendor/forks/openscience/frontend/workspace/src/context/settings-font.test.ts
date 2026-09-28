import { describe, expect, test } from "bun:test"
import { monoFontFamily } from "./settings"

describe("configured mono font stacks", () => {
  test("uses locally installed Söhne Mono first and ends with a generic monospace", () => {
    const stack = monoFontFamily(undefined)

    expect(stack).toStartWith('"Söhne Mono", "Sohne Mono"')
    expect(stack).toEndWith("monospace")
  })

  test("keeps the configured family after the Söhne Mono prefix", () => {
    const stack = monoFontFamily("jetbrains-mono")

    expect(stack.indexOf('"Söhne Mono"')).toBe(0)
    expect(stack.indexOf('"Sohne Mono"')).toBeGreaterThan(stack.indexOf('"Söhne Mono"'))
    expect(stack.indexOf('"JetBrains Mono Nerd Font"')).toBeGreaterThan(stack.indexOf('"Sohne Mono"'))
    expect(stack).toEndWith("monospace")
  })
})
