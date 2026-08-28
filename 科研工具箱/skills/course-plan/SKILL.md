---

name: course-plan

description: "课程论文大纲规划。读取用户主题、上传资料，产出大纲、数据分析规划、图表规划，为后续数据分析和正文撰写做准备。Use when starting a course paper workflow."

argument-hint: [paper-topic]

allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, WebSearch, WebFetch, Agent

---



# 课程论文大纲规划



为以下主题规划课程论文：**$ARGUMENTS**



## 常量



- **SUBJECT_DOMAIN** — 学科领域（cs / humanities / economics / engineering）

- **WORD_COUNT_TARGET** — 目标字数（默认 8000）

- **SKIP_FIGURES** — 是否跳过图表生成（true/false，默认 false；从 CLAUDE.md 中的 `skip_figures` 参数读取）

- **CUSTOM_REQUIREMENTS** — 用户自定义要求



## 输入



1. 论文主题（$ARGUMENTS）

2. 用户上传的参考资料（`user_data/`，可选）

3. 用户提供的大纲草稿（如果存在 `OUTLINE.md`）



## ⛔ 数据存在性 Gate（最重要）



**先做这一步**，决定整个规划走"有图表"还是"无图表"分支：



```bash

echo "=== 数据存在性检查 ==="

DATA_FILES=""

for f in user_data/*.csv user_data/*.json user_data/*.xlsx user_data/*.xls user_data/*.tsv user_data/*.txt; do

    [ -f "$f" ] || continue

    # 排除提取文本类（_extracted.txt 是从 PDF 提取的描述文本，不是数据）

    case "$(basename "$f")" in

        *_extracted.txt) continue ;;

    esac

    DATA_FILES="$DATA_FILES $f"

done



# 检查 SKIP_FIGURES 标志（CLAUDE.md 顶部参数区中的 skip_figures: true）

SKIP_FIGURES=$(grep -E '^- skip_figures:\s*[Tt]rue' CLAUDE.md 2>/dev/null | head -1)



echo "数据文件: ${DATA_FILES:-（无）}"

echo "用户跳过图表: ${SKIP_FIGURES:-否}"

```



**两类硬规则：**



1. **如果 `SKIP_FIGURES=true`（用户在前端关闭了图表）**：

   - 强制走「无图表分支」

   - `PAPER_PLAN.md` 中**禁止规划任何 fig_/TABLE_**，只规划文字结构



2. **如果 `SKIP_FIGURES=false`（用户开启图表）**：

   - 走「有图表分支」

   - **有数据 → 按真实数据规划具体图表**

   - **没数据 → 仍然规划完整图表清单**，并明确标注「**基于仿真/示例数据**」（paper-analysis 步骤会按规划生成仿真数据）

   - **绝不许因为 user_data/ 为空就跳过图表规划** — 用户已经明确开启图表，仿真数据是合理选择



**关键原则：** 是否规划图表只看 `skip_figures` 这一个开关，不看是否有数据。没数据就用仿真数据，但图表规划必须照常做。



## 硬约束



1. **本步骤只规划，不写正文。** 正文由 `course-paper` 完成。

2. 必须产出 `OUTLINE.md` 和 `PAPER_PLAN.md`（即使无图表也要有 PAPER_PLAN.md，明确写「无图表」）。

3. 老师上传的要求文档（`user_data/*_extracted.txt`）优先级高于学科默认结构。

4. **图表规划只许基于真实数据**：禁止凭空编造"将绘制某图"。

5. 文献关键词清单要写进 `OUTLINE.md` 末尾。



## ⛔⛔⛔ 完成铁律（最高优先级）



**本步骤必须产出 `OUTLINE.md`（≥ 800 字节，完整的论文大纲）和 `PAPER_PLAN.md`（≥ 1KB，含 FIGURE_MANIFEST）**。



⛔ **MANDATORY: 用 `Write` 工具直接写出 `OUTLINE.md` 和 `PAPER_PLAN.md`。不要只调 Read/Bash 工具就 end_turn — 这是本步骤失败的 #1 原因。产出必须是真实落盘的文件。**



⛔ **读用户上传的文献/数据时**：

- 不要 `cat` 整个 `_extracted.md/.txt` 文件 — 一个大文件就能把 context budget 吃光，没空间产出主文件。

- 用 `Read` 工具带 offset/limit 范围读，或用 `Grep` 工具按关键词提取。

- CLAUDE.md 已列出所有上传文件清单 + 字数，**优先用清单 + Read 局部，不要全量 cat**。



⛔ **结束前必跑 PASS 阻断验证**（只 echo "❌" 不算，必须显式判定）：

```bash

PASS=true

[ -f OUTLINE.md ] && SZ_O=$(wc -c < OUTLINE.md) || SZ_O=0

[ -f PAPER_PLAN.md ] && SZ_P=$(wc -c < PAPER_PLAN.md) || SZ_P=0

if [ "$SZ_O" -ge 800 ]; then

    echo "✅ OUTLINE.md ($SZ_O bytes)"

else

    echo "❌ OUTLINE.md 缺失或过小 ($SZ_O bytes) — 立即用 Write 工具产出, 不要 end_turn"

    PASS=false

fi

if [ "$SZ_P" -ge 1024 ]; then

    echo "✅ PAPER_PLAN.md ($SZ_P bytes)"

else

    echo "❌ PAPER_PLAN.md 缺失或过小 ($SZ_P bytes) — 立即用 Write 工具产出, 不要 end_turn"

    PASS=false

fi

[ "$PASS" != true ] && echo "⛔ 验证未通过 — 必须修复后再结束本步骤"

```





## 工作流程



### Step 1: 输入梳理



```bash

echo "=== 检查用户上传资料 ==="

ls user_data/ 2>/dev/null || echo "无用户上传文件"



# 列出所有提取文本（PDF/DOCX 已被后端提取）

for f in user_data/*_extracted.txt user_data/*.txt; do

    [ -f "$f" ] && { echo "--- $f ---"; head -c 800 "$f"; echo; }

done



# 检测用户上传的格式模板（.docx）

TEMPLATE_DOCX=$(find user_data -maxdepth 1 -name "*.docx" 2>/dev/null | head -1)

if [ -n "$TEMPLATE_DOCX" ]; then

    echo "检测到用户上传的 docx 模板: $TEMPLATE_DOCX"

    echo "（docx-export 步骤会自动提取该模板的字体/字号/页边距并应用到导出 Word）"

    # 同时检查模板对应的提取文本（如 xxx_extracted.txt），用于了解模板的章节结构

    TEMPLATE_TXT="${TEMPLATE_DOCX%.docx}_extracted.txt"

    [ -f "$TEMPLATE_TXT" ] && { echo "模板内容预览:"; head -c 500 "$TEMPLATE_TXT"; echo; }

fi



# 用户上传的图片：复制到 figures/ 供后续撰写直接引用

mkdir -p figures

USER_IMAGES=""

for f in user_data/*.png user_data/*.jpg user_data/*.jpeg; do

    [ -f "$f" ] || continue

    bn=$(basename "$f")

    cp "$f" "figures/$bn"

    echo "复制用户图片到 figures/: $bn"

    USER_IMAGES="$USER_IMAGES figures/$bn"

done

```



提取要点：

- 老师对格式的要求（字体/字号/行距/页边距/字数）

- 老师对章节结构、参考文献数量的要求

- 用户已上传的数据文件清单（决定是否规划图表）

- 用户已上传的图片（已复制到 figures/，可直接在大纲中规划"嵌入这些图"）



### Step 2: 生成大纲（OUTLINE.md）



按学科领域生成大纲（结构借鉴 lunwen-skill chapter-patterns）。



每章必须给出：**预期字数 / 核心论点 3-5 条 / 关键术语 / 是否引图**。



**计算机科学（cs）：**

```

摘要 + 关键词

1. 引言（15%）

2. 相关工作 / 技术综述（20%）

3. 方法 / 系统设计（30%）

4. 实验与分析（25%，仅在有数据时存在；否则改为「案例分析」或「方法对比」）

5. 结论与展望（10%）

参考文献

```



**人文社科（humanities）：**

```

摘要 + 关键词

1. 引言

2. 文献综述

3. 研究方法（思辨型可省略）

4. 分析与讨论（核心章节，思辨型在此展开）

5. 结论

参考文献

```



**经济管理（economics）：**

```

摘要 + 关键词

1. 引言

2. 理论基础与文献综述

3. 研究假设与模型构建

4. 实证分析（有数据则放图表；无数据则改为「案例剖析」）

5. 结论与建议

参考文献

```



**工程技术（engineering）：**

```

摘要 + 关键词

1. 引言

2. 技术方案设计

3. 实现与测试（有数据则放图表）

4. 结果分析与优化

5. 结论

参考文献

```



`OUTLINE.md` 写作要点：

- 标题用 `## 第N章`，子节用 `### N.1`、`### N.2`

- 每章用一个 markdown 子表标注：字数/论点/术语/引图

- 末尾必须有「文献调研关键词」清单

- 末尾必须有「Claims-Evidence Matrix」（每个核心论点对应的证据来源）



**Claims-Evidence Matrix 模板：**

```markdown

## Claims-Evidence Matrix



| Claim（核心论点） | Evidence（证据来源） | Section（落点章节） | Status（待定/已支撑） |

|------------------|--------------------|-------------------|-------------------|

| [本文方法 X 优于 baseline] | fig_main_result（如有数据） / 文献 [1] [2] | 第 4 章 | 待定 |

| [Y 的提升源于 Z 机制] | fig_ablation / 文献 [3] | 第 4.3 节 | 待定 |

```



如果是无数据论文，Evidence 全部用文献支撑（不写 fig_）。



### Step 3: 数据分析与图表规划（PAPER_PLAN.md）



**分支 A — 有图表（SKIP_FIGURES=false，无论是否有数据）：**



如果有真实数据：

```markdown

# 课程论文：数据分析与图表规划



## 数据资产

- user_data/xxx.csv（N 行，K 列）— 字段：[列名 1] / [列名 2] / ...

- user_data/yyy.json — 含字段 [...]

- 用户已上传的图片（已复制到 figures/）：fig_user_*.png（N 张）



## 分析任务（由 paper-analysis 步骤执行，使用真实数据）

1. 描述性统计 → figures/all_results.json 中保存均值/方差等

2. 主要分析（根据论文主题）：相关性/回归/聚类/时序预测...

3. 验证性分析：稳健性/敏感性



## 图表规划（CHECKLIST，paper-figure 步骤按此清单执行）

- [ ] fig_desc_stats — 描述性统计（直方图/箱线图） — 数据来源 figures/all_results.json[describe] — 落点 §4

- [ ] fig_main_result — 主要结果对比 — 数据来源 figures/all_results.json[main] — 落点 §4

- [ ] fig_xxx — ...

- [ ] TABLE_desc — 描述性统计表 — 落点 §4

- [ ] TABLE_main — 主要结果表 — 落点 §4



## 输出文件命名规范

## STEP_MANIFEST 产出声明

本步骤完成后，必须调用 `engine.step_manifest.write_manifest`（或经 bridge/common 等价入口）在工作区根目录写入 `STEP_MANIFEST.json`，至少包含：stepName / backend（含版本）/ config / inputFiles / outputFiles（含 SHA-256）/ commands / dependencies。质量门禁 `step_manifest` 将校验其存在性与完整性；缺失或无效将导致本步骤无法通过（fail）。

建议额外记录：输入材料来源哈希、模板版本。
所有 fig_ 同时输出 PDF 和 PNG（PNG 用于 Word 导出）：

- figures/fig_xxx.pdf

- figures/fig_xxx.png

表格：figures/TABLE_xxx.md（⛔ 课程论文是 Word 输出，表格用 Markdown 三线表 .md，**不是 .tex**）

```



**如果没真实数据但用户开启了图表**（用仿真数据）：

```markdown

# 课程论文：数据分析与图表规划



## 数据资产

**用户未提供数据文件，将使用仿真/示例数据**（paper-analysis 步骤负责生成）。



## 仿真数据规划（paper-analysis 步骤参考）

基于论文主题「[主题]」，构造合理的仿真数据集：

- 数据规模：N=500 samples × K=8 features（视主题调整）

- 字段定义：

  - id (int): 样本编号

  - feature_1 (float): [含义]，分布假设 N(μ=0, σ=1)

  - feature_2 (categorical): [含义]，取值 {A, B, C}

  - target (float): [因变量]，由 feature_1 + 噪声 生成

- 数据生成方式：基于上述分布用 numpy/pandas 模拟

- 保持学术诚信：在论文中明确注明「数据为仿真生成」



## 分析任务（基于仿真数据）

1. 描述性统计

2. 主要分析（根据论文主题）

3. 验证性分析



## 图表规划（CHECKLIST，正常规划，标注基于仿真数据）

- [ ] fig_desc_stats — 描述性统计（仿真数据）— 落点 §4

- [ ] fig_main_result — 主要结果对比（仿真数据）— 落点 §4

- [ ] TABLE_desc — 描述性统计表 — 落点 §4

- [ ] TABLE_main — 主要结果表 — 落点 §4



## 输出文件命名规范

所有 fig_ 同时输出 PDF 和 PNG（PNG 用于 Word 导出）：

- figures/fig_xxx.pdf

- figures/fig_xxx.png

```



**分支 B — 无图表（SKIP_FIGURES=true，用户显式关闭）：**



```markdown

# 课程论文：图表规划



## 数据资产

（无 — 用户未上传数据文件，且未提供图片）



## 分析任务

（无）



## 图表规划

**本论文不规划任何 fig_ 或 TABLE_。**

- 后续 paper-analysis 与 paper-figure 步骤将被跳过

- 正文以叙述、引用文献、概念框架为主

- 如果某章想要"对比表"或"概念矩阵"，使用 Markdown 表格语法直接写在正文中（不算 figures/ 中的产物）



## 撰写注意

- 写作时不许说"如图 X 所示"或"详见 fig_xxx"

- 所有论点用文献引用支撑（[1] [2] 形式）

```



⛔ 写完 PAPER_PLAN.md 后必须自检：



```bash

echo "=== PAPER_PLAN 自检 ==="

SKIP=$(grep -ciE '^\*\*本论文不规划任何' PAPER_PLAN.md)

HAS_FIG=$(grep -cE '^- \[ \] fig_|TABLE_' PAPER_PLAN.md)

SKIP_FIGURES_FLAG=$(grep -ciE '^- skip_figures:\s*[Tt]rue' CLAUDE.md 2>/dev/null)



if [ "$SKIP" -ge 1 ] && [ "$HAS_FIG" -ge 1 ]; then

    echo "❌ 自检失败：标记了'不规划图表'但又列了 fig_/TABLE_，请删除规划项"

    exit 1

fi

if [ "$SKIP_FIGURES_FLAG" -ge 1 ] && [ "$HAS_FIG" -ge 1 ]; then

    echo "❌ 自检失败：用户已禁用图表（skip_figures=true）但 PAPER_PLAN 中列了 fig_，必须改为'无图表分支'"

    exit 1

fi

if [ "$SKIP_FIGURES_FLAG" -eq 0 ] && [ "$HAS_FIG" -eq 0 ] && [ "$SKIP" -eq 0 ]; then

    echo "❌ 自检失败：用户启用了图表但 PAPER_PLAN 中没列任何 fig_，必须规划完整图表清单（无数据时用仿真数据）"

    exit 1

fi

echo "✅ PAPER_PLAN.md 一致性 OK"

```



### Step 4: 文献关键词清单



在 `OUTLINE.md` 末尾追加：

```markdown

## 文献调研关键词

- 核心：[关键词1]、[关键词2]

- 扩展：[关键词3]、[关键词4]

- 时间范围：近 5 年优先

```



## 输出文件



- `OUTLINE.md` — 论文大纲（章节结构 + 字数分配 + 核心论点 + Claims-Evidence Matrix + 文献关键词）

- `PAPER_PLAN.md` — 数据分析与图表规划（有图表 / 无图表两种分支）



## 关键规则



1. **不写正文，只规划。** 正文交给 course-paper。

2. **是否规划图表只看 `skip_figures` 开关：**

   - 用户开启图表（默认）→ 必须规划完整图表清单

     - 有数据 → 用真实数据规划

     - 没数据 → **用仿真数据规划，不允许跳过图表**

   - 用户关闭图表 → 走「无图表分支」

3. **Claims-Evidence Matrix 必须存在**，是后续撰写质量的基准。

4. **PAPER_PLAN.md 一致性自检** 必须通过。

5. **用户上传图片自动复制到 figures/**，可在大纲中规划"§3.1 引用 fig_user_xxx.png"。

6. **学术诚信**：使用仿真数据时必须在 PAPER_PLAN 和后续论文正文中明确注明。

## 📊 图表配方库引导（规划图表前必读）



⛐ **AI 在 FIGURE_MANIFEST 列任何图之前，先读 SCI 图表配方库**——避免从零写代码、保证风格统一：



```bash

# 1. 图表分布参考（哪些图适合课程论文/课程报告，按学科分类）

cat _utils/figure_exemplars.md 2>/dev/null | head -200 \

  || cat skills/shared-scripts/figure_exemplars.md | head -200



# 2. 调色板和样式规范（颜色/字号/边距）

cat _utils/figure_style_guide.md 2>/dev/null | head -150 \

  || cat skills/shared-scripts/figure_style_guide.md | head -150



# 3. 配方库索引（5 个库共 60+ 张 SCI 级图表代码模板）

ls _utils/figure_recipes_*.md 2>/dev/null \

  || ls skills/shared-scripts/figure_recipes_*.md

```



**为每张要规划的图选择配方编号**（paper-figure 步骤会用 `python3 _utils/get_recipe.py <library> <id>` 提取代码）：

- `basic` (12 张)：基础图（柱状/散点/折线 + 渐变填充/KDE 背景）

- `advanced` (17 张)：高 SCI 影响因子图（Lollipop / SHAP / Kaplan-Meier / Forest plot）

- `empirical` (16 张)：计量/统计图（DID / 分位数回归 / 工具变量）— 经济管理类课程优先

- `academic` (12 张)：AI/CS 图（ablation / t-SNE / training curves）— 计算机/工程类课程优先



⛐ **FIGURE_MANIFEST 列每张图时，建议在图名后注明配方编号**（如 `fig_q1_did  // empirical#8`），

方便 paper-figure 步骤直接定位配方代码。



**⛔ 组合图（Subfigure）按必要性自决**：每张图先自问"单值/单维"还是"多值对比/多维并陈"：



🟢 **适合组合**（panel ≤ 4，每 panel ≥ `0.48\textwidth`）：残差诊断 4 联图 / 方法对比 / 灵敏度多参数 / 处理前后并排 / 同一物理量多视角

🔴 **不要组合**：两张无关图硬拼 / panel > 4 / 单 panel 太挤 / 单图本身复杂（热力图/地理图/3D）



FIGURE_MANIFEST 标注 `[2-panel]` / `[4-panel]` / `[single]`（默认 single 可省），示例：`fig_ablation [2-panel] — w/ vs w/o 模块 — academic #3 — 章节: 消融`。详细判据见 `_utils/writing_rules.md` 第 4 条。**AI 自决，不强求数量，鼓励"信息密度 > 占页数"的设计。**



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



**DrawIO 流程/架构图（paper-figure-drawio 产出 .drawio + .png/.pdf）：**

- fig_arch

- fig_flow_xxx



**TikZ 图（paper-figure 产出 tikz_*.pdf）：**

- tikz_xxx



**总数：DATA=N, DRAWIO=M, TIKZ=K, ALL=N+M+K**

<!-- END FIGURE_MANIFEST -->

```



⛔ **铁律：**

- **每条只写文件名主干**（不带 .py / .drawio / .png / .pdf 后缀）

- **⛔⛔ 图名必须以 `fig_` 或 `tikz_` 前缀开头**（问题「规划了图却没生成」的根因）：数据图/流程图/架构图一律 `fig_xxx`，TikZ 几何图一律 `tikz_xxx`。**严禁用 `image2`、`图2`、`chart1`、`示意图` 这类没有前缀的名字**——下游对账脚本按 `fig_`/`tikz_` 前缀在 manifest 章节里抓图名，不带前缀的会被直接漏掉，导致该图静默不生成。图名用小写英文+下划线，见名知意（如 `fig_turbidity_trend`、`fig_flow_q1`）。

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

    # ⛔ 校验 manifest 里的图名前缀：抓 BEGIN..END 之间的列表项，凡不以 fig_/tikz_ 开头的报警

    START=$(grep -n '<!-- BEGIN FIGURE_MANIFEST -->' "$PLAN_FILE" | head -1 | cut -d: -f1)

    END=$(grep -n '<!-- END FIGURE_MANIFEST -->' "$PLAN_FILE" | head -1 | cut -d: -f1)

    BAD=$(sed -n "${START},${END}p" "$PLAN_FILE" | grep -E '^[[:space:]]*-[[:space:]]+' | grep -vE '^[[:space:]]*-[[:space:]]+(fig_|tikz_)' | sed -E 's/^[[:space:]]*-[[:space:]]*//')

    if [ -n "$BAD" ]; then

      echo "❌ 以下图名缺少 fig_/tikz_ 前缀，会被下游对账漏掉、导致图不生成，必须改名："

      echo "$BAD" | sed 's/^/    · /'

    else

      echo "✅ 所有图名前缀合规（fig_/tikz_）"

    fi

  else

    echo "❌ FIGURE_MANIFEST 区块缺失，必须按上面格式追加（即使无图也要写 ALL=0）"

  fi

fi

```

