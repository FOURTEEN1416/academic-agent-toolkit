---
name: comp-statistics-topic
description: "统计建模大赛选题与数据规划。根据官方主题方向，自拟具体题目、设计研究方案、规划数据来源。Use when user says ”统计建模选题”, ”stats topic”, ”自拟题目”."
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

图表预规划契约（规划方法/配方编号铁律/硬规则/组合图政策/DrawIO-TikZ 路由表/输出模板/FIGURE_MANIFEST 格式）的**唯一真源**在 `_utils/figure_plan_contract.md`（与 `skills/shared-scripts/figure_plan_contract.md` 同源双副本），本技能正文不再复制，按 tag 按需加载：

```bash
CONTRACT=_utils/figure_plan_contract.md
[ -f "$CONTRACT" ] || CONTRACT=../_utils/figure_plan_contract.md
[ -f "$CONTRACT" ] || CONTRACT=skills/_utils/figure_plan_contract.md
[ -f "$CONTRACT" ] || CONTRACT=academic-toolkit/skills/_utils/figure_plan_contract.md
awk '/^<[a-z_]+>$/ {print NR": "$0}' "$CONTRACT"   # tag 目录；行号随改版漂移，以实跑输出为准
```

| tag | 何时读 |
|---|---|
| `<figure_planning_method>` | 开始规划图表（套餐匹配 + 数据形态推导法） |
| `<recipe_number_rule>` | 给每张图写配方编号前 |
| `<hard_rules>` | 规划清单定稿前 |
| `<subfigure_policy>` | 考虑组合图（Subfigure）时 |
| `<drawio_tikz_routing>` | 规划 DrawIO/TikZ 清单时 |
| `<output_format_stats>` | 输出 TOPIC_PLAN.md 图表预规划模板时（含技术路线图链路） |
| `<figure_manifest_format>` | 输出 FIGURE_MANIFEST 前（必读） |

```bash
# 本步必读的两个 tag：
for t in output_format_stats figure_manifest_format; do
  awk -v s="<$t>" -v e="</$t>" '$0==s{f=1} $0==e{f=0} f' "$CONTRACT"
done
```

**本场景（统计建模）场景参数**：技术路线图放**引言章节末尾**；无 GPT Image 场景图（纯数据/统计赛题）；无逐问流程图。

### Step 6: 输出

保存到 `TOPIC_PLAN.md`：选题理由、研究设计、数据规划、统计方法、论文结构、图表预规划。

## ⛔⛔⛔ FIGURE_MANIFEST（机器可读对账清单，必须输出）

**写完上面的「图表预规划」后，在 `TOPIC_PLAN.md` 的最后追加一个机器可读的清单区块。下游 comp-code / paper-figure / paper-figure-drawio / 写作 SKILL / workflow_engine.py 都按此清单对账。少一张就触发 AUTO-RECOVER。**

格式、锚点（`<!-- BEGIN/END FIGURE_MANIFEST -->`）与铁律（文件名主干、`fig_`/`tikz_` 前缀、数量一一对应、skip_figures/skip_drawio 时留空但锚点必须在）**按共享契约 `<figure_manifest_format>` tag 执行**（`_utils/figure_plan_contract.md`）。统计建模场景无 GPT Image 类目，总数格式为 `DATA=N, DRAWIO=M, TIKZ=K, ALL=N+M+K`。

产出结构、存在性和最低完整性由 `finish` 按模板中的 `output_contract` 自动核验；修复返回的具体问题，不复制执行验证脚本。

## 关键规则

- 题目要具体（不能太宽泛）
- 数据要可得（优先有公开数据的题目）
- 方法要规范（假设检验、模型诊断是评审重点）
- 创新点要明确
- 查重风险：不能照搬已有论文
- ⛔ 主输出文件：`TOPIC_PLAN.md`。不要在根目录写额外报告
- ⛔ Markdown 中的 LaTeX 公式：`$$` 块级公式单独成行且前后空行，行内用 `$...$`，多行环境用块级，避免 `\text{}` 包裹中文
