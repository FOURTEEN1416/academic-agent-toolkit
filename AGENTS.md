# Academic Agent Toolkit — 仓库入口（宿主无关）

> 本仓库是一个**完整academic-toolkit**（全学术 Agent 工具箱，6 大能力域 + Agent 运行时），数模竞赛只是其一。
> **主控文档（单一真源）：[academic-toolkit/AGENTS.md](academic-toolkit/AGENTS.md)** —— 开工前必须先读它。
> **驱动协议**：任意能读文件、能执行 Python CLI 的智能体均可驱动本项目，不依赖特定宿主。
> 机器可读契约：`cd academic-toolkit && python -m engine.workflow_cli boot`

## 驱动协议（任何 Agent）

1. 读本文件、`academic-toolkit/AGENTS.md` 与 `academic-toolkit/skills/agent-bootstrap/SKILL.md`（与 boot 的 `required_reads` 一致）
2. `cd academic-toolkit && python -m engine.workflow_cli boot` 取得契约
3. `python -m engine.workflow_cli probe` 探测能力与 TOOL_GAP
4. 缺工具时 `python -m engine.workflow_cli forge --tool/--skill ...`
5. 多步流程：`start` → `next`（自动给执行会话及技能正文）→ `session run/write`（自动记录）→ `session finish`（一次验收/推进）；旧 `complete --evidence` 仅兼容外部集成
6. 单技能任务：按 `academic-toolkit/AGENTS.md` §三 路由表直接读 SKILL.md

高频意图直达（多步任务按 `academic-toolkit/AGENTS.md` §三 路由表选模板；以下单技能直达，直接读对应 SKILL.md）：

| 用户意图 | 直达技能 |
|---|---|
| 引用格式 / 参考文献规范 | `academic-toolkit/skills/citation-check/SKILL.md` |
| 机制图 / 架构图 | `academic-toolkit/skills/paper-figure-drawio/SKILL.md` |
| 数值一致性 / 前后数字核对 | `academic-toolkit/skills/comp-consistency/SKILL.md` |

**主控 = 当前驱动本项目的 Agent。** 同一时刻只有一个主控；引擎（engine/）只编排不执行；
不存在「调用另一个 agent runtime」的逻辑。

**硬规则**：无证据＝未执行 · TOOL_GAP 不伪造通过 · 三振升级 · 执行操作自动留痕，finish统一核验，人工批准不可代替。

自举技能：`academic-toolkit/skills/agent-bootstrap/` · 铸造技能：`academic-toolkit/skills/tool-forge/`

**运行环境边界**：本仓不随带任何客户端专用配置；驱动只需文件读取与 CLI 执行能力。仓库自带中性 L1 参考实现 `academic-toolkit/hooks/agent_audit_l1.py`：PreToolUse/PostToolUse/PostToolUseFailure 三类工具事件写入项目根 `.engine/audit/operations.jsonl`，`git add .`/`-A`/`--all` 类治理命令 deny exit 2、其余只记录，钩子自身故障 fail-open；`python academic-toolkit/hooks/agent_audit_l1.py --print-bootstrap` 输出可嵌入任意运行环境的注册引导器。注册与否由运行环境决定；未注册即按 `unavailable` 处理（不阻断），L2（引擎）/L3（evidence）始终可用。

## 仓库地图（治理入口）

| 路径 | 性质 |
|------|------|
| `academic-toolkit/` | 产品主体：skills/execution/engine/tools/tests/hooks/data；内嵌第三方引擎在 `third_party/`（pinned + UPSTREAM，溯源同 `check_provenance.py`） |
| `capabilities/catalog.json` | 能力目录（技能须全部映射；一致性由工具箱 asset 系门禁 + `check_asset_utilization --strict` 守护） |
| `dev-docs/` | 内部真源根（gitignored 私有，公开仓不分发）：**操作日志 `dev-docs/LOG.md`（唯一记账真源）· 任务计划 `dev-docs/task_plan.md` · 审计报告** |
| `SECURITY.md`、`CHANGELOG.md` | 安全策略 / 公开版本记录 |
| `assets-local/`（随公开仓分发：获奖论文页面原件与版面卡、`contest-regs/` 官方原件、`cumcm-templates/`、`reference-figures/`、`ip-materials/`；版面蒸馏台账 `layout-distill/progress.json` 18/62 完成；`award-papers/graduate`、`award-papers/mathorcup-bigdata` 私有子集仅本地） | 随仓分发（私有子集不入 git） |
| `academic-toolkit/workspaces/`（华为杯等演练产物） | 本地材料与产物（不入 git） |

## 硬性规则（冲突时以主控文档为准）

1. 引擎（engine/）只编排不执行；执行者是当前驱动 Agent。
2. 完成步骤使用执行会话 `finish`，由引擎从实际操作构造证据；禁止伪造审核产物。
3. 改代码后跑 `python academic-toolkit/tools/final_check.py`（固定仓库根依次跑全量 `pytest -q`、`check_provenance`、`secret_scan --strict`，结果写 `dev-docs/FINAL_CHECK.json`；单步调试用 `--only <step>`）；改测试后先 `python academic-toolkit/tools/sync_baselines.py --check` 核对基线锚点。
4. `dev-docs/` 是内部真源根，全私有零入库；`vendor/` 已按收编裁决入库（fork→vendor 改名激活，溯源走 `tools/check_provenance.py`）。
5. 文档治理遵守 `meta-doc-governance`：全文读完、污染必清。
6. **路径/密钥卫生**：tracked 配置不得写本机绝对路径；`.env` 永不入库；
   `python academic-toolkit/tools/secret_scan.py --strict` 机检。

## 测试口径（pytest.ini 为唯一真源）

| 运行位置 | 收集范围 | 基线 | 用途 |
|----------|---------|------|------|
| 仓库根 `pytest -q` | `academic-toolkit/tests` | **1355 collected**（W-SLIM 瘦身批 +9 自测；验收批 +1；复核批 +1；对抗扫描批 +3；合同判据收紧批 +11；仿真建模赛补齐批 +17；W1/W2/W5 测试批 +19；W6 基线单源批 +4；2026-10-27 宿主清洗批（退役宿主测试、以 `test_agent_audit_hook.py` 14 例接替）净减 9 例；同日收尾批 host_dep_scan 扩容钉测试 +2 后）；最近实跑记录见 `pytest.ini`；保留临时目录入口，不改生产断言 | 仓库级回归 |
| `academic-toolkit/` 内 `pytest -q` | 工具箱自有 tests | **1355 collected**（相同 tests 收集范围；实跑结果见唯一真源 `pytest.ini`） | 技能验收基线（硬规则 3 口径） |
| **公开 clone / CI** | 已提交内容 | 以 CI 实测为准 | 门禁 |

- catalog 一致性由工具箱 asset 系测试 + `check_asset_utilization --strict` 守护。
- **数字使用纪律（2026-10-02 用户裁决）**：基线数字唯一用途是防静默丢测试的漂移锚点；它不是完成验收证据——完成验收用与改动面直接相关的行为证据（功能实测/受影响链路跑通/真实命令输出）；对文档与技能正文类改动宣称「全量测试绿」不构成质量证明；禁止为 1-off 数字差异写考证（重跑 collect-only 以实跑为准）。验证服务效果与质量，不为过闸而过闸。
- 基线演进历史见 `CHANGELOG.md` 与内部 `dev-docs/LOG.md`；`dev-docs/truth-index.md` 为内部副本，不入库。
- `norecursedirs` 防线（pytest.ini）永不放松；`releases/` 目录现已不存在（历史发布快照叙事见 CHANGELOG）。
- 新增技能必须：SKILL.md + catalog 映射 + CONTEST_SKILL_MAP 归类 + `build_skill_index.py --emit`。
