---
name: paper-results-report
description: "Use when the user asks to ”write an experiment report”, ”summarize experimental results”, or a post-experiment summary."
version: 0.1.0
tags: [Research, Reporting, Experiments, Obsidian]
---

# Results Report

Write the **complete post-experiment summary report** after analysis artifacts are ready.

This skill is for the stage **after** `results-analysis`.

## Role boundary

### `results-analysis` does
- strict statistics,
- real figures,
- figure interpretation scaffolding,
- stats appendix.

### `results-report` does
- complete experiment wrap-up report,
- decision-oriented narrative,
- figure-by-figure interpretation inside a coherent structure,
- limitations, failure cases, and next actions,
- Obsidian write-back into `Results/Reports/`.

When the task is to create or redesign paper-ready figures/tables themselves, rely on `fig-publication-chart` instead of expanding `results-report` into figure/table production.

Do not replace strict analysis with confident prose. If the analysis bundle is missing, first identify the blocker and request or produce the missing bundle.

Hard gate: do not write a complete report when `analysis-report.md`, `stats-appendix.md`, `figure-catalog.md`, provenance, or the primary comparison question is missing. In that case, write only a blocker summary and route back to `results-analysis`.

## Default output

The default report is an **internal research report**, not manuscript prose.

It should be named as:

```text
YYYY-MM-DD--{experiment-line}--r{round}--{purpose}.md
```

Example:
- `2026-03-18--freezing--r03--transfer-summary.md`
- `2026-03-18--contrastive-adversarial--r02--ablation-report.md`

The note title should be:

```text
{Experiment Line} / Round {N} / {Purpose} / {YYYY-MM-DD}
```

Naming rules are inlined in 「必读件要点（内联）」 below — apply them before finalizing the filename or note title（原 `references/report-naming.md` 未随仓，见 ASSET-GAP）.

## Required frontmatter

```yaml
---
type: results-report
date: 2026-03-18
experiment_line: freezing
round: 3
purpose: transfer-summary
status: active
source_artifacts:
  - analysis-output/analysis-report.md
  - analysis-output/stats-appendix.md
linked_experiments:
  - Experiments/Freezing-Study.md
linked_results:
  - Results/Freezing-vs-Adapter.md
---
```

## Default report structure

The report must include all sections below.

1. **Executive Summary**
2. **Experiment Identity and Decision Context**
3. **Setup and Evaluation Protocol**
4. **Main Findings**
5. **Statistical Validation**
6. **Figure-by-Figure Interpretation**
7. **Failure Cases / Negative Results / Limitations**
8. **What Changed Our Belief**
9. **Next Actions**
10. **Artifact and Reproducibility Index**

Section-by-section guidance is inlined in 「必读件要点（内联）」 below — apply it before writing（原 `references/report-structure.md` 未随仓，见 ASSET-GAP）.

## Workflow

### 1. Confirm the report object

Lock these fields first:
- date,
- experiment line,
- round,
- purpose,
- linked experiment note,
- linked durable result note if one already exists.

If round is unknown, do not silently invent a semantic round. Use `r00` only as a temporary placeholder and state that it should be normalized later.

### 2. Read the strict analysis bundle

Minimum required inputs:
- `analysis-report.md`
- `stats-appendix.md`
- `figure-catalog.md`
- actual figures, if available

If these are missing, either generate them first with `results-analysis` or explicitly state which claims cannot be supported.
Do not turn loose CSV/Markdown artifacts into a polished report unless the strict analysis bundle has already validated unit of analysis, primary metric, and claim wording.

### 3. Write the report as a decision object

This report is not a transcript of outputs.

Each section must answer a real question:
- What did we test?
- What changed numerically?
- What is actually supported?
- What failed or remains uncertain?
- What should we do next?

Reasoning-depth guidance is inlined in 「必读件要点（内联）」 below（原 `references/decision-oriented-analysis.md` 未随仓，见 ASSET-GAP）.

### 4. Interpret figures inside the report

Do not only attach figures.

For each main figure:
- introduce why it is included,
- state the key observation,
- explain the supported interpretation,
- explain the decision implication.

Figure-interpretation and statistical-completeness guidance is inlined in 「必读件要点（内联）」 below（原两份 references 未随仓，见 ASSET-GAP）.

### 5. Choose the write target explicitly

If the current repo is bound to an Obsidian project knowledge base:
- create or update `Results/Reports/{report-name}.md`,
- link back to the relevant `Experiments/` note,
- update the matching canonical `Results/` note when a durable conclusion is now supported,
- append a short trace to today's `Daily/` note,
- update `project-memory/<project_id>.md`.

If the repo is **not** bound:
- write the report as a local markdown artifact in the requested output location or next to the analysis bundle,
- keep the same filename contract,
- explicitly say that no Obsidian write-back was attempted.

Use `lit-obsidian-kb-core` conventions only for bound repos. Internal experiment reports belong in `Results/Reports/`, not `Writing/`.

### 6. End with explicit next actions

The report must end with operational decisions, for example:
- stop a weak branch,
- schedule one missing ablation,
- promote a stable finding into manuscript-facing writing,
- update the active plan.

## Required quality bar

- The report must be dateable, searchable, and attributable to one experiment line and one round.
- The report must cite actual evidence from the analysis bundle.
- The report must include negative results when they matter.
- The report must separate stable conclusion from tentative interpretation.
- The report must say what changed in project belief and what should happen next.
- The report must preserve Claim Candidate wording and must not promote `speculative` or `observed` claims into decisive conclusions.

## 必读件要点（内联，原上游 7 份必读件未随仓——见 ASSET-GAP.md）

本节把上游 7 份必读件的可执行要点内联，正文不依赖缺失文件即可执行：

1. **report-naming**：文件名 `YYYY-MM-DD--{experiment-line}--r{round}--{purpose}.md`（round 两位零填充；purpose 用小写连字符受控词，如 transfer-summary / ablation-report / error-analysis / scale-report / replication-check）；笔记标题 `{Experiment Line} / Round {N} / {Purpose} / {YYYY-MM-DD}`；同一实验线同轮次不得重名。
2. **report-structure**：按上文 10 节顺序成文，不得删节 Executive Summary / Statistical Validation / Next Actions 三节；每节至少一段实质内容，确无内容写「无——原因」。
3. **decision-oriented-analysis**：全文面向决策——每个结论回答「改变了哪个判断、下一步做什么」；区分 观察（数字）→ 解释（含义）→ 行动（建议）三层，不写过程性流水账。
4. **figure-interpretation**：每张主图四要素——为何入选、关键观察、支持的解释、决策含义；禁止只贴图不解读。
5. **statistical-completeness**：每个统计主张须含 n、效应量、置信区间、精确 p 值、检验名与前提核查、多重比较处置；禁止只写「显著/不显著」。
6. **EVIDENCE-PROPAGATION**：引用 Claim Candidate 时保留其强度标签（speculative/observed/confirmed），报告不得把 speculative/observed 提升为决定性结论；证据指针（文件+位置）随结论传播。
7. **example-results-report**：产出前对照最小样例自查——frontmatter 齐全、10 节齐备、每图有四要素解读、结尾有可执行 Next Actions。

## Reference files

原上游必读件均未随仓（要点已内联于上节；登记见 ASSET-GAP.md），获得上游来源后按原路径回填：
- `references/report-structure.md`（缺失——要点已内联）
- `references/report-naming.md`（缺失——要点已内联）
- `references/figure-interpretation.md`（缺失——要点已内联）
- `references/statistical-completeness.md`（缺失——要点已内联）
- `references/decision-oriented-analysis.md`（缺失——要点已内联）
- `references/EVIDENCE-PROPAGATION.md`（缺失——要点已内联）
- `examples/example-results-report.md`（缺失——要点已内联）
