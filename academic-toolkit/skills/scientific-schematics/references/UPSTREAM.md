# Scientific Schematics 技能来源记录

- Upstream: https://github.com/FOURTEEN1416/openscience（fork 自 synthetic-sciences/openscience， 科研绘图能力扩展集成）
- Pinned commit: 40d8e07（2026-11-16 实测上游 main HEAD 40d8e070bc52a5d735653573a8c321390ecbb500，v2.0.153 线；原 85f1d46）
- Checklist date: 2026-08-28（2026-11-16 同步复核）
- Local use: `skills/scientific-schematics/`（SKILL.md 及附带 references/assets/scripts）
- License: Apache-2.0（见仓库 LICENSE）
- Local adaptation: 原样集成，未改动 SKILL.md 正文；路径引用按本套件目录结构解析。

## Upgrade rule

上游 fork 更新后，对比 SKILL.md 与附带资产再同步；同步后刷新本文件的 Pinned commit 与 Checklist date。

## 同步评估（2026-11-16，85f1d46→40d8e07，UP-10）

- vendor/forks/openscience 已镜像同步至实测 HEAD。⚠️ 上游已将本技能来源目录重构迁移：`visualization/scientific-schematics` → `backend/cli/skills/core/schematics`（文件命名 best_practices.md→best-practices.md，新增 review-loop.md/style-guide.md/trim_margins.py）。
- 技能侧重收编**待专项按改写融入规程执行**：上游重构后目录与文件名变化需逐件映射，本仓附加件（QUICK_REFERENCE.md/README.md/example_usage.sh/test_ai_generation.py）的存续逐一裁决后再合并，不盲目覆盖。
