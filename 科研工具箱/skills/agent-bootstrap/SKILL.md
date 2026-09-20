---
name: agent-bootstrap
description: 任意智能体自举驱动本科研工具箱：读协议、探测能力、选择路由或启动工作流。触发词：启动项目、如何驱动、bootstrap、自举、宿主无关接入、agent 开始工作。
status: active
---

# agent-bootstrap — 宿主无关 Agent 自举协议

## 定位

本技能告诉**当前驱动本项目的任意 Agent**（Claude Code / Cursor / Gemini CLI /
MiMo Desktop / OpenCode / ZCode / 自写脚本）如何在 5 分钟内合法接入并开始工作。

**不依赖任何宿主专用配置。** OpenCode / ZCode 配置仅为可选适配器（见 `agents/adapters/`）。

## 输入契约

- 仓库已 clone（本检出目录名以本地为准，勿假设绝对路径）
- 用户需求文本（竞赛题 / 论文 / 文献 / 图表 / 其他）

## 执行步骤

1. **读协议**
   - 仓库根 `AGENTS.md`（宿主中立入口）
   - `科研工具箱/AGENTS.md`（路由与门禁细节）
   - 机器可读契约：在 `科研工具箱/` 下执行 `python -m engine.workflow_cli boot`

2. **探测能力**
   ```bash
   cd 科研工具箱
   python -m engine.workflow_cli probe
   ```
   阅读 `host_adapters` 与 `gaps`。适配器缺失不阻断；环境缺口按 hint 补齐或改用替代路径。

3. **确定驱动标签**
   - 在 evidence 中自报 `agent`：如 `claude-code` / `cursor` / `mimo-desktop`
   - 可用环境变量 `ACAT_AGENT_LABEL` 固定默认标签

4. **选择路径**
   - **竞赛/多步管线**：`python -m engine.workflow_cli start --template comp_cumcm --workspace <ws>` → `next` → 执行 → `complete`
   - **单技能任务**：按 `科研工具箱/AGENTS.md` §三 路由表读 `skills/<name>/SKILL.md` 直接执行
   - **能力不足**：转入 `skills/tool-forge`

5. **执行与回报**
   - 产出写入 StepAction.workspace（工作流）或用户指定目录（单技能）
   - 完成步骤必须 `complete_step` + 真实 `execution_evidence`（schema_version=1）
   - 无宿主 L1 时审计允许 `unavailable`，但 L3 证据不可省略

## 输出契约

- 已选定的驱动路径（工作流 ID 或技能名）
- probe 摘要（可用适配器 / 关键 gaps）
- 后续动作清单

## 质量铁律

- 引擎只编排不执行；执行者是你（当前 Agent）
- 同一时刻只有一个主控 Agent
- 无证据＝未执行
- TOOL_GAP：不够就 forge 或如实上报，禁止伪造通过

## 关联

- 协议实现: `科研工具箱/engine/agent_protocol.py`
- 能力探测: `科研工具箱/engine/capability_probe.py`
- 工具铸造: `skills/tool-forge`
- 可选适配器: `agents/adapters/`
