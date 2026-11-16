import { McpUrl } from "@synsci/util/mcp-url"

export namespace McpRemoteUrl {
  export function network(
    input: string | URL,
    label = "Remote MCP URL",
    options: { allowLoopbackHttp?: boolean } = {},
  ): URL {
    const value = new URL(input)
    const problem = McpUrl.networkProblem(value, label, options.allowLoopbackHttp === true)
    if (problem) throw new Error(problem)
    return value
  }

  export function endpoint(input: string | URL): URL {
    const problem = McpUrl.endpointProblem(input)
    if (problem) throw new Error(problem)
    return new URL(input)
  }

  /** Discovered OAuth URLs may use loopback HTTP only when the configured MCP
   * endpoint itself is loopback HTTP. An HTTPS server must not be able to turn
   * metadata into a credential-bearing request to a local service. */
  export function discovered(input: string | URL, endpoint: string | URL, label: string): URL {
    const configured = McpRemoteUrl.endpoint(endpoint)
    return network(input, label, {
      allowLoopbackHttp: configured.protocol === "http:" && McpUrl.loopback(configured),
    })
  }

  /** Bun's redirect:"error" currently surfaces an internal UnexpectedRedirect
   * as an unhandled test error. Manual mode plus an explicit 3xx rejection has
   * the same no-forwarding guarantee and a controlled application error. */
  export async function fetchNoRedirect(input: string | URL, init?: RequestInit): Promise<Response> {
    const response = await fetch(input, { ...init, redirect: "manual" })
    if (response.status >= 300 && response.status < 400) {
      await response.body?.cancel().catch(() => undefined)
      throw new Error(`Redirects are not allowed for credential-bearing MCP requests (${response.status})`)
    }
    return response
  }
}
