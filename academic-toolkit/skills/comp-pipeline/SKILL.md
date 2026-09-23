---
name: comp-pipeline
description: "数学建模竞赛全流程编排器（轻量变体）。引擎标准流程为国赛/华为杯同构 14 步（workflow_cli --template comp_cumcm / comp_huawei）；本技能是无引擎场景下的手动串联编排：串起问题分析、文献、建模、求解、结果、论文、编译、审查八个阶段。触发词：数模全流程、完整做一道竞赛题、comp-pipeline、从读题到交付。"
allowed-tools: [Read, Write, Edit, Bash(python:*), WebFetch, WebSearch]
---

# 数学建模竞赛全流程编排器

## 目的
编排数模竞赛从拿到题目到提交论文的完整流程。本技能是**编排器**，不代替具体技能，只负责调度、检查点、产物传递。

## 两种运行模式（先选对，再动手）

| 模式 | 入口 | 适用 |
|------|------|------|
| **标准模式（正式竞赛推荐）** | `python -m engine.workflow_cli start --template comp_cumcm`（国赛）或 `--template comp_huawei`（华为杯） | 引擎 14 步流程，带质量门禁、STEP_MANIFEST 溯源、伴生技能绑定与完成证据闸。**国赛与华为杯 14 步 1:1 同构**（仅页数/图表量等赛事参数不同），权威步骤表见 `CONTEST_SKILL_MAP.md` §一/§七 |
| **轻量模式（本技能）** | 直接读本 SKILL.md 按下文 8 阶段执行 | 无引擎环境（如宿主无法跑 Python CLI）或快速试做小题；无引擎门禁，纪律靠技能自述约束 |

**标准模式 14 步主链**（每步绑定主技能，伴生技能清单见 CONTEST_SKILL_MAP §二）：

```
S01 赛题分析(comp-problem-analysis) → S02 文献调研与核验(comp-literature)
→ S03 建模求解(comp-modeling) → S04 编程实现(comp-code)
→ S05 图表生成(paper-figure) → S06 流程与架构图绘制(paper-figure-drawio)
→ S07 逻辑对抗复核(comp-review，引擎默认包含，`skip_review=true` 可跳过)
→ S08 竞赛论文撰写(comp-paper-zh/comp-paper-en) → S09 代码-论文一致性检查(comp-consistency)
→ S10 编译与合规检查(comp-compile-zh/comp-compile-en) → S11 数模视觉审查(comp-visual-review)
→ S12 数模编辑修订(comp-editor) → S13 数模最终复审(comp-final-review)
→ S14 最终交付审计(comp-final-audit)
```

> 轻量 8 阶段是上链的子集裁剪（缺架构图步与一致性检查/视觉审查/编辑修订/终审/交付审计等质量步）——**正式竞赛不要停在 8 阶段收工**，至少补跑 S09/S13 两道闸。

## 输入契约
- `PROBLEM.md` — 竞赛题目（必需）
- `data/` — 题目附带的数据文件（可选）

## 执行流程（轻量模式：8 阶段变体）

按以下顺序执行，每阶段产出后暂停等用户确认（📌=检查点）：

```
① comp-problem-analysis  [📌] → PROB_ANALYSIS.md
② comp-literature           → LITERATURE.md（可选，跳过用 skip_literature）
③ comp-modeling       [📌] → MODEL.md
④ comp-code           [📌] → solution.py + figures/ + TABLE_*.md
⑤ comp-statistics-topic          → RESULTS.md
⑥ comp-paper-zh       [📌] → paper.md
⑦ comp-compile-zh     [📌] → paper.pdf / paper.docx
⑧ comp-review         [📌] → review_report.md → 修改 → 重审
```

> 图表环节主动路由（2026-09-11 接线）：④ 数据图由 paper-figure 三轴选图规范把关；需要选图顾问/图库选型时调 `fig-visualization-advisor` / `agent-figure-gallery`；高规格框架图（人工多候选裁决）走 `paper-framework-figure-studio-pro`。

## 编排规则

1. **阶段产物**：每个阶段产出写入 `workspaces/{id}/` 目录
2. **检查点**：📌 阶段完成后展示「决策面板」，等用户确认
3. **产物传递**：前一阶段产物作为后一阶段输入
4. **动态裁剪**：按用户参数调整步骤
   - `language=zh/en` → 切换中文/英文论文
   - `output_format=docx` → 追加 DOCX 导出
   - `skip_literature` → 跳过文献调研
   - `skip_review` → 跳过审查
5. **防编造**：所有引用文献必须过 `tools/scholar_fetch.py` 三查验证；往届优秀论文（`data/historical_papers.md`）仅作写法/模式借鉴，不入参考文献

## 决策面板模板（检查点）

```
━━━ 阶段 [X] [名称] 完成 ━━━

产物：
- [文件1]
- [文件2]

指标：
- 字数/方法数/结果质量

就绪进入阶段 [Y]？可输入：
1. 继续
2. 查看进度
3. 调整参数
4. 暂停
━━━━━━━━━━━━━━━━━━
```

## 质量门禁

- **完整性**：论文中的引用必须存在（三查通过）
- **结果合理性**：数值结果必须可复现
- **格式规范**：符合竞赛格式（对标 cumcmthesis.cls）

## 输出契约
- `paper.md` / `paper.pdf` / `paper.docx` — 最终论文
- `figures/` — 结果图
- `review_report.md` — 审查报告
- `workspaces/{id}/` — 全部中间产物