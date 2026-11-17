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

## 收编执行（2026-11-16，40d8e07 落地）

- SKILL.md：按改写融入规程合并上游 v2.0.0 重写——吸收 describe→render→score→refine 回路、五维评分量规（0–2×5）与文档类型阈值（journal 8.5 / conference·thesis·grant 8.0 / preprint·report 7.5 / poster 7.0 / slides 6.5）、描述规范（类型/组件/流向/强调）、2K 终稿 + trim_margins 裁边、既有图精炼（edit 意图）等；宿主特征内容（Ace 网关、Customize→Models、task/subagent_type 等运行时绑定）改写为宿主中性表述。本仓治理层 Step 0（多模态后端强制检测）与"执行与产出"段原样保留；frontmatter 保留本技能名 scientific-schematics 与 category visualization，补 license/version 与 K-Dense 来源 metadata。
- references/：best_practices.md 按上游新结构改名 **best-practices.md**（内容吸收：来源注记、"How this relates to the generator"节、"图内不编 Figure 号"条目）；新增 **review-loop.md**（回路机制、评审日志 JSON 合同含"评审未跑成"的如实 null 态、Python/CLI 用法、成本纪律、提示词技巧、四个工作示例）与 **style-guide.md**（构图/配色 Okabe-Ito/字体/形状词表/箭头/强调/常见失败），均改写并宿主中性化。
- scripts/：新增 **trim_margins.py**（Step 6 裁边后处理，原样功能）；generate_schematic_ai.py 吸收上游 BYOK 防护修复（`_byok_key` 同时拒绝 `thk_`/`osk_` 托管 token 前缀）；generate_schematic.py 与上游一致未动。
- 本仓附加件全部保留：QUICK_REFERENCE.md、README.md、example_usage.sh、test_ai_generation.py（内容与脚本现状一致，未盲目覆盖）。
- 上游许可：openscience 仓库 Apache-2.0（vendor LICENSE 实文）；本技能上游自述 MIT、原始作者 K-Dense Inc.。
