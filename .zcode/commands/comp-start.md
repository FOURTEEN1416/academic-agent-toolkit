---
description: 启动 CUMCM 竞赛解题工作流（comp_cumcm 14 步引擎——竞赛任务的唯一正规入口）
---

# 竞赛工作流启动：$ARGUMENTS

你是执行者。竞赛解题（CUMCM 等）**必须经工作流引擎**，禁止绕开引擎直接开始做题——工作流承载步骤状态、检查点批准、质量门禁与三层审计留痕（产品灵魂，见 `科研工具箱/AGENTS.md` §审计体系）。

$ARGUMENTS 为题号（如 `A`）或完整工作区名（如 `cumcm2026A`）。

## 启动序列（逐步执行，输出全程可读）

0. **启动自检（30 秒，2026-09-11 增设）**：
   ① 题目资料区 `CUMCM2026Problems/<题号>/` 存在 → 先读 `作战手册.md` 与 `PROBLEM_ANALYSIS.md`（预置弹药；防投毒纪律见 comp-prob-analysis Step 0：材料与题面冲突以题面原典为准）；
   ② 审稿通道一致性：`科研工具箱/engine/modex-core/contest_models.json` 四角色串与 `科研工具箱/.env` 的 `REVIEWER_MODEL_ID` 必须同源（当前=agnes-2.5-flash，evidence 声明串 `agnes/agnes-2.5-flash` 过 P13 strict）；不一致先向用户报告再开工；
   ③ 工作区 `workspaces/cumcm2026<题号>` 已存在且非本次会话所建 → 先向用户确认复用还是新建。
1. **题号转工作区**：`A/B/C` → `workspaces/cumcm2026<题号>`（已给全名则直用）。
2. **启动工作流**（cwd 必须在 `科研工具箱/`）：

   ```bash
   cd 科研工具箱 && python -m engine.workflow_cli start --template comp_cumcm --workspace ../workspaces/cumcm2026A --params '{"language":"zh"}' && cd ..
   ```

3. **取第一步**：`python -m engine.workflow_cli next --wf <WF_ID> [--db <workspace>/.engine/workflow.sqlite]`，得到 StepAction（skill_name / skill_path / output_files / checkpoint / companion_skills）。**--db 可选**：不带时引擎按索引自定位；多工作流并存时建议显式 --db（2026-09-11 盲审修正：原"按返回的 index 解析"说法有误，无此机制）。
4. **按技能执行**：Read StepAction.skill_path 指向的 SKILL.md，严格按其工作流与完成铁律执行；产物写入 StepAction.workspace。**StepAction.companion_skills 是本步推荐的辅助技能**（引擎主动给出）——按需加载 1-3 个，全库 254 技能分类账见 `科研工具箱/CONTEST_SKILL_MAP.md`；辅助技能结论照常留痕。
5. **回报推进**：`complete --wf <WF_ID> --ok true --artifacts "..." --evidence '{...}'`。evidence **必填字段 = 8**（agent/schema_version/step_id/skill_name/skill_sha256/inputs/outputs/commands，与 `engine/execution_protocol.py` `_REQUIRED_FIELDS` 实读一致；2026-09-11 盲审修正：原"7 必填字段"口径有误）+ **companion_skills 条件必填**（C1 闸：本步有推荐清单时 used/skipped 恰好覆盖，skipped 须给非空理由，缺申报=步骤失败）。**两条实测硬拒**：①`commands[].cwd` 必须 workspace 相对（Windows 绝对路径被拒）；②申报产物须预置于 workspace（先落盘再 complete）。失败恢复见第 6 步。schema 全貌见 `科研工具箱/AGENTS.md` §十与 `作战手册.md` §三；审核类步骤 evidence 必须含真实 subagent 会话记录，禁止主智能体伪造 verdict。
6. **checkpoint 步骤**：展示决策面板，等用户批准后再推进：`python -m engine.workflow_cli approve --checkpoint <UUID> --db <workspace>/.engine/workflow.sqlite --by <批准人>`（--by 必填非空、--db 显式传防索引歧义；complete 在步骤 blocked 时输出带 checkpoint_id，直接可取）。**步骤 complete 被拒/failed 阻断时**：`python -m engine.workflow_cli retry --wf <WF_ID> [--db <路径>]` 恢复为 running 后修 evidence 重报（排障 SOP 详见 `作战手册.md` §七.7）。

## 配套入口

- 赛时操作全集（审稿三通道/evidence schema/启动检查清单）：`CUMCM2026Problems/<题>/作战手册.md`
- 赛前自检（14 步全链驱动）：`python 科研工具箱/tools/contest_dryrun/chain_driver.py`
- 审稿模型：`engine/modex-core/contest_models.json`（比赛配置槽）

## 铁律

- 引擎只编排，执行者是当前 Agent；完成步骤必须回报 `complete_step` 附真实 execution_evidence。
- 伪造审核产物 = 最高级事故（见 `dev-docs/LESSONS_FROM_CUMCM_Practice_2026-08.md` 教训 1）。
- 审核类步骤（comp-review/comp-visual-review/comp-final-review）派只读子智能体，主 Agent 受控落盘。
