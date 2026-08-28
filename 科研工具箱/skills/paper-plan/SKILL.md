---
name: paper-plan
description: "Generate a structured paper outline from review conclusions and experiment results. Use when user says \"paper outline\", \"plan the paper\", or wants to create a paper plan before writing."
argument-hint: [topic-or-narrative-doc]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Agent, WebSearch, WebFetch, mcp__codex__codex, mcp__codex__codex-reply
---

# Paper Plan: From Review Conclusions to Paper Outline

Generate a structured outline from: **$ARGUMENTS**

## Constants

- **TARGET_VENUE = `ICLR`** — Override via Additional Parameters. Supported: ICLR, NeurIPS, ICML.
- **MAX_PAGES** — ICLR=9, NeurIPS=9, ICML=8. Override via Additional Parameters.
- **CUSTOM_REQUIREMENTS** — User's custom instructions, highest priority.
- **REVIEWER_SCRIPT** — External reviewer script

## Inputs

1. NARRATIVE_REPORT.md / STORY.md / AUTO_REVIEW.md / CLAIMS_FROM_RESULTS.md
2. Experiment results (JSON/CSV in `figures/`, `experiment_results.md`, `figures/experiment_data.json`)
3. IDEA_REPORT.md (if applicable)
4. FINAL_PROPOSAL.md (if applicable, from research-refine-pipeline)

If none exist, generate plan from $ARGUMENTS description.

## Orchestra-Guided Writing Overlay

Read `../shared-references/writing-principles.md` when framing contribution, Abstract, Introduction.
Read `../shared-references/venue-checklists.md` before freezing outline.

## ⛔⛔⛔ Output Contract (highest priority)

**Must produce `PAPER_PLAN.md` (≥ 1KB, complete outline)**.

⛔ **MANDATORY: Use the `Write` tool to write `PAPER_PLAN.md` directly. Don't only run Read/Bash tools and `end_turn` — that's the #1 reason this step fails. The output must be a real file on disk, not a chat response.**

⛔ **Reading user-uploaded literature/data**:
- DO NOT `cat` entire `_extracted.md/.txt` files — even one 50 MB file will exhaust your context budget for the actual outline.
- USE `Read` tool with explicit ranges (e.g., `Read user_data/xxx_extracted.md offset=0 limit=200`) or `Grep` to extract specific information.
- The CLAUDE.md already lists all uploaded files with character counts — use that index, don't bulk-read.

⛔ **MUST run output verification before ending**:
```bash
PASS=true
[ -f PAPER_PLAN.md ] && SZ=$(wc -c < PAPER_PLAN.md) || SZ=0
if [ "$SZ" -ge 1024 ]; then
    echo "✅ PAPER_PLAN.md ($SZ bytes)"
else
    echo "❌ PAPER_PLAN.md missing or too small ($SZ bytes) — use Write tool to create it now, do NOT end_turn yet"
    PASS=false
fi
[ "$PASS" != true ] && echo "⛔ Verification failed — must complete before ending step"

```



## STEP_MANIFEST 产出声明

本步骤完成后，必须调用 `engine.step_manifest.write_manifest`（或经 bridge/common 等价入口）在工作区根目录写入 `STEP_MANIFEST.json`，至少包含：stepName / backend（含版本）/ config / inputFiles / outputFiles（含 SHA-256）/ commands / dependencies。质量门禁 `step_manifest` 将校验其存在性与完整性；缺失或无效将导致本步骤无法通过（fail）。

建议额外记录：输入数据/大纲来源哈希。

## Workflow
### Step 1: Extract Claims and Evidence

Build Claims-Evidence Matrix:
| Claim | Evidence | Status | Section |
|-------|----------|--------|---------|

Identify one-sentence contribution, 3-5 core claims, known weaknesses.

### Step 2: Determine Structure

Section count is flexible (5-8). Choose based on paper type:

**Empirical**: Intro → Related → Method → Experiments → Analysis → Conclusion
**Theory+Exp**: Intro → Related → Prelim → Experiments → Theory A → Theory B → Conclusion
**Method**: Intro → Related → Method → Experiments → Ablation → Conclusion

Front-load the contribution: title, abstract, intro, hero figure should make the claim clear.

### Step 3: Section-by-Section Planning

For each section: content summary, key claims, figure/table plan, page budget, key citations.

Abstract: what→why hard→how→evidence→strongest result (150-250 words).
Introduction: hook→gap→contribution→results preview→hero figure (1.5 pages).
Related Work: ≥1 full page, organized by category, synthesize not list.

### Step 4: Content-Driven Figure Planning (Exemplar + Audit + Benchmark)

#### Phase A: Exemplar Awareness

Before planning figures, **read the figure exemplars file** to calibrate expectations:

```bash
cat _utils/figure_exemplars.md 2>/dev/null || cat skills/shared-scripts/figure_exemplars.md
# Also browse recipe libraries (60+ SCI-grade chart code templates, for reference)
ls _utils/figure_recipes_*.md 2>/dev/null || ls skills/shared-scripts/figure_recipes_*.md
```

**5 recipe libraries available** (browse to inspire your figure plan, not mandatory):
- `basic` (12): standard plots with gradient fills / KDE backgrounds / Rain Cloud / Lollipop
- `advanced` (17): high-impact SCI charts (SHAP / Kaplan-Meier / Forest plot / Sankey)
- `empirical` (16): econometrics/stats (DID / IV / quantile regression)
- `academic` (12): AI/CS charts (ablation / t-SNE / training curves)
- `competition` (23): contest-style (convergence / Pareto / bubble+KDE)

> **Nature / Science / Cell venue?** Stick to `basic` / `advanced` / `empirical` / `academic`. 
> **Avoid** `competition` — contest charts (Pareto fronts, convergence curves) violate Nature aesthetics. 
> The downstream `nature-figure` step uses recipes only for *layout inspiration* — colors are overridden by `PALETTE_NATURE`.

> **Recipe numbers are suggested starting points.** When listing each figure in FIGURE_MANIFEST, you may annotate the recipe id (e.g. `fig_ablation  // academic#3`); the downstream `paper-figure` step extracts the code via `python3 _utils/get_recipe.py academic 3` as a template, then adapts to your actual data. Annotation optional — paper-figure can also pick by data shape.

**⛔ Subfigure composition: AI decides by necessity, not count.** For each figure, ask "single value/dimension" or "multi-value comparison/multi-dimensional juxtaposition":

🟢 **Compose** (panels ≤ 4, each ≥ `0.48\textwidth`): residual diagnostic 4-panel (Q-Q / residual-fitted / histogram / residual-time), method/model comparison (A vs B), sensitivity for 2-4 parameters, before/after montages (image enhancement/denoising/segmentation hero figures), same quantity at multi-view/multi-time.

🔴 **Do NOT compose**: unrelated figures forced into one row, panels > 4 (split into two figures), single panel < `0.45\textwidth`, complex figures by themselves (heatmap, geo map, 3D render, network graph).

Annotate in FIGURE_MANIFEST as `[2-panel]` / `[4-panel]` / `[single]` (single is default, may omit). Example: `fig_ablation [2-panel] — w/ vs w/o module — academic #3 — section: Ablation`. Full criteria in `_utils/writing_rules.md` rule 4. **AI judges per-figure based on necessity; no hard count target — encourage "information density > page footprint".**

Find the section matching your venue (ICLR/NeurIPS/JMLR etc.) and review the figure/table density. Don't mechanically copy — understand "what density is normal for this paper length."

The ratios and counts above are reference points only. Claude should adapt based on the specific research.

#### Phase B: Section-by-Section Audit

For every subsection in the outline, answer three questions:

1. **What is the core conclusion/content?** (one sentence)
2. **Can the reader understand it from text alone?** Or does it need a figure/table?
   - Numerical comparison → table or bar chart
   - Trend over time → line plot
   - Structural relationships → architecture diagram or flowchart
   - Distribution → histogram/boxplot/heatmap
   - Algorithm → pseudocode or flowchart
   - Pure discussion (e.g., related work categorization) → no figure needed
3. **If needed, figure or table?**
   - Precise values (coefficients, accuracy) → table
   - Visual trends/comparisons → figure
   - Both → main results in table, supplementary visualization in figure

Record results in a "Section Audit" table in the output.

#### Phase C: Benchmark Check

After planning, count total figures+tables and compare with Phase A exemplars:

| Item | Exemplar Reference | This Paper | Status |
|------|-------------------|-----------|--------|
| Data figures (PDF) | [ref] | [actual] | ✅/⚠️ |
| Tables (LaTeX) | [ref] | [actual] | ✅/⚠️ |
| TikZ diagrams (architecture/roadmap) | [ref] | [actual] | ✅/⚠️/❌ |
| Algorithm pseudocode | [ref] | [actual] | ✅/⚠️ |
| Total | [ref] | [actual] | ✅/⚠️ |
| Density (pages/element) | [ref] | [actual] | ✅/⚠️ |

**If any item is ⚠️, go back to Phase B audit table and add missing figures/tables.**

Key checks:
- Method section has architecture diagram or pseudocode?
- Every experiment in experiments section has a figure or table?
- Any section > 3 pages with no visual element?
- Introduction has a hero figure?

#### ⛔ Phase D: TikZ 架构图规划检查

参考 `figure_exemplars.md` 中的"TikZ 架构图分布规律"和"各论文类型 TikZ 图参考建议"表，根据论文类型和内容自主决定是否需要 TikZ 图。

**位置一：绪论/引言 — 技术路线图或研究框架图**
- 硕士论文（CS/AI）：研究框架图（问题→方法→实验→结论的宏观流程）
- 硕士论文（经管/统计）：研究路线图（问题→文献→假设→数据→实证→结论）
- 本科论文：技术路线图（简化版研究框架）
- 期刊论文（ICLR/NeurIPS 等）：可选，方法复杂时建议有

**位置二：方法/模型章节 — 模型架构图或理论框架图**
- CS/AI 方向：整体模型架构图（输入→模块→输出），复杂模块可额外画细节图
- 经管/统计方向：理论模型框架图（变量关系路径图，标注假设 H1/H2/H3）

**位置三：内容触发的高级数学/物理 TikZ 图（强烈推荐，按章节内容评估）**

除了架构图，凡论文某一章涉及"可精确刻画的数学结构"，应主动规划一张 TikZ 图作为该章点睛图（见 `figure_exemplars.md`「TikZ 不止架构图」触发表）：
- 优化/规划求解 → 可行域图（约束+等高线+最优解）
- 微分方程/动力系统 → 相平面图 / 向量场
- 物理/力学/光学场景 → 受力分析图 / 光路图
- 平面几何/向量 → 几何示意图
- 神经网络/深度学习 → MLP / CNN / Transformer 架构
- 物理约束建模/PINN → PINNs 架构图
- 中介/调节/因果机制 → SEM 路径图
完整模板见 `tikz_examples_extra.tex`（A–O）。这类图比普通数据图更能体现专业度，但只在内容真正匹配时加，不要硬塞。

**⛔ 位置四：感知/重构类任务的定性"门面图"（命中必规划）**

若论文核心产出本身可视（图像增强/去雾/去噪/超分/分割/检测/重构/生成、信号或音频处理、三维重建等），对照 `figure_exemplars.md`「领域特定门面图」触发表，**必须规划 `fig_*_visual_cmp` 真实样本前后/方法并排对比图（含关键区域局部放大），归入 Figure Plan 的数据图类，优先级排在所有指标图之前**。所有客观指标（PSNR/SSIM/NIQE/mIoU/mAP 等）都是为佐证肉眼效果而生——只画指标图却漏掉真实样本对比图是本末倒置。用真实数据样本，不要用 AI 生成的想象图。

**规划原则：参考范例自主决定，决定了就必须写进 Figure Plan。后续图表生成和编译检查都以 Figure Plan 为准。**

在 Figure Plan 表格中，TikZ 图应标注位置和类型：

```markdown
| ID | Type | Description | Location | Priority |
|----|------|-------------|----------|----------|
| TikZ-1 | 技术路线图/研究框架图 | 整体研究逻辑链路 | 绪论/Introduction | 必须/推荐 |
| TikZ-2 | 模型架构图/理论框架图 | 核心方法的内部结构 | 方法/Method | 必须/推荐 |
```

**⚠️ 如果 Figure Plan 中 TikZ 图数量为 0，对照"各论文类型 TikZ 图参考建议"表确认是否合理。如果范例建议有但规划中没有，标注理由。**

### Step 5: Citation Scaffolding

Per-section citation plan. Never generate BibTeX from memory. Flag uncertain with `[VERIFY]`.

### Step 6: Cross-Review

Send outline to external reviewer for feedback:

```bash
mkdir -p _tmp
cat << 'REVIEW_EOF' > _tmp/_review_prompt.txt
Please review this paper outline. Focus on:
1. Is the story arc compelling? (hook → gap → contribution → evidence)
2. Does the Claims-Evidence Matrix have gaps?
3. Is the figure plan sufficient for the page budget?
4. Are there structural issues (missing sections, wrong ordering)?
5. Score (1-10) and top 3 improvements needed.

## Paper Outline:
REVIEW_EOF
cat PAPER_PLAN.md >> _tmp/_review_prompt.txt
PYTHON=""; for _c in "$MH_PYTHON" python python3; do [ -z "$_c" ] && continue; if $_c -c "import sys" >/dev/null 2>&1; then PYTHON="$_c"; break; fi; done; [ -z "$PYTHON" ] && PYTHON=python
$PYTHON "$REVIEWER_SCRIPT" --prompt-file _tmp/_review_prompt.txt --thread-file _tmp/_reviewer_thread.json 2>&1 | tee _tmp/_outline_review.txt
```

If reviewer script unavailable, skip this step.

### Step 7: Output

Save to `PAPER_PLAN.md` with: title, one-sentence contribution, Claims-Evidence Matrix, section structure, figure plan, citation plan, reviewer feedback.

## Key Rules

- Large files: use Bash heredoc
- No author information
- Honest about evidence gaps
- MAX_PAGES = main body to Conclusion (refs/appendix excluded)
- Claims-Evidence Matrix is the backbone
- Front-load the story
- Section count is flexible (5-8)
- ⛔ Main output: `PAPER_PLAN.md`. Don't write extra reports to root
- ⛔ LaTeX in Markdown: `$$` block formulas on own line with blank lines before/after, inline `$...$`, multi-line environments (aligned/cases) must be block-level, avoid `\text{}` with CJK


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
