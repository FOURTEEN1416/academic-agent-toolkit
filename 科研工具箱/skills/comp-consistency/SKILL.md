---
name: comp-consistency
description: Use when a mathematical modeling competition paper must be checked against its canonical results JSON, code outputs, figures, and reported headline metrics before compilation.
---

# Competition Code-Paper Consistency

Read `RESULTS.md`, `figures/all_results.json`, `paper/main.tex`, and declared figures. Create `CONSISTENCY_REPORT.json` with `ok`, `claims`, and each claim's paper location, result-ledger path, observed values, and comparison status. Any missing metric, mismatched value, or untraceable claim sets `ok` to false.

Auxiliary sweep (2026-09-12 asset wiring): also run `python tools/paper_data_check.py <工作区>` (repo-root relative; the tool existed unwired before this line) and fold its findings into `CONSISTENCY_REPORT.json` — it cross-checks paper numbers against the result ledger and is the mandatory machine backstop for this step. The contract and `ok` semantics above remain unchanged.

## 退出判据（Verification）

本步完成前逐项自检（不达标即视为未完成）：

- [ ] 数值口径逐项对账（正文/图表/代码/账本四向）
- [ ] 不一致项给出处置（改文/改图/说明）而非忽略
- [ ] 百分比、精度、单位变体已纳入比对
- [ ] 报告为机器可读结构，可供审计引用

## 常见合理化（Common Rationalizations）

| 合理化 | 现实 |
|---|---|
| "数值差一点点不算问题" | 评审会按数值对账：同一量出现两个值即判不可信。 |
| "只对正文和表" | 图与代码同属公开产物，四向不对账就有缺口。 |
| "以前对过一遍了" | 任何一处改动都会让旧结论失效；本步必须重跑。 |

> 本段与 `skills/_utils/anti_rationalization.md`（全局版）配套：本表是本步专属，
> 全局版覆盖跨步骤通用借口。新增借口时优先落到本表（更贴岗位），能泛化再上升。
