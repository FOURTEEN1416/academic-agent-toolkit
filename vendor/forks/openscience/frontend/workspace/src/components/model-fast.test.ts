import { describe, expect, test } from "bun:test"
import { exactRouteFastMode, routeModelBase } from "./model-fast"

describe("exact-route fast mode", () => {
  test("is absent when no route of the model advertises fast", () => {
    const selected = { id: "gemini-3.7-flash", modes: { standard: {} }, provider: { id: "google" } }
    expect(exactRouteFastMode(selected, "standard", [selected])).toBeUndefined()
    expect(exactRouteFastMode(undefined, "standard")).toBeUndefined()
  })

  test("is offered by the exact route that advertises it", () => {
    const route = { id: "gpt-5.6-sol", modes: { standard: {}, fast: {} }, provider: { id: "openai", name: "OpenAI" } }
    expect(exactRouteFastMode(route, "fast")).toEqual({ active: true, offered: true })
    expect(exactRouteFastMode(route, "standard")).toEqual({ active: false, offered: true })
  })

  test("a subscription route says the tier is included", () => {
    const codex = { id: "gpt-5.6-sol", modes: { fast: {} }, provider: { id: "openai-codex", name: "OpenAI (Codex)" } }
    expect(exactRouteFastMode(codex, "standard")).toEqual({
      active: false,
      offered: true,
      note: "Included in your ChatGPT subscription.",
    })
  })

  test("a route without the tier names the routes of the same model that have it", () => {
    const ace = { id: "anthropic/claude-opus-5", modes: {}, provider: { id: "openrouter", name: "Ace" } }
    const key = { id: "claude-opus-5", modes: { fast: {} }, provider: { id: "anthropic", name: "Anthropic" } }
    const other = { id: "claude-sonnet-5", modes: { fast: {} }, provider: { id: "anthropic", name: "Anthropic" } }
    expect(exactRouteFastMode(ace, "standard", [ace, key, other])).toEqual({
      active: false,
      offered: false,
      note: "Not offered on this route. Available through Anthropic.",
    })
    expect(routeModelBase("openai/gpt-5.6-sol")).toBe("gpt-5.6-sol")
    expect(routeModelBase("gpt-5.6-sol")).toBe("gpt-5.6-sol")
  })
})
