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
- [x] Phase 24 (2026-09-19): 仓库治理收口（用户裁定）——①公开基准集 `benchmarks/` 废弃入库：77 文件/112 KB **零丢失**归档 `dev-docs/archive/legacy-benchmarks-tests-20260919/`（含 README 损失清单 + manifest.tsv 逐文件 sha256）；②依赖核查后**收窄废弃范围**——仅移除 `tests/test_cumcm_benchmark.py`，`test_minimum_catalog.py`/`test_anti_ai_toolkit.py` 两个独立门禁保留入库（故 pytest.ini 保留 `tests`）；③`.zcode/skills` NTFS 联结重建（旧联结指向已失效的 `D:\Desktop\数模竞赛` → ZCode 技能链断裂，现已恢复 260 技能可见）；④基线口径全仓统一为 2026-09-19 实测值（460 收集）；⑤新增 CI 最小集
- [x] Phase 26 (2026-09-20): **宿主无关 · 自适应 Agent 泛化改造**（详见 `docs/superpowers/specs/2026-09-20-host-agnostic-adaptive-agent.md`）——①引擎深度重构：`agent_bridge.py` canonical + `opencode_bridge.py` shim；evidence/默认 agent 标签改为 `acat-agent`（自由字符串）；quality_gates 模型解析链泛化（contest → adapters/*/models.json → 可选宿主目录，显式 env 覆盖时不扫默认宿主）；②新增 `agent_protocol`/`capability_probe`/`tool_forge` + CLI `boot`/`probe`/`forge`（boot/probe/forge 惰性加载重型依赖）；③旧宿主降为可选适配器（`agents/adapters/*`，协议不依赖）；④文档入口泛化（根/工具箱 AGENTS.md + README）+ 技能 `agent-bootstrap`/`tool-forge` 入册入图入索引；⑤测试基线 628→**639**（620+19）
- [x] Phase 27 (2026-09-20): **收尾整理**——清 `__pycache__`/`.pytest_cache`/`workflow-index.json`（保留 .engine 审计/SQLite 与 tools/*.pyc）；CHANGELOG/LOG/README/CLAUDE.md/galaxy-*/acat-doc-governance/CROSS_PROJECT 措辞与路径同步；opencode/zcode 配置标 optional 适配器；徽章 skills 263 / capabilities 310；复验 pytest **639** + health 整体健康
- [x] Phase 28 (2026-09-21/22): **系统升级四批收编合仓**（多窗口第五轮；wt/batch1~4 `--no-ff` 并入 main，详见 LOG 续42/续43 与 CHANGELOG v1.3.0）——①batch1 缺陷快修九项（12c7e50：恒真断言、反 AI 检测器基线加载链与退出码契约、case_fetcher 统计自洽、个人路径占位化、secret_scan 家目录 WARN→FAIL、lint 基线相对路径、gpt_image 第三方域名去硬编码、arxiv_miner 隐式依赖与空元素、plotting_env_check `--strict`）；②batch2 公开面与口径八项（01bf509：**CHANGELOG 定版 v1.3.0**、真源指针公开侧改写、技能计数双轨（tracked/盘面）、`科研工具箱/baseline/` 吞件陷阱修复、快速开始补依赖安装步、LICENSE 与历史引用本地性修正）；③batch3 机制补强九项（de2280d：RunLogger 落盘链路接通、workflow-index 原子写与回退、CLI 错误契约 + `--evidence-file`、catalog 双向校验 + 补齐、`--help` 契约冒烟扩容、断链棘轮盲区四类、适配器三方对账、**门禁互检去重**（全量 153.77s→93.18s，**-39.4%**）、17 工具零覆盖分档）；④batch4 产品能力（2e2fdf1：管线模板 `academic_outputs`（poster→slides）与 `course_teaching`、写论文/审稿循环/文献三簇仲裁表、§三路由表扩容、auto_review 模板 required_checks 补齐）；⑤收官 35ebb8f：asset_gap_register 处置（批次四领地 3 条销账 + 2 条目录补过期台账）、plotting_env_check 入 CLI `--help` 名单（33→34）、**基线口径统一回填 717**（根级 pytest = 工具箱 **696** + 根级门禁 **21**，另 1 skipped = docx_template_fill 钉住；本轮前置为 09-22 华为杯管线补齐 8→14 步与国赛同构，中间基线 651）

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

> ⚠️ **本节正文为 2026-08-30 时点快照**（保留作历史）。当前唯一有效基线（**2026-09-22 四批收编合仓收官实测**）：
> 根级 `pytest -q` = **717 passed / 0 failed**（= 工具箱 **696** + 根级门禁 **21**，另 **1 skipped**）——
> 口径真源见根 `AGENTS.md` §测试口径 与 `pytest.ini` 注释（公开侧口径唯一真源），内部副本 `dev-docs/truth-index.md` §当前基线。
> 历史时点快照（诚实保留，勿当现值）：2026-08-30 = 242 passed / provenance 28/28 / 245 技能；
> 2026-09-19 两轮升级后 = 576（工具箱 441 + 根级门禁 19，provenance 66/66、catalog 307 条 / 260 技能）；
> 2026-09-20 宿主无关轮 = 639（620+19）；2026-09-22 华为杯管线补齐轮 = 651（630+21）。

All phases delivered（历史记录见下方 Errors/Decisions）。2026-08-30 历史时点验证快照：
- `python -m pytest -q` = **242 passed**（三管线/逐技能/绘图域回归含内）
- `python tools/check_provenance.py` = **28/28**（27 台账 + vendor）
- `tools/skill_library_audit.py` = OK（245 skills / 44 templates / template_missing_skill=0）
- 逐技能 C2：245 单技能条目 100% 验收状态分类（207 真实证据 + 38 诚实 blocked），留档 workspaces/skill_c2_batch1-19
- v1.2.0 已发布（GitHub Release）；全库已同步 GitHub（HEAD 见 git log）
