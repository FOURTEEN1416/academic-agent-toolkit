## Step 4: Write each chapter

本文件是 `skills/comp-paper-zh/SKILL.md` Step 4 的执行细则；触发条件与放行判据见 SKILL.md「Workflow」。写作方法展开见 `skills/comp-paper-zh/references/writing-playbook.md`（按节读）。

### 先把这一章写好（写完再检查，检查不能代替写好）

本章的产出是给评委读的论文，不是给闸门读的报文。六条共同写法（完整展开、正反例与范文对照见 `skills/comp-paper-zh/references/writing-playbook.md` §1，动笔前读该节；方法论源 `skills/_utils/human_competition_paper_style.md`）：

1. 段首句给本段结论，后续句子给推导与数值。
2. 数值嵌进因果句（"比质量上限低 18%"），不"结果如下表"后甩一串数。
3. 章首 2-3 句交代本章解决哪个问、用什么模型族、按什么顺序展开。
4. 假设给理由、选型给对比、记号首次出现即定义——写"为什么"不写"是什么"。
5. 图题陈述发现，禁止"XX 对比图 / XX 结果图"式空题。
6. 段间靠内容承接，不用"首先/其次/最后"机械过渡链。

**⛔ CRITICAL: ALL numerical results in the paper MUST come from `figures/*.json` or `RESULTS.md`.**

**⛔ NEVER `cat figures/*_results.json`.** These result files often contain full-precision time-series arrays (tens of MB / hundreds of thousands of lines); reading them whole blows up the context — local models fail outright, and GPT-via-transit chokes on protocol translation of the oversized payload and stalls on repeated `api_retry`. **The paper text only uses scalar values (fitness / optimal solution / solve time / metrics); the giant arrays are for figures, not prose.** Before writing any result chapter, run the `summarize` script below to get a KB-level overview (scalars shown verbatim — zero precision loss — only big arrays compressed to "length + range + first 3 samples"):

```bash

cat RESULTS.md

python skills/_utils/summarize_results.py 2>/dev/null || python academic-toolkit/skills/_utils/summarize_results.py 2>/dev/null || python ../../skills/_utils/summarize_results.py

```

Every scalar you need is in `RESULTS.md` or the range/sample of the summary above. If one scalar isn't fully shown, fetch just that value with `python3 -c "import json;d=json.load(open('figures/all_results.json'));print(d['key'])"` — still never read the whole file. Copy the exact numbers into the LaTeX text. Do NOT round differently, do NOT estimate, do NOT make up numbers that "look reasonable". If a number is not in the data, it cannot appear in the paper.

**⛔ 动笔前先读获奖语料（六大板块通用：摘要/问题分析/建模推导/求解/检验/结论，一个都不能跳）：**

写每个板块前，按题型取 **2-3 张版面卡**做结构与密度参照：`academic-toolkit/data/award_layout_cards.json`（工作区 cwd 下回退 `data/award_layout_cards.json`；由 layout-distill 的 `status=done` 卡投影生成，字段 `section_tree` / `abstract_slots` / `figure_table_conventions` / `sentence_templates` / `transferable_points`）。选卡：先匹配本题 `problem_type`（国赛 A/B/C/D/E），同题型不足 3 张再按同赛事补。**当前覆盖 18/62 篇**（以文件 `coverage.ratio` 实值为准，随蒸馏推进增长）——索引外那 44 篇尚未蒸馏，**不得声称"已对标全部范文"，也不得把 62 当可用样本数**；索引文件缺席或该赛事/题型无卡时**如实说明并跳过对标**，不虚构"读过"。

```bash
CARD=data/award_layout_cards.json
[ -f "$CARD" ] || CARD=academic-toolkit/data/award_layout_cards.json
[ -f "$CARD" ] || CARD=../../data/award_layout_cards.json
python - "$CARD" <<'PY'
import json, sys
idx = json.load(open(sys.argv[1], encoding='utf-8'))
print('coverage:', idx['coverage']['ratio'], '| skipped:', idx['skipped'])
for c in idx['cards']:
    if c['problem_type'] == 'A':          # 换成本题题型
        print(c['paper_id'], '|', ' / '.join(s['title'] for s in c['section_tree']))
PY
```

| 板块 | 取卡片字段 | 配套语料（技能限定路径） |
|---|---|---|
| 摘要 | `abstract_slots` | `skills/award-paper-mining/data/abstract_golden_structure.md` |
| 全文句式与段落节奏 | `sentence_templates` + `transferable_points` | `skills/award-paper-mining/data/sentence_pattern_library.md` |
| 图表使用与版面 | `figure_table_conventions` | `skills/award-paper-mining/data/figure_table_conventions.md` + `skills/award-paper-mining/data/typography_spec.md` |
| 章节顺序与各章功能 | `section_tree` | — |

模仿其信息密度与节奏（一段承载几个论点、数值怎么嵌进叙述、推导怎么铺开）；**禁止照抄措辞**——照抄同时踩查重与 AI 痕迹两道闸。

**⛔ 数模竞赛（cumcm/huawei/mathorcup）必须严格按模板的章节顺序写：**

```

1_restatement.tex  — 问题重述（用自己的话重述，不是抄题目）

2_assumptions.tex  — 模型假设（5-7 条，每条有内容+合理性说明）

3_symbols.tex      — 符号说明（⛔ 见下方格式规则）

4_problem1.tex     — 问题一的建模与求解

5_problem2.tex     — 问题二的建模与求解

6_problem3.tex     — 问题三的建模与求解

7_sensitivity.tex  — 灵敏度分析与模型检验

8_evaluation.tex   — 模型评价与推广

A_code.tex         — 附录：代码

```

**⛔ 模型假设必须在符号说明之前。** 不要合并成一个章节，不要调换顺序。文件名必须和模板 `\input{sections/...}` 一致。

**⛔ 模型假设数量控制**：4-5 条，不要超过 6 条。每条假设 1-2 句话（假设内容 + 合理性说明），不要写成长段落。假设太多说明问题没简化好。

**⛔ 符号说明表格控制**：15-20 个变量以内。只列正文中实际使用的核心变量，不要把所有中间变量都列进去。

**⛔ 分页规则（所有章节通用）：**

- **不要在 section 文件内部加 `\newpage`、`\clearpage` 或 `\nopagebreak`** — 让 LaTeX 自动分页，手动干预容易产生空白页

- main.tex 里只在摘要后和目录后用分页，正文章节之间不要加

- compile_utils.sh 会自动移除 section 文件里的 `\newpage`/`\clearpage`/`\nopagebreak`

- **例外**：符号说明文件（compile_utils.sh 会自动转成 longtable 支持跨页）

**⛔⛔ 符号说明表格格式（必须 longtable，禁止漂浮）：**

所有竞赛模板的 `main.tex` 都加载 `\usepackage[section]{placeins}`（每节末自动 `\FloatBarrier`）。符号表若用 `\begin{table}[!ht]/[ht]/[htbp]`，放不下就被推到节末，留下"节标题 + 一句话 + 大半页空白"。**符号说明必须 `\begin{longtable}`**：非浮动、可跨页、标题不分离，无需 `\centering` 和引导文字；短表（<半页）用 `\begin{table}[H]` 就地。符号控制在 15-20 个以内、表格控制在半页以内。自检由 `symbol_layout_check`（`skills/_utils/writing_check.sh` 全家桶）接管；任何 section 文件出现 `\begin{table}[!ht]/[ht]/[htbp]` 都要改。

完整根因、longtable 模板与反例见 `skills/comp-paper-zh/references/writing-playbook.md` §2。

**⛔ 写每个章节前，先读 MODELING_REPORT.md 和 RESULTS.md 对应部分的内容。** 不要凭记忆写——数值结果、公式推导、算法步骤都必须从这些文档中提取。

**⛔ 跨章上下文 + 图数据绑定（防"两张皮"）：**

- **每写完一章**，立刻往工作区根目录 `_writing_context.md` 追加 3-5 行要点卡（核心论点／关键数字／新定义的符号术语／已讨论的图表）；**写下一章前先 `cat _writing_context.md`**，承接前文结论、复用已定义术语（不重复定义）、保持同一指标数字全文一致——详见 `skills/_utils/writing_rules.md` 的 `<chapter_context_card>`。

- **写每张图/表的分析前**，先按 `<figure_data_binding>`：从 FIGURE_MANIFEST/latex_includes 认清"这张图画的是什么量" → 去 `RESULTS.md`／`figures/all_results.json` 定位它对应的真实数值 → 分析里只用这些真值，**禁止凭图形状/位置猜数、禁止编造坐标**。

Read RESULTS.md for exact numbers — ensure paper numbers match computation results.

**⛔ 结果分析章必须逐问消费 `RESULTS.md` 的 `## 发现账本（FINDINGS）`（写每个结果段之前先读该问六项）：** baseline vs 选定、差值/消融、灵敏度/误差、机理/决策含义、对下一问的约束、适用边界。每个 **headline number（本节要评委记住的那个数）必须带一句"差在哪 / 为什么 / 改变什么决策"**——baseline 差值、机理、决策含义三者至少给一项，**禁止裸数字复述**。✗「问题一最优成本为 1.23 万元。」→ ✓「……比基准调度低 12%，差额主要来自充电窗口重排（机理），使机队规模由 6 架降到 5 架（决策含义）。」账本缺项、或只有方法名没有 baseline 对比数的，回 comp-code 补齐，不许用空泛定性话术顶替；账本六项模板见 `skills/comp-code/SKILL.md` 的 Step 7。

**⛔⛔ 创新点（模型评价/结论章）按 `skills/_utils/innovation_contract.md` 写：** 2-4 条，每条"常规做法 → 本文做法 → 差别"，差别必须带 baseline 差值或消融证据；换任何题目都成立的表述不算本题创新。

**⛔ 图文数值一致性规则：** 描述图表内容时（如"从图X可以看出，模型A的RMSE为0.023"），数值必须从 `figures/*.json` 或 `RESULTS.md` 中读取，不要凭记忆编写。写完后用 `bash ../../skills/_utils/writing_check.sh paper/`（cwd=工作区根）检查一致性。

**⛔ 长表格处理规则（>12 行的数据表格）：** 正文禁止直接放超过 12 行数据行的表格。处理：正文放缩略版（前 3 行 + 中间 `$\vdots$` + 后 3 行，可加一行汇总统计，脚注"完整结果见附录 X"），附录放完整 `longtable`（`paper/appendix/`）。写表前先数 `figures/TABLE_*.tex` 的数据行；`compile_utils.sh` 会兜底截断，但源头按本规则写。缩略版 LaTeX 示例与判断细则见 `skills/comp-paper-zh/references/writing-playbook.md` §3。

Follow the interleaving, embedding, and LaTeX rules from `skills/_utils/writing_rules.md`.

**⛔ 图文并茂硬规则（每个章节都必须遵守）：**

- 图用 `\begin{figure}[H]`、短表 `\begin{table}[H]`、伪代码 `\begin{algorithm}[H]` 就地；表禁止 `[htbp]`（会被 `\FloatBarrier` 逼到节末留半页空白），长表/符号表用 `longtable`。
- 每张图/表后必须有 ≥5 行分析文字（数值解读 + 对比 + 结论）才能放下一个；**禁止两张图连续出现中间无分析段落**。
- `\includegraphics[width=0.85\textwidth,keepaspectratio]`；不加 `height=0.38\textheight` 之类的小高度（会把图压小），仅接近整页高的图加 `height=0.9\textheight` 防溢出。**width 不得小于 `0.8\textwidth`**。
- **禁止用 `subfigure`/`subcaption` 并排多张独立 PDF**：一张图一个 figure 环境、宽度 ≥ `0.85\textwidth`。多面板数据图用 matplotlib `plt.subplots` 合成**单个 PDF**（`[2-panel]`/`[4-panel]` 走这条）。
- 数据结果图默认一张一行；只有同类可比、各自单列都只占半页且配文后留白过半时，才做 2-panel。
- **逻辑框图（流程图/架构图/技术路线图/TikZ 几何·算法·示意图）永远单列独占**，不论主题多相关都不并排。

完整判据与决策流程见 `skills/comp-paper-zh/references/writing-playbook.md` §4。

每写完一章自查体量：`wc -c paper/sections/当前章节.tex`（中文 LaTeX ≈900 字符/页）。预期 5 页的章只有 ~2000 字符就当场扩写，不留到最后。

<exemplar_depth>

### Writing depth reference

**国赛一等奖 (25-30 pages, 3 sub-problems)**:

- 问题重述+分析 (2-3p): restate in own words, extract core problems — not copying the problem statement

- 模型假设+符号说明 (2p): 4-5 assumptions (hard cap 6, each with content + justification, not too many not too few), one complete symbol table with 15-20 variables (符号/含义/单位 three columns, do not split into multiple tables)

- Each sub-problem (5-7p): model formulation (2p, with derivation and physical meaning) + solution method (1.5p, with algorithm steps) + results with table+figure (1p) + analysis (0.5-1.5p, numerical meaning + comparison with expectations + reasoning)

- 灵敏度分析 (2-3p): ≥2 key parameters, each with variation curve plot + analysis paragraph

- 模型评价 (2p): 3-4 strengths + 2-3 weaknesses + generalization directions. Pure text discussion, no figures or tables needed

**华为杯一等奖 (55-65 pages typical, comp_rules guidance 历届经验口径，非官方规定)**: deeper derivations, more thorough analysis per sub-problem (8-10p each), 灵敏度分析 (4-5p), 模型评价 (3p, pure text, no figures) with comparison to other methods

**统计建模获奖 (35-40 pages)** — chapter structure is content-driven, page allocation reference:

- 绪论/前言 (4-8p): research background + literature review (grouped by 3-4 themes, 3-5 papers per theme with detailed discussion) + research objectives

- 数据描述与预处理 (6-8p): data source + variable description table + descriptive statistics table + exploratory analysis (distribution / trend / cross-tabulation plots)

- 模型/方法 chapters (6-10p): theoretical basis + formula derivation + parameter settings + implementation details (adjust by actual number of models)

- Core results analysis (10-16p): the most important part of the paper — every result needs 2-3 paragraphs of interpretation, not just "as shown in Table X"

- 结论与建议 (3-5p): conclusions + recommendations + innovation points + limitations and future work

Common traits of award-winning papers:

- Solid exploratory analysis (cross-tabulation, group comparisons, rich visualization)

- Core analysis chapters occupy 40-50% of total pages, every numerical result has deep interpretation

- Specific chapter titles ("基于集成学习的生育意愿影响因素分析" not "模型构建")

- Include "innovation & limitations" discussion (reviewer bonus points)

| Type | Pages | Characters | References |

|------|-------|-----------|------------|

| 数模国赛 (30p limit) | 25-30 | 18000-25000 | ≥10 |

| 华为杯（历届经验口径，非官方规定；对齐 comp_rules guidance） | 40-60（一等奖通常 55-65） | 30000-40000 | ≥15 |

| MathorCup | 35-40 | 25000-35000 | ≥10 |

| 华中杯 | 25-30 | 18000-25000 | ≥10 |

| 五一杯 | 25-30 | 18000-25000 | ≥10 |

| 统计建模 | 35-40 | 25000-35000 | ≥20 |

</exemplar_depth>

<figure_usage_principles>

### Figure/table usage by competition type

**统计建模**: Figures first, tables second. Figure/table selection is driven by the actual analysis methods used — regression uses forest plots + regression tables, prediction uses prediction comparison plots + accuracy tables, classification uses confusion matrices + ROC, evaluation uses radar charts + ranking tables. Every analysis step should have a corresponding figure or table.

**数模竞赛**: "字不如表，表不如图". Every sub-problem must have independent result display (table + figure). Comprehensive comparison figures are additional supplements. Reviewers value information density and aesthetics.

Do not force figures where they are not needed (pure literature review, theoretical derivation). 执行 Agent decides figure count and placement based on content needs.

</figure_usage_principles>

<stats_figure_placement>

### Stats modeling paper figure placement rules

Figure/table selection is driven by research content, not fixed type templates. Below are figures mapped to analysis methods:

**Data description stage** (almost all papers need these):

- Descriptive statistics table (required), data distribution plots / boxplots, correlation heatmap, time series trend plots

**Model results stage** (select based on actual methods used):

- Regression: regression result table + coefficient forest plot

- Prediction: prediction comparison plot (actual vs predicted) + model accuracy table (MAE/RMSE/R²) + error distribution plot

- Classification: confusion matrix + ROC curve + model comparison table (Accuracy/F1/AUC)

- Clustering: cluster scatter plot / t-SNE + silhouette score table

- Evaluation: comprehensive score ranking table + radar chart

- Causal inference: baseline regression table + robustness check table + heterogeneity comparison plot

**Model interpretation / diagnostics stage** (select as needed):

- Feature importance / SHAP plot, residual diagnostics, sensitivity analysis plot, ablation table

**Principle**: Core result figures/tables go in the body text. Appendix only for code and very long auxiliary tables.

</stats_figure_placement>

<chapter_writing_points>

### Chapter writing points (universal, adapt to research logic)

**⛔ 写作风格铁律（所有章节都必须遵守）：**

- **禁止在正文中使用 `\begin{itemize}` 或 `\begin{enumerate}` 列表。** 黑点/编号列表是最明显的 AI 写作痕迹。必须用连贯的段落叙述。

  - 需要列举时用行内编号："（1）...（2）...（3）..."，或改写为自然衔接的连贯段落（不用"首先/其次/最后"机械过渡链——那是过程式骨架，与"首先...再...接着...最后"同属 AI 痕迹）

  - 例外：模型假设列表（可用编号）、附录

- **每段至少 3-5 句话。** 不要写只有 1-2 句的短段落。

- **连续段落不能以相同句式开头。** 如连续三段都以"本文..."开头，必须改。

- **段落长短错落。** 相邻段落字数几乎相等（差 <20%）说明节奏单一，是 AI 结构痕迹；长段展开论证、短段给结论，写作时自查。

- **图题写发现，不写「XX 对比图」。** 图题应陈述该图揭示的结论（如"误差随噪声水平升高呈指数增长"），"XX 对比图 / XX 结果图"式空标题是 AI 痕迹。

- **关键数据给误差范围或置信区间，禁止全文统一四位小数。** 所有数值一刀切同一精度是机器输出痕迹；按量纲与误差水平取有效位，关键估计量附 ± 区间或置信区间。

- **图号必须显式引用、句式换着来（标准优秀论文口径）。** 每张图都要点名"图 N"让读者对上号（硬规范，别为避免套路删图号）；要禁的是"图X展示了……从图中可以看出……"这种图作主语+空话的单调重复，不是禁止一切图作主语。相邻两图引用句式必须不同，在括号旁注（首选）／句首带出／动词引导／图作主语（带实质结论时可用）／后置印证间轮换。详见 `skills/_utils/writing_rules.md` 的"图表是论据"规则。

- **禁止元叙述和内部指令泄露。** 正文中不能出现"参赛者"、"参赛队伍"、"RESULTS.md"、"figures/*.json"、"AGENTS.md"等内部文件名或工作流术语。用"本文"代替"我们团队"，论文是独立学术文档。

**⛔⛔ 优化/规划与求解章节写法（modex-3 同源吸收 2026-09-22，置于本清单最前执行）：**

#### ⛔⛔ 优化/规划类模型：决策变量、目标函数、约束条件必须分段交代

**适用范围**：模型里出现 `\min` / `\max`、或有"最优/最省/最大化/选址/指派/排班/路径/调度/配比"这类
决策问题时**必须**照此写。**统计建模（评价指标体系 / DEA / PCA / 回归 / 预测）不适用**，按上面的
"theoretical basis → formulas → parameters"写即可。

> 依据：最优化问题的三要素就是**决策变量、目标函数、约束条件**。优秀论文通常按这条辨识顺序
> 组织；硬要求是三者各自清楚可辨。把三者混成一坨公式是评委最容易看出"没想清楚"的地方 ——
> 他扫一眼找不到"你到底在决定什么"。

**要求是"三者各自清楚可辨"，不是"必须切成三个小节"。** 惯用顺序是
决策变量 → 目标函数 → 约束条件 → 变量取值范围，照它写读者最省力；真正的硬线只有一条：
**评委扫一眼就能分清哪个是决策变量、哪个是目标、约束有几条**。

- 变量多、约束多的复杂模型（如四类变量九条约束）→ 分小节或用表格+公式承载，否则没法逐条核对
- 只有一两个变量、两三条约束的简单模型 → 一段文字 + 一个 `aligned` 公式就够，
  **不要为了凑结构硬切三个小节** —— 数模论文讲少而精，形式服务于内容

**⛔⛔ 怎么在"禁止 itemize/enumerate"的前提下把三要素分开写（必读，否则会写成一坨散文）**

上面的写作铁律禁止正文用黑点/编号列表，于是最容易出现的失败形态是**把四类决策变量和九条约束
全揉进一个自然段**（"决策变量有四类：$y_k$ 表示…；$x_{ijk}$ 表示…；模型须满足如下约束。
动用车辆数不超过 5 辆，即…。沿路线的累积载量…"）—— 信息都在，但评委无法逐条核对，
等于没写清楚。**这不是列表禁令的错，是选错了载体。** 正确做法：

| 要素 | 用什么载体 | 为什么不违反列表禁令 |
|---|---|---|
| 决策变量 | **三线表**（符号／含义／类型／下标范围）+ 表后一段讲类型理由 | 表格不是列表，全篇本来就要用表 |
| 0-1 变量的语义 | `cases` **公式** | 公式不是列表 |
| 目标函数 | `equation` 独立成式 + 一句话讲来源 | — |
| 约束条件 | 按现实机理分组；一个 `equation` 里用 `aligned` 逐条排开，组后成段解释各行含义 | 公式不是列表 |
| 变量取值范围 | 与约束同一个 `aligned` 的最后一行，或单独一式 | — |

这套载体正是运筹学论文的标准形态：**公式承担"逐条罗列"，散文承担"解释为什么"**。
⛔ 别为了守列表禁令而牺牲可核对性，也别用 `itemize` 去偷懒。

**⛔ 展示公式必须编号（PDF/LaTeX 硬线）。** 正文中的目标函数、状态方程、推导式和成组约束统一使用
非星号的 `equation` / `align` / `gather` / `multline`；禁止 `equation*`、`align*`、`\\[...\\]`
和 `$$...$$`。若多条约束只需要一个组号，用 `equation` 外层加 `aligned`；若每条都需要单独讨论，
用 `align` 逐行编号。后文会引用的公式必须加 `\\label{eq:语义名}` 并通过 `\\eqref{...}` 引用，
禁止手写固定数字。只有行内短符号和短定义不要求编号。

**⛔ 子问题章内部的小节标题要带上模型是什么，别写空标题。** 优化题最容易起成"模型建立"
"模型求解"这类谁都能套的题目，评委从目录上看不出你做了什么：

| ❌ 空标题 | ✅ 带信息的标题 |
|---|---|
| 模型建立 | 基于 0-1 整数规划的服务站选址模型 |
| 模型求解 | 分支切割法求解与最优选址方案 |
| 结果分析 | 选址方案的成本构成与覆盖率分析 |
| 灵敏度分析（作为子问题内的小节时） | 预算上限变动对选址数量的影响 |

⛔ **只管子问题章（第 4/5/6 章）内部的小节，不要拿去改章级标题。** 上面骨架里的
"1 问题重述""7 灵敏度分析与模型检验""8 模型评价与推广"是竞赛通行的章名，评委按它定位，
**照原样保留**。要带信息的是它们下面的小节，例如第 7 章内部可分
"需求波动 ±20% 下的方案稳定性""depot 位置切换的影响"。

**① 决策变量（先声明，这是全部推导的地基）**

必须交代五件事：**符号、含义、类型、下标范围、类型理由**。句式用"设 $x$ 表示…"或"记 $x$ 为…"。

- **类型理由不能省**：为什么必须取整（人数/车辆数不可分）、为什么是 0-1（选或不选，没有中间态）、
  为什么连续（可任意分割的流量/配比）。⛔ 只写"$x_j$ 为整数"不给理由 = 没想清楚。
- **0-1 变量一律用分段函数写清两种取值各自的现实含义**，不许只写"$y_j \in \{0,1\}$"：

```latex
设 $x_{ij}$ 表示是否把第 $i$ 个需求点指派给第 $j$ 个服务站，因"指派"只有成立与不成立
两种状态、不存在部分指派，故取 0-1 变量：
\begin{equation}
x_{ij}=\begin{cases}
1, & \text{第 } i \text{ 个需求点由第 } j \text{ 个服务站服务},\\
0, & \text{否则},
\end{cases}\qquad i=1,\dots,m;\ j=1,\dots,n
\end{equation}
```

**② 目标函数（独立成式，并说明"为什么是这个目标"）**

- 独立一个公式环境，带 `\min` / `\max`，不要和约束挤在一行。
- **紧跟一句话交代目标的来源**，引赛题原话（口径与 `MODELING_REPORT.md` 的目标溯源表一致）。
- 多目标要说清怎么处理（加权 / 分层 / Pareto），权重怎么定、量纲怎么统一。

```latex
题目要求"在满足全部需求点覆盖的前提下使总建设与运营成本最低"，故以总成本最小为目标：
\begin{equation}
\min\ Z=\sum_{j=1}^{n} f_j y_j+\sum_{i=1}^{m}\sum_{j=1}^{n} c_{ij} d_i x_{ij}
\end{equation}
其中第一项为服务站固定建设成本，第二项为需求点到服务站的运输成本。
```

**③ 约束条件（独立于目标、按现实机理分组，每组必须有业务含义）**

- 目标函数必须与约束分开。多条同类约束用一个 `equation + aligned`（或 `cases`）纵向罗列，默认整组
  共用一个可见编号；功率守恒、状态递推、终端条件等会被单独讨论的机理可各自独立编号。
- 默认不在论文里写 `C1/C2`、`H1/H2`、“审计项”“约束验证编号”等内部工程标签。只有正文后续确实要
  逐条引用时才设置语义化子编号，否则由公式承担罗列、由自然语言按顺序解释现实含义。
- **每组约束下面必须有业务解释**，说明各行对应题目里的哪个现实限制。
  ⛔ 只有公式没有解释 = 评委无法判断你有没有漏约束，这是最常见的扣分点。
- 每个优化子问题必须出现“独立展示的目标函数 + 至少一个约束公式组”，或明确通过 `\eqref{...}`
  说明沿用了哪些前序约束并只写新增约束；不能只用一句“满足前述全部条件”带过。
- 建议用"约束类型清单"自查有没有漏（**不是要求全都有，是用来查漏**）：

| 类型 | 典型表达 | 对应的现实限制 |
|---|---|---|
| 需求覆盖 | $\sum_j x_{ij}\ge 1$ | 每个需求点至少被服务一次 |
| 资源/预算上限 | $\sum_i b_i x_i\le B$ | 总投入不超过预算 |
| 容量约束 | $\sum_i d_i x_{ij}\le Q_j y_j$ | 单站服务量不超过其容量 |
| 总量固定 | $\sum_i x_i=k$ | 恰好选 $k$ 个 / 总量守恒 |
| 至多/至少选 | $\sum_{i\in S} x_i\le 2$ | 同一区域最多建 2 个 |
| 互斥 | $x_a+x_b\le 1$ | 两方案不能同时采用 |
| 逻辑联动（big-M） | $x_j\le M y_j$ | 未开设的站点不能有流量 |
| 时间窗 | $a_i\le t_i\le b_i$ | 必须在时间窗内到达 |
| 流量平衡 | $\sum_{\text{in}}=\sum_{\text{out}}$ | 节点不积压不凭空产生 |
| 度约束 / 子回路消除 | $\sum_{e\in\delta(S)}x_e\ge 2$ | 路径不能断成多个圈 |

- **线性化技巧必须解释,不能只丢公式**。`big-M`、分段线性、绝对值转换、
  `max` 转约束这些,都要说清"原来的非线性长什么样、为什么这样一改就等价"。
  例：$x_j\le My_j$ 的作用是"$x_j>0$ 时逼 $y_j=1$",从而把目标里只在开设时才计入的
  固定成本 $f_jy_j$ 变成线性项。⛔ $M$ 取多大也要给依据（取数据上界,不是随手写 99999）。

**④ 变量取值范围 + 模型定性（收口）**

- 非负/整数/上下界单独一行列出。
- 紧接一段说明：这是什么类型的问题（LP / ILP / MILP / NLP / 多目标 / 动态规划）、
  **规模多大**（变量数、约束数，按下标范围算出来）、**为什么选这个求解方法**
  （精确求解器还是启发式；若用启发式要说清为什么精确解不可行 —— NP-hard / 规模爆炸）。

**⛔ 反面写法（评委看不出你在决定什么）**：

```latex
（错误 ❌ — 三要素糊成一坨，决策变量从没定义过就直接用，约束没有业务含义）
本文建立如下优化模型：$\min\sum c_{ij}x_{ij}+\sum f_jy_j$，其中满足
$\sum_j x_{ij}=1$，$\sum_i d_ix_{ij}\le Q_j$，$x_{ij},y_j\in\{0,1\}$，
使用 Gurobi 求解得到最优解。
```
问题：$x_{ij}$ / $y_j$ / $c_{ij}$ / $f_j$ / $Q_j$ 全部没交代含义；没说为什么是 0-1；
两条约束不知道对应题目哪句话；没说模型类型与规模；"使用 Gurobi 求解"没说为什么能精确求解。

**⛔ 与上游一致性**：三要素的内容必须与 `MODELING_REPORT.md` 对得上 —— 目标函数要能在
它的**目标/约束原文溯源表**里找到对应行，约束条数不能少于建模阶段登记的关键约束数
（那些下游 `constraint_audit.py` 会复核）。⛔ 不许在论文里新编一个建模阶段没有的约束，
也不许把建模阶段有的关键约束在论文里悄悄漏掉。

#### ⛔ 每个模型的建模小节必答「人类痕迹四问」

评审实测反馈：「模型建立过程一点没有」「找不到公式」——AI 式建模只把公式摆出来，看不见人的决策痕迹。
每个建模小节动笔前自问四问，答不上来就是没写完（第四问可与检验章节呼应，但必须点名）：

1. **为什么选这个方法**：对比过哪些替代方案、各自为何不合适（一两句写进正文，与摘要"候选方法对比"要素同源）；
2. **参数从哪来**：数据估计、文献取值还是标定实验，给出处与取值依据，不凭空落数；
3. **完整推导链**：从假设到结论逐步呈现，关键一步一行，读者能跟着验算；禁止只给终式；
4. **这个模型哪里脆弱**：哪里可能失真、对哪个假设或参数最敏感——检验章节（灵敏度/误差界）必须回应这一问。

**正反对照（建模小节开头怎么写）**：

- ❌ AI 式：直接抛公式。"建立 XGBoost 模型：[公式]。参数取 n_estimators=500。"——看不见选择理由、参数依据与推导过程，评委有理由怀疑模型是抄的。

- ✅ 人类式：先说约束冲突，再引出建模选择。"样本特征含连续与类别两类量纲，直接最小二乘会被类别维度主导，故先将类别量做目标编码，再以梯度提升树拟合非线性项：[公式]。树深与学习率按 5 折交叉验证在训练段标定；弱学习器个数受样本量约束取 500（附录参数表）。该模型对编码泄露最敏感，第 X 章灵敏度分析单独检验。"

#### ⛔⛔ 求解小节：写"解为什么可信"，不要复述算法原理

数模论文的核心是**建模**与**求解**，不是算法教学。评委关心的是"模型对不对、这个解可不可信"，
不是"你能不能把遗传算法讲清楚"。**算法叙述要短。**

| 该写（占求解小节大头） | 不该写（教科书内容，最多一句带过） |
|---|---|
| 为什么选这个解法（问题规模／NP-hard／精确解可行性） | 遗传算法的选择、交叉、变异怎么操作 |
| 能解释结果的比较：与基准/边界对照、误差、容量余量、参数变化 | 模拟退火的 Metropolis 准则推导 |
| 关键实现选择及其理由（怎么分解、怎么线性化、种子怎么构造） | 逐行伪代码、时间复杂度 $O(n^2)$ 的推导 |
| 结果的现实边界（容量余量、误差范围、适用条件） | 算法的历史沿革与文献综述 |

**⛔ 算法名 + 一句作用 + 引文，就够了。** 例："用 OR-Tools 约束路由求解器\cite{xx}、
以几何种子初始化的模拟退火\cite{xx}、以及 CBC 整数规划\cite{xx} 三种原理不同的方法
交叉求解，三者收敛到同一目标值则可相互印证。"—— 不要再展开这三种方法各自怎么工作。

> ⛔ 上例的 `\cite{}` 只是占位写法；**实际用哪个引用命令按模板**，唯一真源见 SKILL.md「引用命令」表（`\upcite` 只在 cumcm / 华中杯 / wuyi / dongsansheng 有定义，其余模板写它会 undefined control sequence）。

**⛔ 不要为了篇幅去写伪代码和复杂度分析。** 那是计算机类论文的体例。
数模论文里它们属于**附录内容**：伪代码放 `paper/appendix/`，算法参数（初温、降温率、迭代数、
求解器时限、随机种子）也一并列进附录的参数表。正文只需一句"全流程以固定随机种子运行，
结果可复现，参数见附录 X"。

**要交代清楚的是下面这些事，怎么组织、放在哪个小节、要不要单独设节，由题目自己定：**

- 求解难度与方法选择的理由（规模、是否 NP-hard、精确解可行不可行）
- 关键实现选择及其依据（怎么分解、怎么线性化、多起点怎么构造）
- **结果的解释边界**：与基准或理论界的差异、误差范围、哪项容量最接近上限、结论在哪些参数范围内稳定。
  后台逐项检查仍必须运行，但正文只保留其中有数学或现实解释价值的数值，不写函数名和通过状态。

⛔ **不要套固定的小节名或固定条数。** 有的题一段话就说完（模型简单、调用现成求解器直接出解），
有的题需要单独讨论误差、敏感性或基准比较；单纯确认约束未被违反不值得另设一节。
判断标准只有一个：**读者能否确信这个解是对的**。数模论文讲少而精，
没内容的小节标题比没有小节更糟。

⛔ 唯一的比例硬线：**"解为什么可信"的篇幅不能少于"算法怎么工作"的篇幅。** 前者是评委看的，
后者是教科书内容。

**⛔ 诚实边界**：解析下界／松弛界**不是可行方案**，它与最优解的差值只能用来确认"最优解没有
异常偏低"，**不能解读成"还有这么多优化空间"**。这条写错是硬伤。

**Expansion strategies** when content is thin (not padding — substantive content):
- Formula listed without derivation → add step-by-step derivation with physical meaning explanation
- Result with only "如表所示" → add 2-3 paragraphs of interpretation (numerical meaning, comparison with expectations, reasoning, comparison with other methods)
- Assumptions as bare list → add justification for each assumption
- Literature review only lists papers → add method summary for each and connection to this work

**⛔⛔ 扩写只能往「建模深度」和「结果可信度」上扩，不许往「算法叙述」上扩。**
数模论文的核心是建模与求解，算法原理是教科书内容。篇幅不够时该补的是：
模型假设的合理性论证、口径定义的推敲、结果与预期/基准的对比、灵敏度与鲁棒性、
约束松紧分析、结论的业务含义 —— 而**不是**把遗传算法的交叉变异步骤展开写、
不是加逐行伪代码、不是补时间复杂度推导（那些属附录）。
⛔ 判据：正文里"算法怎么工作"的字数若超过"解为什么可信"的字数，就是写反了。

**绪论/前言** (all papers):

- Research background (why this problem matters) → Literature review / research status (what others did, what gaps remain) → Research objectives / content / contributions → Paper structure overview

- Literature review organized by theme (≥15 citations), not chronologically listed

**数据与预处理** (almost all papers need this):

- Data source → Sample description (time range / sample size / variable count) → Variable definition / coding table → Missing value / outlier handling → Exploratory analysis (distribution plots / trend plots / cross-tabulation)

- Exploratory analysis is a key capability demonstration for reviewers — do not skip

**模型/方法 chapters** (organize by actual research content):

- Each model/method: theoretical basis (1-2 paragraphs) → mathematical formulas → parameter setting rationale → implementation details

- Multiple models: can introduce all models first then show results (Example B style), or give each model its own chapter with results (Example A style)

**结果分析 chapters** (core, should occupy 40-50% of paper):

- Every result must have: numerical presentation (table/figure) → interpretation (2-3 paragraphs, not just "as shown in Table X") → comparison with expectations / other methods → reasoning

- Multi-model comparison: horizontal comparison table + rationale for selecting the best model

**结论与建议**:

- Main conclusions (echo research objectives) → Policy / application recommendations (specific and actionable) → Innovation points → Limitations and future work

- "Innovation & limitations" can be inside the conclusion or a standalone chapter (Example B style)

- ⛔ 结论章禁止复述摘要：不复述各问数值结果，必须给出局限性与适用边界（模型在哪类场景失效、对哪个假设/参数最敏感、结论在什么范围内成立）

- ⛔ 创新点按 `skills/_utils/innovation_contract.md` 写（2-4 条，每条"常规做法 → 本文做法 → 差别"，差别带 baseline/消融证据）——与结果章、摘要同一口径，不另起一套说法

</chapter_writing_points>
