# ADAPTATION 本地化适应性改写声明 — plot-from-data

- 上游：本地完整复刻（原始上游与作者未详，来源未随件声明）。
- 本地化适应性改写内容：
  - 集成进 academic-toolkit 技能路由（SKILL.md 元数据与本仓 frontmatter 规范对齐）；
  - 数据读取路径改为仓库/工作区相对约定，去除本地环境私有路径依赖；
  - 输出落位遵循本仓 `figures/` 与 FIGURE_MANIFEST 契约；
  - 与 `_utils/` 共享检查器（figure_pdf_quality_check 等）口径对齐。

## 样例分发裁决（2026-11-16）

- 本技能 `examples/*.png`（20 张，含取自 `vendor/forks/paper-plot-skills/originals/` 的
  10 张原图与 10 张复现图）的公开分发，经 owner 于 2026-11-16 裁决确认**可随公开仓
  分发**；旧表述「样例仅本地使用、不再分发」作废（台账：dev-docs/vendor-asset-index.md
  #20 行）。
- 边界不变：上游 paper-plot-skills **代码**仍无 License，维持仅本地对照使用、不得
  再分发；本裁决仅覆盖样例 PNG。
