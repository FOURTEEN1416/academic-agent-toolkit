---

name: course-paper

description: "课程论文撰写。基于已生成的大纲（OUTLINE.md）、数据分析（RESULTS.md）、图表（figures/）撰写完整正文并嵌入图片，严格遵守 Claims-Evidence Matrix 与图表/引用闭环自检。"
argument-hint: [paper-topic]

allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, WebSearch, WebFetch, Agent

---

# 课程论文撰写（基于已规划大纲 + 图表）

为以下主题撰写课程论文正文：**$ARGUMENTS**

## 常量

- **SUBJECT_DOMAIN** — 学科领域

- **WORD_COUNT_TARGET** — 目标字数（默认 8000）

- **CUSTOM_REQUIREMENTS** — 用户自定义要求

## 输入（前置步骤产出）

1. `OUTLINE.md` — 论文大纲 + Claims-Evidence Matrix + 文献关键词（**必须存在**）

2. `PAPER_PLAN.md` — 数据与图表规划（**必须存在**，含「有图表/无图表」分支标记）

3. `RESULTS.md` — 数据分析结果（如有数据分析步骤）

4. `figures/all_results.json` — 数据分析的数值结果（如有）

5. `figures/` — 已生成的图表（PDF + PNG）

6. `user_data/` — 用户上传资料

## 硬约束

1. **必须基于已存在的 OUTLINE.md 与 Claims-Evidence Matrix，不要重新生成大纲。**

2. **图表/正文一致性 4 条铁律**：

   - 写之前 figures/ 中存在的每张图都必须在正文嵌入引用

   - 正文 `![](figures/xxx.png)` 引用的图必须真实存在于 figures/

   - PNG 优先；只有 PDF 时使用 PDF（用 `![](figures/xxx.pdf)`，docx 导出会自动转）

   - 写正文时**禁止**说"如图 X 所示"但 figures/ 没有该图

2b. **⛔ 图表阐述必须承上启下、有逻辑（不许孤岛式）**：先 `cat _utils/writing_rules.md 2>/dev/null || cat skills/shared-scripts/writing_rules.md`，按其中「图不是孤岛/承上启下的逻辑流」原则写——每张图要从上文自然引出、顺一条逻辑线阐述、再接到下文，**禁止**"凭空冒出一张图 + 一句干巴描述（如'图3展示了X分布，可以看出…'）"这种删了不影响行文的孤岛；图号引用句式换着来（别每段都"图N…"开头）、两张图之间必须有充分分析正文（不许连排）。

3. **数值一致性铁律**：正文中的所有数值（精度、误差、参数等）必须能在 RESULTS.md 或 all_results.json 中找到来源。禁止编造数字。

4. **Claims-Evidence 闭环**：OUTLINE.md 中 Matrix 的每个 Claim 必须在正文对应章节出现，且 Evidence 链接确实可达。

5. **引用闭环**：正文上标 `[N]` 必须在参考文献列表中存在；参考文献列表中的每条都必须在正文中被引用。

6. **字数控制**：±20%；各章节字数比例与 OUTLINE.md 规划一致（容差 ±30%）。

7. 输出文件：**`COURSE_PAPER.md`**。

## ⛔⛔⛔ 完成铁律（最高优先级，违反则本步骤失败）

**本步骤必须产出 `COURSE_PAPER.md`（≥ 5KB，完整的课程论文内容）**。

⛔ **MANDATORY: 用 `Write` 工具直接写出 `COURSE_PAPER.md`。不要只调 Read/Bash 工具就 end_turn — 这是本步骤失败的 #1 原因。产出必须是真实落盘的文件。**

⛔ **读用户上传的文献/数据时**：

- 不要 `cat` 整个 `_extracted.md/.txt` 文件 — 一个大文件就能把 context budget 吃光，没空间产出主文件。

- 用 `Read` 工具带 offset/limit 范围读，或用 `Grep` 工具按关键词提取。

- AGENTS.md 已列出所有上传文件清单 + 字数，**优先用清单 + Read 局部，不要全量 cat**。

产出结构、存在性和最低完整性由 `finish` 按模板中的 `output_contract` 自动核验；修复返回的具体问题，不复制执行验证脚本。

## 工作流程

### Step 0: 恢复检查（断线重跑必读）

⛔ **本步骤可能因为断线/手动重跑被多次启动**。每次启动前**必须**先扫描已有产物：

```bash

SIZE=$([ -f COURSE_PAPER.md ] && wc -c < COURSE_PAPER.md || echo 0)

echo "COURSE_PAPER.md: $SIZE 字节"

```

**根据扫描结果决定行动**：

| 状态 | 行动 |

|---|---|

| COURSE_PAPER.md ≥ 8000 字节（≈ 2500 字以上，已是完整论文） | **跳到 Step 6 自检**，仅做最终验证；不要重写已有正文 |

| COURSE_PAPER.md 存在但过小（< 8000 字节） | **续写**：读已有内容 → 用 Edit 工具补缺失章节，**不要从头重写** |

| 不存在 | 从 Step 1 开始 |

⛔ **铁律**：已有 COURSE_PAPER.md 内容不要丢弃；用 Read + Edit 续写。

### Step 1: 读取所有规划文件

```bash

echo "=== 读取大纲 ==="

[ -f OUTLINE.md ] || { echo "❌ OUTLINE.md 不存在，无法继续"; exit 1; }

cat OUTLINE.md

echo "=== 读取图表规划 ==="

[ -f PAPER_PLAN.md ] || { echo "❌ PAPER_PLAN.md 不存在"; exit 1; }

cat PAPER_PLAN.md

echo "=== 检查图表分支 ==="

NO_FIG=$(grep -ciE '^\*\*本论文不规划任何' PAPER_PLAN.md)

echo "无图表分支: $NO_FIG"

echo "=== 列出已生成的图表 ==="

ls -la figures/*.png figures/*.pdf 2>/dev/null

# ⛔ 课程论文是 Word 输出，表格是 Markdown 三线表 .md（不是 .tex）

ls -la figures/TABLE_*.md 2>/dev/null || echo "（暂无 TABLE_*.md）"

echo "=== 读取数据分析结果（如有） ==="

[ -f RESULTS.md ] && head -200 RESULTS.md

[ -f figures/all_results.json ] && python3 -c "import json; d=json.load(open('figures/all_results.json',encoding='utf-8')); print('JSON 顶层 keys:', list(d.keys()) if isinstance(d, dict) else type(d).__name__)"

```

### Step 2: 提取 Claims-Evidence Matrix

```bash

echo "=== 提取 Claims-Evidence Matrix ==="

python3 -c "

import re

text = open('OUTLINE.md', 'r', encoding='utf-8').read()

m = re.search(r'## Claims.Evidence Matrix\s*\n(.*?)(?=\n##|\Z)', text, re.DOTALL | re.IGNORECASE)

if not m:

    print('⚠ OUTLINE.md 未找到 Claims-Evidence Matrix（请补全后再继续）')

else:

    print(m.group(0))

"

```

如果没找到 Matrix，必须先回头补到 OUTLINE.md（这是后续自检的基础）。

### Step 3: 文献调研

基于 `OUTLINE.md` 末尾的"文献调研关键词"清单，使用 WebSearch 搜索：

- 优先近 5 年文献

- 每个核心论点至少有 1-2 篇支撑文献

- 整理成 `references_pool.md`

**⛔ 必须使用 `$SCHOLAR_SCRIPT` 搜索文献，禁止凭记忆编造：**

```bash

PYTHON=""; for _c in "$MH_PYTHON" python python3; do [ -z "$_c" ] && continue; if $_c -c "import sys" >/dev/null 2>&1; then PYTHON="$_c"; break; fi; done; [ -z "$PYTHON" ] && PYTHON=python

SCHOLAR_SCRIPT="tools/scholar_fetch.py"

$PYTHON "$SCHOLAR_SCRIPT" bibtex "你的研究主题关键词" --max 10

```

- 只引用搜索结果中返回的论文（有 title + authors + year + DOI）

- **检查 `match_label`**：`"good"` 直用、`"partial"` 核对标题、`"low"` 换关键词重搜或 WebSearch 兜底；`match_score < 0.3` 不要盲信

- 搜不到的不引用，宁少勿假

- 目标 10-15 篇，搜索结果不足就用搜到的数量

```markdown

## 文献候选池

[1] 作者. 标题[J]. 期刊, 年份, 卷(期): 页码. — 核心观点：xxx — 用于支撑 Claim X

[2] ...

```

### Step 4: 分章撰写（嵌入图表）

按 OUTLINE.md 章节顺序写入 `COURSE_PAPER.md`。

**写作铁律：**

1. **图表嵌入**：在每个需要图的位置写 Markdown 图片语法

   ```markdown

   ![图 4-1：方法对比结果](figures/fig_main_result.png)

   ```

   - 图题格式：`图 X-Y：说明`

   - 必须在该图前后明确引用："如图 4-1 所示，..."

   - **PNG 优先**；如果只有 PDF，写成 `figures/fig_xxx.pdf`（docx 导出会兜底转换）

1b. **表格嵌入（⛔ 必须用预生成的 .md 表格，禁止手抄）**：

   - paper-figure 步骤已把所有结果表格生成为 `figures/TABLE_*.md`（Markdown 三线表，数值来自 JSON，最可靠）

   - 在需要表格的位置**直接嵌入**：`cat figures/TABLE_xxx.md >> COURSE_PAPER.md`（或把 .md 表格内容原样复制进正文），前后加 1-2 句解读

   - ⛔ **禁止**自己凭记忆手写表格数字（会编造/记错）；⛔ **禁止**写 `\begin{table}` / `\input{figures/TABLE_*.tex}`（Word 不渲染 LaTeX）

   - 每个 `figures/TABLE_*.md` 都必须在正文中嵌入，一张都不能漏

2. **数值引用**：如果正文出现数字（精度、误差等），必须在末尾备注其来源章节，便于后续核查

   - 例：「准确率达到 94.7%（详见 §4.2 实验结果）」

   - 数字来源必须可追溯到 `RESULTS.md` 或 `figures/all_results.json`

3. **上标引用**：`[1]`、`[2,3]`、`[4-6]`，每个引用号必须对应参考文献列表中的条目

4. **章节字数比例**：按 OUTLINE.md 中的占比分配（默认）：

   - 引言 15% / 文献综述 20% / 方法 30% / 实验 25% / 结论 10%

5. **语言风格**：学术正式；避免空话；每论点有支撑

6. **段落组织**：每个二级标题下 ≥2 段；用过渡词连接

---

## ⛔⛔⛔ 反 AI 痕迹写作铁律（Word 模式必须遵守，违反等同失败）

**单源共享契约，本地不复制正文**：执行写稿前按 tag 加载 `course_writing_contract.md`（`skills/_utils/` 与 `skills/shared-scripts/` 双副本一致）的 `<anti_ai_trace_rules>` 节，逐条遵守 6+1 条铁律（禁 bullet 叙述 / 加粗格式 / 段长 / 句式多样 / 图号引用 / 去口头禅 / 人文引文纪律）与无图表分支规则：

```bash
RULES="skills/_utils/course_writing_contract.md"; [ -f "$RULES" ] || RULES="academic-toolkit/skills/_utils/course_writing_contract.md"; [ -f "$RULES" ] || RULES="../../skills/_utils/course_writing_contract.md"; sed -n "/<anti_ai_trace_rules>/,/<\/anti_ai_trace_rules>/p" "$RULES"
```
### Step 5: 写参考文献

把 references_pool.md 中实际被引用的文献整理成正式参考文献列表：

```markdown

## 参考文献

[1] 张三, 李四. 论文标题[J]. 期刊名, 2024, 12(3): 45-67.

[2] Smith J. Paper Title[J]. Journal Name, 2023, 10(2): 100-120.

```

格式 GB/T 7714-2015。

### Step 6: 完整自检 ⛔（不能跳过）

写完后必须运行 6 项自检，**任何一项失败必须回去修复后重新自检**。

```bash

echo "================================================="

echo "课程论文写作完成自检（6 项必查）"

echo "================================================="

# ============================

# 自检 1：字数核对

# ============================

echo ""

echo "=== 1. 字数核对 ==="

TARGET=$(grep -E '^- word_count_target:' AGENTS.md 2>/dev/null | sed -E 's/.*: *//' | head -1)

TARGET=${TARGET:-8000}

ACTUAL=$(python3 -c "import re; t=open('COURSE_PAPER.md','r',encoding='utf-8').read(); t=re.sub(r'!\[[^\]]*\]\([^)]+\)','',t); t=re.sub(r'\[[\d,\-]+\]','',t); print(len(t))")

LOW=$((TARGET * 8 / 10))

HIGH=$((TARGET * 12 / 10))

echo "目标字数: $TARGET / 实际: $ACTUAL（容差范围 $LOW ~ $HIGH）"

if [ "$ACTUAL" -lt "$LOW" ]; then

    echo "❌ 字数偏少，需要补充内容"

elif [ "$ACTUAL" -gt "$HIGH" ]; then

    echo "❌ 字数偏多，需要压缩内容"

else

    echo "✅ 字数 OK"

fi

# ============================

# 自检 2：章节字数分配

# ============================

echo ""

echo "=== 2. 各章字数分布 ==="

python3 << 'PY'

import re

text = open('COURSE_PAPER.md', 'r', encoding='utf-8').read()

# 按 ## 一级章节切分

chs = re.split(r'(?m)^## ', text)

for i, ch in enumerate(chs[1:], 1):

    title = ch.split('\n', 1)[0][:30]

    chars = len(ch)

    # 移除图片标记和引用标记后再计数

    body = re.sub(r'!\[[^\]]*\]\([^)]+\)', '', ch)

    body = re.sub(r'\[[\d,\-]+\]', '', body)

    print(f'  §{i} [{title}] — 字符数 {len(body)}')

PY

# ============================

# 自检 3：图表闭环（引用 ↔ 嵌入 ↔ 存在）

# ============================

echo ""

echo "=== 3. 图表闭环检查 ==="

python3 << 'PY'

import os, re

text = open('COURSE_PAPER.md', 'r', encoding='utf-8').read()

# 文中所有 markdown 图片引用

embedded = set(m.group(1) for m in re.finditer(r'!\[[^\]]*\]\(([^)]+)\)', text))

# figures/ 中所有图（同名 png/pdf 视为同一张）

fig_dir = 'figures'

existing = set()

if os.path.isdir(fig_dir):

    for f in os.listdir(fig_dir):

        if f.startswith('fig_') and f.endswith(('.png', '.pdf', '.jpg', '.jpeg')):

            existing.add(os.path.splitext(f)[0])

embedded_basenames = set()

for e in embedded:

    bn = os.path.splitext(os.path.basename(e))[0]

    embedded_basenames.add(bn)

# A. figures/ 有但正文未嵌入

missed_in_text = existing - embedded_basenames

if missed_in_text:

    print('❌ 这些图存在于 figures/ 但正文未引用嵌入:')

    for m in sorted(missed_in_text):

        print('  -', m)

else:

    print('✅ figures/ 中所有图都已被嵌入')

# B. 正文嵌入但 figures/ 没有

missed_in_fs = embedded_basenames - existing

if missed_in_fs:

    print('❌ 这些图被正文引用但 figures/ 中不存在:')

    for m in sorted(missed_in_fs):

        print('  -', m)

else:

    print('✅ 正文嵌入的所有图都真实存在')

# C. 正文中有"如图 X 所示"但没有对应嵌入

ref_without_embed = re.findall(r'如图\s*[\d\-\.]+', text)

if ref_without_embed and not embedded_basenames:

    print('❌ 正文出现"如图 X 所示"但没有任何图片嵌入语法')

PY

# ============================

# 自检 4：Claims-Evidence 闭环

# ============================

echo ""

echo "=== 4. Claims-Evidence 闭环检查 ==="

python3 << 'PY'

import re

plan = open('OUTLINE.md', 'r', encoding='utf-8').read()

paper = open('COURSE_PAPER.md', 'r', encoding='utf-8').read()

m = re.search(r'## Claims.Evidence Matrix\s*\n(.*?)(?=\n##|\Z)', plan, re.DOTALL | re.IGNORECASE)

if not m:

    print('⚠ OUTLINE.md 中未找到 Claims-Evidence Matrix，跳过该项检查')

else:

    table = m.group(1)

    # 提取 Claim 列（第一列）

    rows = [ln for ln in table.split('\n') if '|' in ln and not re.match(r'\s*\|[\s\-:|]+\|\s*$', ln)]

    claims = []

    for r in rows[1:]:  # 跳过表头

        parts = [c.strip() for c in r.strip().strip('|').split('|')]

        if len(parts) >= 1 and parts[0] and parts[0] != 'Claim' and len(parts[0]) > 4:

            claims.append(parts[0])

    if not claims:

        print('⚠ Claims-Evidence Matrix 中未提取到 claim 行')

    else:

        miss = []

        for c in claims:

            # 提取 claim 中的关键词（去除 [] 包装、超过 30 字截断）

            kw = re.sub(r'^\[|\]$', '', c).strip()

            kw_short = kw[:15] if len(kw) > 15 else kw

            # 取前几个汉字/英文词作为搜索锚点

            anchor = re.sub(r'[\W_]+', '', kw_short)[:6]

            if anchor and anchor not in re.sub(r'[\W_]+', '', paper):

                miss.append(c)

        if miss:

            print(f'❌ {len(miss)} 个 claim 未在正文中找到对应内容:')

            for c in miss[:5]:

                print('  -', c[:80])

        else:

            print(f'✅ 所有 {len(claims)} 个 claim 都在正文中有体现')

PY

# ============================

# 自检 5：引用闭环（上标 ↔ 参考文献）

# ============================

echo ""

echo "=== 5. 引用闭环检查 ==="

python3 << 'PY'

import re

text = open('COURSE_PAPER.md', 'r', encoding='utf-8').read()

# 提取参考文献列表的编号（## 参考文献 之后的 [N]）

m = re.search(r'(?m)^##\s*参考文献\s*\n(.*?)(?=\n##|\Z)', text, re.DOTALL)

ref_section = m.group(1) if m else ''

ref_nums = set(int(n) for n in re.findall(r'^\[(\d+)\]', ref_section, re.MULTILINE))

# 提取正文中所有 [N] 引用

body = text[:m.start()] if m else text

cite_nums = set()

for cm in re.finditer(r'\[(\d+(?:[,\-]\d+)*)\]', body):

    seg = cm.group(1)

    for token in seg.split(','):

        if '-' in token:

            a, b = token.split('-')

            cite_nums.update(range(int(a), int(b) + 1))

        else:

            cite_nums.add(int(token))

dangling = cite_nums - ref_nums

unused = ref_nums - cite_nums

if dangling:

    print(f'❌ 正文有 {len(dangling)} 个悬空引用（无对应参考文献条目）: {sorted(dangling)}')

else:

    print(f'✅ 正文 {len(cite_nums)} 个引用号都有对应参考文献')

if unused:

    print(f'⚠ 参考文献中 {len(unused)} 条未被引用: {sorted(unused)} — 建议删除或在正文补充引用')

ref_count = len(ref_nums)

if ref_count < 10:

    print(f'⚠ 参考文献数量 {ref_count} < 10，建议补充')

elif ref_count > 20:

    print(f'⚠ 参考文献数量 {ref_count} > 20，建议精简')

else:

    print(f'✅ 参考文献数量 {ref_count} 在合理范围 [10-20]')

PY

# ============================

# 自检 6：数值一致性（正文 ↔ RESULTS.md）

# ============================

echo ""

echo "=== 6. 数值一致性检查 ==="

python3 << 'PY'

import os, re, json

text = open('COURSE_PAPER.md', 'r', encoding='utf-8').read()

results_text = ''

if os.path.exists('RESULTS.md'):

    results_text += open('RESULTS.md', 'r', encoding='utf-8').read() + '\n'

if os.path.exists('figures/all_results.json'):

    try:

        results_text += json.dumps(json.load(open('figures/all_results.json', 'r', encoding='utf-8')), ensure_ascii=False)

    except: pass

if not results_text:

    print('（无 RESULTS.md 或 all_results.json，跳过数值检查）')

else:

    # 提取正文中的数值（百分比/小数）

    nums_in_paper = set()

    for nm in re.finditer(r'(\d+\.\d+)\s*[%％]?', text):

        nums_in_paper.add(nm.group(1))

    # 用前 4 位匹配（容许尾数修约）

    suspicious = []

    for n in nums_in_paper:

        n4 = n[:4]

        if n4 not in results_text and n not in results_text:

            suspicious.append(n)

    if suspicious:

        print(f'⚠ {len(suspicious)} 个正文数值在 RESULTS/JSON 中找不到来源（可能是编造）:')

        for n in suspicious[:8]:

            print('  -', n)

        print('  请回头核对，或在正文中加上引用 [N] 表明数据出处。')

    else:

        print('✅ 正文所有显式数值都能在 RESULTS/JSON 中找到')

PY

echo ""

echo "================================================="

echo "自检完成。如有 ❌ 项必须修复后重新自检。"

echo "================================================="

```

### Step 7: 残留 Markdown 标记清理

```bash

echo "=== 残留 Markdown 标记 ==="

grep -nE '\*\*[^*]+\*\*|^___' COURSE_PAPER.md | head -10

```

清理 `**bold**` 形式的残留（除非确实需要加粗，但课程论文很少用）。

## 输出文件

## 执行与产出

使用当前执行会话完成本步工作；产物路径按当前步骤合同。程序采集真实操作、输入输出、版本与运行清单，模型只负责实质成果和领域质量。

保留实际输入来源与模板信息；其内容摘要由程序记录。
- `references_pool.md` — 文献候选池（中间产物）

- `COURSE_PAPER.md` — 最终课程论文（**主产出**，含图片嵌入和参考文献）

## 关键规则

1. **必须基于已存在的 OUTLINE.md 与 figures/，不要重新规划。**

2. **图表/正文一致性 4 条铁律必须在自检中通过。**

3. **Claims-Evidence Matrix 是质量基准，每个 Claim 必须在正文有体现。**

4. **引用闭环：上标 ↔ 参考文献条目一一对应。**

5. **数值禁编造**：所有数字必须能在 RESULTS.md 或 all_results.json 中找到来源。

6. **PNG 优先**：Word 导出需要 PNG。

7. **不要堆代码块**：课程论文以叙述为主，代码块只在必要时出现且不超过 15 行。

## ⛔ FIGURE_MANIFEST 对账（写完正文必跑，规划了几张就必须嵌入几张）

**单源共享契约**：对账脚本按 tag 加载 `course_writing_contract.md` 的 `<figure_manifest_reconcile>` 节（`PROD_DOC` 按本技能产物填写：course-paper=COURSE_PAPER.md / course-report=COURSE_REPORT.md）：

```bash
RULES="skills/_utils/course_writing_contract.md"; [ -f "$RULES" ] || RULES="academic-toolkit/skills/_utils/course_writing_contract.md"; [ -f "$RULES" ] || RULES="../../skills/_utils/course_writing_contract.md"; sed -n "/<figure_manifest_reconcile>/,/<\/figure_manifest_reconcile>/p" "$RULES"
```
## ⛔ 通用 paper-stage 审计（所有写稿步骤共用，跨工作流）

**单源共享契约**：审计脚本按 tag 加载 `course_writing_contract.md` 的 `<paper_stage_audit>` 节；审计未通过必须按提示修正正文 / results.json 后重跑：

```bash
RULES="skills/_utils/course_writing_contract.md"; [ -f "$RULES" ] || RULES="academic-toolkit/skills/_utils/course_writing_contract.md"; [ -f "$RULES" ] || RULES="../../skills/_utils/course_writing_contract.md"; sed -n "/<paper_stage_audit>/,/<\/paper_stage_audit>/p" "$RULES"
```
