## Step 3: Figure inventory + mandatory embedding plan

本文件是 `skills/comp-paper-zh/SKILL.md` Step 3 的执行细则；触发条件与放行判据见 SKILL.md「Workflow」。

Before writing any chapter, build a complete inventory of available figures:

```bash

ls figures/*.pdf figures/TABLE_*.tex figures/TABLE_*.md figures/tikz_*.pdf 2>/dev/null

cat figures/latex_includes.tex 2>/dev/null   # figure→PDF 映射真源：每个 \begin{figure} 块从这里复制

```

**⛔ MANDATORY: Build a FIGURE EMBEDDING PLAN before writing any chapter:**

```

FIGURE EMBEDDING PLAN:

1. fig_desc_stats.pdf → 第三章 描述性统计 → caption: "图X 核心变量描述性统计分布"

2. fig_model_comparison.pdf → 第四章 模型对比 → caption: "图X 模型性能对比雷达图"

3. TABLE_regression.tex(PDF模式) / TABLE_regression.md(Word模式) → 第四章 回归分析 → caption: "表X 回归分析结果"

4. tikz_diagrams.pdf (几何/算法/架构 TikZ, from latex_includes.tex) → 对应章节 → caption: "图X 弦长递推几何关系示意"

```

> 表格按输出模式选格式：PDF 模式 `\input{figures/TABLE_*.tex}`；Word/docx 模式 `cat figures/TABLE_*.md`。figures/ 里有几个 TABLE 文件就嵌入几个，一张不漏。

**Rules:**

- **⛔ 图表嵌入受引擎 `figure_narrative` 强制闸**：finish 时全量重扫正文，凡「全文零 `\ref` 引用」的**零引用孤儿**（旁有叙述不豁免——"如下图所示"不算引用）与「被引用但零解读」的图直接拒绝完成（真实终版曾 20+ 图中 11+ 张孤儿——图海堆砌是图表 AI 味首因）。嵌入每张图时**同步写两句**：引用句（"图~\ref{fig:xxx} 显示……"）+ 解读句（该图揭示的结论）。没有解读可写的图不要嵌入。

- **⛔ 图表 caption 必须是中文**（中文论文）。如果 `latex_includes.tex` 里的 caption 是英文，嵌入时必须翻译成中文

- **⛔ 必须使用 `latex_includes.tex` 里的 figure 代码块**，不要自己写 `\includegraphics`。直接复制整个 `\begin{figure}...\end{figure}` 块，只改 caption 为中文

- **⛔ TikZ 图必须嵌入**：`latex_includes.tex` 里每个引用 `tikz_diagrams.pdf` / `tikz_*.pdf` 的 `\begin{figure}...\end{figure}` 块都要复制到对应章节，一张都不能漏

- **⛔ 图片路径必须是 `../figures/xxx.pdf`**（因为 sections/ 在 paper/ 下面）

- Only embed figures whose PDF files actually exist — do not create figure environments for PDFs that don't exist

- **⛔⛔ 图要由论证自然引出，而不是套模板句（铁律）**：每张图都要嵌在行文里，让正文的论证需要"顺理成章地"引出它，读者读到这里正好需要看这张图。判断标准只有一个——**读起来是流畅的承上启下，不是逐张贴标签**。

  - **✅ 要达到的三个目的（是目的，不是句式模板，更不是每张图都要照抄的固定结构）**：让读者明白 ①这张图在讲什么、②它承接上文的什么、③它支撑什么结论。怎么把这三点织进段落、按什么顺序、用什么句式，由你按当时的行文自由安排——可以先给结论再放图印证，可以先描述现象再引出图解释。**要变的是"怎么写"（句式、切入角度、顺序），不变的是"写多深"。**

  - **⛔⛔ 图后解读的深度底线（铁律，本次要根治的第二个核心问题）**：每张图后面的解读**绝不能一句话带过**（像"见图 24：盘入螺线、两段圆弧与盘出螺线在切点处光滑连接"这样单句收尾就是失败）。每张图的配文（图前引导+图后解读合计）**必须落地这三样，缺一不可**：①**具体数值**——从图里读出的关键数字（极径 4.229m、缩短 7.59%、峰值 1.72 m/s 等），不是泛泛说"趋势明显"；②**对比或趋势**——和基准/其他方案/前一问的对照，或量沿某轴怎么变；③**推论或衔接**——这张图证明了什么、暴露了什么瓶颈、引出下文哪一步。做不到这三样，说明这张图对论证没用，那就不该放。

    - **❌ 敷衍反例（现在的通病，禁止）**：「弧长优化过程与对比见图 25：多起点收敛到同一最优邻域，最优值稳定低于基准。」——只有一句、没有数值、没有量化对比、戛然而止。

    - **✅ 标杆正例（要模仿的充实度）**：「由图 15 可见，碰撞半径随螺距增大严格单调下降：螺距由 0.4m 增至 0.55m 时，碰撞半径由 7.04m 单调降至 2.289m；数据点与 R_t=4.5m 阈值线的交点恰对应临界螺距 p_min=0.448m，交点左侧盘不进边界、右侧可盘入。曲线在交点附近斜率适中，说明临界螺距的反演稳定、二分求根条件良好。」——数值、单调趋势、阈值交点、稳定性推论俱全，且句式自然不套路。

  - **⛔⛔ 严禁句式套路化（本次要根治的核心问题）**：绝对不许把每张图都写成同一个骨架的句子，尤其是「【图类型】（如图 N）+ 动词 + 一句结论」这种统一开头（例："瀑布图（如图 33）把……"、"雷达图（如图 34）对比……"、"热力图（如图 35）表明……"——连续几张图都这么起头就是失败）。**相邻的图、同一节里的图，引导句的切入角度和句式必须换着来**：有的从上文结论切入、有的从要回答的问题切入、有的从图里的反常现象切入、有的干脆把图揉进正在展开的论述里不单独起句。像好论文那样叙述，而不是给每张图发一张格式一样的说明卡。

  - **✅ 图号必须显式引用（学术规范，与"去套路化"并行不悖）**：每张图在正文里都必须被明确点名（"图 N"），让读者能把这段文字准确对应到是哪张图——这是数模/论文的硬规范，不能为了避免套路就把图号删掉。**要变的是引用的句式和位置，不是要不要引用**。至少在下面几种切入方式之间轮换，相邻两张图不要用同一种：

    - 句首带出：「图 3 所示流程中，第三阶段的双阈值门控……」

    - 句中括注：「……该前提基本成立（见图 2）：传播度与文本强度……」

    - 动词引导：「观察图 4 中的三条收敛曲线，其差异集中体现于……」

    - 图作主语：「图 5 对比了本文方法与基线在四项指标上的表现……」（**限量：整节最多一次，绝不能当默认开头；相邻两张图都以「图 N…」起句直接判违规**）

    - 后置印证：「……这一结论在图 6 中得到印证。」

    要点：图号一定要出现，但别让每张图都用「图 N + 动词 + 一句结论」这一种开头。

  - **⛔ 严禁套话占位**：像"如图 X 所示"、"下图展示了实验结果"、"图 X 是本文的流程图"这种不含任何实质信息、换成任何一张图都成立的句子，等于没写。说不出这张图独有的内容和作用，就说明这张图对论证没用，那就不该放（"放进去要有用，不然不如不放"）。

  - **⛔ 术语与代号必须通俗化**：正文首次出现的专业术语、内部代号、变量简写（如 C4、C14、blend、脊线分布、弱监督自洽上界、C~密度），必须先用一句大白话说清"它是什么/衡量什么"再用；严禁把建模流水线里的内部代号、临时命名不加解释直接搬进正文——论文是给评委看的，不是给流水线看的。

  - **⛔ 图注（caption）只写简短标签（中文主体 ≤20 字，不含"图 N"编号）**：`\caption{}` 只写这张图是什么的名词短语；判据、参数、坐标含义、结论移到正文那段图解读里，别塞进题注（否则图下方折成多行很难看）。反例 `\caption{覆盖半径几何示意：站点为圆心、R=3km 覆盖圆、区域出车距离与响应时间判据}` → 正例 `\caption{站点覆盖半径几何示意}`。详见 `skills/_utils/writing_rules.md` 的图注长度总则；编译阶段会扫 caption 长度，超限判违规。

  - **⛔ 严禁两个 `\begin{figure}...\end{figure}` 环境直接相邻**（`\end{figure}` 后紧跟 `\begin{figure}`、中间没有正文段落）。若确需连续展示两图，必须在它们之间写一段过渡正文，说清楚两图之间的逻辑关系（为什么先看这张再看那张）。

**⛔⛔⛔ DrawIO 图嵌入规则（最容易被遗漏，必须逐条检查）：**

DrawIO 图（技术路线图、求解流程图、Pipeline 图等）的 `\begin{figure}...\end{figure}` 代码块在 `latex_includes.tex` 的**末尾部分**（由 paper-figure-drawio 步骤追加）。你必须把它们嵌入到正确的章节：

| DrawIO 图类型 | 嵌入位置 | 章节文件 |

|--------------|---------|---------|

| 技术路线图 (fig_roadmap) | 问题重述章节末尾 | `1_restatement.tex` 或 `1_introduction.tex` |

| 子问题求解流程图 (fig_flow_q1/q2/q3) | 对应子问题的"模型建立"小节开头，先写 2-3 句引导文字（概述本问题的求解思路和主要步骤），再放流程图 | `5_problem1.tex`、`6_problem2.tex` 等 |

| 数据处理 Pipeline (fig_pipeline) | 数据预处理章节 | 数据处理相关章节 |

| TikZ 几何/算法图 (tikz_diagrams.pdf) | 几何示意图→对应子问题章节开头；算法流程图→模型建立小节 | 对应子问题/模型章节 |

**⛔⛔ 铁律：子问题流程图必须分散到各自的问题章节，严禁全部堆在"问题分析"(2_analysis) 一章。**

把 fig_flow_q1~q5 五张图全塞进问题分析章节，是最常见也最难看的错误：一个章节连插 5 张大图，LaTeX 浮动机制会把它们全推到章节开头层层堆叠，正文被挤到后面，排版严重失衡。正确做法：`fig_flow_q1` → `5_problem1.tex`、`fig_flow_q2` → `6_problem2.tex`、…、`fig_flow_q5` → `9_problem5.tex`，每章一张、紧跟该问题的引导文字之后。问题分析章节(2_analysis)**最多只放整体技术路线图 fig_roadmap 一张**，其余流程图一律不许出现在该章节。

**写完所有章节后（以及每写完一章），运行布局检查：**

```bash

python skills/_utils/figure_layout_check.py paper/ 2>/dev/null || python academic-toolkit/skills/_utils/figure_layout_check.py paper/ 2>/dev/null || python ../../skills/_utils/figure_layout_check.py paper/

```

覆盖三件引擎不查的事：① `figures/*.pdf` 全部被正文引用（`figure_narrative` 引擎闸只查"已嵌入正文"的图——零引用孤儿与零叙述都拦，查不到从未嵌入的文件）；② FIGURE_MANIFEST 对账——规划了几张就必须产出几张并嵌入几张，一张不漏；③ 流程图堆叠——问题分析章节里 `fig_flow_qN` ≥2 张即违约（见上方铁律）。任何 ❌ 立即修复后再继续写下一章，不要等到最后。

TikZ 图通过 `latex_includes.tex` 里的 `\includegraphics{tikz_diagrams.pdf}` 图块嵌入（不要用 `\input`），位置同上表。

> 图连排（两个 figure/table 环境相邻、中间无正文）若还零 `\ref` 引用，由 `figure_narrative` 引擎闸在 finish 全量重扫直接拒绝完成；被引用的连排引擎不拦——写的时候就守上方连排禁令，别等闸拦。
