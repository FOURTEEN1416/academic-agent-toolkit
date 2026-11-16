import type { SessionHarness } from "./harness"

export namespace Toolset {
  /** The repair-only tool is executable internally, but is never advertised. */
  export function active(tools: Record<string, unknown>) {
    return Object.keys(tools).filter((name) => name !== "invalid")
  }

  export function previous(
    records: SessionHarness.Entry[],
    input: { messageID: string; profile: string; mode: string },
  ) {
    // Internal compaction/title requests must not replace the active agent's
    // baseline. Retried requests compare against the same preceding assistant.
    const entry = records.findLast(
      (item) => item.messageID !== input.messageID && item.profile === input.profile && item.mode === input.mode,
    )
    return entry?.tools.map((item) => item.name).filter((name) => name !== "invalid")
  }

  function list(names: string[]) {
    const shown: string[] = []
    for (const name of names) {
      if (shown.length === 20 || shown.join(", ").length + name.length > 384) break
      shown.push(name)
    }
    return `${shown.join(", ")}${shown.length < names.length ? ` (${names.length - shown.length} more)` : ""}`
  }

  export function notice(current: string[], previous?: string[]) {
    if (!previous) return
    const before = new Set(previous)
    const after = new Set(current)
    const added = [...after].filter((name) => !before.has(name)).toSorted()
    const removed = [...before].filter((name) => !after.has(name)).toSorted()
    if (!added.length && !removed.length) return
    // The first line is what the transcript shows as the row label, so it
    // names the change rather than announcing that one happened.
    return [
      ...(added.length ? [`Tools added: ${list(added)}.`] : []),
      ...(removed.length ? [`Tools removed: ${list(removed)}.`] : []),
      "Use only the currently advertised tool definitions. This changes availability, not filesystem or execution authority.",
    ].join("\n")
  }
}
