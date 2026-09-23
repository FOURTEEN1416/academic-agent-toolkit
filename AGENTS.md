# Academic Agent Toolkit — 仓库入口（宿主无关）

> 本仓库是一个**完整academic-toolkit**（全学术 Agent 工具箱，6 大能力域），数模竞赛只是其一。
> **主控文档（单一真源）：[academic-toolkit/AGENTS.md](academic-toolkit/AGENTS.md)** —— 开工前必须先读它。
> **驱动协议**：任意能读文件、能执行 Python CLI 的智能体均可驱动本项目，不依赖特定宿主。
> 机器可读契约：`cd academic-toolkit && python -m engine.workflow_cli boot`

## 驱动协议（任何 Agent）

1. 读本文件与 `academic-toolkit/AGENTS.md`
2. `cd academic-toolkit && python -m engine.workflow_cli boot` 取得契约
3. `python -m engine.workflow_cli probe` 探测能力与 TOOL_GAP
4. 缺工具时 `python -m engine.workflow_cli forge --tool/--skill ...`
5. 多步流程：`start` → `next` → 按 StepAction 执行 → `complete`（evidence.agent 自报你的工具名）
6. 单技能任务：按 `academic-toolkit/AGENTS.md` §三 路由表直接读 SKILL.md

**主控 = 当前驱动本项目的 Agent。** 同一时刻只有一个主控；引擎（engine/）只编排不执行；
不存在「调用另一个 agent runtime」的逻辑。

**硬规则**：无证据＝未执行 · TOOL_GAP 不伪造通过 · 三振升级 · complete_step 必须附真实 evidence。

自举技能：`academic-toolkit/skills/agent-bootstrap/` · 铸造技能：`academic-toolkit/skills/tool-forge/`

## 可选宿主适配器（非驱动前提）

| 适配器 | 配置文件 | 状态 |
|------|----------|------|
| generic（协议层） | 无需配置 | **默认可用**：AGENTS.md + skills/ + workflow_cli |
| OpenCode Desktop | `opencode.json`（subagent 角色内联） | 可选适配器 |
| ZCode | `.zcode/skills/` 本地联结（不入 git） | 可选适配器（L1 hook 按本地未提交配置自建，契约见 academic-toolkit/tests/test_zcode_host_compat.py D 段） |
| Claude Code / Cursor / MiMo 等 | 无需专用配置 | 可选；直接按协议驱动 |

需要适配器元数据时 `python -m engine.workflow_cli forge --adapter <name>` 本地生成。
L1 拦截式审计在无宿主 hook 时记为
`unavailable`（不阻断）；L2（引擎）/L3（evidence）始终可用。

## OpenCode 可选适配说明（保留兼容）

- OpenCode 经 `opencode.json` 的 `skills.paths` 扫描 `./academic-toolkit/skills`，subagent 角色内联于该文件
- `opencode.json` 使用 `数模专家` 作为默认 primary agent（仅 OpenCode 用户）
- MCP 路径用占位符；本机绝对路径放在**未提交**本地覆盖中
- hook/配置变更后需重启对应宿主会话才生效

## ZCode 可选适配说明（保留兼容）

- `.zcode/skills` 是指向 `academic-toolkit/skills` 的 NTFS 目录联结（不跟踪入 git）。
  重建：`cmd /c mklink /J .zcode\skills academic-toolkit\skills`
- L1 hooks：`academic-toolkit/hooks/zcode_audit_l1.py`（fail-open），注册形态契约见
  `academic-toolkit/tests/test_zcode_host_compat.py` D 段
- 审稿模型名须与 `engine/modex-core/contest_models.json` 或适配器 `models.json` 一致

## 仓库地图（治理入口）

| 路径 | 性质 |
|------|------|
| `academic-toolkit/` | 产品主体：skills/engine/tools/tests/hooks/data |
| `capabilities/catalog.json` | 能力目录（技能须全部映射；一致性由工具箱 asset 系门禁 + `check_asset_utilization --strict` 守护，原根级 tests 硬校验已随 2026-09-23 适配层裁决退役） |
| `dev-docs/` | 内部真源根（gitignored 私有）：**操作日志 `dev-docs/LOG.md`（2026-09-23 起唯一记账真源，公开仓不分发）· 任务计划 `dev-docs/task_plan.md` · 审计报告** |
| `releases/`（本地 dated 快照，不入库）、`SECURITY.md`、`CHANGELOG.md` | 发布快照 / 安全策略 / 公开版本记录 |
| `assets-local/award-papers/`、`赛前试炼任务/`、`workspaces/` 等 | 本地材料与产物（不入 git） |

## 硬性规则（冲突时以主控文档为准）

1. 引擎（engine/）只编排不执行；执行者是当前驱动 Agent。
2. 完成步骤必须回报 `complete_step` 并附 execution_evidence，禁止伪造审核产物。
3. 改代码后跑 `python -m pytest -q`（仓库根）+ `python academic-toolkit/tools/check_provenance.py`。
4. `dev-docs/` 是内部真源根，默认私有；`vendor/` 不入 git。
5. 文档治理遵守 `meta-doc-governance`：全文读完、污染必清。
6. **路径/密钥卫生**：tracked 配置不得写本机绝对路径；`.env` 永不入库；
   `python academic-toolkit/tools/secret_scan.py --strict` 机检。

## 测试口径（2026-09-23 宿主适配层移除收口批实测，pytest.ini 为唯一真源）

| 运行位置 | 收集范围 | 基线 | 用途 |
|----------|---------|------|------|
| 仓库根 `pytest -q` | `academic-toolkit/tests` | **773 passed / 0 failed**（另 4 skipped：私有资料区缺位语义 skip 2 + docx_template_fill pyc 缺陷钉住 1 + 适配器元数据缺席 skip 1；collect-only 777。2026-09-23 v2.0 W3 清洗后实测口径） | 仓库级回归 |
| `academic-toolkit/` 内 `pytest -q` | 工具箱自有 tests | **773 passed / 0 failed**（与仓库根同口径） | 技能验收基线（硬规则 3 口径） |
| **公开 clone / CI** | 已提交内容 | 以 CI 实测为准（历史：713+5 skipped / 0 failed @ run 35711171875） | 门禁 |

- catalog 一致性由工具箱 asset 系测试 + `check_asset_utilization --strict` 守护。
- 上一时点基线 **791 = 工具箱 766 + 根级门禁 25** 保留作历史，见 `pytest.ini` 注释（公开侧口径真源）；`dev-docs/truth-index.md` 为内部副本，不入库。
- `releases/` 永不进测试收集。
- 新增技能必须：SKILL.md + catalog 映射 + CONTEST_SKILL_MAP 归类 + `build_skill_index.py --emit`。
