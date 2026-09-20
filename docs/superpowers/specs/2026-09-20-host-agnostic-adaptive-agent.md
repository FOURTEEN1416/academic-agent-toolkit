# 宿主无关 · 自适应 Agent 工程系统改造设计

> 日期：2026-09-20 · 状态：实施中
> 目标：不依赖特定宿主；任何能读文件、跑 Python CLI 的智能体皆可驱动本项目，
> 并可通过能力探测 + 工具铸造协议，自适应构建为自己所用的工具。

## 1. 问题

原系统将 OpenCode Desktop / ZCode 写死为「正式/主控宿主」：

- 文档入口以宿主名路由，新 Agent 无法仅凭仓库自举
- `opencode_bridge` 命名与默认 agent 标签绑定 OpenCode
- `quality_gates` 模型解析链硬回退 `.opencode/agents/`
- L1 审计在无宿主 hook 时语义不清
- 缺少「能力不够 → 自己造工具」的正式协议

## 2. 目标与非目标

**目标**

1. 宿主中立：驱动协议只依赖文件系统 + Python CLI
2. 引擎深度重构：去 OpenCode 专有命名与默认值，旧宿主降为可选适配器
3. 自适应：`capability_probe` 探测运行时 → `tool_forge` 按 TOOL_GAP 铸造工具/技能
4. 通用 Agent 皆可：Claude Code / Cursor / Gemini CLI / MiMo Desktop / 自写脚本

**非目标**

- 不重写 261 个领域技能的内容
- 不删除 OpenCode/ZCode 配置（保留为可选适配器）
- 不引入必须在线的外部调度服务

## 3. 架构

```
任意 Agent
    │  ① boot / 读 AGENTS.md
    ▼
agent_protocol ──► bootstrap 契约（硬规则 / CLI / 目录）
    │
    ├─► capability_probe ──► python/包/CLI/API/适配器/TOOL_GAP
    │         │
    │         └─ gap ──► tool_forge ──► tools/*.py + skills/<name>/ + catalog 登记
    │
    ├─► skills/ + tools/（执行面）
    │
    └─► workflow_cli（start → next → complete）
              │
              ├ L2 引擎审计（operations.jsonl）
              ├ L3 evidence（complete_step）
              └ L1 可选：宿主 hook/插件（无则 unavailable，不阻断）
```

### 3.1 模块映射

| 模块 | 职责 |
|------|------|
| `engine/agent_bridge.py` | StepAction/StepResult 宿主中立定义（canonical） |
| `engine/opencode_bridge.py` | 兼容 shim，re-export agent_bridge |
| `engine/agent_protocol.py` | bootstrap 契约、默认 agent 标签、协议版本 |
| `engine/capability_probe.py` | 运行时/依赖/适配器/GAP 探测 |
| `engine/tool_forge.py` | 工具与技能脚手架铸造 + catalog 登记辅助 |
| `engine/quality_gates.py` | 模型解析：contest → adapters/*/models.json → 可选宿主 agent 目录 |
| `engine/workflow_cli.py` | 新增 `boot` / `probe` / `forge`；描述去宿主 |
| `agents/adapters/*` | 可选宿主适配器元数据（非运行时依赖） |

### 3.2 Agent 驱动协议（v1）

任何 Agent 的最小闭环：

1. 读仓库根 `AGENTS.md`（宿主中立入口）
2. `python -m engine.workflow_cli boot` 取得契约 JSON
3. `python -m engine.workflow_cli probe` 探测能力与 GAP
4. 按需 `forge` 铸造工具/技能
5. 竞赛/长流程：`start` → `next` → 执行技能 → `complete`（evidence.agent 填自己的标识）
6. 短任务：按路由表直接读 `skills/<name>/SKILL.md` 并调用 `tools/`

**硬规则（宿主无关）**

- 引擎只编排不执行；执行者 = 当前驱动本项目的 Agent
- 同一时刻只有一个主控 Agent
- 无证据＝未执行；complete_step 必须附真实 execution_evidence
- TOOL_GAP：工具够不到就报告状态未知或铸造补丁，绝不伪造通过
- 三振升级：同一思路失败 3 次必须换路或上报

### 3.3 证据 agent 字段

`execution_evidence.agent` 为**非空自由字符串**，由驱动方自报：

- 通用示例：`"claude-code"` / `"cursor"` / `"mimo-desktop"` / `"acat-agent"`
- 可选适配器示例：`"opencode-desktop"` / `"zcode"`

引擎不再默认写死 OpenCode。

### 3.4 质量门禁模型解析（重构后）

```
1. ACAT_CONTEST_MODELS 环境变量 → 指定 JSON
2. engine/modex-core/contest_models.json
3. agents/adapters/*/models.json（任意宿主/通道可写角色模型）
4. 可选宿主 agent 目录（.opencode/agents、.claude/agents、agents/roles…）
   经 ACAT_ADAPTER_AGENTS_DIRS 或自动发现
5. 皆空 → 无配置模型；strict 比对降级 skip/warn（不阻断）
```

### 3.5 能力探测 `capability_probe`

输出 JSON：

- `python`: 版本 / 关键包是否可导入
- `cli`: xelatex / node / git / drawio 等（复用 RuntimePaths + which）
- `env_presence`: 相关环境变量是否存在（**不打印值**）
- `host_adapters`: opencode / zcode / claude_code / mimocode / generic 配置是否在位
- `gaps`: 机器可读 TOOL_GAP 列表（缺包/缺 CLI/缺适配器）

### 3.6 工具铸造 `tool_forge`

| 动作 | 产物 |
|------|------|
| forge tool | `tools/<name>.py`（argparse + JSON 输出骨架） |
| forge skill | `skills/<name>/SKILL.md`（触发/输入/步骤/输出/铁律） |
| forge adapter | `agents/adapters/<id>/adapter.json`（可选） |
| register hint | 提示补 `capabilities/catalog.json`（技能须短横线 capability_id） |

约束：名称 `[a-z0-9][a-z0-9-]{1,63}`；已存在不覆盖（`--force` 才覆盖）；铸造产物必须遵守 TOOL_GAP 与无证据未执行原则。

### 3.7 可选宿主适配器

| 适配器 | 配置 | 状态 |
|--------|------|------|
| generic | 无 | 永远可用（协议层） |
| opencode | `opencode.json` + `.opencode/` | 可选 |
| zcode | `.zcode/` | 可选 |
| claude-code | `.claude/` / `AGENTS.md`/`CLAUDE.md` | 可选 |
| mimocode | `.mimocode/` | 可选 |

适配器只提供「技能发现 / L1 hook / 子智能体角色」等增强，**不是驱动前提**。

## 4. 文档改造

| 文件 | 变化 |
|------|------|
| 根 `AGENTS.md` | 宿主中立协议入口；适配器矩阵降级为可选 |
| `科研工具箱/AGENTS.md` | 主控=当前 Agent；OpenCode/ZCode 为可选适配器 |
| 根 `README.md` | hosts 徽章改为 Any Agent；协议/铸造说明 |
| `skills/agent-bootstrap/` | 新技能：任意 Agent 如何自举 |
| `skills/tool-forge/` | 新技能：如何探测 GAP 并铸造工具 |

## 5. 测试策略

- 兼容：`opencode_bridge` shim → 既有 import 不炸
- 新增：`test_agent_protocol.py` / `test_capability_probe.py` / `test_tool_forge.py`
- 调整：`test_independence_contract.py` 钉新措辞；`test_opencode_configuration.py` 钉「可选适配器」语义
- 回归：仓库根 `pytest -q`；`catalog` 根级门禁；新技能必须入册

## 6. 迁移顺序

1. DESIGN（本文件）
2. engine：agent_bridge / probe / forge / protocol / quality_gates / CLI
3. adapters + bootstrap/tool-forge 技能 + catalog
4. 文档（根 AGENTS / 工具箱 AGENTS / README）
5. 测试补齐 + 全量回归 + 基线数字同步

## 7. 验收（2026-09-20 复验）

- [x] 无 OpenCode/ZCode 时，仅凭 AGENTS.md + workflow_cli 可 boot/probe/start/next/complete（协议层 boot/probe/forge 实测通过）
- [x] `probe` 能列出适配器在位状态与 TOOL_GAP
- [x] `forge --tool/--skill` 能生成可运行骨架且二次调用默认不覆盖
- [x] 旧宿主配置仍在位且测试语义为「可选适配器」
- [x] 既有测试通过 shim 不因改名失败；全量 pytest **639 passed** + catalog 门禁通过
- [x] 文档收尾：CHANGELOG/LOG/README/CLAUDE.md/galaxy-*/acat-doc-governance 措辞同步；缓存与 workflow-index 已清
