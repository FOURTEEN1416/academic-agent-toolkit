import { describe, expect, test } from "bun:test"
import { pick, shapeJson } from "../../src/tool/webfetch"

const pypi = {
  info: { name: "modal", version: "1.5.5", requires_python: ">=3.9" },
  releases: Object.fromEntries(
    Array.from({ length: 400 }, (_, index) => [
      `1.${index}.0`,
      [{ filename: `modal-1.${index}.0.whl`, size: 1_000_000 + index, digests: { sha256: "0".repeat(64) } }],
    ]),
  ),
  urls: [{ filename: "modal-1.5.5.whl" }, { filename: "modal-1.5.5.tar.gz" }],
}

describe("webfetch JSON shaping", () => {
  test("pick reads dotted keys, indexes and the last element", () => {
    expect(pick(pypi, "info.version")).toBe("1.5.5")
    expect(pick(pypi, "urls[-1].filename")).toBe("modal-1.5.5.tar.gz")
    expect(pick(pypi, "urls[0].filename")).toBe("modal-1.5.5.whl")
    expect(pick(pypi, "info.missing.deeper")).toBeUndefined()
    expect(pick(pypi, "urls.filename")).toBeUndefined()
  })

  test("a selector of only separators names no path", () => {
    // The tokenizer matches neither a key nor an index, so the walk has no
    // step to take. Returning the document would make shapeJson report a
    // narrow selection that never happened.
    expect(pick(pypi, ".")).toBeUndefined()
    expect(pick(pypi, "..")).toBeUndefined()
    expect(pick(pypi, "[")).toBeUndefined()
    const shaped = shapeJson(JSON.stringify(pypi), ["."])!
    expect(JSON.parse(shaped.output)).toEqual({})
    expect(shaped.note).toContain("not found: .")
  })

  test("a selection keeps only the asked paths and names the ones not found", () => {
    const content = JSON.stringify(pypi)
    const shaped = shapeJson(content, ["info.version", "info.requires_python", "info.summary"])!
    expect(JSON.parse(shaped.output)).toEqual({
      "info.version": "1.5.5",
      "info.requires_python": ">=3.9",
    })
    expect(shaped.note).toContain("selected 3 paths")
    expect(shaped.note).toContain("not found: info.summary")
    expect(shaped.output.length).toBeLessThan(200)
  })

  test("an unselected registry document past the inline cap is cut with its keys and the way to select", () => {
    const content = JSON.stringify(pypi)
    expect(content.length).toBeGreaterThan(40_000)
    const shaped = shapeJson(content, undefined)!
    expect(shaped.output.length).toBeLessThan(41_000)
    expect(shaped.output).toContain("an object with keys info, releases, urls")
    expect(shaped.output).toContain('Call again with select, e.g. ["info.version"]')
    // A small document passes through untouched.
    expect(shapeJson(JSON.stringify({ ok: true }), undefined)).toBeUndefined()
    // Not JSON at all: nothing to shape.
    expect(shapeJson("<html></html>", ["info"])).toBeUndefined()
  })
})
