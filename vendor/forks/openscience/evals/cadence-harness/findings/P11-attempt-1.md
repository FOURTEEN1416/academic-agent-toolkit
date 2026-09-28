# P11 attempt 1 — search routing and settlement

## Outcome

The run was cancelled after 744 seconds with no final response. It completed five model calls and 17 tool calls, downloaded the accession table and WorldClim archive into session scratch, but never reached analysis. Two `research_search` calls remained open for 377 seconds until cancellation.

Evidence bundle:

`~/.openscience-dev/researchagent-test/campaigns/run-2026-08-27T05-53-16-261Z-p11-80b13785/runs/p11`

## Root cause

- The isolated profile resolved model access to `byok`, but `ResearchRouting.select()` ignored that choice. Because the signed-in account was Ace-enabled, every search was sent to managed search before the configured Firecrawl key.
- Managed attempts took roughly 92–120 seconds before falling back. The supplied Firecrawl credential itself was healthy in an independent live preflight.
- `FirecrawlSearch.search()` sent a timeout hint in the request body but had no client-side settlement deadline. Two fallback transports therefore remained pending indefinitely and kept the whole parallel tool batch and model turn busy.
- The raw `AbortError` seen in the runner was a tool/model cancellation symptom, not the cause. The durable runtime journal continued capturing the turn correctly.

## Agent and scientific behavior

- The agent used relevant sources and kept downloads in session scratch.
- It retried source discovery with increasingly specific searches, but the latency was infrastructure-driven rather than inference-loop polling.
- No scientific result, report, figure, or Result artifact existed, so this attempt cannot be judged for substantive task quality.

## General correction

- Make search routing follow the explicit Managed versus BYOK access choice. An Ace entitlement must not override BYOK.
- Give Firecrawl transport a real client-side deadline in addition to its provider request hint so every tool call settles.
- Preserve the existing managed-operation idempotency and settlement behavior for Managed mode.
- If a managed dispatch fails ambiguously, fall back only to the free community route. Starting the user's Firecrawl route after a managed operation may already be in flight would violate the access choice and risk duplicate provider work.

## Verification

- Focused routing/search tests: 21 passed.
- Backend TypeScript check passed.
- P11 must be rerun from a fresh project/session against the restarted source-pinned backend.
