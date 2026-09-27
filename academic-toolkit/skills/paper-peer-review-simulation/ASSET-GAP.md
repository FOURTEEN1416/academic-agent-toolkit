# ASSET-GAP 资产缺口声明 — paper-peer-review-simulation

> 2026-09-28 深读批补登，上游资产未随本仓集成：以下条目为正文实际引用、盘上缺失、
> 且未经内联标记/登记册棘轮/本清单三渠道豁免的资产。

## 缺失资产清单（6 项，2026-09-28 审计）

- `shared/sprint_contract.schema.json`（scripts/check_sprint_contract.py:21 硬编码依赖，缺它该脚本 load_schema() 必抛 FileNotFoundError）
- `scripts/check_phase_conformance.py`
- `scripts/check_panel_synthesis.py`
- `scripts/check_re_review_synthesis.py`
- `scripts/recompute_receipts.py`
- `scripts/review_panel_provenance.py`

## 缺失资产清单（第二批补登，2026-09-28 逐件核对）

> 以下均为 SKILL.md 正文/引用表实际引用、盘上确认缺失的资产（上游 ARS 资产未随本仓集成）。
> `shared/sprint_contract.schema.json` 已在上方首批清单登记，此处不重复。

### agents/（7 件，对应 SKILL.md「Agent File References」表逐件核对）

- `agents/field_analyst_agent.md`
- `agents/eic_agent.md`
- `agents/methodology_reviewer_agent.md`
- `agents/domain_reviewer_agent.md`
- `agents/perspective_reviewer_agent.md`
- `agents/devils_advocate_reviewer_agent.md`
- `agents/editorial_synthesizer_agent.md`

### templates/（3 件）

- `templates/peer_review_report_template.md`
- `templates/editorial_decision_template.md`
- `templates/revision_response_template.md`

### examples/（2 件）

- `examples/hei_paper_review_example.md`
- `examples/interdisciplinary_review_example.md`

### shared/ 与 docs/design/

- `shared/references/intent_clarification_protocol.md`
- `shared/mode_spectrum.md`
- `shared/contracts/reviewer/full.json`
- `shared/contracts/reviewer/methodology_focus.json`
- `docs/design/2026-05-18-ars-v3.9.2-agent-phase-classification.md`

### 路由目标缺位

- 根 `AGENTS.md` 的 "Routing Discipline (v3.9.2)" 节（SKILL.md 路由纪律与直连模式两处引用）——上游 ARS 适配残留，本仓替代：评审修订链回 paper-write 族
- `related_skills` 路由目标 `academic-paper`（上游供稿 / 下游修订模式）——上游 ARS 适配残留，本仓替代：评审修订链回 paper-write 族
- `related_skills` 路由目标 `academic-pipeline`（orchestrator Stage 3 编排依赖）——上游 ARS 适配残留，本仓替代：评审修订链回 paper-write 族
- `related_skills` 路由目标 `tw-hei-intelligence`（高教数据核验依赖）——上游 ARS 适配残留，本仓替代：评审修订链回 paper-write 族
