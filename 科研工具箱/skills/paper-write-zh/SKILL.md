---
name: paper-write-zh
description: "Draft a Chinese academic paper in LaTeX using XeLaTeX + ctex. Use when user says \"写中文论文\", \"中文LaTeX\", \"Chinese paper writing\", or wants to generate Chinese LaTeX content."
argument-hint: [topic]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Agent, WebSearch, WebFetch
---

# Chinese Paper LaTeX Writing

Draft a Chinese LaTeX paper section by section: **$ARGUMENTS**

## Constants

- **PAPER_TYPE** — `bachelor`/`master`/`journal`. Default `journal`.
- **MAX_PAGES** — bachelor=25, master=55, journal=15. Body pages must be ≥ MAX_PAGES.
- **CUSTOM_REQUIREMENTS** — Highest priority.
- **REVIEWER_SCRIPT** — External reviewer script `reviewer_client.py`

## Inputs

1. **PAPER_PLAN.md** — outline with data analysis summary
2. **NARRATIVE_REPORT.md** — research narrative
3. **figures/** — PDFs + `latex_includes*.tex` + `tikz_diagrams.tex`（TikZ，编译为 `tikz_diagrams.pdf`）
4. **user_data/** — user materials (.cls/.docx templates, data files)

If `user_data/` has CSV/JSON, read exact values with pandas before writing experiment chapters.

## Load shared rules

```bash
cat _utils/writing_rules.md 2>/dev/null || cat skills/shared-scripts/writing_rules.md
```

## Template selection

Priority: user `.cls` > user `.docx` > built-in template

Built-in templates in `templates/`:
- `bachelor_main.tex` — 本科毕业论文 (ctexart)
- `master_main.tex` — 硕士学位论文 (ctexbook)
- `journal_main.tex` — 期刊论文 (ctexart, two-column)

Copy template to `paper/main.tex`, replace all bracket placeholders with actual content.
Template handles fonts, spacing, margins, gbt7714, headers/footers — do not write main.tex from scratch.

**⛔ 栏数（单栏/双栏）** — 以 CLAUDE.md 里的「栏数」指令为准（如有）：
- `column_layout=single`：`\documentclass[...]` 选项中**去掉 `twocolumn`**。若用的是 journal 模板（默认 twocolumn），还要把摘要区的 `\twocolumn[\begin{@twocolumnfalse} ... \end{@twocolumnfalse}]` 降级为普通单栏写法（顺序排布 标题/作者/摘要/关键词），否则单栏下会编译报错。
- `column_layout=double`：`\documentclass[...]` 选项中**必须含 `twocolumn`**。本科/硕士模板默认单栏，需自行加上 `twocolumn`，摘要用 `\twocolumn[\begin{@twocolumnfalse}...]` 跨栏。
- CLAUDE.md 未给栏数指令时，按模板自带默认（journal=双栏，bachelor/master=单栏）。

**⛔ CRITICAL TEMPLATE RULES:**
1. **NEVER rewrite main.tex from scratch** — the template has carefully tuned preamble
2. **NEVER replace `\listoftables`/`\listoffigures` with hand-written text** — use auto-generated lists
3. Only replace bracket placeholders (`[论文标题]`, `[作者]`, etc.) with actual content
4. Only modify `\input{sections/...}` lines to match actual section filenames

<abstract_format>
### Abstract format

The template uses manual typesetting for abstracts (`\begin{center}{\heiti 摘要}\end{center}` + `\begin{center}{\bfseries Abstract}\end{center}`). Do not use two `\begin{abstract}` environments — ctexart's abstract title is fixed as "摘要", so the English abstract would also show a Chinese title.

Chinese abstract: 500-700 characters. Aim to fill most of one page but leave 3-4 lines margin at the bottom — overflowing onto a second page looks worse than being slightly short. Content chain: 研究背景与意义 → 现有方法不足 → 本文方法 → 数据来源与处理 → 关键数值结果（精度、R²、p值等）→ 应用价值与建议.

English abstract: 350-500 words, faithful translation covering the same structure and all numerical results. Same principle — fit on one page, do not overflow.
</abstract_format>

## ⛔⛔⛔ 完成铁律（最高优先级，违反则本步骤失败）

**根据 `params.output_format` 决定主产物路径**：

- **PDF 模式（默认）**：必须产出 `paper/main.tex`（基于模板，≥ 5KB）+ `paper/sections/*.tex`（每章节 ≥ 500 字符）+ `paper/references.bib`
- **docx 模式（用户选 Word 输出）**：必须产出 `paper/main.md`（**单文件**，含完整论文，≥ 5KB）。**禁止产 paper/main.tex**

⛔ **如何识别当前模式**：
```bash
grep -q "Word（.docx）" CLAUDE.md && echo "MODE=docx" || echo "MODE=pdf"
```

⛔ **结束前必跑产出验证**（步骤的最后一步，绝不省略）：
```bash
echo "=== 产出验证（必须全部 ✅）==="
MODE=$(grep -q "Word（.docx）" CLAUDE.md 2>/dev/null && echo docx || echo pdf)
echo "MODE: $MODE"
PASS=true
if [ "$MODE" = "docx" ]; then
    [ -f paper/main.md ] && SZ=$(wc -c < paper/main.md) || SZ=0
    if [ "$SZ" -ge 5120 ]; then echo "✅ paper/main.md ($SZ bytes)"; else echo "❌ paper/main.md 缺失或过小 ($SZ bytes)"; PASS=false; fi
else
    [ -f paper/main.tex ] && SZ=$(wc -c < paper/main.tex) || SZ=0
    if [ "$SZ" -ge 5120 ]; then echo "✅ paper/main.tex ($SZ bytes)"; else echo "❌ paper/main.tex 缺失或过小 ($SZ bytes)"; PASS=false; fi
    SECT_COUNT=$(ls paper/sections/*.tex 2>/dev/null | wc -l)
    if [ "$SECT_COUNT" -ge 3 ]; then echo "✅ paper/sections/*.tex ($SECT_COUNT 个章节)"; else echo "❌ paper/sections/ 章节过少 ($SECT_COUNT)"; PASS=false; fi
fi
[ "$PASS" != true ] && echo "⛔ 产出验证失败 — 必须补全后重新跑验证, 不要结束本步骤"
```
**如果验证失败,继续补全产出而不是退出**。



## STEP_MANIFEST 产出声明

本步骤完成后，必须调用 `engine.step_manifest.write_manifest`（或经 bridge/common 等价入口）在工作区根目录写入 `STEP_MANIFEST.json`，至少包含：stepName / backend（含版本）/ config / inputFiles / outputFiles（含 SHA-256）/ commands / dependencies。质量门禁 `step_manifest` 将校验其存在性与完整性；缺失或无效将导致本步骤无法通过（fail）。

建议额外记录：模板来源哈希、BibTeX 条目数、引用格式。

## Workflow
### Step 0: Backup + resume check + 上游验证

**⛔ 上游输出完整性检查（写论文前必做）：**
```bash
echo "=== 上游输出完整性检查 ==="
UPSTREAM_OK=true

# 1. 核心文件是否存在
for f in PAPER_PLAN.md RESULTS.md; do
    if [ -f "$f" ]; then
        sz=$(wc -c < "$f")
        echo "✅ $f ($sz 字符)"
        [ "$sz" -lt 500 ] && { echo "  ⚠ 文件过小，内容可能不完整"; UPSTREAM_OK=false; }
    else
        echo "⚠ $f 不存在（将使用最小大纲兜底）"
    fi
done

# 2. 实验数据文件
[ -f figures/all_results.json ] && echo "✅ figures/all_results.json" || echo "⚠ 无 all_results.json，数值可能不准确"
[ -f experiment_results.md ] && echo "✅ experiment_results.md" || echo "  （无 experiment_results.md，将依赖 RESULTS.md）"

# 3. 图表文件
PDF_COUNT=$(ls figures/*.pdf 2>/dev/null | wc -l)
echo "PDF 图表: $PDF_COUNT 张"
[ "$PDF_COUNT" -eq 0 ] && echo "⚠ 无 PDF 图表，论文将缺少图片"

# 4. latex_includes.tex
[ -f figures/latex_includes.tex ] && echo "✅ figures/latex_includes.tex" || echo "⚠ 无 latex_includes.tex，图表嵌入代码缺失"

echo "=== 上游检查完成 ==="
$UPSTREAM_OK || echo "⚠ 部分上游文件不完整，继续执行但结果可能欠佳"
```

Back up existing `paper/` to `paper-backup-{timestamp}/`. Check for incomplete sections:
```bash
echo "=== 断点续写检查 ==="
if [ -d "paper/sections" ]; then
    for f in paper/sections/*.tex; do
        [ -f "$f" ] || continue
        chars=$(wc -c < "$f")
        if [ "$chars" -lt 500 ]; then
            echo "⚠ 占位符: $(basename $f) ($chars 字符) — 需要续写"
        else
            echo "✅ 已完成: $(basename $f) ($chars 字符)"
        fi
    done
fi
```
Resume: only write placeholder sections (<500 chars or contains "待补充"/"placeholder"), skip completed ones (>2000 chars). See `<resume_strategy>` in writing_rules.md for full details.

**⛔ 数值来源规则（全文遵守）：**
所有论文中的数值（精度、RMSE、R²、p-value、系数、训练时间等）必须来自 `figures/all_results.json` 或 `RESULTS.md`。

**⛔ 禁止 `cat figures/*_results.json`。** 这些结果文件可能含全精度时序数组（可达数十 MB / 数十万行），整读会撑爆上下文——本地大模型直接失败、经中转的 GPT 因协议翻译超长反复 `api_retry` 卡死。**论文正文只用标量数值（精度/RMSE/R²/p 值/系数/训练时间等），巨型数组是给图表用的、不进正文。** 写任何含数值的章节之前，用下面的 `summarize` 脚本拿 KB 级摘要（标量原样显示、精度零损失，只把大数组压成「长度+范围+前3样本」）：
```bash
[ -f RESULTS.md ] && cat RESULTS.md
python3 - <<'PY'
import json, os, glob
def summarize(v, depth=0):
    if isinstance(v, list):
        n=len(v); nums=[x for x in v if isinstance(x,(int,float))]
        if nums: return f'list[{n}] range=[{min(nums):.4g},{max(nums):.4g}] sample={v[:3]}'
        if v and isinstance(v[0], (list,dict)): return f'list[{n}] of {type(v[0]).__name__}, first_shape={len(v[0]) if hasattr(v[0],"__len__") else "?"}'
        return f'list[{n}] sample={str(v[:3])[:80]}'
    if isinstance(v, dict) and depth<2:
        return 'dict{'+', '.join(f'{k}: {summarize(x,depth+1)}' for k,x in list(v.items())[:6])+'}'
    return f'{type(v).__name__}={str(v)[:60]}'
for f in sorted(glob.glob('figures/*_results.json')):
    sz=os.path.getsize(f); d=json.load(open(f,encoding='utf-8'))
    print(f'\n=== {os.path.basename(f)} ({sz//1024}KB) ===')
    if isinstance(d, dict):
        for k,v in d.items(): print(f'  {k}: {summarize(v)}')
    else: print(f'  {summarize(d)}')
PY
```
论文要引的标量都在 `RESULTS.md` 和上面摘要的 range/sample 里；若某个标量摘要没显示全，用 `python3 -c "import json;d=json.load(open('figures/all_results.json'));print(d['键名'])"` 定点取那一个值，仍然不要整读。原样复制数字填入论文，不要凭记忆估算、四舍五入或编造数值。最终的 quality gate 会做数值一致性检查，编造的数字会被发现。

**⛔ Claims-Evidence 对照（必须严格遵循规划）：**

写每个章节前，先重读 PAPER_PLAN.md 中的 claims-evidence 矩阵：
```bash
grep -A 100 'Claims-Evidence\|claim.*evidence\|claim-evidence\|观点.*证据' PAPER_PLAN.md 2>/dev/null | head -30
```

写作纪律：
- 论文中的每个论断必须对应到规划中的某一行
- 不要添加规划外的新论断（如有新发现，先更新 PAPER_PLAN.md）
- 不要跳过规划中的论断（即使是负面结果也要如实报告）
- 每个论断的数值证据必须与 `figures/all_results.json` 一致

如果某个规划中的论断在数据中找不到证据，诚实写"初步结果提示 X，更严谨的验证留待未来工作"，不要编造证据。

### Step 1: Initialize

Create `paper/`, copy template to `main.tex`, generate `math_commands.tex` (paper-specific commands only — do not redefine `\sin`, `\cos`, `\log`, etc.).

### Step 2: Figure inventory

Before writing any section, build a complete inventory of available figures. This prevents empty figure environments (caption without image).

```bash
echo "=== Available PDF figures ==="
ls -la figures/*.pdf 2>/dev/null || echo "No PDF figures found"
echo ""
echo "=== Available table files (PDF模式: .tex / Word模式: .md) ==="
ls -la figures/TABLE_*.tex figures/TABLE_*.md 2>/dev/null || echo "No TABLE files found"
echo ""
echo "=== TikZ 几何/算法/架构图 ==="
# TikZ 图由 paper-figure-drawio 生成为 figures/tikz_diagrams.tex → 编译成 figures/tikz_diagrams.pdf
# （历史命名可能是 tikz_architecture_examples.tex，一并兼容）。TikZ 的 PDF 已被写进 latex_includes.tex。
ls -la figures/tikz_*.pdf figures/tikz_*.tex 2>/dev/null || echo "No TikZ diagrams"
grep -l 'tikz_' figures/latex_includes.tex >/dev/null 2>&1 && echo "→ TikZ 已在 latex_includes.tex 中，按其图块嵌入对应章节" || true
echo ""
echo "=== latex_includes.tex content (figure→PDF mapping) ==="
cat figures/latex_includes.tex 2>/dev/null || echo "No latex_includes.tex"
```

From the output above, build a mapping table: figure label → PDF filename → target section. Only embed figures whose PDF files actually exist — do not create figure environments for PDFs that don't exist (this causes empty figures with just a caption and no image).

**⛔ TikZ 图（如 `figures/tikz_diagrams.pdf` / `figures/tikz_*.pdf`）必须嵌入论文。** 它们已在 `latex_includes.tex` 中有对应 `\includegraphics` 图块，按几何/算法/架构图的章节归属嵌入（几何示意图→对应子问题章节，算法流程图→模型建立章节）。**禁止漏掉任何 `tikz_*.pdf`。**

**⛔ 中文论文的图表 caption 必须是中文。** 如果 `latex_includes.tex` 里的 caption 是英文，嵌入时必须翻译成中文。例如：`\caption{Model Performance Comparison}` → `\caption{模型性能对比}`。

Also scan `figures/*.tex` for all `\begin{figure}` / `\begin{table}` blocks with their `\label{}`. After writing, verify all embedded:
```bash
grep -oh '\\label{[^}]*}' figures/*.tex 2>/dev/null | sort -u > _all_fig_labels.txt
grep -oh '\\label{[^}]*}' paper/sections/*.tex paper/main.tex 2>/dev/null | sort -u > _embedded_labels.txt
comm -23 _all_fig_labels.txt _embedded_labels.txt  # should be empty
```

### Step 2.5: 文献预检索（写正文之前必须完成）

**⛔ 在写任何 \cite{} 之前，必须先建立已验证的文献池。**

目的：先搜索到真实存在的论文，写正文时只引用池子里的论文，避免编造不存在的文献。

```bash
PYTHON=""; for _c in "$MH_PYTHON" python python3; do [ -z "$_c" ] && continue; if $_c -c "import sys" >/dev/null 2>&1; then PYTHON="$_c"; break; fi; done; [ -z "$PYTHON" ] && PYTHON=python
mkdir -p _tmp

# 根据论文的关键主题领域搜索真实论文
# （根据你的具体选题调整搜索词）
# 示例：
#   $PYTHON "$SCHOLAR_SCRIPT" bibtex "空间杜宾模型 数字经济" --max 5
#   $PYTHON "$SCHOLAR_SCRIPT" bibtex "算力基础设施 区域发展" --max 5
```

搜索后，创建 `_tmp/_verified_refs.txt`，每行一篇已验证论文：
```
key: lesage_2009_spatial | title: Introduction to Spatial Econometrics | authors: LeSage, Pace | year: 2009 | match: good
```

**写正文时只能引用这个池子里的论文。** 如果需要引用池子外的论文，先搜索验证后再加入池子。

**兜底**：如果 `scholar_fetch.py` 搜不到或 `match_label="low"`，用 WebSearch 在 Google Scholar / Semantic Scholar 网站上搜索，手动核实标题+作者+年份后再加入池子。

### Step 3: Write each section

**⛔ CRITICAL: Do NOT write the abstract now.** 跳过摘要章节，先写正文。摘要位置先写占位符 `% [摘要待 Step 4.5 正文完成后填写]`。摘要必须最后写，因为要从各章节摘取**具体数值**——先写就是凭印象编数字。

Step 4.5 才回来填摘要：到时候读 `RESULTS.md` / `experiment_results.md` / `figures/all_results.json` 和所有 `sections/*.tex`，提取实测数值后写摘要。

Writing order: method/core → experiments → introduction → related work → conclusion.
Save each section immediately. If approaching output limit, create `% [PLACEHOLDER]` files for remaining sections.

**⛔ 写实验/结果章节前，必须先读 experiment_results.md / RESULTS.md / figures/*.json 获取精确数值。** 不要凭记忆编造结果——所有数值（精度、R²、p 值、系数等）必须从数据文件中提取。

**⛔ 写作风格铁律：**
- **禁止在正文中使用 `\begin{itemize}` 或 `\begin{enumerate}`。** 用连贯段落叙述，需要列举时用"（1）...（2）...（3）..."行内编号或"首先...其次..."过渡词。
- **每段至少 3-5 句话，不要写 1-2 句的短段落。**
- **连续段落不能以相同句式开头。**

Follow all rules from `_utils/writing_rules.md` (interleaving, embedding, LaTeX constraints, page filling, resume strategy).

**⛔ 跨章上下文 + 图数据绑定（防"两张皮"）：**
- **每写完一章**，立刻往工作区根目录 `_writing_context.md` 追加 3-5 行要点卡（核心论点／关键数字／新定义的符号术语／已讨论的图表）；**写下一章前先 `cat _writing_context.md`**，承接前文结论、复用已定义术语（不重复定义）、保持同一指标数字全文一致——详见 `_utils/writing_rules.md` 的 `<chapter_context_card>`。
- **写每张图/表的分析前**，先按 `<figure_data_binding>`：从 FIGURE_MANIFEST/latex_includes 认清"这张图画的是什么量" → 去 `RESULTS.md`／`figures/all_results.json` 定位它对应的真实数值 → 分析里只用这些真值，**禁止凭图形状/位置猜数、禁止编造坐标**。

**⛔ 图文并茂硬规则（每个章节都必须遵守）：**
- **浮动符（受控浮动）**：图用 `\begin{figure}[H]`（就地钉死），表用 `\begin{table}[H]`（就地）。图用 `[H]` 是为了钉在引出文字正下方、从机制上杜绝多图连排（`[htbp]` 会让 LaTeX 把多张图攒到一页、最伤可读性）；代价是极少数"图接近整页高+恰好落页底"时上方留一段空白，但图已限高在 `0.9\textheight` 内、且每张图前后都有引导/承接文字，此情形罕见且优于连排。模板已加载 `\usepackage[section]{placeins}`，每节末自动 `\FloatBarrier`（防残余浮动体跨节）。⛔ 表格不要用 `[htbp]`：会被 `\FloatBarrier` 逼到节末，在表上方留半页空白；短表用 `[H]` 就地，超长表用 `\begin{longtable}`。伪代码 `\begin{algorithm}[H]` 保持就地。
- 每张图/表后面必须有 ≥5 行分析文字（数值解读+对比+结论），然后才能放下一张图
- **✅ 图号必须显式引用、但句式换着来**：每张图都要用 `\ref{}` 或"图 N"点名，让读者对上号（硬规范，别为避免套路就删图号）；相邻两张图的引用句式必须不同，在括号旁注（首选，如"波动不超过 3.7%（图~\ref{fig:x}）"）／句首带出／动词引导（"观察图~\ref{fig:x} 可见"）／图作主语（带实质结论时可用）／后置印证之间轮换。**要禁的是"图 N 展示了……从图中可以看出……"这种空洞流水账的单调重复，不是禁止引用图号。**
- 绝对禁止两张图连续出现中间没有分析段落
- 图片用 `\includegraphics[width=0.85\textwidth,keepaspectratio]`（以宽度为主，高度自适应）。⛔ 不要再加 `height=0.38\textheight` 这种小高度限制——在 `keepaspectratio` 下 height 只会把图**压得更小**：方形或竖高的图（热力图、雷达图、森林图、混淆矩阵、竖排子图、流程图）会被 0.38 页高卡到只有半页宽，导致"图很小看不清"。只有当某张图确实接近整页高、可能溢出时，才加 `height=0.9\textheight` 作为防溢出兜底

After each section, check chars:
```bash
chars=$(wc -c < "paper/sections/当前章节.tex")
echo "当前章节: $chars 字符"
# Chinese LaTeX ≈ 800-1000 chars/page
# If chapter page budget in PAPER_PLAN.md is 5 pages but only 2000 chars (~2.5 pages), expand immediately
```

<exemplar_depth>
#### Writing depth by paper type

**本科毕业论文 (30 pages, 5 chapters)**:
- 绪论 (5-6p): 研究背景 1-2 段 + 国内外研究现状按 2-3 个方向分类综述 + 研究内容与方法 + 论文结构
- 理论基础 (5-6p): 核心概念定义 + 相关理论介绍 + 技术路线说明, each concept in full paragraphs (not one-sentence mentions)
- 方法/系统设计 (8-10p): 整体架构 + 各模块详细设计 + 关键算法/公式 + 实现细节
- 实验/测试 (6-8p): 实验环境 + 数据集 + 评价指标 + 主要结果表 + 对比图 + 结果分析 (1-2 paragraphs per result)
- 总结与展望 (2-3p): 工作总结 + 不足之处 + 未来改进方向

**硕士论文 — CS/AI (80 pages, 6 chapters)**:
- 绪论 (8-10p): 研究背景 2-3 段详细论述 + 国内外研究现状按子领域分 3-4 类每类 3-5 篇详细讨论 + 研究内容与创新点
- 相关工作 (12-14p): 按子领域分组, each sub-field has overview paragraph + representative methods detailed + connection to this work
- 方法 (18-20p): each core concept in full paragraphs (definition → formula → intuition → connection to this work), derivation steps not skipped
- 实现 (10-12p): 系统架构 + 数据流 + 超参数配置 + 工程优化细节
- 实验 (20-24p): every result has 2-3 paragraphs of interpretation (数值分析 + 原因分析 + 与其他方法对比), not just "如表所示我们更好"
- 总结 (4-6p): 改述贡献 + 局限性 + 未来工作

**硕士论文 — 经管/统计 (80 pages)**:
- 绪论 (6-8p): research background + significance + literature review + research gap + contributions
- 文献综述 (12-14p): grouped by 3-4 themes, 5-8 papers per theme with detailed discussion
- 理论与方法 (10-16p): theoretical framework / model specification (adapt by research type: causal inference writes hypotheses + variables + model; prediction writes model selection + parameters; evaluation writes indicator system + weighting method)
- 数据与描述性分析 (10-16p): data source + sample description + variable definition table + descriptive stats + exploratory analysis
- 核心分析 (20-24p): organized by research content (causal: regression + robustness + heterogeneity; prediction: model comparison + error analysis; evaluation: comprehensive scoring + dimensional analysis), every result has 2-3 paragraphs of interpretation
- 结论 (6p): main findings + policy recommendations + limitations + future directions

**期刊论文 (15 pages, 5-6 sections)**:
- Introduction (1.5p): hook → gap → contribution → results preview
- Related Work (1-1.5p): by category, synthesize not list
- Method (2-2.5p): notation → formulation → algorithm, compact but complete
- Experiments (3-4p): setup → main results → ablation → analysis
- Conclusion (0.5p): rephrase contributions + limitations

| Type | Pages | Characters | References |
|------|-------|-----------|------------|
| 本科 (30p) | 25-30 | 10000-15000 | ≥20 |
| 硕士 (80p) | 50-60 | 30000-50000 | ≥50 |
| 期刊 (15p) | 12-15 | 6000-8000 | ≥30 |
</exemplar_depth>

#### Per-section minimum figures/citations
- 绪论: ≥1 figure + ≥3 citations
- 相关工作: ≥1 figure/table + ≥3 citations
- 方法: ≥2 figures + ≥2 citations
- 实验: ≥3 figures/tables + ≥3 citations
- 结论: ≥1 citation

Core result tables (主结果对比表, 消融实验表) and key analysis figures belong in the body, not appendix. Appendix only: code, very long auxiliary tables, extra experiment details.

**Expansion strategies** (not padding — substantive content):
- Formula without derivation → add step-by-step derivation with physical meaning
- Result with only "如表所示" → add 2-3 paragraphs (数值含义 + 与预期对比 + 原因分析 + 与其他方法对比)
- Literature review only lists papers → add method summary for each + connection to this work
- Algorithm as pseudocode only → add explanation, complexity analysis, convergence discussion

#### Figure usage principle

"字不如表，表不如图" — but figures only where data needs visualization (data description, experiment results). Do not force figures into pure literature review or theoretical derivation. Claude decides figure count and placement based on content needs.

### Step 4: Build references

Follow the `<references_workflow>` in `_utils/writing_rules.md`.
gbt7714 package handles bibliographystyle — only need `\bibliography{references}`.
Verify references.bib is non-empty before proceeding to next step.

**⛔ 使用 scholar_fetch.py 工具获取所有参考文献的 BibTeX。禁止凭记忆编造 BibTeX。**

**⛔ 引用写法规则：写正文时，citation key 必须包含描述性关键词，格式为 `作者姓_年份_主题关键词`。**
例如：`\cite{wang_2023_supply_chain_resilience}` 而不是 `\cite{wang2023supply}`。
这样搜索时能用关键词找到正确的论文。如果不确定作者/年份，用 `TODO__` 前缀：`\cite{TODO__digital_economy_spatial_spillover}`。

```bash
# Step 4a: 收集所有引用 key 并提取搜索关键词
grep -roh '\\cite[tp]*{[^}]*}' paper/sections/*.tex paper/main.tex 2>/dev/null \
  | grep -oP '\{[^}]+\}' | tr -d '{}' | tr ',' '\n' | sed 's/^ *//;s/ *$//' | sort -u > _tmp/_cited_keys.txt
echo "引用 key 数量: $(wc -l < _tmp/_cited_keys.txt)"
cat _tmp/_cited_keys.txt

# Step 4b: 逐个搜索并获取 BibTeX（用描述性关键词搜索）
PYTHON=""; for _c in "$MH_PYTHON" python python3; do [ -z "$_c" ] && continue; if $_c -c "import sys" >/dev/null 2>&1; then PYTHON="$_c"; break; fi; done; [ -z "$PYTHON" ] && PYTHON=python
while IFS= read -r key; do
    # 将 citation key 转为搜索词：去掉 TODO__ 前缀，下划线替换为空格
    query=$(echo "$key" | sed 's/^TODO__//; s/_/ /g')
    echo "--- 获取: $key (搜索: $query) ---"
    $PYTHON "$SCHOLAR_SCRIPT" bibtex "$query" --max 3
    sleep 0.5
done < _tmp/_cited_keys.txt
```

处理每个搜索结果：
1. **检查 `match_label`**：`"good"` → 直接使用。`"partial"` → 核实标题是否匹配你的引用意图。`"low"` → 很可能搜错了，换更好的关键词重新搜索或用 WebSearch。
2. **检查 `match_score`**：分数 < 0.3 说明搜索结果大概率不是你想引用的论文，不要盲目使用。
3. 选择正确的论文，将其 `bibtex` 字段复制到 `paper/references.bib`。
4. 将 .tex 文件中的 citation key 替换为 BibTeX 条目中的实际 key。
5. 如果 `bibtex_source=auto`，在条目上方加 `% [VERIFY]`。
6. 如果 `match_label="low"` 且找不到更好的结果，加 `% [LOW_MATCH - 请核实是否为目标论文]`，并用 WebSearch 兜底。

### Step 5: De-AI polish

See `<de_ai_polish>` in `_utils/writing_rules.md`.

### Step 5.5: 最后写摘要 ⛔

⛔ **MANDATORY: 现在才写摘要**（替换 Step 3 留的占位符）。

先读 `RESULTS.md` / `experiment_results.md` / `figures/all_results.json` 和所有 `sections/*.tex` 文件，提取实测数值（准确率、F1、p 值、系数等）。然后用这些**已验证的数字**写摘要，不要编造任何数值。

结构：研究背景 → 现有方法不足 → 本文方法 → 数据来源 → 关键数值结果 → 应用价值。中文摘要 500-700 字，英文摘要 350-500 词，填满一页但留 3-4 行底部空白（宁短勿溢）。

写完后自检：摘要里每个数字必须在正文中出现。

```bash
for n in $(grep -oE '[0-9]+\.[0-9]+' paper/sections/0_abstract.tex | sort -u); do
  grep -q "$n" paper/sections/*.tex RESULTS.md 2>/dev/null \
    || echo "⛔ 摘要数字 $n 未在正文中出现 — 疑似编造"
done
```

### Step 6: Cross-review

Send draft to external reviewer for feedback:

```bash
mkdir -p _tmp
cat << 'REVIEW_EOF' > _tmp/_review_prompt.txt
请评审这篇中文学术论文草稿。重点关注：
1. 逻辑流畅性和论证结构
2. 论点-证据对齐（每个论点是否有数据支撑？）
3. 写作清晰度和简洁性
4. 缺失内容或薄弱章节
5. 评分（1-10）和最需要改进的 3 个方面

## 论文各章节：
REVIEW_EOF
for f in paper/sections/*.tex; do
    [ -f "$f" ] && echo "### $(basename $f)" >> _tmp/_review_prompt.txt && cat "$f" >> _tmp/_review_prompt.txt
done
PYTHON=""; for _c in "$MH_PYTHON" python python3; do [ -z "$_c" ] && continue; if $_c -c "import sys" >/dev/null 2>&1; then PYTHON="$_c"; break; fi; done; [ -z "$PYTHON" ] && PYTHON=python
$PYTHON "$REVIEWER_SCRIPT" --prompt-file _tmp/_review_prompt.txt --thread-file _tmp/_reviewer_thread.json 2>&1 | tee _tmp/_cross_review.txt
```

If reviewer script unavailable, skip this step.

### Step 7: Final verification

```bash
bash _utils/writing_check.sh paper/ 2>/dev/null || bash skills/shared-scripts/writing_check.sh paper/
```

Also verify:
```bash
source .env_skill 2>/dev/null || true  # 加载 MAX_PAGES 等数值参数
echo "=== 各章节字符数 ==="
total=0
for f in paper/sections/*.tex; do
    chars=$(wc -c < "$f")
    total=$((total + chars))
    echo "  $(basename $f): $chars 字符"
done
echo "  总计: $total 字符"
echo "  目标: ≥ ${MAX_PAGES:-30} × 800 = $((${MAX_PAGES:-30} * 800)) 字符"
```
- Total chars ≥ MAX_PAGES × 800 (expand thinnest sections if not)
- references.bib exists and non-empty
- No template bracket placeholders remaining
- All figures/*.pdf referenced in sections
- No `\input{../figures/...}` in section files

**Figure embedding verification (must pass before finishing)**:
```bash
echo "=== 图表嵌入检查 ==="
missing=0
for pdf in figures/*.pdf; do
    [ -f "$pdf" ] || continue
    bn=$(basename "$pdf")
    if ! grep -rq "$bn" paper/sections/*.tex paper/main.tex 2>/dev/null; then
        echo "MISSING: $bn 未嵌入任何章节"
        missing=$((missing + 1))
    fi
done
for fig_tex in figures/*.tex; do
    [ -f "$fig_tex" ] || continue
    for lbl in $(grep -oh '\\label{[^}]*}' "$fig_tex" 2>/dev/null); do
        if ! grep -rq "$lbl" paper/sections/*.tex paper/main.tex 2>/dev/null; then
            echo "MISSING: $lbl (from $(basename $fig_tex)) 未嵌入"
            missing=$((missing + 1))
        fi
    done
done
echo "缺失: $missing"
```
If any figures are missing, go back and embed them into the appropriate sections before finishing. **⛔ Do NOT finish until missing = 0.**

**⛔ Page count pre-check (MUST pass before finishing):**

> ⛔ **MAX_PAGES 指正文页数**（章节 1 - 结论，含图表）— 不含 摘要 / 目录 / 参考文献 / **附录代码**。
> 检查只统计 `paper/sections/*.tex`，附录代码归 `paper/appendix/*.tex`。

```bash
source .env_skill 2>/dev/null || true  # 加载 MAX_PAGES 等数值参数

# 1. sections/ 不应该含代码块
code_in_body=0
for f in paper/sections/*.tex; do
    [ -f "$f" ] || continue
    if grep -qE '\\begin\{(lstlisting|verbatim|minted|python|matlab)\}' "$f" 2>/dev/null; then
        code_in_body=$((code_in_body + 1))
        echo "  ⚠️ $f 含代码块 — 代码应放 paper/appendix/"
    fi
done

# 2. 正文字符与页数
total=0
for f in paper/sections/*.tex; do
    [ -f "$f" ] || continue
    chars=$(wc -c < "$f")
    total=$((total + chars))
done
est_pages=$((total / 900))
echo "正文字符: $total, 估算页数: ~$est_pages, 目标: ≥ ${MAX_PAGES:-30}"
if [ -n "$MAX_PAGES" ] && [ "$est_pages" -lt "$((MAX_PAGES * 80 / 100))" ]; then
    echo "⛔ 正文页数低于目标 80%，必须扩充最薄章节（不要靠附录代码凑数）"
fi
```
If estimated pages < 80% of MAX_PAGES, expand the thinnest chapters before finishing.

⛔ **正文 vs 附录归档约束**：
- `paper/sections/` — 仅正文章节（绪论 / 方法 / 结果 / 讨论 / 结论）
- `paper/appendix/` — 代码 / 长数据表 / 求解日志 / 公式补充推导
- 把代码塞 sections/ 会让页数预检虚高但正文实际薄

## Key Rules

- Use templates, do not write main.tex from scratch
- XeLaTeX compilation required
- Citation format: gbt7714 (superscript `[1]`), not natbib
- No `\hypersetup{colorlinks=true}` — conflicts with hidelinks
- Body pages ≥ MAX_PAGES
- No real author info — use placeholders
- Primary output: `paper/` directory, temp files: `_tmp/`
- ⛔ **本步骤只写论文 .tex 文件，不要重新生成图表 PDF、不要修改 code/*.py、不要重新运行分析代码。** 图表和数据已由前序步骤生成完毕，直接引用即可
- Large files: Bash heredoc
- Backup before overwrite


---

## ⛔ FIGURE_MANIFEST 对账（写完正文必跑，规划了几张就必须嵌入几张）

```bash
echo "=== FIGURE_MANIFEST 对账 ==="
PLAN_FILE=""
for f in PROBLEM_ANALYSIS.md PAPER_PLAN.md MODELING_REPORT.md TOPIC_PLAN.md; do
  [ -f "$f" ] && grep -q "<!-- BEGIN FIGURE_MANIFEST -->" "$f" && { PLAN_FILE="$f"; break; }
done
if [ -n "$PLAN_FILE" ]; then
    START=$(grep -n "<!-- BEGIN FIGURE_MANIFEST -->" "$PLAN_FILE" | head -1 | cut -d: -f1)
    END=$(grep -n "<!-- END FIGURE_MANIFEST -->" "$PLAN_FILE" | head -1 | cut -d: -f1)
    EXPECTED_FIGS=$(sed -n "${START},${END}p" "$PLAN_FILE" | grep -oE "^[[:space:]]*-[[:space:]]+(fig_[a-zA-Z0-9_]+|tikz_[a-zA-Z0-9_]+)" | sed "s/^[[:space:]]*-[[:space:]]*//")
    manifest_missing=0
    for name in $EXPECTED_FIGS; do
        if ! ls figures/${name}.pdf figures/${name}.png 2>/dev/null | head -1 | grep -q .; then
            echo "❌ MANIFEST: $name 文件不存在"
            manifest_missing=$((manifest_missing + 1))
        elif ! grep -rqE "${name}\.(pdf|png)" paper/sections/ paper/main.tex 2>/dev/null; then
            echo "❌ MANIFEST: $name 文件存在但论文未引用"
            manifest_missing=$((manifest_missing + 1))
        fi
    done
    if [ "$manifest_missing" -gt 0 ]; then
        echo "⛔ FIGURE_MANIFEST 对账失败 ($manifest_missing 张): 必须把这些图都画出来 + 嵌入正文后再结束"
    else
        echo "✅ FIGURE_MANIFEST 全部嵌入"
    fi
fi
```

## ⛔ 通用 paper-stage 审计（所有写稿步骤共用，跨工作流）

写完正文 / 编译前必须跑一次通用审计，独立于 PROBLEM_FACTS.json 是否存在：

```bash
# 通用 paper 审计：
#   [13] 正文结论与 results.json 一致（防"最优解 X 但正文写 Y"）
#   [14] 事件源归属（防"凭变量名脑补撞击 / 命中 / 拦截"）
# 即使没 PROBLEM_FACTS.json（普通学术 / 课程论文 / 人文社科），也会以"简化模式"跑独立审计。
if [ -f _utils/facts_audit.py ]; then
    python3 _utils/facts_audit.py --stage paper 2>&1 | tee -a AUDIT_REPORT.md
    PRC=$?
    if [ "$PRC" = "1" ]; then
        echo "❌ 通用 paper-stage 审计未通过 — 必须按上面提示修正正文 / results.json 后重新跑"
    fi
fi
```

