# ADAPTATION 本地化适应性改写声明 — plot-from-data

> 依据 2026-09-28 修订规则（无 License 上游件经过本地化适应性改写后可推送）入库。

- 上游：无 License 上游技能，本地完整复刻（原始上游与作者未详，来源未随件声明）。
- 本地化适应性改写内容：
  - 集成进 academic-toolkit 技能路由（SKILL.md 元数据与本仓 frontmatter 规范对齐）；
  - 数据读取路径改为仓库/工作区相对约定，去除宿主私有路径依赖；
  - 输出落位遵循本仓 `figures/` 与 FIGURE_MANIFEST 契约；
  - 与 `_utils/` 共享检查器（figure_pdf_quality_check 等）口径对齐。
- 风险与边界：上游无 License，本仓以"本地化改写衍生物"形态分发；如权利人提出主张，
  将按删除流程处理（见根 README 的资产溯源说明）。
