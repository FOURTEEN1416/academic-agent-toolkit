import { expect, test } from "bun:test"
import { escapeHtml, htmlResponse } from "../../src/util/html"

test("escapeHtml escapes active HTML payloads", () => {
  expect(escapeHtml(`<img src=x onerror="alert(1)">`)).toBe("&lt;img src=x onerror=&quot;alert(1)&quot;&gt;")
})

test("htmlResponse blocks script execution with CSP", () => {
  const res = htmlResponse("<p>hello</p>")
  expect(res.headers.get("Content-Type")).toBe("text/html; charset=utf-8")
  expect(res.headers.get("Content-Security-Policy")).toContain("script-src 'none'")
})
