---
name: humanities-write-latex
description: "人文社科论文撰写（LaTeX/PDF 版）。基于 OUTLINE.md（含 Claims-Evidence Matrix）撰写完整正文：文本细读 + 理论分析 + 历史语境 + 递进论证，用 $SCHOLAR_SCRIPT 真实检索文献（禁编造），产出 paper/main.tex（ctexart）+ paper/references.bib，交 paper-compile-zh 编译 PDF。严格遵守反 AI 痕迹与引用闭环自检。Use when continuing a humanities/social-science paper workflow in LaTeX/PDF mode."
argument-hint: [paper-topic]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, WebSearch, WebFetch, Agent
---

# 人文社科论文撰写（LaTeX / PDF）

为以下主题撰写人文社科论文正文：**$ARGUMENTS**

> **输出形态**：PDF（LaTeX）。产出 **`paper/main.tex`**（ctexart 文档类，中文）+ **`paper/references.bib`**，
> 由下游 `paper-compile-zh` 用 xelatex 编译成 `paper/main.pdf`。
> 论文以**文字论证 + 文本细读 + 文献对话**为主，默认无图。
> ⛔ **若 `figures/` 目录下有图**（用户开启了数据图表/理论框架图，前置步骤已生成），
> 用 `\begin{figure}...\includegraphics[width=0.8\linewidth]{figures/fig_xxx}...\end{figure}` 嵌入并 `\ref` 引用；
> `figures/` 为空则纯文字撰写，不要伪造图片引用。
> ⛔ **有图时，图的阐述必须承上启下、有逻辑**：先 `cat _utils/writing_rules.md 2>/dev/null || cat skills/shared-scripts/writing_rules.md`，按其中「图不是孤岛/承上启下的逻辑流」原则——每张图从上文自然引出、顺逻辑线阐述、再接到下文（`\caption` 只写简短标签，细节写进正文），**禁止**"凭空冒出一张图 + 一句干巴描述"这种删了不影响行文的孤岛；图号引用句式换着来、两图之间要有充分正文（不连排）。

## 常量
- **WORD_COUNT_TARGET** — 目标字数（默认 8000）
- **CUSTOM_REQUIREMENTS** — 用户自定义要求

## 输入（前置产出）
1. `OUTLINE.md` — 大纲 + Claims-Evidence Matrix + 文献关键词（**必须存在**）
2. `PAPER_PLAN.md` — 文献规划 + FIGURE_MANIFEST
3. `user_data/` — 研究对象文本、已读文献（含 `*_extracted.md`）

## ⛔ 学术严谨性硬规则（任何阶段不可妥协，与 docx 版完全一致）

**R1 文献真实性**
- 每条引用必须来自 `$SCHOLAR_SCRIPT` 真实检索结果，或用户 `user_data/` 提供的材料。
- 绝不编造作者+年份+标题。中文文献若无 DOI，标注真实出处（期刊/出版社+年份），不伪造 DOI。

**R2 文本细读**
- 引用研究对象原文（小说/史料/访谈）必须是 `user_data/` 里真实存在的段落，标页码/章节。
- 不杜撰"原文引文"。找不到就改写为概括性描述。

**R3 论证支撑**
- 每个分论点必须有"材料 + 分析"双重支撑，不空谈理论。

**R4 理论准确性**
- 引用理论家观点（福柯/布尔迪厄/阿甘本等）必须符合其原意，不张冠李戴。
- 拿不准的理论归属，用 WebSearch 核实或改为不归因的表述。

## 工作流程

### Step 0: 恢复检查（断线重跑必读）
```bash
SIZE=$([ -f paper/main.tex ] && wc -c < paper/main.tex || echo 0)
echo "paper/main.tex: $SIZE 字节"
ls figures/*.pdf figures/*.png 2>/dev/null | head
```
| 状态 | 行动 |
|------|------|
| `paper/main.tex` ≥ 6KB | 已写过，检查质量后做引用闭环自检即可 |
| 不存在/过小 | 从 Step 1 开始 |

### Step 1: 读取规划
```bash
[ -f OUTLINE.md ] || { echo "❌ OUTLINE.md 不存在"; exit 1; }
cat OUTLINE.md
[ -f PAPER_PLAN.md ] && cat PAPER_PLAN.md
ls user_data/ 2>/dev/null
mkdir -p paper
```
⛔ 读 user_data 大文件用 `Read` 带 offset/limit 或 `Grep`，不要全量 cat。

### Step 2: 文献检索（SCHOLAR — 真实文献，禁编造）

**先读中国学者发表路径指南**（哪类期刊看哪种文献最多，CSSCI / 北核 / 集刊 / 学位论文差异）：
```bash
cat _utils/humanities-platform-guide.md 2>/dev/null || cat skills/shared-scripts/humanities-platform-guide.md
```

按 OUTLINE.md 的文献关键词检索：
```bash
PYTHON=""; for _c in "$MH_PYTHON" python python3; do [ -z "$_c" ] && continue; if $_c -c "import sys" >/dev/null 2>&1; then PYTHON="$_c"; break; fi; done; [ -z "$PYTHON" ] && PYTHON=python
$PYTHON "$SCHOLAR_SCRIPT" bibtex "研究主题关键词" --max 15
```
- 只引用返回结果中的论文（有 title+authors+year+DOI/真实出处）。检查 `match_label`：good 直用、partial 核对标题、low 换关键词或 WebSearch。
- **人文社科中文文献**：很多在知网/CSSCI，OpenAlex/S2 可能查不到。用户 `user_data/` 提供的文献优先；AI 检索补充英文文献。
- **绝不因"查不到 DOI"就退回编造**；搜不到就改写为不需引用的表述，或标 `[待补充出处]`。
- 把检索到的真实 BibTeX 条目写入 `paper/references.bib`（用 `\cite{key}` 在正文引用）。也可不用 bib，改用文末手写 GB/T 7714 列表 + `\textsuperscript{[N]}` 上标（二选一，全文统一）。

目标 **15-20 篇**（课程论文 15 篇左右即可），宁少勿假。

### Step 3: 逐章撰写（核心）

**⛔ CRITICAL: 不要现在写摘要。** 跳过摘要环境，按 OUTLINE.md 章节顺序先写正文（引言 + 主体各章 + 结论）。摘要位置先留占位符 `% [摘要待 Step 4.5 正文完成后填写]`。摘要必须最后写——它要凝练**各章已写定的核心论点**，先写就是凭设想编结论。

Step 4.5 才回来写摘要：通读已落定的章节，从已存在的论点中提取摘要五段式，不要超出正文范围。

⛔ **先读写作模板**（摘要五段式、引言四步、主体段落"主张-材料-分析-小结"、结论三段式）：
```bash
cat _utils/humanities-writing-templates.md 2>/dev/null | head -120
```

**引用理论家前**，查双语术语对照表（350+ 术语，避免译名混用）：
```bash
cat _utils/humanities-terminology-bilingual.md 2>/dev/null | head -200 || cat skills/shared-scripts/humanities-terminology-bilingual.md | head -200
```

⛔ **写作纪律**：
- 按 OUTLINE.md 的章节顺序和 Claims-Evidence Matrix 逐章写。
- 每章 = 分论点 + 文本/史料/数据支撑 + 理论分析 + 与文献对话 + 小结过渡。
- 学术语体：克制、精确、有论证层次。不用口号、不堆形容词、不空喊"具有重要意义"。
- 段落之间有逻辑推进（递进/转折/因果），不是平行罗列。

### Step 4: 落盘 paper/main.tex（ctexart 中文骨架）

用 `Write` 落盘 `paper/main.tex`。基础骨架（单文件即可，无需拆 sections/*.tex）：

```latex
\documentclass[12pt,a4paper]{ctexart}
\usepackage[margin=2.5cm]{geometry}
\usepackage{setspace}
\usepackage{enumitem}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{hyperref}
\hypersetup{hidelinks}
\onehalfspacing
\setlength{\parindent}{2em}

\title{论文标题}
\author{}
\date{}

\begin{document}
\maketitle

\begin{abstract}
（300-500字：研究问题→方法→核心论点→意义。连贯成段，不分点。）

\noindent\textbf{关键词：} 词1；词2；词3；词4；词5
\end{abstract}

\section{引言}
（提出问题 → 文献综述与对话 → 本文论点与创新 → 结构预告。
引用用 \textsuperscript{\cite{key}} 或脚注 \footnote{...}。）

\section{第一主体章}
（分论点 + 材料 + 分析 + 与文献对话 + 小结过渡）

% ……其余章节……

\section{结论}
（回应引言问题 → 总结论点 → 局限与展望）

% ===== 参考文献（二选一，全文统一）=====
% 方案 A：用 bib（推荐，配合 paper/references.bib）
% \bibliographystyle{gbt7714-numerical} % 若模板支持
% \bibliography{references}
%
% 方案 B：手写列表（无 bib 时用）
\begin{thebibliography}{99}
\bibitem{key1} 作者. 标题[J]. 期刊, 年份, 卷(期): 页码.
% ……实际被引用的文献，按 GB/T 7714-2015……
\end{thebibliography}

\end{document}
```

⛔ **LaTeX 注意事项**：
- 中文标点直接写（ctex 已处理）。`%` `&` `_` `#` `$` 等特殊字符要转义（`\%` `\&` `\_` `\#` `\$`）。
- 引用闭环：每个 `\cite{key}`/上标 [N] 都要有对应文献条目，反之亦然。
- 不要 `\input` 不存在的文件；单文件 main.tex 最稳。

### Step 4.5: 最后写摘要 ⛔

⛔ **MANDATORY: 现在才写摘要**（替换 Step 3 留的占位符 `% [摘要待 Step 4.5 正文完成后填写]`）。

通读 paper/main.tex 中已落定的引言 / 各章 / 结论，按摘要五段式凝练：

1. **研究定位**：从引言的"问题化"凝练，1-2 句
2. **分析框架**：1 句说明方法/路径
3. **各章论点**：依次抽各章核心论点（递进，非罗列），2-3 句
4. **总体结论**：从结论章节的核心论断凝练，1 句
5. **关键词**：3-5 个，覆盖研究对象 + 方法 + 理论框架

中文 300-500 字，连贯成段不分点。**禁止超出正文范围编造论点**。

```bash
# 自检：摘要里的关键概念必须在正文中也出现
abs_kws=$(sed -n 's/.*关键词[：:]//p' paper/main.tex | head -1 | tr '；;，,、 ' '\n' | grep -v '^$')
for kw in $abs_kws; do
  grep -q "$kw" paper/main.tex || echo "⛔ 关键词 $kw 不在正文 — 是否编造？"
done
```

### Step 5: 编译自检 + 引用闭环 ⏎

自检前先读两份规范（21 条文本规则人类版 + GB/T 7714 排版细节）：
```bash
cat _utils/humanities-text-review.md 2>/dev/null || cat skills/shared-scripts/humanities-text-review.md
cat _utils/humanities-formatting-guide.md 2>/dev/null || cat skills/shared-scripts/humanities-formatting-guide.md
```


```bash
echo "=== 1. main.tex 存在性与体量 ==="
[ -f paper/main.tex ] && wc -c < paper/main.tex || echo "❌ 缺 paper/main.tex"

echo "=== 2. LaTeX 结构自检 ==="
grep -c '\\section' paper/main.tex || true
grep -q '\\begin{document}' paper/main.tex && grep -q '\\end{document}' paper/main.tex \
  && echo "✅ document 环境完整" || echo "❌ document 环境不完整"
grep -q '\\documentclass.*ctex' paper/main.tex && echo "✅ ctex 文档类" || echo "⚠ 非 ctex 文档类，中文可能编译失败"

echo "=== 3. 引用闭环（\\cite 或上标 ↔ 文献条目）==="
python3 << 'PY'
import re
t=open('paper/main.tex',encoding='utf-8').read()
cites=set(re.findall(r'\\cite\{([^}]+)\}',t))
cites={k.strip() for grp in cites for k in grp.split(',')}
items=set(re.findall(r'\\bibitem\{([^}]+)\}',t))
# bib 文件里的 key
import os
bibkeys=set()
if os.path.exists('paper/references.bib'):
    bibkeys=set(re.findall(r'@\w+\{([^,]+),',open('paper/references.bib',encoding='utf-8').read()))
known=items|bibkeys
dangling=cites-known if cites else set()
print(f'❌ 悬空 \\cite(无对应条目): {sorted(dangling)}' if dangling else f'✅ {len(cites)} 个 \\cite 都有对应条目')
# 数字上标 [N] 方案
nums=set(int(n) for n in re.findall(r'textsuperscript\{?\[(\d+)\]',t))
if nums: print(f'数字上标引用 {len(nums)} 处（若用手写列表请人工核对编号连续）')
PY

echo "=== 4. 文本质检（21 条规则：可信度/术语/格式/语体/结构/论证）==="
# 质检工具接受 .tex（按行扫描，LaTeX 命令不影响可信度/语体/论证类规则）
PYTHON=""; for _c in "$MH_PYTHON" python python3; do [ -z "$_c" ] && continue; if $_c -c "import sys" >/dev/null 2>&1; then PYTHON="$_c"; break; fi; done; [ -z "$PYTHON" ] && PYTHON=python
REVIEW_PY="${HUMANITIES_REVIEW_SCRIPT:-}"
[ -f "$REVIEW_PY" ] || REVIEW_PY="_utils/humanities_review.py"
[ -f "$REVIEW_PY" ] || REVIEW_PY="tools/humanities_review.py"
if [ -f "$REVIEW_PY" ]; then
  "$PYTHON" "$REVIEW_PY" paper/main.tex --severity warning
else
  echo "（质检工具未就绪，跳过本项；请人工核查文献真实性与引用闭环）"
fi
```
⛔ **质检 error 级问题必须逐条修复后重跑**（编造文献 R1、超年份 R1-03 等是硬伤）。

## ⛔⛔⛔ 完成铁律（最高优先级）
**必须产出 `paper/main.tex`（≥ 6KB，含完整 document 环境）。** ⛔ 用 `Write` 真实落盘，不要只 Read/Bash 就 end_turn。
编译由下游 `paper-compile-zh` 负责，本步骤只产出可编译的 LaTeX 源码。
```bash
PASS=true
[ -f paper/main.tex ] && SZ=$(wc -c < paper/main.tex) || SZ=0
[ "$SZ" -ge 6144 ] && echo "✅ paper/main.tex ($SZ)" || { echo "❌ 缺失/过小 ($SZ) — 立即 Write"; PASS=false; }
grep -q '\\end{document}' paper/main.tex 2>/dev/null || { echo "❌ 缺 \\end{document}"; PASS=false; }
[ "$PASS" != true ] && echo "⛔ 验证未通过"
```

⛔ **图表嵌入检查（若 `figures/` 有图则必跑）：**

```bash
echo "=== 图表嵌入检查 (LaTeX 模式) ==="
missing=0
for pdf in figures/*.pdf figures/*.png; do
    [ -f "$pdf" ] || continue
    bn=$(basename "$pdf")
    if ! grep -rq "$bn" paper/main.tex 2>/dev/null; then
        echo "❌ MISSING: $bn — 已生成但 paper/main.tex 未 \\includegraphics 引用"
        missing=$((missing + 1))
    fi
done
echo "缺失嵌入: $missing"
[ "$missing" -gt 0 ] && echo "⛔ 不允许结束：图已生成但正文未嵌入，必须用 \\begin{figure}...\\includegraphics{figures/xxx}...\\end{figure} 嵌入对应章节。"
```

## 输出文件
- `paper/main.tex` — 最终论文 LaTeX 源（**主产出**，ctexart）
- `paper/references.bib` — 参考文献（若用 bib 方案）

## 关键规则
1. 基于已有 OUTLINE.md 与 Claims-Evidence Matrix，不重新规划。
2. R1-R4 学术诚信红线全程遵守。
3. 文献必须 `$SCHOLAR_SCRIPT` 真实检索，目标 15-20 篇，宁少勿假，查不到标 `[待补充出处]`。
4. 引用闭环：`\cite`/上标 [N] ↔ 文献条目一一对应。
5. 反 AI 痕迹：克制语体、论证递进、不空喊意义。

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

