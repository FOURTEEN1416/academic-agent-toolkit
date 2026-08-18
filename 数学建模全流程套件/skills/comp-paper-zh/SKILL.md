---

name: comp-paper-zh

description: "数学建模竞赛/统计建模中文论文撰写。按竞赛规范结构生成完整 LaTeX 论文。Use when user says \"写竞赛论文\", \"competition paper\", \"建模论文\"."

argument-hint: [competition-type]

allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Agent, WebSearch, WebFetch

---



# Competition Paper Writing (Chinese)



Write a competition paper based on modeling results: **$ARGUMENTS**



## ⚡ 快速模式检测（开头先跑）



```bash

FAST_MODE=0

grep -q 'MH_FAST_MODE=1' CLAUDE.md 2>/dev/null && FAST_MODE=1

echo "FAST_MODE=$FAST_MODE"

```



**若 `FAST_MODE=1`（速度优先）：** 仍必须产出完整论文（各章齐全、子问题全覆盖、图表按 manifest 嵌入、正文页数达标、引用真实数据不编造、通过产出验证），但**跳过**：图文数值一致性逐句核对、AUDIT_OK 溯源反查、发现小瑕疵后的反复润色重写。一次写成、结构与内容齐全即可。**若 `FAST_MODE=0`（默认）：** 后文所有一致性检查照常执行。



## Constants



- **COMPETITION** — `stats` = 统计建模, `huazhong` = 华中杯, `wuyi` = 五一杯, `mathorcup` = MathorCup, others = 数模竞赛 (cumcm/huawei/etc.)

- **MAX_PAGES** — Default 20. Body pages (chapter 1 through conclusion) must be ≥ MAX_PAGES.

- **CUSTOM_REQUIREMENTS**



## Inputs



1. PROBLEM_ANALYSIS.md, MODELING_REPORT.md, RESULTS.md

2. figures/, code/



## Load shared rules



```bash

cat _utils/writing_rules.md 2>/dev/null || cat skills/shared-scripts/writing_rules.md

```



<paper_structure>

## Paper Structure by Competition Type



### 数模竞赛 (cumcm/huawei/mathorcup/huazhong/etc.)



Template: `templates/cumcm/main.tex` (国赛/华为杯), `templates/mathorcup/main.tex` (MathorCup), `templates/apmcm_zh/main.tex` (亚太赛中文 APMCM), `templates/huazhong/main.tex` (华中杯), `templates/wuyi/main.tex` (五一杯)



**⛔ MathorCup 与 亚太赛中文(APMCM) 都使用 `MathorCupmodeling.cls` 文档类**（模板文件夹已包含 cls）。使用 `\bianhao{}`、`\tihao{}`、`\timu{}` 设置队伍信息，`\keyword{}` 设置关键词。摘要用 `\begin{abstract}...\end{abstract}` 环境。参考文献用 `\begin{thebibliography}` 环境。



**⛔ 华中杯必须使用 `cumcmthesis` 文档类**（模板文件夹 `huazhong/` 已包含 cls + 字体）。华中杯模板使用 `\begin{abstract}...\keywords{}\end{abstract}` 环境写摘要（不是手动排版），参考文献用 `\begin{thebibliography}` 环境（不是 `\bibliography{}`）。



```

摘要（~1页，含关键词）

1 问题重述

2 模型假设

3 符号说明

4 问题一的建模与求解（each sub-problem gets its own chapter）

5 问题二的建模与求解

6 问题三的建模与求解

7 灵敏度分析与模型检验

8 模型评价与推广

参考文献

附录 A：代码

```

**⛔ 国赛提交文件命名规则（强制）**：

1. **所有提交文件必须以中文命名**，例如：`论文.pdf`、`代码说明.txt`、`支撑材料.pdf`、`AI工具使用详情.pdf`
2. **禁止使用英文文件名**提交，如 `paper.pdf`、`code_description.txt` 等
3. **程序说明仅使用 TXT 文件**（`代码说明.txt`），不使用 Markdown 或其他格式
4. **压缩包命名**：`参赛编号+队号.zip`（如 `20260001_A01.zip`），内部文件中文命名

**⛔ AI工具使用声明规则（2026国赛强制）**：

1. **声明位置**：AI工具使用声明必须放在**参考文献之前**，不能放在附录中
2. **声明内容**：仅声明以下两项使用了AI：
   - **资料查询**：使用AI辅助检索文献、查找数据来源
   - **语言润色**：使用AI辅助润色论文语言表达
3. **禁止声明**：不要声明代码编写、图表制作、建模求解等环节使用了AI（即使实际使用了，也只需声明资料查询和润色）
4. **声明格式**：使用 `ai_usage_declaration.py` 工具生成，或手动写入以下内容：

```latex
\section*{AI工具使用声明}
本参赛队在竞赛过程中使用了AI工具，主要用于资料查询和语言润色，详细使用情况见支撑材料。
```



### 统计建模 (stats)



Template: `templates/stats/main.tex`



**Chapter structure is driven by research content, not fixed templates.**



Award-winning stats modeling papers vary wildly in structure — some organize by model, some by analysis step, some by research question. There is no "standard structure". Claude must design chapters autonomously based on the actual content in TOPIC_PLAN.md / MODELING_REPORT.md.



#### Fixed skeleton (must keep)



```

表格清单

插图清单

摘要（中英文，分页）

一、绪论/前言（研究背景 + 文献综述/研究现状 + 研究目标/内容）

  ↓

  [Middle chapters: content-driven, Claude designs autonomously, typically 3-5 chapters]

  ↓

N、结论与建议（结论 + 建议/展望 + 创新与不足）

参考文献

致谢

附录（代码）

```



#### Middle chapter design guide



After reading TOPIC_PLAN.md, design middle chapters following these principles:



**Principle 1: Chapter titles must be specific, not generic**

- ✗ "四、模型构建" → ✓ "四、基于 CNN 的水质预测模型构建与评价"

- ✗ "五、实证分析" → ✓ "五、生育意愿的影响因素——集成学习模型"



**Principle 2: Organize by research logic chain, not by textbook methodology**

- If the research has multiple sub-problems/models, each model can be its own chapter

- If the research uses a single method with deep analysis, organize by analysis steps



**Principle 3: Data and method chapters can be merged or separated**

- Simple data (one dataset) → merge into "数据与方法"

- Complex data (multi-source, heavy preprocessing) → separate chapter "数据描述与预处理"



#### Award-winning paper structure examples (reference only, do not copy)



**Example A — Classification + Path Analysis (fertility intention)**:

前言 → 模型构建 (introduce ensemble + Bayesian network) → 数据说明和预处理 → 探索性特征分析 → 生育意愿的影响因素 (ensemble results) → 生育意愿影响路径 (Bayesian network results) → 结论与建议



**Example B — Mixed Modeling (data factors & economic growth)**:

研究背景+文献 → 研究思路和模型介绍 → 理论分析 → 模型构建 (production function + regression + ARIMA, each a section) → 模型应用 (GDP prediction) → 总结与建议 → 创新与不足



**Example C — DEA Evaluation (economic sustainability)**:

绪论 → 文献综述 → 研究区域概况 → 评价指标体系构建 → 数据优化处理 (normalization + PCA) → DEA 模型建立及求解 → 结论及建议



**Example D — Deep Learning Prediction (water quality CNN)**:

绪论 → 模型构建思路与创新 → 数据描述及预处理 → 主成分分析 → CNN 模型构建与评价 (with model comparison) → 结论与展望



**Key observations**:

- No award-winning paper uses the "baseline regression → robustness → heterogeneity" causal inference structure (unless the topic IS causal inference)

- Chapter count varies from 5-7, determined by content

- "Model introduction / theoretical basis" can come before or after the data chapter

- "Innovation & limitations" can be inside the conclusion or a standalone chapter



#### Chapter design checklist (self-check before writing)



- [ ] Does every chapter title contain specific research content (not generic "模型构建")?

- [ ] Does the chapter order follow the research logic chain (reader can follow naturally)?

- [ ] Do core analysis chapters (model results) occupy 40-50% of the paper?

- [ ] Is there a dedicated data description / exploratory analysis chapter (reviewers value data understanding)?

- [ ] Does the conclusion include "innovation" and "limitations" (reviewer bonus points)?



Use Chinese numbering (一、二、三...) with sub-sections (一)(二)(三). Do not use 1、2、3 or 1.1、1.2 format.

Fixed sections that must be kept: 表格清单, 插图清单, 中英文摘要, 绪论, 结论, 参考文献, 致谢.

</paper_structure>



## ⛔⛔⛔ 完成铁律（最高优先级）



**根据 `params.output_format` 决定主产物**：



- **PDF 模式（默认）**：`paper/main.tex`（≥ 5KB）+ `paper/sections/*.tex` + `paper/references.bib`

- **docx 模式**：`paper/main.md`（单文件，≥ 5KB）。**禁止产 paper/main.tex**



⛔ **结束前必跑产出验证**：

```bash

MODE=$(grep -q "Word（.docx）" CLAUDE.md 2>/dev/null && echo docx || echo pdf)

echo "MODE: $MODE"

PASS=true

if [ "$MODE" = "docx" ]; then

    [ -f paper/main.md ] && SZ=$(wc -c < paper/main.md) || SZ=0

    [ "$SZ" -ge 5120 ] && echo "✅ paper/main.md ($SZ)" || { echo "❌ paper/main.md 缺失或过小"; PASS=false; }

else

    [ -f paper/main.tex ] && SZ=$(wc -c < paper/main.tex) || SZ=0

    [ "$SZ" -ge 5120 ] && echo "✅ paper/main.tex ($SZ)" || { echo "❌ paper/main.tex 缺失或过小"; PASS=false; }

    SECT_COUNT=$(ls paper/sections/*.tex 2>/dev/null | wc -l)

    [ "$SECT_COUNT" -ge 3 ] && echo "✅ sections ($SECT_COUNT)" || { echo "❌ 章节过少"; PASS=false; }

fi

[ "$PASS" != true ] && echo "⛔ 产出验证失败 — 必须补全后重新跑验证, 不要结束本步骤"

```



## Workflow



### Step 0: Backup + resume check + upstream validation



**⛔ 上游输出完整性检查（写论文前必做）：**

```bash

echo "=== 上游输出完整性检查 ==="

UPSTREAM_OK=true



# 1. 核心文件是否存在

for f in PROBLEM_ANALYSIS.md MODELING_REPORT.md RESULTS.md; do

    if [ -f "$f" ]; then

        sz=$(wc -c < "$f")

        echo "✅ $f ($sz 字符)"

        [ "$sz" -lt 500 ] && echo "  ⚠ 文件过小，内容可能不完整"

    else

        echo "❌ $f 不存在！"

        UPSTREAM_OK=false

    fi

done



# 2. 子问题覆盖度：赛题分析 vs 建模报告 vs 代码结果

#    统一口径（历史 bug：这里正则漏了 0-9，"问题1/问题2"数不出来 → 覆盖度检查静默失效）

PROB_COUNT=$(bash _utils/count_subproblems.sh PROBLEM_ANALYSIS.md)

MODEL_COUNT=$(bash _utils/count_subproblems.sh MODELING_REPORT.md)

RESULT_FILES=$(ls figures/problem_*_results.json 2>/dev/null | wc -l)

echo "子问题数: 分析=$PROB_COUNT, 建模=$MODEL_COUNT, 代码结果=$RESULT_FILES"

[ "$MODEL_COUNT" -lt "$PROB_COUNT" ] && echo "⚠ 建模报告覆盖子问题数少于赛题分析"

[ "$RESULT_FILES" -lt "$PROB_COUNT" ] && echo "⚠ 代码结果文件数少于子问题数"



# 3. 图表文件是否存在

PDF_COUNT=$(ls figures/*.pdf 2>/dev/null | wc -l)

echo "PDF 图表: $PDF_COUNT 个"

[ "$PDF_COUNT" -eq 0 ] && echo "⚠ 没有 PDF 图表，论文将缺少图片"



# 4. all_results.json 是否存在

[ -f figures/all_results.json ] && echo "✅ all_results.json 存在" || echo "⚠ all_results.json 不存在，论文数值可能不准确"



# 5. latex_includes.tex 是否存在

[ -f figures/latex_includes.tex ] && echo "✅ latex_includes.tex 存在" || echo "⚠ latex_includes.tex 不存在，图表嵌入代码缺失"



echo "=== 上游检查完成 ==="

```



**⛔⛔ 能力验收闸门（写论文前必做，承接全链合同的最后一环，零额度两模式都跑）：** 论文是最终交付物，绝不能把没做到/做砸的能力写成成果。写正文前先核编码阶段的能力验收总账：

```bash

FAST_MODE=0; grep -q 'MH_FAST_MODE=1' CLAUDE.md 2>/dev/null && FAST_MODE=1

python _utils/paper_claim_check.py --audit CAPABILITY_AUDIT.md --checklist CAPABILITY_CHECKLIST.json --sections paper/sections --fast $FAST_MODE

PCC=$?   # 0=全通过可写 1=有能力项未通过(FAIL/严格模式PENDING,不该写) 2=无总账跳过

```

> `PCC=1` 说明有能力项在编码阶段验收就没通过（FAIL/PENDING）——**回到 comp-code 把它真做到 PASS，再来写论文**，别把没做成的能力写进最终稿。写完正文后本闸会再跑一次（见 Step 6），那次还会扫正文有没有"吹了没通过的能力"。⛔ 承上启下收口：赛题分析定合同 → 建模认领 → 编码实现验收 → **论文只如实书写验收通过的成果**。



Back up existing `paper/`. Check for incomplete sections from previous runs:

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

Resume rules: only write placeholder sections (<500 chars or contains "待补充"/"placeholder"), skip completed ones (>2000 chars). Save each chapter immediately — do not accumulate in memory.



### Step 1: Copy template (based on COMPETITION type)



```bash

mkdir -p paper/sections

# Select template based on competition type — copy entire folder (tex + cls + fonts)

TMPL_BASE="_templates"

[ -d "$TMPL_BASE" ] || TMPL_BASE="templates"



if [ "$COMPETITION" = "stats" ] || echo "$ARGUMENTS" | grep -qi "统计建模\|stats"; then

    echo "Using stats template"

    cp "$TMPL_BASE/stats/"* paper/ 2>/dev/null

elif echo "$ARGUMENTS" | grep -qi "apmcm_zh\|亚太.*中文\|亚太赛中文" || grep -qi "apmcm_zh\|亚太.*中文\|亚太赛中文" CLAUDE.md 2>/dev/null; then

    echo "Using APMCM (Chinese) template (MathorCupmodeling.cls)"

    cp "$TMPL_BASE/apmcm_zh/"* paper/ 2>/dev/null

elif echo "$ARGUMENTS" | grep -qi "mathorcup\|MathorCup\|mathor" || grep -qi "mathorcup" CLAUDE.md 2>/dev/null; then

    echo "Using MathorCup template"

    cp "$TMPL_BASE/mathorcup/"* paper/ 2>/dev/null

elif echo "$ARGUMENTS" | grep -qi "huazhong\|华中杯" || grep -qi "huazhong\|华中杯" CLAUDE.md 2>/dev/null; then

    echo "Using huazhong template"

    cp "$TMPL_BASE/huazhong/"* paper/ 2>/dev/null

elif echo "$ARGUMENTS" | grep -qi "huawei\|华为杯" || \

     grep -qE "^## 竞赛规则.*华为杯|^- 赛事:\s*comp_huawei" CLAUDE.md 2>/dev/null; then

    # ⛔ 模板选择必须精确：只在"## 竞赛规则（华为杯...）"标题行或显式 "- 赛事: comp_huawei" 命中

    # 不能用泛泛的 `grep huawei CLAUDE.md` — 丰满模式 / 其他描述文字可能含"华为杯"字眼误触发

    echo "Using huawei template"

    cp "$TMPL_BASE/huawei/"* paper/ 2>/dev/null

elif echo "$ARGUMENTS" | grep -qi "wuyi\|五一杯" || grep -qi "wuyi\|五一杯" CLAUDE.md 2>/dev/null; then

    echo "Using wuyi template"

    cp "$TMPL_BASE/wuyi/"* paper/ 2>/dev/null

elif echo "$ARGUMENTS" | grep -qi "cumcm\|国赛" || grep -qi "cumcm\|国赛" CLAUDE.md 2>/dev/null; then

    echo "Using cumcm template"

    cp "$TMPL_BASE/cumcm/"* paper/ 2>/dev/null

elif echo "$ARGUMENTS" | grep -qi "changsanjiao\|长三角" || grep -qi "changsanjiao\|长三角" CLAUDE.md 2>/dev/null; then

    echo "Using changsanjiao template"

    cp "$TMPL_BASE/changsanjiao/"* paper/ 2>/dev/null

elif echo "$ARGUMENTS" | grep -qi "huashu\|华数杯" || grep -qi "huashu\|华数杯" CLAUDE.md 2>/dev/null; then

    echo "Using huashubei template"

    cp "$TMPL_BASE/huashubei/"* paper/ 2>/dev/null

elif echo "$ARGUMENTS" | grep -qi "diangong\|电工杯" || grep -qi "diangong\|电工杯" CLAUDE.md 2>/dev/null; then

    echo "Using diangongbei template"

    cp "$TMPL_BASE/diangongbei/"* paper/ 2>/dev/null

elif echo "$ARGUMENTS" | grep -qi "dongsansheng\|东三省\|辽宁" || grep -qi "dongsansheng\|东三省\|辽宁" CLAUDE.md 2>/dev/null; then

    echo "Using dongsansheng template"

    cp "$TMPL_BASE/dongsansheng/"* paper/ 2>/dev/null

elif echo "$ARGUMENTS" | grep -qi "shuwei\|数维杯" || grep -qi "shuwei\|数维杯" CLAUDE.md 2>/dev/null; then

    echo "Using shuweibei template"

    cp "$TMPL_BASE/shuweibei/"* paper/ 2>/dev/null

else

    echo "Using default template"

    cp "$TMPL_BASE/default/"* paper/ 2>/dev/null

fi

# Rename to main.tex if needed

[ -f paper/main.tex ] && echo "Template copied: $(wc -l < paper/main.tex) lines" || echo "ERROR: template not found!"

```



**⛔ 模板复制后立即验证（必须通过才能继续）：**

```bash

echo "=== 模板完整性验证 ==="

if [ ! -f paper/main.tex ]; then

    echo "❌ CRITICAL: paper/main.tex 不存在！模板复制失败"

else

    # 通用检查

    grep -q 'documentclass' paper/main.tex && echo "✅ documentclass 存在" || echo "❌ 缺少 documentclass"

    grep -q '\\input{sections/' paper/main.tex && echo "✅ sections input 存在" || echo "❌ 缺少 sections input"

    grep -q 'thebibliography\|bibliography{' paper/main.tex && echo "✅ 参考文献结构存在" || echo "❌ 缺少参考文献"

    grep -q 'appendices\|\\appendix' paper/main.tex && echo "✅ 附录结构存在" || echo "❌ 缺少附录"



    # ⛔ 模板指纹校验：对比 paper/main.tex 和模板原文，确认是复制的不是 Claude 自己写的

    TMPL_BASE="_templates"

    [ -d "$TMPL_BASE" ] || TMPL_BASE="templates"

    # 找到当前使用的模板原文

    TMPL_MAIN=""

    for d in "$TMPL_BASE"/*/; do

        [ -f "${d}main.tex" ] || continue

        # 用 documentclass 行匹配

        TMPL_CLS=$(grep 'documentclass' "${d}main.tex" 2>/dev/null | head -1)

        PAPER_CLS=$(grep 'documentclass' paper/main.tex 2>/dev/null | head -1)

        if [ "$TMPL_CLS" = "$PAPER_CLS" ]; then

            TMPL_MAIN="${d}main.tex"

            break

        fi

    done



    if [ -n "$TMPL_MAIN" ]; then

        echo "模板原文: $TMPL_MAIN"

        # 对比前 20 行（preamble 部分），如果差异超过 5 行说明被重写了

        DIFF_COUNT=$(diff <(head -20 "$TMPL_MAIN") <(head -20 paper/main.tex) 2>/dev/null | grep -c '^[<>]')

        if [ "$DIFF_COUNT" -gt 10 ]; then

            echo "❌ CRITICAL: paper/main.tex 的 preamble 和模板差异过大（$DIFF_COUNT 行不同）— 可能被重写了！"

            echo "⛔ 强制从模板重新复制..."

            cp paper/main.tex paper/main.tex.broken 2>/dev/null

            TMPL_DIR=$(dirname "$TMPL_MAIN")

            cp "$TMPL_DIR"/* paper/ 2>/dev/null

            echo "✅ 模板已重新复制（旧文件备份为 main.tex.broken）"

        else

            echo "✅ 模板指纹校验通过（preamble 差异 $DIFF_COUNT 行，在允许范围内）"

        fi

    else

        echo "⚠ 未找到匹配的模板原文，跳过指纹校验"

    fi

fi

```



Read the copied template to understand its structure before writing:

```bash

cat paper/main.tex

```



**⛔ 你必须完整读取 main.tex 模板内容。后续写章节时，只修改 sections/*.tex 文件，不要重写 main.tex。**



Use the template as-is. Only modify:

- Replace bracket placeholders (`[论文标题]`, `[中文摘要内容]`, etc.) with actual content

- Replace `\input{sections/...}` filenames if your section files have different names

- Fill in the abstract and keywords



**⛔ CRITICAL TEMPLATE RULES (violation = broken PDF):**



1. **NEVER rewrite main.tex from scratch** — the template has 100+ lines of carefully tuned preamble (fonts, margins, section numbering, citation format). Writing from scratch will break fonts, margins, and formatting.



2. **NEVER replace `\listoftables`/`\listoffigures` with hand-written text lists** — the template uses LaTeX auto-generated lists. If you write "表1.xxx\n表2.yyy" manually, the list won't update when tables change.



3. **NEVER add a separate cover page for MathorCup** — MathorCup 官方格式没有独立封面。队伍编号表格+标题+摘要都在第一页。不要自己加 `\maketitle` 或写一个大标题封面。直接用模板里的格式：表格 → 分隔线 → 标题 → 摘要。



4. **NEVER change the cover page year/届数 format** — replace `[竞赛年份]` with the actual year (e.g., `2026`), `[届数]` with the actual number (e.g., `十二`).



5. **Verify after writing**: `diff paper/main.tex` against the template — only bracket placeholders and `\input` lines should differ.



6. **MathorCup 模板验证**：检查 main.tex 使用 `\documentclass{MathorCupmodeling}`，`\bianhao{}`/`\tihao{}`/`\timu{}` 已填写。



7. **华中杯模板验证**：检查 `\documentclass[withoutpreface,bwprint]{cumcmthesis}` 未被修改，摘要使用 `\begin{abstract}...\keywords{}\end{abstract}` 环境，参考文献使用 `\begin{thebibliography}{99}...\end{thebibliography}`，附录使用 `\begin{appendices}...\end{appendices}`，不要自己加 `\usepackage{geometry}`。



8. **⛔ 华为杯专属：模板与标题约束（gmcmthesis，只对华为杯生效）**：



   下面这段自检脚本**仅在华为杯工作流执行**（用 grep huawei 包住，其他竞赛跳过保持原本行为）：



   ```bash

   # 仅华为杯触发以下标题检查（其他竞赛跳过）

   if grep -qi "huawei\|华为杯" CLAUDE.md 2>/dev/null; then

       title_line=$(grep -oE '\\title\{[^}]+\}' paper/main.tex | head -1)

       echo "[华为杯] Title: $title_line"



       # 1. 禁止 \\ 强制换行（避免第二行字号变小 bug，gmcmthesis v1.5.0+ 已支持自动按宽度换行）

       if echo "$title_line" | grep -qE '\\\\'; then

           echo "⛔ [华为杯] \\title{} 含 \\\\ 强制换行 — 改成单行让 cls 自动换行"

       fi



       # 2. 拦截 AI 美化标题（华为杯严禁自创标题，必须用赛题官方原标题）

       if echo "$title_line" | grep -qE '(基于.*的|.*的研究|.*的应用|.*的探索|.*：一种)'; then

           echo "⚠ [华为杯] 标题含 AI 风格修饰词 — 华为杯必须严格使用赛题官方标题，不能自创"

           echo "  反例：⛔ '基于 X 的 Y 研究' / ⛔ 'Y 的探索与应用' / ⛔ 'Y：一种基于 X 的方法'"

           echo "  正确：直接抄赛题题面给的官方标题（不改一个字）"

       fi



       # 3. 提示对照赛题原始文本

       if ls user_data/*_extracted.txt >/dev/null 2>&1; then

           echo "[华为杯] 赛题文件前 5 行（请确认 \\title{} 与赛题官方标题一致）:"

           head -5 user_data/*_extracted.txt 2>/dev/null | head -15

       fi

   fi

   ```



   **⛔ 华为杯标题硬约束（其他竞赛保持原本，不受影响）**：

   - `\title{...}` 必须使用赛题官方原标题（从 `user_data/*_extracted.txt` 抄），严禁自创 "基于 X 的 Y"

   - 不要在 `\title{}` 里写 `\\` 换行（cls v1.5.0+ 已支持自动按宽度换行，多行字号保持一致）

   - 题目长就一行写完，模板自动换行渲染



9. **五一杯模板验证**：检查承诺书页完整保留，摘要使用手动排版（`\noindent \textbf{关键词：}` 在上，`\noindent \textbf{摘\quad 要：}` 在下，不用 `\begin{abstract}` 环境），参考文献使用 `\begin{thebibliography}`，附录第一节是文件列表表格。**⛔ 五一杯额外检查**：(a) 不要加 `\usepackage{cite}`（和 natbib 冲突会导致编译错误），(b) 不要重复加载 `\usepackage{subcaption}` 和 `\usepackage{float}`（cls 已包含），(c) 不要加 `\maketitle`（五一杯用手写承诺书页，不用 cls 的 maketitle），(d) 不要删除 `withoutpreface` 选项。



The cover page uses `\fzxbsong` (方正小标宋) and `\fsgb` (仿宋GB2312) fonts with `\cline{2-2}` underlines in a tabular. These fonts have fallback definitions — if the .ttf files are not installed, they fall back to `\heiti` and `\fangsong`.



When replacing cover page placeholders, ONLY change the text inside `[...]` brackets. Do NOT touch `\cline{2-2}`, `\\`, `&`, or any LaTeX commands:

```latex

% Template has (和 cover station.tex 格式一致):

参赛学校：&[学校名称]\\\cline{2-2}

% Replace ONLY the bracket text:

参赛学校：&某某大学\\\cline{2-2}

% NEVER remove \cline{2-2} (creates underline) or & (column separator)

```



Do NOT modify:

- `\documentclass` line (font size, paper size)

- `\usepackage[...]{geometry}` (page margins)

- `\ctexset{section=...}` (chapter numbering format)

- `\pagestyle` / `\fancyhf` (header/footer)

- `\usepackage[...]{natbib}` or `\usepackage[...]{gbt7714}` (citation format)

- Cover page structure (封面布局)

- `\listoftables` / `\listoffigures` (表格与插图清单 — 自动生成，不要手写)

- Anything before `\begin{document}` (preamble)

- The cover page, abstract, TOC, and bibliography sections in main.tex — only replace placeholder text within them



Write all chapter content in separate `paper/sections/*.tex` files. The main.tex `\input{sections/...}` lines load them automatically. Do not paste chapter content directly into main.tex.



If you need to add packages, add them after the existing `\usepackage` block, before `\begin{document}`.



Do not write main.tex from scratch — the template handles fonts, spacing, margins, citation format, headers/footers.



Note: citation command depends on the template. **stats / huawei / dongsansheng / apmcm_zh / mathorcup / huashubei** load `natbib` with the `super`(or `\setcitestyle{super}`) option → use `\cite{key}` directly (auto-superscript). **cumcm / wuyi** load `natbib[numbers]` **without** super → `\cite` gives inline `[1]`, so body text MUST use `\upcite{key}` to get superscript. **huazhong / apmcm / changsanjiao / diangongbei / shuweibei / mcm** use a manual `\@cite` superscript hack (or manual thebibliography) → use `\cite{key}` directly. ⛔ `\upcite` is ONLY defined in cumcm / huazhong / wuyi / dongsansheng — do NOT use `\upcite` in any other template (undefined → compile error); use `\cite` there.



Do not redefine LaTeX built-in commands (`\sin`, `\cos`, `\tanh`, `\log`, `\exp`, `\max`, `\min`, etc.) in math_commands.tex.



### Step 2: Abstracts



**⛔ CRITICAL: Do NOT write the abstract now.** Skip this step entirely. Write a placeholder `[摘要待正文完成后填写]` in the abstract section. The abstract MUST be written LAST (after Step 5) because it needs specific numerical results from all chapters. Writing it first = making up numbers.



Come back to fill the abstract in Step 5 (final check), after all body chapters are complete. At that point, read RESULTS.md and all section .tex files to extract the actual numbers.



<abstract_format>

The template uses manual typesetting for abstracts. Do not use two `\begin{abstract}` environments — ctexart shows "摘要" as title for both.



**⛔ 华中杯例外**：华中杯模板基于 `cumcmthesis` 文档类，使用 `\begin{abstract}...\keywords{}\end{abstract}` 环境。不要改成手动排版格式。正确写法：

```latex

\begin{abstract}

[中文摘要内容，400-600字]

\keywords{[关键词1]\quad [关键词2]\quad [关键词3]}

\end{abstract}

```



**⛔ 五一杯说明**：五一杯模板有承诺书页（第一页）和封面页（第二页）。**五一杯摘要使用手动排版（不用 `\begin{abstract}` 环境）**：关键词在上（`\noindent \textbf{关键词：}...`），摘要在下（`\noindent \textbf{摘\quad 要：}`）。这是五一杯官方格式，跟国赛/华中杯不同。承诺书页不要删除。



Correct format for cumcm/stats templates (already in template):

```latex

% === 中文摘要 ===

\begin{center}

{\zihao{3}\heiti 摘\hspace{2em}要}

\end{center}

\zihao{-4}\songti

[中文摘要内容，600-800字，写满一整页]

\noindent\textbf{关键词：}...



% === 英文摘要（新页）===

\newpage

\begin{center}

{\zihao{3}\bfseries Abstract}

\end{center}

[English abstract, 400-600 words, faithful translation]

\noindent\textbf{Keywords:} ...

```



**数模竞赛摘要（国赛/MathorCup/APMCM/五一杯等通用）**: 400-600 字, every sub-problem must have specific numerical results。



⛔⛔ **必须按问题分段，绝不允许所有问题挤成一大段。** 段骨架：

- 第 1 段：背景概述 + 整体建模思路

- 第 2 段起：**每个"针对问题 X"独占一段**（方法 + 具体数值结果）

- 末段：模型评价与推广

- **段间强制用 LaTeX 空行分隔**（源码里空一行 = 一个新段落）。五一杯手动排版摘要，分段规则同样适用。



⛔⛔ **摘要关键内容加粗（只在摘要正文，用 LaTeX `\textbf{}`）**：评审快速扫读摘要抓重点，把最关键的方法与结果加粗是加分项。**只加粗以下三类"结论锚点"**：

1. **关键结果数值**（最终答案数字）：如 `\textbf{2376.8}`、`\textbf{98.7\%}`、`\textbf{12.4 km}`（注意 `%` 在 LaTeX 里要写 `\%`）

2. **核心方法/模型名**：如 `\textbf{NSGA-II}`、`\textbf{灰色预测 GM(1,1)}`——**每个方法名只在首次出现或结论处加粗一次**，不是每次提到都加

3. **关键结论的核心名词**



⛔ **加粗铁律（防加粗过多反而杂乱，宁少勿多）**：

- 每段 **1~3 处**，全篇 **≤ 12 处**。超了就是错。

- **禁止**：整句 `\textbf{}`、背景铺垫加粗、连接词加粗、同一方法名反复加粗。

- ⛔ 只用 `\textbf{}`（LaTeX），**不要用 markdown `**xxx**`**（LaTeX 下 `**` 不渲染成粗体、会原样显示）。

- ⛔ **不影响关键词行**：`\textbf{关键词：}` 那个加粗是标签本身，照旧。

- ⛔ `\textbf{}` 只包文字，**数字本身必须仍从正文如实摘出**，不能因加粗改动或编造。

- ⛔ 五一杯等手动排版摘要同样适用（`\textbf{}` 在正文任意位置都合法）。



正例：`本文构建 \textbf{NSGA-II} 多目标模型，求得最优成本 \textbf{2376.8 万元}，较基线降低 \textbf{12.3\%}。`



⛔ **硬约束：一个自然段里绝不允许出现两个及以上"针对问题"。** 正反例：



```latex

（正确 ✅ — 每个"针对问题 X"之间空一行，各自独立成段）

本文针对……建立了……模型。



针对问题一，首先……，采用……算法，最优解为……，适应度达 0.917。



针对问题二，构建……模型，……MAPE 由 29.48\% 降至 14.93\%。



针对问题三，……预测结果为 952.8、1570.5、11030.9。



灵敏度分析表明……，模型评价显示……。

```



```latex

（错误 ❌ — 问题二/三挤在同一段，评委无法按问题快速定位）

针对问题二，构建……模型，MAPE 14.93\%。针对问题三，预测结果为 952.8、1570.5。

```



⛔ **写完摘要后跑自检（检测→修复→再检测闭环，用 `python` 不是 `python3`）**：

```bash

# 中文竞赛摘要通常在 main.tex 的 \begin{abstract} 环境（国赛/华中杯/MathorCup）

# 或 main.tex 手动排版段（五一杯），少数模板在 sections/0_*.tex — 定位逻辑已内置，直接跑：

python - <<'PY'

import re, os, glob, sys

BS = chr(92)  # 反斜杠。不要在本脚本里写双反斜杠——经 bash 传输可能被折叠成单反斜杠，弄坏正则



def locate_abstract():

    """按优先级提取摘要文本，返回 (文本, 位置描述)；找不到返回 (None, None)"""

    mt = "paper/main.tex"

    if os.path.isfile(mt):

        s = open(mt, encoding="utf-8", errors="ignore").read()

        # 1) abstract 环境（国赛/华中杯/MathorCup）：用字符串 find，避免正则转义

        beg, end = BS + "begin{abstract}", BS + "end{abstract}"

        i0, i1 = s.find(beg), s.find(end)

        if i0 != -1 and i1 > i0:

            inner = s[i0 + len(beg) : i1]

            if "针对问题" in inner:

                return inner, "paper/main.tex 的 abstract 环境"

        # 2) 五一杯手动排版：从"摘…要"标记（容忍 quad/hspace/全角空格）到 section/关键词 为止

        m = re.search("摘[^要]{0,16}要", s)

        if m:

            tail = s[m.end():]

            stops = [x for x in (tail.find(BS + "section"), tail.find("关键词")) if x != -1]

            seg = tail[: min(stops)] if stops else tail[:4000]

            if "针对问题" in seg:

                return seg, "paper/main.tex 的手动排版摘要段"

    # 3) 兜底：个别模板把摘要放 sections/

    for pat in ("paper/sections/0_*.tex", "paper/sections/*abstract*.tex"):

        for f in sorted(glob.glob(pat)):

            s = open(f, encoding="utf-8", errors="ignore").read()

            if "针对问题" in s:

                return s, f

    return None, None



text, where = locate_abstract()

if text is None:

    print("⚠ 未定位到含'针对问题'的摘要文本（可能尚未写摘要），跳过自检"); sys.exit(0)

bad = []

for i, para in enumerate(re.split(r"\n\s*\n", text), 1):

    if len(re.findall(r"针对问题", para)) > 1:

        bad.append((i, para.strip()[:80]))

if bad:

    print(f"❌ 摘要（{where}）中 {len(bad)} 个段落挤了多个'针对问题' — 必须每个独立成段（段间空一行）：")

    for i, snip in bad:

        print(f"  段 {i}: {snip}...")

    sys.exit(1)

print(f"✓ 摘要按问题分段正确（{where}）")

# ── 新增：写作风格量化检查 ──
print()
print("=== Writing Style Quantitative Check ===")

# 1) 短句占比 (<20字)
import re, os
BS = chr(92)
mt = "paper/main.tex"
s, where = None, None
if os.path.isfile(mt):
    with open(mt, encoding="utf-8", errors="ignore") as f:
        s = f.read()
    beg, end = BS + "begin{abstract}", BS + "end{abstract}"
    i0, i1 = s.find(beg), s.find(end)
    if i0 != -1 and i1 > i0:
        s = s[i0 + len(beg):i1]
        where = "paper/main.tex abstract environment"
    else:
        m = re.search("摘[^要]{0,16}要", s)
        if m:
            tail = s[m.end():]
            stops = [x for x in (tail.find(BS + "section"), tail.find("\u5145\u94fe\u8bed")) if x != -1]
            seg = tail[:min(stops)] if stops else tail[:4000]
            if "\u5针对问题" in seg:
                s = seg
                where = "paper/main.tex manual paragraph"

if s is None:
    print("⚠ 未定位到摘要，跳过风格检查")
else:
    # 按双新行分割段落
    paragraphs = re.split(r"\n\s*\n", s)
    short_sentences = 0
    for p in paragraphs:
        clean = re.sub(r"\\.[^\\s]*|{[^}]*}", "", p)
        clean = re.sub(r"\\s+", "", clean)
        if len(clean) > 0 and len(clean) < 20:
            short_sentences += 1
    short_ratio = short_sentences / len(paragraphs) if len(paragraphs) > 0 else 0
    print(f"段落数: {len(paragraphs)}, 短句(<20字): {short_sentences}, 占比: {short_ratio:.1%}")
    if short_ratio > 0.5:
        print("⚠ 短句占比过高 (>50%)——可能过于口语化，建议加大学术词汇连接")
    else:
        print("✓ 短句占比适中")

    # 2) 学术词汇密度
    academic_kw = ["建立", "提出", "采用", "模型", "算法", "分析", "结果", "结论", "理论", "方法", "研究", "实验", "数据", "统计", "回归", "优化", "证明", "推导", "公式", "方程"]
    clean_text = re.sub(r"\\\[.*?\\\]", "", s)
    clean_text = re.sub(r"\\\\begin.*?\\\\end", "", clean_text, flags=re.DOTALL)
    clean_text = re.sub(r"\\\(.*?\\\)", "", clean_text)
    clean_text = re.sub(r"\\\\text\{.*?\\\\}", "", clean_text)
    ac_count = 0
    for kw in academic_kw:
        ac_count += len(re.findall(kw, clean_text))
    char_count = len(clean_text)
    if char_count > 0:
        acad_density = ac_count / char_count * 1000
        print(f"学术词汇密度: {acad_density:.2f} per 1000 chars (建议: ≥1.0%)")
        if acad_density < 1.0:
            print("⚠ 学术词汇密度偏低——建议加入更多学术词汇")
        else:
            print("✓ 学术词汇密度健康")

    # 3) 被动语态占比
    passive_patterns = [r"是.*?(?:得到|产生|形成|获得)", r"由.*?所构成", r"被.*?模型", r"可被|可以被"]
    passive_count = 0
    for pat in passive_patterns:
        passive_count += len(re.findall(pat, s))
    passive_ratio = passive_count / len(paragraphs) if len(paragraphs) > 0 else 0
    print(f"被动语态检测项: {passive_count} 处，占比估计: {passive_ratio:.1%}")
    if passive_ratio > 0.05:
        print("⚠ 被动语态占比偏高——建议精简，改用主动语态")
    else:
        print("✓ 被动语态占比适度")

    # 4) 高频连接词检查
    conn_kw = ["通过", "基于", "针对", "考虑", "作为", "因此", "但是", "然而"]
    conn_count = 0
    for kw in conn_kw:
        conn_count += len(re.findall(kw, s))
    print(f"高频连接词出现: {conn_count} 次（'通过'/'基于'/'针对'为Top 3）")
    unique_conn = len(set(re.findall(conn_kw[0] + "|" + conn_kw[1] + "|" + conn_kw[2], s)))
    print(f"Top3连接词变体: {unique_conn} 处")

print("=== Writing Style Quantitative Check END ===")
# NEW_ABSTRACT_CHECK_BLOCK_START
print()
print("=== Abstract Quality Self-Check ===")
def check_abstract_elements(text, mode="unknown"):
    issues = []
    # Background
    bg_patterns = ["随着", "最近", "针对"]
    has_bg = any(re.search(p, text) for p in bg_patterns)
    if not has_bg:
        issues.append("WARNING: Lacking background-intro opening")
    # Method
    method_kw = ["建立", "提出", "采用", "模型", "算法"]
    has_method = any(kw in text for kw in method_kw)
    if not has_method:
        issues.append("WARNING: No explicit method description")
    # Results
    result_count = len(re.findall(r"\\textbf\{[0-9.%,\s]+\}", text))
    if result_count < 3:
        issues.append("Results only " + str(result_count) + " numbers")
    else:
        print("OK: Abstract result count " + str(result_count) + " (>=3)")
    # Conclusion
    conclusion_kw = ["表明", "验证", "证明", "得出", "结论"]
    has_conclusion = any(kw in text for kw in conclusion_kw)
    if not has_conclusion:
        issues.append("WARNING: No concluding summary")
    return issues

# Locate abstract
BS = chr(92)
mt = "paper/main.tex"
text, where = None, None
if os.path.isfile(mt):
    s = open(mt, encoding="utf-8", errors="ignore").read()
    beg, end = BS + "begin{abstract}", BS + "end{abstract}"
    i0, i1 = s.find(beg), s.find(end)
    if i0 != -1 and i1 > i0:
        text = s[i0 + len(beg):i1]
        where = "paper/main.tex of abstract environment"
    else:
        m = re.search("摘[^要]{0,16}要", s)
        if m:
            tail = s[m.end():]
            stops = [x for x in (tail.find(BS + "section"), tail.find(充链语)) if x != -1]
            seg = tail[:min(stops)] if stops else tail[:4000]
            if "针对问题" in seg:
                text = seg
                where = "paper/main.tex of manual abstract paragraph"
    if text is None:
        for pat in ("paper/sections/0_*.tex", "paper/sections/*abstract*.tex"):
            for f in sorted(glob.glob(pat)):
                s2 = open(f, encoding="utf-8", errors="ignore").read()
                if "针对问题" in s2:
                    text = s2
                    where = f
                    break
        if text: break

if text is None:
    print("Warning: Cannot locate abstract, skipping element check")
    import sys; sys.exit(0)

issues = check_abstract_elements(text, where or "unknown")
if issues:
    print("The following elements need attention:")
    for i in issues:
        print("  " + i)
    print("Non-blocking but recommended to fix during writing.")
else:
    print("OK: All 4 abstract elements present: background/method/results/conclusion")

# 2) Re-count results
result_count = len(re.findall(r"\\textbf\{[0-9.%,\s]+\}", text))
if result_count < 3:
    print("Warning: Abstract has only " + str(result_count) + " numbers (<3)")
else:
    print("OK: Abstract has " + str(result_count) + " numbers, sufficient")

# 3) Check opening style
bg_openers = ["随着", "最近", "针对"]
has_bg_opener = any(re.search(p, text[:200]) for p in bg_openers)
if has_bg_opener:
    print("OK: Abstract uses background-intro opening (advantage: 91.9%)")
else:
    print("Warning: Abstract does not use typical background-intro opening")

print("=== Abstract Quality Self-Check END ===")
# NEW_ABSTRACT_CHECK_BLOCK_END-->

PY

```

⛔ **闭环规则：若自检 `exit 1`（检测到挤段），立即回到检测输出括号里指出的摘要位置（main.tex 的 abstract 环境或手动排版段），在每个"针对问题 X"前补一个 LaTeX 空行拆成独立段落，然后重跑上面的自检，直到输出"✓ 摘要按问题分段正确"为止，方可进入下一步。**



**⛔⛔ 丰满模式摘要标准（华为杯默认 / 任意竞赛开启丰满模式时生效，1500-2200 字，跨两页）**：



⛔ **触发条件**：若 `CLAUDE.md` 含以下任一关键词，本节规范覆盖通用 400-600 字规则：

- `huawei` / `华为杯` — 华为杯默认走丰满模式

- `丰满模式` / `rich_mode` — 任意竞赛通过前端"丰满模式"开关启用



**自检命令**：

```bash

if grep -qiE "huawei|华为杯|丰满模式|rich_mode" CLAUDE.md 2>/dev/null; then

    echo "[丰满模式触发] 摘要按 1500-2200 字 + 6 项要素 + 5 段骨架写"

fi

```



丰满模式下官方允许/鼓励摘要跨两页，**字数压在 400-600 字会让评委觉得工作量不够**。



**篇幅与结构（强制）**：

- **总字数 1500-2200 字**（不算空格、空行），允许跨 2 页，**不要刻意压缩到一页**

- **每子问题段 280-400 字**（5 个问题 → 1400-2000 字主体 + 100-200 字开头背景 + 关键词）

- 段间用 LaTeX 空行分隔，**每段独立成块**，便于评委按问题快速定位



**6 项展示要素清单（每段必须命中）**：



| 要素 | 反例（AI 常犯） | 正例（华为杯优秀作品） |

|---|---|---|

| **1. 产业/社会背景开头** | 直接讲数据集 + 技术瓶颈 | "随着...的发展，...的应用推动了对...的需求。...作为核心组件，其性能优化对于...至关重要。" |

| **2. 过程式叙述骨架** | "构建了 XGBoost 三分类模型" | "**首先** 利用傅里叶变换分析噪声，**再** 提取 X/Y/Z 特征，**接着** 建立 A/B/C 模型对比，**最后** 借助混淆矩阵和交叉验证评估模型" |

| **3. 候选方法对比** | 只讲最优方案（XGBoost） | 列 2-3 个候选方法 + 选定 + 选择理由（MLP / 随机森林 / MLP-RF 加权集成；Solow / 二次多项式 / 温度饱和） |

| **4. 中间过程数值** | 只给最终 MAPE/R² | 加候选模型对比数（"MAPE 由 29.48% 降至 14.93%"、"参数估计值分别接近 1.5、1.4、1.5"） |

| **5. 附件预测结果数值** | 只说"已对附件三 400 样本完成预测" | **列若干代表性预测值**："部分模型预测结果为 952.8 W/m³、1570547.8 W/m³、11030.9 W/m³、..."（4-10 个数值） |

| **6. 可视化手段提及** | 不提图表 | "借助混淆矩阵和残差图"、"对磁通密度可视化"、"部分结果以表格呈现" |



**关键词数量**：8-12 个，**算法名 + 数学工具 + 模型族**全列，每个 `\quad` 分隔

- ❌ 反例（5-6 个）：磁芯损耗 XGBoost Steinmetz方程 方差分解 NSGA-II

- ✅ 正例（8+ 个）：多层感知机 随机森林 最小二乘法 温度饱和模型 方差分析（ANOVA） 多目标优化 双目标-单目标转化 粒子群算法

**⛔ 关键词行约束（国赛强制）**：`\keywords{...}` 或 `\noindent\textbf{关键词：}...` 中所有关键词加上 `\quad` 分隔后，**必须在一行内排完，不得换行**。若关键词过多导致换行，应精简至 6-8 个核心关键词，确保单行容纳。自检方法：编译 PDF 后检查关键词行是否有换行，若有则减少关键词数量。



**5 段华为杯摘要骨架模板**（按这个填）：

```latex

% 第 1 段：产业背景 + 问题导入（150-200 字）

随着[领域]的快速发展，[技术/产品]的[关键性能]优化对[应用场景]至关重要。

[问题对象]作为[系统]中的核心组件，其[关键指标]直接影响[宏观目标]。

本文针对[赛题 5 个子问题]，基于[数据集规模]，建立了[方法链概述]。



% 第 2 段：问题一（280-400 字，过程式 + 候选对比 + 数值）

针对问题一[简称]，[首先]...[再]...建立 [方法 A、B、C] 等模型进行对比，

最终选用 [选定方法] 并通过 [评估方式] 验证。结果表明 [关键数值1, 2]，

[附件二/三/四 的具体结果如：分类为正弦波 20 个、三角波 44 个、梯形波 16 个]。



% 第 3-5 段：问题二、三、四、五，结构同问题一



% 第 6 段（可选）：模型评价与意义（80-150 字）



% 关键词（8-12 个，\quad 分隔）

\noindent\textbf{关键词：} 算法名1 \quad 算法名2 \quad ... \quad 数学工具N

```



⛔ **华为杯摘要写作禁区**：

- ❌ 把摘要压到 1 页：评委一眼判工作量不够

- ❌ 只讲最终方案不讲候选对比：评委看不到方法选择的合理性

- ❌ 关键词只 5-6 个：丧失关键词检索曝光

- ❌ 开头直接讲数据集 / 技术细节：缺少产业背景定位

- ❌ 不列附件预测代表数值：评委无法快速核验工作量



**统计建模摘要**: 500-700 字, aim to fill most of one page but leave 3-4 lines margin at bottom — overflowing onto a second page looks worse than being slightly short. Content chain: 研究背景与意义 → 现有方法不足 → 本文方法 → 数据来源与处理 → 关键数值结果 → 应用价值与政策建议. English abstract: 350-500 words, same structure and all numerical results, also fit on one page.

</abstract_format>



### Step 3: Figure inventory + mandatory embedding plan



Before writing any chapter, build a complete inventory of available figures:



```bash

echo "=== Available PDF figures ==="

ls -la figures/*.pdf 2>/dev/null || echo "No PDF figures found"

echo ""

echo "=== Available table files (PDF模式: .tex / Word模式: .md) ==="

ls -la figures/TABLE_*.tex figures/TABLE_*.md 2>/dev/null || echo "No TABLE files found"

echo ""

echo "=== latex_includes.tex content (figure→PDF mapping) ==="

cat figures/latex_includes.tex 2>/dev/null || echo "No latex_includes.tex"

echo ""

echo "=== TikZ 几何/算法/架构图 ==="

# TikZ 由 paper-figure-drawio 生成为 figures/tikz_diagrams.tex → 编译成 figures/tikz_diagrams.pdf（多图则 tikz_*.pdf / tikz_diagrams_N.pdf）

# 它们的 \includegraphics 图块已写进 latex_includes.tex，按 latex_includes.tex 嵌入即可。

ls figures/tikz_*.pdf 2>/dev/null && echo "→ 有 TikZ 图，必须嵌入" || echo "No TikZ diagrams"

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

- **⛔ 图表 caption 必须是中文**（中文论文）。如果 `latex_includes.tex` 里的 caption 是英文，嵌入时必须翻译成中文

- **⛔ caption 要短**：流程图/路线图/架构图的 caption 只写图的类别/主题，**≤ 20 个汉字**（如「问题一求解流程图」「整体技术路线图」）。若上游 caption 是一长串方法描述，嵌入时必须精简成短标题，详细说明放进正文，**禁止让 caption 超过一行**

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

  - **⛔ 图注（caption）只写简短标签（中文主体 ≤20 字，不含"图 N"编号）**：`\caption{}` 只写这张图是什么的名词短语；判据、参数、坐标含义、结论移到正文那段图解读里，别塞进题注（否则图下方折成多行很难看）。反例 `\caption{覆盖半径几何示意：站点为圆心、R=3km 覆盖圆、区域出车距离与响应时间判据}` → 正例 `\caption{站点覆盖半径几何示意}`。详见 `_utils/writing_rules.md` 的图注长度总则；编译阶段会扫 caption 长度，超限判违规。

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



**写完所有章节后，必须运行以下检查确认 DrawIO/TikZ 图全部嵌入：**

```bash

echo "=== DrawIO/TikZ 嵌入检查 ==="

for pdf in figures/fig_roadmap.pdf figures/fig_flow_*.pdf figures/fig_pipeline*.pdf figures/fig_framework*.pdf; do

    [ -f "$pdf" ] || continue

    bn=$(basename "$pdf")

    if grep -rq "$bn" paper/sections/*.tex paper/main.tex 2>/dev/null; then

        echo "✅ $bn 已嵌入"

    else

        echo "❌ $bn 未嵌入 — 必须立即修复！"

    fi

done

# ⛔ TikZ 图检查（按 PDF 文件名核对，最可靠）

for tpdf in figures/tikz_diagrams.pdf figures/tikz_diagrams_*.pdf figures/tikz_*.pdf; do

    [ -f "$tpdf" ] || continue

    tbn=$(basename "$tpdf")

    if grep -rq "$tbn" paper/sections/*.tex paper/main.tex 2>/dev/null; then

        echo "✅ TikZ $tbn 已嵌入"

    else

        echo "❌ TikZ $tbn 未嵌入 — 必须立即修复！"

    fi

done

# ⛔ 流程图堆叠检查：问题分析章节(2_analysis)里的子问题流程图数量必须 ≤1，

#    否则就是把 fig_flow_q1~q5 违规堆在了分析章节（见上文铁律）。

_analysis_tex=$(ls paper/sections/2_*.tex 2>/dev/null | head -1)

if [ -n "$_analysis_tex" ]; then

    _flow_in_analysis=$(grep -oE 'fig_flow_q[0-9]+' "$_analysis_tex" 2>/dev/null | sort -u | wc -l)

    if [ "$_flow_in_analysis" -ge 2 ]; then

        echo "❌ 问题分析章节含 $_flow_in_analysis 张子问题流程图 — 违反铁律！必须把 fig_flow_q1~q5 分散到各自问题章节(5_problem1.tex 等)，分析章节最多留 fig_roadmap 一张。"

    else

        echo "✅ 流程图未堆叠在问题分析章节"

    fi

fi

```

**如果有任何 ❌，必须立即修复后再继续写下一章。不要等到最后才修复。**



Also scan `figures/*.tex` for all `\begin{figure}` / `\begin{table}` blocks with their `\label{}`. After writing, verify all are embedded:

```bash

grep -oh '\\label{[^}]*}' figures/*.tex 2>/dev/null | sort -u > _tmp/all_fig_labels.txt

grep -oh '\\label{[^}]*}' paper/sections/*.tex paper/main.tex 2>/dev/null | sort -u > _tmp/embedded_labels.txt

comm -23 _tmp/all_fig_labels.txt _tmp/embedded_labels.txt  # should be empty

```



**⛔ 图连排检查（防「两张图连在一起中间没文字」）**：检测是否有两个 figure/table 环境直接相邻、中间无正文：

```bash

echo "=== 图表连排检查 ==="

for f in paper/sections/*.tex; do

    [ -f "$f" ] || continue

    # 把每个 \end{figure|table} 到下一个 \begin{figure|table} 之间的正文抠出来，若只有空白/注释则判为连排

    # ⛔ 反斜杠用 chr(92)+re.escape 构造：本机 bash heredoc 会吞裸反斜杠，直接写 \\end 会 re.error

    python - "$f" << 'PYEOF'

import re, sys

t = open(sys.argv[1], encoding='utf-8', errors='ignore').read()

BS = chr(92)

END = re.escape(BS + 'end') + r'\{(?:figure|table)\}'

BEG = re.escape(BS + 'begin') + r'\{(?:figure|table)\}'

bad = 0

for g in re.finditer(END + r'(.*?)' + BEG, t, re.DOTALL):

    body = re.sub(r'%[^\n]*', '', g.group(1))   # 去注释

    body = re.sub(r'\s+', '', body)             # 去空白

    if len(body) < 80:                          # 夹缝实际正文 < 80 字符 → 敷衍（连排或一句话带过）

        bad += 1

if bad:

    print("  X %s: 有 %d 处图间正文过少（<80字，疑似敷衍/一句话带过）——每张图后必须有充分解读：具体数值+对比或趋势+推论或衔接，不许单句收尾" % (sys.argv[1], bad))

PYEOF

done

echo "（无输出=未发现连排）"

```

**如发现连排，必须在两图之间补写引导/过渡正文后再继续。**



TikZ 图通过 `latex_includes.tex` 里的 `\includegraphics{tikz_diagrams.pdf}` 图块嵌入（不要用 `\input`）。按图的内容映射到章节：

- 技术路线图/研究框架图/问题关系图 → 问题重述章节末尾（`1_restatement.tex`），不要放到后面的子问题章节

- 各子问题求解流程图/几何示意图 → 对应子问题章节开头（`4_problem1.tex`、`5_problem2.tex`、`6_problem3.tex` 等）

- 模型架构图 → 对应模型章节



### Step 3.5: 文献预检索（写正文之前必须完成）



**⛔ 在写任何 \cite{} 之前，必须先建立已验证的文献池。**



```bash

PYTHON=""; for _c in "$MH_PYTHON" python python3; do [ -z "$_c" ] && continue; if $_c -c "import sys" >/dev/null 2>&1; then PYTHON="$_c"; break; fi; done; [ -z "$PYTHON" ] && PYTHON=python

mkdir -p _tmp

# 根据论文主题搜索真实论文，建立引用池

# 示例（根据实际选题调整）：

#   $PYTHON "$SCHOLAR_SCRIPT" bibtex "你的核心方法关键词" --max 5

#   $PYTHON "$SCHOLAR_SCRIPT" bibtex "你的研究领域关键词" --max 5

```



搜索后创建 `_tmp/_verified_refs.txt`，写正文时只引用池子里的论文。需要新引用时先搜索验证再加入池子。



**兜底**：如果 `scholar_fetch.py` 搜不到或 `match_label="low"`，用 WebSearch 在 Google Scholar / Semantic Scholar 网站上搜索，手动核实标题+作者+年份后再加入池子。



### Step 4: Write each chapter



**⛔ CRITICAL: ALL numerical results in the paper MUST come from `figures/*.json` or `RESULTS.md`.**



**⛔ NEVER `cat figures/*_results.json`.** These result files often contain full-precision time-series arrays (tens of MB / hundreds of thousands of lines); reading them whole blows up the context — local models fail outright, and GPT-via-transit chokes on protocol translation of the oversized payload and stalls on repeated `api_retry`. **The paper text only uses scalar values (fitness / optimal solution / solve time / metrics); the giant arrays are for figures, not prose.** Before writing any result chapter, run the `summarize` script below to get a KB-level overview (scalars shown verbatim — zero precision loss — only big arrays compressed to "length + range + first 3 samples"):

```bash

cat RESULTS.md

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

Every scalar you need is in `RESULTS.md` or the range/sample of the summary above. If one scalar isn't fully shown, fetch just that value with `python3 -c "import json;d=json.load(open('figures/all_results.json'));print(d['key'])"` — still never read the whole file. Copy the exact numbers into the LaTeX text. Do NOT round differently, do NOT estimate, do NOT make up numbers that "look reasonable". If a number is not in the data, it cannot appear in the paper.



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



**⛔⛔ 符号说明表格格式（必须用 longtable + 禁止漂浮，否则会出现"半页空白 + 表格塞下一页"）：**



⛔ **根因警告**：**所有数学建模竞赛模板**（国赛 / 华为杯 / MathorCup / 华中杯 / 五一杯 / 美赛 / 华数杯 / 统计建模 / 长三角 / 电工杯 / 东三省 / 数维杯 / APMCM 等 13 个模板）的 `main.tex` 都启用了 `\usepackage[section]{placeins}`，作用是"每个 section 末尾自动插 `\FloatBarrier` 阻止浮动跨节"——这本来是好规范（防止图表漂到下一节），**但会让浮动表无法跨节漂移**。如果 AI 用 `\begin{table}[!ht]` / `[!h]` / `[htbp]` 写符号说明等小节的表格，且表格高度 + 引导文字超出剩余页面空间，LaTeX 会：

1. 把 `[!ht]` 表格扔到本节内能放下的位置 → 通常是节末

2. 节标题 + 引导文字停留在节开头 → **当前页大段空白**

3. 评委看到的就是"4. 符号说明" + 一句话 + 大半页空白 + 翻页才看到表



⛔ **不是华为杯独有问题**：所有竞赛都有这个陷阱。只是华为杯 gmcmthesis 字号大（4 号字 ≈ 14pt + 1.5 行距）、页边距宽，更容易触发"放不下当前页"的浮动条件，所以更显眼。



✅ **正确做法（务必遵守）**：

- **必须用 `\begin{longtable}` 而不是 `\begin{table}` + `\begin{tabular}`**

- longtable 不是 float，**不参与浮动**，就地排版 → 没有"漂走"问题

- longtable 天然支持跨页，标题永远在表格开头，不会出现标题和表格分离

- 不需要 `\centering`（longtable 自带居中）

- 不需要引导文字（"本文所用主要符号..."），节标题直接紧跟表格

- compile_utils.sh 会自动把 table+tabular 转成 longtable（兜底），但**源头写对最稳**



❌ **绝对反例**（任一出现都会引发空白页问题）：

```latex

\begin{table}[!ht]      % ❌ 漂浮，可能被推到节末

\begin{table}[ht]       % ❌ 同样漂浮

\begin{table}[htbp]     % ❌ 漂浮，加 b/p 让 LaTeX 决定页位

```



✅ **正确写法**：

```latex

\section{符号说明}

\begin{longtable}{clc}

\caption{主要符号说明}\label{tab:symbols} \\

\toprule

符号 & 含义 & 单位 \\

\midrule

\endfirsthead

\toprule

符号 & 含义 & 单位 \\

\midrule

\endhead

$N$ & 总数量 & 个 \\

$x_i$ & 第$i$个变量 & --- \\

... \\

\bottomrule

\end{longtable}

```



⛔ **写完符号说明章节后必跑自检**（在 paper/sections/ 里扫表格浮动反例）：

```bash

# 1. 符号说明文件不应该有 \begin{table}（必须用 longtable）

for f in paper/sections/*symbol*.tex paper/sections/*符号*.tex paper/sections/4_*.tex; do

    [ -f "$f" ] || continue

    if grep -q '\\begin{table}' "$f" 2>/dev/null; then

        echo "❌ $(basename $f): 用了 \\begin{table}，必须改成 \\begin{longtable}"

        echo "   会导致华为杯 'placeins[section]' 强制 FloatBarrier 时表格漂到节末，留大段空白"

    fi

done



# 2. 任何章节里的 \begin{table}[!ht] / [ht] / [htbp] 漂浮选项警告

BAD_FLOAT=$(grep -rEn '\\begin\{table\}\[(!?ht?|htbp|tb|b|p)\]' paper/sections/ 2>/dev/null)

if [ -n "$BAD_FLOAT" ]; then

    echo "⚠ 检测到表格用了漂浮选项（可能引发空白页）："

    echo "$BAD_FLOAT" | head -5

    echo "   建议：短表（< 半页）改用 \\begin{table}[H]（强制就地），长表 / 符号说明用 \\begin{longtable}"

fi

```



- 符号控制在 15-20 个以内，表格控制在半页以内



**⛔ 写每个章节前，先读 MODELING_REPORT.md 和 RESULTS.md 对应部分的内容。** 不要凭记忆写——数值结果、公式推导、算法步骤都必须从这些文档中提取。



**⛔ 跨章上下文 + 图数据绑定（防"两张皮"）：**

- **每写完一章**，立刻往工作区根目录 `_writing_context.md` 追加 3-5 行要点卡（核心论点／关键数字／新定义的符号术语／已讨论的图表）；**写下一章前先 `cat _writing_context.md`**，承接前文结论、复用已定义术语（不重复定义）、保持同一指标数字全文一致——详见 `_utils/writing_rules.md` 的 `<chapter_context_card>`。

- **写每张图/表的分析前**，先按 `<figure_data_binding>`：从 FIGURE_MANIFEST/latex_includes 认清"这张图画的是什么量" → 去 `RESULTS.md`／`figures/all_results.json` 定位它对应的真实数值 → 分析里只用这些真值，**禁止凭图形状/位置猜数、禁止编造坐标**。



Read RESULTS.md for exact numbers — ensure paper numbers match computation results.



**⛔ 图文数值一致性规则：** 描述图表内容时（如"从图X可以看出，模型A的RMSE为0.023"），数值必须从 `figures/*.json` 或 `RESULTS.md` 中读取，不要凭记忆编写。写完后用 `bash _utils/writing_check.sh paper/` 检查一致性。



**⛔ 长表格处理规则（>12 行的数据表格）：**



正文中**禁止**直接放超过 12 行的表格（调度方案、完整数据列表、逐步迭代结果等）。处理方式：



1. **正文：只放缩略版**（前 3 行 + 后 3 行 + 中间 `$\vdots$` 省略），底部注明"完整结果见附录 X"

2. **附录：放完整表格**（用 longtable 环境，允许跨页）



示例（正文缩略版）：

```latex

\begin{table}[H]

\centering

\caption{问题一调度方案（部分）}

\begin{tabular}{cccc}

\toprule

任务 & 设备 & 开始时间 & 结束时间 \\

\midrule

1 & A & 0 & 5 \\

2 & B & 2 & 8 \\

3 & A & 5 & 12 \\

\multicolumn{4}{c}{$\vdots$} \\

28 & C & 45 & 52 \\

29 & A & 48 & 55 \\

30 & B & 50 & 58 \\

\bottomrule

\end{tabular}

\label{tab:q1_schedule_short}

\footnotesize 注：完整调度方案（30 条记录）见附录 B。

\end{table}

```



**判断标准：** 写表格前先数数据行数。如果 `figures/TABLE_*.tex` 或结果表格超过 **12 行**数据行，必须自动生成缩略版（前 3-5 行 + `$\vdots$` + 后 3 行，可再加一行**汇总统计**如均值/最优/总计 Makespan）+ 附录完整版（`longtable`，放 `paper/appendix/` 如 `A_code.tex` / 新建 `A_tables.tex`）。不要把 100+ 行的 longtable 直接嵌入正文章节。`compile_utils.sh` 也会自动检测并截断超长表格兜底，但最好写的时候就按本规则处理好。



Follow the interleaving, embedding, and LaTeX rules from `_utils/writing_rules.md`.



**⛔ 图文并茂硬规则（每个章节都必须遵守）：**

- **浮动符（受控浮动）**：图用 `\begin{figure}[H]`（就地钉死），表用 `\begin{table}[H]`（就地）。图用 `[H]` 是为了钉在引出文字正下方、从机制上杜绝多图连排（`[htbp]` 会让 LaTeX 把多张图攒到一页、最伤可读性）；代价是极少数"图接近整页高+恰好落页底"时上方留一段空白，但图已限高在 `0.9\textheight` 内、且每张图前后都有引导/承接文字，此情形罕见且优于连排。模板已加载 `\usepackage[section]{placeins}`，每节末自动 `\FloatBarrier`（防残余浮动体跨节）。⛔ 表格不要用 `[htbp]`：会被 `\FloatBarrier` 逼到节末，在表上方留半页空白（符号表最常中招）；短表用 `[H]` 就地，超长表用 `\begin{longtable}`。伪代码 `\begin{algorithm}[H]` 保持就地。

- 每张图/表后面必须有 ≥5 行分析文字（数值解读+对比+结论），然后才能放下一张图

- 绝对禁止两张图连续出现中间没有分析段落

- 图片用 `\includegraphics[width=0.85\textwidth,keepaspectratio]`（以宽度为主，高度自适应）。⛔ 不要再加 `height=0.38\textheight` 这种小高度限制——在 `keepaspectratio` 下 height 只会把图**压得更小**：方形或竖高的图（热力图、雷达图、森林图、混淆矩阵、竖排子图、流程图）会被 0.38 页高卡到只有半页宽，导致"图很小看不清"。只有当某张图确实接近整页高、可能溢出时，才加 `height=0.9\textheight` 作为防溢出兜底

- **⛔ 禁止使用 LaTeX `subfigure`/`subcaption` 并排「多张独立 PDF」。** 每张图必须独占一个 `\begin{figure}[H]...\end{figure}` 环境，宽度 ≥ `0.85\textwidth`。不要用 `\begin{subfigure}{0.48\textwidth}` 把两张独立 PDF 缩成半页宽——这会导致图片太小看不清。如果确实需要对比两张图，分成两个独立的 figure 环境，中间加 2-3 句过渡分析文字。

  **✅ 例外（推荐做法）：多面板组合图（FIGURE_MANIFEST 标了 `[2-panel]` / `[4-panel]`）应当在 matplotlib 内一次性画出 —— 用 `plt.subplots(1, 2)` 或 `plt.subplots(2, 2)` + 每子图 `(a)(b)(c)(d)` 标签 —— 输出为「单个 PDF」，LaTeX 引用时仍是 `\includegraphics[width=0.85\textwidth]{fig_xxx.pdf}` 一行搞定。这种方式既能并排对比又能保持高分辨率，不属于禁令范围。详见 `_utils/writing_rules.md` 第 4 条。

  **🟡 数据图不是都要并排——默认单列，留白才触发**：数据结果图**默认一张一行**；只有当两张图**同类/可比**（如两变量分布、两场景同类曲线）、且**各自单列都只占半页、配文字后留半页以上白**时，才做成 2-panel 并排把版面填满。两张图不相关的，哪怕都很空也各自单列，不为凑页硬拼（详见 `_utils/writing_rules.md` 第 4 条决策流程 3.5 步）。

  **⛔ 但逻辑框图例外中的例外——流程图/架构图/技术路线图/TikZ 几何·算法·架构示意图（drawio 或 tikz 生成的逻辑框图）绝对单列独占，不论主题多相关都不并排**：它们靠节点文字和连线表意，缩成半栏字就糊了，并排没有信息收益。上面的✅ matplotlib 合成单 PDF 只针对**数据结果图**（柱状/折线/热力/混淆矩阵等）的并排对比，逻辑框图（含 tikz_*.pdf）不走这条、永远一张一行。

- **⛔ 图片宽度下限：** `width` 参数不得小于 `0.8\textwidth`。任何 `width=0.5\textwidth`、`width=0.48\textwidth`、`width=0.45\textwidth` 都是错误的，必须改为 `0.85\textwidth` 或 `0.9\textwidth`



> ⛔ 长表格处理规则见上方「长表格处理规则（>12 行的数据表格）」一处（含缩略版示例 + 汇总统计行 + 附录 longtable + compile_utils.sh 兜底）。此处原来重复写了一遍「>15 行」版本，阈值与上面的 12 行矛盾（同一张表可能一处判超、一处判过，逼 AI 反复改），已删除，统一以上面的 **12 行** 阈值为准。



After each chapter, check character count:

```bash

chars=$(wc -c < "paper/sections/当前章节.tex")

echo "当前章节: $chars 字符 (~$(echo "scale=1; $chars/900" | bc) 页)"

# Chinese LaTeX ≈ 800-1000 chars per page

# If chapter expected 5 pages but only 2000 chars (~2.5 pages), expand immediately

```



<exemplar_depth>

#### Writing depth reference



**国赛一等奖 (25-30 pages, 3 sub-problems)**:

- 问题重述+分析 (2-3p): restate in own words, extract core problems — not copying the problem statement

- 模型假设+符号说明 (2p): 5-7 assumptions (each with content + justification, not too many not too few), one complete symbol table with 15-25 variables (符号/含义/单位 three columns, do not split into multiple tables)

- Each sub-problem (5-7p): model formulation (2p, with derivation and physical meaning) + solution method (1.5p, with algorithm steps) + results with table+figure (1p) + analysis (0.5-1.5p, numerical meaning + comparison with expectations + reasoning)

- 灵敏度分析 (2-3p): ≥2 key parameters, each with variation curve plot + analysis paragraph

- 模型评价 (2p): 3-4 strengths + 2-3 weaknesses + generalization directions. Pure text discussion, no figures or tables needed



**华为杯一等奖 (40-50 pages)**: deeper derivations, more thorough analysis per sub-problem (8-10p each), 灵敏度分析 (4-5p), 模型评价 (3p, pure text, no figures) with comparison to other methods



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

| 华为杯 | 40-50 | 30000-40000 | ≥15 |

| MathorCup | 35-40 | 25000-35000 | ≥10 |

| 华中杯 | 25-30 | 18000-25000 | ≥10 |

| 五一杯 | 25-30 | 18000-25000 | ≥10 |

| 统计建模 | 35-40 | 25000-35000 | ≥20 |

</exemplar_depth>



<figure_usage_principles>

#### Figure/table usage by competition type



**统计建模**: Figures first, tables second. Figure/table selection is driven by the actual analysis methods used — regression uses forest plots + regression tables, prediction uses prediction comparison plots + accuracy tables, classification uses confusion matrices + ROC, evaluation uses radar charts + ranking tables. Every analysis step should have a corresponding figure or table.



**数模竞赛**: "字不如表，表不如图". Every sub-problem must have independent result display (table + figure). Comprehensive comparison figures are additional supplements. Reviewers value information density and aesthetics.



Do not force figures where they are not needed (pure literature review, theoretical derivation). Claude decides figure count and placement based on content needs.

</figure_usage_principles>



<stats_figure_placement>

#### Stats modeling paper figure placement rules



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

#### Chapter writing points (universal, adapt to research logic)



**⛔ 写作风格铁律（所有章节都必须遵守）：**

- **禁止在正文中使用 `\begin{itemize}` 或 `\begin{enumerate}` 列表。** 黑点/编号列表是最明显的 AI 写作痕迹。必须用连贯的段落叙述。

  - 需要列举时用行内编号："（1）...（2）...（3）..."或"首先...其次...最后..."

  - 例外：模型假设列表（可用编号）、附录

- **每段至少 3-5 句话。** 不要写只有 1-2 句的短段落。

- **连续段落不能以相同句式开头。** 如连续三段都以"本文..."开头，必须改。

- **图号必须显式引用、句式换着来（标准优秀论文口径）。** 每张图都要点名"图 N"让读者对上号（硬规范，别为避免套路删图号）；要禁的是"图X展示了……从图中可以看出……"这种图作主语+空话的单调重复，不是禁止一切图作主语。相邻两图引用句式必须不同，在括号旁注（首选）／句首带出／动词引导／图作主语（带实质结论时可用）／后置印证间轮换。详见 `_utils/writing_rules.md` 的"图表是论据"规则。

- **禁止元叙述和内部指令泄露。** 正文中不能出现"参赛者"、"参赛队伍"、"RESULTS.md"、"figures/*.json"、"CLAUDE.md"等内部文件名或工作流术语。用"本文"代替"我们团队"，论文是独立学术文档。



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

</chapter_writing_points>



**Expansion strategies** when content is thin (not padding — substantive content):

- Formula listed without derivation → add step-by-step derivation with physical meaning explanation

- Result with only "如表所示" → add 2-3 paragraphs of interpretation (numerical meaning, comparison with expectations, reasoning, comparison with other methods)

- Assumptions as bare list → add justification for each assumption

- Algorithm as pseudocode only → add explanation of key steps, complexity analysis, convergence discussion

- Literature review only lists papers → add method summary for each and connection to this work



### Step 5: References



Follow the `<references_workflow>` in `_utils/writing_rules.md`.

Stats papers: ≥20 references. The stats template uses `natbib` with `[numbers, square, super]` — use `\cite{key}` in body text (auto-superscript) + `\bibliography{references}` + `\bibliographystyle{plainnat}`. **cumcm / wuyi** load `natbib[numbers]` (no super) + `\bibliographystyle{gbt7714-numerical}` + `\bibliography{references}` — body text MUST use `\upcite{key}` (not `\cite`, which gives inline `[1]`). The huazhong template uses `\begin{thebibliography}{99}...\end{thebibliography}` — manually add `\bibitem` entries (do not use `\bibliography{}`); body uses `\cite`. ⛔ `\upcite` exists ONLY in cumcm / huazhong / wuyi / dongsansheng; every other template uses `\cite`.



**⛔ 使用 scholar_fetch.py 工具获取所有参考文献的 BibTeX。禁止凭记忆编造 BibTeX。**



**⛔ 引用编号必须按正文出现顺序排列（1, 2, 3, 4...），不能跳着来。** 使用 `\begin{thebibliography}` 的模板：`\bibitem` 的排列顺序必须跟正文中 `\cite{}` 首次出现的顺序一致。使用 `\bibliography{references}` 的模板：BibTeX 会自动按引用顺序编号（gbt7714-numerical / plainnat 都支持）。写完所有章节后，检查引用编号是否连续递增，如果不是，调整 `\bibitem` 顺序或 `.bib` 文件中的条目顺序。



**⛔⛔ 正文中引用编号必须全局递增出现（严格，不可违反）：**



写正文时每个引用编号必须比之前所有已出现的编号大（即首次引用必须按 [1], [2], [3], [4]... 顺序）：

- ✅ 正确：全文第一个引用 [1]，第二个 [2]，第三个 [3]...

- ❌ 错误：正文中先出现 [3]，然后出现 [8]，又回到 [1] — 引用编号跳跃

- ❌ 错误：前文已出现 [5]，后文再出现新引用为 [3] — 编号回退



**如何保证递增：**

- 所有引用的 key 在 .bib 文件或 thebibliography 环境中的排列顺序 = 它们在正文中首次出现的顺序

- 如果写作时发现某处需要一个新引用，它的编号会自动是当前已用编号的最大值+1

- 写完所有章节后，逐段扫描正文，确认引用编号 [N] 严格递增（只允许重复已出现的编号）



**⛔ 引用格式规则（中文竞赛论文必须上标）：**

- 必须用上标引用样式：`\bibliographystyle{gbt7714-numerical}` 或 natbib 的 `super` 选项

- 如果模板用的是 `plain/plainnat/unsrt`（非上标），正文中必须用 `\upcite{}` 或 `\textsuperscript{\cite{}}` 而不是 `\cite{}`

- 禁止：非上标样式 + 直接 `\cite{}` → 引用会显示为 `[1]` 而非上标 `¹`



**⛔ 多引用合并规则（合并必须按编号升序）：**



同一处引用多篇文献时：

- ✅ 正确：`方法A\cite{a,b,c}` — 一个 \cite 命令，多个 key 用逗号分隔，**且 a,b,c 对应的编号必须升序**（如 [1,2,5]）

- ✅ 正确：`方法A\cite{a}\cite{b}` — 如果 a,b 编号不相邻（如 [3] 和 [7]），也可以分开写

- ❌ 错误：`方法A\cite{a}\cite{b}\cite{c}` — 多个连续 \cite 且编号相邻，必须合并成 `\cite{a,b,c}`

- ❌ 错误：`方法A\cite{c,a,b}` — 编号顺序错乱（如 [5,1,2]），必须改成 `\cite{a,b,c}`（[1,2,5]）

- ❌ 错误：`方法A\cite{a,b}` 但 a=[3]、b=[1] — 编号降序，必须改成 `\cite{b,a}`（[1,3]）



**合并的判定规则（严格）：**

1. 多引用里的 key 必须按其编号升序排列 → 如 [1,2,5] 对应 `\cite{key_of_1, key_of_2, key_of_5}`

2. 如果两个引用编号不相邻（中间差 > 1），建议合并为一个 `\cite{}` 保持整洁

3. 如果不能保证升序，**宁愿分开写** `\cite{a}\cite{b}` 也不要错序合并

4. 写作时难以预知最终编号，可先按 key 的出现逻辑合并，编译后用 compile_check.sh 检查并调整



**⛔ 引用写法规则：写正文时，citation key 必须包含描述性关键词，格式为 `作者姓_年份_主题关键词`。**

例如：`\cite{wang_2023_supply_chain_resilience}` 而不是 `\cite{wang2023supply}`。

不确定作者/年份时用 `TODO__` 前缀：`\cite{TODO__digital_economy_spatial_spillover}`。



```bash

# Step 5a: 收集所有引用 key

grep -roh '\\cite[tp]*{[^}]*}' paper/sections/*.tex paper/main.tex 2>/dev/null \

  | grep -oP '\{[^}]+\}' | tr -d '{}' | tr ',' '\n' | sed 's/^ *//;s/ *$//' | sort -u > _tmp/_cited_keys.txt

echo "引用 key 数量: $(wc -l < _tmp/_cited_keys.txt)"



# Step 5b: 逐个搜索并获取 BibTeX（用描述性关键词搜索）

PYTHON=""; for _c in "$MH_PYTHON" python python3; do [ -z "$_c" ] && continue; if $_c -c "import sys" >/dev/null 2>&1; then PYTHON="$_c"; break; fi; done; [ -z "$PYTHON" ] && PYTHON=python

while IFS= read -r key; do

    query=$(echo "$key" | sed 's/^TODO__//; s/_/ /g')

    echo "--- 获取: $key (搜索: $query) ---"

    $PYTHON "$SCHOLAR_SCRIPT" bibtex "$query" --max 3

    sleep 0.5

done < _tmp/_cited_keys.txt

```



处理每个搜索结果：

1. 检查 `match_label`：`"good"` → 直接使用。`"partial"` → 核实标题。`"low"` → 很可能搜错了，换关键词或用 WebSearch。

2. `match_score` < 0.3 说明大概率不是目标论文，不要盲目使用。

3. 将 .tex 中的 citation key 替换为 BibTeX 条目中的实际 key。

4. `bibtex_source=auto` 的条目加 `% [VERIFY]`。`match_label="low"` 的加 `% [LOW_MATCH]`。



### Step 5.5: De-AI polish



See `<de_ai_polish>` in `_utils/writing_rules.md`.



### Step 5.6: Write abstract NOW (after all chapters are complete)



**⛔ MANDATORY: NOW write the abstract.** Read RESULTS.md and all section .tex files. Extract the actual numerical results from each sub-problem. The abstract must contain ONLY numbers that appear in the body text — do NOT invent or round differently.



**⛔ 统计建模必须写中英文两个摘要**：先写中文摘要（500-700字），然后将中文摘要忠实翻译为英文摘要（350-500 words），所有数值结果、方法名称、结论必须一一对应。数模竞赛（国赛/五一杯/MathorCup/华中杯等）只写中文摘要。



For math modeling competitions: each sub-problem must have its specific result in the abstract (e.g., "问题一采用XX算法，最优解为YY，空间利用率达ZZ%")。



Read `_utils/writing_rules.md` for abstract format rules (分段、首行缩进、长度).



### Step 6: Final verification



```bash

bash _utils/writing_check.sh paper/ 2>/dev/null || bash skills/shared-scripts/writing_check.sh paper/

```



**⛔ 能力声称终检（正文写完后跑，扫"有没有把没通过的能力写成成果"）：**

```bash

FAST_MODE=0; grep -q 'MH_FAST_MODE=1' CLAUDE.md 2>/dev/null && FAST_MODE=1

python _utils/paper_claim_check.py --audit CAPABILITY_AUDIT.md --checklist CAPABILITY_CHECKLIST.json --sections paper/sections --fast $FAST_MODE

PCC=$?   # 此时正文已成型：会扫未通过能力名是否出现在正文(WARN),并复核验收状态(FAIL阻断)

```

> WARN（未通过能力名出现在正文）：确认不是把没做成的写成做到了；若确在"局限/未来工作"里如实提及可放行。`PCC=1`：仍有能力未通过验收，不能定稿。



Also check:

```bash

source .env_skill 2>/dev/null || true  # 加载 MAX_PAGES 等数值参数

echo "=== 各章节字符数 ==="

total=0

for f in paper/sections/*.tex; do

    chars=$(wc -c < "$f")

    total=$((total + chars))

    echo "  $(basename $f): $chars 字符 (~$(echo "scale=1; $chars/900" | bc) 页)"

done

echo "  总计: $total 字符 (~$(echo "scale=1; $total/900" | bc) 页)"

# ⛔ 页数是否达标以下方「正文页数预检」为唯一权威判断（统一按 900 字符/页）。

#    这里只打印各章明细供定位最薄章节，不再给"×800"的独立目标——之前 800/900 两套

#    口径并存会让 AI 看到自相矛盾的目标（同段 /900 估页却按 ×800 判达标）而反复纠结。

echo "  （页数达标判断见下方「正文页数预检」，统一按 900 字符/页；本段仅看各章明细找最薄章节）"

```

- 用上面的各章明细找出最薄的 1-2 章优先扩充；页数是否达标以下方「正文页数预检」为准

- Any sub-problem chapter <3500 chars (~4 pages) needs expansion

- All figures/*.pdf and TABLE files (PDF模式 .tex / Word模式 .md) referenced in sections/正文

- No template bracket placeholders remaining (`[论文标题]`, `[中文摘要内容]`, etc.)



**⛔ Constraint consistency check (MUST do before finishing):**

Read PROBLEM_ANALYSIS.md (or the original problem statement in user_data/) and check every numerical result in the paper against the problem's constraints:

```

=== 论文-题目约束一致性检查 ===

1. 读取题目中的所有约束条件（容量、预算、时间窗、数量限制等）

2. 逐个检查论文正文中的结果是否满足这些约束

3. 例如：题目说"车辆载重上限 6000kg"，论文写"装载 7344kg" → 矛盾，必须修正

4. 例如：题目说"30 个省份"，论文分析了 28 个 → 不完整，必须补充

5. 摘要中的数字是否与正文一致？

6. 不同章节引用同一个结果时数字是否一致？（如问题一的最优解在摘要、正文、结论中出现 3 次，必须完全相同）

```

如果发现矛盾，修改论文正文（不是修改约束）。如果是代码结果本身违反约束，说明代码有 bug，需要回到 comp-code 修复。



**⛔ Page count pre-check (MUST pass before finishing — do NOT leave this to compile step):**



> ⛔ **MAX_PAGES 指正文页数**（章节 1 - 结论，含图表），**不含**摘要 / 目录 / 参考文献 / **附录代码**。

> 检查只统计 `paper/sections/*.tex`，附录代码归 `paper/appendix/*.tex`，单独不限页数。



```bash

source .env_skill 2>/dev/null || true  # 加载 MAX_PAGES 等数值参数

echo "=== 正文页数预检（只查 paper/sections/，不含附录代码）==="



# 1. sections/ 不应该含代码块（lstlisting / \begin{python} / \begin{verbatim}）

code_in_body=0

for f in paper/sections/*.tex; do

    [ -f "$f" ] || continue

    if grep -qE '\\begin\{(lstlisting|verbatim|minted|python|matlab)\}' "$f" 2>/dev/null; then

        code_in_body=$((code_in_body + 1))

        echo "  ⚠️ $f 含代码块 — 代码必须放 paper/appendix/，不能放正文"

    fi

done

if [ "$code_in_body" -gt 0 ]; then

    echo "⛔ CRITICAL: $code_in_body 个正文章节含代码块，必须移到 paper/appendix/"

    echo "  原因：正文页数预检按字符 / 900 估算，代码块行多但表达密度低，会让 est_pages 虚高 → 实际正文单薄"

fi



# 2. 正文字符统计 + 估算页数

total_chars=0

for f in paper/sections/*.tex; do

    [ -f "$f" ] || continue

    chars=$(wc -c < "$f")

    total_chars=$((total_chars + chars))

done

est_pages=$((total_chars / 900))

echo "正文字符: $total_chars, 估算页数: ~$est_pages 页, 目标: ≥ ${MAX_PAGES:-30} 页"



# 3. 附录单独统计（仅信息）

if [ -d paper/appendix ]; then

    appendix_chars=0

    for f in paper/appendix/*.tex; do

        [ -f "$f" ] || continue

        appendix_chars=$((appendix_chars + $(wc -c < "$f")))

    done

    appendix_pages=$((appendix_chars / 900))

    echo "（附录字符: $appendix_chars, 估算 ~$appendix_pages 页，不计入 MAX_PAGES 检查）"

fi



if [ -n "$MAX_PAGES" ] && [ "$est_pages" -lt "$((MAX_PAGES * 80 / 100))" ]; then

    echo "⛔ CRITICAL: 正文页数严重不足 ($est_pages < 80% of $MAX_PAGES)"

    echo "必须扩充最薄的章节后再结束（华为杯：每子问题正文 ≥ 8-10 页 + ≥ 6-8 张图表 + ≥ 8-15 个公式）"

    echo "扩展方向：补公式推导（每步可解释）/ 增过程图（建模/算法流程）/ 加灵敏度分析 / 充实结果讨论"

fi

```

If estimated pages < 80% of MAX_PAGES, you MUST expand the thinnest 2-3 chapters before finishing. Read MODELING_REPORT.md and RESULTS.md for additional content to add (more derivation, more result analysis, more parameter discussion).



⛔ **正文 vs 附录归档约束**：

- `paper/sections/` — 仅放正文章节（绪论 / 方法 / 结果 / 讨论 / 结论）

- `paper/appendix/` — 放代码 / 长数据表 / 求解日志 / 公式补充推导 / 算法伪代码

- 严禁把代码塞 sections/（会让页数预检虚高但实际正文薄）



⛔ **页数扩展约束（防幻觉）— 写公式 / 加过程图 / 加灵敏度时必须遵守**：



| 扩展方向 | ✅ 允许 | ⛔ 禁止 |

|---|---|---|

| **补公式推导** | 从 MODELING_REPORT.md 抄推导链；中间步骤展开（如 (a)→(b) 的代数变换写明）；编号 (1)(2)(3) 连续 | 凭印象写新公式；编"假设 X 服从 Y 分布"等没有依据的统计假设；公式里编数字（如 ρ=0.873） |

| **增过程图** | 用 plot_utils 真画图（gen_fig_xxx.py 跑出 PDF/PNG）；流程图节点对应 comp-code 实际算法步骤；TikZ 流程图节点文本与代码注释一致 | 用占位符；编一个不存在的算法步骤；流程图数字不与 RESULTS 一致 |

| **加灵敏度** | 必须**真跑** sensitivity 代码，把结果存 `figures/sensitivity_*.json`；表格数字从 json 读 | 直接在正文写"参数 α 增加 10% 时目标值下降 5.2%" 而**没有真跑实验** |

| **充实结果讨论** | 解读已有结果（results.json / RESULTS.md）；对比基准方法；分析误差来源 | 重复说同一件事；加"如表所示"水文；编未做的对比实验 |



⛔ **进阶扩展方向（按题型分类，所有数字必须真跑代码产出）**：



**🔹 通用扩展（任何题型都适用，每个能扩 3-8 页）**：



| 扩展模块 | 内容 | 必须真做的事 | 推荐图表 |

|---|---|---|---|

| **数据预处理章节** | 异常值检测（boxplot/Mahalanobis）/ 缺失值处理（均值/KNN/多重插补）/ 归一化（min-max/z-score/robust）/ 特征工程（PCA/多项式/交互项）/ 数据划分（8:1:1 或 K-Fold） | comp-code 跑预处理脚本，保存 `figures/preprocess_*.json` | EDA 概览 4-panel（basic #1+#5）/ 预处理前后 2-panel / 缺失值热图 / 相关性矩阵 |

| **多算法对比** | 同一问题用 ≥3 个算法解（GA/SA/PSO/Greedy / RF/XGBoost/LightGBM/DNN / SVM/Logistic/kNN） | 真跑所有算法，记录准确率/F1/RMSE/运行时间/收敛迭代数 | 收敛曲线对比（comp #1）/ Performance Profile（adv #25）/ 雷达图 / 方法对比柱状图 |

| **超参敏感性** | 学习率 / batch size / 正则化系数 / 树深度 / λ 罚项；用 grid search / 贝叶斯优化 / Optuna | 用 sklearn.model_selection 跑 GridSearchCV，保存 `figures/hpopt_*.json` | 超参敏感性热图 / 等高线图 / 学习曲线 2-panel |

| **消融实验**（ML 类必备） | 移除某组件看性能变化（完整方法 vs -A vs -B vs -C 各组件） | 真跑每个消融变体，保存 `figures/ablation_*.json` | Diverging Bar（adv #20）/ 消融对比表 |

| **复杂度分析** | 时间复杂度 O(N²)/O(N log N) / 空间复杂度 / 实测 wall clock time（不同 N 下） | 用 time.perf_counter() 真测，画 log-log 复杂度图 | 复杂度 log-log 图 / 内存占用曲线 |

| **理论支撑** | 收敛性证明（数值方法）/ 唯一性证明 / 可行性证明 / 稳定性分析 | 从 MODELING_REPORT.md 抄推导，不能新编；引文献 | TikZ 证明流程图（推导逻辑可视化） |

| **可解释性** | SHAP / LIME / PDP / 决策树可视化 / 注意力图（NN 类） | 用 shap.Explainer / lime 真跑，保存 `figures/explain_*.json` | SHAP 摘要图（adv #7）/ ICE+PDP（adv #26）/ 注意力热图 |



**🔹 工程优化类（A/B 题）专属扩展**：



| 扩展模块 | 内容 | 真做要求 |

|---|---|---|

| **多目标 Pareto** | 双目标 / 三目标 Pareto 前沿 + 决策偏好分析 | 用 NSGA-II / MOEAD 真跑（pymoo 库） |

| **鲁棒性分析** | 数据扰动 / 参数扰动下的解稳定性 | 蒙特卡洛 N=1000 次扰动 |

| **求解器对比** | Gurobi / CPLEX / SCIP / 自实现启发式 | 真跑各求解器对比 |

| **大规模数据扩展** | 100/1000/10000 实例规模下的算法表现 | 跑不同规模 benchmark |



**🔹 数据分析/ML 类（C/D 题）专属扩展**：



| 扩展模块 | 内容 | 真做要求 |

|---|---|---|

| **误差来源分解** | 偏差-方差权衡（bias-variance tradeoff）；噪声拆解 | 5×CV + 多模型测 bias 和 variance |

| **类别不平衡处理** | SMOTE / 欠采样 / 类别权重 | 真跑各方法对比 |

| **特征重要性** | 排列重要性 / SHAP / 信息增益 | 至少 2 种方法交叉验证 |

| **学习曲线诊断** | train / val 损失曲线，判断欠拟合 / 过拟合 | 真跑不同训练集大小 |



**🔹 综合建模类（E/F 题）专属扩展**：



| 扩展模块 | 内容 | 真做要求 |

|---|---|---|

| **多种建模思路对比** | 机理模型 vs 数据驱动 vs 混合模型；同一现象 3 种描述 | 真跑各建模思路 |

| **物理一致性检查** | 量纲检验 / 守恒律 / 边界条件 | 公式真验 |

| **仿真验证** | 数值仿真 vs 解析解 / 历史数据回测 | 真跑仿真代码 |

| **不确定性量化** | 蒙特卡洛 / Bootstrap / 贝叶斯后验 | N≥500 次重复 |



⛔ **仅当本轮确实扩展了章节，才立即重跑 facts_audit**（即时验证扩展内容没引入虚构数字）：



> ⛔ **去重说明**：这份 `paper` 阶段审计与下面 Step 7 的 `facts_audit.py --stage paper` 是**同一份检查**（[13][14][15][16]）。Step 7 的是**权威终检、一定会跑**。所以这里**只在"页数不足→你本轮真的动手扩展了章节"时才补跑**——目的是扩完当场抓虚构数字，不用等到 Step 7。**如果页数已达标、本轮没扩展任何章节，跳过这里**（Step 7 会兜底，不重复跑，省时省额度）。



```bash

# 仅在本轮发生了章节扩展后执行；未扩展则跳过（Step 7 --stage paper 权威兜底）

cd $WORKSPACE_DIR

python3 _utils/facts_audit.py paper  # 重检 [13][14][15][16] 数字溯源 / 事件源 / 约束闭环

```



[15] 会抽 60 个 2 位以上小数浮点数核对是否能在 results.json / PROBLEM_FACTS.json 找到。

**审计 FAIL 不允许结束**，必须把不能溯源的数字改回真实值或删掉。



⛔ **乱码防护（LaTeX 模式）**：



- 公式定界符：`\begin{equation} ... \end{equation}` 或 `$ ... $`（不要 markdown `$$...$$`）

- 特殊字符必须转义：`& → \&`、`% → \%`、`_ → \_`、`# → \#`、`~ → \~{}`、`^ → \^{}`

- 中英文混排：变量符号英文（如 R²、RMSE、α），描述中文；不要中英文之间多空格

- 中文标点和英文符号之间不加空格（如 `f(x)。` 而非 `f(x) 。`）

- 公式中含中文用 `\text{...}`（如 `\sum_{i \in \text{测试集}}`）



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



# ⛔ FIGURE_MANIFEST 对账: 规划了几张就必须画几张并嵌入

echo ""

echo "=== FIGURE_MANIFEST 对账 ==="

PLAN_FILE=""

for f in PROBLEM_ANALYSIS.md PAPER_PLAN.md MODELING_REPORT.md; do

  [ -f "$f" ] && grep -q '<!-- BEGIN FIGURE_MANIFEST -->' "$f" && { PLAN_FILE="$f"; break; }

done

if [ -n "$PLAN_FILE" ]; then

    START=$(grep -n '<!-- BEGIN FIGURE_MANIFEST -->' "$PLAN_FILE" | head -1 | cut -d: -f1)

    END=$(grep -n '<!-- END FIGURE_MANIFEST -->' "$PLAN_FILE" | head -1 | cut -d: -f1)

    EXPECTED_FIGS=$(sed -n "${START},${END}p" "$PLAN_FILE" | grep -oE '^[[:space:]]*-[[:space:]]+(fig_[a-zA-Z0-9_]+|tikz_[a-zA-Z0-9_]+)' | sed 's/^[[:space:]]*-[[:space:]]*//')

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

        echo "⛔ FIGURE_MANIFEST 对账失败 ($manifest_missing 张): 必须把这些图都画出来 + 嵌入正文"

        missing=$((missing + manifest_missing))

    else

        echo "✅ FIGURE_MANIFEST 全部嵌入"

    fi

else

    echo "(没有 FIGURE_MANIFEST, 跳过对账)"

fi

echo "总缺失: $missing"

```

If any figures are missing, go back and embed them into the appropriate sections before finishing. **⛔ Do NOT proceed to Step 7 until missing = 0.** Repeat the check after each fix.



**⛔ 模板完整性自检（写完所有章节后必须检查 main.tex 没有被破坏）：**

```bash

echo "=== main.tex 模板完整性检查 ==="

TMPL_OK=0

TMPL_FAIL=0



# 通用检查（所有模板）

grep -q 'documentclass' paper/main.tex && { echo "✅ documentclass"; TMPL_OK=$((TMPL_OK+1)); } || { echo "❌ 缺少 documentclass"; TMPL_FAIL=$((TMPL_FAIL+1)); }

grep -q '\\input{sections/' paper/main.tex && { echo "✅ sections input"; TMPL_OK=$((TMPL_OK+1)); } || { echo "❌ 缺少 sections input"; TMPL_FAIL=$((TMPL_FAIL+1)); }

grep -q 'thebibliography\|bibliography{' paper/main.tex && { echo "✅ 参考文献"; TMPL_OK=$((TMPL_OK+1)); } || { echo "❌ 缺少参考文献"; TMPL_FAIL=$((TMPL_FAIL+1)); }

grep -q 'appendices\|\\\\appendix' paper/main.tex && { echo "✅ 附录"; TMPL_OK=$((TMPL_OK+1)); } || { echo "❌ 缺少附录"; TMPL_FAIL=$((TMPL_FAIL+1)); }

grep -q 'superscript\|\\@cite\|setcitestyle.*super' paper/main.tex && { echo "✅ 上标引用"; TMPL_OK=$((TMPL_OK+1)); } || { echo "❌ 缺少上标引用定义"; TMPL_FAIL=$((TMPL_FAIL+1)); }



# 五一杯特有检查

if grep -qi 'wuyi\|五一杯' CLAUDE.md 2>/dev/null; then

    grep -q '承诺书' paper/main.tex && { echo "✅ 五一杯承诺书页"; TMPL_OK=$((TMPL_OK+1)); } || { echo "❌ 五一杯缺少承诺书页"; TMPL_FAIL=$((TMPL_FAIL+1)); }

    grep -q 'image2' paper/main.tex && { echo "✅ 五一杯封面logo"; TMPL_OK=$((TMPL_OK+1)); } || { echo "❌ 五一杯缺少封面logo"; TMPL_FAIL=$((TMPL_FAIL+1)); }

    grep -q '关键词' paper/main.tex && { echo "✅ 五一杯关键词"; TMPL_OK=$((TMPL_OK+1)); } || { echo "❌ 五一杯缺少关键词"; TMPL_FAIL=$((TMPL_FAIL+1)); }

fi



# MathorCup 特有检查

if grep -qi 'mathorcup' CLAUDE.md 2>/dev/null; then

    grep -q 'MathorCupmodeling' paper/main.tex && { echo "✅ MathorCup cls"; TMPL_OK=$((TMPL_OK+1)); } || { echo "❌ MathorCup 未使用正确 cls"; TMPL_FAIL=$((TMPL_FAIL+1)); }

    grep -q '\\bianhao\|\\tihao\|\\timu' paper/main.tex && { echo "✅ MathorCup 队伍信息"; TMPL_OK=$((TMPL_OK+1)); } || { echo "❌ MathorCup 缺少队伍信息"; TMPL_FAIL=$((TMPL_FAIL+1)); }

fi



# 亚太赛中文 (APMCM) 特有检查 — 复用 MathorCupmodeling 文档类

if grep -qi 'apmcm_zh\|亚太.*中文\|亚太赛中文' CLAUDE.md 2>/dev/null; then

    grep -q 'MathorCupmodeling' paper/main.tex && { echo "✅ APMCM(中文) cls"; TMPL_OK=$((TMPL_OK+1)); } || { echo "❌ APMCM(中文) 未使用正确 cls (应为 MathorCupmodeling)"; TMPL_FAIL=$((TMPL_FAIL+1)); }

    grep -q '\\bianhao\|\\tihao\|\\timu' paper/main.tex && { echo "✅ APMCM(中文) 队伍信息"; TMPL_OK=$((TMPL_OK+1)); } || { echo "❌ APMCM(中文) 缺少队伍信息"; TMPL_FAIL=$((TMPL_FAIL+1)); }

fi



# 华中杯特有检查

if grep -qi 'huazhong\|华中杯' CLAUDE.md 2>/dev/null; then

    grep -q 'cumcmthesis' paper/main.tex && { echo "✅ 华中杯 cls"; TMPL_OK=$((TMPL_OK+1)); } || { echo "❌ 华中杯未使用 cumcmthesis"; TMPL_FAIL=$((TMPL_FAIL+1)); }

fi



echo ""

echo "模板检查: $TMPL_OK 通过, $TMPL_FAIL 失败"

[ "$TMPL_FAIL" -gt 0 ] && echo "⛔ 必须修复所有失败项！可能是 main.tex 被意外重写了，请从模板重新复制并只替换占位符。"

```



### Step 7: Output



数模竞赛: sections/ numbered by sub-problem (4_problem1.tex, 5_problem2.tex...)

统计建模: sections/ by academic structure (1_introduction.tex, 2_data_method.tex...)



## Key Rules



- Use templates from `templates/`, do not write main.tex from scratch

- Chinese/English abstracts: manual typesetting, not two `\begin{abstract}` environments

- Citation format: use whichever the template provides (stats: natbib `[1]`, cumcm: gbt7714 superscript, huazhong: thebibliography manual entries, wuyi: gbt7714-numerical)

- No `\hypersetup{colorlinks=true}` — conflicts with hidelinks

- Body pages ≥ MAX_PAGES (can exceed, must not fall short)

- No team info — use placeholders

- Tables: three-line style (booktabs)

- Primary output: `paper/` directory, temp files: `_tmp/`

- ⛔ **本步骤只写论文 .tex 文件，不要重新生成图表 PDF、不要修改 code/*.py、不要重新运行分析代码。** 图表和数据已由前序步骤（paper-figure / comp-code）生成完毕，直接引用即可

- Large files: Bash heredoc

- ⛔ **Bash heredoc 必须用带引号的 `'EOF'`（防止 `\\` 被转义）：**

  - ✅ 正确：`cat << 'EOF' > paper/sections/4_problem1.tex`（引号内 `\\` 原样保留）

  - ❌ 错误：`cat << EOF > paper/sections/4_problem1.tex`（无引号，`\\` 变成 `\`，导致表格 `Misplaced \noalign` 错误）

  - 这是表格编译失败的最常见原因——40+ 处 `\\` 全部变成 `\`，编译器只报第一个错就停了



## ⛔ 数据可追溯性（写稿强制规则）



> 防止「图文表面自洽但数据是历史版本」的 bug。详见 `_utils/error_prevention.md` 第九章。



正文/图表/附录引用的**每一个具体数字**必须满足：

1. 能在当前 `results.json` 或 `figures/all_results.json` 里 `grep` 到

2. RESULTS.md 末尾有 `<!-- AUDIT_OK source=results.json rechecked_at=<timestamp> -->` 凭证

3. 工作区没有 `results_v*.json` / `results_old.json` 等历史文件残留

4. 描述任何"依赖载体 / 上游变量动态变化的派生属性"（作用范围 / 时变参数 / 状态依赖容量 / 时变转化率等）时，**禁止**简化成"以静态点为中心的固定区域"或"取均值后当常数"，除非确为静态实体且已显式声明简化条件



写完正文前自检：

```bash

# 1. 检查 RESULTS.md 末尾凭证 + 可疑虚构数字清零

grep -q '<!-- AUDIT_OK source=' RESULTS.md || { echo "❌ 缺 AUDIT_OK 凭证 — 先回 comp-code 跑约束审计"; }

if grep -q 'n_suspicious_numbers=' RESULTS.md; then

    grep -qE 'n_suspicious_numbers=0([^0-9]|$)' RESULTS.md \

        && echo "✅ 审计凭证完整（含虚构数字清零确认）" \

        || echo "❌ 凭证里 n_suspicious_numbers > 0，存在虚构嫌疑数字，先回 comp-code 跑 facts_audit_v2 清理"

else

    echo "✅ 审计凭证存在（旧版凭证，未含虚构数字字段）"

fi



# 1c. ⛔ 普适审计（所有题型必跑：参数密集型 / 简单题 / 普通学术 / 课程论文 / 人文社科）

#     facts_audit.py 在 paper stage 有简化模式：无 PROBLEM_FACTS.json 时

#     仍能跑 [13] 正文结论一致性 + [14] 事件源归属（自动跳过不适用题型）+ [15] 正文数字溯源

#     ⛔ 修复历史 bug：之前 if 是 [-f PROBLEM_FACTS.json]，导致简单题 + PDF 中文工作流

#        全程无 paper 阶段审计，凭印象的虚构数字漏网。改为按 _utils/facts_audit.py 存在判断。

if [ -f _utils/facts_audit.py ]; then

    python3 _utils/facts_audit.py --stage paper 2>&1 | tee -a AUDIT_REPORT.md

    PAPER_RC=$?

    if [ $PAPER_RC -eq 1 ]; then

        echo "❌ Step 5 结论审计失败：正文结论性陈述与 results.json 不一致 / 含虚构数字。先修正文，再编译。"

    fi

fi



# 1d. ⛔ 含多种事件源的题目必查（防"写稿脑补事件源"）

#     凡是涉及"谁做了什么 N 次"的指向性陈述，必须能在 results.json 的 verb_to_sources

#     映射 + events 列表里反推；不允许凭计数器变量名脑补来源。

#     facts_audit --stage paper 的 [14] 项会自动跑事件源归属审计；若 results.json

#     未声明 verb_to_sources/events 字段，本检查跳过（本题不涉及多事件源）。

echo "(事件源归属审计已包含在 facts_audit --stage paper 的 [14] 项里)"



# 2. 检查历史文件残留

HIST=$(ls results_v*.json results_old.json *_backup.json 2>/dev/null | wc -l)

[ "$HIST" -gt 0 ] && echo "⚠ 发现 $HIST 个历史 JSON 文件，可能造成版本漂移：$(ls results_v*.json results_old.json *_backup.json 2>/dev/null)" || echo "✅ 无历史 JSON 残留"



# 3. 数字溯源兜底：⛔ 仅当 facts_audit.py 不可用时才跑这段简化版（30 采样）。

#    facts_audit --stage paper 的 [15] 项已含更全的 60 采样 + 容差匹配 + 溯源；两者都跑会

#    因采样数不同(30 vs 60)给出不一致结论 → AI 反复回查。facts_audit 在时以它为准，不在时

#    这段兜底保证数字溯源不缺席（不降检查覆盖）。

if [ ! -f _utils/facts_audit.py ]; then

python3 -c "

import os, re, json

# 找正文（按优先级试候选路径，任一存在即用；全部不存在则跳过）

text = ''

for p in ('paper/main.tex', 'paper/main.md', 'RESULTS.md', 'main.tex', 'main.md'):

    if os.path.exists(p):

        text = open(p, encoding='utf-8').read()

        print(f'读取正文: {p}')

        break

if not text:

    print('⚠ 未找到正文文件（paper/main.tex / main.md / RESULTS.md），跳过数字溯源检查')

    raise SystemExit(0)

# 合并多份结果 JSON（results.json + figures/all_results.json + 任何 results_*.json 当前版）

results_str = ''

for p in ('results.json', 'figures/all_results.json', 'figures/results.json'):

    if os.path.exists(p):

        try:

            results_str += json.dumps(json.load(open(p, encoding='utf-8')), ensure_ascii=False)

        except Exception as e:

            print(f'⚠ 读取 {p} 失败: {e}')

if not results_str:

    print('⚠ 未找到 results.json / figures/all_results.json，无法做数字溯源校验')

    raise SystemExit(0)

nums = re.findall(r'[-+]?\d+\.\d{2,}', text)[:30]

miss = [n for n in nums if n not in results_str]

print(f'抽样 {len(nums)} 个数字，{len(nums)-len(miss)} 个能在结果 JSON 中找到')

if miss:

    print(f'⚠ 找不到的: {miss[:5]}{\"...\" if len(miss)>5 else \"\"}')

"

fi

```



