# Overlay Suggestion Scripts

- Scripts root: [`../README.md`](../README.md)
- Overlay references are selected from the bundled/provider contracts owned by
  each overlay script.

## What Lives Here

`scripts/overlay/` 提供 advice-first overlay 建议脚本：根据当前任务上下文输出推荐的 external overlay / provider / role reference，不直接改变 router assignment。

## Current Scripts

| Script | Purpose |
| --- | --- |
| [`suggest-overlays.ps1`](suggest-overlays.ps1) | 统一建议 overlay catalogs：`agency` / `gitnexus` / `turix-cua` / `ruc-nlpir` / `vco` |
| [`suggest-browserops-provider.ps1`](suggest-browserops-provider.ps1) | 建议 BrowserOps provider |

## Rule

- overlay suggestion 是 advisory surface，不是第二路由器；
- 若脚本需要新的 overlay reference，先更新对应的 executable provider
  contract 和本目录说明。
