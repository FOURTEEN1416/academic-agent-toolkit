import type { Message, Part, UserMessage } from "@synsci/sdk/v2/client"

/**
 * A user message the runtime wrote to keep a turn going: a harness or loop
 * continuation, a background worker's completion carrying the `<task>`
 * envelope, or the carrier of a compaction that fired by itself mid-turn.
 * Nobody typed it, so it opens no turn of its own; the work that answers it
 * belongs to the turn the user actually started. A manual `/compact` is the
 * user's own action and draws its own boundary, and so is a shell-mode
 * command, whose synthetic text is the user's own action.
 */
export function isContinuationCarrier(message: Message, parts: readonly Part[] | undefined): boolean {
  if (message.role !== "user") return false
  const internal = (message as UserMessage).internal
  if (internal?.type === "continuation") return true
  if (internal?.type === "compaction") return internal.auto === true
  if (!parts?.length) return false
  const texts = parts.filter((part): part is Extract<Part, { type: "text" }> => part.type === "text")
  return (
    texts.length === parts.length &&
    texts.every((part) => part.synthetic) &&
    texts.some((part) => /^\s*<task\b/.test(part.text) || wakeLabel(part) !== undefined)
  )
}

/** Sessions written before wakes carried a marker still hold compute-job
 * reports in this exact wording. */
const LEGACY_COMPUTE_WAKE = /^Compute job \S+ (\((.*)\) ended with status (\w+)\.|could not be watched)/

/** The one line a runtime report (a compute job ending, a study update) shows
 * in the trace, or undefined for text that is not such a report. */
export function wakeLabel(part: Extract<Part, { type: "text" }>): string | undefined {
  if (!part.synthetic) return
  const marker = part.metadata?.["openscience.wake"] as { label?: unknown } | undefined
  if (typeof marker?.label === "string") return marker.label
  const legacy = LEGACY_COMPUTE_WAKE.exec(part.text)
  if (!legacy) return
  return legacy[2] ? `Compute job ${legacy[2]} ${legacy[3]}` : part.text.split(/(?<=\.)\s/)[0]
}

/** The user message that opened the turn a message belongs to: itself for a
 * real request, the nearest earlier real request for a carrier. */
export function turnOpener(
  messages: readonly Message[],
  index: number,
  parts: (id: string) => readonly Part[] | undefined,
): Message | undefined {
  for (let i = index; i >= 0; i--) {
    const message = messages[i]
    if (!message || message.role !== "user") continue
    if (!isContinuationCarrier(message, parts(message.id))) return message
  }
  return undefined
}
