---
name: docx-format-check
description: "导出 Word 前的 Markdown 格式自检与修复。检查代码块、公式编号、表格、图片、Markdown 残留等会影响 docx 渲染的格式问题，必要时直接修复。Use when user says \"docx 自检\", \"word 格式检查\", \"docx-format-check\"."
argument-hint: [target-markdown-file]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# DOCX 格式自检（Markdown → Word 友好性）

在 docx-export 之前对 Markdown 做最后一道格式自检，专注于**会让生成的 .docx 走样的格式问题**，并在能直接修复时立即修复（无需用户确认）。

> 与 docx-precheck（图片闭环 / LaTeX 残留 / 引用闭环 / 字数）不重复。本步骤只关心：
> - 代码块是否会被 docx 渲染为「全部挤成一行」
> - 公式块是否会被识别为编号公式
> - Markdown 表格是否会渲染为三线表
> - 图片是否会被嵌入（PDF 引用 / SVG 引用 / 缺 PNG）
> - Markdown 噪声（粗体过多、内联代码用错、转义字符残留）

## 输入

- **TARGET_FILE** — 默认从 `$ARGUMENTS` 或按下面优先级自动检测：
  - `PROPOSAL.md` / `LITERATURE_REVIEW.md` / `COURSE_PAPER.md` / `COURSE_REPORT.md` / `NARRATIVE_REPORT.md` / `paper/main.md` / `REPORT.md`

## 输出

- **`DOCX_FORMAT_CHECK_REPORT.md`** — 检查与修复报告
- 直接修改的 Markdown（如有自动修复）

## ⛔⛔⛔ 完成铁律（最高优先级）

**本步骤必须产出 `DOCX_FORMAT_CHECK_REPORT.md`（≥ 200 字节，包含自检结果汇总）**。

即使**没有发现任何问题**也要写报告（写"全部检查通过"即可）。

⛔ **结束前必跑产出验证**：
```bash
[ -f DOCX_FORMAT_CHECK_REPORT.md ] && SZ=$(wc -c < DOCX_FORMAT_CHECK_REPORT.md) || SZ=0
[ "$SZ" -ge 200 ] && echo "✅ DOCX_FORMAT_CHECK_REPORT.md ($SZ)" \
    || echo "❌ DOCX_FORMAT_CHECK_REPORT.md 缺失 — 必须写一份报告（即使无问题也要写"全部通过"）"
```

## 工作流程

### Step 0：读取上游 precheck 报告 + 格式对照表

**Step 0a — 上游 precheck 报告**（机械化检查的结果）

`docx-precheck` 步骤已经把规则化检查的结果写到 `DOCX_PRECHECK_REPORT.md`。优先按里面的 fatal/critical 警告条目修源 md，再做后续 Step 2-6 的自检。

```bash
if [ -f DOCX_PRECHECK_REPORT.md ]; then
    echo "=== 上游 precheck 报告（fatal/critical 段） ==="
    awk '/^## (Fatal|致命|Critical)/,/^## /' DOCX_PRECHECK_REPORT.md | head -80
fi
```

读完后逐条用 Edit 修源 md，最后在本步骤的报告里记录"已根据 precheck 修复 N 项"。

**Step 0b — 格式对照表**（参考，不是硬约束）

引擎层会在工作区写一份 `_format_reference.md`，里面有：
- 本工作流的字号/字体/页边距/行距规范（来自对应 docx_style_profile，**会被引擎自动应用**，你不需要在 md 里调字号）
- 推荐的章节骨架（按工作流类型定制：竞赛/课程论文/课程报告/开题/综述都不同）
- 题注/公式编号/表格/图片/参考文献的范式
- 自检清单

⛔ **本对照表的定位**：
- **硬性规则**（必须遵守）：用 `#` 标记标题不要用 `- `、题注独占行、公式编号同行、表格分隔行齐全、不要 LaTeX 残留 — 这些是 docx 引擎能否正确渲染的前提
- **软性参考**（可自由发挥）：具体的章节叫什么、章节深度、章节顺序、字数分配、用几张图几张表 — **完全由作者根据论文实际内容决定**，不要为了凑骨架而强行填空章节

也就是说，对照表里"推荐的章节骨架"只是**结构示例**，不是"必须照搬"。如果论文实际只需要 3 个章节，就不要硬塞 5 个；如果需要 7 个章节，就大胆写。**字号字体不需要在 md 里设置**，引擎按 profile 自动应用。

```bash
if [ -f _format_reference.md ]; then
    echo "=== 格式对照表（_format_reference.md）核心规范摘要 ==="
    head -20 _format_reference.md
    echo "（完整对照表用 Read 工具读取，重点关注引擎特殊路径：摘要/关键词/题注/公式编号）"
else
    echo "⚠ _format_reference.md 不存在（引擎层生成失败），按本 SKILL.md 默认规则检查"
fi
```

### Step 1：定位目标文件

```bash
TARGET_FILE=""
for cand in PROPOSAL.md LITERATURE_REVIEW.md COURSE_PAPER.md COURSE_REPORT.md NARRATIVE_REPORT.md paper/main.md REPORT.md; do
    if [ -f "$cand" ]; then TARGET_FILE="$cand"; break; fi
done
[ -z "$TARGET_FILE" ] && { echo "❌ 找不到目标 Markdown"; exit 1; }
echo "Target: $TARGET_FILE"
```

### Step 2：代码块自检（最常见 docx 走样问题）

读完整文件，用 Read 工具，按以下规则逐项检查：

**Check A0 — 章节标题 / 图注 / 公式编号被误写成 list（最高优先级）**

LLM 有时会把章节标题、图注、独行公式编号写成 `- xxx` 列表项，docx 引擎会按 list 渲染加上 "•"，让标题前面显示 "• 一、问题重述"、"• 4.1.1 子模型"、"• 图 4-1：xxx"、"• (1)"。

```bash
# 找疑似伪标题（行首 - 后接中文章节序号 / 数字小节号 / 摘要/关键词/参考文献）
grep -nE '^- (第[一二三四五六七八九十百千零〇0-9]+[章节部篇]|[一二三四五六七八九十]+、|（[一二三四五六七八九十]+）|[0-9]+(\.[0-9]+){0,4}\.?\s|摘要|Abstract|关键词|Keywords|参考文献|References|致谢|附录|Appendix)' "$TARGET_FILE" || true

# 找疑似伪图注：行首 - 后接「图 X：」「表 X：」「Figure X」「Table X」
grep -nE '^- (图|表|Figure|Fig\.?|Table|Tab\.?)\s*[0-9A-Za-z][0-9A-Za-z\-\.]*\s*[：:、\.\-]' "$TARGET_FILE" || true
grep -nE '^- (图|表)\s*[：:]' "$TARGET_FILE" || true

# 找疑似独行公式编号（- (1) / - [1] / - 【1】）
grep -nE '^- *[\[\(【] *[0-9]+(\.[0-9]+)? *[\]\)】] *$' "$TARGET_FILE" || true
```

**修复**（用 Edit 工具）：
- `- 一、问题重述` / `- 第三章 模型构建` → `# 一、问题重述` / `# 第三章 模型构建`
- `- 1.1 问题背景` → `## 1.1 问题背景`（按数字段数定级别：1 段 → H1，2 段 → H2，3 段 → H3，4 段 → H4）
- `- 摘要` / `- 关键词：xxx` / `- 参考文献` / `- 附录` → `## 摘要` / `## 关键词：xxx` / `## 参考文献` / `## 附录`
- `- 图 4-1：方法对比` → `图 4-1：方法对比`（去 bullet，保留正文，单独一行紧跟在图片下面）
- `- (1)` / `- [1]` 紧跟在公式块后 → 合并到上一条公式末尾，统一成 ` (n)` 形式：`$$ y = ax $$ (1)`

**Check A — 代码块缺失栏栅**
- 单行代码（` `单反引号` `）数量是否过多（>20 处可能误用）
- 长代码段是否漏了 ```` ``` ```` 包围（特征：连续 ≥ 3 行相似缩进的代码却没在 fenced block 里）

**Check B — 代码块语法不规范**
- ```` ``` ```` 闭合不平衡（开块数 ≠ 闭块数）
- 嵌套代码块（` ``` ` 在另一个 ` ``` ` 里）— docx 渲染会断裂

```bash
# 统计 ``` 出现次数（应为偶数）
COUNT=$(grep -c '^```' "$TARGET_FILE")
[ $((COUNT % 2)) -ne 0 ] && echo "❌ 代码块标记不平衡（共 $COUNT 个 \`\`\`）"
```

**Check C — 代码缩进破坏**
- 检测是否有「附录代码全部塞进一段」的特征：单段内 ≥ 200 字符且含 `def `/`class `/`import `/`return ` 等关键字 → 该段实际应是代码块

**修复策略**：
- 若发现 Check C 命中，定位段落，用 Edit 工具把它替换为 ```` ```python ... ``` ```` 包裹（保留原内容）
- 若 Check B 命中（标记不平衡），定位最后一个孤立的 ```` ``` ````，根据上下文决定是补开块还是补闭块

### Step 3：公式块自检

**Check D — 公式编号语法**

docx-cn-engine 支持两种公式编号写法：
1. `$$ ... $$ (1)` — 块外编号
2. `$$ ... \tag{1} $$` — 块内 \tag

非这两种写法的「公式 + 编号」会让编号被当成正文：
- ❌ `$$...$$**（1）**` （加粗中文括号）
- ❌ `公式（1）：$$...$$` （编号在公式前）
- ❌ `$$ y = x $$ \quad (1)` （quad 间距残留）

```bash
# 找形如 $$...$$（中文括号编号）的可疑写法
grep -nE '\$\$.*\$\$\s*[（(][0-9]+[)）]' "$TARGET_FILE" || true
# 找公式后的中文括号编号（要修成英文括号）
grep -nE '\$\$\s*（[0-9]+）' "$TARGET_FILE" || true
```

**修复**：把所有 `（n）` 替换为 ` (n)`，并确保紧跟在结束 `$$` 后只有一个空格。

**Check D2 — 块公式必须有编号（论文规范）**

所有块公式 `$$...$$` 必须按出现顺序连续编号 `(1)(2)(3)...`，否则正文中无法引用「由式 (3) 可得」。

用以下脚本扫描所有未编号的块公式：

```bash
python3 - <<'PY'
import re
content = open("$TARGET_FILE", encoding="utf-8").read()
# 过滤代码块（避免误报）
content_no_code = re.sub(r'```.*?```', '', content, flags=re.DOTALL)

no_label = []
seen = []
# 多行块公式
for m in re.finditer(r'^[ \t]*\$\$[ \t]*$([\s\S]*?)^[ \t]*\$\$([^\n]*)$',
                     content_no_code, re.MULTILINE):
    body, tail = m.group(1), m.group(2).strip()
    inline_tag = re.search(r'\\tag\{([^}]+)\}', body)
    trail_label = re.match(r'\(\d+(?:\.\d+)?\)', tail)
    if inline_tag:
        seen.append(inline_tag.group(1))
    elif trail_label:
        seen.append(trail_label.group(0).strip("()"))
    else:
        line = content_no_code[:m.start()].count('\n') + 1
        no_label.append((line, body.strip()[:60]))

# 单行块公式
for m in re.finditer(r'^[ \t]*\$\$([^\n$]+)\$\$([^\n]*)$',
                     content_no_code, re.MULTILINE):
    body, tail = m.group(1), m.group(2).strip()
    trail_label = re.match(r'\(\d+(?:\.\d+)?\)', tail)
    if trail_label:
        seen.append(trail_label.group(0).strip("()"))
    else:
        line = content_no_code[:m.start()].count('\n') + 1
        no_label.append((line, body.strip()[:60]))

print(f"已编号公式 ({len(seen)}): {seen}")
print(f"未编号公式 ({len(no_label)}):")
for line, sn in no_label[:15]:
    print(f"  L{line}: {sn}...")
PY
```

**修复策略**：
- 对每个未编号公式用 Edit 工具补编号：单行末尾追加 ` (n)`、多行结尾的 `$$` 后追加 ` (n)`
- 编号取**未用过的下一个连续整数**（与已编号公式延续）
- 编号必须**全文唯一连续**，不能重复也不能跳号
- 章节多时也可用章节-序号 `(1.1) (1.2) (2.1)`，但风格全文一致

**Check E — 块公式格式**
- 块公式 `$$` 必须独立成行（Markdown 渲染要求）
- 不能在行内用 `$$...$$`（应该用 `$...$`）

```bash
# 找行内 $$...$$（同一行内有两次 $$）
grep -nE '\$\$.+\$\$' "$TARGET_FILE" | grep -v '^\s*\$\$' || true
```

**修复**：把行内的 `$$X$$` 改成 `$X$`（行内公式）。

**Check E2 — 裸 LaTeX 块公式（缺 `$$` 包围）**

⛔ **最常见的渲染失败原因**：AI 写公式时直接写 `v_k = b\sqrt{1+\theta_k^2}.\tag{12}` 而忘了用 `$$...$$` 包围，渲染器把整行当纯文本显示出 `\sqrt`、`\tag` 等 LaTeX 命令字面字符。

```bash
# 扫描裸 LaTeX 命令（反斜杠开头）但当前行不在 $$ 块或 $...$ 行内公式内
python3 - <<'PY'
import re, sys
text = open("$TARGET_FILE", encoding="utf-8").read()
# 移除已正确包围的代码块、$$ 块、$ 行内
cleaned = re.sub(r'```[\s\S]*?```', '', text)
cleaned = re.sub(r'`[^`\n]+`', '', cleaned)
cleaned = re.sub(r'\$\$[\s\S]*?\$\$', '', cleaned)
cleaned = re.sub(r'\$[^\n$]+\$', '', cleaned)
# 找裸 LaTeX 命令
pattern = r'\\(tag|sqrt|hat|frac|tfrac|dot|ddot|begin\{(?:aligned|cases|bmatrix|pmatrix|equation)|cdot|pm|mp|in|exists|forall|big|cap|cup|vec|widehat|widetilde|left|right|sum|prod|int|partial|nabla|infty|leq|geq|neq|approx)\b'
bad = []
for i, line in enumerate(cleaned.split('\n'), 1):
    if re.search(pattern, line):
        bad.append((i, line.strip()[:90]))
if bad:
    print(f"❌ 发现 {len(bad)} 处裸 LaTeX（缺 $$ 包围）：")
    for ln, s in bad[:15]:
        print(f"  L{ln}: {s}")
    sys.exit(1)
else:
    print("✓ 公式包围检查通过")
PY
```

**修复**：用 Edit 工具把每条违规行包进 `$$...$$` 块（前后空行）：
- 原：`v_k = |\dot P_k| = b\sqrt{1+\theta_k^2}|\dot\theta_k|. \tag{12}`
- 改：

  ```
  
  $$
  v_k = |\dot P_k| = b\sqrt{1+\theta_k^2}|\dot\theta_k|. \tag{12}
  $$
  
  ```

### Step 4：表格自检

**Check F — 三线表必备**

```bash
# 找 Markdown 表格起始行
grep -n '^\s*|.*|.*|' "$TARGET_FILE" | head -20
```

逐表检查：
- 第一行是表头
- 第二行必须是 `|---|---|...` 分隔行
- 列数是否一致（cell 用 `|` 计数）

**修复**：
- 缺分隔行 → 在表头下加 `|---|...|---|`（按列数）
- 列数不齐 → 补空 cell

**Check G — 表格内含特殊字符**
- cell 内 `|` 必须转义为 `\|`
- cell 内不能有未配对的 `$`

### Step 5：图片自检（与 docx-precheck 互补）

**Check H — Markdown 引用语法**

```bash
# 找所有 ![]()
grep -oE '!\[[^]]*\]\([^)]+\)' "$TARGET_FILE" | sort -u
```

逐张检查：
- 引用路径是否存在（如果不存在但同名 .pdf 在，提示用户 docx-precheck 会自动转 PNG）
- 引用是否用了 `<img>` HTML 标签 — docx-cn-engine 不支持，应改成 Markdown 语法
- 图片说明（alt text）是否带「图 X：」前缀 — docx-export 会把 alt 当图题

**修复**：
- 把 `<img src="..." />` 全改成 `![](path)`
- 如果有 alt 但不含「图 X」编号，按章节顺序补上「图 X：」前缀（保守：只在 alt 完全为空时补，已有 alt 不动）

**Check H2 — 图号起句去套路化（⛔ Word 导出最刺眼的 AI 痕迹，独立兜底不靠写作步骤自检）**

> 背景：写作步骤已要求图号引用句式轮换，但那是同一个 AI 写完自检、容易放过；PDF 链路由 comp-compile 的 `writing_check.sh` 独立兜底，Word 链路此前缺这道。本 Check 就是 Word 的独立门控——**不管上游写没写好，导出前这里再扫一遍、当场改**。

扫正文里"图 N…/表 N…"起句的分析段（`如图/由图/从图/见图/观察图` 这类把图号沉在句中的带出式不算）：
```bash
python - "$TARGET_FILE" <<'PYEOF'
import re, sys
text = open(sys.argv[1], encoding='utf-8', errors='ignore').read().replace('\r\n', '\n')
m = re.search(r'\n##\s*(附录|参考文献|Appendix|References)', text)
body = text[:m.start()] if m else text
# 中文"图/表 N…"起句，或英文"Figure/Fig./Table/Tab. N…"起句
open_re = re.compile(r'^(图|表)\s*\d|^(Figure|Fig\.?|Table|Tab\.?)\s*\d', re.IGNORECASE)
# 英文带出式（把图号沉在句中，不算起句违规）：As shown in.../Observing.../From.../In...
leadin_re = re.compile(r'^(as\s|in\s|from\s|observing\b|see\b|per\b|following\b|according)', re.IGNORECASE)
def is_prose(p):
    s = p.strip()
    if len(s) < 15 or s[0] in '#>|`!*-\\%{}$&': return False
    if re.match(r'^\d+\.', s): return False
    return True
def is_opener(p):
    s = p.strip()
    return bool(open_re.match(s)) and not bool(leadin_re.match(s))
sections = re.split(r'(?m)^##\s', body)
adj, heavy = 0, []
tot_open, tot_ref = 0, 0
for sec in sections:
    proses = [p for p in re.split(r'\n\s*\n', sec) if is_prose(p)]
    flags = [is_opener(p) for p in proses]
    adj += sum(1 for i in range(len(flags)-1) if flags[i] and flags[i+1])
    if sum(flags) >= 3: heavy.append(sum(flags))
    tot_open += sum(flags)
    # 引用了图/表的散文段（图号出现在段里任意位置）——作分母
    tot_ref += sum(1 for p in proses if re.search(r'(图|表)\s*\d|(Figure|Fig\.?|Table|Tab\.?)\s*\d', p, re.I))
# 全文普遍性：图号起句段占"所有引用图表的段"比例过高 = 通篇一个套路（拦"隔开但普遍"）
ratio = (tot_open / tot_ref) if tot_ref else 0
pervasive = tot_ref >= 5 and ratio > 0.35
if adj or heavy or pervasive:
    if adj:   print(f"  X {adj} 处相邻段落都以「图 N…/表 N…」起句 — 最刺眼的套路")
    if heavy: print(f"  X {len(heavy)} 个章节图号起句段 >=3（{heavy}）— 每张图都'图N开头'太单调")
    if pervasive: print(f"  X 全文 {tot_open}/{tot_ref} 段以「图N/表N」起句（{ratio:.0%}>35%）— 通篇一个套路，即便彼此隔开也太单调")
    print("  修复：把点名的段落改成 括号旁注（『……（图 3）』）／动词引导（『观察图 4 中……』）／后置印证（『……在图 5 得到印证』），「图作主语」整节最多一次")
    sys.exit(3)
print("  ✅ 图号引用句式无套路化")
PYEOF
```

**修复（⛔ 检测→修复→再检测闭环，本步骤有 Edit 能力，当场改）**：若 `exit 3`，用 Read 读 `$TARGET_FILE`，把被点名的"图 N…/表 N…"开头段改写成括号旁注／动词引导／后置印证等切入方式（图作主语整节最多一次），改完**重跑本检测直到输出 ✅**。这是 Word 导出前图号套路化的最后一道拦截，不通过不结束。

**Check H3 — 两张图连排检测（⛔ Word 排版不如 PDF 顺畅的主因，独立兜底）**

> 背景：写作步骤有"严禁两图直接相邻"的规则和自检，但同 H2 一样靠写作 AI 自觉；PDF 由 `writing_check.sh` + comp-compile 的 figure-stacking 双重独立兜底，Word 此前只有写作自检。两张图中间没有充分正文，docx 渲染出来就是"图叠图"、断裂感强。本 Check 是 Word 的独立拦截。

扫相邻两张图之间的实际正文字数（与写作步骤 5.4 同口径）：
```bash
python - "$TARGET_FILE" <<'PYEOF'
import re, sys
t = open(sys.argv[1], encoding='utf-8', errors='ignore').read()
# 只查正文（附录/参考文献前）；附录里代码图连排不算
m = re.search(r'\n##\s*(附录|参考文献|Appendix|References)', t)
body = t[:m.start()] if m else t
imgs = list(re.finditer(r'!\[[^\]]*\]\([^)]*\)', body))
bad = []
for i in range(len(imgs) - 1):
    gap = body[imgs[i].end():imgs[i+1].start()]
    # 去掉标题行后再数正文（两图分处不同小节、中间只有标题也算连排，需补过渡）
    prose = re.sub(r'(?m)^#{1,6}\s.*$', '', gap)
    prose = re.sub(r'\s+', '', prose)
    if len(prose) < 80:
        # 打印前一张图的 alt 前 20 字便于定位
        alt = re.match(r'!\[([^\]]*)\]', imgs[i].group(0))
        tag = (alt.group(1)[:20] if alt else '?')
        bad.append(tag)
if bad:
    print(f"  X {len(bad)} 处两图之间正文不足 80 字（图叠图/一句话带过）：{bad}")
    print("  修复：在这两张图之间补一段充分正文——上一张图的解读（具体数值+趋势/对比+推论），并自然引出下一张图；不许两图直接贴一起或只用一句话过渡")
    sys.exit(3)
print("  ✅ 无两图连排")
PYEOF
```

**修复（⛔ 检测→修复→再检测闭环）**：若 `exit 3`，用 Read 读 `$TARGET_FILE`，在被点名的两图之间补足过渡正文（把上一张图讲透 + 引出下一张），改完**重跑直到输出 ✅**。这道拦截让 Word 的图文节奏和 PDF 一样顺，不再图叠图。

### Step 6：Markdown 噪声自检

**Check I — 转义字符残留**

```bash
# 找连续反斜杠（pandoc 转换可能留下）
# 注: (?!...) 是 PCRE 语法, 必须用 grep -P (git bash 内置 grep 支持; 否则用 grep -E 退化为简单匹配)
grep -nP '\\\\(?!\$|\(|\)|\[|\])' "$TARGET_FILE" 2>/dev/null | head -10 \
  || grep -nE '\\\\[^$()[\]]' "$TARGET_FILE" 2>/dev/null | head -10
```

**Check J — HTML 残留**

```bash
# 找 HTML 标签（除了 <br> <sub> <sup> 这些 docx-cn-engine 支持的）
grep -nE '<(div|span|p|h[1-6]|table|tr|td|thead|tbody)[^>]*>' "$TARGET_FILE" | head -10
```

**Check J2 — 数学符号 `<` `>` 未包进 `$...$`**

⛔ Claude 写公式时容易出现 `$R_2$<R_1$` 或 `$a<b$`（先关 `$` 再写 `<` 又开 `$`）, docx 里 `<R_1` 会被当成字面字符。

```bash
# 找数学符号 < / > 紧贴非空白字符的可疑模式（排除 HTML 标签和 ![](url) 链接）
grep -nE '\$[^$]+\$\s*[<>]\s*[A-Za-z_]|[A-Za-z0-9_]\s*[<>]\s*\$' "$TARGET_FILE" | head -10
# 也找单独 < > 后跟字母（疑似漏写 $ 包裹）
grep -nE '(?<!`|/|=|"|>)\s<\s*[A-Za-z_][A-Za-z0-9_]*\s*[<>=]' "$TARGET_FILE" | head -10 2>/dev/null || true
```

**修复策略**：把 `$a$<b$` / `$a<b$` 这种合并成单一公式 `$a < b$`（注意符号两边加空格让 LaTeX 渲染正确）。

**Check K — 加粗滥用**

```bash
# 加粗段落（整段都是 ** ... **）
grep -cE '^\*\*[^*]+\*\*$' "$TARGET_FILE"
```

**修复**：HTML 表格转 Markdown；`\` 双反斜杠还原成单反斜杠（除 LaTeX 公式中的换行）；游离 `<` `>` 数学符号包进单一 `$...$`。

### Step 7：生成报告

写入 `DOCX_FORMAT_CHECK_REPORT.md`：

```markdown
# DOCX 格式自检报告

**目标文件**：`<TARGET_FILE>`
**自检时间**：$(date '+%Y-%m-%d %H:%M:%S')

## 检查结果汇总

| 类别 | 状态 | 修复次数 |
|------|------|----------|
| 代码块完整性（A/B/C） | ✅/⚠️ | N |
| 公式编号语法（D/E） | ✅/⚠️ | N |
| 三线表格式（F/G） | ✅/⚠️ | N |
| 图片引用（H） | ✅/⚠️ | N |
| Markdown 噪声（I/J/K） | ✅/⚠️ | N |

## 自动修复的问题

- [行号 X] 把附录代码段包入 ```python ... ``` 代码块
- [行号 Y] `（1）` → ` (1)`（公式编号）
- [行号 Z] 表格补充分隔行 `|---|---|`

## 仍需人工处理的问题

（如有无法自动判断的情形，列在这里）

## 结论

- ✅ 通过：可以安全进入 docx-export
- ⚠️ 修复后通过：已自动修复 N 处，仍可继续
- ❌ 需人工修复：存在 M 处需手工干预的问题（列在上节）
```

### Step 8：阻塞判定

- 如果 Step 7 中「仍需人工处理」非空且影响 docx 可读性 → 写入报告但不退出（`exit 0`），让 docx-export 继续，避免误伤
- 如果代码块标记不平衡（无法决定补哪头）→ 报告中标红，但 `exit 0`（让用户在最终 docx 里看到明显异常再回头修）
- **本步骤不强制阻塞工作流**，docx-export 永远会跑

## 注意事项

1. **修复要保守**：拿不准时只在报告里记录，不要乱改。错改用户内容比漏改危险得多。
2. **不要改公式语义**：除了把 `（）` 替换为 ` ()`、把 `$$X$$` 改 `$X$`，公式本体一律不动。
3. **代码块语言标记**：包裹时尽量给 `python`/`bash`/`text`，但只在能 100% 推断时用，否则用裸 ```` ``` ````。
4. **不要重复 docx-precheck 的检查**：图片闭环、字数、引用闭环、LaTeX 残留 都已经被 docx-precheck 覆盖。
