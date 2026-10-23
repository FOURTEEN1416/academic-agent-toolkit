# 版式与赛事结构 playbook（comp-paper-zh）

本文件承接 SKILL.md 的「赛事结构」「模板骨架纪律」「华为杯官方格式」三块细则，**按需读，不整篇下发**：
写章节前读 §1 对应赛事那一段；Step 1 复制完模板后读 §2；`comp_huawei` 另读 §3–§4。
SKILL.md 只保留路由、可执行命令与硬门禁；细则真源是本文件与 `_templates/`。

## 1. 赛事结构（Paper Structure by Competition Type）

### 数模竞赛 (cumcm/huawei/mathorcup/huazhong/etc.)

Template: `_templates/cumcm/`（国赛：`cumcmthesis.cls` + `cumcm2026.sty` + 骨架 `main.tex`）
华为杯：`_templates/huawei/`（`gmcmthesis.cls` + 骨架 `main.tex` + 封面 `logo.pdf`/`title.pdf`；字体 SimSun/SimHei/KaiTi/LiSu 不随库分发，取法见其 README.md）

⛔ **sty 定制纪律（防双源分叉）**：需要改样式时**禁止整份复制 `cumcm2026.sty` 后私改**（双源分叉：diff 说不清改了什么，合规无法对账）。正确做法：复制同目录 `cumcm2026_local.example.sty` 为 `cumcm2026_local.sty`——`\input` 真源 + 只在 PATCH 区追加差异 + BASELINE 行登记基线版本；`cumcm2026.sty` 头部有 `TEMPLATE_VERSION` 基线标记。

⛔ **其余赛事模板现状**：模板目录已收编进 `_templates/<模板目录>/`，Step 1 的 case 表把规范 `comp_*` ID 一一映射到目录（comp_huazhong 复用 `cumcm/`；comp_teddy / comp_certcup / comp_zhongqing / comp_tianfu / comp_shenzhen / comp_huadong 暂无专用目录，按档案 `template_cls: ctexart` 走通用骨架 `default/`——这是档案指定文档类的通用骨架，不是跨赛事套用）。目录不在位时断言**显式报错 exit 1 并给出补救路径**，不改用其他赛事模板。

**⛔ MathorCup 与 亚太赛中文(APMCM) 都使用 `MathorCupmodeling.cls` 文档类**（该 cls 随 `_templates/mathorcup/` 与 `_templates/apmcm_zh/` 入库，直接走下方分支复制）。使用 `\bianhao{}`、`\tihao{}`、`\timu{}` 设置队伍信息，`\keyword{}` 设置关键词。摘要用 `\begin{abstract}...\end{abstract}` 环境。参考文献用 `\begin{thebibliography}` 环境。

**⛔ 华中杯必须使用 `cumcmthesis` 文档类**（与国赛同源：本仓库 `_templates/cumcm/` 已入库 cls+sty+骨架，可直接 `cp _templates/cumcm/* paper/` 复用；中文渲染由 ctex 走系统字体，无需随模板捆绑字体）。华中杯模板使用 `\begin{abstract}...\keywords{}\end{abstract}` 环境写摘要（不是手动排版），参考文献用 `\begin{thebibliography}` 环境（不是 `\bibliography{}`）。

```

摘要（~1页，含关键词）

1 问题重述

2 模型假设

3 符号说明

4 问题一的建模与求解（each sub-problem gets its own chapter）

5 问题二的建模与求解

6 问题三的建模与求解

7 灵敏度分析与模型检验

8 模型评价与推广

参考文献

附录 A：代码

```

> 赛事合规硬门禁（国赛提交文件命名 / AI 工具使用声明）不在本 playbook：唯一真源见 `skills/comp-paper-zh/SKILL.md` 的「赛事合规硬门禁」节。


### 统计建模 (stats)

Template: `templates/stats/main.tex`

**Chapter structure is driven by research content, not fixed templates.**

Award-winning stats modeling papers vary wildly in structure — some organize by model, some by analysis step, some by research question. There is no "standard structure". 执行 Agent must design chapters autonomously based on the actual content in TOPIC_PLAN.md / MODELING_REPORT.md.

#### Fixed skeleton (must keep)

```

表格清单

插图清单

摘要（中英文，分页）

一、绪论/前言（研究背景 + 文献综述/研究现状 + 研究目标/内容）

  ↓

  [Middle chapters: content-driven, 执行 Agent designs autonomously, typically 3-5 chapters]

  ↓

N、结论与建议（结论 + 建议/展望 + 创新与不足）

参考文献

致谢

附录（代码）

```

#### Middle chapter design guide

After reading TOPIC_PLAN.md, design middle chapters following these principles:

**Principle 1: Chapter titles must be specific, not generic**

- ✗ "四、模型构建" → ✓ "四、基于 CNN 的水质预测模型构建与评价"

- ✗ "五、实证分析" → ✓ "五、生育意愿的影响因素——集成学习模型"

**Principle 2: Organize by research logic chain, not by textbook methodology**

- If the research has multiple sub-problems/models, each model can be its own chapter

- If the research uses a single method with deep analysis, organize by analysis steps

**Principle 3: Data and method chapters can be merged or separated**

- Simple data (one dataset) → merge into "数据与方法"

- Complex data (multi-source, heavy preprocessing) → separate chapter "数据描述与预处理"

#### Award-winning paper structure examples (reference only, do not copy)

**Example A — Classification + Path Analysis (fertility intention)**:

前言 → 模型构建 (introduce ensemble + Bayesian network) → 数据说明和预处理 → 探索性特征分析 → 生育意愿的影响因素 (ensemble results) → 生育意愿影响路径 (Bayesian network results) → 结论与建议

**Example B — Mixed Modeling (data factors & economic growth)**:

研究背景+文献 → 研究思路和模型介绍 → 理论分析 → 模型构建 (production function + regression + ARIMA, each a section) → 模型应用 (GDP prediction) → 总结与建议 → 创新与不足

**Example C — DEA Evaluation (economic sustainability)**:

绪论 → 文献综述 → 研究区域概况 → 评价指标体系构建 → 数据优化处理 (normalization + PCA) → DEA 模型建立及求解 → 结论及建议

**Example D — Deep Learning Prediction (water quality CNN)**:

绪论 → 模型构建思路与创新 → 数据描述及预处理 → 主成分分析 → CNN 模型构建与评价 (with model comparison) → 结论与展望

**Key observations**:

- No award-winning paper uses the "baseline regression → robustness → heterogeneity" causal inference structure (unless the topic IS causal inference)

- Chapter count varies from 5-7, determined by content

- "Model introduction / theoretical basis" can come before or after the data chapter

- "Innovation & limitations" can be inside the conclusion or a standalone chapter

#### Chapter design checklist (self-check before writing)

- [ ] Does every chapter title contain specific research content (not generic "模型构建")?

- [ ] Does the chapter order follow the research logic chain (reader can follow naturally)?

- [ ] Do core analysis chapters (model results) occupy 40-50% of the paper?

- [ ] Is there a dedicated data description / exploratory analysis chapter (reviewers value data understanding)?

- [ ] Does the conclusion include "innovation" and "limitations" (reviewer bonus points)?

Use Chinese numbering (一、二、三...) with sub-sections (一)(二)(三). Do not use 1、2、3 or 1.1、1.2 format.

Fixed sections that must be kept: 表格清单, 插图清单, 中英文摘要, 绪论, 结论, 参考文献, 致谢.

## 2. 模板骨架纪律（复制模板后必读）

### 2.1 只用模板、只改占位符

Use the template as-is. Only modify:

- Replace bracket placeholders (`[论文标题]`, `[中文摘要内容]`, etc.) with actual content

- Replace `\input{sections/...}` filenames if your section files have different names

- Fill in the abstract and keywords

### 2.2 CRITICAL TEMPLATE RULES 1-7（违反 = PDF 坏版）

**⛔ CRITICAL TEMPLATE RULES (violation = broken PDF):**

1. **NEVER rewrite main.tex from scratch** — the template has 100+ lines of carefully tuned preamble (fonts, margins, section numbering, citation format). Writing from scratch will break fonts, margins, and formatting.

2. **NEVER replace `\listoftables`/`\listoffigures` with hand-written text lists** — the template uses LaTeX auto-generated lists. If you write "表1.xxx\n表2.yyy" manually, the list won't update when tables change.

3. **NEVER add a separate cover page for MathorCup** — MathorCup 官方格式没有独立封面。队伍编号表格+标题+摘要都在第一页。不要自己加 `\maketitle` 或写一个大标题封面。直接用模板里的格式：表格 → 分隔线 → 标题 → 摘要。

4. **NEVER change the cover page year/届数 format** — replace `[竞赛年份]` with the actual year (e.g., `2026`), `[届数]` with the actual number (e.g., `十二`).

5. **Verify after writing**: `diff paper/main.tex` against the template — only bracket placeholders and `\input` lines should differ.

6. **MathorCup 模板验证**：检查 main.tex 使用 `\documentclass{MathorCupmodeling}`，`\bianhao{}`/`\tihao{}`/`\timu{}` 已填写。

7. **华中杯模板验证**：检查 `\documentclass[withoutpreface,bwprint]{cumcmthesis}` 未被修改，摘要使用 `\begin{abstract}...\keywords{}\end{abstract}` 环境，参考文献使用 `\begin{thebibliography}{99}...\end{thebibliography}`，附录使用 `\begin{appendices}...\end{appendices}`，不要自己加 `\usepackage{geometry}`。

### 2.3 专项模板验证：五一杯

9. **五一杯模板验证**：检查承诺书页完整保留，摘要使用手动排版（`\noindent \textbf{关键词：}` 在上，`\noindent \textbf{摘\quad 要：}` 在下，不用 `\begin{abstract}` 环境），参考文献使用 `\begin{thebibliography}`，附录第一节是文件列表表格。**⛔ 五一杯额外检查**：(a) 不要加 `\usepackage{cite}`（和 natbib 冲突会导致编译错误），(b) 不要重复加载 `\usepackage{subcaption}` 和 `\usepackage{float}`（cls 已包含），(c) 不要加 `\maketitle`（五一杯用手写承诺书页，不用 cls 的 maketitle），(d) 不要删除 `withoutpreface` 选项。

### 2.4 封面占位符与字体

The cover page uses `\fzxbsong` (方正小标宋) and `\fsgb` (仿宋GB2312) fonts with `\cline{2-2}` underlines in a tabular. These fonts have fallback definitions — if the .ttf files are not installed, they fall back to `\heiti` and `\fangsong`.

When replacing cover page placeholders, ONLY change the text inside `[...]` brackets. Do NOT touch `\cline{2-2}`, `\\`, `&`, or any LaTeX commands:

```latex

% Template has (和 cover station.tex 格式一致):

参赛学校：&[学校名称]\\\cline{2-2}

% Replace ONLY the bracket text:

参赛学校：&某某大学\\\cline{2-2}

% NEVER remove \cline{2-2} (creates underline) or & (column separator)

```

### 2.5 不得修改的清单

Do NOT modify:

- `\documentclass` line (font size, paper size)

- `\usepackage[...]{geometry}` (page margins)

- `\ctexset{section=...}` (chapter numbering format)

- `\pagestyle` / `\fancyhf` (header/footer)

- `\usepackage[...]{natbib}` or `\usepackage[...]{gbt7714}` (citation format)

- Cover page structure (封面布局)

- `\listoftables` / `\listoffigures` (表格与插图清单 — 自动生成，不要手写)

- Anything before `\begin{document}` (preamble)

- The cover page, abstract, TOC, and bibliography sections in main.tex — only replace placeholder text within them

### 2.6 章节文件与宏包

Write all chapter content in separate `paper/sections/*.tex` files. The main.tex `\input{sections/...}` lines load them automatically. Do not paste chapter content directly into main.tex.

If you need to add packages, add them after the existing `\usepackage` block, before `\begin{document}`.

Do not write main.tex from scratch — the template handles fonts, spacing, margins, citation format, headers/footers.

## 3. 华为杯官方格式硬约束（写作完成后逐项自检）

**⛔ 华为杯官方格式硬约束（版式 / 摘要 / 引用 / 提交）** —— 完整证据见
[`references/huawei-official-format.md`](references/huawei-official-format.md)，
机检字段同步在 `engine/modex-core/comp_rules.json` → `contests.comp_huawei` profiles 约束带（`hw-*` 条，vintage 2026-23rd）。
写作完成后**逐项自检**：

| 项 | 硬约束 | 自检命令/位置 |
|---|---|---|
| 页边距 | 上下左右各 **≥ 2.5 cm**（22届口径/工程保守值，23届官方无页边距条款 → comp_rules `hw-margins: unknown`；gmcmthesis.cls 默认已修 25mm，勿回退） | `grep -n "geometry" paper/main.tex` / `gmcmthesis.cls` |
| 页眉 | **禁止有页眉** | PDF 顶部 50pt 区无文字 |
| 页码 | 自**摘要页**起、页脚中部、阿拉伯数字从 1 连续 | PDF 逐页页脚 |
| 首页 | 封皮不可删，4 logo 不可替换；**除首页外不得出现单位/姓名/队号**（否则论文无效） | 全文检索校名/姓名/队号 |
| 摘要 | **≤ 2 页**、**无需英文**、必须含 **建模思路/主要方法/模型/结果与结论/创新点/关键词** 六要素 | 摘要页 PDF 提取 |
| 字体 | 题目三号黑体、一级标题四号黑体（均居中）、其余小四宋体、单倍行距 | cls 设置 |
| 参考文献 | 方括号编号、**按正文引用次序**；书籍/期刊/网络三种表述；**引用程序须注明来源**（未标注且雷同按抄袭认定） | 文末 + 正文引用处 |
| 承诺书 | 官方模板无承诺书页（21届模板实测；23届 `hw-pledge: unknown`，实践口径不变：校级材料不入论文） | 前 3 页不得命中「承诺书」（命中转人工确认） |
| 页数 | 当届 **unknown**（50 为历届内部口径不作官方主张；本轮任务口径经任务级覆盖通道下发） | `quick_gates --compliance-profile comp_huawei` |

## 4. 华为杯标题硬约束

   **⛔ 华为杯标题硬约束（其他竞赛保持原本，不受影响）**：

   - `\title{...}` 必须使用赛题官方原标题（从 `user_data/*_extracted.txt` 抄），严禁自创 "基于 X 的 Y"

   - 不要在 `\title{}` 里写 `\\` 换行（cls v1.5.0+ 已支持自动按宽度换行，多行字号保持一致）

   - 题目长就一行写完，模板自动换行渲染
