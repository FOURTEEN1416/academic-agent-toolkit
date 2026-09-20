---
name: tool-forge
description: 自适应工具铸造：探测 TOOL_GAP 后为当前 Agent 铸造工具与技能骨架并登记能力目录。触发词：缺工具、TOOL_GAP、造一个工具、自适应构建、forge、工具铸造、补技能。
status: active
---

# tool-forge — 自适应工具铸造协议

## 定位

驱动本项目的 Agent 在发现**工具/技能缺口**时，按本协议为自己铸造可调用资产，
而不是空等外部交付或伪造执行结果。

## 输入契约

- 已运行 `python -m engine.workflow_cli probe`（或明确的缺口描述）
- 缺口名称与目的（purpose）

## 执行步骤

1. **确认缺口类型**
   - `python_package` / `cli`：环境类——**不自动伪造安装**，按 probe hint 配置或改用替代
   - 任务缺工具/技能：进入铸造
   - 可选宿主适配器缺失：可铸造 adapter 元数据，或直接忽略（协议不依赖）

2. **铸造资产**
   ```bash
   cd 科研工具箱
   python -m engine.workflow_cli forge --tool my-tool --purpose "一句话目的"
   python -m engine.workflow_cli forge --skill my-skill --purpose "一句话目的" --linked-tool my-tool
   python -m engine.workflow_cli forge --adapter my-host --purpose "某宿主可选适配"
   # 或按 probe gap 建议：
   python -m engine.workflow_cli forge --gap '{"kind":"optional_adapter","id":"foo","hint":"..."}'
   ```
   默认不覆盖已有文件；确需覆盖加 `--force`。

3. **实现真实逻辑**
   - 打开 `tools/<name>.py` 按任务实现；骨架的 `implemented: false` 必须在真实完成前保持诚实
   - 输出保持 `--json` 机读契约，便于 evidence 与门禁消费

4. **补全技能契约**
   - 完善 `skills/<name>/SKILL.md` 的输入/输出/步骤/铁律
   - 短横线命名的技能须映射进 `capabilities/catalog.json`（根级 catalog 门禁会硬校验）

5. **自检与留痕**
   ```bash
   python tools/<name>.py --json
   python -m pytest tests/test_minimum_catalog.py -q   # 若改了 catalog/skills
   ```
   将 forge 命令与产物路径写入 execution_evidence.commands/outputs

## 输出契约

- 铸造结果 JSON（路径、status=created/exists、invoke 命令）
- catalog 登记状态（技能类）
- 实现状态：scaffolded → implemented（有真实测试/产物后才可改）

## 质量铁律

- TOOL_GAP：铸造前不宣称能力已存在
- 无证据＝未执行：evidence 必须包含真实命令与产物
- 名称约束：`[a-z0-9][a-z0-9-]{1,63}`
- 默认不覆盖已有工具/技能（防误伤既有资产）

## 关联

- 实现: `科研工具箱/engine/tool_forge.py`
- 探测: `科研工具箱/engine/capability_probe.py`
- 自举: `skills/agent-bootstrap`
- 目录: `capabilities/catalog.json`
