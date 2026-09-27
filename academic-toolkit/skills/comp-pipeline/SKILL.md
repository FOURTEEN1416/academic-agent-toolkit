---
name: comp-pipeline
description: "数学建模竞赛全流程入口：把竞赛任务映射到引擎工作流模板（国赛 comp_cumcm、华为杯 comp_huawei、其他赛事对应 comp_*），由引擎分派各步骤并独占流程状态；本技能不再维护并行编排或手动阶段面板。触发词：数模全流程、完整做一道竞赛题、comp-pipeline、从读题到交付。"
allowed-tools: [Read, Write, Edit, Bash(python:*), WebFetch, WebSearch]
---

# 数学建模竞赛全流程入口

## 职责

本技能只负责把竞赛任务映射到正确的引擎模板并恢复既有工作流；不代替具体技能执行业务，不维护第二套阶段状态、检查点面板或手动编排顺序。唯一的步骤状态来自工作流引擎。

## 模板选择

| 任务 | 模板 |
|------|------|
| 国赛（CUMCM） | `comp_cumcm` |
| 华为杯（研究生数学建模） | `comp_huawei` |
| 美赛（MCM/ICM） | `comp_mcm` |
| 其他数模赛事 | `engine/modex-core/templates.json` 中对应 `comp_*`（亚太、MathorCup、统计建模、深圳杯等） |

各模板步骤、主技能与伴生技能的权威对照见 `CONTEST_SKILL_MAP.md`；国赛与华为杯主链 1:1 同构，仅页数/图表量等赛事参数不同。

## 输入

竞赛题目（`PROBLEM.md`）与附带数据（`data/`）。创建工作流时把赛事名、语言（zh/en）、输出格式（pdf/docx）、是否跳过文献或评审等保存为业务参数；密钥不入参数。

## 执行

1. 已有工作流 ID 则恢复当前状态，不重开一条并行的流程；没有时用 `python -m engine.workflow_cli start --template <模板> --workspace <工作区> --params <业务参数JSON>` 创建。
2. 用 `next` 领取当前步骤及其主技能、产物合同与执行会话；只执行当前步骤，不提前调用后续技能。
3. 检查点等待真实批准：`workflow_cli approve --checkpoint ID --by <批准人>`；无回复不是同意。
4. 每步完成后由会话 `finish` 统一验收并推进；质量问题在当前步骤返修。

## 质量纪律（随任务始终）

- **防编造**：所有引用文献必须过 `tools/scholar_fetch.py` 三查验证；往届优秀论文（`data/historical_papers.md`）仅作写法/模式借鉴，不入参考文献。
- **结果可复现**：论文中的数值结果必须能由交付代码与数据复现。
- **格式合规**：终稿格式以对应赛事 `comp_rules.json` 配置与官方规范摘要为准。
- **图表资源候选**：数据图由 `paper-figure` 三轴选图规范把关；需要选图顾问/图库选型时按需调 `fig-visualization-advisor` / `agent-figure-gallery`；高规格框架图（人工多候选裁决）走 `paper-framework-figure-studio-pro`。候选按任务需要选取，不为凑数堆调用。

引擎 CLI 无法运行时如实报告 TOOL_GAP 并停下等待处置，不切换到无门禁的手动阶段旁路继续做题。
