# Verify Fixture Index

- Verify root: [`../README.md`](../README.md)
- Contract fixtures are kept beside the gate that consumes them; bundled
  specialist fixtures remain outside this cleanup.

## What Lives Here

`scripts/verify/fixtures/` 保存 gate smoke / pilot / mock 输入样本，用于在不触碰真实 runtime / external provider 的前提下验证 gate 行为。

## Current Fixtures

| File | Purpose |
| --- | --- |
| `llm-acceleration.mock.json` | LLM acceleration overlay mock input |
| `prompt-asset-boost.mock.json` | prompt asset boost mock input |
| `pilot-browserops.json` | BrowserOps pilot fixture |
| `pilot-deep-extraction.json` | deep extraction pilot fixture |
| `pilot-desktopops.json` | DesktopOps pilot fixture |
| `pilot-memory.json` | memory pilot fixture |
| `pilot-prompt.json` | prompt pilot fixture |
| `document-cleanup-safety/` | protected document cleanup fixture families |

## Rule

- verify fixture 是稳定输入样本，不是运行时输出；
- 若 fixture 与 `references/fixtures/**` 的 governed baseline 存在重叠，应优先在 docs 或 README 中说明两者边界。
