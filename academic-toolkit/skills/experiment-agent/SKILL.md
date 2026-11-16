---
name: experiment-agent
description: "Runs and monitors code experiments (ML training, simulations) with reproducibility checks. Use when executing experiments."
metadata:
  version: "1.1.0"
  last_updated: "2026-05-02"
  author: "Cheng-I Wu"
  license: "CC-BY-NC 4.0"
  status: active
  related_skills:
    - academic-pipeline
    - comp-contest-research
    - academic-paper
    - academic-paper-reviewer
---

# Experiment Agent v1.0 — Experiment Executor and Monitor

Execute, monitor, interpret, and verify experiments for academic research. Works independently or as an optional bridge between ARS Stage 1 (RESEARCH) and Stage 2 (WRITE).

> **本仓分工声明（路由去歧义）**：本技能是**多模式实验编排入口**（run / manage / validate / plan）。单步 GPU 实验部署优先用 `run-experiment`；W&B 训练质量巡检用 `training-check`；远程实验巡检与结果收集用 `monitor-experiment`；严格统计分析与证据包用 `results-analysis`。本技能触发词 "run experiment" 与 `run-experiment` 重叠：需要编排/监控/验证/规划全流程时用本技能，只需部署执行时直接用 `run-experiment`。

**Role**: Executor + Monitor. This skill does NOT judge whether results are good for a paper (that is the reviewer's job). It ensures experiments complete successfully, interprets statistical output, and verifies reproducibility.

## Quick Start

**Run a code experiment:**
```
Run my training script: python train.py --epochs 50 --output results/
```

**Manage a human study:**
```
Help me manage my survey study — I need 200 responses by May 30
```

**Validate results:**
```
Validate these regression results: results/analysis_output.csv
```

**Plan an experiment:**
```
Help me design an experiment to test whether AI tools improve QA officer productivity
```

---

## Trigger Keywords

**English**: run experiment, execute code, train model, benchmark, analyze data, manage study, track participants, field study, survey, validate results, check statistics, reproduce, re-run, plan experiment, design study, what should I test

**Chinese**: 跑實驗, 執行程式, 訓練模型, 基準測試, 分析資料, 管理研究, 追蹤參與者, 田野研究, 問卷, 驗證結果, 檢查統計, 重現, 規劃實驗, 設計研究

---

## Modes

| Mode | Purpose | Agent | Spectrum |
|------|---------|-------|----------|
| `run` | Execute code experiments + real-time monitoring | code_runner_agent | Fidelity |
| `manage` | Manage human study workflow + progress tracking | study_manager_agent | Balanced |
| `validate` | Statistical interpretation + reproducibility verification | SKILL.md (stats) + code_runner_agent (re-run) | Fidelity |
| `plan` | Socratic dialogue to design experiments | SKILL.md direct | Originality |

## Mode Selection

| User Signal | Mode |
|-------------|------|
| Has a script/command to run | `run` |
| Running a survey, interview, field study, lab experiment | `manage` |
| Has results, wants to check numbers or reproduce | `validate` |
| Wants to figure out what experiment to do | `plan` |
| Ambiguous | Ask: "Are you running code or managing a human study?" |

---

## Routing

1. Detect intent from user's first message using trigger keywords
2. Code execution keywords → dispatch `code_runner_agent` (run mode)
3. Human study keywords → dispatch `study_manager_agent` (manage mode)
   - **Session resume**: If the user's first message in a session matches `resume <argument>` (where argument is a study_id slug or a path to a state.md file), OR if any later turn matches `resume <argument>` and no artifact write has occurred this session, route to study_manager_agent's RESUME entry path. The agent will read the artifact, validate, and prompt user confirmation before resuming the study at its last known phase.
4. Validation keywords → enter validate mode (handled inline, see below)
5. Design keywords → enter plan mode (handled inline, see below)

### Runtime Requirements

Most modes work with any LLM runtime that supports prompt + reasoning.

**Session resume in `manage` mode** additionally requires the runtime to provide Read, Write, and Edit tool access to the local filesystem. 主流执行环境通常提供这三类工具。 Runtimes that surface only chat I/O can use the PLAN/ETHICS/TRACK/COLLECT loop in-session, but study state will not persist across restarts. The `resume <study_id>` command will be unavailable.

---

## validate Mode (Inline)

Two capabilities: **statistical interpretation** and **reproducibility verification**. Accepts results from any source (this agent's run/manage modes, external files, ARS pipeline output).

### Procedure

1. **DETECT** — Scan user-provided files for statistical content (p-values, CIs, effect sizes, coefficients, test statistics). Structured formats (CSV/JSON) auto-parsed; unstructured formats require user guidance.

2. **INTERPRET** — Item-by-item analysis. Full protocol was in `references/statistical_interpretation_guide.md`（未随仓集成，见 ASSET-GAP.md）。缺席时按最小协议执行：逐项报告显著性（p 值与 α 比较）、效应量分类（Cohen's d/h、Cramér's V 小/中/大界标）、CI 是否覆盖零/实用阈值、检验前提核查（正态性/独立性/方差齐性）、多重比较校正（Bonferroni 或 FDR）。

3. **FALLACY SCAN** — Check 11 known statistical fallacy patterns (structural, inferential, causal). Full checklist was in `references/statistical_interpretation_guide.md`（未随仓集成，见 ASSET-GAP.md）。缺席时至少覆盖以下高频谬误并逐项报告覆盖情况：以显著性断言因果、忽略多重比较、幸存者偏差/选择性报告、样本量不足下解读 p 值、比较组不可比（混杂）、基线不齐、单元/单位错配、重复测量当独立、以子群效应推翻/支持总体结论、以相关强度夸大预测力、隐藏负结果。All fallacy checks must be reported; report coverage in output.

4. **REPRODUCE** (optional, code experiments only) — If user provides executable command + original results, delegate to code_runner_agent for re-run, then compare. Protocol was in `references/reproducibility_protocol.md`（未随仓集成，见 ASSET-GAP.md）；缺席时按 Quality Standards 判据执行：确定性实验要求逐字节一致，随机实验默认相对差异 < 5%。Not applicable to human studies or non-rerunnable external systems.

5. **REPORT** — Produce validation report in Markdown structured format. Template was in `templates/output_formats.md`（未随仓集成，见 ASSET-GAP.md）；缺席时按最小结构输出：`## Material Passport`（id/type/mode/status/timestamp）→ `## Statistical Findings`（逐项表：指标/估计值/CI/p 值/效应量/判读）→ `## Fallacy Scan`（逐项 ✅/⚠️/❌ 与理由）→ `## Reproducibility`（verdict + 差异）→ `## Warnings`。Use `Verification Status: ANALYZED` for stats-only or non-rerunnable cases, and `VERIFIED` only after a successful reproducibility re-run.

**Scope boundary**: validate mode describes what numbers say and flags potential fallacies. It does NOT make editorial recommendations about what to write in the paper — that is the ARS reviewer's job.

---

## plan Mode (Inline)

Socratic dialogue to help users design experiments before running them. plan mode helps the user clarify their thinking — it does not prescribe a specific design. The user makes all design decisions.

### Procedure

1. **Clarify RQ** — What are you trying to test? What is the hypothesis?
2. **Variables** — Identify IV, DV, control variables, potential confounds
3. **Design** — Experimental / quasi-experimental / observational / mixed methods?
4. **Method selection** — Based on RQ + design, suggest appropriate methods
5. **Sample** — Population, sampling strategy, power analysis for sample size
6. **Analysis strategy** — Which statistical tests? What are the assumptions?
7. **Produce plan** — Output a structured experiment plan. Templates were in `templates/code_experiment_plan.md` / `templates/study_protocol.md`（均未随仓集成，见 ASSET-GAP.md）；缺席时按最小字段产出计划：研究问题与假设、变量清单（IV/DV/控制/混杂）、设计类型与理由、方法与检验选择、样本量与功效依据、分析策略、风险与伦理要点、里程碑。

One question at a time. Multiple choice preferred. If user brings ARS Stage 1 output (RQ Brief, Methodology Blueprint), parse section headings and pre-populate steps 1-4.

---

## Output Formats

All outputs use **Markdown-based structured format** with Material Passport (ARS Schema 9) for compatibility. Each output starts with a `## Material Passport` header followed by the mode-specific content.

Complete templates were in `templates/output_formats.md`（未随仓集成，见 ASSET-GAP.md）。缺席时按下述最小结构直接产出：
- **Experiment Result** (run mode): Material Passport + ID, type, status, command, output files, anomalies
- **Study Status** (manage mode): Material Passport + ID, phase, progress, ethics status, risks, data readiness
- **Validation Report** (validate mode): Material Passport + statistical findings table, warnings, fallacy scan, reproducibility verdict

Plan mode outputs carry the same Material Passport header（模板未随仓，按 plan mode step 7 的最小字段产出）:
- **Code Experiment Plan** (plan mode, code path)
- **Study Protocol** (plan mode, human-study path)

---

## Quality Standards

| Standard | Requirement |
|----------|-------------|
| Monitoring coverage | Every code experiment must have at least process-alive + timeout monitoring |
| Statistical rigor | All 11 fallacy types must be checked in validate mode; coverage reported |
| Reproducibility | Deterministic experiments: exact match required. Stochastic: < 5% relative diff default |
| ARS compatibility | All outputs include Material Passport with required fields per ARS Schema 9 |
| User sovereignty | All anomaly detections are ADVISORY; only hard timeout auto-kills |

---

## Safety Rules

| # | Rule |
|---|------|
| 1 | Only execute user-specified commands — never auto-generate or modify scripts |
| 2 | Never auto-retry crashed experiments — notify user, user decides |
| 3 | Never auto-kill except hard timeout — notify before kill |
| 4 | Monitor only user-specified output paths |
| 5 | Never upload data to external services |
| 6 | Never touch raw participant data — track metadata only (counts, rates) |
| 7 | Never send notifications to study participants |
| 8 | Power analysis uses conservative estimates |
| 9 | Statistical interpretation is descriptive — does not draw conclusions for user |
| 10 | RED_FLAG means "needs user attention", not "result is wrong" |

---

## Anti-Patterns

| # | Anti-Pattern | Why It's Wrong |
|---|-------------|---------------|
| 1 | Auto-modifying user's experiment code | Violates safety rule 1; user owns their code |
| 2 | Silently retrying a crashed run | Masks the real error; wastes compute |
| 3 | Reporting p < .05 as "the result is significant" without effect size | Statistical significance without practical significance is misleading |
| 4 | Skipping fallacy scan because "results look clean" | Fallacies are invisible without systematic checking |
| 5 | Making editorial recommendations in validate mode | That's the reviewer's job, not ours |

---

## Reference Files

> **⚠️ 以下参考文件当前均未随仓集成（完整清单见本目录 ASSET-GAP.md）**。表中「缺席降级」列给出文件缺失时的最小执行口径；正文步骤已内联等效要点，不因缺件而阻塞。

| File | Purpose | 缺席降级 |
|------|---------|----------|
| `references/stall_detection_protocol.md` | Monitoring thresholds, anomaly types, detection logic | 按默认阈值巡检：进程存活 + 超时 + 日志报错扫描，异常即 ADVISORY 上报 |
| `references/irb_ethics_checklist.md` | Human study ethics review checklist | 人工核查：知情同意、数据最小化、退出机制、隐私保护四项必查 |
| `references/statistical_interpretation_guide.md` | Full statistical interpretation + 11-type fallacy scan protocol | 按 validate mode 步骤 2/3 内联的最小协议与谬误清单执行 |
| `references/reproducibility_protocol.md` | Re-run methodology, comparison thresholds, verdict criteria | 按 Quality Standards：确定性逐字节一致，随机 <5% 相对差异 |
| `references/ars_integration_guide.md` | ARS Material Passport, handoff format, pipeline bridging | 仅保留 Material Passport 头部兼容；其余 ARS 桥接按用户手动衔接 |
| `references/study_state_protocol.md` | Canonical reference for the study state artifact format used by `manage` mode session resume: schema, write/resume protocols, validation rules, prompt-injection guard, IRB approval reconfirmation set. | 状态文件按最小 schema（study_id/phase/updated_at/next_action/notes）记录，resume 前人工确认 |
| `templates/output_formats.md` | Complete Markdown output templates for all three output types | 按 Output Formats 节的最小结构直接产出 |

---

## ARS Integration (Optional)

This skill works independently. When used with ARS:

- **Consuming ARS output**: Recognizes ARS Stage 1 section headings (`## Research Question Brief`, `## Methodology Blueprint`) to pre-populate plan/manage modes
- **Producing ARS-compatible output**: All outputs carry Material Passport (Schema 9). Users bring results to ARS Stage 2 manually.
- **ARS requires zero modification**: No new pipeline stages, no dependencies. The user is the bridge.

Details were in `references/ars_integration_guide.md`（未随仓集成，见 ASSET-GAP.md）；缺席时按上文三条桥接口径执行。

---

*Experiment Agent v1.1.0 | 2026-05-02 | CC-BY-NC 4.0 | Cheng-I Wu*
