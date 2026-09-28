const loopback = new Set(["localhost", "127.0.0.1", "::1", "[::1]"])

export function terminalEndpointAvailable(value: string, origin?: string) {
  const base = origin ?? (typeof location === "object" ? location.origin : undefined)
  if (URL.canParse(value)) {
    return loopback.has(new URL(value).hostname)
  }
  if (!base || !URL.canParse(base) || !URL.canParse(value, base)) return false
  return loopback.has(new URL(value, base).hostname)
}
