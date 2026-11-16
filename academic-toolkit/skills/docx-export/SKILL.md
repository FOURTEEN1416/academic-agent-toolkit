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
- 可选：样式配置 JSON（如 competition_zh.json），位于仓库根 `academic-toolkit/third_party/docx-style-profiles/`（工具侧会按候选目录自动探测；本文件内所有工具/样式路径均按下方多候选解析，不要按字面单路径硬套）

## 执行步骤

### Phase 1: 格式检查
先运行 DOCX 预检查（如果可用）。工具路径按多候选解析（当前 cwd → 仓库根 `academic-toolkit/` 前缀回退，对齐 quality-check 的模式）：
```bash
PRE=""
for cand in tools/docx_precheck.py academic-toolkit/tools/docx_precheck.py ../../tools/docx_precheck.py; do
    [ -f "$cand" ] && PRE="$cand" && break
done
[ -n "$PRE" ] && python "$PRE" <input.md> || echo "WARN: docx_precheck.py not found; record as CHECK_UNAVAILABLE"
```
检查：标题层级、图表引用、公式格式、引用格式。

### Phase 2: 导出 DOCX
调用 docx 导出引擎（同一多候选解析）：
```bash
EXP=""
for cand in tools/docx_export.py academic-toolkit/tools/docx_export.py ../../tools/docx_export.py; do
    [ -f "$cand" ] && EXP="$cand" && break
done
[ -n "$EXP" ] && python "$EXP" <input.md> <output.docx> --profile competition_zh
```

可用的样式配置（仓库根 `academic-toolkit/third_party/docx-style-profiles/`；`--profile` 接受内置样式名对应的 JSON 路径或自定义样式 JSON 路径）：
- `competition_zh.json` — 数模竞赛中文样式（对标 cumcmthesis.cls）
- `competition_en.json` — 数模竞赛英文样式
- `course_paper.json` — 课程论文样式
- `course_report.json` — 课程报告样式
- `default_cn_thesis.json` — 中文毕业论文样式（`--profile` 缺省时的默认）
- `literature_review.json` — 文献综述样式
- `thesis_proposal.json` — 开题报告样式
- `reference_paper_general.json` — 通用参考论文样式
- `covers/` — 封面子样式（cumcm.json、huawei.json、mcm.json、default_zh.json、default_en.json）

### Phase 3: 验证
1. 确认 .docx 已生成且非空
2. 用 Phase 1 解析出的 `$PRE`（docx_precheck.py）复核格式

### 上游产物如何传入
- `_text_profile.json`（format-profile 产出）：作为 `--profile` 的值传入（`--profile _text_profile.json`）。工具按「缺失字段用默认值填充」合并样式，因此它与内置样式 JSON 同样可用；两者二选一。
- `_template_map.json`（docx-template-map 产出）：放在工作区根，由 `tools/docx_template_fill.py` 自动发现（`--workspace` 指向工作区根即可），docx-export 无需重复传参。按契约：模板映射第 3 轮仍失败时，fill 工具退回正则启发式填充，导出流程继续（工作区无 `_template_map.json` 时同理）。

## 输出契约
- `<output>.docx`（Word 文档）

## 质量铁律
1. 中文论文用 SimSun 正文 + SimHei 标题，西文 Times New Roman
2. 三线表格式（顶线 1.5pt + 表头线 0.75pt + 底线 1.5pt）
3. 标题必须用 Word 原生样式（Heading 1-4），不能用加粗文本冒充
4. 图片居中，最大宽 14cm