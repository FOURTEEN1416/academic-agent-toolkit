import { test, expect, beforeEach } from "bun:test"
import { createHash } from "node:crypto"
import path from "path"
import fs from "fs/promises"
import { auth } from "@modelcontextprotocol/sdk/client/auth.js"
import { Global } from "../../src/global"
import { McpAuth } from "../../src/mcp/auth"
import { McpOAuthProvider } from "../../src/mcp/oauth-provider"

// A remote MCP resource advertises which authorization server protects it. A
// refresh token and a client secret were issued by one such server; they must
// only ever go back there, whatever the resource advertises later.

const fingerprint = createHash("sha256").update("mcp-oauth-issuer-binding").digest("hex")

beforeEach(async () => {
  await fs.mkdir(Global.Path.data, { recursive: true })
  const entries = await fs.readdir(Global.Path.data)
  await Promise.all(
    entries
      .filter((name) => name.startsWith("mcp-auth.json"))
      .map((name) => fs.rm(path.join(Global.Path.data, name), { force: true })),
  )
})

/** An authorization server that records every token request it receives. */
function authorizationServer(options: { tokenPath?: string } = {}) {
  const tokenPath = options.tokenPath ?? "/token"
  const requests: URLSearchParams[] = []
  const server = Bun.serve({
    port: 0,
    hostname: "127.0.0.1",
    async fetch(req) {
      const url = new URL(req.url)
      if (url.pathname === "/.well-known/oauth-authorization-server") {
        return Response.json({
          issuer: url.origin,
          authorization_endpoint: `${url.origin}/authorize`,
          token_endpoint: `${url.origin}${tokenPath}`,
          response_types_supported: ["code"],
          grant_types_supported: ["authorization_code", "refresh_token"],
          token_endpoint_auth_methods_supported: ["none", "client_secret_post"],
        })
      }
      if (url.pathname === tokenPath) {
        requests.push(new URLSearchParams(await req.text()))
        return Response.json({
          access_token: `access-from-${url.port}`,
          token_type: "Bearer",
          refresh_token: `refresh-from-${url.port}`,
          expires_in: 3600,
        })
      }
      return new Response("not found", { status: 404 })
    },
  })
  const origin = `http://127.0.0.1:${server.port}`
  return {
    server,
    requests,
    origin,
    issuer: { authorizationServer: `${origin}/`, tokenEndpoint: `${origin}${tokenPath}` },
  }
}

/** The MCP resource, whose protected-resource metadata names an authorization
 * server that the test can change at any time. */
function resource() {
  const advertised = { origin: "" }
  const server = Bun.serve({
    port: 0,
    hostname: "127.0.0.1",
    fetch(req) {
      const url = new URL(req.url)
      if (url.pathname.startsWith("/.well-known/oauth-protected-resource")) {
        return Response.json({
          resource: `${url.origin}/mcp`,
          authorization_servers: [`${advertised.origin}/`],
        })
      }
      return new Response("unauthorized", { status: 401 })
    },
  })
  return {
    server,
    url: `http://127.0.0.1:${server.port}/mcp`,
    advertise: (origin: string) => (advertised.origin = origin),
  }
}

function provider(name: string, url: string, flowState?: string) {
  return new McpOAuthProvider(
    name,
    url,
    { clientId: "client-1", clientSecret: "canary-client-secret" },
    { onRedirect: async () => {} },
    { verify: async () => undefined, authorityFingerprint: fingerprint, flowState },
  )
}

const expired = (refreshToken: string) => ({
  accessToken: "stale-access",
  refreshToken,
  expiresAt: Date.now() / 1000 - 60,
})

test("a stored refresh token and client secret go only to the server that issued them", async () => {
  const legitimate = authorizationServer()
  const attacker = authorizationServer()
  const mcp = resource()
  const name = "issuer-bound-refresh"
  try {
    await McpAuth.set(
      name,
      {
        tokens: expired("canary-refresh-token"),
        credentialAuthorityFingerprint: fingerprint,
        credentialIssuer: legitimate.issuer,
      },
      mcp.url,
    )
    // The resource now advertises the attacker's server. The local config and
    // the MCP URL are unchanged, so the stored credentials are still in use.
    mcp.advertise(attacker.origin)

    const tokens = await provider(name, mcp.url).tokens()

    expect(attacker.requests).toHaveLength(0)
    expect(legitimate.requests).toHaveLength(1)
    expect(legitimate.requests[0]!.get("refresh_token")).toBe("canary-refresh-token")
    expect(legitimate.requests[0]!.get("client_secret")).toBe("canary-client-secret")
    expect(tokens?.access_token).toBe(`access-from-${new URL(legitimate.origin).port}`)
    const saved = await McpAuth.get(name)
    expect(saved?.tokens?.refreshToken).toBe(`refresh-from-${new URL(legitimate.origin).port}`)
    expect(saved?.credentialIssuer).toEqual(legitimate.issuer)
  } finally {
    legitimate.server.stop(true)
    attacker.server.stop(true)
    mcp.server.stop(true)
    await McpAuth.remove(name)
  }
})

test("the SDK's own auth() also sends the refresh to the bound server, not the advertised one", async () => {
  const legitimate = authorizationServer()
  const attacker = authorizationServer()
  const mcp = resource()
  const name = "issuer-bound-sdk-auth"
  try {
    await McpAuth.set(
      name,
      {
        tokens: expired("canary-refresh-token"),
        credentialAuthorityFingerprint: fingerprint,
        credentialIssuer: legitimate.issuer,
      },
      mcp.url,
    )
    mcp.advertise(attacker.origin)

    const result = await auth(provider(name, mcp.url), { serverUrl: mcp.url })

    expect(result).toBe("AUTHORIZED")
    expect(attacker.requests).toHaveLength(0)
    // The provider refreshes when the SDK reads the expired tokens, and the
    // SDK refreshes the pair it was handed once more; every request went to
    // the issuer.
    expect(legitimate.requests.length).toBeGreaterThan(0)
    expect(legitimate.requests[0]!.get("refresh_token")).toBe("canary-refresh-token")
    expect((await McpAuth.get(name))?.credentialIssuer).toEqual(legitimate.issuer)
  } finally {
    legitimate.server.stop(true)
    attacker.server.stop(true)
    mcp.server.stop(true)
    await McpAuth.remove(name)
  }
})

test("a token endpoint that moved since authorization receives nothing", async () => {
  const issuer = authorizationServer({ tokenPath: "/v2/token" })
  const mcp = resource()
  const name = "issuer-endpoint-moved"
  try {
    mcp.advertise(issuer.origin)
    await McpAuth.set(
      name,
      {
        tokens: expired("canary-refresh-token"),
        credentialAuthorityFingerprint: fingerprint,
        // Authorized when the server's metadata named /token.
        credentialIssuer: { authorizationServer: `${issuer.origin}/`, tokenEndpoint: `${issuer.origin}/token` },
      },
      mcp.url,
    )

    const tokens = await provider(name, mcp.url).tokens()

    expect(issuer.requests).toHaveLength(0)
    // The stale pair comes back untouched so the SDK surfaces re-authorization.
    expect(tokens?.access_token).toBe("stale-access")
    expect((await McpAuth.get(name))?.tokens?.refreshToken).toBe("canary-refresh-token")
  } finally {
    issuer.server.stop(true)
    mcp.server.stop(true)
    await McpAuth.remove(name)
  }
})

test("a credential stored before issuers were recorded is bound by its first refresh", async () => {
  const original = authorizationServer()
  const attacker = authorizationServer()
  const mcp = resource()
  const name = "issuer-legacy-binding"
  try {
    mcp.advertise(original.origin)
    await McpAuth.set(name, { tokens: expired("legacy-refresh"), credentialAuthorityFingerprint: fingerprint }, mcp.url)

    const first = await provider(name, mcp.url).tokens()
    expect(first?.access_token).toBe(`access-from-${new URL(original.origin).port}`)
    expect((await McpAuth.get(name))?.credentialIssuer).toEqual(original.issuer)

    // From now on the resource's metadata no longer chooses the server.
    mcp.advertise(attacker.origin)
    await McpAuth.updateTokens(name, expired(`refresh-from-${new URL(original.origin).port}`))
    const second = await provider(name, mcp.url).tokens()
    expect(second?.access_token).toBe(`access-from-${new URL(original.origin).port}`)
    expect(attacker.requests).toHaveLength(0)
    expect(original.requests).toHaveLength(2)
  } finally {
    original.server.stop(true)
    attacker.server.stop(true)
    mcp.server.stop(true)
    await McpAuth.remove(name)
  }
})

test("a browser flow keeps the server it redirected to through the code exchange", async () => {
  const name = "issuer-flow-binding"
  const url = "https://mcp.example/mcp"
  const state = "flow-state-1"
  try {
    await McpAuth.updateOAuthState(name, state, {
      serverUrl: url,
      authorityFingerprint: fingerprint,
      allowDisabled: false,
    })
    const flow = provider(name, url, state)

    // Nothing discovered yet: the SDK performs discovery.
    expect(await flow.discoveryState()).toBeUndefined()
    await flow.saveDiscoveryState({ authorizationServerUrl: "https://auth.example/" })
    expect(await flow.discoveryState()).toEqual({ authorizationServerUrl: "https://auth.example/" })

    // Between the redirect and the callback the resource names another server:
    // the exchange does not proceed there with the code, verifier and secret.
    await expect(flow.saveDiscoveryState({ authorizationServerUrl: "https://evil.example/" })).rejects.toThrow(
      /changed during authorization/,
    )
    expect(await flow.discoveryState()).toEqual({ authorizationServerUrl: "https://auth.example/" })

    // Another process finishing the same flow reads the same server.
    expect(await provider(name, url, state).discoveryState()).toEqual({
      authorizationServerUrl: "https://auth.example/",
    })
  } finally {
    await McpAuth.remove(name)
  }
})

test("a passive provider refuses a discovery that names another server for bound credentials", async () => {
  const name = "issuer-passive-refusal"
  const url = "https://mcp.example/mcp"
  try {
    await McpAuth.set(
      name,
      {
        tokens: { accessToken: "access", refreshToken: "refresh", expiresAt: Date.now() / 1000 + 3600 },
        credentialAuthorityFingerprint: fingerprint,
        credentialIssuer: { authorizationServer: "https://auth.example/", tokenEndpoint: "https://auth.example/token" },
      },
      url,
    )
    const passive = provider(name, url)
    expect(await passive.discoveryState()).toEqual({ authorizationServerUrl: "https://auth.example/" })
    await expect(passive.saveDiscoveryState({ authorizationServerUrl: "https://evil.example/" })).rejects.toThrow(
      /changed since it was authorized/,
    )
    // The same server, restated, is fine; and a discovery reset never unbinds.
    await passive.saveDiscoveryState({ authorizationServerUrl: "https://auth.example/" })
    await passive.invalidateCredentials("discovery")
    expect((await McpAuth.get(name))?.credentialIssuer).toEqual({
      authorizationServer: "https://auth.example/",
      tokenEndpoint: "https://auth.example/token",
    })
  } finally {
    await McpAuth.remove(name)
  }
})
