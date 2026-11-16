import type { Message, Part, Session } from "@synsci/sdk/v2"

/** Session titles retain history; a resumed worker's header describes its latest assignment. */
export function delegatedAssignment(
  session: Pick<Session, "id" | "parentID"> | undefined,
  messages: readonly Message[],
  parts: Record<string, Part[]>,
) {
  if (!session?.parentID) return
  const calls = messages
    .filter((message) => message.role === "assistant" && message.sessionID === session.parentID)
    .flatMap((message) => parts[message.id] ?? [])
    .filter(
      (part) =>
        part.type === "tool" &&
        part.tool === "task" &&
        "metadata" in part.state &&
        part.state.metadata?.sessionId === session.id,
    )
    .toSorted((a, b) => a.id.localeCompare(b.id))
  const latest = calls.at(-1)
  if (latest?.type !== "tool") return
  const input = latest.state.input
  const description = typeof input.description === "string" ? input.description.trim() : ""
  const phase = typeof input.subagent_type === "string" ? input.subagent_type.trim() : ""
  return description ? { description, phase } : undefined
}
