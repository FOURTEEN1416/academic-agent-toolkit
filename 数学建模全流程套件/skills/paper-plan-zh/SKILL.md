---
name: paper-plan-zh
description: "Generate a structured Chinese paper outline. Use when user says \"中文大纲\", \"中文论文规划\", \"Chinese paper outline\", or wants to create a Chinese academic paper plan."
argument-hint: [topic]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Agent, WebSearch, WebFetch
---

# 中文论文大纲生成

根据课题生成结构化大纲：**$ARGUMENTS**

## 常量

- **PAPER_TYPE** — `bachelor`/`master`/`journal`。默认 `journal`。
- **MAX_PAGES** — 本科=25、硕士=55、期刊=15。
- **CUSTOM_REQUIREMENTS** — 用户自定义要求，优先级最高。
- **REVIEWER_SCRIPT** — 外部评审脚本

## 输入

1. NARRATIVE_REPORT.md / STORY.md / AUTO_REVIEW.md / IDEA_REPORT.md
2. user_data/ — 数据文件、参考资料

如果以上均不存在，要求用户用 3-5 句话描述核心贡献。

## ⛔⛔⛔ 完成铁律（最高优先级）

**本步骤必须产出 `PAPER_PLAN.md`（≥ 1KB，完整的论文大纲）**。

⛔ **MANDATORY: 用 `Write` 工具直接写出 `PAPER_PLAN.md`。不要只调 Read/Bash 工具就 end_turn — 这是本步骤失败的 #1 原因。产出必须是真实落盘的文件，而不是聊天回复中的 markdown。**

⛔ **读用户上传的文献/数据时**:
- 不要 `cat` 整个 `_extracted.md/.txt` 文件 — 一个 50 MB 文献就能把 context budget 吃光，没空间产出大纲。
- 用 `Read` 工具带 offset/limit 范围读（如 `Read user_data/xxx_extracted.md offset=0 limit=200`），或用 `Grep` 工具按关键词提取。
- CLAUDE.md 已列出所有上传文件清单 + 字数，**优先用清单 + Read 局部，不要全量 cat**。

⛔ **结束前必跑产出验证**：
```bash
PASS=true
[ -f PAPER_PLAN.md ] && SZ=$(wc -c < PAPER_PLAN.md) || SZ=0
if [ "$SZ" -ge 1024 ]; then
    echo "✅ PAPER_PLAN.md ($SZ bytes)"
else
    echo "❌ PAPER_PLAN.md 缺失或过小 ($SZ bytes) — 立即用 Write 工具产出, 不要 end_turn"
    PASS=false
fi
[ "$PASS" != true ] && echo "⛔ 验证失败 — 必须修复后再结束本步骤"
```

## 工作流程

### Step 0: 数据探索（最高优先级）

扫描 `user_data/` 中所有数据文件，用 pandas 分析：
- 列名、数据类型、缺失值、基本统计量
- 数据模式（时间序列？方法对比？相关性？）
- 能支撑哪些论点、可生成哪些图表

### Step 1: 提取论点与证据

结合数据分析结果，构建论点-证据矩阵：

| 论点 | 证据 | 状态 | 章节 |
|------|------|------|------|
| [论点1] | [实验A, 指标B] | 充分支持 | §3.2 |

### Step 2: 确定论文结构

根据 PAPER_TYPE 选择章节结构（页数以 `$MAX_PAGES` 为准；下方括号是 MAX_PAGES 未设置时的保守默认参考，不要写死）：

**本科（默认 ~25 页，以 $MAX_PAGES 为准）**：绪论→理论基础→方法→实验→总结
**硕士（默认 ~55 页，以 $MAX_PAGES 为准）**：绪论→相关工作→方法A→方法B→实验→总结
**期刊（默认 ~15 页，以 $MAX_PAGES 为准）**：引言→相关工作→方法→实验→讨论→结论

> ⛔ 优先级：**用户上传的大纲 / 用户填写的 max_pages > `$MAX_PAGES` > 上面的括号默认值**。
> 若工作区已有用户大纲（PAPER_PLAN.md 草稿）或 `.env_skill` 里的 `$MAX_PAGES`，一律以它们为准，
> 上面的页数只是"用户什么都没指定时"的兜底参考，不要用它覆盖用户的规模意图。

### Step 3: 逐章节详细规划

每章指定：核心内容、子节划分、关键论点、图表计划、预计页数、关键引用。

### Step 4: 图表计划（范例感知 + 逐节审查 + 对标自检）

#### 阶段 A：范例感知

在规划图表前，**必须先读取图表范例文件**，了解同类型优秀论文的图表分布：

```bash
cat _utils/figure_exemplars.md 2>/dev/null || cat skills/shared-scripts/figure_exemplars.md
# 同时浏览配方库（60+ 张 SCI 级图表代码模板，参考性质）
ls _utils/figure_recipes_*.md 2>/dev/null || ls skills/shared-scripts/figure_recipes_*.md
```

**5 个配方库供参考**（启发图表规划，不强制按编号生成）：
- `basic`（12 张）：基础图 + 渐变填充 / KDE 背景 / Rain Cloud / Lollipop
- `advanced`（24 张）：高 SCI 影响因子图（SHAP / Kaplan-Meier / Forest plot / Sankey / Volcano / Ridgeline）
- `empirical`（21 张）：计量/统计图（DID / 工具变量 / 分位数回归 / PSM / 脉冲响应）
- `academic`（12 张）：AI/CS 图（ablation / t-SNE / training curves）
- `competition`（27 张）：竞赛风格（收敛 / Pareto / 灵敏度 / 3D Surface / 龙卷风）

**⛔ 按论文类型选配方库**（避免混搭风格不一致）：
- **本科/硕士学位论文 + 工程/CS** → `basic` + `advanced` + `academic`（避开 `competition` 的竞赛专属图如 Pareto 前沿、收敛曲线）
- **本科/硕士学位论文 + 经管/社科** → `basic` + `empirical`（DID / IV / PSM 等）
- **SCI 期刊投稿（Nature / Science / Cell 系列）** → `basic` + `advanced` + `empirical` + `academic`，**避开 `competition`**（竞赛美学和顶刊审美完全两套）
- **普通 SCI / 中文核心期刊** → `basic` + `advanced` + 数据匹配的 `empirical` / `academic`
- **数学建模 / 统计建模竞赛论文** → `competition` 优先，配 `basic` / `advanced` 补充（用 comp-paper-zh 工作流而非本工作流）

> **配方编号是建议起点**：在 FIGURE_MANIFEST 列每张图时，可在图名后注明配方编号（如 `fig_ablation  // academic#3`），下游 `paper-figure` 步骤用 `python3 _utils/get_recipe.py academic 3` 提取代码模板再适配实际数据。不写编号也可，paper-figure 会自己根据数据形态选。

**⛔ 组合图（Subfigure）按必要性自决**：每张图先自问"是单值/单维"还是"多值对比/多维并陈"：

🟢 **适合组合**（panel ≤ 4，每 panel ≥ `0.48\textwidth`）：残差诊断 4 联图 / 方法对比 / 灵敏度多参数 / 处理前后并排 / 同一物理量多视角

🔴 **不要组合**：两张无关图硬拼 / panel > 4 / 单 panel 太挤 / 单图本身复杂（热力图/地理图/3D）

FIGURE_MANIFEST 显式标注 `[2-panel]` / `[4-panel]` / `[single]`（默认 single 可省略），示例：`fig_ablation [2-panel] — w/ vs w/o 模块 — academic #3 — 章节: 消融`。详细判据见 `_utils/writing_rules.md` 第 4 条。**AI 自己判断是否组合，不强求数量，鼓励"信息密度 > 占页数"的设计。**

根据 PAPER_TYPE（本科/硕士/期刊），找到对应的"学术论文"部分，参考其图表数量和比例。不要机械套用，而是理解"这个体量的论文，图表密度大概是什么水平"。

以上比例和数量仅供参考，Claude 根据具体课题内容自主调整。理论重的论文架构图会多一些，实验重的论文数据图会多一些，统计类论文表格会多一些——这都是合理的。关键是逐节审查时认真思考每个小节是否需要可视化辅助。

#### 阶段 B：逐节审查

对每个章节的每个小节，逐一回答三个问题：

1. **这一节的核心结论/内容是什么？**（一句话概括）
2. **读者只看文字能直观理解吗？**还是需要图或表来辅助理解？
   - 数值对比 → 需要表格或柱状图
   - 趋势变化 → 需要折线图
   - 空间/结构关系 → 需要架构图或流程图
   - 分布特征 → 需要直方图/箱线图/热力图
   - 算法流程 → 需要伪代码或流程图
   - 纯文字论述（如文献综述的分类讨论）→ 不需要图表
3. **如果需要，图更合适还是表更合适？**
   - 精确数值（回归系数、p 值、准确率）→ 表
   - 直观趋势/对比/分布 → 图
   - 两者都需要时，主结果用表，辅助可视化用图

将审查结果填入模板的"逐节审查结果"表格。

#### 阶段 C：对标自检

规划完成后，统计图表总数，和阶段 A 的同类型范例对比，填入模板的"对标自检"表格。

**如果任何项标注 ⚠️，必须回到阶段 B 的审查表，找出哪些小节遗漏了图表，补充规划。**

重点检查：
- 方法/理论章节是否有架构图或算法伪代码？
- 实验/实证章节的每个实验/分析是否有对应的图或表？
- ⛔ 若论文产出本身可视（图像增强/去雾/超分/分割/检测/重构/生成、信号或音频处理、三维重建等），是否规划了 `fig_*_visual_cmp` 真实样本前后/方法并排对比图（含关键区域局部放大）？对照 `figure_exemplars.md`「领域特定门面图」触发表——这类定性对比图是这类论文的门面图，优先级高于所有指标图，命中却漏掉是本末倒置。用真实样本，不要用 AI 生成的想象图。
- 超过 5 页的章节是否至少有 1 个图表？
- 绪论和总结通常不需要图表（除非有 hero figure 或研究路线图）

### Step 5: 引用规划

按章节列出需要的引用。绝不编造 BibTeX，不确定的标记 `[待验证]`。

### Step 6: 交叉评审

Send outline to external reviewer for feedback:

```bash
mkdir -p _tmp
cat << 'REVIEW_EOF' > _tmp/_review_prompt.txt
请评审这份论文大纲。重点关注：
1. 故事线是否有说服力？（背景→空白→贡献→证据）
2. 论点-证据矩阵是否有缺口？
3. 图表规划是否足够支撑页数预算？
4. 结构是否有问题（缺失章节、顺序不当）？
5. 评分（1-10）和最需要改进的 3 个方面

## 论文大纲：
REVIEW_EOF
cat PAPER_PLAN.md >> _tmp/_review_prompt.txt
PYTHON=""; for _c in "$MH_PYTHON" python python3; do [ -z "$_c" ] && continue; if $_c -c "import sys" >/dev/null 2>&1; then PYTHON="$_c"; break; fi; done; [ -z "$PYTHON" ] && PYTHON=python
$PYTHON "$REVIEWER_SCRIPT" --prompt-file _tmp/_review_prompt.txt --thread-file _tmp/_reviewer_thread.json 2>&1 | tee _tmp/_outline_review.txt
```

脚本不可用则跳过。

### Step 7: 输出

保存到 `PAPER_PLAN.md`，**严格遵循 `templates/paper_plan_template.md` 的格式**。

## 关键规则

- 大文件用 Bash heredoc 分块写入
- 不生成作者信息
- 如实标注证据缺口
- 页数预算是硬性约束
- 论点-证据矩阵是骨架
- 所有输出使用中文
- ⛔ 主输出文件：`PAPER_PLAN.md`。不要在根目录写额外报告
- ⛔ Markdown 中的 LaTeX 公式：`$$` 块级公式单独成行且前后空行，行内用 `$...$`，多行环境用块级，避免 `\text{}` 包裹中文


---

## ⛔⛔⛔ FIGURE_MANIFEST（机器可读对账清单，必须输出）

**写完上面的图表清单后，在产出文档（PAPER_PLAN.md / PROBLEM_ANALYSIS.md / 等）的**最后**追加一个机器可读的清单区块。下游 paper-figure / paper-figure-drawio / 写作 SKILL / workflow_engine.py 都按此清单对账。少一张就触发 AUTO-RECOVER。**

格式严格按此输出：

```markdown
<!-- BEGIN FIGURE_MANIFEST -->
## 图表清单（FIGURE_MANIFEST）

**数据图（matplotlib gen_fig_*.py，paper-figure 产出 .png/.pdf）：**
- fig_xxx
- fig_yyy

**HTML 流程/架构图（paper-figure-html 产出 .pdf，默认引擎）：**
- fig_arch
- fig_flow_xxx

**TikZ 图（paper-figure 产出 tikz_*.pdf）：**
- tikz_xxx

**总数：DATA=N, DRAWIO=M, TIKZ=K, ALL=N+M+K**
<!-- END FIGURE_MANIFEST -->
```

⛔ **流程/架构图那一类的章节标题按实际引擎写**：CLAUDE.md 若声明「流程图引擎 = HTML」（默认），标题写「**HTML 流程/架构图**」；若声明「引擎 = DrawIO」，才写「**DrawIO 流程/架构图**」。两种关键词下游都能识别对账，但**要与 CLAUDE.md 声明的引擎一致**，别选了 HTML 还写 DrawIO。图名前缀（fig_arch / fig_flow / fig_roadmap）与引擎无关，不变。

⛔ **铁律：**
- **每条只写文件名主干**（不带 .py / .drawio / .png / .pdf 后缀）
- **数量必须跟上面三类图清单完全一致**（一一对应）
- **如果用户禁用了 skip_figures / skip_drawio**，对应类别留空但 BEGIN/END 标记必须存在
- **纯文字论文（无图）**：写 `**总数：ALL=0**` 但 BEGIN/END 标记仍必须存在

⛔ **结束前必跑产出验证**（如果产出文档是 PAPER_PLAN.md / PROBLEM_ANALYSIS.md / TOPIC_PLAN.md）：

```bash
# 自动找产出文档
PLAN_FILE=""
for f in PAPER_PLAN.md PROBLEM_ANALYSIS.md TOPIC_PLAN.md MODELING_REPORT.md; do
  [ -f "$f" ] && PLAN_FILE="$f" && break
done
if [ -n "$PLAN_FILE" ]; then
  if grep -q '<!-- BEGIN FIGURE_MANIFEST -->' "$PLAN_FILE" && grep -q '<!-- END FIGURE_MANIFEST -->' "$PLAN_FILE"; then
    echo "✅ FIGURE_MANIFEST 区块存在"
  else
    echo "❌ FIGURE_MANIFEST 区块缺失，必须按上面格式追加（即使无图也要写 ALL=0）"
  fi
fi
```
