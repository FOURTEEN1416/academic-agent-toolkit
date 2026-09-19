---
name: comp-final-review
description: Use when a mathematical modeling competition submission requires a final evidence-based re-review after edits and before delivery.
---

# Competition Final Review

## Inputs

Read the final paper source and PDF, executable code, `RESULTS.md`, `figures/all_results.json`, `CONSISTENCY_REPORT.json`, `LITERATURE.md`, literature search evidence, `COMP_REVIEW_VERDICT.json`, `VISUAL_REVIEW_VERDICT.json`, and `EDITOR_CHANGELOG.md`. If any required input is absent, record it as a fatal verification gap.

## Execution

1. Confirm every earlier fatal finding is fixed with traceable evidence, or remains explicitly unresolved.
2. Recheck the paper's central claims against the canonical result ledger and consistency report.
3. Recheck citation closure, compilation state, figure review status, and delivery-file completeness.
4. Do not repeat a prior verdict blindly: inspect the edited source and the final PDF independently.
5. Classify every issue as `fatal`, `major`, or `minor`; a fatal is any missing required evidence, unresolved leakage, unsupported central claim, invalid result trace, or competition-format blocker.

## Outputs

Write `FINAL_REVIEW.md` with the reviewed inputs, evidence locations, findings, and required remediation. Write `FINAL_REVIEW_VERDICT.json` as an object containing `findings` and integer `fatal_count`; each finding must include an ID, severity, location, evidence, and fix. Write `REVIEW_EXECUTION_EVIDENCE.json` with the independently completed `reviewer`, `visual_reviewer`, `editor`, and `final_reviewer` role records. Each role record must contain `session_id`, `model`, `output_file`, `output_sha256`, and `completed_at`; calculate the hash from the final workspace output file. The primary agent writes this evidence after receiving read-only child-agent conclusions. A nonzero fatal count blocks `comp-final-audit`. If a visual API was unavailable, retain its `unavailable` status rather than converting it to a pass.

## 退出判据（Verification）

本步完成前逐项自检（不达标即视为未完成）：

- [ ] 由只读子智能体执行，且为 full 模式（四角色证据齐备）
- [ ] 模型证据与比赛配置一致（strict 比对通过）
- [ ] 结论明确（通过/有条件通过/不通过）并给理由
- [ ] 发现问题已回灌到对应步骤产物

## 常见合理化（Common Rationalizations）

| 合理化 | 现实 |
|---|---|
| "前面审过了，这里走个流程" | 终审是最后一道独立视角；省掉它等于放弃唯一的结构性防线。 |
| "模型用哪个无所谓" | 审稿模型证据必须与配置一致，否则证据链不成立。 |
| "有问题记在心里就行" | 未回灌的发现不会进入产物，下一轮还会复现。 |

> 本段与 `skills/_utils/anti_rationalization.md`（全局版）配套：本表是本步专属，
> 全局版覆盖跨步骤通用借口。新增借口时优先落到本表（更贴岗位），能泛化再上升。
