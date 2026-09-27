# ASSET-GAP 资产缺口声明 — paper-writing-pipeline

> 2026-09-28 深读批补登，上游资产未随本仓集成：以下条目为 SKILL.md 正文实际引用（含 File Structure 声明逐件枚举）、盘上缺失、且未经内联标记/登记册棘轮/本清单三渠道豁免的资产。本仓集成时仅收 references/（29 件已在库）与 scripts/check_pipeline_integrity.py；agents/、templates/、examples/ 及上游版式路径（shared/、docs/、AGENTS.md）均未随本仓集成。
> 口径说明：①正文以 `academic-paper/agents/draft_writer_agent.md`、`academic-paper/agents/peer_reviewer_agent.md` 别名引用的即下列 agents/ 文件，不重复列；②File Structure 中 10 个模板基名按同列 `latex_article_template.tex` 例外推断为 `.md`，其中 revision_tracking 采用正文精确内联路径 `templates/revision_tracking_template.md`；③`AGENTS.md` 指上游仓根路由文档（"Routing Discipline (v3.9.2)"）；④跨技能断链按"登记在引用方"口径列于本清单（academic-pipeline、academic-paper-reviewer 两技能目录在本仓不存在，comp-contest-research 存在但缺该 references 文件）；⑤references/ 内 19+ 件、scripts/check_pipeline_integrity.py、comp-contest-research/SKILL.md 已真实在库，不列。

## 缺失资产清单（47 项，2026-09-28 审计）

agents/（12 件，正文 File Structure："one file per agent (12 total)"）：

- `agents/intake_agent.md`
- `agents/literature_strategist_agent.md`
- `agents/structure_architect_agent.md`
- `agents/argument_builder_agent.md`
- `agents/draft_writer_agent.md`
- `agents/citation_compliance_agent.md`
- `agents/abstract_bilingual_agent.md`
- `agents/peer_reviewer_agent.md`
- `agents/formatter_agent.md`
- `agents/socratic_mentor_agent.md`
- `agents/visualization_agent.md`
- `agents/revision_coach_agent.md`

templates/（11 件）：

- `templates/imrad.md`
- `templates/literature_review.md`
- `templates/case_study.md`
- `templates/theoretical_paper.md`
- `templates/policy_brief.md`
- `templates/conference_paper.md`
- `templates/latex_article_template.tex`
- `templates/bilingual_abstract.md`
- `templates/credit_statement.md`
- `templates/funding_statement.md`
- `templates/revision_tracking_template.md`

examples/（9 件）：

- `examples/imrad_hei_example.md`
- `examples/literature_review_example.md`
- `examples/plan_mode_guided_writing.md`
- `examples/chinese_paper_example.md`
- `examples/revision_mode_example.md`
- `examples/revision_recovery_example.md`
- `examples/clinical_citation_verification_checklist.md`
- `examples/clinical_epistemic_status_example.md`
- `examples/version_family_reconciliation_example.md`

shared/（7 件，上游版式路径）：

- `shared/style_calibration_protocol.md`
- `shared/references/intent_clarification_protocol.md`
- `shared/raise_framework.md`
- `shared/mode_spectrum.md`
- `shared/sprint_contract.schema.json`
- `shared/contracts/writer/full.json`
- `shared/contracts/evaluator/full.json`

docs/（2 件，上游版式路径）：

- `docs/design/2026-05-18-ars-v3.9.2-agent-phase-classification.md`
- `docs/design/2026-04-27-ars-v3.6.6-generator-evaluator-contract-design.md`

上游仓根（1 件）：

- `AGENTS.md`

跨技能断链（5 件，登记在引用方）：

- `academic-pipeline/SKILL.md`
- `academic-pipeline/references/passport_as_reset_boundary.md`
- `academic-pipeline/agents/integrity_verification_agent.md`
- `academic-paper-reviewer/references/sprint_contract_protocol.md`
- `comp-contest-research/references/apa7_style_guide.md`

## 处置口径

- 本声明使上述断链显性化（audit 豁免），删除本文件前必须先补齐资产或登记新台账。
- 若后续获得上游来源：按先 fork 后集成惯例拉取 → 补 UPSTREAM.md 台账 → 从 tools/asset_gap_register.json 删除对应条目 → 删除本声明。

## 补登（2026-09-28 第二轮：references/revision_patch_protocol.md 等指向的 scripts/）

- `scripts/ars_apply_revision_patch.py`
- `scripts/revision_roadmap.py`
- `scripts/_block_parser.py`
- `scripts/ars_anchorize_draft.py`

（policy_anchor_table.md、policy_anchor_disclosure_protocol.md、committee_correspondence_protocol.md、
citation_styles.md、imrad_structure.md、reporting_guidelines.md、vlm_figure_verification.md 各自指向的
其余 scripts/* 未在深读中逐一定名，收编时按正文逐文件核对补列。）

## 补登（2026-09-28 逐行轮：references/ 内部引用的上游 scripts）

- `scripts/ars_anchorize_draft.py`（revision_patch_protocol.md）
- `scripts/ars_apply_revision_patch.py`（同上）
- `scripts/_block_parser.py`（同上）
- `scripts/revision_roadmap.py`（同上）
- `scripts/verify_submission_package.py`（同上 :164）
- `scripts/check_policy_anchor_table.py` 及其 test（policy_anchor_table.md:8）
- `scripts/policy_anchor_disclosure_referee.py`（policy_anchor_disclosure_protocol.md）
- `scripts/check_policy_anchor_protocol.py`（同上 :199-200）
- `scripts/test_policy_anchor_disclosure.py`（同上）
- `scripts/check_committee_correspondence.py`（committee_correspondence_protocol.md:11,156）
