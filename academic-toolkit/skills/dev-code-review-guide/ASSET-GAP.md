# ASSET-GAP 资产缺口声明 — dev-code-review-guide

> 2026-09-28 深读批补登，上游资产未随本仓集成：以下条目为 SKILL.md 末尾 Resources 节正文实际引用、盘上缺失、且未经内联标记/登记册棘轮/本清单三渠道豁免的资产。注：正文以 `**…**` 粗体引用致 audit 的动态占位符判定静默跳过机检（`*` 被当通配符），故此前从未进 FAIL/acknowledged 名册，本清单使其显性化。

## 缺失资产清单（6 项，2026-09-28 审计）

- `references/code-review-best-practices.md`
- `references/common-bugs-checklist.md`
- `references/security-review-guide.md`
- `assets/pr-review-template.md`
- `assets/review-checklist.md`
- `scripts/pr-analyzer.py`

## 处置口径

- 本声明使上述断链显性化（audit 豁免），删除本文件前必须先补齐资产或登记新台账。
- 若后续获得上游来源：按先 fork 后集成惯例拉取 → 补 UPSTREAM.md 台账 → 从 tools/asset_gap_register.json 删除对应条目 → 删除本声明。
