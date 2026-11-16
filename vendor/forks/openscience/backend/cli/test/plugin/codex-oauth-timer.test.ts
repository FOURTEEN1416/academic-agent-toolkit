import { test, expect } from "bun:test"
import { waitForOAuthCallback } from "../../src/plugin/codex"

const pkce = { verifier: "verifier", challenge: "challenge" }

test("a sign-in attempt that is never answered times out", async () => {
  await expect(waitForOAuthCallback(pkce, "first", 10)).rejects.toThrow("OAuth callback timeout")
})

test("both abandoned and replacement sign-ins settle", async () => {
  const results = await Promise.allSettled([
    waitForOAuthCallback(pkce, "first", 10),
    waitForOAuthCallback(pkce, "second", 30),
  ])
  expect(results.map((result) => result.status)).toEqual(["rejected", "rejected"])
})
