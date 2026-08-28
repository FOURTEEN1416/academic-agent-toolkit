# Task Plan: Phase 1 Infrastructure Completion

## Goal
Complete Phase 1 infrastructure from the handover, CodeSucker fusion design, and systematic upgrade plan: a general STEP_MANIFEST protocol, quality gate integration, and four stable bridge tools.

## Route And Risk
- Primary route: 开发执行 after 接管项目 baseline.
- Task depth: 标准任务, because this touches engine infrastructure, tools, and tests but stays inside the accepted architecture.
- Authorization boundary: implement Phase 1 from `docs/superpowers/plans/2026-08-18-systematic-audit-and-upgrade.md` lines 106-165; do not start Phase 2 template/domain upgrades yet.

## Phases
- [x] Phase 1: Read handover, fusion design, and system upgrade plan
- [x] Phase 2: Inspect current engine/tool/test owners and working tree
- [x] Phase 3: Complete STEP_MANIFEST protocol and generic quality gate
- [x] Phase 4: Implement stable bridges: latex, solver, citation, visual
- [x] Phase 5: Add/adjust pytest coverage for protocol, gates, and bridges
- [x] Phase 6: Run full verification and record delivery status
- [x] Phase 7: Implement 5 named gates: paper_consistency / citation_integrity / experiment_reproduc / figure_provenance / compilation_log
- [x] Phase 8: Nested metadata merge in template_resolver (Phase 6 standard)
- [x] Phase 9: Batch migration of 39 templates via tools/upgrade_templates.py
- [x] Phase 10: Upgrade 40 SKILL.md with STEP_MANIFEST production declaration
- [x] Phase 11: Provenance ledger: check_provenance.py + 9 UPSTREAM.md files
- [x] Phase 12: Close audit-report-identified final audit gap with a machine-backed `AUDIT_REPORT.json` generator and CLI path
- [x] Phase 13: Tighten CodeSucker source-materials gate to enforce manifest, report, rendered hashes, and page limits
- [x] Phase 14: Remove pytest collection conflict from legacy CodeSucker demo script
- [x] Phase 15: Convert soft review model mismatch into hard fail for comp-final-review (strict_model_match)
- [x] Phase 16: Fix broken test setup ordering (write all files before manifest, include verdict in declared outputs)
- [x] Phase 17 (2026-08-28): 文档治理 — 盘点 dev-docs 真源骨架（不重建）、探针校准 225 tests、补 LOG.md、刷新 truth-index
- [x] Phase 18 (2026-08-28): ZCode 兼容层 — 根 AGENTS.md + .zcode/config.json(docsearch MCP) + .zcode/skills 联结（gitignored）
- [x] Phase 19 (2026-08-28): 科研绘图扩展 — fork 10 上游仓库（vendor/forks 暂存），集成 9 技能 + UPSTREAM.md 溯源 + catalog 入册 scientific_plotting_expanded
- [x] Phase 20 (2026-08-28): 全量文档治理 — 3 审计代理通读 45+ 文档 + 手工 legacy 逐字节比对；17 份加"仅供追溯"横幅；修 COMP_REVIEW 损坏声明/INVENTORY 拼接段/CHANGELOG 许可矛盾/b4 标题诚实化/LESSONS M6/README 过期声明
- [x] Phase 21 (2026-08-28): 命名对齐科研工具箱定位 — 数学建模全流程套件/ → 科研工具箱/（git mv），15 活跃文件 80 处引用更新，历史 dated 快照保留原文
- [x] Phase 23 (2026-08-28): 全能力公开发布 — catalog 9 项 private_extension→experimental（用户裁定），CHANGELOG v1.1.0，本地发布包 releases/v1.1（269 能力/247 技能净化包）
- [x] Phase 22 (2026-08-28): 数学建模大赛工具集/ 整包归档至 dev-docs/archive/（零丢失核查，见 dev-docs/DELETION_LOG.md）；新增 acat-doc-governance 技能 + /doc-governance 命令

## Key Questions
1. Does `STEP_MANIFEST.json` capture input hashes, config, output hashes, backend, commands, and dependencies robustly?
2. Do the four bridge tools provide stable CLI/JSON contracts and manifest-backed outputs without relying on temporary patches?
3. Does the full test suite prove Phase 1 infrastructure is integrated without breaking CodeSucker?

## Decisions Made
- Phase 1 scope is not a minimal patch. It is the full engine infrastructure slice described in the upgrade plan: manifest protocol, quality gate extension, and four stable bridge entrypoints.
- Phase 2 domain/template upgrades are explicitly out of scope for this task and should start only after Phase 1 has tests and clean verification.
- Bridge design choice: one shared `tools/bridge_common.py` plus one stable CLI script per concern, each writing a result JSON and a manifest-backed `STEP_MANIFEST.json`.
- Audit report follow-up: `PHASE1_PHASE6_AUDIT_REPORT.md` is treated as a gap signal, not as the deliverable. The real upgrade target is to make final delivery audit generation executable and testable.

## Errors Encountered
- Prior user-triggered task tool attempted planner orchestration and was cancelled; no usable subagent output was produced.
- `tests/test_quality_gates.py` initially failed during import because `engine/quality_gates.py` had an unindented `from .step_manifest` inside a `try:` block. Fixed the import structure and verified 35 tests pass.
- New step manifest tests exposed relative explicit manifest paths resolving against process CWD instead of workspace. Fixed `validate_manifest()` to resolve relative paths under workspace and reject manifest paths outside workspace.
- Phase 1 bridge tests confirmed the shared bridge contract, manifest output, and failure diagnostics across latex/solver/citation/visual paths.
- Final-audit follow-up initially exposed two test-design issues: a direct pending→completed transition (state machine correctly rejected it), and a CLI test that monkeypatched `ROOT` to an empty temp project. Fixed both by following the real runner transition path and using the real suite root for catalog loading.
- CodeSucker bridge initially failed because config provenance keys were being over-asserted against the manifest. The bridge now validates the canonical manifest fields without requiring CLI echo of bridge-only config metadata.
- The legacy `tools/test_end_to_end.py` demo script conflicted with `tests/test_end_to_end.py` during pytest collection; it has been renamed to `tools/codesucker_end_to_end_demo.py`.
- **复核发现（2026-08-19）**：`tests/test_end_to_end.py` 的两个多步工作流测试存在假阳性——`while True` 循环退出后未断言 `r.status == "completed"`，即使 `comp-paper-zh` 因 min_size（10000B > 5000B 写入）失败也会通过。已修复：execute_action 写入量提升至 16000B 满足全部门禁，并补充 `assert r.status == "completed"`。
- **复核清理（2026-08-19）**：删除 `tools/` 下 10 个 git 跟踪的历史 debug 脚本（debug_cumcm/debug_fig/debug_full/debug_gate/debug_manifest/debug_manifest2/debug_model/debug_model3/debug_size/debug_step1）。确认 `tools/run_cumcm_e2e.py` 与 `tools/test_workflow.py` 为已跟踪的手动验证脚本、不被 pytest 收集，保留。

## Status
All phases from the systematic upgrade plan are delivered, plus the audit-report follow-up gap is closed and the CodeSucker source-materials gate has been tightened. Final verification after re-audit and fixes: `python -m pytest -q` = 225 passed; `python tools/check_provenance.py` = 18/18 passed; CodeSucker core `npm test` = all 7 groups passed; CodeSucker 相关 18 项 pytest 全通过。
