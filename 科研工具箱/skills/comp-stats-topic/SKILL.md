---
name: comp-stats-topic
description: "统计建模大赛选题与数据规划。根据官方主题方向，自拟具体题目、设计研究方案、规划数据来源。Use when user says \"统计建模选题\", \"stats topic\", \"自拟题目\"."
argument-hint: [official-theme-direction]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, WebSearch, WebFetch, Agent
---

# 统计建模大赛：选题与数据规划

根据官方主题方向进行选题和研究设计：**$ARGUMENTS**

## 背景

统计建模大赛与数学建模竞赛不同：没有固定赛题，需自拟题目、自找数据，侧重统计方法规范性。

## 工作流程

### Step 1: 主题解读与选题

搜索相关热点和公开数据，提出 3-5 个候选题目，每个包含：研究问题、数据来源、统计方法、创新点、可行性。

### Step 2: 数据源规划

公开数据源：国家统计局、中国知网、Wind、CSMAR、UCI、Kaggle、世界银行、WHO。
优先使用 `user_data/` 中已有数据。

### Step 3: 研究设计

研究问题（2-3 个子问题）、研究设计（按题目类型调整）、论文结构规划。

**根据题目类型选择研究设计框架**：

- **因果推断类**（DID/RDD/IV/政策评估/影响因素）：研究假设（H1/H2/H3）→ 变量定义（因变量/自变量/控制变量）→ 统计方法（描述性统计→回归分析→稳健性检验→异质性分析）
- **预测类**（时序预测/需求预测/趋势预测）：预测目标定义 → 特征变量选择 → 模型候选列表（≥3 个模型）→ 评价指标（MAE/RMSE/MAPE/R²）→ 训练/验证/测试划分策略
- **分类/聚类类**（用户画像/异常检测/模式识别）：分类/聚类目标定义 → 特征工程方案 → 模型候选列表 → 评价指标（Accuracy/F1/AUC/Silhouette）→ 交叉验证策略
- **综合评价类**（效率评价/质量排名/指标体系）：评价对象与目标 → 指标体系层次结构 → 权重确定方法（AHP/熵权法/组合赋权）→ 综合评价模型（TOPSIS/灰色关联/DEA）

### Step 4: 数据来源建议

列出推荐的数据获取方式（网站名+具体数据集名），不写代码 — 代码由 comp-code 负责。

### Step 5: 图表预规划

在输出前，**读取图表范例文件**了解统计建模获奖论文的图表分布：

```bash
# 1. 读图表范例和套餐（了解各方法类型推荐的图表组合）
cat _utils/figure_exemplars.md 2>/dev/null || cat skills/shared-scripts/figure_exemplars.md
# 2. 读图表选择指南（了解每种图表的适用场景和数据特征匹配）
cat _utils/figure_style_guide.md 2>/dev/null || cat skills/shared-scripts/figure_style_guide.md
```

找到"统计建模大赛"部分的图表套餐，结合 figure_style_guide 的决策表，根据本选题的研究方法自主规划。

**⛔ MANDATORY: 在 TOPIC_PLAN.md 中输出结构化的图表预规划清单。** 后续 `comp-code` 和 `paper-figure` 都会读这个清单逐项生成和验证。

**图表规划方法（按分析步骤推导，不要套固定模板）：**

先读 `figure_exemplars.md` 中的"按研究方法的图表套餐"部分：
- 如果本选题的方法匹配某个套餐（A-F），以该套餐的必选项为基础，再根据具体选题增减
- 如果不匹配任何套餐，用下面的"数据形态推导法"

再读 `figure_style_guide.md` 的 "By data shape" 决策表，对每个分析步骤做推导：

| 你的分析步骤输出 | 对应的数据形态 | 推荐图表 |
|----------------|--------------|---------|
| 多个变量的时间趋势 | 时间×值 | 折线图 basic #3 |
| 变量间相关系数矩阵 | N×N 矩阵 | 聚类热力图 advanced #14 |
| 多模型在多指标上的数值 | 方法×指标矩阵 | 分组柱状图 basic #1 或 方法对比热力图 advanced #16 |
| 系数±标准误列表 | 系数+CI | 森林图 empirical #1 |
| 正负方向的效应值 | 正负差值 | 发散柱状图 advanced #20 |
| 多组的分布形态 | 多组连续值 | Ridgeline advanced #23 或 Grouped Violin advanced #24 |
| 地理空间数据 | 地理×值 | 地图热力图 competition #7 |
| 排名数据 | 名称×单一数值 | 棒棒糖图 advanced #1 |
| 模块增量贡献 | 步骤×增量 | Waterfall advanced #6 |

**⛔ 每张图必须写明配方编号和选择理由**，格式：
`fig_xxx — 发散柱状图 (advanced #20) — 效应分解有正有负，发散柱状图能直观展示方向 — 章节: 实证结果`

**⛔ 配方编号是必填项！** 格式为 `(类别 #编号)`，如 `(advanced #1)`、`(basic #3)`、`(empirical #1)`、`(competition #7)`。系统会根据配方编号自动注入对应的代码模板到 Claude 的 prompt 中。如果不写配方编号，Claude 将无法获得配方代码，只能从零写图表脚本，质量无法保证。如果图表类型不在配方库中，写 `(custom)` 标注。

**硬规则：**
- 同一种图表类型不超过 3 次
- 每张图必须指定具体类型（不能写"分布图"，要写"Ridgeline Plot"或"核密度图"或"箱线图"）
- 至少 1 张 DrawIO 技术路线图（参考 `drawio_rules.md` 模板 A 三栏布局）
- 如果涉及空间数据，必须有空间分布地图
- 如果涉及模型对比（≥3个模型），至少用 2 种不同的对比图表类型

格式必须如下：

```markdown
## 图表预规划

### PDF 图表清单（comp-code 负责生成）
- fig_xxx — [具体图表类型] ([类别 #编号]) — [展示什么数据/传达什么信息] — 章节: [目标章节]
- 示例: fig_coef — 森林图 (empirical #1) — 回归系数及置信区间 — 章节: 实证结果
- 示例: fig_rank — 棒棒糖图 (advanced #1) — 方法排名对比 — 章节: 模型对比
- ...（根据实际选题和研究方法自主规划，每张图必须带配方编号）

### LaTeX 表格清单（comp-code 负责生成）
- TABLE_xxx — [表格描述] — 章节: [目标章节]
- ...

### DrawIO 架构图清单（流程与架构图绘制步骤负责生成）
- DrawIO-1: 技术路线图 → fig_roadmap.drawio → 引言章节末尾 [必须]
- DrawIO-N: [其他按需] → [文件名] → [章节位置]

### TikZ 架构图清单（流程与架构图绘制步骤负责生成，需要精确连线或公式的图）
- tikz_xxx — [变量关系图/算法流程图等] — 章节: [目标章节] [按需]

### 图表多样性检查
[列出每种图表类型的使用次数，确认无重复超过 3 次]

总计: ~X PDF 图 + ~Y 表格 + Z DrawIO 图 + W TikZ 图
```

**每个图表必须有：编号、文件名、具体类型、配方编号（如 `advanced #1`）、描述、目标章节。** 这是后续所有步骤的合同。配方编号缺失会导致系统无法自动注入配方代码。

**⛔ 组合图（Subfigure）按必要性自决**：每张图先自问"是单值/单维"还是"多值对比/多维并陈"：

🟢 **适合组合**（panel ≤ 4，每 panel ≥ `0.48\textwidth`）：残差诊断 4 联图 / 方法对比 / 灵敏度多参数 / 处理前后并排 / 同一物理量多视角

🔴 **不要组合**：两张无关图硬拼 / panel > 4 / 单 panel 太挤 / 单图本身复杂（热力图/地理图/3D）

FIGURE_MANIFEST 显式标注 `[2-panel]` / `[4-panel]` / `[single]`（默认 single 可省略），示例：`fig_q2_residual_diag [4-panel] — 残差诊断 — basic #5 — 章节: 模型验证`。详细判据见 `_utils/writing_rules.md` 第 4 条。**AI 自己判断是否组合，不强求数量，鼓励"信息密度 > 占页数"的设计。**

#### DrawIO / TikZ 架构图预规划

**技术路线图用 DrawIO 生成**（参考 `drawio_rules.md` 模板 A 三栏布局），其他需要精确连线或公式的图用 TikZ。

**位置一：引言章节末尾 — DrawIO 技术路线图（必须）**
- 展示整个研究的逻辑链路（按题目类型调整）：
  - 因果推断类：问题提出→文献梳理→假设建立→数据收集→实证分析→稳健性检验→结论
  - 预测类：问题提出→文献梳理→数据采集→特征工程→模型构建→模型对比→预测应用→结论
  - 分类/聚类类：问题提出→文献梳理→数据采集→特征工程→模型训练→结果评估→模型解释→结论
  - 综合评价类：问题提出→文献梳理→指标构建→权重确定→综合评价→结果分析→对策建议→结论
- 让评审一眼看清研究的整体设计
- 三栏布局：左栏阶段标签 + 中栏虚线框内容 + 右栏研究方法

**位置二：数据与方法章节 — TikZ 分析框架图（可选，需要精确连线时用 TikZ）**
- 展示变量关系和分析路径：自变量→中介变量→因变量的路径，标注假设 H1/H2/H3
- 如果有 DID/RDD 等因果推断设计，画出识别策略示意图

### Step 6: 输出

保存到 `TOPIC_PLAN.md`：选题理由、研究设计、数据规划、统计方法、论文结构、图表预规划。

## ⛔⛔⛔ FIGURE_MANIFEST（机器可读对账清单，必须输出）

**写完上面的「图表预规划」后，在 `TOPIC_PLAN.md` 的最后追加一个机器可读的清单区块。下游 comp-code / paper-figure / paper-figure-drawio / 写作 SKILL / workflow_engine.py 都按此清单对账。少一张就触发 AUTO-RECOVER。**

**格式严格按此输出（不要漏 `<!-- BEGIN/END FIGURE_MANIFEST -->` 锚点）：**

```markdown
<!-- BEGIN FIGURE_MANIFEST -->
## 图表清单（FIGURE_MANIFEST）

**数据图（matplotlib gen_fig_*.py，paper-figure 产出 .png/.pdf）：**
- fig_xxx
- fig_yyy

**DrawIO 流程/架构图（paper-figure-drawio 产出 .drawio + .png/.pdf）：**
- fig_roadmap

**TikZ 图（paper-figure 产出 tikz_*.pdf）：**
- tikz_xxx

**总数：DATA=N, DRAWIO=M, TIKZ=K, ALL=N+M+K**
<!-- END FIGURE_MANIFEST -->
```

⛔ **铁律：**
- **每条只写文件名主干**（不带 `.py` / `.drawio` / `.png` / `.pdf` 后缀）
- **数量必须跟上面「图表预规划」清单完全一致**（一一对应）
- **如果用户禁用了 skip_figures / skip_drawio**，对应类别留空但 BEGIN/END 标记必须存在

⛔ **结束前必跑产出验证**：
```bash
PASS=true
[ -f TOPIC_PLAN.md ] && SZ=$(wc -c < TOPIC_PLAN.md) || SZ=0
if [ "$SZ" -ge 1024 ]; then
    echo "✅ TOPIC_PLAN.md ($SZ bytes)"
else
    echo "❌ TOPIC_PLAN.md 缺失或过小 ($SZ bytes) — 立即用 Write 工具产出, 不要 end_turn"
    PASS=false
fi
if grep -q '<!-- BEGIN FIGURE_MANIFEST -->' TOPIC_PLAN.md 2>/dev/null && grep -q '<!-- END FIGURE_MANIFEST -->' TOPIC_PLAN.md 2>/dev/null; then
    echo "✅ FIGURE_MANIFEST 区块存在"
else
    echo "❌ FIGURE_MANIFEST 区块缺失，必须按上面格式追加（即使无图也要写 ALL=0）"
    PASS=false
fi
[ "$PASS" != true ] && echo "⛔ 验证未通过 — 必须修复后再结束本步骤"
```

## 关键规则

- 题目要具体（不能太宽泛）
- 数据要可得（优先有公开数据的题目）
- 方法要规范（假设检验、模型诊断是评审重点）
- 创新点要明确
- 查重风险：不能照搬已有论文
- ⛔ 主输出文件：`TOPIC_PLAN.md`。不要在根目录写额外报告
- ⛔ Markdown 中的 LaTeX 公式：`$$` 块级公式单独成行且前后空行，行内用 `$...$`，多行环境用块级，避免 `\text{}` 包裹中文
