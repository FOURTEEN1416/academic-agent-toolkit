# 科研图表风格指南

Claude 画图时参考此文件，提升图表的学术美观度。所有图表必须达到 SCI/Nature 发表水准。

## 配色范围与验收

数据图与流程/架构图是两个独立的样式空间，互不覆盖：数据图按工作区种子随机去指纹（见下方配色契约），流程图走 TikZ/DrawIO 语义令牌。
默认数据图调用 `setup_style()`，Nature 数据图调用 `setup_style('nature')`；图中比较对象采用当前 `PALETTE` / `COLORS`，连续量选择语义合适的渐变。用户明确选灰阶时保持灰阶；未选时不从黑白流程图、论文模板 bwprint 或“灰度打印可辨认”推导全图转灰。检查器不得自行加入全灰阶断言，也不得因单张中性几何图没有彩色而判失败。数据、坐标、误差范围与验证标准不随配色改变。

## 论文落地版面五条基线

- 共用系列的多面板图：`consolidate_shared_legends(fig, axes, where='top'|'right')`，让图例与数据区分离。
- 重复随机实验：中心线 + `uncertainty_band`；每个点的数值转入表格，图中只留关键阈值/拐点。
- 字号按最终插入尺寸反算：`set_paper_placement`；数据密时加高、缩短或拆图，不放大源画布后整体缩小。
- 带字热力图：`draw_vector_heatmap(..., annot='auto')`，矢量单元格 + 真实背景对比检测。
- 坐标轴：`dynamic_limits` 设置数据驱动范围，`declutter_axes` 精简上/右边框和网格。柱图通常包含零点，折线/散点不强制从零开始。

这些接口只统一出版质量，不覆盖调用方显式传入的色系（`palette` 参数或颜色列表）。

### 共同质量契约与依据

- 默认随机和 Nature 共用相同的印刷字号、对比度、遮挡与快照检查。风格改变不降低质量门，也不增加无上限的模型返修。
- 常规文字最终印刷 ≥8pt，运行时目标 8.25pt；这是本项目中文论文的可读性选择，并非 Nature 的统一字号规定。多面板需要给图例、色条独立空间；信息密集可加高或分组，不靠巨大源画布缩小或减少真实数据过关。
- 标注只保留必要名称、单位、阈值或数值。结论、统计解释、重复实验次数和区间定义放图注；不能编造误差带。
- 算法自动修复只调整文字位置、可读墨色和版面。数据、误差范围、模型结论与用户配色语义保持不变；无安全位置则给出明确失败，不输出假合格。
- PDF 检查以最终合成背景为准，处理透明度、图片和图形绘制顺序。复杂背景或无法判断的情况给出复核提醒，不制造确定的失败或成功。

参考：[Nature formatting guide](https://www.nature.com/nature/for-authors/formatting-guide) 的最终尺寸可读性与面板关联原则；[Ten Simple Rules for Better Figures](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1003833) 的目的、媒介和简洁表达原则。借鉴原则，不照搬固定配色或论文页数限制。

## 按图表类型的配色策略（⛔ 必须遵循）

<figure_selection_guide>
## Data → Figure Type Decision Table

Before choosing a figure type, analyze the data characteristics, then match using this table. Read the full code from the corresponding recipes file.

<selection_priority>
### Selection priority: match data shape, not visual novelty

Choose the figure type that best communicates your data, not the fanciest one available. The decision order is:

1. **First check the "By data shape" table below** — match your data characteristics to the recommended figure type
2. **If multiple options fit**, prefer the one your target audience (competition judges, reviewers) will instantly understand
3. **Use advanced recipes** (Lollipop, Dumbbell, Waterfall, SHAP, etc.) when they genuinely add information that basic charts cannot show — e.g., Waterfall shows incremental contribution, SHAP shows feature direction
4. **Use basic recipes** (grouped bar, line, scatter) when they are the clearest way to present the data — a well-made grouped bar chart is better than a confusing Bump chart

A paper needs visual variety — mix basic and advanced charts. A paper with ALL advanced charts looks like it's trying too hard. A paper with ALL bar charts looks monotonous. Balance is key.

Repeated comparable experiments may reuse the same chart type and encoding. Do not force a new chart type merely to satisfy a quota; vary layout only when the scientific relationship warrants it.
</selection_priority>

### By data shape

| Data characteristic | Best figure type | Recipes file | Avoid |
|---|---|---|---|
| ≤3 methods × 1-2 metrics | Three-line table | — | Any chart — too few data points for a meaningful figure |
| 4+ methods × 1 metric | Lollipop Chart or Grouped Bar | advanced #1, basic #1 | — |
| A vs B (2 methods, multiple metrics) | Dumbbell Chart | advanced #2 | heatmap — 2 rows looks like a traffic light |
| A vs B vs C (3-5 methods, multiple metrics) | Grouped Bar Chart or Radar chart | basic #1, competition #5 | — |
| Methods × Metrics matrix (≤5×5) | Method Comparison Heatmap or Grouped Bar | advanced #16, basic #1 | — |
| Methods × Metrics (show trends across metrics) | Parallel Coordinates | advanced #17 | multiple separate charts |
| Methods × Metrics matrix (>5×5) | Heatmap with values | basic #5 | — |
| Methods × Datasets ranking | Bump Chart or Grouped Bar | advanced #4, basic #1 | — |
| Before/after comparison | Dumbbell Chart or Grouped Bar | advanced #2, basic #1 | — |
| Before/after (paired samples) | Paired Dot Plot | advanced #22 | grouped bar (hides individual variation) |
| Relative to baseline (±%) | Diverging Bar Chart | advanced #20 | grouped bar (doesn't show direction clearly) |
| Two-group mirror comparison | Back-to-Back Bar Chart | advanced #21 | — |
| Multi-model statistical comparison | Taylor Diagram | advanced #19 | separate RMSE/R²/StdDev bar charts |
| Distribution comparison (5-15 groups) | Ridgeline Plot | advanced #23 | multiple histograms (wastes space) |
| Distribution comparison (2-4 groups × categories) | Grouped Violin Plot | advanced #24 | box plot (hides distribution shape) |
| Module contribution (ablation) | Waterfall Chart | advanced #6 | bar chart |
| Time series (1-3 lines) | Line plot with CI band | basic #3 | — |
| Time series (4+ lines) | Small multiples (subplot grid) | basic #12 | spaghetti plot |
| Distribution (1 group) | Violin + strip | basic #11 | histogram |
| Distribution (2-5 groups) | Rain Cloud Plot | academic #4 | box plot |
| Proportion/composition | Donut Chart or Stacked Area | basic #6, #8 | pie chart |
| Correlation matrix | Heatmap + dendrogram | advanced #14 | plain heatmap |
| 2D scatter + relationship | Scatter + regression + R² | basic #4 | — |
| 2D joint distribution (large N) | Hexbin + marginal histograms | competition #24 | plain scatter (overplotting) |
| 2D joint distribution (small N, clusters) | KDE contour + marginal density | competition #25 | plain scatter |
| 2D relationship + distribution | Scatter + regression + marginal density | competition #26 | scatter without marginals |
| High-dim features | t-SNE/UMAP scatter | academic #2 | — |
| 3D clustering results (3 features) | 3D scatter + centroids | competition #27 | 2D scatter (loses dimension) |
| Multi-criteria evaluation | Radar chart | competition #5 | — |
| Feature importance | SHAP Summary Plot | advanced #7 | horizontal bar |
| Classification result | Confusion matrix | competition #10 | — |
| Binary classifier comparison | ROC + AUC | competition #11 | — |
| Probability reliability | Calibration Plot | advanced #11 | — |
| Sensitivity (single-param sweep, rank drivers) | Tornado Chart (barh sorted by range) | competition #2 | grouped bar (loses ranking) |
| Throughput/flow loss per stage | Sankey Diagram | advanced #5 | stacked bar (hides chain) |
| Two-factor response / error propagation | 3D Surface + projected contour | competition #6 | heatmap (loses magnitude) |

### By problem domain (competition)

| Problem type | Recommended figures | Recipes |
|---|---|---|
| Optimization (GA/PSO/SA) | Convergence curve + 3D surface + Pareto front | comp #1, #6, #3 |
| Scheduling/routing | Gantt chart + Network path | comp #15, #16 |
| Classification/clustering | Confusion matrix + ROC + 3D cluster scatter | comp #10, #11, #13 |
| Regression/prediction | Prediction vs Actual with CI band + Error Rain Cloud + Multi-step decay + Model accuracy heatmap | empirical #12, #14, #16, #13 |
| Sensitivity analysis | Tornado chart + Contour + 3D surface | comp #2, #14, #6 |
| Spatial data | China province choropleth + Spatiotemporal matrix | comp #7, #18 |
| Multi-objective | 2D Pareto + 3D Pareto surface | comp #3, #19 |
| Factor decomposition | Waterfall chart | comp #20, advanced #6 |

### By problem domain (academic/empirical)

| Paper type | Recommended figures | Recipes |
|---|---|---|
| DID/causal inference | Parallel trends + Event study + Placebo | empirical #2, #3, #4 |
| Regression analysis | Forest plot + Heterogeneity forest + Marginal effects | empirical #1, #10, #15 |
| Prediction/forecasting | Prediction with CI band + Error Rain Cloud + Multi-step decay + Model heatmap | empirical #12, #14, #16, #13 |
| Deep learning | Training curves + Attention map + t-SNE | academic #3, #6, #2 |
| Model comparison | Grouped Bar + Method Comparison Heatmap + Radar | basic #1, advanced #16, comp #5 |
| Hyperparameter tuning | Sensitivity grid + 3D loss landscape | academic #7, #8 |
| Meta-analysis | Forest plot + Funnel plot | empirical #1, advanced #12 |
| Survival analysis | Kaplan-Meier curve | advanced #9 |
| Genomics/omics | Volcano plot + Cluster heatmap | advanced #10, #14 |
| Method agreement | Bland-Altman plot | advanced #8 |

### Anti-patterns (check before generating — but use judgment)

Not every "upgrade" is appropriate. Check this table, but choose based on clarity for your audience.

| ❌ If you were going to use... | ✅ Consider this instead | Why | When to upgrade |
|---|---|---|---|
| Single-metric bar chart for ranking | Lollipop Chart | Less visual noise for pure ranking | When showing 5+ items ranked by one metric |
| Horizontal bar for feature importance | SHAP Summary Plot | Shows direction + magnitude | When you have SHAP values available |
| Bar chart for ablation | Waterfall Chart | Shows incremental contribution | Always — waterfall is strictly better for ablation |
| Bar chart for before/after (2 groups) | Dumbbell Chart | Shows direction and magnitude of change | When comparing exactly 2 conditions |
| Plain box plot | Rain Cloud Plot | Distribution shape + box stats + raw data | When sample size > 20 and distribution shape matters |
| Pie chart | Donut Chart | More modern, less visual distortion | Always |
| Plain heatmap | Heatmap + dendrogram | Adds clustering structure | When row/column ordering matters |
| Stacked bar (non-temporal) | Sankey Diagram | Shows flow direction | When data represents flow/routing |
| RdYlGn colormap | coolwarm or YlOrRd | Red-yellow-green = traffic light | Always |

**Keep using grouped bar chart when:**
- Comparing 3-5 methods across 2-5 metrics (this is what grouped bar charts are designed for)
- Your audience is competition judges or non-specialist reviewers who expect familiar chart types
- The data has clear, discrete categories on the x-axis
- You already have too many advanced charts in the paper and need visual variety

**Keep using line chart when:**
- Showing trends over time or continuous x-axis
- Comparing convergence curves or training progress
</figure_selection_guide>

<bar_chart_alternatives>
### 柱状图使用指南

柱状图是最通用、最易读的图表类型之一。不要回避使用它。

**适合用柱状图的场景（直接用，不需要替代）：**
- 3-5 个方法在 2-5 个指标上的对比 → 分组柱状图
- 类别数据的频次/计数对比 → 普通柱状图
- 需要评委/读者一眼看懂的核心结果 → 分组柱状图
- 论文中已经有多个高级图表，需要平衡 → 柱状图

**适合用替代方案的场景：**

| 场景 | 替代方案 | 原因 |
|------|---------|------|
| 单指标排名（5+项） | Lollipop Chart | 纯排名场景，棒棒糖更简洁 |
| 消融实验 | Waterfall Chart | 展示增量贡献，柱状图做不到 |
| 前后两组对比 | Dumbbell Chart | 展示变化方向和幅度 |
| 特征重要性（有SHAP值） | SHAP Summary Plot | 同时展示重要性和方向 |
| 多数据集排名变化 | Bump Chart | 展示排名交叉 |

**全篇图表多样性规则：** 先按数据关系选图，不为“看起来不一样”强换图型。若同一图型连续重复，应检查是否能用共享尺度的多 panel、表格或更贴合数据关系的图型减少重复；只有替代图同样准确时才更换。
</bar_chart_alternatives>

不同图表类型有不同的最佳配色策略，不能一刀切：

### ⛔ 颜色使用通用规则

**数据颜色**（柱子、线条、散点等）：必须用 `PALETTE[i]` 或 `PALETTE_LIGHT[i]`，不要硬编码 hex 颜色。
**语义颜色**（上升/下降/中性等）：用 `COLORS['up']`、`COLORS['down']`、`COLORS['neutral']`，不要硬编码 `#27ae60` 或 `#e74c3c`。
**辅助颜色**（必要网格线/文字/语义标注框）：用 `COLORS['grid']`、`COLORS['text']`、`COLORS['bg_box']`；无信息作用的装饰不添加。
**渐变起点**：用 `_lighten(PALETTE[0], 0.6)` 而不是硬编码 `#b0c4de`。

这样切换配色方案（journal/soft/npg/colorblind）时，所有颜色自动跟随。

配方代码中的硬编码颜色是历史遗留，写新代码时用上述变量替代。

### ★★ 图表质量跃升清单（想让图"专业耐看"，先过这 6 条——建议而非强制）

同一套 `setup_style()` 下，图的档次差别几乎全来自下面 6 条，而**不是**图内文字多少。经对 94 张真实竞赛图的逐图核对，高分图与平庸图的差距集中在这里。**按题目实际需要挑用，不要为凑指标硬加**：

1. **只合并需要同步比较的 panel**：共享样本、尺度或论证链的 2–4 个 panel 可以并陈（如“主结果 + 残差诊断”）；没有直接比较关系的内容应拆图。按论文最终宽度检查，任一 panel 需要缩字、堆图例或塞解释句才能放下时就拆开。单 panel 并不低级，信息边界清楚比数量多更重要。
2. **判据可视化——把"该不该越界"画出来**：有阈值/上限/约束/合格线时，画一条 `axhline`/`axvline`（虚线 + 线旁短标签），让读者直接看到"实测离限还有多远"。这是"有判据"和"只有一堆曲线"的分水岭。
3. **表达不确定性**：有多次重复/置信区间/误差范围时，用 `fill_between` 画置信带或 `errorbar` 画误差棒，不要只画一条均值线。一条光溜的线读者无法判断可信度。
4. **图型跟着数据形态走，别一律折线柱状**：三维响应面用 `plot_surface`、分布形态用小提琴/Rain Cloud、密集散点用 `hexbin`、流向用桑基、排序驱动因子用 Tornado（见上方决策表）。**只会 plot/bar/scatter 是平庸图最明显的信号。**
5. **色彩层次用派生色**：同族深浅用 `_lighten(PALETTE[i], 0.5)` 做填充/次要元素，主色留给主体。比"每条线换一个色相"更高级、更像期刊图。
6. **图层次序 `zorder`**：网格/参考带在底（`zorder=0-1`）、数据在中（`2-3`）、标注在顶（`4+`）。不设 zorder 时数据可能被网格线或填充压住。

**配套的两条工程习惯**（能明显减少返工）：
- **共用引导模块**：图多于 5 张时，建一个 `figures/_figbase.py` 放公共内容——JSON 载入、指标口径函数（如 `rel_err`/`acc90`，**与建模阶段口径一致**避免各图各算导致论文数字打架）、`log_floor(vals)` 函数（对数轴零值地板：真值为 0 时用它占位并单独标注，**禁止静默丢点**；⛔ 地板要**按各图真实数据下界现算**、贴着最小值下方半个数量级，**别写死 `1e-18` 这类极小常量**——会把对数轴撑到 6+ 个数量级、图边一大片空白，详见技法 11）、中文缺字替换（雅黑缺 `⛔✔⚠ν̈` 等字符，PDF 里会渲染成空白方框，统一过一个 `cn()` 函数替换）。各 `gen_fig_*.py` 统一 `from _figbase import ...`，避免几十份脚本重复样板。
- **每个脚本写文件级 docstring**：开头用三引号写明「本图讲什么 + 每个 panel 是什么 + 数据来源哪个 JSON + 关键数值」。这不是形式主义——写的过程会迫使你先想清楚"这张图要让读者看到什么"，是"先想再画"和"边画边凑"的分界。有余力时连版式一起写（如"原生宽 8.2in，正文按 0.98\textwidth 引用 → 缩放约 0.75，最小字号上页 ≥6pt"），能提前避免"缩到页面上字看不清"。

⛔⛔ **和下面「图内文字最小化」的关系（别搞反）**：减的是解释性文字，不是数据证据。信息由适合本题的 panel、判据线、置信带，以及图前后的正文解读承载；简短 caption 只负责说明图是什么。不要为了少字删掉论证所需的数据层，也不要把无关层包装成“信息密度”。

### ⛔ 工程卫生（保证"图是可信的工程产物"）
- **数值/常数从真实来源读**：坐标、阈值、统计量、每个 bar 的高度应来自计算结果或数据文件（如 `results.json`、`df`），不要在绘图脚本里凭空写死来路不明的数字。图里的每个数字都要对得上正文。
- **连续 colormap 优先走 PALETTE 派生**：需要连续色阶时（热力图、3D surface、密度图），优先 `LinearSegmentedColormap.from_list(..., [_lighten(PALETTE[0],0.7), PALETTE[0]])`；少用硬编码 `cmap='viridis'/'YlOrRd'`（与随机配色不同步），`jet` 有感知误导不要用。
- **异量纲隔离，别强行同轴**：单位/量级差异大的量（如"时间 s"和"百分比 %"）不要塞进同一个 Y 轴。用双轴 `ax.twinx()`（各自标注单位）或拆成上下 panel。同轴混画不同量纲会让读者误判相对大小。
- **图能独立复现**：脚本从数据到 `save_fig` 一条龙跑通，不依赖手动改数或某次交互状态；交付前顺手清掉调试残留（`plt.show()`、被注释掉的整段旧画法）。

### 柱状图（Bar Chart）
- **2 组对比**：用同色系深浅（如 `PALETTE[0]` + `PALETTE_LIGHT[0]`），不要用两种完全不同的颜色
- **3-5 组对比**：用 PALETTE 前 3-5 色，饱和度统一
- **单组多类别**：用同一色系的渐变（如从 `PALETTE[0]` 到 `PALETTE_LIGHT[0]` 的 n 个梯度），不要每根柱子一个颜色
- **⛔ 禁止**：plt.cm 渐变色、matplotlib 默认蓝色、超过 6 种不同颜色

### 折线图（Line Chart）
- **2-3 条线**：用高对比色（如 PALETTE[0] 实线 + PALETTE[1] 虚线），线宽 2pt，加标记点
- **4+ 条线**：用 PALETTE 前 n 色和不同线型区分；标记点只在稀疏采样处出现，避免每点都画造成糊线
- **带 CI 带**：主线用 PALETTE[0]，CI 带用同色 alpha=0.15
- **⛔ 禁止**：所有线同色、线宽 <1.5pt、无标记点

### 饼图（Pie Chart）
- 用 PALETTE 前 n 色 + `wedgeprops={'edgecolor':'white', 'linewidth':2}`
- 最大扇区用 PALETTE[0]，其余按大小排序用后续色
- 小于 5% 的扇区合并为"其他"
- **⛔ 禁止**：超过 7 个扇区、无白色分隔线、3D 效果

### 热力图（Heatmap）
- 相关性矩阵（正负对比）：`cmap='coolwarm'`，`center=0`，下三角 mask。**⛔ 不要用 `RdBu_r`**——深红深蓝太沉重，`coolwarm` 更柔和
- 方法对比热力图（归一化性能）：`cmap='YlGnBu'` 或 `cmap='coolwarm'`，浅色背景+深色高亮；矩阵较小且精确数值是论证所需时才逐格标数，否则保留 colorbar 并仅标关键单元
- 频率/计数：`cmap='YlOrRd'` 或 `cmap='Blues'`
- **⛔ 禁止**：`jet` colormap、`RdBu_r`（太深沉）、密集矩阵逐格堆字、相关矩阵上下三角重复展示
- **⛔ 反模式**：≤5 行的方法对比不要用深色热力图，改用 Radar chart 或 Dumbbell chart

### 散点图（Scatter）
- 单组：PALETTE[0]，`alpha=0.6`，`s=20-40`
- 多组：PALETTE 前 n 色，不同标记形状（o/s/^/D）
- 加回归线：`color=PALETTE[1]`，虚线

### 箱线图/小提琴图
- 用 PALETTE_LIGHT 填充 + PALETTE 边框
- 中位线用深色加粗

## 配色方案

### ★ 默认：裸调 `setup_style()`，不要传 palette 参数

```python
setup_style()   # ← 就这样，不带参数
```

**为什么不传参数：** `setup_style()` 不带参数时进入「自动去指纹随机模式」——它按**当前工作区**的确定性种子，从内置的 29 套精选配色库里自动挑一套，并同步随机版式风格（边框/刻度/网格/线宽）和中文字体。效果是：

- **同一篇论文内所有图表配色/风格统一**（同种子）；
- **不同论文各不相同**（种子按工作区变）；
- **重跑结果不变**（确定性，可复现，绝不用时间戳）。

这正是防「不同队伍/不同论文图表撞脸」的核心机制。**⛔ 除非下面列出的特殊情况，否则一律裸调 `setup_style()`，不要自己指定 `palette='soft'`/`'npg'` 之类——那样会关掉自动随机，让所有论文退回同一套固定配色（同质化）。**

### 什么时候才显式传 palette（例外）

只有这几种情况才传具体配色名：

1. **用户明确点名了配色**：工具箱构建不读取任何宿主前端标记，直接把配色名或十六进制列表显式传给 `setup_style(palette=...)`。
2. **用户要求色盲无障碍**：`setup_style(palette='colorblind')`。
3. **调试/复现某套特定配色**：临时传名字，正式出图前改回裸调。

可用的配色名（供例外情况参考，正常出图无需关心）：`soft`（柔蓝珊瑚薄荷）、`journal`（低饱和莫兰迪，SCI 顶刊感）、`tableau`（10 色高区分度）、`npg`（自然科学鲜明对比）、`nejm`（统计/医学柔和）、`science`（IEEE/工程经典）、`colorblind`（无障碍）。传列表也行：`setup_style(palette=['#5B9BD5','#ED7D7D',...])`。

### 用色规范（不管哪套配色都适用）

- 代码里用色一律引用 `PALETTE[0]`、`PALETTE[1]`… 和 `COLORS['primary']` 等**语义变量**，它们会随 `setup_style()` 选中的配色自动变化。**⛔ 绝不硬编码十六进制色值**（如 `color='#5B9BD5'`），硬编码会绕过随机、造成跨论文撞色。
- **⛔ 绝不用 matplotlib 默认色** `#1f77b4`（那种"默认蓝"是最明显的"没调过样式"信号）。
- **渐变色（热力图/填充）**：用 `cmap='coolwarm'`（红蓝对比柔和版）或 `cmap='YlOrRd'`（暖色渐变），不要用 `jet` 或 `RdBu_r`（太深沉）。

## 字体与排版

```python
plt.rcParams.update({
    'font.size': 11,                    # 正文字号
    'axes.labelsize': 12,               # 坐标轴标签稍大
    'axes.titlesize': 13,               # 标题再大一号
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'legend.fontsize': 10,
    'font.family': 'sans-serif',
    'mathtext.fontset': 'stix',         # 数学字体用 STIX（接近 Times）
})
```

## 让图表更高级的技巧

### 1. 去掉顶部和右侧边框（已在 plot_utils 中默认）
```python
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
```

### 2. 柱状图加数值标注
```python
for bar in bars:
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
            f'{bar.get_height():.1f}', ha='center', va='bottom', fontsize=9)
```

### 3. 折线图加标记点 + 置信带
```python
ax.plot(x, y, 'o-', markersize=5, linewidth=1.5, color=NATURE[0])
ax.fill_between(x, y_low, y_high, alpha=0.15, color=NATURE[0])
```

### 4. 热力图用 mask 只显示下三角
```python
mask = np.triu(np.ones_like(corr, dtype=bool), k=1)
sns.heatmap(corr, mask=mask, annot=True, fmt='.2f', cmap='coolwarm', center=0)
```

### 5. 回归系数森林图（实证论文核心图）
```python
ax.errorbar(coefs, y_pos, xerr=[coefs-ci_low, ci_high-coefs],
            fmt='o', color=NATURE[3], ecolor='#95A5A6', capsize=4, markersize=6)
ax.axvline(x=0, color=NATURE[0], linestyle='--', linewidth=0.8, alpha=0.7)
```

### 6. 分组柱状图加误差棒
```python
bars = ax.bar(x + offset, vals, width, yerr=errs, capsize=3,
              color=NATURE[i], edgecolor='white', linewidth=0.5)
```

### 7. 多面板子图对齐
```python
fig, axes = plt.subplots(2, 2, figsize=(5.7, 5.6), layout='constrained')
set_paper_placement(fig)  # 示例尺寸；按实际 PDF/Word 插入尺寸复核
for i, ax in enumerate(axes.flat):
    ax.set_title(f'({chr(97+i)})', loc='left', pad=3)
```

使用一个布局系统：constrained/compressed layout 不再叠加 `tight_layout` 或 `subplots_adjust`。
专用图例和色条区由 GridSpec 分配。手工版式显式设置 `fig._mh_manual_layout=True`，
一次性安排位置，再检查最终输出；没有适用于所有图的 pad 上限或固定面板尺寸。

> **⛔ 子图标注必须用 `ax.set_title()` 而不是 `ax.text(transAxes)`。**
> 原因：`ax.text(-0.08, 1.05, ..., transform=ax.transAxes)` 的坐标是相对于 axes 逻辑区域的，
> 但 `set_aspect('equal')` 或 `constrained_layout` 会让实际绘图区域在分配空间内缩小，
> 导致 `y=1.05` 看起来离图很远。`set_title(loc='left', pad=3)` 会自动贴着实际渲染出的
> axes 边框上方，不受 aspect ratio 影响。

### 8. 保存时确保高质量
```python
save_fig(fig, 'figures/fig_xxx.pdf')
```

### 9. 分布图用 `stairs` 阶梯轮廓，别用 `bar` 堆砖块（最省力的"高级感"）
画分布/直方图时，`ax.bar` 画出来是一排砖块、边框粗重；`ax.stairs` 是连续阶梯轮廓 + 填充，
期刊感强得多，而且相邻 bin 之间没有多余竖线干扰。**同样的数据，观感差一档**：

```python
counts, edges = np.histogram(vals, bins=np.arange(3.5, 22.5, 1.0))
ax.stairs(counts, edges, fill=True,
          color=_lighten(PALETTE[0], 0.50),   # 浅色填充
          edgecolor=PALETTE[0], lw=1.5, zorder=4)
```
需要上下对镜像对照（如"真实分布 vs 预测分布"）时，把一侧取负即可，比并排双色柱更直观：
```python
ax.stairs(share_true * 100, edges, fill=True, color=_lighten(PALETTE[2], 0.48), edgecolor=PALETTE[2])
ax.stairs(-share_pred * 100, edges, fill=True, color=_lighten(PALETTE[0], 0.48), edgecolor=PALETTE[0])
ax.axhline(0, lw=1.2, color=COLORS['text'])          # 镜像轴
# 负半轴标成正数（读者看的是"占比"不是负值）；⛔ 必须先 set_yticks 再 set_yticklabels，
# 否则 matplotlib 会报 FixedFormatter 警告、且换版本后标签可能对不上刻度
_yt = ax.get_yticks()
ax.set_yticks(_yt)
ax.set_yticklabels([f'{abs(t):.0f}' for t in _yt])
```

### 10. 量化两个值的差距：用双向箭头，不要写文字框
要说明"A 比 B 高多少"时，**别写一句话塞进图内**——在两点之间画双向箭头 + 一个短标签，
读者一眼看到"差在哪、差多少"，且几乎不占地方（这也是「图内文字最小化」的正解）：

```python
ax.annotate('', xy=(q_high, y), xytext=(q_low, y),
            arrowprops=dict(arrowstyle='<->', color=PALETTE[4], lw=1.5))
ax.text((q_low + q_high) / 2, y - 0.05, f'差 {(q_high - q_low) * 100:.1f} pp',
        ha='center', va='top', fontsize=8.5, fontweight='bold', color=PALETTE[4])
```
适用：两条 ECDF 在某分位处的差距、改进前后的提升量、上限与实测的余量、两方案的间隔。

### 11. 对数轴的零值地板：`0` 会被静默丢掉，必须显式处理 —— 但**地板要贴近数据，不能"远低于"**
`set_yscale('log')` / `set_xscale('log')` 时，值为 `0` 的点会被 matplotlib **无声丢弃**——
图上少了点却没有任何提示，这是很隐蔽的数据不诚实。所以要用地板值占位 + 单独标注。

⛔⛔ **但地板值必须【贴近真实数据下界】，绝不能设成"远低于数据量级"的极小值。**
（实测翻车：某 ECDF 图真实数据主体在 $10^1\sim10^2$ nm、1% 分位才 3.7nm，地板却设 `1e-3` →
对数轴被撑到 **6.1 个数量级**，左边约 **40% 的图宽是纯空白**，曲线在那段只是一条平线，
图看着"左边空一大片"。地板改到 0.5nm 后轴跨降到 3.5 个数量级，空白基本消失。）

**定地板的方法（三步）**：
```python
nz = vals[vals > 0]
# ⛔ 相交/重合等情形会产出 1e-15 量级的浮点残差，那不是真实数据，要和 0 一起归为"零"
EPS = 1e-6
real = nz[nz > EPS]
LOG_FLOOR = 10 ** (np.floor(np.log10(real.min())) - 0.5)   # ① 贴着真实最小值下方半个数量级
plot_v = np.where(vals > EPS, vals, LOG_FLOOR)
ax.set_yscale('log')
ax.set_ylim(LOG_FLOOR * 0.7, real.max() * 1.3)             # ② 轴界贴着地板给，别再往下留空
ax.scatter(x, plot_v, color=PALETTE[0])
n_zero = int((vals <= EPS).sum())
if n_zero:                                                 # ③ 地板并了多少点，必须写出来
    ax.scatter(x[vals <= EPS], np.full(n_zero, LOG_FLOOR),
               marker='v', color=COLORS['down'], zorder=6)
    ax.text(LOG_FLOOR * 0.8, ax.get_ylim()[1], f'← {n_zero} 个 = 0 并入左端',
            fontsize=7.2, ha='left', va='top')
```
**自检**：算一下 `log10(轴上界/轴下界)`。**超过 4 个数量级就要警觉**——除非数据真的横跨那么多量级，
否则就是地板设太低。真实数据只跨 2 个量级时，别让轴跨 6 个。

#### ⛔⛔ 更上位的原则：**轴只覆盖「有数据的区间」，别为极少数极端点留一大段空轴**

上面的地板技巧治的是"地板设太低"，但**真正的病根常常是"为了把某个东西画进轴内，让轴覆盖了没有数据的一大段"**。
调地板治不了这种（实测踩过完整一轮，三版数据在此）：

| 做法 | 轴跨 | 曲线真正在变化的横向占比 |
|---|---|---|
| 地板 `1e-3`、左界 8e-4 | 6.10 | 11% / 21% / 20% |
| 地板抬到 `0.5`、左界 0.35（"贴近数据下界"） | 3.46 | 12% / 31% / 29% |
| **左界直接设 10（砍掉无数据段）** | **2.00** | **12% / 44% / 36%** |

那张 ECDF 图：判据线 δ=1.8nm 想画进轴内，但 90.8% 的点在 100nm 以上、0.5–13nm 只有 **1.24%** 的点，
δ 处的纵截距几乎全由 d=0 的相交对贡献 —— **δ 附近本来就没数据**。于是：
- 左界拉到 0.35 → 左边 64% 图宽是平线；抬到 10nm 仍有 43%
- 连**断轴双 panel 也没用**：左 panel 曲线只上升 0.016–0.038、有变化占比仅 1–19%，还是平线

**⛔⛔ 第 0 步（比下面所有事都靠前）：定轴范围前，先打印数据真实 min/max。**
不是"心里大概有数"，是**真的打印出来看一眼**。实测踩过的坑：主胞边长常量 `L = 10000`，
而数据坐标系其实以原点为中心（`[-L/2, +L/2]`），脚本却写了 `set_xlim(0, L)` ——
负坐标那一半（实测 46%~79% 的点）被静默裁到轴外，图上只剩挤在角落的一小撮。
matplotlib 不报错、静态检查也扫不出来，就这么进了成品 PDF。

```python
A = np.vstack([P, Q])            # 或任何即将画上去的数组
for k, nm in enumerate('xyz'[:A.shape[1]]):
    print(f'{nm}: {A[:, k].min():.1f} .. {A[:, k].max():.1f}')
```

**常量名会骗人**：`L` / `SIZE` / `LENGTH` 到底是「边长」还是「坐标上界」？去常量定义处
确认，别猜——本例 `code/params.py` 里写得很清楚：`HALF = L / 2  # 半边长，坐标上下界`。
`save_fig` 里有运行时兜底闸（>20% 的点落在轴外就打警告），但那是最后一道网，别指望它。

**然后才是：先问「这段轴上有数据吗」，再谈地板怎么设。**
1. 看分位数/直方计数定出"数据真正密集的起点"，**轴界就设在那里**（如 `set_xlim(10, 1000)`）；
2. 落在轴外的极少数点、以及关键判据值，**用图例标签或一行注记承载数值**，不要为它们留一段空轴。
   这是披露显示范围的特定场景，不是要求所有图例携带结论数值。图例先用短组名识别系列，
   在图注或图前后正文交代 "`d<10nm` 的点占 1.24%（其中 187 对已相交），贡献已计入曲线左端起始高度"。
   必要样本口径、阈值和条件仍可保留为短标签，不把多条结果摘要塞进图例。
3. ⛔ 但**必须写明轴外还有多少点、去哪了**，否则是数据不诚实。

**ECDF 尤其不需要地板**：`F(x)=P(X≤x)` 已把 `d=0` 的点算进任意 `x>0` 处的高度，
用全量算 ECDF、只在显示上裁 x 范围即可，`d=0` 体现为"曲线左端的起始高度"，零信息损失。

### 12. 同一物理量两种口径并列：加第二坐标轴（`twiny`/`twinx`）做换算刻度
当一个量有两种等价表述（时长↔效率、原值↔百分比、绝对量↔归一化），不要画两张图、也不要
只标一种让读者自己换算——在**同一根轴的对面**加换算刻度，一张图读两种口径：

```python
ax.set_xlabel(r'PPDU 时长 $T$ (ms)')
axt = ax.twiny()                       # 上方第二 x 轴
axt.set_xlim(ax.get_xlim())            # ⛔ 必须同步范围，否则刻度对不上
ticks = np.array([1.0, 2.0, 3.0, 4.5])
axt.set_xticks(ticks)
axt.set_xticklabels([f'{t / (t + 0.144):.3f}' for t in ticks])   # 换算成占空效率
axt.set_xlabel(r'对应占空效率 $\varsigma = T/(T+144\,\mu s)$', labelpad=3)
axt.tick_params(axis='x', length=2.5)
```
⛔ 注意与「异量纲隔离」的区别：这里是**同一个量的两种口径**（可换算）才用；两个**不同物理量**
（时间 vs 百分比）挤一根轴是错的，那种情况要用 `twinx` 各自标单位、或干脆拆 panel。

### 13. QQ 图加 95% 逐点包络（比一根参考线专业得多）
只画一条正态参考线，读者无法判断"偏离多少才算显著"。用 Beta 序统计量算出逐点置信包络，
越出包络的才是真尾部偏离：

```python
from scipy import stats
(osm, osr), (slope, icpt, r) = stats.probplot(resid, dist='norm')
ax.scatter(osm, osr, s=10, color=PALETTE[0], alpha=0.55, rasterized=True)
ax.plot([osm.min(), osm.max()], [slope * osm.min() + icpt, slope * osm.max() + icpt],
        '--', color=PALETTE[1], lw=1.6, label=f'正态参考线（$R^2$={r**2:.4f}）')
n = resid.size; k = np.arange(1, n + 1)          # 第 k 个序统计量服从 Beta(k, n-k+1)
lo = stats.norm.ppf(stats.beta.ppf(0.025, k, n - k + 1)) * slope + icpt
hi = stats.norm.ppf(stats.beta.ppf(0.975, k, n - k + 1)) * slope + icpt
ax.fill_between(np.sort(osm), lo, hi, color=PALETTE[3], alpha=0.22, label='95% 逐点包络')
```

### 14. 大量散点加 `rasterized=True`（控制 PDF 体积，不牺牲文字清晰度）
上千个散点写进矢量 PDF 会让文件膨胀到几 MB、打开卡顿。给**数据层**开栅格化，
坐标轴/文字仍是矢量（缩放不虚）：

```python
ax.scatter(x, y, s=9, color=PALETTE[0], alpha=0.34, linewidths=0,
           rasterized=True)          # 只栅格化点，标签文字仍矢量
```
适用：散点云 > 500 点、蜂群图、密集轨迹。热力图/柱状图不需要。

### 15. ★★ 版面精调六件套（"看起来专业"的直接来源，实测差距最大的一组）

对 94 张真实竞赛图统计：高分图集和平庸图集在这六项上的差距是**压倒性**的（前者 46%-82% 都做，
后者 0%-17%）。**图型选对了但还是显得"业余"，八成是这六项没做。**
⛔ 下面给的数值是精调后的参考量级，**按你的图实际调整，不要当死数照抄**。

**① 手动指定刻度位置（差距最大：82% vs 7%）**
matplotlib 默认刻度经常给出 `0 / 2.5 / 5.0 / 7.5` 这种无意义分割，或者密到糊掉。
自己按**数据语义**挑刻度，尤其**把关键阈值/上限/范围端点塞进刻度**——读者能直接从轴上读出结论：

```python
ax.set_xticks([4, 8, 12, 16, 21])        # 21 是题给硬上限 → 进刻度，一眼看出实测顶到上限
ax.set_yticks([0, 0.2, 0.4, 0.6, 0.8, 0.9, 1.0])   # 0.9 是 Q90 判据线 → 单独加一个刻度
# 数据范围很窄时（如 0.41~0.44）别让 matplotlib 给 0/0.2/0.4，那样细节全糊：
ax.set_yticks([0.41, 0.42, 0.43, 0.44])
# 刻度本身无意义时（状态矩阵、类别条形的位置轴）主动清空，别留一排没用的数字：
ax.set_yticks([])
```

**② 字号定义成常量族，不要每处随手写（46% vs 0%）**
随手写字号会导致同一张图里标注 8pt、9pt、8.5pt 混用，看着"脏"。开头定一套层级，全图复用：

```python
FS_ANNO, FS_TICK, FS_LAB, FS_TITLE, FS_LEG = 8.4, 9.0, 10.4, 11.4, 8.6
#         标注    刻度    轴标签   面板标题  图例
ax.set_xlabel('...', fontsize=FS_LAB)
ax.tick_params(labelsize=FS_TICK)
ax.set_title('(a) ...', fontsize=FS_TITLE, fontweight='bold', loc='left', pad=5)
```
层级关系（**标注 < 刻度 < 轴标签 < 面板标题**）比具体数值更重要。

#### 最终插入尺寸决定原生画布与字号

先读取项目的真实栏宽、插图宽度和页面高度约束，再调用 `set_paper_placement`。
最终字号 = 源字号 × 实际插入宽度 / 源画布宽度；若高度先达到页面上限，实际宽度还会进一步减小。
普通文字最终 ≥8pt，默认目标 8.25pt；不能只看源文件字号，也不能靠扩大源画布解决拥挤。

下面仅是当前 `fig_include_size.py` 数据图分档的起步参考，不是固定模板或验收尺寸。
示例按正文净宽 6.5in 估算；Word 的宽度限制、实际模板和高度约束可能给出更小的插入尺寸。

| 图的长宽比 r=高/宽 | 分档给的 width | 示例上页显示宽 | 参考原生宽 |
|---|---|---|---|
| r ≤ 0.80（横图/宽图） | `0.90\textwidth` | 5.85in | 约 6.4in |
| 0.80 < r ≤ 1.20（近方图） | `0.80\textwidth` | 5.20in | 约 5.7in |
| 1.20 < r ≤ 1.60（偏竖） | `0.60\textwidth` | 3.90in | 约 4.3in |
| r > 1.60（瘦高） | `0.46\textwidth` | 2.99in | 约 3.3in |

逻辑框图按实际文字密度另选 0.80–0.98 倍正文宽，不直接套数据图分档；满宽仍不可读时回源重排。
分档系数与代码保持同步，但不能把过去某张图“放大后少遮了几个点”的结果推广为防遮挡算法。
图例所占空间还与文字长度、列数、字号、字体和布局有关；即使占比很小，也可能正好盖住关键峰值。

密集内容先分配图例/色条/数值专用区域，再调整行列、适量增高或按语义拆图。
高度增加可能跨越分档或触发高度限制，必须重新检查实际字号，不能只承诺“加高就不影响字号”。
必要数据、误差范围、刻度含义和用户色系不变；线宽也按最终尺寸检查。

#### 多 panel 共用 colorbar：明确分配空间

多个面板表示同一量、同一归一化范围时，才共用一个色条。密集多面板优先给色条独立 GridSpec 列，
不要靠反复改 `fraction` / `pad` 试运气。下面展示位置关系；`sm` 来自实际绘制的矩阵或曲面。

```python
fig = plt.figure(figsize=(5.7, 5.6), layout='constrained')
set_paper_placement(fig)
gs = fig.add_gridspec(2, 3, width_ratios=[1, 1, 0.06])
axes = np.array([[fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1])],
                 [fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[1, 1])]])
cax = fig.add_subplot(gs[:, 2])
# 在 axes 中绘制共享归一化的真实数据，取得 sm，再创建色条：
# cbar = fig.colorbar(sm, cax=cax)
# cbar.set_label('短名称（单位）')
```

`fig.colorbar(sm, ax=axes)` 在布局引擎正确管理空间时也合法，不能按 API 名字误判遮挡。
当前 `save_fig` 不会对 constrained/compressed、手工布局或 3D 图无条件调用 `tight_layout`。
布局引擎默认关闭不等于禁止显式启用；创建图时选择好一个系统，保存时保留它。

#### 多 panel 的轴标签：只合并语义相同的轴

共享坐标含义、单位与范围的面板可只在下排/左列标注；不同物理量的面板保留各自标签。
按可读间距选择主刻度，保留关键阈值和单位，不用固定刻度数删除必要信息。

**③ 图例去框 + 收紧（37% vs 0%）**
默认图例带灰边框、条目松散，占地方还显土。去框 + 收紧间距：

```python
ax.legend(frameon=False,          # ★ 去掉那个灰框
          fontsize=FS_LEG,
          handlelength=1.7,       # 默认 2.0 偏长
          labelspacing=0.28,      # 默认 0.5 偏松
          handletextpad=0.36,
          borderpad=0.2,
          loc='upper right')      # 仅为候选位置；须通过最终边界与遮挡检查
```

**④ 浅色填充 + 主色描边（`_lighten` 用了 113 次 vs 0 次）**
这是"层次感"最廉价也最有效的来源：**填充用同色浅版、边线用主色**，而不是整块实色。
比"每个系列换一个色相"高级得多，也不会让图变成调色盘：

```python
ax.stairs(counts, edges, fill=True,
          color=_lighten(PALETTE[0], 0.50),   # 填充：主色的浅版（0.4~0.6 最常用）
          edgecolor=PALETTE[0], lw=1.5)       # 描边：主色本身
ax.bar(x, y, color=_lighten(PALETTE[1], 0.44), edgecolor=PALETTE[1], linewidth=1.4)
ax.fill_between(x, lo, hi, color=_lighten(PALETTE[2], 0.60), alpha=0.42)  # 置信带更浅
```
`_lighten` 系数经验值：**主体填充 0.4~0.5**、**背景带/次要元素 0.55~0.7**、**渐变起点 0.6~0.8**。

**⑤ `zorder` 分层 + 关键点白描边（95% / 86%）**
不设 `zorder` 时数据可能被网格线或填充压住；关键标记点加白描边能从密集背景里"跳出来"：

```python
# 层次约定：参考带/网格 0-2 → 填充 3 → 数据主体 4-6 → 关键标记 7-9
ax.fill_between(x, lo, hi, color=..., alpha=0.2, zorder=2)
ax.plot(x, y, lw=2.0, color=PALETTE[0], zorder=6)
ax.scatter(x_key, y_key, s=86, color=PALETTE[2], zorder=8,
           edgecolors='white', linewidths=1.1)      # ★ 白描边=从背景里跳出来
ax.plot(x, y, '-o', markersize=4.4, markeredgecolor='white', markeredgewidth=0.7)
```

**⑥ 多 panel 在建图时分配版面，不在末尾反复挤边距**
多面板默认使用 `layout='constrained'`，需要公共图例、colorbar、边际分布或说明区时，
直接在 GridSpec 中给它们专用行/列。`tight_layout()` 只能处理简单矩形子图，不能证明图例、
inset 和自由文字没有遮挡；启用 constrained/compressed layout 后也不得再调用它或
`subplots_adjust()`，否则布局引擎会被关闭。

```python
fig = plt.figure(figsize=(6.0, 4.4), layout='constrained')
gs = fig.add_gridspec(3, 2, height_ratios=[0.13, 1.0, 1.0])
legend_ax = fig.add_subplot(gs[0, :]); legend_ax.axis('off')
axes = [fig.add_subplot(gs[r, c]) for r in (1, 2) for c in (0, 1)]
# 公共图例画到 legend_ax；需要 colorbar 时同样另建窄 cax。
```
只有完全手工的复杂版式才允许 `fig._mh_manual_layout=True` 后一次性设置 GridSpec 间距，
并由作者负责最终尺寸的逐图复核；不得同时混用两个布局系统。

## 避免的常见丑图

- ❌ 默认蓝色单色（用多色配色方案）
- ❌ 图内加 `plt.title()`（标题只在 LaTeX caption 中）
- ❌ 默认灰色网格线（去掉或用极淡的虚线）
- ❌ 图例遮挡数据（放在空白区域或图外）
- ❌ 坐标轴标签用变量名（如 `col_1`，应改为有意义的中文/英文标签）
- ❌ 字体太小（打印后看不清）
- ❌ 用 `jet` colormap（色盲不友好，用 `coolwarm` 或 `viridis`）

## ⛔ 防遮挡规则（文字/数据/曲线互相遮挡是最常见的图表质量问题）

### ⛔⛔ 上位原则：图内文字最小化，结论进正文（治遮挡的根，最先执行）
遮挡最常见的根因不是"没摆好"，而是**往绘图区塞了本不该进图的文字**。目标：**图内尽量不写字，最多留极简短标注**。放任何文字进图前先过下面三层闸。

**第 1 层·禁止（一律进图前后正文，不要浮在数据上）**
多行结论陈述、判据解释、方法说明、参数罗列——例如把这种框压在曲线上：

```
实测范围 4–21          ← ❌ 4 行统计结论浮在数据上，必然遮挡
中位 13.0
打满 21 的行占 5.12%
越界 0 行
```

这些内容移到图前后的正文解读，caption 只保留简短名词短语。这样不占绘图区、不遮挡且可检索，**信息零丢失**。判据：**两行及以上的解释性文字框一律移出图**；只有单位、公式或数值必须并列时才允许极短的两行锚点。

**第 2 层·克制（真要标，优先用"不占绘图区"的机制，别手写 `ax.text`）**

| 想标的东西 | ❌ 别手写 | ✅ 改用 |
|---|---|---|
| 柱顶/条端数值 | 每根柱都写数 | 只标正文会引用的关键柱；需要多个值时用 **`ax.bar_label`** 并做最终重叠检查 |
| 多条线/多个系列的身份 | 每条线旁写名字 | **图例**；图内无净空时用 GridSpec 专用区域或 `shared_legend`，不悬挂在画布外 |
| 散点/极值点的标签 | 密集堆放长标签 | **`smart_labels` / `adjustText`** 或少量手动偏移提供候选位置；最终复查数据、引线与边界 |
| 多个标注点（≥3） | 全堆图顶 | 只留正文真正讨论的点；必须全部区分时用短代号，含义写进正文 |
| 结论数值、占比、量级 | 图内文字框 | **图前后正文** |
| 阈值/上限线的说明 | 一句话 | 线旁**一个短标签**（如 `上限 21`），细节进正文 |

**第 3 层·必需（不受限制，砍掉反而是残图）**
坐标轴标签 + 单位、图例、colorbar、隐藏刻度时的直接数据标注。这些是图可读的下限，**不要为了"少写字"删掉**。

**颜色职责必须分开**：系列色/粉彩色首先是视觉分组的“填充”，不是文字墨色。普通数值、阈值和短注释
默认使用 `COLORS['text']`；不得直接写 `color=PALETTE[i]` 或 `color=PALETTE_LIGHT[i]` 来给文字着色。
若类别身份确实需要彩色文字，按文字所在的**实际合成背景**校验，普通文字至少 4.5:1；不能因为源字号达到 14pt 就放宽，插入论文后它可能被缩小。
深色柱/色块内可以用白字，浅色柱内使用深色字；不能让数字跟着方块一起变浅，导致“有颜色但看不清”。

**配额参考**：图内 `ax.text`/`annotate` **每个 panel ≤2 个、每个 ≤1 行**（按 panel 算，多 panel 图不必因此变挤）。超了先问：“删掉后还能从轴、图例和正文读懂吗？”能就删；需要解释的移入正文。

**万一信息非图内呈现不可**：拆一个专门的文字/图例**子面板**，或扩大边距留白区放，**绝不浮在数据上**。横向类别行过密时保持原生宽度不变，只增加画布高度（最高 8in），避免论文按栏宽缩放后字号反而更小。

⛔ **不要过度收缩**：本条减的是“解释性文字”，不是数据和证据。题目确实需要的 panel、置信带和判据线应保留；不服务于当前结论的层、框和标注则删除。把结论搬进图前后正文是为了让图更清楚，不是把图做简陋。

### 图例位置

图内图例、顶部图例和右侧图例都可以合格；按数据空白、标签长度和面板结构选择，
不要把“总是上方”或“用了 `loc='best'`”当规则。顶部通常适合少量横向条目，
右侧或独立单元格适合较长列表，但都须在最终尺寸下核对。

- 简单单图用 `auto_legend(ax)`：原位置安全就保留，有冲突时先测量图内其他位置，再分配轴外区域。
  面积较大但有真实净空的图例也可保留；`occ_tol` 不能用来许可覆盖曲线或误差带。
- 多面板先判断系列语义是否相同。共同系列可用 `consolidate_shared_legends(fig, axes)`，
  默认按实际文本宽高选择紧凑顶部/右侧区域；也可显式设置 `where='top'` 或 `'right'`。
  不为每张图复制固定 0.18 顶部行高，不默认 `mode='expand'` 把短图例铺满。
- 复杂布局确需 GridSpec 专用行/列时按最终字号测量区域，不使用负坐标或
  `bbox_inches='tight'` 将图例悬挂在画布外；合格的现有独立区域不必为了统一而改动。
- `shared_legend` / `consolidate_shared_legends` 也可分配图级区域；只合并同一语义系列。
  不同面板里同名但不同含义的系列不能误合并。
- 保存后检查图例与相邻面板、标题、直接标签、数据及整张画布边界，不只检查图例所在轴。
- 放不下时缩短说明性标签、调整列数或拆图；不能将必要标签压到最终 8pt 以下。

下面是可运行的布局示例，使用合成数据验证独立图例区，并非论文结果：

```python
# layout-regression: dedicated-legend
import numpy as np
import matplotlib.pyplot as plt
from _utils.plot_utils import setup_style, set_paper_placement, save_fig, consolidate_shared_legends, PALETTE
setup_style()
fig, axes = plt.subplots(1, 2, figsize=(6.4, 3.8), layout='constrained')
set_paper_placement(fig)
x = np.linspace(0, 1, 31)
for i, ax in enumerate(axes):
    ax.plot(x, x ** (i + 1), color=PALETTE[0], label='Series A')
    ax.plot(x, 0.2 + 0.6 * x, color=PALETTE[1], linestyle='--', label='Series B')
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Response (a.u.)')
    ax.set_title(f'({chr(97 + i)})', loc='left')
consolidate_shared_legends(fig, axes)  # 按标签测量区域，不把示例固定成所有图的模板
save_fig(fig, 'figures/fig_layout_legend.pdf')
plt.close(fig)
```

更少的条目并不要求轴外图例；有真实稳定净空时保留图内图例即可。
专用区域只是可靠的布局手段，仍要通过保存钩子、公共检查器与最终渲染复核。
位置与留白偏好只作设计建议，不因“顶部图例多”新增硬失败或模型返修轮次；
只对实际遮挡、裁切和不可读问题处理。不得为多样性随机换位置。

### 数值标注
- **柱状图标注**：优先少量必要值；`bar_label` 只生成初始位置，不会检查邻柱、误差棒或边界。柱内完整容纳且对比度合格也可保留。
- **密集柱值**：改用独立值列、增高或拆图；删去的重复标注仍保留在完整结果表中，不以旋转或小字号掩盖拥挤。
- **散点图标注**：`smart_labels` / `adjustText` 和手动偏移都要复核最终位置与指向，不能将标签移动到错误类别。
- **热力图数值**：按最终印刷 ≥8pt 规划；密集时不逐格标数，但保留色条、完整矩阵和读数途径。
- **文字不得被线穿过**：单个标签也要检查其矩形范围，不能因为“只有一条文字、没有文字互撞”就跳过。
  优先移动到曲线的法向空白侧；白色或不透明背景框只能改善文字对比度，**不能覆盖曲线来伪装修复**。
  若没有空位，删去该标注、缩成短代号，或把它放入专用说明区。
- **散点、星号与箭头也算实体**：按最终渲染后的符号外接框和箭头路径检查，文字框不得与其相交；不能只检测文字之间是否重叠。
- **柱内/柱外必须二选一**：完整落在柱体内且对比度合格可以保留；跨骑柱边界一律视为遮挡，改用柱外固定值列或删去次要数值。
- **类别行锁定**：水平柱图、棒棒糖图和甘特图的标签不得越过相邻类别行中线。避让空间不足时先删减解释性标注，再缩成短代号或固定值列，最后增加画布高度；禁止把标签推到邻行。
- **⛔ 单条竖线标注（如 Makespan 线）**：线旁一个**短标签**即可，别放 X 轴刻度区（会和刻度重叠）。**只有 1-2 条竖线时**才把短标签贴到线顶：
  ```python
  # ❌ 错误：标注放在 X 轴附近，和刻度重叠
  ax.text(makespan, 0, f'Makespan={makespan}', color='red')
  # ✅ 正确（仅 1-2 条竖线）：短标签贴线顶，用 transform 定位
  ax.axvline(makespan, color=PALETTE[0], ls='--', lw=1.5)
  ax.text(makespan, 0.97, f'M={makespan}', color=COLORS['text'],
          transform=ax.get_xaxis_transform(), ha='right', va='top', fontsize=9)
  ```
- **⛔⛔ 多条竖线/多个标注（≥3 个）时禁止全堆图顶**（会层叠糊成一团，是最常见的遮挡事故）：先只保留正文实际讨论的线；必须全部区分时用**短编号 ①②③ + 图例**，详细含义写进正文。绝不把多个文字标签都塞到 `y=0.95` 顶部。

### 曲线/数据点重叠
- **多条折线重叠**：用不同线型（实线/虚线/点线/点划线）+ 不同标记（o/s/^/D）区分
- **散点图数据密集**：降低 `alpha=0.5-0.7`，或用 hexbin/KDE 等高线代替
- **多组箱线图/小提琴图**：确保组间间距足够，`width` 不要超过 0.8

### inset / 局部放大图
- 只有主图确有稳定空白区时才允许 inset；位置必须在最终布局和最终插图宽度下复核。
- 主图无空白区或 inset 信息量较大时，用 GridSpec 作为独立 panel，并用连接线表达对应范围。
- inset 不得覆盖峰值、拐点、关键容差带、柱顶数字、图例、坐标标签，也不得跨入相邻 panel。
- **覆盖层配额**：同一 panel 的 inset、统计框、图例三者最多同时保留一个在绘图区内；需要两个及以上时，
  至少一个必须迁入 GridSpec 专用行/列。不要把“主图 + inset + 统计框 + 图例”叠成四层。
- 边际分布不是 inset：散点主图配顶部/右侧分布时，必须用 GridSpec/`subplot_mosaic` 分配独立 axes，
  共享坐标并隐藏重复刻度；不得把边际轴浮盖在主图上。

### 对数轴与双轴
- 对数轴跨越多个数量级时，次刻度只保留每个 decade 的 2、5 两档，次刻度不显示标签；
  默认 8 个次刻度/decade 在窄 panel 中会连成“黑梳子”。`plot_utils` 保存钩子只会对
  Matplotlib 默认且过密的 `LogLocator` 自动稀疏，自定义 locator 不会被改写。
- `twinx()` 只在两个量纲确实必须共用 x 轴时使用。左右轴颜色、标签与对应曲线一致，但刻度文字仍需
  达到背景对比度；两侧都为对数轴或都有密集注释时，优先拆为上下共享 x 的两个 panel。
- 对数轴稀疏化不得改变主刻度、范围、数据或数值精度；只减少装饰性的次刻度。

### 遮挡修复顺序（必须按此顺序）
1. 删除图内结论句，把解释放回正文；
2. 合并重复图例，给图例/colorbar/边际分布分配专用区域；
3. 将 inset 改成独立 panel，或删去重复证据；
4. 保持最终栏宽不变，只增加必要的画布高度或拆图；
5. 最后才移动少量短标签并校验真实背景对比度。

不得用缩小到 8pt 以下、无限放大原生画布、`bbox_inches='tight'`、反复 `tight_layout()`，
或给文字铺不透明白底盖住数据来换取表面上的“不重叠”。

### 坐标轴标签
- **长标签**：用 `rotation=45, ha='right'` 斜着显示，或换行 `'第一行\n第二行'`
- **中文标签**：每个标签不超过 6 个字，超过就缩写或换行
- **刻度太密**：用 `ax.xaxis.set_major_locator(MaxNLocator(nbins=6))` 减少刻度数

### 通用技巧
```python
# 保存时确保不裁切标签
save_fig(fig, 'xxx.pdf')

# 多子图在创建时分配布局；不要在末尾反复 tight_layout 碰运气
fig, axes = plt.subplots(1, 2, layout='constrained')

# 少量散点标注的候选避让；仅在预装 adjustText 时使用，缺包可手动留白，不在绘图中联网安装
from adjustText import adjust_text
texts = [ax.text(x[i], y[i], labels[i], fontsize=8) for i in range(len(x))]
adjust_text(texts, ax=ax, arrowprops=dict(arrowstyle='->', color=COLORS['ref_line'], lw=0.5))
# 还需检查最终位置、指向及边界；不能把调用成功视为遮挡检查通过
```

## SciencePlots 库（可选）

通过 `setup_style()` 或 `setup_style(palette='nature')` 统一初始化。
若环境已安装 SciencePlots，公共助手按已有策略使用它；缺失时采用内置样式，不在绘图中联网安装。
不要在 setup 后再次 `plt.style.use(...)` 覆盖中文后备字体、字号或保存契约。

## TikZ 技术路线图/架构图参考（仅学习结构，不是固定模板）

> **规范优先级**：TikZ 成品必须以 `tikz_rules.md` 的“语义驱动、自适应布局”规范为准。下面保留的旧代码只用于查看某种 TikZ 语法如何实现分层、并行、判断和汇聚，**不得复制固定色值、固定宽高、固定节点数或固定模板选择逻辑**。任何“必须用某模板/某颜色/圆角/纵向/13cm”的旧措辞都视为历史示例，不构成生产规则。

TikZ 图质量差的根因通常不是“颜色不够多”，而是信息拓扑选错、层级不清、交叉和遮挡、最终尺寸文字过小，以及视觉编码与论文语境不一致。好的技术路线图可以横向、纵向、分栏或泳道，也可以黑白；方向和样式应由真实依赖关系与版面共同决定。

### 设计原则

1. **先定语义**：颜色、形状、线型分别承担什么含义，写进图契约
2. **按拓扑布局**：线性、分层、并行、循环、几何各用合适的布局，不按题型套模板
3. **减少交叉**：先重排节点，再设路由；反馈和长边走外围
4. **使用真实边界间距**：间距取决于文字、边标签和最终栏宽，不固定为某个厘米值
5. **最终尺寸可读**：主要语义有效字号约 8pt 以上，密图优先拆分而非缩小
6. **风格自适应**：黑白、单色、定性配色均可；同一语义在一篇论文内保持一致
7. **过程与结果分离**：技术路线图、流程图、架构图只表达对象、方法、依赖和输出名称；不得写入本题已经算出的最终数值，也不得写“验证通过”“结论成立”“显著优于”等结果性判断。算法精度、步长和迭代上限属于过程设置，可以保留；真正的结果进入数据图、表格和正文。

### 历史模板 1/2/3：存在已知遮挡问题，仅保留迁移说明

模板 1（纵向路线图）、模板 2（问题关系图）、模板 3（模型架构图）是早期简单版本，存在左侧文字重叠、线穿过节点等问题。**⛔ 不要使用模板 1/2/3，改用模板 4/9/10/11。**

- 模板 1 的场景 → 用模板 4 或模板 9
- 模板 2 的场景 → 用模板 10（管道式）
- 模板 3 的场景 → Claude 自由画架构图，遵守防遮挡规则即可

### 历史示例 4：分阶段分组结构（仅参考语法）

白底 + 浅灰虚线框分阶段 + 蓝色主节点（微阴影）+ 白色子节点 + 蓝色粗箭头。简洁专业，适合所有论文类型。不依赖 `backgrounds` 和 `fit` 库。

**完整代码**：
- 通用版：见 `demo_roadmap_template4.tex`
- 竞赛专用版（多问题双行+星号标注）：见 `demo_roadmap_competition.tex`

`demo_roadmap_competition.tex` 仅展示“阶段内主节点 + 子节点”的一种实现。竞赛论文应按真实子问题依赖决定串行、并行或混合结构；不得机械四列排布，也不得用星号宣称未经证据支持的“最优方法”。

**使用规则：只参考相对定位、样式集中定义和连线语法。生产图必须重做图契约、布局和论文级语义令牌，不能只改文字。**

**核心样式定义**（直接复制到 tikzpicture 参数）：
```latex
\begin{tikzpicture}[scale=1.0,
    main/.style={rectangle, rounded corners=3pt,
        minimum width=5.5cm, minimum height=0.7cm,
        draw=blue!80, line width=0.7pt, fill=blue!6,
        font=\small\bfseries, align=center,
        drop shadow={opacity=0.15, shadow xshift=0.5pt, shadow yshift=-0.5pt}},
    sub/.style={rectangle, rounded corners=2pt,
        minimum width=2.4cm, minimum height=0.6cm,
        draw=teal!70, line width=0.5pt, fill=white,
        font=\footnotesize, align=center},
    dashbox/.style={rectangle, rounded corners=4pt,
        draw=gray!40, dashed, line width=0.7pt, fill=gray!2},
    bigarrow/.style={-stealth, line width=1.4pt, color=blue!70},
    smarrow/.style={-stealth, line width=0.5pt, color=gray!50},
    label/.style={font=\small\bfseries, color=black!70},
]
```

**历史语法片段**（只用于理解节点、连线和分组框写法，不得重复套用到每个阶段）：
```latex
% === 阶段 N ===
% 历史写法：固定框和绝对坐标。生产图应改为 fit + 相对布局。
\node[dashbox, minimum width=13cm, minimum height=2cm] (boxN) at (0, Y) {};
\node[label, anchor=north west] at (boxN.north west) {\scriptsize 阶段名称};

% 主节点（颜色由当前论文语境决定）
\node[main] (mN) at (0, Y+0.35) {主步骤名称};

% 3. 子节点（白色，一行排列，间距 2.8cm）
\node[sub] (sNa) at (-4.2, Y-0.65) {方法A};
\node[sub] (sNb) at (-1.4, Y-0.65) {方法B};
\node[sub] (sNc) at (1.4, Y-0.65) {方法C};
\node[sub] (sNd) at (4.2, Y-0.65) {方法D};
\foreach \x in {sNa,sNb,sNc,sNd} {\draw[smarrow] (mN) -- (\x);}

% 4. 阶段间粗箭头
\draw[bigarrow] (0, Y-1.4) -- (0, Y-2.0);
```

**历史双层写法**（仅演示语法；生产图不得据此固定 4.2cm）：
```latex
\node[dashbox, minimum width=13cm, minimum height=4.2cm] (boxN) at (0, Y) {};
% 第一行主节点 + 子节点
\node[main] (mN) at (0, Y+1.7) {第一步};
\node[sub] ... % 子节点
% 第二行主节点 + 子节点
\node[main] (mNb) at (0, Y-0.5) {第二步};
\node[sub] ... % 子节点
```

**生产图替换原则**：
- 历史示例中的 13cm、2cm、4.2cm 和固定 x 坐标都不是规范；组框用 `fit`，间距按真实节点边界自适应；
- 子节点数量和拓扑决定方向、行列与间距，禁止为凑成四列而复制或压缩内容；
- 阶段间距由最终字号、箭头和边标签共同决定，并在论文实际宽度下复核；
- “最佳”“关键”“异常”等强调必须有真实语义依据，并通过形状/线型/文字冗余表达。

**使用规则：下面的色值是历史演示值，不得作为题型绑定色板。生产图从当前论文语境选择黑白、单色或少量语义色，并通过集中令牌管理。**

<tikz_color_schemes>
#### 历史配色演示（仅说明 xcolor 写法，不按论文类型选择）

**历史方案 A：低饱和蓝灰+淡青（无默认题型，仅演示 xcolor 写法）**
```latex
main/.style={fill={rgb,255:red,200;green,218;blue,235},
    draw={rgb,255:red,140;green,170;blue,200}, ...},
sub/.style={fill={rgb,255:red,218;green,232;blue,220},
    draw={rgb,255:red,165;green,200;blue,175}, ...},
bigarrow: color={rgb,255:red,74;green,144;blue,184}
```

**历史方案 B：钢蓝+浅灰蓝（无题型绑定，仅演示 xcolor 写法）**
```latex
main/.style={fill={rgb,255:red,180;green,210;blue,235},
    draw={rgb,255:red,120;green,160;blue,200}, ...},
sub/.style={fill={rgb,255:red,220;green,230;blue,240},
    draw={rgb,255:red,170;green,190;blue,210}, ...},
bigarrow: color={rgb,255:red,70;green,100;blue,150}
```

**历史方案 C：薰衣草紫+淡粉（无题型绑定，仅演示 xcolor 写法）**
```latex
main/.style={fill={rgb,255:red,210;green,195;blue,230},
    draw={rgb,255:red,170;green,150;blue,200}, ...},
sub/.style={fill={rgb,255:red,235;green,215;blue,225},
    draw={rgb,255:red,200;green,175;blue,195}, ...},
bigarrow: color={rgb,255:red,130;green,100;blue,160}
```

**方案 D：青绿+薄荷（适合环境/地理/生态）**
```latex
main/.style={fill={rgb,255:red,175;green,220;blue,210},
    draw={rgb,255:red,120;green,185;blue,170}, ...},
sub/.style={fill={rgb,255:red,215;green,235;blue,225},
    draw={rgb,255:red,170;green,205;blue,190}, ...},
bigarrow: color={rgb,255:red,60;green,130;blue,120}
```

**方案 E：暖灰+赭石（适合人文/历史/法学，低调沉稳）**
```latex
main/.style={fill={rgb,255:red,225;green,210;blue,195},
    draw={rgb,255:red,190;green,170;blue,150}, ...},
sub/.style={fill={rgb,255:red,235;green,230;blue,220},
    draw={rgb,255:red,200;green,195;blue,180}, ...},
bigarrow: color={rgb,255:red,140;green,120;blue,100}
```

**历史说明（已废止）**：
| 旧分类标签 | 旧示例（不得据此自动选择） |
|---------|---------|
| 经管/统计/社科/竞赛 | 曾用 A（不能作为默认） |
| CS/AI/电子/通信 | 曾用 B（不能作为默认） |
| 医学/生物/心理 | 曾用 C（不能作为默认） |
| 环境/地理/生态/农学 | 曾用 D（不能作为默认） |
| 人文/历史/法学/哲学 | 曾用 E（不能作为默认） |

All schemes share the same structural rules: white background, dashed boxes, rounded corners, draw-order layering. Only the fill/draw colors differ.
</tikz_color_schemes>

```latex
\begin{figure}[H]
\centering
\begin{tikzpicture}[scale=0.85, every node/.style={scale=0.85},
    main/.style={fill={rgb,255:red,200;green,218;blue,235},
        draw={rgb,255:red,140;green,170;blue,200}, rounded corners=3pt,
        minimum width=4.5cm, minimum height=0.6cm, align=center,
        font=\small, line width=0.4pt},
    sub/.style={fill={rgb,255:red,218;green,232;blue,220},
        draw={rgb,255:red,165;green,200;blue,175}, rounded corners=2pt,
        minimum width=2cm, minimum height=0.5cm, align=center,
        font=\footnotesize, line width=0.3pt},
    bigarrow/.style={-{Stealth[length=7pt,width=5pt]}, line width=1.8pt,
        color={rgb,255:red,74;green,144;blue,184}},
    smarrow/.style={-{Stealth[length=3pt]}, line width=0.3pt, color=gray!40},
    lbl/.style={font=\small\bfseries, color=black},
    dashbox/.style={draw=gray!40, dashed, rounded corners=4pt,
        fill={rgb,255:red,248;green,249;blue,250}},
]

% 第一步：虚线框（先画，节点覆盖在上面）
\node[dashbox, minimum width=10.5cm, minimum height=1.6cm] (b1) at (0, -0.3) {};
\node[lbl, anchor=east] at ([xshift=-6pt]b1.west) {综述};
\node[dashbox, minimum width=10.5cm, minimum height=5.2cm] (b2) at (0, -3.15) {};
\node[lbl, anchor=east] at ([xshift=-6pt]b2.west) {模型构建};
\node[dashbox, minimum width=10.5cm, minimum height=2.2cm] (b3) at (0, -6.65) {};
\node[lbl, anchor=east] at ([xshift=-6pt]b3.west) {实证分析};
\node[dashbox, minimum width=10.5cm, minimum height=2.2cm] (b4) at (0, -9.35) {};
\node[lbl, anchor=east] at ([xshift=-6pt]b4.west) {策略应用};
\node[dashbox, minimum width=10.5cm, minimum height=2.2cm] (b5) at (0, -12.05) {};
\node[lbl, anchor=east] at ([xshift=-6pt]b5.west) {结论};

% 第二步：节点和箭头
% 阶段1
\node[main] (m1) at (0, 0) {绪论};
\draw[bigarrow] (0,-0.7) -- (0,-1.3);

% 阶段2
\node[main] (m2) at (0,-1.8) {理论基础};
\node[sub] (s2a) at (-2.8,-2.7) {文献回顾};
\node[sub] (s2b) at (-0.9,-2.7) {概念界定};
\node[sub] (s2c) at (0.9,-2.7) {理论框架};
\node[sub] (s2d) at (2.8,-2.7) {研究假设};
\foreach \x in {s2a,s2b,s2c,s2d} {\draw[smarrow] (m2) -- (\x);}
\node[main] (m2b) at (0,-3.6) {模型设定};
\foreach \x in {s2b,s2c} {\draw[smarrow] (\x) -- (m2b);}
\node[sub] (s2e) at (-2.2,-4.5) {变量定义};
\node[sub] (s2f) at (0,-4.5) {计量模型};
\node[sub] (s2g) at (2.2,-4.5) {识别策略};
\foreach \x in {s2e,s2f,s2g} {\draw[smarrow] (m2b) -- (\x);}
\draw[bigarrow] (0,-5.2) -- (0,-5.8);

% 阶段3
% 阶段3 — 以下节点文字仅为示例，根据实际研究内容替换
% Example nodes shown below. Replace with actual research content:
% 预测类：数据预处理/模型构建/模型对比/预测应用
% 分类类：特征工程/模型训练/分类评估/模型解释
% 评价类：指标构建/权重确定/综合评价/结果分析
% 因果推断类：描述统计/回归分析/稳健检验/异质分析
\node[main] (m3) at (0,-6.3) {模型构建与分析};
\node[sub] (s3a) at (-3.2,-7.2) {数据预处理};
\node[sub] (s3b) at (-1.1,-7.2) {模型构建};
\node[sub] (s3c) at (1.1,-7.2) {模型对比};
\node[sub] (s3d) at (3.2,-7.2) {结果分析};
\foreach \x in {s3a,s3b,s3c,s3d} {\draw[smarrow] (m3) -- (\x);}
\draw[bigarrow] (0,-7.9) -- (0,-8.5);

% 阶段4
\node[main] (m4) at (0,-9) {策略应用};
\node[sub] (s4a) at (-2.2,-9.9) {制度优化};
\node[sub] (s4b) at (0,-9.9) {实施路径};
\node[sub] (s4c) at (2.2,-9.9) {保障措施};
\foreach \x in {s4a,s4b,s4c} {\draw[smarrow] (m4) -- (\x);}
\draw[bigarrow] (0,-10.6) -- (0,-11.2);

% 阶段5
\node[main] (m5) at (0,-11.7) {结论};
\node[sub] (s5a) at (-2.2,-12.6) {主要结论};
\node[sub] (s5b) at (0,-12.6) {创新点};
\node[sub] (s5c) at (2.2,-12.6) {研究展望};
\foreach \x in {s5a,s5b,s5c} {\draw[smarrow] (m5) -- (\x);}

\end{tikzpicture}
\caption{研究技术路线图}
\label{fig:research-roadmap}
\end{figure}
```

**架构要点（Claude 画技术路线图时必须遵循）：**
1. **不依赖 `backgrounds` 和 `fit` 库**——只用 `tikz` + `arrows.meta` + `positioning` + `shapes.geometric` + `calc`
2. **不要灰色大背景 `\fill`**——白底最安全，不会出现黑色外围
3. 虚线框用 `dashbox` 样式（手动坐标 + minimum width/height），极浅灰填充 `rgb(248,249,250)`
4. **先画虚线框，再画节点**——利用绘制顺序，节点的 fill 自然覆盖虚线框
5. 左侧标签用 `lbl` 样式，**颜色必须是 `color=black`**，不要蓝色
6. 主节点统一橙色（`rgb(240,195,150)`），子节点统一绿色（`rgb(185,215,180)`）
7. 阶段间用蓝色粗箭头 `bigarrow`，节点间用灰色细箭头 `smarrow`
8. `scale=0.85` 确保一页放得下，阶段控制在 4-5 个
9. 子节点间距至少 1.5cm，超过 4 个分两行
10. **禁止用 `on background layer`、`fit=()`、灰色大背景 `\fill`**

#### 虚线框坐标计算规则（⛔ 防止框重叠）

虚线框用手动坐标，必须按以下规则计算，不能靠猜：

**单层阶段**（1 个主节点 + 1 行子节点）：
- 主节点 y 坐标 = `Y`
- 子节点 y 坐标 = `Y - 0.9`
- 虚线框中心 y = `(Y + Y-0.9) / 2 = Y - 0.45`
- 虚线框高度 = `1.6cm`
- 粗箭头从 `Y - 1.6` 到 `Y - 2.2`（间距 0.6）
- 下一阶段主节点 y = `Y - 2.7`（间距 = 上一阶段底部 + 0.5）

**双层阶段**（2 个主节点 + 2 行子节点）：
- 第一主节点 y = `Y`，第一行子节点 y = `Y - 0.9`
- 第二主节点 y = `Y - 1.8`，第二行子节点 y = `Y - 2.7`
- 虚线框中心 y = `(Y + Y-2.7) / 2 = Y - 1.35`
- 虚线框高度 = `3.4cm`
- 粗箭头从 `Y - 3.4` 到 `Y - 4.0`
- 下一阶段主节点 y = `Y - 4.5`

**三层阶段**（主节点 + 子节点 + 第二主节点 + 第二行子节点 + 第三行子节点）：
- 虚线框高度 = `5.2cm`，按实际内容范围计算

**关键公式**：
```
dashbox_center_y = (最高节点y + 最低节点y) / 2
dashbox_height = (最高节点y - 最低节点y) + 1.4cm  (上下各留 0.7cm padding)
bigarrow_start_y = 最低节点y - 0.7
bigarrow_end_y = bigarrow_start_y - 0.6
next_stage_main_y = bigarrow_end_y - 0.5
```

**验证方法**：每个虚线框的底边 y = `center_y - height/2`，下一个虚线框的顶边 y = `next_center_y + next_height/2`。两者之间必须有 ≥ 0.3cm 的间距，否则会重叠。
    % 阶段间粗箭头（灰蓝色，和竖条同色系）
    bigarrow/.style={-{Stealth[length=8pt, width=6pt]}, line width=2pt,
        color={rgb,255:red,90;green,120;blue,150}},
    % 节点间细箭头
    arrow/.style={-{Stealth[length=4pt]}, line width=0.5pt, color=gray!60},
]

% ========== 阶段一：研究设计 ==========
\node[stagelabel, rotate=90] (L1) at (-6.5, 0) {研究设计};
\node[stagebox] (B1) at (0, 0) {};
\node[main] (m1) at (0, 0.8) {研究问题确定};
\node[sub] (s1a) at (-3, -0.3) {文献梳理};
\node[sub] (s1b) at (-1, -0.3) {理论分析};
\node[sub] (s1c) at (1, -0.3) {假设提出};
\node[sub] (s1d) at (3, -0.3) {研究设计};
\draw[arrow] (m1) -- (s1a); \draw[arrow] (m1) -- (s1b);
\draw[arrow] (m1) -- (s1c); \draw[arrow] (m1) -- (s1d);

% 阶段间箭头
\draw[bigarrow] (0, -1.8) -- (0, -2.5);

% ========== 阶段二：数据与变量 ==========
\node[stagelabel, rotate=90] (L2) at (-6.5, -4.2) {数据与变量};
\node[stagebox] (B2) at (0, -4.2) {};
\node[main] (m2) at (0, -3.4) {数据收集与处理};
\node[sub] (s2a) at (-3.5, -4.5) {数据来源};
\node[sub] (s2b) at (-1.2, -4.5) {变量构建};
\node[sub] (s2c) at (1.2, -4.5) {描述性统计};
\node[sub] (s2d) at (3.5, -4.5) {相关性分析};
\draw[arrow] (m2) -- (s2a); \draw[arrow] (m2) -- (s2b);
\draw[arrow] (m2) -- (s2c); \draw[arrow] (m2) -- (s2d);

% 阶段间箭头
\draw[bigarrow] (0, -6) -- (0, -6.7);

% ========== 阶段三：实证分析 ==========
\node[stagelabel, rotate=90] (L3) at (-6.5, -8.8) {实证分析};
\node[stagebox, minimum height=3.8cm] (B3) at (0, -8.8) {};
\node[main] (m3) at (0, -7.6) {模型构建};
% 子节点分两行 — 以下节点文字仅为示例，根据实际研究内容替换
\node[sub] (s3a) at (-3.5, -8.8) {数据预处理};
\node[sub] (s3b) at (-1.2, -8.8) {模型构建};
\node[sub] (s3c) at (1.2, -8.8) {模型对比};
\node[sub] (s3d) at (3.5, -8.8) {结果分析};
\draw[arrow] (m3) -- (s3a); \draw[arrow] (m3) -- (s3b);
\draw[arrow] (m3) -- (s3c); \draw[arrow] (m3) -- (s3d);
\node[main] (m3b) at (0, -10.1) {模型诊断与检验};

% 阶段间箭头
\draw[bigarrow] (0, -11) -- (0, -11.7);

% ========== 阶段四：结论 ==========
\node[stagelabel, rotate=90] (L4) at (-6.5, -12.8) {结论建议};
\node[stagebox, minimum height=2cm] (B4) at (0, -12.8) {};
\node[main] (m4) at (0, -12.4) {研究结论};
\node[sub] (s4a) at (-2, -13.4) {政策建议};
\node[sub] (s4b) at (0, -13.4) {研究局限};
\node[sub] (s4c) at (2, -13.4) {未来展望};
\draw[arrow] (m4) -- (s4a); \draw[arrow] (m4) -- (s4b); \draw[arrow] (m4) -- (s4c);

\end{tikzpicture}
\caption{研究技术路线图}
\label{fig:research-roadmap}
\end{figure}
```

**架构要点（模板 4 通用规则）：**
1. **绘制顺序决定层级**：先画灰色大背景 → 再画白色虚线框 → 最后画节点和箭头。Do not use `on background layer` or `fit` library
2. 虚线框用 `dashbox` 样式（手动坐标，白色填充），不用 `fit`
3. 左侧阶段标签水平书写，放在虚线框外面左侧
4. 视觉语言从论文语境和角色语义推导；可以黑白、单色或少量类别色，不绑定上方历史色板
5. 主流程与辅助/反馈边用线宽、线型或箭头形状区分，不能只靠颜色
6. 阅读方向由真实依赖和最终栏宽决定，可纵向、横向、分栏或泳道
7. 高饱和色可用于小面积、有依据的唯一强调点；禁止无语义彩虹和颜色独占编码
8. 间距按节点真实边界和边标签动态确定；放不下时重排或拆图，不机械压成固定列数

### 常见丑图 vs 好图对比

| 丑图特征 | 改进方法 |
|----------|---------|
| 每个阶段无理由换颜色 | 先定义角色语义；颜色不是必要时改用编号、组框和线型 |
| 用了 `on background layer` 导致黑底 | 用绘制顺序控制层级 |
| 形状没有语义 | 为不同角色选择稳定形状；直角或圆角都可 |
| 箭头太细看不清 | 按最终插图尺寸提高有效线宽和对比度 |
| 节点挤在一起 | 增加真实边界净空、改变方向或拆成总览+局部 |
| 没有层次感 | 用留白、对齐、组框、字号和线型建立层次，颜色仅作辅助 |
| 箭头交叉乱 | 用 `|-` 和 `-|` 走直角路径，避免斜线交叉 |
| 字体太大 | 节点内用 `\small`，标签用 `\footnotesize` |


### 历史示例 9：圆形编号 + 卡片分层（语法参考）

**视觉特征**：左侧圆形编号+阶段名称 + 浅色卡片区域 + 方法节点/工具节点双层信息 + 右侧胶囊输出标签。适合方法论丰富的实证研究。

**历史代码**（只学习卡片分层写法，不得只改文字后直接交付）：

```latex
\begin{figure}[H]
\centering
\begin{tikzpicture}[
    phasenum/.style={circle, fill={rgb,255:red,#1}, minimum size=22pt,
        font=\footnotesize\bfseries, text=white, inner sep=0pt},
    phasename/.style={font=\small\bfseries, color={rgb,255:red,#1}, anchor=west},
    method/.style={fill={rgb,255:red,#1}, draw={rgb,255:red,#2}, 
        rounded corners=4pt, minimum width=3.4cm, minimum height=0.85cm, 
        align=center, font=\small, line width=0.5pt},
    tool/.style={fill={rgb,255:red,248;green,248;blue,248}, 
        draw={rgb,255:red,210;green,210;blue,210}, rounded corners=2pt,
        minimum width=1.8cm, minimum height=0.5cm, align=center,
        font=\scriptsize, line width=0.3pt},
    outputtag/.style={fill={rgb,255:red,#1}, rounded corners=10pt,
        minimum width=1.6cm, minimum height=0.4cm, align=center,
        font=\tiny\bfseries, text=white, inner sep=2pt},
    pipe/.style={-{Stealth[length=7pt, width=5pt]}, line width=1.8pt,
        color={rgb,255:red,200;green,210;blue,225}},
    inner/.style={-{Stealth[length=3pt]}, line width=0.4pt, color=gray!45},
    card/.style={fill={rgb,255:red,#1}, rounded corners=6pt, line width=0pt},
]
% Phase 1: 研究设计（蓝色）
\fill[card={245;green,250;blue,255}] (-1, 2.3) rectangle (15.5, -0.8);
\node[phasenum={100;green,160;blue,210}] at (-0.2, 1.7) {1};
\node[phasename={80;green,140;blue,190}] at (0.4, 1.7) {研究设计};
\node[method={232;green,243;blue,252}{165;green,200;blue,230}] (rq) at (3.2, 1.0) {研究问题提出};
\node[method={232;green,243;blue,252}{165;green,200;blue,230}] (lit) at (7.2, 1.0) {系统文献综述};
\node[method={232;green,243;blue,252}{165;green,200;blue,230}] (hypo) at (11.2, 1.0) {假设与框架构建};
\draw[inner] (rq) -- (lit); \draw[inner] (lit) -- (hypo);
\node[tool] at (3.2, -0.05) {文献计量}; \node[tool] at (5.5, -0.05) {知识图谱};
\node[tool] at (8.2, -0.05) {理论推演}; \node[tool] at (11.2, -0.05) {概念模型};
\node[outputtag={100;green,160;blue,210}] at (14.2, 1.0) {理论模型};
\draw[pipe] (7.2, -0.8) -- (7.2, -1.6);
% Phase 2: 数据准备（绿色）— 同样结构，换色
% Phase 3: 实证分析（橙色）— 三行：模型设定→机制检验→稳健性
% Phase 4: 结论建议（紫色）
% 每阶段重复：卡片背景 → 编号+名称 → 方法节点行 → 工具节点行 → 输出标签 → 管道箭头
\end{tikzpicture}
\caption{研究技术路线图}
\end{figure}
```

**历史四阶段配色示意**（不是生产色板；真实配色按图契约重定）：
- 研究设计：编号 `rgb(100,160,210)`，卡片 `rgb(245,250,255)`，方法节点 `rgb(232,243,252)`
- 数据准备：编号 `rgb(80,170,130)`，卡片 `rgb(245,252,248)`，方法节点 `rgb(230,246,237)`
- 实证分析：编号 `rgb(215,155,75)`，卡片 `rgb(255,251,243)`，方法节点 `rgb(255,244,228)`
- 结论建议：编号 `rgb(150,120,180)`，卡片 `rgb(250,247,255)`，方法节点 `rgb(242,237,252)`

**架构要点**：
1. 不依赖 `backgrounds`/`fit` 库，用绘制顺序控制层级
2. 左侧圆形编号 + 阶段名称文字（不要用色带竖条）
3. 方法节点和工具节点形成双层信息，方法节点 y 间距 ≥ 1.0cm
4. 工具节点间距 ≥ 2.2cm，一行最多 5 个
5. 右侧胶囊标签标注每阶段输出物
6. 完整示例见 `demo_roadmap_research_premium.tex`

---

### 历史示例 10：管道分段 + 并行分支 + 汇聚（语法参考）

**视觉特征**：5段管道色块 + 白色卡片带顶部彩色装饰条 + 并行三分支建模 + 汇聚节点 + 圆角胶囊方法标签 + 左侧圆形编号。适合多模型对比、数据驱动研究。

**完整代码**：见 `demo_roadmap_research_pipeline.tex`

**历史五阶段配色示意**（不是生产色板；颜色不得替代阶段标题和结构）：
- 问题定义：标题 `rgb(85,155,210)`，背景 `rgb(244,249,255)`
- 特征工程：标题 `rgb(75,162,125)`，背景 `rgb(242,251,244)`
- 模型构建：标题 `rgb(212,158,75)`，背景 `rgb(255,250,240)`
- 评估验证：标题 `rgb(142,115,182)`，背景 `rgb(249,244,255)`
- 结论建议：标题 `rgb(102,132,112)`，背景 `rgb(246,249,246)`

**架构要点**：
1. 每个 Stage 是一个大圆角色块（`draw=none` 无边框），内含白色卡片
2. 卡片顶部有 0.15cm 彩色装饰条
3. Stage 3 用并行三分支 + Σ 汇聚节点，展示多模型对比
4. 方法标签用圆角胶囊样式，标签间距 ≥ 2cm
5. 汇聚节点和下方卡片间距 ≥ 0.8cm

---

### 历史示例 5：算法流程图（判断与外围回路语法）

```latex
\begin{figure}[H]
\centering
\begin{tikzpicture}[
    node distance=0.8cm,
    process/.style={fill=blue!10, draw=blue!50, rounded corners=4pt,
        minimum width=3.5cm, minimum height=0.8cm, align=center,
        font=\small, line width=0.6pt},
    decision/.style={fill=orange!12, draw=orange!50, diamond, aspect=2.5,
        minimum width=2cm, align=center, font=\small, line width=0.6pt,
        inner sep=1pt},
    io/.style={fill=gray!8, draw=gray!50, rounded corners=3pt,
        minimum width=3cm, minimum height=0.7cm, align=center, font=\small},
    arrow/.style={-{Stealth[length=5pt]}, line width=0.7pt, color=gray!70},
    yesno/.style={font=\footnotesize, color=gray!60},
]
\node[io] (start) {输入数据 $D$};
\node[process, below=of start] (init) {初始化参数 $\theta_0$};
\node[process, below=of init] (compute) {计算目标函数 $f(\theta)$};
\node[process, below=of compute] (update) {更新参数 $\theta \leftarrow \theta - \alpha\nabla f$};
\node[decision, below=of update] (conv) {收敛?};
\node[io, below=of conv] (output) {输出最优解 $\theta^*$};
\draw[arrow] (start) -- (init);
\draw[arrow] (init) -- (compute);
\draw[arrow] (compute) -- (update);
\draw[arrow] (update) -- (conv);
\draw[arrow] (conv) -- node[yesno, right] {是} (output);
\draw[arrow] (conv.west) -- ++(-1.5,0) node[yesno, above] {否} |- (compute.west);
\end{tikzpicture}
\caption{优化算法流程图}
\label{fig:algorithm-flow}
\end{figure}
```

### 历史示例 6：数据处理 Pipeline（横向相对定位语法）

```latex
\begin{figure}[H]
\centering
\begin{tikzpicture}[
    node distance=0.3cm,
    stage/.style={fill=#1!12, draw=#1!50, rounded corners=5pt,
        minimum width=2.2cm, minimum height=2.2cm, align=center,
        font=\small, line width=0.6pt},
    detail/.style={font=\tiny, color=gray!40, align=center, text width=2cm},
    arrow/.style={-{Stealth[length=6pt]}, line width=1pt, color=gray!50},
]
\node[stage=blue] (raw) {\textbf{原始数据}\\[2pt]\footnotesize 多源采集};
\node[stage=blue, right=1cm of raw] (clean) {\textbf{数据清洗}\\[2pt]\footnotesize 缺失值/异常值};
\node[stage=teal, right=1cm of clean] (feat) {\textbf{特征工程}\\[2pt]\footnotesize 变量构建};
\node[stage=teal, right=1cm of feat] (model) {\textbf{模型训练}\\[2pt]\footnotesize 参数优化};
\node[stage=blue, right=1cm of model] (eval) {\textbf{评估验证}\\[2pt]\footnotesize 交叉验证};
\node[detail, below=0.3cm of raw] {CSV/API/\\数据库};
\node[detail, below=0.3cm of clean] {插值/IQR/\\标准化};
\node[detail, below=0.3cm of feat] {PCA/交互项/\\时序特征};
\node[detail, below=0.3cm of model] {XGBoost/\\DNN/SVM};
\node[detail, below=0.3cm of eval] {RMSE/AUC/\\$R^2$};
\draw[arrow] (raw) -- (clean);
\draw[arrow] (clean) -- (feat);
\draw[arrow] (feat) -- (model);
\draw[arrow] (model) -- (eval);
\draw[arrow, dashed, color=red!40] (eval.north) -- ++(0,0.8) -| (feat.north)
    node[pos=0.25, above, font=\tiny, color=red!50] {特征调优};
\end{tikzpicture}
\caption{数据处理与建模流程}
\label{fig:pipeline}
\end{figure}
```

### 历史示例 7：变量关系路径图（边标签语法）

```latex
\begin{figure}[H]
\centering
\begin{tikzpicture}[
    node distance=2cm and 3cm,
    var/.style={fill=#1!12, draw=#1!50, rounded corners=5pt,
        minimum width=3cm, minimum height=1cm, align=center,
        font=\small, line width=0.7pt},
    arrow/.style={-{Stealth[length=5pt]}, line width=0.8pt},
    coef/.style={font=\footnotesize, fill=white, inner sep=2pt},
]
\node[var=blue] (x) {\textbf{自变量}\\数字化转型};
\node[var=orange, above right=1.5cm and 3.5cm of x] (m) {\textbf{中介变量}\\创新能力};
\node[var=red, below right=1.5cm and 3.5cm of x] (y) {\textbf{因变量}\\企业绩效};
\draw[arrow, color=blue!60] (x) -- node[coef, below] {$c'$ (直接效应)} (y);
\draw[arrow, color=orange!60] (x) -- node[coef, above left] {$a$ (H1)} (m);
\draw[arrow, color=red!60] (m) -- node[coef, above right] {$b$ (H2)} (y);
\node[fill=gray!8, draw=gray!40, rounded corners=3pt,
    minimum width=2.5cm, minimum height=0.7cm, align=center,
    font=\footnotesize, below=1.5cm of y] (ctrl) {控制变量\\企业规模/行业/年份};
\draw[-{Stealth[length=4pt]}, dashed, color=gray!40, line width=0.5pt] (ctrl) -- (y);
\node[font=\footnotesize\itshape, color=gray!50, below=0.3cm of x] {H3: $a \times b$ 中介效应};
\end{tikzpicture}
\caption{理论模型与研究假设}
\label{fig:theoretical-model}
\end{figure}
```

### 历史示例 8：单问题求解流程图（分支与汇聚语法）

```latex
\begin{figure}[H]
\centering
\begin{tikzpicture}[
    node distance=0.7cm and 1.2cm,
    step/.style={fill=#1!10, draw=#1!45, rounded corners=4pt,
        minimum width=3.5cm, minimum height=0.75cm, align=center,
        font=\small, line width=0.5pt},
    substep/.style={fill=gray!6, draw=gray!35, rounded corners=3pt,
        minimum width=2.6cm, minimum height=0.6cm, align=center,
        font=\footnotesize, line width=0.4pt},
    decision/.style={fill=orange!10, draw=orange!45, diamond, aspect=2.8,
        minimum width=1.5cm, align=center, font=\small, line width=0.5pt, inner sep=1pt},
    note/.style={font=\tiny, color=gray!40, text width=3cm, align=left},
    arrow/.style={-{Stealth[length=4pt]}, line width=0.5pt, color=gray!55},
    yesno/.style={font=\tiny, color=gray!50},
    phaselabel/.style={font=\tiny\bfseries, color=#1!50, rounded corners=2pt,
        fill=#1!6, inner sep=2pt},
]
% 阶段一：数据准备
\node[phaselabel=blue] (L1) at (-3.5, 0) {数据准备};
\node[step=blue] (input) at (0, 0) {读取附件数据};
\node[step=blue, below=of input] (eda) {数据探索与可视化};
\node[decision, below=0.8cm of eda] (missing) {有缺失值?};
\node[substep, right=1.5cm of missing] (fill) {插值/删除处理};
\node[step=blue, below=0.8cm of missing] (clean) {清洗后数据集};
\draw[arrow] (input) -- (eda); \draw[arrow] (eda) -- (missing);
\draw[arrow] (missing) -- node[yesno, above] {是} (fill);
\draw[arrow] (fill.south) |- (clean);
\draw[arrow] (missing) -- node[yesno, right] {否} (clean);
% 阶段二：建模（并行两种方法）
\node[phaselabel=teal] (L2) at (-3.5, -4.5) {模型构建};
\node[step=teal, below=0.8cm of clean] (formulate) {建立数学模型};
\node[substep, below left=0.8cm and 0.8cm of formulate] (method1) {方法A：精确求解};
\node[substep, below right=0.8cm and 0.8cm of formulate] (method2) {方法B：启发式};
\draw[arrow] (clean) -- (formulate);
\draw[arrow] (formulate.south) -- ++(0,-0.3) -| (method1.north);
\draw[arrow] (formulate.south) -- ++(0,-0.3) -| (method2.north);
\node[note, right=0.3cm of formulate] {目标函数\\约束条件\\决策变量};
% 阶段三：对比选优
\node[substep, below=0.7cm of method1] (result1) {结果A};
\node[substep, below=0.7cm of method2] (result2) {结果B};
\node[step=orange, below=1.2cm of formulate] at (0, -8.5) (compare) {方法对比与选优};
\draw[arrow] (method1) -- (result1); \draw[arrow] (method2) -- (result2);
\draw[arrow] (result1.south) |- (compare.west);
\draw[arrow] (result2.south) |- (compare.east);
% 阶段四：验证
\node[step=orange, below=0.7cm of compare] (verify) {结果验证与分析};
\node[step=red, below=0.7cm of verify] (sense) {灵敏度/稳健性分析};
\node[step=red, below=0.7cm of sense] (output) {输出最终方案};
\draw[arrow] (compare) -- (verify); \draw[arrow] (verify) -- (sense); \draw[arrow] (sense) -- (output);
\end{tikzpicture}
\caption{问题一求解流程}
\label{fig:solve-flow-q1}
\end{figure}
```

### TikZ 语法速查（参数仅作起点，必须以最终 PDF 反校）

```latex
% 在 tikzpicture 外部定义（放在 preamble 或 figure 环境开头）
\usetikzlibrary{arrows.meta, positioning, shapes.geometric, calc, decorations.pathreplacing, shadows}

% 颜色：先定义本论文的语义令牌；不要按阶段机械 blue/teal/orange/red
% 黑白、单色+强调、少量定性色均可，且须有形状/线型/文字冗余编码

% 节点间距起点（最终按节点真实边界、边标签和栏宽调整）
% 紧凑型：node distance=0.5cm and 0.8cm
% 标准型：node distance=0.8cm and 1.2cm
% 宽松型：node distance=1.2cm and 2cm

% 箭头样式起点（最终按语义和缩放后的有效线宽调整）
% 主流程：-{Stealth[length=5pt]}, line width=0.7pt, color=gray!70
% 数据流：-{Stealth[length=4pt]}, line width=0.5pt, dashed, color=gray!40
% 反馈：-{Stealth[length=4pt]}, line width=0.5pt, dashed, color=red!40
```
