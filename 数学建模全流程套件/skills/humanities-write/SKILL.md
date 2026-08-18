---
name: humanities-write
description: "人文社科论文撰写。基于 OUTLINE.md（含 Claims-Evidence Matrix）撰写完整正文：文本细读 + 理论分析 + 历史语境 + 递进论证，用 $SCHOLAR_SCRIPT 真实检索文献（禁编造），产出 HUMANITIES_PAPER.md。严格遵守反 AI 痕迹与引用闭环自检。Use when continuing a humanities/social-science paper workflow."
argument-hint: [paper-topic]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, WebSearch, WebFetch, Agent
---

# 人文社科论文撰写（基于已规划大纲）

为以下主题撰写人文社科论文正文：**$ARGUMENTS**

> **输出形态**：Word（docx）。产出 **`HUMANITIES_PAPER.md`**（markdown，下游 docx-export 转 .docx）。
> 论文以**文字论证 + 文本细读 + 文献对话**为主，默认无图。
> ⛔ **若 `figures/` 目录下有图**（用户开启了数据图表/理论框架图，前置步骤已生成），
> 则在对应章节用 markdown 图片语法 `![图N：说明](figures/fig_xxx.png)` 嵌入，并在正文「如图 N 所示」处引用；
> 禁用 `\includegraphics` 等 LaTeX 命令。`figures/` 为空则纯文字撰写，不要伪造图片引用。
> ⛔ **有图时，图的阐述必须承上启下、有逻辑**：先 `cat _utils/writing_rules.md 2>/dev/null || cat skills/shared-scripts/writing_rules.md`，按其中「图不是孤岛/承上启下的逻辑流」原则——每张图从上文自然引出、顺逻辑线阐述、再接到下文，**禁止**"凭空冒出一张图 + 一句干巴描述"这种删了不影响行文的孤岛；图号引用句式换着来（别每段都"图N…"开头）、两图之间要有充分正文（不连排）。

## 常量
- **WORD_COUNT_TARGET** — 目标字数（默认 8000）
- **CUSTOM_REQUIREMENTS** — 用户自定义要求

## 输入（前置产出）
1. `OUTLINE.md` — 大纲 + Claims-Evidence Matrix + 文献关键词（**必须存在**）
2. `PAPER_PLAN.md` — 文献规划 + FIGURE_MANIFEST
3. `user_data/` — 研究对象文本、已读文献（含 `*_extracted.md`）

## ⛔ 学术严谨性硬规则（任何阶段不可妥协）

**R1 不编造**：绝不生成不可查阅的文献（作者/标题/期刊/年份/页码任一项都不能编）。绝不虚构引文内容（没读到原文就说没读到）。绝不编造史实/年份/事件细节。
**R2 区分知道与不知道**：不确定的引文位置用占位符 `[待补充出处]`，不要编一个"看似合理"的引用。
**R3 文献红线**：不根据标题推测内容；没读到原文不描述其"论证过程/核心发现"；不混淆"作者观点"与"作者引用的他人观点"。
**R4 生成后自查**：所有文献是否真实？所有引文是否标了来源（哪怕占位符）？有没有把推测写成断言？

## ⛔ 方法论三原则
1. 理论是工具、文本/史料是目的地（理论命名材料里已存在的现象，不是给材料强加答案）。
2. 历史背景是语境不是解释（背景回答"为何此时提出此问题"，不回答"文本说了什么"）。正确顺序：材料细读 → 指出内部张力 → 引入历史背景 → 论证对应关系。
3. 论点从材料内部生长。

## 工作流程

### Step 0: 恢复检查（断线重跑必读）
```bash
SIZE=$([ -f HUMANITIES_PAPER.md ] && wc -c < HUMANITIES_PAPER.md || echo 0)
echo "HUMANITIES_PAPER.md: $SIZE 字节"
```
| 状态 | 行动 |
|---|---|
| ≥ 8000 字节（已是完整论文） | 跳到 Step 5 自检，不重写 |
| 存在但过小 | 读已有内容 → Edit 续写缺失章节，不从头重写 |
| 不存在 | 从 Step 1 开始 |

### Step 1: 读取规划
```bash
[ -f OUTLINE.md ] || { echo "❌ OUTLINE.md 不存在"; exit 1; }
cat OUTLINE.md
[ -f PAPER_PLAN.md ] && cat PAPER_PLAN.md
```
⛔ 读 user_data 大文件用 `Read` 带 offset/limit 或 `Grep`，不要全量 cat。

### Step 2: 提取 Claims-Evidence Matrix
```bash
python3 -c "
import re
t=open('OUTLINE.md',encoding='utf-8').read()
m=re.search(r'## Claims.Evidence Matrix\s*\n(.*?)(?=\n##|\Z)',t,re.DOTALL|re.IGNORECASE)
print(m.group(0) if m else '⚠ 未找到 Matrix，需先补到 OUTLINE.md')
"
```

### Step 3: 文献检索（⛔ 用工具，禁编造）

读取文献综述/拆解方法 + 中国学者发表路径（哪类期刊看哪种文献最多）：
```bash
cat _utils/humanities-literature-review.md 2>/dev/null || cat skills/shared-scripts/humanities-literature-review.md
cat _utils/humanities-platform-guide.md 2>/dev/null || cat skills/shared-scripts/humanities-platform-guide.md
```

**英文文献 + 有 DOI 的中外文献 → 用 `$SCHOLAR_SCRIPT` 真实检索：**
```bash
PYTHON=""; for _c in "$MH_PYTHON" python python3; do [ -z "$_c" ] && continue; if $_c -c "import sys" >/dev/null 2>&1; then PYTHON="$_c"; break; fi; done; [ -z "$PYTHON" ] && PYTHON=python
$PYTHON "$SCHOLAR_SCRIPT" bibtex "研究主题关键词" --max 15
```
- 只引用返回结果中的论文（有 title+authors+year+DOI/真实出处）。检查 `match_label`：good 直用、partial 核对标题、low 换词重搜。
- 中文人文社科文献很多无 DOI：OpenAlex 兜底返回的真实中文论文标题可用，自动 BibTeX 标 `% [VERIFY]` 提醒核对卷期页码。
- **绝不因"查不到 DOI"就退回编造**；搜不到就改写为不需引用的表述，或标 `[待补充出处]`。

**用户自己在知网/国家哲社文献中心(NCPSSD)/万方搜索后提供的文献**：按 `_utils/humanities-literature-analysis.md` 的五层拆解法分析整合（只分析提取到的原文，不推测未读部分）。

目标 **15-20 篇**（课程论文 15 篇左右即可），宁少勿假。整理成 `references_pool.md`。

### Step 4: 分章撰写（HUMANITIES_PAPER.md）

**⛔ CRITICAL: 不要现在写摘要。** 跳过摘要章节，按 OUTLINE.md 章节顺序先写正文（引言 + 主体各章 + 结论）。摘要位置先留占位符 `<!-- 摘要待 Step 4.5 正文完成后填写 -->`。摘要必须最后写——因为它要凝练**各章已写定的核心论点**，先写就是凭设想编结论。

Step 4.5 才回来写摘要：到时候通读已落定的引言/各章/结论，从已存在的论点中提取摘要五层（研究定位 → 分析框架 → 各章论点 → 总体结论 → 关键词），不要超出正文范围。

按 OUTLINE.md 章节顺序写。**写作模板（摘要五层结构、引言五步、章节开头/结尾、过渡段、论点句、理论引入、结语、脚注）必读**：
```bash
cat _utils/humanities-writing-templates.md 2>/dev/null || cat skills/shared-scripts/humanities-writing-templates.md
```

**引用理论家 / 学派核心概念前**，先查双语术语对照表（350+ 术语，统一中文译名，避免「赤裸生命/裸命/裸生命」混译）：
```bash
cat _utils/humanities-terminology-bilingual.md 2>/dev/null || cat skills/shared-scripts/humanities-terminology-bilingual.md | head -200
```
（文件较大用 head 看头部即可；按需用 grep 查具体术语）

核心写法（详见模板）：
- **摘要**五层：研究定位 → 分析框架 → 各章论点（递进，非罗列）→ 总体结论 → 关键词。
- **引言**五步：有张力的细节切入 → 问题化 → 学术史定位 → 分析框架 → 论点句。**不要**从"X 是重要作品"或时代背景开头。
- **章节开头**从材料细节或上章张力切入，不从理论定义/背景介绍开头。
- **章节结尾**：收拢论点 → 点出遗留张力 → 用一个从论证内部生长的问题引向下章（不写"下一章将分析…"）。
- **理论引入**三层：定义（自己的语言）→ 适用性论证 → 落地到具体细节。不要词典式介绍、不要大段引原文。
- **材料细读**：找有张力的细节（不是著名段落）→ 慢读（为什么是这个词/时态）→ 从细节推出论点。
- **结语**三步：收拢核心洞察（非各章结论叠加）→ 回应引言核心问题 → 向更大问题敞开。

### ⛔⛔⛔ 反 AI 痕迹写作铁律（Word 模式必守，违反等同失败）

1. **禁止用 markdown bullet/编号（`-`/`*`/`1.`）写正文叙述。** "三个递进的子问题""研究目标""创新点"等必须用连贯段落 + 过渡词（首先/其次/最后），或行内括号编号（1）（2）（3）。bullet 仅用于参考文献列表等。
2. **加粗写 `**标签**：内容`，不要 `**标签：**内容`**（冒号包进 `**` 里 docx 引擎匹配不到，留下孤立 `**`）。
3. **每段至少 3-5 句**，1-2 句短段是 AI 痕迹。
4. **连续段落不能同句式开头**（三段都"本文…"必改，交替用"首先/为此/在此基础上/不同于/另一方面"）。
5. **去 AI 口头禅**：少用"值得注意的是""综上所述""随着…的发展""具有重要意义"。"研究表明"必须紧跟具体引用号 [N]。
6. **理论/引文是论据不是主语**：段落不要以"福柯认为""如某某所说"开头堆砌；先提出你的论点 → 引文/理论作支撑 → 推论。

### ⛔ 公式与特殊格式
- 人文社科一般无公式；若涉及（如语言学/逻辑学），行内用 `$...$`、块级用独立成行的 `$$...$$`（`$$` 必须成对、独占一行）。
- 中文引号用全角""''；外文人名首次出现可括注原文，传记信息放脚注。

### Step 4.5: 最后写摘要 ⛔

⛔ **MANDATORY: 现在才写摘要**（替换 Step 4 留的占位符）。

通读 HUMANITIES_PAPER.md 已落定的引言 / 各章 / 结论，按摘要五层结构提取：

1. **研究定位**：从引言的"问题化"和"学术史定位"段落凝练
2. **分析框架**：从引言的"分析框架"句子凝练
3. **各章论点**：依次抽取各章的核心论点句（递进，非罗列）
4. **总体结论**：从结论章节的核心论断凝练
5. **关键词**：3-5 个，覆盖研究对象 + 方法 + 理论框架

中文摘要 300-500 字，连贯成段不分点。**禁止超出正文范围编造论点**。

```bash
# 自检：摘要里的关键概念必须在正文中也出现
for kw in $(echo "你的关键词1 你的关键词2 你的关键词3"); do
  grep -q "$kw" HUMANITIES_PAPER.md || echo "⛔ 关键词 $kw 不在正文 — 是否编造？"
done
```

### Step 5: 写参考文献 + 自检 ⛔

自检前先读两份规范（21 条文本规则人类版 + GB/T 7714 排版细节，给 Claude 整体直觉）：
```bash
cat _utils/humanities-text-review.md 2>/dev/null || cat skills/shared-scripts/humanities-text-review.md
cat _utils/humanities-formatting-guide.md 2>/dev/null || cat skills/shared-scripts/humanities-formatting-guide.md
```


参考文献按 GB/T 7714-2015 格式，把 `references_pool.md` 中**实际被引用**的整理成列表。

写完跑自检（任一 ❌ 必修后重检）：
```bash
echo "=== 1. 字数 ==="
TARGET=$(grep -E '^- word_count_target:' CLAUDE.md 2>/dev/null | sed -E 's/.*: *//' | head -1); TARGET=${TARGET:-8000}
ACTUAL=$(python3 -c "import re;t=open('HUMANITIES_PAPER.md',encoding='utf-8').read();t=re.sub(r'\[[\d,\-]+\]','',t);print(len(t))")
echo "目标 $TARGET / 实际 $ACTUAL（容差 $((TARGET*8/10))~$((TARGET*12/10))）"

echo "=== 2. 引用闭环（上标 ↔ 参考文献）==="
python3 << 'PY'
import re
text=open('HUMANITIES_PAPER.md',encoding='utf-8').read()
m=re.search(r'(?m)^##\s*参考文献\s*\n(.*?)(?=\n##|\Z)',text,re.DOTALL)
ref=set(int(n) for n in re.findall(r'^\[(\d+)\]',m.group(1) if m else '',re.MULTILINE))
body=text[:m.start()] if m else text
cite=set()
for cm in re.finditer(r'\[(\d+(?:[,\-]\d+)*)\]',body):
    for tok in cm.group(1).split(','):
        if '-' in tok: a,b=tok.split('-'); cite.update(range(int(a),int(b)+1))
        else: cite.add(int(tok))
dangling=cite-ref; unused=ref-cite
print(f'❌ 悬空引用(无对应文献): {sorted(dangling)}' if dangling else f'✅ {len(cite)} 个引用都有对应文献')
if unused: print(f'⚠ 参考文献未被引用: {sorted(unused)}')
n=len(ref)
print(f'⚠ 文献 {n} 篇 <15 偏少' if n<15 else (f'⚠ 文献 {n} 篇 >25 偏多' if n>25 else f'✅ 文献 {n} 篇在合理区间[15-20]'))
PY

echo "=== 3. Claims-Evidence 闭环 ==="
python3 << 'PY'
import re
plan=open('OUTLINE.md',encoding='utf-8').read(); paper=open('HUMANITIES_PAPER.md',encoding='utf-8').read()
m=re.search(r'## Claims.Evidence Matrix\s*\n(.*?)(?=\n##|\Z)',plan,re.DOTALL|re.IGNORECASE)
if not m: print('⚠ 无 Matrix，跳过')
else:
    rows=[l for l in m.group(1).split('\n') if '|' in l and not re.match(r'\s*\|[\s\-:|]+\|\s*$',l)]
    claims=[ [c.strip() for c in r.strip().strip('|').split('|')][0] for r in rows[1:] ]
    claims=[c for c in claims if c and c!='Claim' and len(c)>4]
    miss=[c for c in claims if re.sub(r'[\W_]+','',re.sub(r'^\[|\]$','',c))[:6] not in re.sub(r'[\W_]+','',paper)]
    print(f'❌ {len(miss)} 个 claim 未在正文体现: '+'; '.join(c[:40] for c in miss[:5]) if miss else f'✅ 全部 {len(claims)} 个 claim 都有体现')
PY

echo "=== 4. 残留 markdown 标记 ==="
grep -nE '\*\*[^*]+\*\*' HUMANITIES_PAPER.md | head -5 || echo "✅ 无残留 **"

echo "=== 5. 文本质检（21 条规则：可信度/术语/格式/语体/结构/论证）==="
# $HUMANITIES_REVIEW_SCRIPT = humanities_review.py 绝对路径（引擎已注入）；缺失时回退工作区 _utils 或仓库 tools
PYTHON=""; for _c in "$MH_PYTHON" python python3; do [ -z "$_c" ] && continue; if $_c -c "import sys" >/dev/null 2>&1; then PYTHON="$_c"; break; fi; done; [ -z "$PYTHON" ] && PYTHON=python
REVIEW_PY="${HUMANITIES_REVIEW_SCRIPT:-}"
[ -f "$REVIEW_PY" ] || REVIEW_PY="_utils/humanities_review.py"
[ -f "$REVIEW_PY" ] || REVIEW_PY="tools/humanities_review.py"
if [ -f "$REVIEW_PY" ]; then
  "$PYTHON" "$REVIEW_PY" HUMANITIES_PAPER.md --severity warning
else
  echo "（质检工具未就绪，跳过本项；请人工核查文献真实性与引用闭环）"
fi
```
⛔ **质检 error 级问题必须逐条修复后重跑**（编造文献 R1、空脚注 F-01、超年份 R1-03 等是硬伤）。
warning 级（术语不一致 T、过度断言 R3、语体 S、论证断裂 L）尽量修；修不动的要能说明理由。


## ⛔⛔⛔ 完成铁律（最高优先级）
**必须产出 `HUMANITIES_PAPER.md`（≥ 5KB）。** ⛔ 用 `Write` 真实落盘，不要只 Read/Bash 就 end_turn。
```bash
PASS=true
[ -f HUMANITIES_PAPER.md ] && SZ=$(wc -c < HUMANITIES_PAPER.md) || SZ=0
[ "$SZ" -ge 5120 ] && echo "✅ HUMANITIES_PAPER.md ($SZ)" || { echo "❌ 缺失/过小 ($SZ) — 立即 Write"; PASS=false; }
[ "$PASS" != true ] && echo "⛔ 验证未通过"
```

⛔ **图表嵌入检查（若 `figures/` 有图则必跑）：**

```bash
echo "=== 图表嵌入检查 (Markdown/docx 模式) ==="
missing=0
for img in figures/*.png figures/*.pdf figures/*.jpg figures/*.svg; do
    [ -f "$img" ] || continue
    bn=$(basename "$img")
    [ "$bn" = "latex_includes.tex" ] && continue
    if [ -f HUMANITIES_PAPER.md ]; then
        if ! grep -q "$bn" HUMANITIES_PAPER.md; then
            echo "❌ MISSING: $bn — 已生成但 HUMANITIES_PAPER.md 未用 ![caption](figures/$bn) 嵌入"
            missing=$((missing + 1))
        fi
    fi
done
echo "缺失嵌入: $missing"
[ "$missing" -gt 0 ] && echo "⛔ 不允许结束：图已生成但正文未嵌入，必须在对应章节用 ![图N：说明](figures/xxx.png) 嵌入。"
```

## 输出文件
- `references_pool.md` — 文献候选池（中间产物）
- `HUMANITIES_PAPER.md` — 最终论文（**主产出**，含参考文献）

## 关键规则
1. 基于已有 OUTLINE.md 与 Claims-Evidence Matrix，不重新规划。
2. R1-R4 学术诚信红线 + 方法论三原则全程遵守。
3. 文献必须 `$SCHOLAR_SCRIPT` 真实检索，目标 15-20 篇，宁少勿假，查不到标 `[待补充出处]`。
4. 引用闭环：上标 [N] ↔ 参考文献条目一一对应。
5. 反 AI 痕迹 6 条铁律必须遵守（Word 输出）。
6. 论证必须递进、理论必须落地到具体材料细节。

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

