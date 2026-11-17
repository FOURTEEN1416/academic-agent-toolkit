# Plotly 技能来源记录

- Upstream: https://github.com/FOURTEEN1416/openscience（fork 自 synthetic-sciences/openscience， 科研绘图能力扩展集成）
- Pinned commit: 40d8e07（2026-11-16 实测上游 main HEAD 40d8e070bc52a5d735653573a8c321390ecbb500，v2.0.153 线；原 85f1d46）
- Checklist date: 2026-08-28（2026-11-16 同步复核）
- Local use: `skills/plotly/`（SKILL.md 及附带 references/assets/scripts）
- License: Apache-2.0（见仓库 LICENSE）
- Local adaptation: 原样集成，未改动 SKILL.md 正文；路径引用按本套件目录结构解析。

## Upgrade rule

上游 fork 更新后，对比 SKILL.md 与附带资产再同步；同步后刷新本文件的 Pinned commit 与 Checklist date。

## 同步评估（2026-11-16，85f1d46→40d8e07，UP-10）

- vendor/forks/openscience 已镜像同步至实测 HEAD（6141 文件更新、632 项上游重构删除；上游高频发版大版本演进）。GitHub 端 FOURTEEN1416 fork 仓库的同步推送须由仓库所有者执行（本仓不代推）。
- 上游技能包变化：plotly 位于 `backend/cli/skills/visualization/plotly`（SKILL.md 与 chart-types.md 大幅重写）；scientific-schematics 重构迁移为 `backend/cli/skills/core/schematics`（文件改名 best-practices.md，新增 review-loop/style-guide/trim_margins）。
- 技能侧重收编**待专项按改写融入规程执行**：本仓 SKILL.md 含"执行与产出"适配段（执行会话/溯源门禁），上游新版亦全文重写——直接覆盖会丢失适配层；须重放适配后收编。宿主特征词预检：上游新版 plotly 三件 0 命中。

## 收编执行（2026-11-16，40d8e07 落地）

- 已融入（改写）：SKILL.md frontmatter——description 增补路由语义（dashboards/exploratory/presentations；静态出版图改派 matplotlib / scientific-visualization）；metadata 修正真实来源链（origin: K-Dense-AI/scientific-agent-skills，adapted-by: Synthetic Sciences，skill-author/author: K-Dense Inc.）。capabilities/catalog.json 的 plotly 条目 description 已同步。
- 保留（本仓裁决成果）："执行与产出"适配段（执行会话/合同/figure_provenance 溯源门禁）原样保留。
- 未融入及原因：references/chart-types.md 上游 delta 仅一处代码示例 `)])`→`)]`，经核对为上游引入的语法残缺（3D Mesh 示例少一个右括号），不吸收；references/layouts-styling.md 上游 delta 仅示例 colorway 三色改为 plotly 默认色，属低价值噪声，不吸收。export-interactivity / graph-objects / plotly-express 三件与上游完全一致。
- 上游许可：openscience 仓库 Apache-2.0（vendor LICENSE 实文）；plotly 技能件上游自述 MIT、原始作者 K-Dense Inc.。
