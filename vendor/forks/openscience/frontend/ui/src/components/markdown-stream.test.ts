import { expect, test } from "bun:test"
import { parseMarkdown } from "../context/marked"
import { reconcileMarkdown, sanitize } from "./markdown"

const labels = { copy: "Copy", copied: "Copied" }

async function stream(text: string, step: number) {
  const container = document.createElement("div")
  for (let end = step; end < text.length + step; end += step) {
    const next = document.createElement("div")
    next.innerHTML = sanitize(await parseMarkdown(text.slice(0, end)))
    reconcileMarkdown(container, next, labels)
  }
  return container
}

test("a streamed message ends with exactly its code blocks, framed once each, in order", async () => {
  const text = await Bun.file(new URL("./fixtures/streamed-audit.md", import.meta.url)).text()
  const container = await stream(text, 37)
  const blocks = Array.from(container.querySelectorAll('[data-component="markdown-code"]'))
  expect(blocks.map((block) => block.querySelector("pre")?.textContent?.trim())).toEqual([
    "Modal input changed after approval",
    "Modal staging input exceeds the 100 MiB approval limit",
    "Tool execution aborted",
    "oof_accuracy\noof_average_precision\nmean_fold_accuracy\nmean_fold_average_precision",
  ])
  // Every frame has one pre and one copy button; no bare pre survives.
  for (const block of blocks) {
    expect(block.querySelectorAll("pre")).toHaveLength(1)
    expect(block.querySelectorAll('[data-slot="markdown-copy-button"]')).toHaveLength(1)
  }
  expect(container.querySelectorAll("pre")).toHaveLength(4)
  expect((container.textContent ?? "").split("Modal input changed after approval")).toHaveLength(2)
})

test("a copied state survives the next streamed update of the same block", async () => {
  const container = await stream("Before\n\n```text\nalpha\n```\n\nafter", 6)
  const button = container.querySelector('[data-slot="markdown-copy-button"]')!
  button.setAttribute("data-copied", "true")
  const next = document.createElement("div")
  next.innerHTML = sanitize(await parseMarkdown("Before\n\n```text\nalpha\n```\n\nafter, and more"))
  reconcileMarkdown(container, next, labels)
  expect(container.querySelector('[data-slot="markdown-copy-button"]')?.getAttribute("data-copied")).toBe("true")
  expect(container.querySelectorAll("pre")).toHaveLength(1)
})
