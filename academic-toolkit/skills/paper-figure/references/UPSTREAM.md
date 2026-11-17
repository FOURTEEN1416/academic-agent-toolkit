# paper-figure references（figures4papers 收编件）来源记录

- Upstream: https://github.com/ChenLiu-1996/figures4papers （本地 fork：https://github.com/FOURTEEN1416/figures4papers，先 Fork 后集成惯例）
- Pinned commit: 0ddfbd3fc9892e804a3fa01ae46bd0d32617f2aa（2026-11-16 实测上游 main HEAD；原 3c181f85 @ 2026-09-06）
- Checklist date: 2026-09-09（2026-11-16 同步复核）
- Local use: `skills/paper-figure/references/`（semantic-palette.md 语义调色板 / composition-patterns.md 构图五模式）
- License: **CC BY-NC-4.0**（上游 LICENSE 原文 Attribution-NonCommercial 4.0 International）——仅限非商业科研/竞赛使用，与本仓库整体许可口径一致
- Local adaptation: 非照抄，适应性改写——①中文化并映射到本套件语境（"proposed method"→"本队方法/关键结果"）；②与现有 `setup_style()` elegant 低饱和板划界（语义映射层 vs 具体色板层，互补不替换）；③代码示例对齐本库 `figure_check.sh`/vision 质检与 `_utils/figure_style_guide.md` 检查口径；④补"使用顺序建议"接到出图前规划阶段；⑤**2026-09-10 增补（非上游内容，来源另行标注）**：composition-patterns.md 模式一补"印刷宽度前置条件"（三图连排专项裁定，依据为版面字号数学而非上游）；semantic-palette.md 增 §五交叉校验调色板（来源为外部公众号文章与竞赛截图，非 figures4papers，逐条标注于该节）；SKILL.md 同日增"外部规范红线"段（概念图/数据图分家等）。上游三件本体（语义映射/五模式/消融 alpha/hatch）内容未被该批增补改动。

## Upgrade rule

上游更新时先在 fork 上同步，复查 references 两份文件是否需要重收编；任何取用固定新 pinned commit 并更新本文件。

## 2026-11-16 同步记录（3c181f85→0ddfbd3，UP-8）

- 上游 2 个月变化：新增 `figure_MACL/`（4 绘图脚本 + 6 图）与 `figure_RNAGenScape/plot_comparison_speed.py`，更新 README 与 `plot_ablation.py`，删除 `figure_CellSpliceNet/figures/ablation.png`。vendor/forks/figures4papers 已镜像同步至实测 HEAD。
- NC 口径合规复核：新增内容仍为论文绘图脚本与示例图（CC BY-NC-4.0，Attribution-NonCommercial 4.0），仅限非商业科研/竞赛使用，与本仓库口径一致，复核通过。
- references 两份蒸馏件（semantic-palette.md / composition-patterns.md）的来源内容未受本次上游更新影响，无需重收编。

### 2026-11-16 收尾批：示例脚本技法吸收（收编落地，吸收自 pin `0ddfbd3`）

上一节"无需重收编"指两份蒸馏件的**源**（`scientific-figure-making/references/`）在两 pin 间未变，属实；本批在此基础上，把上游**新增示例脚本**中可泛化的绘图技法改写融入本技能（改写非照搬，来源映射如下）：

- `figure_MACL/`（plot_overview / plot_exp_task / plot_exp_sub / plot_exp_qa，+1278 行 + 12 图）→ `composition-patterns.md`：
  - 模式二增补：图级底部共享图例条（`fig.legend` + `rect` 让位）与手造图例句柄（`Line2D`/`Patch` + 数据键→展示名改名）；
  - 模式四增补：面板 y 轴向外取整到刻度步长、跨面板同指标统一 ylim；
  - 新增 §七：zorder 分层（网格 0<参考线 1<数据 3）与自定义虚线 `(0,(8,4))`、axvline 面板语义分界、个体-聚合双线（spaghetti alpha 0.2 + 粗均值线）、统一标注行（`label_y = peak + max(2, 0.08*peak)`，peak 计入参考线）、并列平均名次公式；
  - `SKILL.md`：证据溯源段补"gen_fig docstring 记数据来源/提取日期"；`_figbase.py` 引导段补"方法样式表集中一处防漂移"。
- `figure_RNAGenScape/plot_comparison_speed.py`（+66）→ `composition-patterns.md` §七-5：log 轴跨数量级柱状、乘法留白与乘法偏移标注、本队深蓝锚点+基线淡彩（与 semantic-palette §一同构，semantic-palette.md 无需改动）。
- `figure_CellSpliceNet/plot_ablation.py`（+51/-18，并删除 figures/ablation.png）→ `composition-patterns.md` 模式五增补：hatch 兼作数据组判别（留一 vs 单模态配对柱、第二组 `hatch='/'`+灰边线）、柱内标签底色按 BT.601 亮度自适应。
- **未吸收（记档）**：MACL 的 stage×task 矩阵聚合指标（final/new/seen/forgetting）属持续学习领域专用，竞赛论文低频，不进参考件；README 变更（徽章/引用格式微调）无技法价值；上游脚本硬编码 Helvetica/`text.usetex` 与本库 `academic.mplstyle` 字体链冲突，不采纳。
- License 复核：本批吸收内容仍为 CC BY-NC-4.0（口径见 `dev-docs/audits/2026-11-16-裁决落地/LICENSE_FACTS.md`），仅限非商业科研/竞赛使用，与本仓口径一致。
- 逐技能明细：`dev-docs/audits/2026-11-16-裁决落地/absorb-figures4papers.md`。

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
- 两源评估总账：`dev-docs/figure-skills-batch-assessment.md`
