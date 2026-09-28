# Case Library（高信号 GitHub 案例库）

本文件用于给 `scholarly-publishing` / `submission-checklist` / `manuscript-as-code` / `latex-submission-pipeline` / `slides-as-code` 提供可复用的案例参考。

> 注意：我们不照搬内容，而是抽取其“可复用结构/规范/自动化管线”。

## 1) 写作清单 / 投稿清单

- `khufkens/paper_writing_checklist`：论文写作 checklist（适合做 pre-submission 自检清单）
- `philippbayer/submission_checklist`：投稿检查清单（可移植到 `submission-checklist`）
- `writing-resources/awesome-scientific-writing`：科学写作资源合集（做“引用库/训练素材”）

## 2) Manuscript-as-code（论文工程化）

- `manubot/rootstock`：可复现论文模板（CI、引用、协作）
- `manubot/manubot`：Manubot 工具链（引用、构建、协作写作）
- `greenelab/deep-review`：深度同行评审/结构化评审实践（适合返修/审稿视角）

## 3) 顶刊作图 / 发表级图形规范

- `garrettj403/SciencePlots`：matplotlib 风格文件与发表风格配置
- `holoviz/colorcet`：高质量色图/调色板（含色盲友好方案）
- `callumrollo/cmcrameri`：科学可视化 colormap（感知一致性）
- `nschloe/tikzplotlib`：matplotlib → TikZ（用于 LaTeX 论文矢量图）

## 4) LaTeX 工程化 / CI 构建

- `xu-cheng/latex-action`：GitHub Actions 编译 LaTeX 的常用 action
- `overleaf/chktex`：LaTeX lint（常见错误/风格问题）
- `cmhughes/latexindent.pl`：LaTeX 格式化工具（latexindent）
- `borisveytsman/acmart`：ACM 官方模板与规范示例
- `tuna/thuthesis`：大型 LaTeX 模板工程化示例（结构、宏包、文档化）

## 5) Slides-as-code / Web Slides

- `hakimel/reveal.js`：网页幻灯片框架（可导出/可嵌入交互）
- `slidevjs/slidev`：Markdown → Slides（开发者友好）
- `marp-team/marp`：Markdown → Slides（更偏版式控制）
- `quarto-dev/quarto-cli`：Quarto（报告/论文/幻灯片一体）
- `astefanutti/decktape`：网页 slides 导出 PDF（用于 reveal.js 等）

