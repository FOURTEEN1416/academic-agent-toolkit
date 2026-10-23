---
name: comp-final-review
description: Use when a mathematical modeling competition submission requires a final evidence-based re-review after edits and before delivery.
---

# Competition Final Review

在 `comp_cumcm` 链中本步是第 13 步终审：成文步（第 8 步）已完成九维自评并产出 `PAPER_SCORING.json`；本步复核九维分数与失分段落清单是否闭环，再做独立证据复核与交付合规判定。其他链以模板步号为准。

## Inputs

Read the final paper source and PDF, executable code, `RESULTS.md`, `figures/all_results.json`, `CONSISTENCY_REPORT.json`, `LITERATURE.md`, literature search evidence, `PAPER_SCORING.json` when the paper-writing step produced it (the nine-dimension scores and loss-paragraph list), `COMP_REVIEW_VERDICT.json`, `VISUAL_REVIEW_VERDICT.json`, and `EDITOR_CHANGELOG.md`. Also read the submission self-check catalogue `academic-toolkit/data/paper_selfcheck_287.json` and the nine-dimension scoring framework `academic-toolkit/skills/math-modeling-contest-route-selection/references/paper-scoring-framework.md`; the framework is the only source for dimension names, 0-5 anchors, and weights. If any required input is absent, record it as a fatal verification gap; for a legacy workflow that predates `PAPER_SCORING.json`, perform the nine-dimension scoring in this step and mark it as first-pass scoring rather than silently skipping the scoring review.

## Execution

1. Confirm every earlier fatal finding is fixed with traceable evidence, or remains explicitly unresolved.
2. Recheck the paper's central claims against the canonical result ledger and consistency report.
3. Recheck citation closure, compilation state, figure review status, and delivery-file completeness.
4. Do not repeat a prior verdict blindly: inspect the edited source and the final PDF independently.
5. Classify every issue as `fatal`, `major`, or `minor`; a fatal is any missing required evidence, unresolved leakage, unsupported central claim, invalid result trace, or competition-format blocker.
6. Recheck the paper-writing step's nine-dimension scores and loss-paragraph list for closure. This is a review, not a first scoring pass: for every dimension defined in `academic-toolkit/skills/math-modeling-contest-route-selection/references/paper-scoring-framework.md`, using that file's anchors and weights, compare the score and evidence location recorded in `PAPER_SCORING.json` with the current source and final PDF; re-score only where the edited paper no longer supports the recorded score, and state the reason for every difference. A score without a body/figure/table location is not evidence. For every loss dimension, confirm `EDITOR_CHANGELOG.md` records a closing edit or an explicit justified unresolved status; an unexplained gap is a finding. Run the `paper_selfcheck_287.json` items that apply to this paper and record the failed item IDs. Evidence completeness alone cannot pass a paper with weak argumentation: such weaknesses must remain visible as score losses and as fatal/major findings. For a legacy workflow without `PAPER_SCORING.json`, produce the first-pass nine-dimension scores here with the same anchors and record that the input was absent.

## Outputs

Write `FINAL_REVIEW.md` with the reviewed inputs, a per-dimension comparison of the paper-writing scores against the final-review scores, the closure status of every loss paragraph, evidence locations, findings, and required remediation. Write `FINAL_REVIEW_VERDICT.json` as an object containing `findings`, integer `fatal_count`, `scores`, `weighted_total`, `fatal_dimensions`, `selfcheck_failures`, and `loss_closure`; each finding must include an ID, severity, location, evidence, and fix. `scores` is keyed by the nine scoring-framework dimension names, each value `{"score": <reviewed integer 0-5>, "evidence": "<正文/图/表位置>", "initial_score": <paper-writing score 0-5>, "delta_reason": "<why the score changed; empty when unchanged>"}`; `weighted_total` is the framework-weighted sum on the same 0-5 scale (two decimals); `fatal_dimensions` lists the dimensions carrying a fatal finding; `selfcheck_failures` lists the failed self-check item IDs; `loss_closure` lists every loss dimension from `PAPER_SCORING.json` as `{"dimension": "<name>", "status": "closed|open|not_applicable", "evidence": "<EDITOR_CHANGELOG.md 行或正文位置>", "reason": "<closure evidence or return step>"}`. A fatal finding cannot be offset by a higher score. These are verdict content only — they do not add or change engine gates. Write `REVIEW_EXECUTION_EVIDENCE.json` with the independently completed `reviewer`, `visual_reviewer`, `editor`, and `final_reviewer` role records. Each role record must contain `session_id`, `model`, `output_file`, `output_sha256`, and `completed_at`. Generate the file with `python -m engine.workflow_cli session review-evidence --session <ticket> --roles review_roles.json`: the roles file supplies only `session_id`, `model`, and `output_file` for each role; the script resolves the workspace output file, computes `output_sha256`, and stamps `completed_at`. Do not hand-compute hashes or timestamps, and never infer a role from a filename — every role must be named explicitly in the roles file, and a missing role or missing output file is rejected. The primary agent runs the command after receiving read-only child-agent conclusions. A nonzero fatal count blocks `comp-final-audit`. If a visual API was unavailable, retain its `unavailable` status rather than converting it to a pass.

## 退出判据（Verification）

本步完成前逐项自检（不达标即视为未完成）：

- [ ] 由只读子智能体执行，且为 full 模式（四角色证据齐备）
- [ ] 模型证据与比赛配置一致（strict 比对通过）
- [ ] 九维分数与失分段落清单已逐维复核（与成文步评分差异均有理由）
- [ ] 每个失分维度闭环状态已记录（closed/open/not_applicable），open 项有明确回流步骤
- [ ] 结论明确（通过/有条件通过/不通过）并给理由
- [ ] 发现问题已回灌到对应步骤产物

## 常见合理化（Common Rationalizations）

| 合理化 | 现实 |
|---|---|
| "前面审过了，这里走个流程" | 终审是最后一道独立视角；省掉它等于放弃唯一的结构性防线。 |
| "成文步已经打过分，这里照抄就行" | 终审要独立核对分数与失分段落是否真的改到位；照抄初稿评分等于放弃独立复核。 |
| "模型用哪个无所谓" | 审稿模型证据必须与配置一致，否则证据链不成立。 |
| "有问题记在心里就行" | 未回灌的发现不会进入产物，下一轮还会复现。 |

> 本段与 `skills/_utils/anti_rationalization.md`（全局版）配套：本表是本步专属，
> 全局版覆盖跨步骤通用借口。新增借口时优先落到本表（更贴岗位），能泛化再上升。
