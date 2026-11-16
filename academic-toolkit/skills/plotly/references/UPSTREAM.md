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
