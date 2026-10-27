# ADAPTATION 本地化适应性改写声明 — plot-from-data

- 上游：本地完整复刻（原始上游与作者未详，来源未随件声明）。
- 本地化适应性改写内容：
  - 集成进 academic-toolkit 技能路由（SKILL.md 元数据与本仓 frontmatter 规范对齐）；
  - 数据读取路径改为仓库/工作区相对约定，去除本地环境私有路径依赖；
  - 输出落位遵循本仓 `figures/` 与 FIGURE_MANIFEST 契约；
  - 与 `_utils/` 共享检查器（figure_pdf_quality_check 等）口径对齐。
