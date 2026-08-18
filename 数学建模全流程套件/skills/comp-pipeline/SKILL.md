---
name: comp-pipeline
description: "数学建模竞赛全流程编排器：问题分析→文献→建模→求解→结果→论文→编译→审查。Use when 用户要完成一个完整的数模竞赛题目。"
allowed-tools: [Read, Write, Edit, Bash(python:*), WebFetch, WebSearch]
---

# 数学建模竞赛全流程编排器

## 目的
编排数模竞赛从拿到题目到提交论文的完整流程。本技能是**编排器**，不代替具体技能，只负责调度、检查点、产物传递。

## 输入契约
- `PROBLEM.md` — 竞赛题目（必需）
- `data/` — 题目附带的数据文件（可选）

## 执行流程

按以下顺序执行，每阶段产出后暂停等用户确认（📌=检查点）：

```
① comp-prob-analysis  [📌] → PROB_ANALYSIS.md
② comp-literature           → LITERATURE.md（可选，跳过用 skip_literature）
③ comp-modeling       [📌] → MODEL.md
④ comp-code           [📌] → solution.py + figures/ + TABLE_*.md
⑤ comp-stats-topic          → RESULTS.md
⑥ comp-paper-zh       [📌] → paper.md
⑦ comp-compile-zh     [📌] → paper.pdf / paper.docx
⑧ comp-review         [📌] → review_report.md → 修改 → 重审
```

## 编排规则

1. **阶段产物**：每个阶段产出写入 `workspaces/{id}/` 目录
2. **检查点**：📌 阶段完成后展示「决策面板」，等用户确认
3. **产物传递**：前一阶段产物作为后一阶段输入
4. **动态裁剪**：按用户参数调整步骤
   - `language=zh/en` → 切换中文/英文论文
   - `output_format=docx` → 追加 DOCX 导出
   - `skip_literature` → 跳过文献调研
   - `skip_review` → 跳过审查
5. **防编造**：所有引用文献必须过 `tools/scholar_fetch.py` 三查验证

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