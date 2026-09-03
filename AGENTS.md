# Academic Agent Toolkit — 仓库入口（宿主中立）

> 本仓库是一个**完整科研工具箱**（全学术 Agent 工具箱，6 大能力域），数模竞赛只是其一。
> **主控文档（单一真源）：[科研工具箱/AGENTS.md](科研工具箱/AGENTS.md)** —— 开工前必须先读它。
> 它定义架构、三层审计、入口路由、质量门禁与工作流引擎的使用方式。

## 宿主支持矩阵

| 宿主 | 配置文件 | 状态 |
|------|----------|------|
| OpenCode Desktop | `opencode.json` + 根级 `.opencode/`（插件 + subagent） | v1 唯一正式宿主（L1 拦截式审计插件在此层生效） |
| ZCode | `.zcode/config.json` + `.zcode/skills/` + `.zcode/commands/` | 兼容层（2026-08-20 起）；L1 审计插件暂无 ZCode 等价物，审计降级为 L2+L3 |

## ZCode 兼容层说明

- `.zcode/skills` 是指向 `科研工具箱/skills` 的 NTFS 目录联结（不跟踪入 git）。
  重建命令（仓库根，管理员非必需）：
  `cmd /c mklink /J .zcode\skills 科研工具箱\skills`
- `.zcode/config.json` 提供 docsearch MCP（与 OpenCode 同一 server，workspace 级自动连接）。
- `.zcode/commands/doc-governance.md` 提供 `/doc-governance` 文档治理命令；
  治理规程本体在技能 `acat-doc-governance`（含用户铁律：治理必须全文读完所有文档、污染源必清理）。
- ZCode 下子智能体（数模审稿人/数模视觉审查）暂无配置等价物；涉及审核类步骤时
  按 AGENTS.md 的 requires_subagent 规则用通用 subagent 能力替代，并保留证据链。

## 仓库地图（治理入口）

| 路径 | 性质 |
|------|------|
| `科研工具箱/` | 产品主体：skills(247)/engine/tools/tests/data |
| `capabilities/catalog.json` | 能力目录（269 条） |
| `docs/superpowers/` | 设计 spec 与实施计划（dated 快照，仅供追溯） |
| `dev-docs/` | 内部真源根（gitignored 私有）：truth-index 入口索引、archive/ 归档区 |
| `LOG.md` / `task_plan.md` | 操作日志 / 当前任务与验证基线 |
| `benchmarks/`、`releases/`、`governance/`、`tests/` | 基准集 / 发布包 / 资产台账 / 根级测试 |
| `参考论文/` | 62 篇获奖论文统计分析资产（本地，不入 git） |
| `赛前试炼任务/`、`extracted_images/`、`logs/`、`workspaces/` | 本地敏感练习材料与运行产物（均不入 git） |
| `vendor/forks/` | 上游 fork 暂存区（不入 git） |

## 硬性规则（继承自主控文档，冲突时以主控文档为准）

1. 引擎（engine/）只编排不执行；执行者是当前 agent。
2. 完成步骤必须回报 `complete_step` 并附 execution_evidence，禁止伪造审核产物。
3. 改代码后跑 `python -m pytest -q`（科研工具箱/ 下）+ `python tools/check_provenance.py`。
4. `dev-docs/` 是内部真源根，默认私有；`vendor/` 是上游 fork 暂存区，不入 git。
5. 文档治理任务遵守 `acat-doc-governance` 技能铁律：全文读完、污染必清、不窄化定位。

## 测试口径（2026-09-03 定稿，pytest.ini 为准）

| 运行位置 | 收集范围 | 基线 | 用途 |
|----------|---------|------|------|
| 仓库根 `pytest -q` | `科研工具箱/tests` + 根 `tests/`（pytest.ini 限定） | **285 passed** | 仓库级回归 |
| `科研工具箱/` 内 `pytest -q` | 工具箱自有 tests | **242 passed** | 技能验收基线（硬规则 3 口径） |

- `releases/` 是 dated 发布快照（archive 态仅供追溯），**永不进测试收集**——其内部旧测试依赖旧目录结构，扫描必炸（2026-09-03 曾致 333 collection errors）。
- `科研工具箱/tools/` 下的 `test_*.py` 是裸脚本式自检（硬编码 cwd 相对路径），不属于 pytest 套件，从仓库根收集排除。
- `capabilities/catalog.json` 改动后必跑根级 tests：schema 有硬校验（capability_id 用短横线命名=技能映射条目；下划线命名=聚合能力须带 4 个合同扩展字段；status 仅限 experimental/private_extension/正式；全部 skills 目录必须有映射）。
