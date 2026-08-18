---
name: course-report
description: "课程报告撰写。基于已生成的项目事实底稿、大纲、数据与架构图撰写完整正文并嵌入图片，严格遵守事实/Claims/图表/引用闭环自检。Use when continuing a course report workflow."
argument-hint: [project-topic]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, WebSearch, WebFetch, Agent
---

# 课程报告撰写（基于已规划大纲 + 图表）

为以下项目撰写课程报告正文：**$ARGUMENTS**

## 常量

- **SUBJECT_DOMAIN** — 学科领域
- **WORD_COUNT_TARGET** — 目标字数（默认 10000）
- **CUSTOM_REQUIREMENTS** — 用户自定义要求

## 输入（前置步骤产出）

1. `OUTLINE.md` — 报告大纲 + Claims-Evidence Matrix（**必须存在**）
2. `PROJECT_FACTS.md` — 项目事实底稿（**必须存在**，注明有/无源码）
3. `PAPER_PLAN.md` — 数据/图表/架构图规划（**必须存在**）
4. `RESULTS.md` — 数据分析结果（如有）
5. `figures/` — 已生成的图表（架构图/E-R 图/流程图/数据图，PDF + PNG）
6. `user_data/` — 用户上传资料（源码、要求文档、数据）

## 硬约束

1. **必须基于已存在的 OUTLINE.md / PROJECT_FACTS.md / figures/，不许重新规划。**
2. **事实一致性**：正文中所有功能描述必须能在 PROJECT_FACTS.md 中找到对应项；禁止编造模块、函数名、行号。无源码时全部用「拟采用/建议」推测语气。
3. **图表/正文一致性 4 条铁律**（同 course-paper）。
3b. **⛔ 图表阐述必须承上启下、有逻辑（不许孤岛式）**：先 `cat _utils/writing_rules.md 2>/dev/null || cat skills/shared-scripts/writing_rules.md`，按其中「图不是孤岛/承上启下的逻辑流」原则写——架构图/E-R图/流程图/数据图都要从上文自然引出、顺逻辑阐述、再接到下文，**禁止**"凭空冒出一张图 + 一句干巴描述"这种删了不影响行文的孤岛；图号引用句式换着来（别每段都"图N…"开头）、两张图之间必须有充分分析正文（不许连排）。
4. **系统实现章节最长**（占总字数 30-40%）。
5. **关键代码片段控制在 10-20 行**。
6. **Claims-Evidence 闭环**、**引用闭环**、**数值一致性** 三大自检必须通过。
7. 输出文件：**`COURSE_REPORT.md`**。

## ⛔⛔⛔ 完成铁律（最高优先级，违反则本步骤失败）

**本步骤必须产出 `COURSE_REPORT.md`（≥ 3KB，完整的课程报告内容）**。

⛔ **MANDATORY: 用 `Write` 工具直接写出 `COURSE_REPORT.md`。不要只调 Read/Bash 工具就 end_turn — 这是本步骤失败的 #1 原因。产出必须是真实落盘的文件。**

⛔ **读用户上传的文献/数据时**：
- 不要 `cat` 整个 `_extracted.md/.txt` 文件 — 一个大文件就能把 context budget 吃光，没空间产出主文件。
- 用 `Read` 工具带 offset/limit 范围读，或用 `Grep` 工具按关键词提取。
- CLAUDE.md 已列出所有上传文件清单 + 字数，**优先用清单 + Read 局部，不要全量 cat**。

⛔ **结束前必跑 PASS 阻断验证**（只 echo "❌" 不算，必须显式判定）：
```bash
PASS=true
[ -f COURSE_REPORT.md ] && SZ=$(wc -c < COURSE_REPORT.md) || SZ=0
if [ "$SZ" -ge 3072 ]; then
    echo "✅ COURSE_REPORT.md ($SZ bytes)"
else
    echo "❌ COURSE_REPORT.md 缺失或过小 ($SZ bytes) — 立即用 Write 工具产出, 不要 end_turn"
    PASS=false
fi
[ "$PASS" != true ] && echo "⛔ 验证未通过 — 必须修复后再结束本步骤"
```


## 工作流程

### Step 0: 恢复检查（断线重跑必读）

⛔ **本步骤可能因为断线/手动重跑被多次启动**。每次启动前**必须**先扫描已有产物：

```bash
SIZE=$([ -f COURSE_REPORT.md ] && wc -c < COURSE_REPORT.md || echo 0)
echo "COURSE_REPORT.md: $SIZE 字节"
```

**根据扫描结果决定行动**：

| 状态 | 行动 |
|---|---|
| COURSE_REPORT.md ≥ 5000 字节（≈ 1500 字以上，已是完整报告） | **跳到 Step 6 自检**，仅做最终验证；不要重写已有正文 |
| COURSE_REPORT.md 存在但过小（< 5000 字节） | **续写**：读已有内容 → 用 Edit 工具补缺失章节，**不要从头重写** |
| 不存在 | 从 Step 1 开始 |

⛔ **铁律**：已有 COURSE_REPORT.md 内容不要丢弃；用 Read + Edit 续写。

### Step 1: 读取所有规划文件

```bash
echo "=== 读取项目事实 ==="
[ -f PROJECT_FACTS.md ] || { echo "❌ PROJECT_FACTS.md 不存在"; exit 1; }
cat PROJECT_FACTS.md

# 检测是否「无源码」分支
NO_CODE=$(grep -ciE '用户未上传项目源码|无源码' PROJECT_FACTS.md | head -1)
echo "无源码分支: $NO_CODE"

echo "=== 读取大纲 ==="
[ -f OUTLINE.md ] || { echo "❌ OUTLINE.md 不存在"; exit 1; }
cat OUTLINE.md

echo "=== 读取图表规划 ==="
[ -f PAPER_PLAN.md ] || { echo "❌ PAPER_PLAN.md 不存在"; exit 1; }
cat PAPER_PLAN.md

echo "=== 列出已生成的图表 ==="
ls -la figures/*.png figures/*.pdf 2>/dev/null
# ⛔ 课程报告是 Word 输出，数据表格是 Markdown 三线表 .md（不是 .tex），必须嵌入
ls -la figures/TABLE_*.md 2>/dev/null || echo "（暂无 TABLE_*.md）"

echo "=== 读取数据分析结果（如有） ==="
[ -f RESULTS.md ] && head -200 RESULTS.md
```

### Step 2: 提取 Claims-Evidence Matrix

```bash
python3 -c "
import re
text = open('OUTLINE.md', 'r', encoding='utf-8').read()
m = re.search(r'## Claims.Evidence Matrix\s*\n(.*?)(?=\n##|\Z)', text, re.DOTALL | re.IGNORECASE)
print(m.group(0) if m else '⚠ 未找到 Claims-Evidence Matrix')
"
```

### Step 3: 分章撰写（基于事实，嵌入图表）

按 OUTLINE.md 章节顺序写入 `COURSE_REPORT.md`。

**写作铁律：**

1. **第三章设计图嵌入**（如已生成）：
   - 系统总体架构图：`![图 3-1：系统总体架构](figures/fig_arch.png)`
   - E-R 图：`![图 3-2：数据库 E-R 图](figures/fig_er.png)`
   - 业务流程图：`![图 3-x：xxx 流程](figures/fig_flow_xxx.png)`

2. **第四章实现要求**：
   - **每个主要模块**：功能说明 → 关键代码 10-20 行 → 运行效果 → 流程图（如有）
   - 代码片段必须从 PROJECT_FACTS.md 中实际存在的文件取
   - 代码块标注语言：```python / ```javascript 等
   - **无源码分支**：代码示例改写为「示例代码」，使用推测性措辞

3. **第五章测试与结果**：
   - 测试环境用 Markdown 表格
   - ≥3 个功能测试用例（表格）
   - 有数据分析则在此嵌入 fig_perf 等
   - **⛔ paper-figure 已生成的数据表格 `figures/TABLE_*.md`（Markdown 三线表，数值来自 JSON）必须直接嵌入**：`cat figures/TABLE_xxx.md >> COURSE_REPORT.md`（或原样复制进正文），前后加解读。禁止手抄表格数字，禁止写 `\begin{table}`/`\input{*.tex}`（Word 不渲染 LaTeX）。每个 TABLE_*.md 都要嵌入

4. **图片嵌入规范**：图题 `图 X-Y：说明`；PNG 优先

5. **语言风格**：正式但不生硬；具体到模块名/函数名（来自 PROJECT_FACTS）；无源码时用「拟」「建议」「假设」措辞

---

## ⛔⛔⛔ 反 AI 痕迹写作铁律（Word 模式必须遵守，违反等同失败）

Word 输出最常被识别为「AI 写的」就是因为下面这 6 条没遵守。优先级凌驾于章节模板和字数要求。

1. **禁止 markdown bullet/编号列表（`-`、`*`、`1.`、`2.`）作为正文叙述。** 含「需求一/二/三」「设计目标」「关键功能」「核心模块」「子任务」「待解决问题」等场景必须用连贯段落，不许分点罗列。
   - ❌ 错（最典型 AI 痕迹）：
     ```
     本系统需依次实现三个核心功能：
     - 功能一：用户登录与鉴权…
     - 功能二：数据采集与持久化…
     - 功能三：可视化报表生成…
     ```
   - ✅ 对（连贯段落 + 过渡词）：`本系统需依次实现三个核心功能。**首先**，用户登录与鉴权模块基于 JWT 实现…；**其次**，数据采集层通过…；**最后**，可视化报表模块基于 ECharts…。`
   - ✅ 替代（行内括号编号）：`本系统需依次实现三个核心功能：（1）用户登录与鉴权；（2）数据采集与持久化；（3）可视化报表生成。`
   - bullet **唯一允许场景**：输入清单 / 软件依赖 / 接口定义 / 测试用例表 / 参考文献列表，正文叙述一律禁止。

2. **加粗写作 `**标签**：内容`，不要 `**标签：**内容`。** 把冒号包进 `**` 里 docx 引擎正则匹配不到，会留下孤立 `**` 残留。
   - ❌ `**关键词：** 系统设计；模块化；…`
   - ✅ `**关键词**：系统设计；模块化；…`

3. **每段至少 3-5 句话。** 1-2 句的短段落是 AI 痕迹；要么扩写到 3 句以上，要么并入相邻段落。

4. **连续段落不能以相同句式开头。** 三段都「本系统…」开头必须改，交替用「首先」「为此」「在此基础上」「针对…」「不同于…」「另一方面」等多样化连接词。

5. **图号必须显式引用，但句式换着来（标准优秀论文口径）。** 每张图/表都要点名「图 N」让读者对上号（硬规范，别为避免套路删图号）。要禁的是**"图 X 展示了……从图中可以看出……"这种图作主语+空话的单调流水账**，不是禁止一切图作主语。相邻两图引用句式必须不同，在括号旁注（首选）／句首带出／动词引导／图作主语（带实质结论时允许）／后置印证间轮换。
   - ❌ `图 3 展示了系统总体架构。从图中可以看出，本系统采用三层架构。`（图作主语+空话）
   - ✅ 括号旁注：`本系统采用经典三层架构（图 3），展示层、业务层与数据层之间通过 REST 接口解耦。`
   - ✅ 图作主语（带实质结论）：`图 3 给出了系统的三层架构，其中业务层通过 REST 接口与数据层解耦，便于独立扩展。`

6. **去掉 AI 写作口头禅。** 少用「值得注意的是」「综上所述」「这一设计表明」「随着…的发展」「在…的背景下」「具有重要意义」。「研究表明」「多项研究证实」必须紧跟具体引用号 [N]，不能空喊。

---

### Step 4: 写参考文献

5-15 篇，格式 GB/T 7714-2015，按引用顺序编号。

**⛔ 必须使用 `$SCHOLAR_SCRIPT` 搜索文献，禁止凭记忆编造：**
```bash
PYTHON=""; for _c in "$MH_PYTHON" python python3; do [ -z "$_c" ] && continue; if $_c -c "import sys" >/dev/null 2>&1; then PYTHON="$_c"; break; fi; done; [ -z "$PYTHON" ] && PYTHON=python
$PYTHON "$SCHOLAR_SCRIPT" bibtex "项目相关技术关键词" --max 10
```
- 只引用搜索结果中返回的论文（有 title + authors + year + DOI）
- **检查 `match_label`**：`"good"` 直用、`"partial"` 核对标题、`"low"` 换关键词重搜或 WebSearch 兜底；`match_score < 0.3` 不要盲信
- 搜不到的不引用，宁少勿假
- 目标 8-12 篇，搜索结果不足就用搜到的数量

### Step 5: 完整自检 ⛔

```bash
echo "================================================="
echo "课程报告写作完成自检（7 项必查）"
echo "================================================="

# ============================
# 自检 1：字数
# ============================
echo ""
echo "=== 1. 总字数核对 ==="
TARGET=$(grep -E '^- word_count_target:' CLAUDE.md 2>/dev/null | sed -E 's/.*: *//' | head -1)
TARGET=${TARGET:-10000}
ACTUAL=$(python3 -c "import re; t=open('COURSE_REPORT.md','r',encoding='utf-8').read(); t=re.sub(r'\`\`\`.*?\`\`\`','',t,flags=re.DOTALL); t=re.sub(r'!\[[^\]]*\]\([^)]+\)','',t); t=re.sub(r'\[[\d,\-]+\]','',t); print(len(t))")
LOW=$((TARGET * 8 / 10))
HIGH=$((TARGET * 12 / 10))
echo "目标 $TARGET / 实际 $ACTUAL（容差 $LOW ~ $HIGH）"
[ "$ACTUAL" -lt "$LOW" ] && echo "❌ 偏少" || ([ "$ACTUAL" -gt "$HIGH" ] && echo "❌ 偏多" || echo "✅ OK")

# ============================
# 自检 2：第四章是否最长
# ============================
echo ""
echo "=== 2. 各章字数比例（第四章必须最长） ==="
python3 << 'PY'
import re
text = open('COURSE_REPORT.md', 'r', encoding='utf-8').read()
chs = re.split(r'(?m)^## ', text)
sizes = []
for i, ch in enumerate(chs[1:], 1):
    title = ch.split('\n', 1)[0][:30]
    body = re.sub(r'\`\`\`.*?\`\`\`', '', ch, flags=re.DOTALL)
    body = re.sub(r'!\[[^\]]*\]\([^)]+\)', '', body)
    body = re.sub(r'\[[\d,\-]+\]', '', body)
    sizes.append((i, title, len(body)))
    print(f'  §{i} [{title}] — {len(body)} 字符')
if sizes:
    max_idx, max_title, max_size = max(sizes, key=lambda x: x[2])
    # 找第四章（标题中含"实现"或"系统实现"）
    impl_chapters = [s for s in sizes if '实现' in s[1] or 'implementation' in s[1].lower()]
    if impl_chapters:
        impl = max(impl_chapters, key=lambda x: x[2])
        if impl[2] == max_size:
            print(f'✅ 系统实现章节（§{impl[0]}）是最长章节')
        else:
            print(f'❌ 系统实现（§{impl[0]} - {impl[2]}字）不是最长章节，最长是 §{max_idx}（{max_size}字）— 需要扩写实现章节')
PY

# ============================
# 自检 3：事实一致性（正文 ↔ PROJECT_FACTS）
# ============================
echo ""
echo "=== 3. 事实一致性检查 ==="
python3 << 'PY'
import re
facts = open('PROJECT_FACTS.md', 'r', encoding='utf-8').read()
report = open('COURSE_REPORT.md', 'r', encoding='utf-8').read()
no_code = bool(re.search(r'用户未上传项目源码|无源码', facts))

if no_code:
    # 无源码分支：正文不应有具体函数名/行号断言
    suspicious = []
    for m in re.finditer(r'([a-zA-Z_]\w*\.(py|js|ts|java|cpp|c|go|rs):\d+)', report):
        suspicious.append(m.group(1))
    if suspicious:
        print(f'❌ 无源码场景下正文出现具体文件:行号 {len(suspicious)} 处（疑似编造）:')
        for s in suspicious[:5]: print('  -', s)
    else:
        print('✅ 无源码场景下未出现伪造的具体代码定位')
else:
    # 有源码：正文中出现的模块名应能在 PROJECT_FACTS 中找到
    # 提取 PROJECT_FACTS 第 7 节「已实现功能清单」中的模块/函数标识
    m = re.search(r'(?m)^##\s*7\.[^\n]*功能清单\s*\n(.*?)(?=\n##|\Z)', facts, re.DOTALL)
    facts_keywords = set()
    if m:
        for line in m.group(1).split('\n'):
            for kw in re.findall(r'`([^`]+)`|([A-Z][a-zA-Z]+(?:Handler|Manager|Service|Controller|View|Model|Util))', line):
                kw = kw[0] or kw[1]
                if kw and len(kw) > 3:
                    facts_keywords.add(kw)
    # 正文中疑似函数名（CamelCase + Class 关键词）
    report_keywords = set()
    for kw in re.findall(r'\b([A-Z][a-zA-Z]+(?:Handler|Manager|Service|Controller|View|Model|Util))\b', report):
        report_keywords.add(kw)
    fabricated = report_keywords - facts_keywords
    # 简单统计警告（不强制失败，因为 PROJECT_FACTS 可能没穷举所有标识符）
    if fabricated:
        print(f'⚠ 正文出现 {len(fabricated)} 个 PROJECT_FACTS 中未列出的类标识（可能是编造，请人工核对）:')
        for k in list(fabricated)[:10]: print('  -', k)
    else:
        print('✅ 正文中类/服务标识与 PROJECT_FACTS 一致')
PY

# ============================
# 自检 4：图表闭环
# ============================
echo ""
echo "=== 4. 图表闭环检查 ==="
python3 << 'PY'
import os, re
text = open('COURSE_REPORT.md', 'r', encoding='utf-8').read()
embedded = set(m.group(1) for m in re.finditer(r'!\[[^\]]*\]\(([^)]+)\)', text))
fig_dir = 'figures'
existing = set()
if os.path.isdir(fig_dir):
    for f in os.listdir(fig_dir):
        if f.startswith('fig_') and f.endswith(('.png', '.pdf', '.jpg', '.jpeg')):
            existing.add(os.path.splitext(f)[0])
embedded_basenames = set()
for e in embedded:
    embedded_basenames.add(os.path.splitext(os.path.basename(e))[0])
missed_in_text = existing - embedded_basenames
missed_in_fs = embedded_basenames - existing
if missed_in_text:
    print(f'❌ figures/ 中 {len(missed_in_text)} 张图未被正文引用:')
    for m in sorted(missed_in_text): print('  -', m)
else:
    print(f'✅ figures/ 中所有 {len(existing)} 张图已被嵌入')
if missed_in_fs:
    print(f'❌ 正文引用了 {len(missed_in_fs)} 张不存在的图:')
    for m in sorted(missed_in_fs): print('  -', m)
else:
    print('✅ 正文嵌入的图都真实存在')
PY

# ============================
# 自检 5：Claims-Evidence 闭环
# ============================
echo ""
echo "=== 5. Claims-Evidence 闭环 ==="
python3 << 'PY'
import re
plan = open('OUTLINE.md', 'r', encoding='utf-8').read()
report = open('COURSE_REPORT.md', 'r', encoding='utf-8').read()
m = re.search(r'## Claims.Evidence Matrix\s*\n(.*?)(?=\n##|\Z)', plan, re.DOTALL | re.IGNORECASE)
if not m:
    print('⚠ OUTLINE.md 中未找到 Matrix，跳过')
else:
    rows = [ln for ln in m.group(1).split('\n') if '|' in ln and not re.match(r'\s*\|[\s\-:|]+\|\s*$', ln)]
    claims = []
    for r in rows[1:]:
        parts = [c.strip() for c in r.strip().strip('|').split('|')]
        if len(parts) >= 1 and parts[0] and parts[0] != 'Claim' and len(parts[0]) > 4:
            claims.append(parts[0])
    miss = []
    for c in claims:
        anchor = re.sub(r'[\W_]+', '', c)[:6]
        if anchor and anchor not in re.sub(r'[\W_]+', '', report):
            miss.append(c)
    if miss:
        print(f'❌ {len(miss)} 个 claim 未在正文体现:')
        for c in miss[:5]: print('  -', c[:80])
    else:
        print(f'✅ {len(claims)} 个 claim 都在正文中有体现')
PY

# ============================
# 自检 6：引用闭环
# ============================
echo ""
echo "=== 6. 引用闭环 ==="
python3 << 'PY'
import re
text = open('COURSE_REPORT.md', 'r', encoding='utf-8').read()
m = re.search(r'(?m)^##\s*参考文献\s*\n(.*?)(?=\n##|\Z)', text, re.DOTALL)
ref_section = m.group(1) if m else ''
ref_nums = set(int(n) for n in re.findall(r'^\[(\d+)\]', ref_section, re.MULTILINE))
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
print(f'  引用号 {len(cite_nums)} / 参考文献 {len(ref_nums)}')
if dangling: print(f'❌ 悬空引用: {sorted(dangling)}')
else: print('✅ 引用号都有对应文献')
if unused: print(f'⚠ 未使用文献: {sorted(unused)}')
ref_count = len(ref_nums)
if 5 <= ref_count <= 15: print(f'✅ 参考文献数量 {ref_count} 在 [5-15]')
else: print(f'⚠ 参考文献数量 {ref_count} 不在 [5-15] 范围')
PY

# ============================
# 自检 7：代码片段长度
# ============================
echo ""
echo "=== 7. 代码片段长度检查 ==="
python3 << 'PY'
import re
text = open('COURSE_REPORT.md', 'r', encoding='utf-8').read()
blocks = re.findall(r'```[a-z]*\n(.*?)\n```', text, re.DOTALL)
oversized = [b for b in blocks if len(b.split('\n')) > 20]
if oversized:
    print(f'⚠ {len(oversized)}/{len(blocks)} 个代码块超过 20 行（建议精简或放附录）')
    for b in oversized[:3]:
        first = b.split('\n', 1)[0][:60]
        print(f'  - {len(b.split(chr(10)))} 行 | 首行: {first}')
else:
    print(f'✅ 共 {len(blocks)} 个代码块，全部 ≤20 行')
PY

echo ""
echo "================================================="
echo "课程报告自检完成。"
echo "================================================="
```

## 输出文件

- `COURSE_REPORT.md` — 最终课程报告（**主产出**，含图片嵌入）

## 关键规则

1. **基于已存在的 OUTLINE.md / PROJECT_FACTS.md / figures/，不许重新规划。**
2. **每张已生成的图必须在正文嵌入。** PNG 优先；只有 PDF 用 PDF。
3. **系统实现章节最长。**
4. **代码片段不超过 20 行。**
5. **不许编造功能或模块。** 无源码时全用推测语气。
6. **7 项自检全部通过才算完成。**
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
        if ! ls figures/${name}.png figures/${name}.pdf figures/${name}.drawio 2>/dev/null | head -1 | grep -q .; then
            echo "❌ MANIFEST: $name 文件不存在"
            manifest_missing=$((manifest_missing + 1))
        elif ! grep -qE "${name}\.(png|pdf)" COURSE_REPORT.md 2>/dev/null; then
            echo "❌ MANIFEST: $name 文件存在但 COURSE_REPORT.md 未引用"
            manifest_missing=$((manifest_missing + 1))
        fi
    done
    if [ "$manifest_missing" -gt 0 ]; then
        echo "⛔ FIGURE_MANIFEST 对账失败 ($manifest_missing 张): 必须把这些图都画出来 + 嵌入正文后再结束"
    else
        echo "✅ FIGURE_MANIFEST 全部嵌入"
    fi
else
    echo "(规划文档无 FIGURE_MANIFEST, 跳过对账)"
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

