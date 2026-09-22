# Academic Agent Toolkit — 仓库入口（宿主无关）

> 本仓库是一个**完整科研工具箱**（全学术 Agent 工具箱，6 大能力域），数模竞赛只是其一。
> **主控文档（单一真源）：[科研工具箱/AGENTS.md](科研工具箱/AGENTS.md)** —— 开工前必须先读它。
> **驱动协议**：任意能读文件、能执行 Python CLI 的智能体均可驱动本项目，不依赖特定宿主。
> 机器可读契约：`cd 科研工具箱 && python -m engine.workflow_cli boot`

## 驱动协议（任何 Agent）

1. 读本文件与 `科研工具箱/AGENTS.md`
2. `cd 科研工具箱 && python -m engine.workflow_cli boot` 取得契约
3. `python -m engine.workflow_cli probe` 探测能力与 TOOL_GAP
4. 缺工具时 `python -m engine.workflow_cli forge --tool/--skill ...`
5. 多步流程：`start` → `next` → 按 StepAction 执行 → `complete`（evidence.agent 自报你的工具名）
6. 单技能任务：按 `科研工具箱/AGENTS.md` §三 路由表直接读 SKILL.md

**主控 = 当前驱动本项目的 Agent。** 同一时刻只有一个主控；引擎（engine/）只编排不执行；
不存在「调用另一个 agent runtime」的逻辑。

**硬规则**：无证据＝未执行 · TOOL_GAP 不伪造通过 · 三振升级 · complete_step 必须附真实 evidence。

自举技能：`科研工具箱/skills/agent-bootstrap/` · 铸造技能：`科研工具箱/skills/tool-forge/`

## 可选宿主适配器（非驱动前提）

| 适配器 | 配置文件 | 状态 |
|------|----------|------|
| generic（协议层） | 无；`agents/adapters/generic/` | **默认可用**：AGENTS.md + skills/ + workflow_cli |
| OpenCode Desktop | `opencode.json` + 根级 `.opencode/`（插件 + subagent） | 可选适配器（L1 插件在此层生效） |
| ZCode | `.zcode/config.json` + `.zcode/skills/` + `.zcode/commands/` | 可选适配器（L1 hook 等价实现） |
| Claude Code / Cursor / MiMo 等 | 见 `agents/adapters/` | 可选；无配置也可直接按协议驱动 |

适配器元数据：`agents/adapters/*/adapter.json`。L1 拦截式审计在无宿主 hook 时记为
`unavailable`（不阻断）；L2（引擎）/L3（evidence）始终可用。

## OpenCode 可选适配说明（保留兼容）

- `.opencode/skills` 不需要；OpenCode 经 `opencode.json` 的 `skills.paths` 扫描 `./科研工具箱/skills`
- `opencode.json` 使用 `数模专家` 作为默认 primary agent（仅 OpenCode 用户）
- MCP 路径用占位符；本机绝对路径放在**未提交**本地覆盖中
- hook/配置变更后需重启对应宿主会话才生效

## ZCode 可选适配说明（保留兼容）

- `.zcode/skills` 是指向 `科研工具箱/skills` 的 NTFS 目录联结（不跟踪入 git）。
  重建：`cmd /c mklink /J .zcode\skills 科研工具箱\skills`
- L1 hooks：`科研工具箱/hooks/zcode_audit_l1.py`（fail-open；配置改动需重启会话）
- 审稿模型名须与 `engine/modex-core/contest_models.json` 或适配器 `models.json` 一致

## 仓库地图（治理入口）

| 路径 | 性质 |
|------|------|
| `科研工具箱/` | 产品主体：skills/engine/tools/tests/hooks/data |
| `capabilities/catalog.json` | 能力目录（技能须全部映射；根级 tests 硬校验） |
| `agents/adapters/` | 可选宿主适配器元数据（协议不依赖） |
| `docs/superpowers/` | 设计 spec 与实施计划（dated 快照） |
| `dev-docs/` | 内部真源根（gitignored 私有） |
| `LOG.md` / `task_plan.md` | 操作日志 / 任务与验证基线 |
| `releases/`（本地 dated 快照，不入库）、`tests/`、`SECURITY.md` | 发布快照 / 根级门禁测试 / 安全策略 |
| `参考论文/`、`赛前试炼任务/`、`workspaces/` 等 | 本地材料与产物（不入 git） |

## 硬性规则（冲突时以主控文档为准）

1. 引擎（engine/）只编排不执行；执行者是当前驱动 Agent。
2. 完成步骤必须回报 `complete_step` 并附 execution_evidence，禁止伪造审核产物。
3. 改代码后跑 `python -m pytest -q`（仓库根）+ `python 科研工具箱/tools/check_provenance.py`。
4. `dev-docs/` 是内部真源根，默认私有；`vendor/` 不入 git。
5. 文档治理遵守 `acat-doc-governance`：全文读完、污染必清。
6. **路径/密钥卫生**：tracked 配置不得写本机绝对路径；`.env` 永不入库；
   `python 科研工具箱/tools/secret_scan.py --strict` 机检。

## 测试口径（2026-09-22 华为杯管线补齐轮实测，pytest.ini 为唯一真源）

| 运行位置 | 收集范围 | 基线 | 用途 |
|----------|---------|------|------|
| 仓库根 `pytest -q` | `科研工具箱/tests` + 根 `tests/` | **717 passed / 0 failed**（= 工具箱 **696** + 根级门禁 **21**；另 1 skipped） | 仓库级回归 |
| `科研工具箱/` 内 `pytest -q` | 工具箱自有 tests | **696 passed / 0 failed** | 技能验收基线（硬规则 3 口径） |
| 根 `tests/` 单跑 | catalog schema + 反 AI 工具集 | **21 passed** | catalog 改动后必跑 |
| **公开 clone / CI** | 已提交内容 | 以 CI 实测为准（历史：600+3 skipped @ run 35425878920） | 门禁 |

- 历史基线 628/603/460 为保留作历史的时点快照，见 `pytest.ini` 注释（公开侧口径真源）；`dev-docs/truth-index.md` 为内部副本，不入库。
- `releases/` 永不进测试收集。
- 新增技能必须：SKILL.md + catalog 映射 + CONTEST_SKILL_MAP 归类 + `build_skill_index.py --emit`。
