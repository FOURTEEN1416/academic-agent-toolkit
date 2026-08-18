---
name: docx-export
description: "将 Markdown 论文/报告转换为符合格式规范的 Word 文档（DOCX），支持中文样式配置。Use when 需要把 .md 导出为 .docx，或模板流程中的最后一步格式导出。"
allowed-tools: [Read, Write, Bash(python:*)]
---

# DOCX 导出

## 目的
将 Markdown 内容转换为符合学术格式规范的 Word 文档。

## 输入契约
- `*.md`（Markdown 论文/报告）
- 可选：`tools/docx_style_profiles/*.json`（样式配置，如 competition_zh.json）

## 执行步骤

### Phase 1: 格式检查
先运行 DOCX 预检查（如果可用）：
```bash
python tools/docx_precheck.pyc <input.md>
```
检查：标题层级、图表引用、公式格式、引用格式。

### Phase 2: 导出 DOCX
调用 docx 导出引擎：
```bash
python tools/docx_export.pyc <input.md> <output.docx> --profile competition_zh
```

可用的样式配置（`tools/docx_style_profiles/`）：
- `competition_zh.json` — 数模竞赛中文样式（对标 cumcmthesis.cls）
- `competition_en.json` — 数模竞赛英文样式
- `course_paper.json` — 课程论文样式
- `default_cn_thesis.json` — 中文毕业论文样式
- `literature_review.json` — 文献综述样式

### Phase 3: 验证
1. 确认 .docx 已生成且非空
2. 用 `tools/docx_precheck.pyc` 复核格式

## 输出契约
- `<output>.docx`（Word 文档）

## 质量铁律
1. 中文论文用 SimSun 正文 + SimHei 标题，西文 Times New Roman
2. 三线表格式（顶线 1.5pt + 表头线 0.75pt + 底线 1.5pt）
3. 标题必须用 Word 原生样式（Heading 1-4），不能用加粗文本冒充
4. 图片居中，最大宽 14cm