---
name: scholarly-publishing
description: "Use when planning an end-to-end scholarly publishing workflow, including manuscript source-of-truth, submission assets, revision/rebuttal files, camera-ready checks, reproducible build expectations, and publication package structure."
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob]
---

# Scholarly Publishing (论文投稿全流程)

## 你会得到什么（输出契约）

当用户说“我要投稿/返修/相机就绪/需要 LaTeX 工程化/写 rebuttal/写 cover letter”时，本 skill 负责把目标拆成**可交付的出版资产包**：

- `manuscript/`：论文源文件（LaTeX / Word / Markdown 任一作为 *source-of-truth*）
- `figures/`：每张图的源代码/源数据/最终导出要求（PDF/EPS/SVG/TIFF）
- `supplement/`：补充材料（方法细节、附录、扩展实验、额外图表）
- `submission/`：投稿所需文件（cover letter、graphical abstract、highlights、checklist、打包 zip）
- `revision/`：返修资产（rebuttal、diff、逐条回应矩阵）
- `build/`：可复现构建产物（PDF、打包 zip、CI 日志）

> 目标不是“写一段文字/画一张图”，而是产出**能提交、能返修、能复用、能审计**的一套文件与规范。

---

## 何时使用（触发场景）

适用场景（中英混合均可）：
- 投稿/返修：`投稿`、`submission`、`返修`、`revision`、`rebuttal`、`回复审稿意见`、`camera-ready`、`proof`
- LaTeX 工程化：`latex template`、`latexmk`、`bibtex`、`biber`、`Overleaf`、`chktex`、`latexindent`
- 可复现出版包：`manuscript as code`、`reproducible manuscript`、`submission zip`、`paper pdf build`

不适用：
- 仅“从 PDF 提取文本/合并 PDF/批注回复”等纯文档处理。
- 仅“画流程图/概念示意图/数据结果图/组会幻灯片”，且不涉及投稿资产包或出版交付。

---

## 输入信息（最小问询）

为了稳定落地，至少需要：
1) **目标投向**：期刊/会议/出版社（不知道也可以先用“类目”：Nature/IEEE/ACM/NeurIPS/PLOS）
2) **论文类型**：研究论文/方法论文/综述/短文/技术报告
3) **交付物**：投稿包、返修包、camera-ready 包、可复现构建包、项目主页/视频摘要/海报等传播资产（可多选）
4) **写作来源**：是否已有草稿/数据/图？（已有就以“改稿/补齐规范”为主）

---

## 工作流（可执行流程）

### Phase 0 — 选择“单一事实源”（Single Source of Truth）

在以下三者中选一个做源文件（强烈建议只选一个）：
- **LaTeX**：适合期刊/会议、公式多、需要严格排版、可 CI 构建
- **Word**：适合部分医学生命科学期刊/协作者偏 Word 的团队
- **Markdown/Quarto**：适合技术报告/内部报告/可发布网页（可导出 PDF）

> 元规则：同一论文不要在多个格式里并行编辑。其它格式只能是“导出物”。

### Phase 1 — 先建“投稿约束”再写正文

1) 目标投向与模板：记录版式、匿名、页数、图表、引用和补充材料约束
2) 投稿清单：按 pre-submission、submission、revision、camera-ready 四类阶段列出必需文件
3) 明确图的规格：列出每张图的用途、类型（line art / raster / combination）与导出格式（PDF/TIFF）

### Phase 2 — 论文主线（写作）

执行两段式写作：
- 先写“结构大纲（允许 bullet）”
- 再写“最终正文（必须段落，禁止 bullet）”

元规则（顶级期刊通用）：
- **先图后文**：Results 的主线由 Figures 驱动
- **句子不超载**：每句一个主张；每段一个中心句；每节一个问题
- **让审稿人省力**：方法可复现、统计可追溯、图注自解释

### Phase 3 — 图表交付约束

本 skill 只定义投稿所需的图表交付约束，不在正文内要求调用其它作图专家：
- 对 data figure：统一字体、字号、线宽、配色、子图间距、panel label（A/B/C）
- 导出：优先 `PDF/EPS/SVG`（矢量），必要时 `TIFF 600dpi`（栅格）
- 可访问性：色盲友好（Okabe-Ito / colorcet / cmcrameri）

### Phase 4 — LaTeX/构建/打包

如果 source-of-truth 是 LaTeX：
- 明确本地编译命令、lint/format 要求、CI 编译要求和 submission zip 文件清单

如果 source-of-truth 是 Word：
- 仍然遵循“图表输出标准 + 引用一致性 + 文件命名规范”，并准备投稿系统所需附件

### Phase 5 — 投稿与返修

- 投稿前：列出主文稿、图表、补充材料、伦理/数据/利益冲突声明、cover letter
- 返修：维护逐条回应矩阵、修改位置、证据来源和未采纳理由
- 相机就绪：检查最终版式、作者信息、版权/许可、源文件和最终 PDF

### Phase 6 — 传播资产（可选）

如果需要项目主页、视频摘要或海报，先定义输入来源、目标受众、输出目录和会议/机构限制。本 skill 不负责生成幻灯片，也不在正文内要求调用传播类专家。

---

## 规范（Meta Rules）

### A. 资产命名规范

- 图文件：`fig-01-overview.pdf`、`fig-02-results.tiff`
- 子图：`fig-02A-...`、`fig-02B-...`
- 统一用 `kebab-case`；避免空格与中文；避免“final_v7_reallyfinal”

### B. 可复现性最小集（Reproducibility Minimum）

至少提供：
- 构建命令（`make pdf` / `latexmk` / `quarto render`）
- 环境说明（Python 版本、依赖，或 lockfile）
- 图表源（代码/参数）与导出脚本（自动化优先）

### C. 质量门禁（提交前自检）

- 字体一致、字号可读、线宽统一
- 统计图包含不确定性（CI/SEM/SD）并在 caption 解释
- 图注自包含：看 caption 能理解图表达什么、样本量、统计检验
- 引用准确：每个关键主张可追溯到数据或引用

---

## 案例库（GitHub 高信号仓库）

见：`references/case-library.md`（按“写作清单/论文工程化/出版包/返修资产”分类）

---

## 快速调用示例（给 VCO 路由用）

- “我要投稿 Nature 风格论文：请给出投稿资产包目录结构 + checklist + 图表导出标准”
- “顶刊作图：matplotlib 多子图 + 色盲友好 + 导出 PDF + TIFF 600dpi（每张图的规范写清楚）”
- “我要回复审稿意见：请生成 rebuttal 矩阵，并给出逐条回应的写作规范”
- “请把当前 LaTeX 项目接入 GitHub Actions 自动编译并生成 submission zip”
