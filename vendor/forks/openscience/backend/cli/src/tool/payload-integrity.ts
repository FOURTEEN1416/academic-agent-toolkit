import type { MessageV2 } from "../session/message-v2"

export namespace PayloadIntegrity {
  export const MARKER = /…\[\+\d+ chars\]/u
  const LEGACY_LIMIT = 200

  export function hasMarker(value: string) {
    return MARKER.test(value)
  }

  /** Reconstruct an older release's lossy history representation, never an
   * executable argument. New history retains the authoritative input. */
  export function legacyPreview(value: string) {
    if (value.length <= LEGACY_LIMIT) return value
    return value.slice(0, LEGACY_LIMIT) + `…[+${value.length - LEGACY_LIMIT} chars]`
  }

  function occurrences(value: string, needle: string) {
    return value.split(needle).length - 1
  }

  export function assert(input: { content: string; before: string; messages: MessageV2.WithParts[] }) {
    if (!hasMarker(input.content)) return
    for (const message of input.messages) {
      for (const part of message.parts) {
        if (part.type !== "tool" || part.state.status !== "completed") continue
        for (const [field, value] of Object.entries(part.state.input)) {
          if (typeof value !== "string" || value.length <= LEGACY_LIMIT) continue
          const preview = legacyPreview(value)
          if (!input.content.includes(preview)) continue
          // Literal examples already present in a file may be retained or
          // removed. A matching marker alone is not evidence of truncation.
          if (occurrences(input.content, preview) <= occurrences(input.before, preview)) continue
          throw new Error(
            `Refusing a shortened historical argument from ${part.tool} call ${part.callID} (${field}). ` +
              "No action was taken. Recover the complete argument or read the source file; " +
              "OpenScience's …[+N chars] history previews are not complete input.",
          )
        }
      }
    }
  }
}
