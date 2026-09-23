# paper-figure references（figures4papers 收编件）来源记录

- Upstream: https://github.com/ChenLiu-1996/figures4papers （本地 fork：https://github.com/FOURTEEN1416/figures4papers，先 Fork 后集成惯例）
- Pinned commit: 3c181f85e82c6f24948fcaaf3be6696102b41d8d（2026-09-06 上游 main HEAD）
- Checklist date: 2026-09-09
- Local use: `skills/paper-figure/references/`（semantic-palette.md 语义调色板 / composition-patterns.md 构图五模式）
- License: **CC BY-NC-4.0**（上游 LICENSE 原文 Attribution-NonCommercial 4.0 International）——仅限非商业科研/竞赛使用，与本仓库整体许可口径一致
- Local adaptation: 非照抄，适应性改写——①中文化并映射到本套件语境（"proposed method"→"本队方法/关键结果"）；②与现有 `setup_style()` elegant 低饱和板划界（语义映射层 vs 具体色板层，互补不替换）；③代码示例对齐本库 `figure_check.sh`/vision 质检与 `_utils/figure_style_guide.md` 检查口径；④补"使用顺序建议"接到出图前规划阶段；⑤**2026-09-10 增补（非上游内容，来源另行标注）**：composition-patterns.md 模式一补"印刷宽度前置条件"（三图连排专项裁定，依据为版面字号数学而非上游）；semantic-palette.md 增 §五交叉校验调色板（来源为外部公众号文章与竞赛截图，非 figures4papers，逐条标注于该节）；SKILL.md 同日增"外部规范红线"段（概念图/数据图分家等）。上游三件本体（语义映射/五模式/消融 alpha/hatch）内容未被该批增补改动。

## Upgrade rule

上游更新时先在 fork 上同步，复查 references 两份文件是否需要重收编；任何取用固定新 pinned commit 并更新本文件。

## 2026-09-11 追加：绘图 skills 批次（SciPilot / fig-academic）

- 来源一：https://github.com/Haojae/scipilot-figure-skill （本地 fork：FOURTEEN1416/scipilot-figure-skill）
- Pinned commit: 43098ddb9e6a6d142218540c114f9ed38922fc42（2026-06-15 上游 HEAD）
- Checklist date: 2026-09-11
- License: **MIT**
- Local use: `pitfalls-and-intent.md`（选图论证三轴+十八坑拦截清单，适应性改写自 chart_selection.md + viz_pitfalls.md）
- 来源二：https://github.com/TingxiYu/academic-figure-skill （本地 fork：FOURTEEN1416/academic-figure-skill）
- Pinned commit: 1df9940dd01ac939f072b12fe28d6353b79b90f9（2026-07-12 上游 HEAD）
- License: **Apache-2.0**（含 NOTICE 义务，保留于 vendor/forks/academic-figure-skill）
- Local use: composition-patterns.md 增补（期刊栏宽 89/183mm 锚点 + 多面板反冗余三原则：三层递进/Hero Panel/叙事排序）
- 两源评估总账：`dev-docs/figure-skills-batch-assessment.md`（含无 License 三库仅本地对照的裁定）
