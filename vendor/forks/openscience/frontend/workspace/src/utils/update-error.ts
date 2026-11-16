function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null
}

export function updateError(value: unknown, status: number) {
  if (!record(value)) return `Update install failed (${status})`
  const data = record(value.data) ? value.data : undefined
  const detail = [value.error, value.message, data?.message].find((item) => typeof item === "string")
  if (typeof detail !== "string") return `Update install failed (${status})`
  return detail.replace(/^Error:\s*/, "").split("\n", 1)[0]
}

/** A refused update, with what the server said is running and whether a
 * restart that pauses agent turns would go through. */
export class UpdateRefused extends Error {
  readonly blockers: string[]
  readonly pausable: boolean
  constructor(message: string, body: unknown) {
    super(message)
    this.name = "UpdateRefused"
    const data = record(body) ? body : undefined
    this.blockers = Array.isArray(data?.blockers)
      ? data.blockers.filter((item): item is string => typeof item === "string")
      : []
    this.pausable = data?.pausable === true
  }
}
