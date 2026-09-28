import { describe, expect, test } from "bun:test"
import { Config } from "../../src/config/config"

describe("MCP config secrecy", () => {
  test("redacts local environment values and remote headers and client secrets", () => {
    const value = Config.redact({
      model: "openai/gpt-5.6",
      mcp: {
        local: {
          type: "local",
          command: ["bun", "server.mjs"],
          environment: {
            TOKEN: "local-secret",
          },
        },
        remote: {
          type: "remote",
          url: "https://mcp.example.com/mcp",
          headers: {
            Authorization: "Bearer remote-secret",
          },
          oauth: {
            clientId: "public-client",
            clientSecret: "oauth-secret",
          },
        },
        disabled: {
          enabled: false,
        },
      },
    })

    expect(value.model).toBe("openai/gpt-5.6")
    expect(value.mcp?.local).toEqual({
      type: "local",
      command: ["bun", "server.mjs"],
      environment: {
        TOKEN: Config.MCP_SECRET_MASK,
      },
    })
    expect(value.mcp?.remote).toEqual({
      type: "remote",
      url: "https://mcp.example.com/mcp",
      headers: {
        Authorization: Config.MCP_SECRET_MASK,
      },
      oauth: {
        clientId: "public-client",
        clientSecret: Config.MCP_SECRET_MASK,
      },
    })
    expect(value.mcp?.disabled).toEqual({ enabled: false })
  })

  test("restores masked values on edit while allowing explicit deletion", () => {
    const previous: Config.Mcp = {
      type: "remote",
      url: "https://mcp.example.com/mcp",
      headers: {
        Authorization: "Bearer original",
        "X-Remove-Me": "old",
      },
      oauth: {
        clientId: "client",
        clientSecret: "oauth-original",
      },
      timeout: 5_000,
    }
    const next = Config.restoreMcp(
      {
        type: "remote",
        url: "https://mcp.example.com/v2",
        headers: {
          Authorization: Config.MCP_SECRET_MASK,
          "X-New": "new",
        },
        oauth: {
          clientId: "client",
          clientSecret: Config.MCP_SECRET_MASK,
        },
        timeout: 8_000,
      },
      previous,
    )

    expect(next).toEqual({
      type: "remote",
      url: "https://mcp.example.com/v2",
      headers: {
        Authorization: "Bearer original",
        "X-New": "new",
      },
      oauth: {
        clientId: "client",
        clientSecret: "oauth-original",
      },
      timeout: 8_000,
    })
  })

  test("fails closed when a mask has no stored value", () => {
    expect(() =>
      Config.restoreMcp({
        type: "local",
        command: ["bun", "server.mjs"],
        environment: {
          TOKEN: Config.MCP_SECRET_MASK,
        },
      }),
    ).toThrow(/Replace the masked value/)

    expect(() =>
      Config.restoreMcp({
        type: "remote",
        url: "https://mcp.example.com/mcp",
        oauth: {
          clientSecret: Config.MCP_SECRET_MASK,
        },
      }),
    ).toThrow(/Replace the masked value/)
  })

  test("restores MCP secrets inside a general config patch", () => {
    const previous: Config.Info = {
      mcp: {
        local: {
          type: "local",
          command: ["bun", "server.mjs"],
          environment: {
            TOKEN: "original",
          },
        },
      },
    }
    const patch: Config.Info = {
      model: "openai/gpt-5.6",
      mcp: {
        local: {
          type: "local",
          command: ["bun", "server.mjs"],
          environment: {
            TOKEN: Config.MCP_SECRET_MASK,
          },
        },
      },
    }

    expect(Config.restore(patch, previous)).toEqual({
      model: "openai/gpt-5.6",
      mcp: {
        local: {
          type: "local",
          command: ["bun", "server.mjs"],
          environment: {
            TOKEN: "original",
          },
        },
      },
    })
  })
})
