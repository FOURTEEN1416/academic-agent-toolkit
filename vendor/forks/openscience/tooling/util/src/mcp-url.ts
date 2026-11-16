const LOOPBACK = new Set(["localhost", "127.0.0.1", "[::1]", "::1"])

// A query parameter is a credential when one of its words (split on
// punctuation and camelCase) or its whole name without separators is listed.
// Matching words rather than substrings keeps `max_tokens`, `author` and
// `design` usable while `api_key`, `apiKey`, `X-Api-Key` and `accessToken`
// are refused.
const CREDENTIAL = new Set([
  "key",
  "apikey",
  "accesskey",
  "secretkey",
  "privatekey",
  "token",
  "accesstoken",
  "authtoken",
  "apitoken",
  "idtoken",
  "refreshtoken",
  "sessiontoken",
  "secret",
  "clientsecret",
  "password",
  "passwd",
  "pwd",
  "passphrase",
  "auth",
  "authorization",
  "signature",
  "sig",
  "session",
  "sessionid",
  "credential",
  "credentials",
  "bearer",
  "jwt",
])

/** Validation shared by the server, the CLI and the workspace connector form,
 * so a remote MCP URL is accepted or refused with the same reason everywhere. */
export namespace McpUrl {
  export function loopback(value: URL): boolean {
    return LOOPBACK.has(value.hostname.toLowerCase())
  }

  /** Why `value` may not carry credential-bearing MCP or OAuth traffic. */
  export function networkProblem(value: URL, label: string, allowLoopbackHttp: boolean): string | undefined {
    const secure = value.protocol === "https:"
    const local = allowLoopbackHttp && value.protocol === "http:" && loopback(value)
    if (!secure && !local) return `${label} must use HTTPS (loopback HTTP is allowed for development)`
    if (value.username || value.password) return `${label} must not contain URL credentials`
    return undefined
  }

  /** The first query parameter whose name marks it as a credential. */
  export function credentialParameter(value: URL): string | undefined {
    for (const name of value.searchParams.keys()) {
      const words = name
        .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
        .toLowerCase()
        .split(/[^a-z0-9]+/)
        .filter(Boolean)
      if (words.some((word) => CREDENTIAL.has(word)) || CREDENTIAL.has(words.join(""))) return name
    }
    return undefined
  }

  /** Why `input` cannot be saved as a remote MCP endpoint, or undefined when it can.
   * Non-secret query parameters such as a tool selection are allowed; the URL
   * is stored in config and shown in logs, so credentials belong in headers. */
  export function endpointProblem(input: string | URL): string | undefined {
    if (typeof input === "string" && !URL.canParse(input)) return "Remote MCP URL is not a valid URL"
    const value = new URL(input)
    const network = networkProblem(value, "Remote MCP URL", true)
    if (network) return network
    if (value.hash) return "Remote MCP URL must not contain a fragment (#…)"
    const name = credentialParameter(value)
    if (name) {
      return `Remote MCP URL query parameter "${name}" looks like a credential; send it as a request header instead`
    }
    return undefined
  }
}
