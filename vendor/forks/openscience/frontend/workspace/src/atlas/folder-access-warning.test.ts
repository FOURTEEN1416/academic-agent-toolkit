import { describe, expect, test } from "bun:test"

const view = await Bun.file(new URL("./FdaBanner.tsx", import.meta.url)).text()
const style = await Bun.file(new URL("./FdaBanner.css", import.meta.url)).text()

describe("folder access warning", () => {
  test("does not expose a raw probe failure or assume an installation path", () => {
    expect(view).not.toContain("/opt/homebrew")
    expect(view).not.toContain("props.reason")
    expect(view).toContain("terminal or app that started this server")
    expect(view).toContain("which openscience")
  })

  test("uses a clear label and a compact responsive recovery dialog", () => {
    expect(view).toContain("Folder access")
    expect(view).not.toContain(">FDA<")
    expect(view).toContain('class="folder-access-dialog"')
    expect(view).toContain("fit")
    expect(view).toContain("transition")
    expect(style).toContain("width: min(100%, 30rem)")
    expect(style).toContain("@media (max-width: 34rem)")
    expect(style).toContain(":focus-visible")
  })
})
