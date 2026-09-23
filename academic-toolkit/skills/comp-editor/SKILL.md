---
name: comp-editor
description: Use when a mathematical modeling competition draft needs controlled edits in response to documented reviewer findings.
---

# Competition Editor

## Inputs

Read `COMP_REVIEW_VERDICT.json`, `VISUAL_REVIEW_VERDICT.json`, the associated markdown reports, the current paper sources, captions, and the canonical result ledger. Treat a missing report or invalid verdict as a blocking issue, not an invitation to infer reviewer intent.

## Execution

1. Build a list of unresolved finding IDs and their requested fixes.
2. Modify prose, captions, layout, references, or declared delivery materials only for those IDs.
3. Do not alter data, model outputs, equations, or headline metrics without a new computation, updated result ledger, and fresh execution evidence from the responsible step.
4. Preserve unresolved fatal findings in the changelog and route them back to modeling, code, or paper writing instead of hiding them through wording changes.
5. Re-run the narrow validation relevant to every changed file, then return the workspace to the final reviewer.
6. When rewording prose, apply the `anti-defensive-writing` skill's removal taxonomy: strip unnecessary hedges, disclaimers, apology-like framing, and over-explanations while preserving methodological limits, accuracy qualifiers, and required AI-use statements.

## Outputs

Write `EDITOR_CHANGELOG.md`. For every reviewed finding ID, record the disposition (`fixed`, `unresolved`, or `not_applicable`), changed files, a concise description of the edit, the validation command or manual check, and the reason for any unresolved item. Do not claim the paper is delivery-ready; only `comp-final-review` and `comp-final-audit` may make that decision.

## 退出判据（Verification）

本步完成前逐项自检（不达标即视为未完成）：

- [ ] 每条修改可追溯（改了什么、依据哪条意见）
- [ ] 只改被指出的问题，不顺手改结构
- [ ] 改动后与正文数值/结论保持一致
- [ ] 不引入新的事实性断言

## 常见合理化（Common Rationalizations）

| 合理化 | 现实 |
|---|---|
| "顺手优化一下表达" | 编辑步的职责是修订而非重构；越界改动会破坏已验证的一致性。 |
| "改完不用记" | 无变更记录即无法复核；变更清单是本步产物。 |
| "语气改强一点更有力" | 删除 hedging 要有依据，不能变成过度断言。 |

> 本段与 `skills/_utils/anti_rationalization.md`（全局版）配套：本表是本步专属，
> 全局版覆盖跨步骤通用借口。新增借口时优先落到本表（更贴岗位），能泛化再上升。
