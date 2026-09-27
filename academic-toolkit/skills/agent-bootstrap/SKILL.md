---
name: agent-bootstrap
description: 任意智能体自举驱动本academic-toolkit：读协议、探测能力、选择路由或启动工作流。触发词：启动项目、如何驱动、bootstrap、自举、宿主无关接入、agent 开始工作。
status: active
---

# agent-bootstrap — 宿主无关 Agent 自举协议

## 定位

本技能告诉**当前驱动本项目的任意 Agent**（Claude Code / Cursor / Gemini CLI /
MiMo Desktop / OpenCode / ZCode / 自写脚本）如何在 5 分钟内合法接入并开始工作。

**不依赖任何宿主专用配置。** OpenCode / ZCode 配置仅为可选适配器（本地可选自建）。

## 输入契约

- 仓库已 clone（本检出目录名以本地为准，勿假设绝对路径）
- 用户需求文本（竞赛题 / 论文 / 文献 / 图表 / 其他）

## 执行步骤

1. **读协议**
   - 仓库根 `AGENTS.md`（宿主中立入口）
   - `academic-toolkit/AGENTS.md`（路由与门禁细节）
   - 机器可读契约：在 `academic-toolkit/` 下执行 `python -m engine.workflow_cli boot`

2. **探测能力**
   ```bash
   cd academic-toolkit
   python -m engine.workflow_cli probe
   ```
   阅读 `host_adapters` 与 `gaps`。适配器缺失不阻断；环境缺口按 hint 补齐或改用替代路径。

3. **确定驱动标签**
   - 在 evidence 中自报 `agent`：如 `claude-code` / `cursor` / `mimo-desktop`
   - 可用环境变量 `ACAT_AGENT_LABEL` 固定默认标签

3.5 **扫资产台账（先知道自己有什么，再决定怎么做）**
   - 读 `academic-toolkit/data/asset_catalog.json`（probe 输出的 `asset_catalog` 字段是同一份摘要）
   - 按 `when_to_use` / `owner_skills` 匹配当前任务：命中资产 → 先用资产，再造轮子
     （例：写竞赛摘要前读 62 篇摘要统计；画图前查统一配色注册表；建模前查题型案例库）
   - `local_only: true` 条目在私有资料区（`assets-local/` 等）：本机有则用；公开 clone 缺席
     属语义缺位，不算断链，改走降级路径
   - 台账没覆盖到的需求 → TOOL_GAP 流程（forge 或如实上报）

4. **选择路径**
   - **竞赛/多步管线**：`python -m engine.workflow_cli start --template comp_cumcm --workspace <ws>` → `next`（自动提供执行会话/本步技能正文）→ `session run/write` → `session finish`（自动组装证据、一次核验和推进）
   - **单技能任务**：按 `academic-toolkit/AGENTS.md` §三 路由表读 `skills/<name>/SKILL.md` 直接执行
   - **能力不足**：转入 `skills/tool-forge`

5. **执行与回报**
   - 产出写入 StepAction.workspace（工作流）或用户指定目录（单技能）
   - 默认用 `session run --session <next返回路径> --plan <任务计划> --finish`；纯内容用 `session write --path <产物> --stdin`，完成后 `session finish`。程序采集实际返回码、输入输出和指纹，不手填 evidence JSON。
   - 计划只声明业务命令/依赖/产物；明确纯计算且完整依赖的节点可复用，变化时自动重跑受影响节点。不要缓存网络、独立评审或人工批准。
   - `needs_work` 保持本步可编辑，一次修复诊断后再次 finish；不为修字段创建 retry 循环。中断恢复需确认进程已停，不能伪造成功。
   - 旧外部接入仍可 `complete_step` + 真实 `execution_evidence`。无宿主 L1 时审计如实降级；执行会话的机器采集记录独立核验，不冒充宿主L1。

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

- 协议实现: `academic-toolkit/engine/agent_protocol.py`
- 能力探测: `academic-toolkit/engine/capability_probe.py`
- 工具铸造: `skills/tool-forge`
- 可选适配器: 协议不依赖（`forge --adapter` 可本地生成）
