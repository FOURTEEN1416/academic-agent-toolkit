---
description: 启动 CUMCM 竞赛解题工作流（comp_cumcm 14 步引擎——竞赛任务的唯一正规入口）
---

# 竞赛工作流启动：$ARGUMENTS

你是执行者。竞赛解题（CUMCM 等）**必须经工作流引擎**，禁止绕开引擎直接开始做题——工作流承载步骤状态、检查点批准、质量门禁与三层审计留痕（产品灵魂，见 `科研工具箱/AGENTS.md` §审计体系）。

$ARGUMENTS 为题号（如 `A`）或完整工作区名（如 `cumcm2026A`）。

## 启动序列（逐步执行，输出全程可读）

1. **题号转工作区**：`A/B/C` → `workspaces/cumcm2026<题号>`（已给全名则直用）。
2. **启动工作流**（cwd 必须在 `科研工具箱/`）：

   ```bash
   cd 科研工具箱 && python -m engine.workflow_cli start --template comp_cumcm --workspace ../workspaces/cumcm2026A --params '{"language":"zh"}' && cd ..
   ```

3. **取第一步**：`python -m engine.workflow_cli next --wf <WF_ID> --db <workspace>/.engine/workflow.sqlite`（或按返回的 index 解析），得到 StepAction（skill_name / skill_path / output_files / checkpoint）。
4. **按技能执行**：Read StepAction.skill_path 指向的 SKILL.md，严格按其工作流与完成铁律执行；产物写入 StepAction.workspace。
5. **回报推进**：`complete --wf <WF_ID> --ok true --artifacts "..." --evidence '{...}'`（evidence 7 必填字段，schema 见 `科研工具箱/AGENTS.md` §十；审核类步骤 evidence 必须含真实 subagent 会话记录，禁止主智能体伪造 verdict）。
6. **checkpoint 步骤**：展示决策面板，等用户批准后再推进（`approve`）。

## 配套入口

- 赛时操作全集（审稿三通道/evidence schema/启动检查清单）：`CUMCM2026Problems/<题>/作战手册.md`
- 赛前自检（14 步全链驱动）：`python 科研工具箱/tools/contest_dryrun/chain_driver.py`
- 审稿模型：`engine/modex-core/contest_models.json`（比赛配置槽）

## 铁律

- 引擎只编排，执行者是当前 Agent；完成步骤必须回报 `complete_step` 附真实 execution_evidence。
- 伪造审核产物 = 最高级事故（见 `dev-docs/LESSONS_FROM_CUMCM_Practice_2026-08.md` 教训 1）。
- 审核类步骤（comp-review/comp-visual-review/comp-final-review）派只读子智能体，主 Agent 受控落盘。
