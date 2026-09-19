# Academic Agent Toolkit — 仓库入口（宿主中立）

> 本仓库是一个**完整科研工具箱**（全学术 Agent 工具箱，6 大能力域），数模竞赛只是其一。
> **主控文档（单一真源）：[科研工具箱/AGENTS.md](科研工具箱/AGENTS.md)** —— 开工前必须先读它。
> 它定义架构、三层审计、入口路由、质量门禁与工作流引擎的使用方式。

## 宿主支持矩阵

| 宿主 | 配置文件 | 状态 |
|------|----------|------|
| OpenCode Desktop | `opencode.json` + 根级 `.opencode/`（插件 + subagent） | 正式宿主（L1 拦截式审计插件在此层生效） |
| ZCode | `.zcode/config.json` + `.zcode/skills/` + `.zcode/commands/` | **赛时主控宿主**（2026-09-09 起）：L1 审计 hook 等价实现（`科研工具箱/hooks/zcode_audit_l1.py`，PreToolUse/PostToolUse/PostToolUseFailure 写同一 `operations.jsonl`）——**2026-09-11 经用户裁定重启用**（从 64dbd56 恢复形态；契约测试 23/23+引导器落账实测通过；重启会话后宿主自动触发）；技能/引擎/门禁与 OpenCode 全一致 |

## ZCode 主控层说明

- `.zcode/skills` 是指向 `科研工具箱/skills` 的 NTFS 目录联结（不跟踪入 git）。
  重建命令（仓库根，管理员非必需）：
  `cmd /c mklink /J .zcode\skills 科研工具箱\skills`
- `.zcode/config.json` 提供 docsearch MCP（与 OpenCode 同一 server，workspace 级自动连接）与
  **hooks 块（L1 审计，已启用）**：2026-09-11 用户针对"门禁博弈（Goodhart）"威胁裁定重启用，
  从 git 64dbd56 恢复内联引导器形态（PreToolUse 拦截/PostToolUse 落账/PostToolUseFailure 三事件，
  fail-open 铁律：hook 自身故障 stderr 警告+exit 0 放行，exit 2 唯一来源=治理规则命中且必留痕）。
  复验记录：契约测试 23/23、引导器 stdin 模拟落账 +1 条、双口径 270/314 全过（同日盲审两轮回炉后基线升至 379/423，见 LOG 续8/续9）。
  **hook 配置改动需重启会话生效**——下次新会话起宿主自动触发落账。
- **L1 hook 能力**（OpenCode 插件不具备的宿主机制，反向利用；脚本在库、2026-09-11 起已注册启用，预案与历史见 LOG 续6）：宿主层触发、agent 不可绕过；
  PreToolUse 可按治理铁律拦截（如 `git add .` 强制逐文件点名）；落账格式与插件一致，
  L3 交叉比对（`workflow_cli audit` / `detect_unreported_operations`）零改动可用。
- `.zcode/commands/doc-governance.md` 提供 `/doc-governance` 文档治理命令；
  治理规程本体在技能 `acat-doc-governance`（含用户铁律：治理必须全文读完所有文档、污染源必清理）。
- ZCode 下审稿角色（数模审稿人/数模视觉审查等）以通用子智能体（Agent 工具）承担；
  审核证据的模型名必须与 `科研工具箱/engine/modex-core/contest_models.json`（已按 2026-09-10
  用户裁定配置 agnes/agnes-2.5-flash，换模型须同步本文件与证据声明）或 OpenCode 宿主 agent 配置一致，strict 门禁据此硬拦。
- 赛前自检：`python 科研工具箱/tools/contest_dryrun/chain_driver.py`（14 步全链 + 硬闸 + 真编译，
  链路验证级，详见该目录 README）。

## 仓库地图（治理入口）

| 路径 | 性质 |
|------|------|
| `科研工具箱/` | 产品主体：skills(260 个技能；262 目录含 _utils/shared-scripts 两个非技能目录；2026-09-19 实测)/engine/tools/tests/hooks(L1 已启用)/data |
| `capabilities/catalog.json` | 能力目录（307 条，2026-09-19 实测；六域分布 35/74/42/83/12/61） |
| `docs/superpowers/` | 设计 spec 与实施计划（dated 快照，仅供追溯） |
| `dev-docs/` | 内部真源根（gitignored 私有）：truth-index 入口索引、archive/ 归档区 |
| `LOG.md` / `task_plan.md` | 操作日志 / 当前任务与验证基线 |
| `releases/`、`governance/`、`tests/` | 发布包快照 / 资产台账 / 根级门禁测试（19 项） |
| `benchmarks/` | ⚠️ **2026-09-19 起废弃入库**（公开基准集，内容零丢失归档 `dev-docs/archive/legacy-benchmarks-tests-20260919/`）；私有层 `benchmarks/cumcm_private/` 从未入库，**已永久丢失** |
| `参考论文/` | 62 篇获奖论文统计分析资产（本地，不入 git） |
| `赛前试炼任务/`、`extracted_images/`、`logs/`、`workspaces/` | 本地敏感练习材料与运行产物（均不入 git） |
| `vendor/forks/` | 上游 fork 暂存区（不入 git） |

## 硬性规则（继承自主控文档，冲突时以主控文档为准）

1. 引擎（engine/）只编排不执行；执行者是当前 agent。
2. 完成步骤必须回报 `complete_step` 并附 execution_evidence，禁止伪造审核产物。
3. 改代码后跑 `python -m pytest -q`（科研工具箱/ 下）+ `python tools/check_provenance.py`。
4. `dev-docs/` 是内部真源根，默认私有；`vendor/` 是上游 fork 暂存区，不入 git。
5. 文档治理任务遵守 `acat-doc-governance` 技能铁律：全文读完、污染必清、不窄化定位。

## 测试口径（2026-09-19 实测，pytest.ini 为唯一真源）

| 运行位置 | 收集范围 | 基线 | 用途 |
|----------|---------|------|------|
| 仓库根 `pytest -q` | `科研工具箱/tests` + 根 `tests/`（pytest.ini 限定） | **460 passed / 0 failed**（2026-09-19 实测 85.3s，junit 取证，0 error / 0 skipped）。修复过程留痕：首测为 459 + 1 failed，唯一失败项 `科研工具箱/tests/test_quick_gates.py::test_page_check_bad_pdf_errors_without_raising` 根因是 `.venv311` 缺 `pypdf`（缺库时 `_page_check` 返回 SKIP，而测试断言 ERROR）——**非代码缺陷**，补包后转全绿；CI 已固化 `pypdf` 依赖 | 仓库级回归 |
| `科研工具箱/` 内 `pytest -q` | 工具箱自有 tests（441 = 460 − 根级门禁 19） | **441 passed / 0 failed** | 技能验收基线（硬规则 3 口径） |
| 根 `tests/` 单跑 | catalog schema 硬校验 + 反 AI 工具集检查 | **19 passed**（0.30s） | `capabilities/catalog.json` 改动后必跑 |

- ⚠️ **2026-09-19 口径更替**：本表原记"仓库根 452 全量 / 工具箱 408 全量"（2026-09-12 快照）**已失效**——公开基准集 `benchmarks/` 经用户裁定废弃入库（77 文件零丢失归档 `dev-docs/archive/legacy-benchmarks-tests-20260919/`），其唯一依赖测试 `tests/test_cumcm_benchmark.py` 同步移除。经依赖核查，`tests/test_minimum_catalog.py`（仅依赖 `capabilities/catalog.json`）与 `tests/test_anti_ai_toolkit.py`（仅依赖 `科研工具箱/tools`）为**独立门禁，已保留入库**，故 `testpaths` 保留 `tests`。旧口径中"test_cumcm_benchmark 25 项暂不可收集"的算术不再适用。

- 原 6 个 skip 为 hooks 清除态下 D 段注册契约测试（`2a86b6c` 定稿）走"皆无→skip"；2026-09-11 L1 重启用后转真实运行并全过（2026-09-11 实测）。

- `releases/` 是 dated 发布快照（archive 态仅供追溯），**永不进测试收集**——其内部旧测试依赖旧目录结构，扫描必炸（2026-09-03 曾致 333 collection errors）。
- `科研工具箱/tools/` 下的 `test_*.py` 是裸脚本式自检（硬编码 cwd 相对路径），不属于 pytest 套件，从仓库根收集排除。
- `capabilities/catalog.json` 改动后必跑根级 tests：schema 有硬校验（capability_id 用短横线命名=技能映射条目；下划线命名=聚合能力须带 4 个合同扩展字段；status 仅限 experimental/private_extension/正式；全部 skills 目录必须有映射）。
