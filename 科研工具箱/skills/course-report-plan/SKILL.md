---

name: course-report-plan

description: "课程报告大纲规划。读取项目源码与上传资料，提取项目事实，产出大纲与数据/图表/架构图规划。Use when starting a course report workflow."

argument-hint: [project-topic]

allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, WebSearch, WebFetch, Agent

---



# 课程报告大纲规划



为以下项目规划课程报告：**$ARGUMENTS**



## 常量



- **SUBJECT_DOMAIN** — 学科领域（cs / humanities / economics / engineering）

- **WORD_COUNT_TARGET** — 目标字数（默认 10000）

- **SKIP_FIGURES** — 是否跳过数据图表（默认 false）

- **SKIP_DRAWIO** — 是否跳过架构图/流程图（默认 false）

- **CUSTOM_REQUIREMENTS** — 用户自定义要求



## 输入



1. 项目主题（$ARGUMENTS）

2. 用户上传的项目源码（`user_data/` 中的代码文件，可选）

3. 用户上传的要求文档（`user_data/*_extracted.txt`，可选）

4. 用户上传的数据文件（`user_data/*.csv|json|xlsx`，可选）



## ⛔ 数据/源码存在性 Gate



```bash

echo "=== 输入资产清单 ==="



# 1. 源码（决定项目事实底稿是否能成立）

SOURCE_FILES=$(find user_data -type f \( -name "*.py" -o -name "*.js" -o -name "*.ts" -o -name "*.java" -o -name "*.cpp" -o -name "*.c" -o -name "*.go" -o -name "*.rs" -o -name "*.php" -o -name "*.rb" -o -name "*.cs" \) 2>/dev/null | wc -l)

echo "源码文件数: $SOURCE_FILES"



# 2. 数据文件（决定数据图表是否规划）

DATA_FILES=""

for f in user_data/*.csv user_data/*.json user_data/*.xlsx user_data/*.xls; do

    [ -f "$f" ] && DATA_FILES="$DATA_FILES $f"

done

echo "数据文件: ${DATA_FILES:-（无）}"



# 3. 用户上传的图片

USER_IMAGES=""

mkdir -p figures

for f in user_data/*.png user_data/*.jpg user_data/*.jpeg; do

    [ -f "$f" ] || continue

    bn=$(basename "$f")

    cp "$f" "figures/$bn"

    USER_IMAGES="$USER_IMAGES figures/$bn"

done

echo "用户图片已复制到 figures/: ${USER_IMAGES:-（无）}"



# 4. 用户上传的格式模板（.docx）

TEMPLATE_DOCX=$(find user_data -maxdepth 1 -name "*.docx" 2>/dev/null | head -1)

if [ -n "$TEMPLATE_DOCX" ]; then

    echo "检测到用户上传的 docx 模板: $TEMPLATE_DOCX"

    echo "（docx-export 步骤会自动提取该模板格式并应用到导出 Word）"

fi



# 5. 用户标志

SKIP_FIGURES=$(grep -E '^- skip_figures:\s*[Tt]rue' CLAUDE.md 2>/dev/null | head -1)

SKIP_DRAWIO=$(grep -E '^- skip_drawio:\s*[Tt]rue' CLAUDE.md 2>/dev/null | head -1)

echo "跳过数据图表: ${SKIP_FIGURES:-否}"

echo "跳过架构图: ${SKIP_DRAWIO:-否}"

```



**硬规则：**

- `skip_figures=true` → PAPER_PLAN.md 不许列任何 `fig_<数据图>` 和 `TABLE_`

- `skip_figures=false` 且**无数据** → 仍然规划图表，标注「使用仿真数据」（paper-analysis 会生成）

- `skip_drawio=true` → 不许列任何架构/流程图（`fig_arch / fig_er / fig_flow_*`）

- 无源码 → PROJECT_FACTS.md 必须明确写「无源码」，不许编造模块



## 硬约束（借鉴 lunwen-skill fact_extractor）



1. 必须产出 `PROJECT_FACTS.md` / `OUTLINE.md` / `PAPER_PLAN.md` 三个文件。

2. 项目事实只能来源于真实代码或用户主题描述，**禁止编造功能模块**。

3. 大纲中"系统实现"必须是最长章节（30-40%）。

4. 图表规划与可用资源严格匹配（无源码无项目 → 不规划架构图；无数据 → 不规划数据图）。

5. **本步骤只规划，不写正文。**



## ⛔⛔⛔ 完成铁律（最高优先级）



**本步骤必须产出 `OUTLINE.md`（≥ 800 字节，完整的报告大纲）+ `PROJECT_FACTS.md`（项目事实摘要）**。



⛔ **结束前必跑产出验证**：

```bash

PASS=true

[ -f OUTLINE.md ] && SZ=$(wc -c < OUTLINE.md) || SZ=0

[ "$SZ" -ge 800 ] && echo "✅ OUTLINE.md ($SZ)" || { echo "❌ OUTLINE.md 缺失或过小"; PASS=false; }

[ -f PROJECT_FACTS.md ] && PSZ=$(wc -c < PROJECT_FACTS.md) || PSZ=0

[ "$PSZ" -ge 300 ] && echo "✅ PROJECT_FACTS.md ($PSZ)" || { echo "❌ PROJECT_FACTS.md 缺失"; PASS=false; }

[ "$PASS" != true ] && echo "⛔ 产出验证失败 — 必须补全后重新跑验证, 不要结束本步骤"

```



## 工作流程



### Step 1: 检查输入



（已在数据存在性 Gate 中完成）



### Step 2: 提取项目事实（PROJECT_FACTS.md）



**有源码时（必做）**：扫描代码结构，写入 `PROJECT_FACTS.md`：



```markdown

# 项目事实底稿（不许编造，只许据实记录）



## 1. 项目基本信息

- 项目名称：（从 README/package.json/setup.py 提取）

- 编程语言：

- 框架/库：（从依赖文件提取）

- 项目类型：



## 2. 技术栈

（按文件提取）



## 3. 模块结构

（列出主要目录及其职责，每个目录一行）



## 4. 数据库设计

（如有数据库，列出主要表和字段，无则写「无数据库」）



## 5. 核心业务逻辑

（每个关键模块 100-200 字，必须基于真实代码）



## 6. API/接口设计

（如有 API 列出路由与参数，无则写「无 API」）



## 7. 已实现功能清单

（基于代码实际实现，不许写"具有良好的扩展性"等空话）

- 功能 A（位置：xxx.py:LineN）

- 功能 B（位置：yyy.py:LineN）



## 8. 测试覆盖

（如有 tests/ 目录列出测试文件，无则写「无测试」）

```



**无源码时**：在 `PROJECT_FACTS.md` 顶部明确标注：

```markdown

# 项目事实底稿



⚠ 用户未上传项目源码，本报告基于主题描述撰写。



## 项目设想（基于主题描述）

- 项目名称：[从主题推断]

- 项目类型：[从主题推断]

- 技术栈设想：[基于主题选择典型栈，并说明为推测]

- 模块设想：[列出 3-5 个核心模块]



## 写作策略

- 撰写时使用"本系统拟采用..."、"建议..."等推测性措辞

- 不得给出具体函数名、行号

- 代码片段标注为「示例代码」

```



### Step 3: 生成大纲（OUTLINE.md）



按项目类型选大纲。每章必须给出 **预期字数 / 关键术语 / 是否需要图**。



**默认结构（项目实践类）：**



```markdown

# [项目名称] 课程报告



## 摘要（200-300 字）



## 第一章 项目概述（10%）

### 1.1 项目背景

### 1.2 项目目标

### 1.3 开发环境与工具



## 第二章 需求分析（15%）

### 2.1 功能需求

### 2.2 非功能需求

### 2.3 用例分析



## 第三章 系统设计（20%）

### 3.1 总体架构（如不跳过架构图，含 fig_arch；否则用文字描述）

### 3.2 模块设计

### 3.3 数据库设计（含 fig_er，仅在有数据库时）

### 3.4 接口设计



## 第四章 系统实现（35%，最长章节）

### 4.1 [模块A] 实现

### 4.2 [模块B] 实现

### 4.3 [模块C] 实现

…（基于 PROJECT_FACTS 的真实模块清单展开）



## 第五章 测试与结果分析（10%）

### 5.1 测试环境

### 5.2 功能测试用例（Markdown 表格）

### 5.3 性能/数据结果（仅在有数据时放图表）



## 第六章 总结与展望（10%）



## 参考文献（5-15 篇）

```



⛔ **如果无源码**，调整大纲：

- 第三章合并为「方案设计」

- 第四章改为「关键技术分析」（不写实现细节）

- 第五章简化或删除



末尾追加 **Claims-Evidence Matrix**：



```markdown

## Claims-Evidence Matrix



| Claim | Evidence | Section | Status |

|-------|----------|---------|--------|

| 系统实现了功能 A | PROJECT_FACTS §7 + 代码 xxx.py | §4.1 | 已支撑 |

| 系统在性能 X 上达到 Y | RESULTS.md（如有数据） / 文献 [N] | §5.3 | 待定 |

```



### Step 4: 数据/图表/架构图规划（PAPER_PLAN.md）



按多种组合分支规划：



**(A) 有源码 + 有数据 + 不跳架构图：** 全量规划

```markdown

# 课程报告：图表与数据规划



## 架构图（drawio）规划

- [ ] fig_arch — 系统总体架构 → §3.1

- [ ] fig_er — 数据库 E-R 图（如有数据库） → §3.3

- [ ] fig_flow_<module> — 各核心模块流程 → §4.x



## 数据分析图表规划

- [ ] fig_desc — 数据描述性统计 → §5.3

- [ ] fig_perf — 性能/精度对比 → §5.3

- [ ] TABLE_test — 测试用例表 → §5.2



## 输出文件命名规范

## STEP_MANIFEST 产出声明

本步骤完成后，必须调用 `engine.step_manifest.write_manifest`（或经 bridge/common 等价入口）在工作区根目录写入 `STEP_MANIFEST.json`，至少包含：stepName / backend（含版本）/ config / inputFiles / outputFiles（含 SHA-256）/ commands / dependencies。质量门禁 `step_manifest` 将校验其存在性与完整性；缺失或无效将导致本步骤无法通过（fail）。

建议额外记录：输入材料来源哈希、模板版本。
- 数据图：figures/fig_*.png（Word 模式只用 PNG，DPI 350）

- 架构图：figures/fig_*.drawio + figures/fig_*.png（Word 模式不输出 PDF）

- 表格：figures/TABLE_*.md（⛔ 课程报告是 Word 输出，表格用 Markdown 三线表 .md，**不是 .tex**）

```



**(B) 有源码 + 无数据 + 用户开启图表 + 不跳架构图：** 架构图 + 仿真数据图表

```markdown

## 架构图（drawio）规划

- [ ] fig_arch / fig_flow_* / ...



## 数据分析图表规划

**用户未提供数据，将使用仿真/示例数据**（paper-analysis 步骤生成）。

基于项目主题构造合理仿真测试数据：

- 数据规模：N=200 测试样本

- 字段：input/expected/actual/latency_ms

- [ ] fig_perf — 性能对比（仿真）→ §5.3

- [ ] fig_latency — 延迟分布（仿真）→ §5.3

- [ ] TABLE_test — 测试用例表 → §5.2

```



**(C) 跳过架构图 (skip_drawio=true)：**

```markdown

## 架构图（drawio）规划

（用户已禁用 — paper-figure-drawio 将被跳过）



## 数据分析图表规划

（按是否开启图表 + 是否有数据分支，规则同 A/B）

```



**(D) 用户关闭图表 (skip_figures=true)：**

```markdown

**本报告不规划任何 fig_ 或 TABLE_。**

所有论点用文献支撑，撰写时不得说「如图 X 所示」。

```



### Step 5: 自检



```bash

echo "=== PAPER_PLAN 自检 ==="

HAS_DATA_FIG=$(grep -cE '^- \[ \] fig_(desc|perf|main|trend|box|bar|hist|scatter|heatmap|roc|latency)|^- \[ \] TABLE_' PAPER_PLAN.md)

HAS_DRAWIO=$(grep -cE '^- \[ \] fig_(arch|er|flow|module)' PAPER_PLAN.md)

SKIP_FIGURES_FLAG=$(grep -ciE '^- skip_figures:\s*[Tt]rue' CLAUDE.md 2>/dev/null)

SKIP_DRAWIO_FLAG=$(grep -ciE '^- skip_drawio:\s*[Tt]rue' CLAUDE.md 2>/dev/null)



if [ "$SKIP_FIGURES_FLAG" -ge 1 ] && [ "$HAS_DATA_FIG" -ge 1 ]; then

    echo "❌ 自检失败：用户已禁用图表（skip_figures=true）但 PAPER_PLAN 列了数据图"

    exit 1

fi

if [ "$SKIP_DRAWIO_FLAG" -ge 1 ] && [ "$HAS_DRAWIO" -ge 1 ]; then

    echo "❌ 自检失败：用户已禁用架构图（skip_drawio=true）但 PAPER_PLAN 列了 fig_arch/fig_flow_*"

    exit 1

fi

if [ "$SKIP_FIGURES_FLAG" -eq 0 ] && [ "$HAS_DATA_FIG" -eq 0 ]; then

    echo "⚠ 警告：用户启用了图表但 PAPER_PLAN 中没列任何数据图，请补全（无数据时用仿真数据）"

fi

echo "✅ PAPER_PLAN.md 自检 OK"

```



### Step 6: 文献关键词



在 `OUTLINE.md` 末尾追加：

```markdown

## 文献调研关键词

- 核心：[项目领域关键词]

- 扩展：[相关技术关键词]

- 时间范围：近 5 年优先

```



## 输出文件



- `PROJECT_FACTS.md` — 项目事实底稿（有源码必有；无源码注明）

- `OUTLINE.md` — 报告大纲 + Claims-Evidence Matrix + 文献关键词

- `PAPER_PLAN.md` — 数据/图表/架构图规划（按四种分支）



## 关键规则



1. **只规划，不写正文。**

2. **是否规划图表只看 `skip_figures` / `skip_drawio` 开关：**

   - 用户开启图表 → 规划数据图（有数据用真实，没数据用仿真）

   - 用户开启架构图 → 规划 fig_arch/fig_er/fig_flow_*

   - 关闭对应开关时才不规划

3. **无源码不许编造功能**，PROJECT_FACTS.md 必须诚实说明「无源码」。

4. **Claims-Evidence Matrix 必须存在。**

5. **PAPER_PLAN.md 自检必须通过。**

6. **学术诚信**：仿真数据必须在文档中明确注明。





---



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



FIGURE_MANIFEST 标注 `[2-panel]` / `[4-panel]` / `[single]`（默认 single 可省），示例：`fig_perf [2-panel] — 基线 vs 本方案性能对比 — competition #4 — 章节: 性能评估`。详细判据见 `_utils/writing_rules.md` 第 4 条。**AI 自决，不强求数量，鼓励"信息密度 > 占页数"的设计。**



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

