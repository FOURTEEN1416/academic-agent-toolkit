import { describe, expect, test } from "bun:test"
import { readFileSync } from "node:fs"
import { fileURLToPath } from "node:url"
import { iconDefinitions, iconSpecs } from "./iconoir-registry"

const read = (name: string) => readFileSync(fileURLToPath(new URL(name, import.meta.url)), "utf8")

describe("shared icon system", () => {
  test("covers the stable public API with distinct semantic glyphs from one pack", () => {
    expect(Object.keys(iconSpecs)).toHaveLength(114)
    const sources = Object.values(iconSpecs).map((entry) => entry.source)
    expect(new Set(sources).size).toBe(107)
    // Every glyph comes from Lucide except the few with no equivalent there.
    const fallback = sources.filter((source) => !source.startsWith("lucide/"))
    expect(fallback.sort()).toEqual(["discord", "pin-solid", "square", "star-solid"])
    expect(iconSpecs.models.source).toBe("lucide/box")
    expect(iconSpecs.providers.source).toBe("lucide/key-round")
    expect(iconSpecs.task.source).toBe("lucide/list-todo")
    expect(iconSpecs.split.source).toBe("lucide/columns-2")
    expect(iconSpecs.network.source).toBe("lucide/network")
    expect(iconSpecs.artifact.source).toBe("lucide/file-chart-column")
    expect(iconSpecs.file.source).toBe("lucide/file")
    expect(iconSpecs["folder-tree"].source).toBe("lucide/folder-tree")
    const concepts = ["models", "providers", "task", "split", "network", "artifact", "file", "folder-tree"] as const
    expect(new Set(concepts.map((name) => iconSpecs[name].source)).size).toBe(concepts.length)
  })

  test("Lucide bodies restore the stroke the root element carried and leave the width to CSS", () => {
    const definition = iconDefinitions["chevron-down"]
    expect(definition.body.startsWith('<g fill="none" stroke="currentColor"')).toBe(true)
    expect(definition.body).not.toContain("stroke-width")
    expect(definition.body).not.toContain("<!--")
  })

  test("extracts trusted local SVG bodies without nesting or remote loading", () => {
    for (const definition of Object.values(iconDefinitions)) {
      expect(definition.body.length).toBeGreaterThan(0)
      expect(definition.body).not.toContain("<svg")
      expect(definition.body).not.toContain("http://")
      expect(definition.body).not.toContain("https://")
    }
  })
})
