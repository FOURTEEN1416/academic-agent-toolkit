import { afterAll, afterEach, expect, test } from "bun:test"
import { createComponent, createSignal } from "solid-js"
import { mkdtemp, rm } from "node:fs/promises"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { fileURLToPath, pathToFileURL } from "node:url"

const file = fileURLToPath(new URL("./session-sidebar-action.tsx", import.meta.url))
const cleanups: Array<() => void> = []
const server = fileURLToPath(import.meta.resolve("solid-js/web"))
const browser = server.replace(/server\.js$/, "web.js")
const hyper = fileURLToPath(import.meta.resolve("solid-js/h"))
const source = (await Bun.file(hyper).text()).replace("from 'solid-js/web';", `from '${pathToFileURL(browser).href}';`)
const temp = await mkdtemp(join(tmpdir(), "openscience-session-rail-"))
const module = join(temp, "h.mjs")
await Bun.write(module, source)
const h = (await import(pathToFileURL(module).href)).default
const render = (await import(browser)).render
Object.assign(globalThis, { React: { createElement: h, Fragment: h.Fragment } })

afterAll(() => rm(temp, { recursive: true, force: true }))

afterEach(() => {
  cleanups.splice(0).forEach((cleanup) => cleanup())
  document.body.replaceChildren()
})

const load = async () => {
  const exists = await Bun.file(file).exists()
  expect(exists).toBe(true)
  if (!exists) return
  return import("./session-sidebar-action")
}

test("SidebarAction invokes the current callback supplied by its parent", async () => {
  const subject = await load()
  if (!subject) return
  const calls: string[] = []
  const [action, setAction] = createSignal(() => calls.push("initial"))
  const host = document.createElement("div")
  document.body.append(host)
  cleanups.push(
    render(
      () =>
        createComponent(subject.SidebarAction, {
          label: "Files",
          detail: "Project files",
          ariaLabel: "Open project files",
          get onClick() {
            return action()
          },
          children: "F",
        }),
      host,
    ),
  )

  setAction(() => () => calls.push("current"))
  host.querySelector("button")?.click()

  expect(calls).toEqual(["current"])
})
