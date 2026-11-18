---
name: citation-crosscheck
description: "双盲 .bib 字段级交叉核对：盲提取、独立重查、机械 diff，裁决 MATCH/MINOR/MISMATCH。触发词：引用交叉核对、bib audit。"
argument-hint: "[paper-directory-or-bib-file] [--xlsx <path>] [--cited-only|--all]"
allowed-tools: Read, Grep, Glob, Write, Bash(*), WebSearch, WebFetch, Agent
---

# Citation Cross-Check（双盲 .bib 字段级交叉核对）

> 🔒 **本技能是 verdict-bearing 的证据工具，不要包进 `/loop`、`/schedule`、Cron 等定时循环。**
> 它对每条参考文献产出裁决，该裁决只在**参考文献本身变化**时才有新信息——定时重跑不增加任何
> 信号。要排程的是它之前的等待：参考文献定稿 → 跑一次。

## 与在库引用技能的路由分工（先读这段）

本仓库 citation 家族七件各管一段，本技能**只**做「字段级双盲对抗 diff」：

| 技能 | 管什么 | 不管什么 |
|---|---|---|
| `lit-citation-verify` | 核验**原则**与 canonical 源顺序（guidance） | 不做批量检查 |
| `lit-citation-manage` | 引用**管理**：检索、元数据提取、BibTeX 生成、Zotero/Obsidian 流 | 不做裁决性审计 |
| `check-citations` | `.bib` **三源存在性批查**（CrossRef/Semantic Scholar/OpenAlex），抓幻觉/嵌合引用 | 不做字段级 diff，不核作者顺序/venue |
| `citation-check` | 中文国赛 **GB/T 7714 格式与完整性**终检 | 不联网核真伪 |
| `lit-citation-verify-latex` | LaTeX `.tex`+`.bib` **批量存在性**核验（bibsleuth） | 不做字段级对抗 diff |
| `paper-citation-verify` | 投稿前**操作性清单**（placeholder 清理、BibTeX 卫生、DOI/PMID 完整性） | 不联网逐条裁决 |
| **`citation-crosscheck`（本技能）** | **双盲字段级对抗 diff**：A 盲提取 vs B 独立重查 vs 机械门，裁 MATCH/MINOR/MISMATCH/NEEDS_WEBCHECK，出对照 xlsx | 不做 context-fit（引用是否支撑论点）；不替代三源存在性批查 |

**升级路径**：`.bib` 先过 `check-citations` 分诊（快、免费、三源存在性）；报 `not_found`/
`suspicious`、进入投稿终检、或用户点名 crosscheck 时，再用本技能做字段级双盲核对；
`MISMATCH` 修复回写 `.bib` 后可再跑 `check-citations` 回归。建议投稿前与存在性批查**并用**
（本技能补字段准确性，`check-citations` 补存在性/幻觉），不互替。

## 为什么需要双盲（原理）

手录 `.bib` 条目最危险的错误，恰恰是「读起来通顺」的那类：**作者被掉序或漏人**、**年份错一位**、
**venue 张冠李戴**、**DOI 挂错**。单审者看到 `.bib` 原文会被锚定，倾向判「看起来对」；两个互不知情的
提取者无法共享锚点——只有当**两份独立重建的记录彼此一致**时才判通过，分歧处会被机械门逐字段报出。

它抓的是「存在但字段错」；「是否存在/是否幻觉」由 `check-citations` 的三源批查负责；
「是否支撑论点」（context-fit）不在本技能范围——那是写作审稿类技能的职责。

## 依赖与降级路径（如实声明，不假装必达）

- **检索数据源**：arXiv（`/abs/<id>`、`/bibtex/<id>`）、DBLP、CrossRef、ACL Anthology、
  NeurIPS/PMLR、OpenReview，全部公开免费；B 代理用当前宿主实际可用的联网检索/抓取工具
  （WebSearch/WebFetch 语义名，本仓执行侧已有以 web 工具替代上游 API 依赖的先例）。
- **外部 API 不可用/被限流时**：B 必须在 `sources_tried` 里如实记录哪个源失败（如
  `"semantic-scholar(429)"`），并继续尝试通用 web 搜索兜底；C 据此打 `degraded_search` 旗标；
  门对该条只升不降（ESCALATE），主 agent 在 Step 4 亲自动手补查。**降级搜索的 `found:false`
  不等于「查无此文献」**——绝不在降级状态下判 MISMATCH（伪造）。
- **openpyxl 缺失时**：Step 5 改输出**同列结构 CSV**（`citation_crosscheck_<date>.csv`），
  审计不因缺包中断；在报告里注明降级。
- **无 Agent/委派能力的宿主（Tier-3）**：A→B→C 顺序执行；B 无法获得隔离上下文时**必须如实**
  `blind:false`，门会把所有 MATCH/MINOR 降为 ESCALATE（只旗标、不认证）。见下文「条件双盲」。
- **确定性门 `scripts/cx_verify.py`**：纯标准库（argparse/hashlib/json/re/sys/unicodedata），
  零三方依赖、零网络、零本机路径；Windows 用 `python` 运行。

## 常量

- **BLIND = conditional（条件双盲）**——双盲只在宿主能为 B 提供**未继承 `.bib` 视图的隔离上下文**
  时成立。B 只允许拿到「题名 + 第一作者 + 不透明 `dedup_key`」，禁止读 `.bib` 或任何仓库文件；
  B 是否真能作证 `blind:true`，取决于宿主隔离能力，而不取决于提示词写得多严（见 Step 2）。
- **SOURCES** = arXiv、DBLP、CrossRef、ACL Anthology、NeurIPS/PMLR、OpenReview + 通用 web 搜索
  兜底。报告抓取页面实际显示的内容；**任何字段都不许编造**。
- **VERDICTS**（由**主 agent** 在 Step 4 裁定，永不由分片裁定）：
  - `MATCH`——书目等价，仅化妆差异；
  - `MINOR`——格式差异或 preprint-vs-published venue，无需改正；
  - `MISMATCH`——真实不一致：作者错/漏/换序、年份错、venue 错、id 错；
  - `NEEDS_WEBCHECK`——B 未能确认存在，但该条是带 `url` 的 `@misc`/博客/技术报告，B 的
    索引式检索结构性看不见它；主 agent 必须在 Step 4 亲 fetch 该 `url` 后再裁，**禁止**
    把这类条目直接降为 MISMATCH。
- **SCOPE** = 默认仅被引条目（在 `.bbl` 里渲染的）；`--all` 连同未被引的 `.bib` 条目一起审。
- **OUTPUT** = `<paper-dir>/citation_crosscheck_<date>.xlsx`（openpyxl 缺失时同列 CSV）+
  四份中间产物（`cx_A_ourbib`、`cx_B_web`、`cx_C_fielddiff`、门的 `cx_gate.json`）留审计。
  中间产物统一放**项目内 `.engine/tmp/`**（已 gitignore）或系统临时目录，用 `CX_TMP` 变量控制。

## Workflow

以下命令块以 `bash` 为准；`CX_TMP` 建议设为项目内 `.engine/tmp`（相对路径，Windows/Git Bash
与 POSIX 均可）。中间文件按 `dedup_key` 串联，任何一步对不上都要 fail-closed 停下。

```bash
CX_TMP="${CX_TMP:-.engine/tmp}"
mkdir -p "$CX_TMP"
```

### Step 1 — 解析引用集（确定性，主 agent 亲自做）

```bash
# 只搜论文自己的源码树，不搜整个仓库：随包的 author-kit/模板 .tex 带演示 \cite{...}，
# 会虚增引用集。PAPER_DIR 设为主 .tex（\documentclass + \bibliography）所在目录；
# 递归（引用常在 sections/*.tex）；排除 vendored/example 目录。
PAPER_DIR="<论文主 .tex 所在目录>"
cd "$PAPER_DIR"
python - <<'PY'
import os, re, pathlib
TMP = os.environ.get('CX_TMP', '.engine/tmp')
pathlib.Path(TMP).mkdir(parents=True, exist_ok=True)
# 跳过 vendored/example/template 树：author kit 自带演示 \cite{...}。
# 注意这是名字匹配——你想审计的目录**不能**撞名（改名或收窄 SKIP），
# 例如 examples_of_results/ 会被跳过。
SKIP = re.compile(r'(?i)(^|/)(.*template.*|.*upstream.*|.*example.*|.*vendor.*)(/|$)')
# verbatim 类环境与行内 \verb|...| / \lstinline 是代码样例，不是引用。
VERB = re.compile(r'\\begin\{(verbatim|lstlisting|minted|Verbatim)\}.*?\\end\{\1\}', re.S)
# 可选参可能自带方括号：\lstinline[language={[LaTeX]TeX}]|...|
VERBINLINE = re.compile(r'\\(?:verb|lstinline)\*?'
                        r'(?:\[(?:[^\[\]]|\[[^\]]*\])*\])?\s*'
                        r'([^\sA-Za-z])(?:(?!\1).)*\1', re.S)
# url/href/path 的参数里可能有**不是注释**的字面 %。必须先中和它们再删注释，
# 否则同行后面真正的 \cite 会被静默吞掉。
URLCMD = re.compile(r'\\(?:url|href|path|nolinkurl)\s*\{[^{}]*\}')
COMMENT = re.compile(r'(?m)(?<!\\)%.*$')
# 显式引用命令 allowlist。不要用前后缀拼正则：笛卡尔式
# `(no|paren|auto|...)?cite(s|p|t|...)?` 既会发明命令（\citecite、\parenciteyear →
# 从任意花括号参数造出假 key），也会漏掉真实命令（\footfullcite、\volcite、\notecite）。
# 最长优先，\footfullcite 才能赢过 \footcite。
# volcite 家族：第一个花括号参数是卷/页码，不是 cite key。
VOLCITE = {'volcite', 'Volcite', 'pvolcite', 'Pvolcite', 'fvolcite', 'ftvolcite',
           'svolcite', 'tvolcite', 'avolcite',
           'volcites', 'Volcites', 'pvolcites', 'Pvolcites', 'fvolcites', 'svolcites',
           'tvolcites', 'avolcites', 'ftvolcite', 'ftvolcites'}
NAMES = sorted({
    # natbib / LaTeX core（大写变体是真实 natbib 命令）
    'cite', 'Cite', 'citep', 'citet', 'citealp', 'citealt', 'citenum', 'citeyear', 'citeyearpar',
    'citeauthor', 'citefullauthor', 'Citep', 'Citet', 'Citealp', 'Citealt', 'Citeauthor',
    # biblatex 单数 + 复数
    'parencite', 'Parencite', 'footcite', 'footcitetext', 'footcitetexts', 'textcite',
    'Textcite', 'smartcite', 'Smartcite', 'supercite', 'autocite', 'Autocite', 'fullcite',
    'footfullcite', 'notecite', 'Notecite', 'pnotecite', 'Pnotecite', 'fnotecite',
    'citetitle', 'citeurl', 'citedate', 'autocites', 'parencites', 'textcites',
    'smartcites', 'supercites', 'footcites', 'cites', 'Cites', 'nocite', 'nocites',
    # 别名 + 字段/列表形式 + bibentry——真实存在的 biblatex/natbib 家族
    'citetalias', 'citepalias', 'Citetalias', 'Citepalias', 'citefield', 'citelist',
    'bibentry', 'fullciter',
    *VOLCITE,
}, key=len, reverse=True)
# (?![A-Za-z]) 防止 \cite 吃进未知命令的 \citeXYZ；尾随组接受 [opt] 与 {grp} 任意混搭，
# \cites{k1}[note]{k2} 两个 key 都收。
CITE = re.compile(r'\\(?:' + '|'.join(map(re.escape, NAMES)) + r')\*?(?![A-Za-z])'
                  r'((?:\s*(?:\[[^\]]*\]|\{(?:[^{}]|\{[^{}]*\})*\}))+)', re.S)
# 先剥 [optional] 再读花括号组，否则 \cite[see {Smith} p.3]{k} 会把 {Smith} 当幻影 key。
OPTARG = re.compile(r'\[[^\]]*\]', re.S)
GROUP = re.compile(r'\{((?:[^{}]|\{[^{}]*\})*)\}', re.S)
CMDNAME = re.compile(r'\\([A-Za-z]+)')
# \addbibresource[opts]{x.bib} 带可选参；\bibliography{a,b} 可列多个。
BIBRES = re.compile(r'\\(?:bibliography|addbibresource)\s*(?:\[[^\]]*\])?\{([^}]+)\}')
keys, bibs, nocite_all = set(), [], False
for p in sorted(pathlib.Path('.').rglob('*.tex')):
    if SKIP.search(str(p.parent)):
        continue
    src = p.read_text(errors='replace')
    src = VERB.sub(' ', src)
    src = VERBINLINE.sub(' ', src)
    src = URLCMD.sub(' ', src)
    src = COMMENT.sub('', src)
    for res in BIBRES.findall(src):
        bibs += [r.strip() for r in res.split(',') if r.strip()]
    for m in CITE.finditer(src):
        raw_cmd = CMDNAME.match(m.group(0)).group(1)
        cmd = raw_cmd.lower()
        grps = GROUP.findall(OPTARG.sub(' ', m.group(1)))
        if raw_cmd in VOLCITE and len(grps) > 1:
            # volcite 是 {volume}{key}；复数 volcites 交替 {vol}{key}{vol}{key}...，
            # 必须取奇数位参数，否则第二个卷号被当成幻影 key 收走。
            grps = grps[1::2]
        elif raw_cmd in ('citefield', 'Citefield', 'citelist', 'Citelist',
                         'bibentry') and len(grps) > 1:
            # 这些命令只取一个 key 参数。若其后跟着多余花括号组（对歧义源的保护性读取），
            # 不要收成幻影 key（\citelist{k}{publisher} → 只留 'k'）。
            grps = grps[:1]
        for grp in grps:
            toks = [''.join(g.split()) for g in grp.split(',')]
            # \nocite{*} 和 \nocite{*,named}：通配符渲染 .bib 里**每一条**。
            if cmd.startswith('nocite') and '*' in toks:
                nocite_all = True      # 见下文 NOCITE_ALL 说明
            for k in toks:
                if k and k != '*':
                    keys.add(k)
print(f"BIB_RESOURCE={bibs[0] if bibs else '(none found - use the fallback below)'}")
print(f"BIB_RESOURCES_ALL={bibs}")
print(f"NOCITE_ALL={nocite_all}")
print(f"CITED_KEY_COUNT={len(keys)}")
# 把收割结果落盘，供 shell 确定性回读（heredoc 只打印到 stdout，无法设父 shell 变量）。
pathlib.Path(TMP, 'cx_cited_keys.txt').write_text('\n'.join(sorted(keys)))
pathlib.Path(TMP, 'cx_cited_count.txt').write_text(str(len(keys)))
print('\n'.join(sorted(keys)))
PY
# 把 $CITED_KEY_COUNT 设成真实 shell 变量（Step 3.5 要作 --expect 传入）：
# 上面 heredoc 只打印不落变量，从它刚写的文件回读。
CITED_KEY_COUNT=$(cat "$CX_TMP/cx_cited_count.txt")
```

再与编译出的 `main.bbl` 按 **key 集合**交叉核对（不是按数量）：数量对上但 key 被替换，
收割缺漏仍会被掩盖（丢一个真引用、混进一个野 key → 数量不变）。提取渲染出的 key 并 diff 集合：

```bash
# \bibitem[label]{key}（natbib/plain）或 \entry{key}{type}{}（biblatex）——key 都是第一个
# 花括号组。diff 为空 = 收割与 .bbl 一致。
grep -oE '\\(bibitem|entry)\*?(\[[^]]*\])?\{[^}]+\}' main.bbl 2>/dev/null \
  | sed -E 's/.*\{([^}]+)\}$/\1/' | sort -u > "$CX_TMP/cx_bbl_keys.txt"
comm -3 <(sort -u "$CX_TMP/cx_cited_keys.txt") "$CX_TMP/cx_bbl_keys.txt"   # 有输出 ⇒ 查清再走
```

**`.bbl` 交叉核对是条件性的——未编译的投稿没有 `.bbl`。缺席时，先确认 `CITED_KEY_COUNT`
对论文篇幅是否可信再继续；无论有无 `.bbl`，Step 3.5 的 manifest 才是承重的覆盖守卫。**

**若 `NOCITE_ALL=True`，`.tex` 收割结果就不是引用集。** `\nocite{*}` 渲染 `.bib` 里*每一条*，
默认 cited-only 口径下引用集变成「所有被渲染的条目」：有编译 `.bbl` 就取 `.bbl` 的 key，
没有就取 `.bib` 全部条目（等价 `--all`），并在报告里说明。不要按 `\cite` 收割结果继续——
那会恰好漏审所有未被 `\cite` 的条目。

`BIB_RESOURCES_ALL` 列出找到的每个 `\bibliography`/`\addbibresource`（按路径排序）；
`BIB_RESOURCE` 只是第一个。列表不止一项时，以**主** `.tex` 声明的那个为准，不要信排序；
论文确实加载多个时审并集。若 `BIB_RESOURCE` 为空（如 `\input` 摊平的投稿），回退取论文目录下
最大的 `*.bib`；有编译 `main.bbl` 时，直接从其 `\bibitem{...}` 读被引 key（`.bbl` 才是
「实际渲染了什么」的真值）。

产出有序被引 key 清单，并为每条配好**题名 + 第一作者**（这是 B 唯一允许看到的信息）。确认每个
key 都在 `.bib` 里。给每条分配稳定不透明序号 **`dedup_key`**（`01`、`02`…按解析顺序）：这是
下游各分片拼接的规范 id。A 拿到 `dedup_key` + cite key；B 只拿 `dedup_key` + 题名 + 第一作者
（**绝不**给 cite key 或 `.bib` 文本），拼接键不向盲侧泄露任何书目内容。为 Step 3.5 的门写两份
产物（按解析顺序）：`$CX_TMP/cx_dedup_keys.txt`（序号集，空白分隔）与 `$CX_TMP/cx_keymap.tsv`
（每条一行 `dedup_key<TAB>cite_key`——序号→cite key 的**钉**）。Step 3.5 用
`$CX_TMP/cx_keymap.tsv` + `.bib` 构建覆盖 manifest（序号 → cite key → 题名哈希），把 A 对着它
按**映射**核验——下游丢引用**或换引用**都会 fail，只查数量或序号集合会放过「保持数量的替换」。

### Step 2 — 发起 A 与 B，二者互盲

这是只读的**提取扇出**：A、B 是两个只做*记录提取*的分片（各自返回以 `dedup_key` 为键的
`entries[]` 集合——绝不按列表位置、绝不按 B 可见的 cite key、绝不带质量排序），C 产出机械的
逐字段差分，不是裁决。每个分片返回 `{shard_id, entries:[{dedup_key, …}]}` 信封，执行者在 C
之前先做下述机械 `dedup_key` 拼接。

**派发（tier-portable）。** *Tier 1*——Workflow/多智能体运行时：A、B 两个并发分片，都回来后
再 C。*Tier 2*——宿主有 `Agent` 类委派工具：同一条消息里发两个调用（并发、互不共享上下文），
然后 C。这两种都给 B 一个**从未接收过 `.bib` 的全新子上下文**，B 真盲、可如实作证 `blind:true`。
*Tier 3*——无委派能力（裸宿主）：A、B、C 顺序执行；只有宿主能给 B 一个未继承 `.bib` 的上下文
时 B 才算盲，否则 B **必须**作证 `blind:false`，Step 3.5 会把所有通过项降级为旗标。拼接与
字段差分在所有 tier 完全一致；盲不盲由 `blind` 作证 enforcement，不靠派发方式假设。

> **条件双盲（normative）。** 整个交叉核对押在「B 没见过 `.bib`」上。隔离是**前提条件**，
> 不是默认属性：Step 1 的主上下文已经读过 `.bib`，若 B 在同一上下文里跑（或「全新顺序上下文」
> 无法保证丢掉父上下文的 `.bib` 视图），B 就**不是**盲的——此时提示词禁令并没有被*执行*
> （B 可能已观察到父上下文的 `.bib` 读取或 A 的输出）。所以：
> - 宿主能把 B 派发进真正隔离、未继承 `.bib` 的上下文（只投喂题名+一作清单）→ B 作证
>   `blind:true`，本轮正常认证；
> - 否则 → B **必须**作证 `blind:false`，Step 3.5 门把每个 `MATCH`/`MINOR` 降为 `ESCALATE`：
>   本轮仍为主 agent 的 Step 4 webcheck *旗标*分歧，但*不认证*任何条目——这是「带标签的
>   启发式检查」，不是双盲认证。
>
> 永不为「通过」而谎报 `blind:true`——虚假盲作证是唯一能击穿整套交叉核对的东西。

**广度。** 分片数固定为三，是**设计**而非预算：双盲 diff 最少要两份记录（各代表一个出处），
第三个是必须两者都没生产过的差分器。这里广度不是扫描参数，没有 breadth/cost 权衡可调——
它买到的上限是「两份独立记录」，不是集成学习。

- **Agent A（只读仓库）**：读 `.bib`；把每条被引条目**逐字**提取（花括号配平、不重排）→
  `$CX_TMP/cx_A_ourbib.json`，结构
  `{"shard_id":"A","entries":[{"dedup_key","key","bibtex"}]}`。明确指示：**禁止联网搜索**。
- **Agent B（只联网）**：只拿 Step 1 的题名+第一作者清单，为每篇论文独立联网重查记录，输出干净
  BibTeX → `$CX_TMP/cx_B_web.json`，结构
  `{"shard_id":"B","blind","entries":[{"dedup_key","title_queried","found","source_url","bibtex","sources_tried","note"}]}`。
  明确指示：**禁止读任何本地文件/.bib**；某篇无法确认时置 `found:false` 并写 note；绝不编造字段。
  - **`blind` 作证（整个 B 分片置一次）。** 只有当 B 确实运行在不可能见过 `.bib` 的隔离上下文
    （未继承主 agent 历史）时才置 `blind:true`；无法保证时**必须**置 `blind:false`。Step 3.5
    门拒绝为任何非盲作证条目认证 `MATCH`/`MINOR`。
  - **不要把检索限死在 arXiv/DBLP。** 大量正当引用是 workshop 技术报告、公司研究博客、
    会议页面，arXiv 上根本没有。题名在 arXiv 查不到时，B 必须再跑通用 web 搜索，并打开
    **自己搜到的**落地页（项目/博客/会议 URL）之后才能下 `found:false`。B 只凭题名+一作查询
    ——绝不能拿到、也不能使用 `.bib` 条目的 `url` 字段（那个 url 留给主 agent 的 Step 4
    webcheck）。arXiv 查不到**不是**伪造的证据。
  - **逐条记录 `sources_tried`**（如 `["arxiv","crossref","semantic-scholar(429)","web"]`），
    让「降级搜索（某源宕机/限流）导致的 `found:false`」与「真查无」可区分；哪个源失败/被挡，
    写进该条 `note`。

B 回来后，主 agent **按 `dedup_key` 拼接 A 与 B**——Step 1 的每个序号在两侧必须恰好出现一次。
缺号、重号或数量不齐都是 **fail-closed 停机**（重跑出错的那片），绝不静默丢弃、绝不按位置猜。
这次机械拼接取代顺序耦合，且对引用本身不作任何判断——只确认两份提取能对上，才交给 C diff。

### Step 3 — 发起 C，字段差分提取器（A+B 都回来之后）

> **C 只提取，不裁决。** 逐字段差分是机械提取；判定某条*是* `MATCH`（即接纳为正确）是验收
> 裁决，归执行者。所以 C 产出**逐字段证据**，不是逐条裁决：每个字段报
> `same` / `differs`（双侧原值都带上） / `absent`，外加下面的路由旗标。主 agent 在 Step 4
> 依据这些证据裁定每个最终 `MATCH|MINOR|MISMATCH|NEEDS_WEBCHECK`。返回裁决标签的分片即违约。

第三个提取者（新上下文；无委派能力的宿主就顺序再跑一轮）读取两份 JSON（它自己哪份都没生产），
对每对 `dedup_key` 拼接记录逐字段 diff——题名（忽略大小写/花括号）、**作者集合与顺序**、年份、
venue（NeurIPS ≡ "Advances in NIPS"；真换了会议要报出）、卷/页、arXiv id / DOI。输出
`$CX_TMP/cx_C_fielddiff.json`：
`{"shard_id":"C","entries":[{"dedup_key","key","blind","found","sources_tried","url","fields":{"<field>":{"status":"same|differs|absent","ours","web"}},"flags":[...]}]}`
（`found`/`sources_tried`/`blind` 从 B 原样抄，`url` 取自 A，让 Step 4 与门不必回读分片文件；
以拼接的 `dedup_key` 为键）外加 `summary`
`{entries, fields_by_status:{same,differs,absent}, flags_by_type}`——机械字段状态的计数，
**不是**裁决票型。

**C 的关键路由旗标（防住最危险的假阳性）**：若 B 对某条报 `found:false`，而 A 侧 `.bib` 类型是
`@misc`（或以 `url`/`howpublished` 代替 arXiv id/DOI），且 B 的 `sources_tried` 显示它只查了
看不见该 URL 的索引源（arXiv/DBLP 等），C **必须**打旗标 `url_only_source_unqueried`，
**不得**把该条报成「网上不存在」。B 的索引式检索结构性无法确认博客/技术报告引用；只有主 agent
在 Step 4 直接 fetch 该 `url` 才行。`sources_tried` 显示某源宕机/限流时，C 打 `degraded_search`；
B 无论因何种原因返回 `found:false`，C 都打 `web_record_absent`。这些旗标只把条目推进主 agent 的
Step 4 队列——**没有一个是关于引用的结论**，它们记录的是 B 的搜索做了什么，不是参考文献是否可靠。

### Step 3.5 — 跑确定性 verifier 门（`cx_verify.py`，强制）

扇出契约要求终点是「跨模型评审步**或**确定性 verifier 门，且在所有 tier 间完全一致」。本技能
没有跨模型评审，所以门是**外部进程**，在 Tier 1/2/3 上行为相同。**门自己从 A、B 的原始记录重算
字段 diff**（解析两份 `.bibtex`），并直接从 B 读盲性作证；路由旗标同样**从 A、B 自身产物重算**
（`web_record_absent` 来自 B 的 `found`；`degraded_search` / `url_only_source_unqueried` 来自
B 的 `sources_tried` + A 的字段）。C 的 `flags` 只是建议，与重算结果取并集；C 的 schema 违例
（如 `flags` 不是列表）一律 fail-closed。所以 C——本身是个模型分片——**完全不在信任路径里**：
故障或被对抗的 C 漏报分歧字段、伪造 `blind:true`、或*丢掉路由旗标*，都既拿不到 `MATCH`、
也不能把条目放行，因为门对 diff 与路由都不采信 C 的话。

```bash
# 解析门脚本：优先 $CX_VERIFY 环境变量；否则自当前目录逐级向上找本仓技能目录。
# （cwd 通常是论文目录；论文仓与工具箱同仓时向上走即可命中。）
CX_VERIFY="${CX_VERIFY:-}"
if [ -z "$CX_VERIFY" ]; then
  _cx_dir="$(pwd)"
  while :; do
    for _cx_rel in "academic-toolkit/skills/citation-crosscheck/scripts/cx_verify.py" \
                   "skills/citation-crosscheck/scripts/cx_verify.py"; do
      if [ -f "$_cx_dir/$_cx_rel" ]; then CX_VERIFY="$_cx_dir/$_cx_rel"; break; fi
    done
    [ -n "$CX_VERIFY" ] && break
    [ "$_cx_dir" = "$(dirname "$_cx_dir")" ] && break
    _cx_dir="$(dirname "$_cx_dir")"
  done
fi
[ -z "$CX_VERIFY" ] && {
  echo "ERROR: 未找到 cx_verify.py（确定性 verifier 门）。" >&2
  echo "       解析顺序：\$CX_VERIFY → 自 cwd 向上找 academic-toolkit/skills/citation-crosscheck/scripts/ 或 skills/citation-crosscheck/scripts/。" >&2
  echo "       门跑不起来时，禁止手判 MATCH/MINOR 顶替机械门——只能在此停下并报告缺口。" >&2
  exit 1
}
python "$CX_VERIFY" --selftest || exit 1          # 内建用例；失败 = 不要信任这个门
# 构建覆盖 manifest（序号 → cite key → 题名哈希）：用 Step 1 的序号钉（$CX_TMP/cx_keymap.tsv）
# + .bib，用门**自己的解析器**。它与 A 无关，门才能把 A 当映射来核。$BIB = Step 1 解析出的 .bib 路径。
python "$CX_VERIFY" --build-manifest --bib "$BIB" --keymap "$CX_TMP/cx_keymap.tsv" \
        --out-manifest "$CX_TMP/cx_manifest.tsv" || exit 1
# 门重算字段 diff 与路由旗标，并直接读 B 的盲性作证；C 的 flags 仅供并集，C schema 违例即
# fail-closed。覆盖检查强制：--expect-manifest 对 A 核「序号→key/题名」映射（抓住序号集查不出的
# 掉包替换）；--expect / --expect-keys 加数量与序号集检查。空产物、重复/缺失/被替换的 key、
# 被丢的引用、A/B/C key 集合不一致——一律非零退出，绝不读成「干净」。
python "$CX_VERIFY" --a "$CX_TMP/cx_A_ourbib.json" --b "$CX_TMP/cx_B_web.json" \
        --c "$CX_TMP/cx_C_fielddiff.json" \
        --expect "$CITED_KEY_COUNT" --expect-keys "$CX_TMP/cx_dedup_keys.txt" \
        --expect-manifest "$CX_TMP/cx_manifest.tsv" \
        --json "$CX_TMP/cx_gate.json" || exit 1
```

门裁什么、拒裁什么：

- **`MATCH`**——*声明过的*归一化（LaTeX 音标/花括号折叠、大小写、标点；**保序**的姓氏列表；
  固定 venue 别名表）之后每个比较字段相等。
- **`MINOR`**——唯一差异是同一工作的 preprint-vs-published venue。
- **`ESCALATE`**——其余一切，**fail-closed**：任一标识字段不同（`authors`/`year`/`title`/
  `doi`/`arxiv`）、次级字段不同、单侧缺标识字段、venue 对不在声明表、任何路由旗标、
  `found != true`、**或条目未过盲作证**（`blind != true`）。缺盲作证的 `MATCH`/`MINOR` 一律
  降为 `ESCALATE`：本轮仍可*旗标*分歧，但不许*认证*通过。这就是双盲主张的机械化执行——
  无法隔离派发 B 的宿主让 B 置 `blind:false`，门拒绝认证任何条目，检查退化为「带标签的
  启发式」而非「虚假认证」。

**门永不输出 `MISMATCH`。** 分歧只有主 agent 对着出版记录复现后才是发现（finding）：通过路径
机械化，拒绝路径靠外部证据。作者*顺序*被归一化器刻意保留——换序正是本技能要抓的缺陷，
绝不能归一成相等。

### Step 4 — 逐条裁定（主 agent，强制）

任何裁决都不会从分片预装进来。读 `$CX_TMP/cx_gate.json`（门重算的裁决与逐字段证据）——
C 的 `cx_C_fielddiff.json` 仅作审计，**不得**覆盖门。**本步不变式：每个
`MATCH`/`MINOR`/`MISMATCH` 必须立足於 (a) 门的机械判定，或 (b) 主 agent 完成的一次主源 fetch。
任何分片信号——`differs`、`absent`、B 的 `found:false`、路由旗标——本身都不是发现。** 两种
穷尽情形：

- **门判 `MATCH` 或 `MINOR`** → 采纳（情形 (a)，机械）。不要用文字重新争论机械相等判定，
  也不要悄悄升级成 `MISMATCH`；认为门错了，正路是改门的归一化表并补 `--selftest` 用例，
  不是手改某一行。（无旗标 `MATCH` 的含义：两份独立记录一致——**不等于**「已对出版商记录核验」。）
- **门判 `ESCALATE`** → 主 agent **必须先完成主源 fetch，才可裁** `MATCH`/`MINOR`/`MISMATCH`/
  `NEEDS_WEBCHECK`。这是**流程**，不是「首个命中即停」的菜单：把适用的 fetch 都做完，**再**
  决定——不让较早的分支抢跑更严的分支。

  1. **Fetch。** 认出并用 `WebFetch` 抓主源：
     - `.bib` 里带 `url`/`howpublished` 的，先抓它自己的 `url`——`url_only_source_unqueried` /
       `web_record_absent` 情形必做（这个 url B 从没见过）；**并且**
     - 抓字段指向的规范索引——arXiv id 对应 arXiv 摘要页、DOI 对应解析页，否则 venue/会议页。
     存在性未确认的条目，**另跑主 agent 自己的通用 web 搜索**（独立于 B）。记录试过的每个
     URL 与查询词。

  2. **按 fetch 实际返回决定**——每个终态都立足一次已完成的 fetch：
     - 主源**证实** `.bib`（题名 + 作者集合/顺序 + 年份 + id 一致）→ `MATCH`（注明来源；
       对 url 证实的非 arXiv 条目注「blog/tech-report, web-confirmed」）。门报了
       `differs`/`absent` 但主源不复现的，在此降级并记录理由。
     - 同一工作，仅 preprint-vs-published 之差 → `MINOR`。
     - 主源**反驳**标识字段（作者集合/顺序、年份、venue 换了真会议、arXiv id/DOI，
       或题名/副题/措辞实质变更；或页码/卷号区间移动）→ `MISMATCH`，引用抓到的值。
       （字段分歧类 `MISMATCH`——主源复现了分歧；这防的是 B/C 幻觉编造一个*错误*的「修正」。）
     - **存在性无法确认** → 只有当**两条同时成立**才判 `MISMATCH`（伪造）：条目的 `url`
       缺失/失效/相矛盾，**且**主 agent 自己的通用搜索也失败。仅 `url` 失效、或仅 B 的
       `found:false`，**永远不够**——这是通往「伪造」结论的唯一通道，它立足的是主 agent
       自己的空结果，不是 B 的未命中。
     - fetch **无结论**（源不可达/真含糊）→ `NEEDS_WEBCHECK`，留给作者。绝不把无结论的
       fetch 默认成 `MATCH` 或 `MISMATCH`。

  单侧 **`absent`** 字段不按「两侧共有字段」就地了结：门已经把它升级了，裁决按上面的阶梯来自
  抓到的主源（只有当 `.bib` 断言了主源相矛盾的字段，absent 才走向 `MISMATCH`；否则按 fetch
  判 `MATCH`/`MINOR`，absent 写进 `Detail`）。

**每条离开 Step 4 时恰好带四个标签之一**，每个 `MATCH`/`MINOR`/`MISMATCH` 都有门或一次完成的
主 agent fetch 背书。若某 `ESCALATE` 的证据哪条都对不上，那是 fetch 还没做完，不是让分片
拍板的许可。**不要**只凭分片证据改 `.bib`：每一处被应用的修正都必须能追溯到主 agent 的 fetch。

### Step 5 — 产出对照表 + 仅应用已证实的修正

用 openpyxl 生成 `.xlsx`，每条引用一行，列：
`# | BibKey | Link | Our BibTeX | Web BibTeX | B source | Verdict | Author check | Year |
Detail | Fix`。Verdict 单元格着色：绿 = `MATCH`；黄 = `MINOR` 或主 agent 已解决为 MATCH 的
`NEEDS_WEBCHECK`（注明如何解决）；橙 = `MISMATCH`。另加 Summary 页：计数 + 已修/可选清单。

**降级**：openpyxl 不可用时，输出**同列结构**的 `citation_crosscheck_<date>.csv`（UTF-8），
审计继续，报告里注明降级——不因缺包中断。

只把**主 agent 已证实**的 `MISMATCH` 修正写回 `.bib`；论文已编译则重编译让 `.bbl` 吃进修正，
并复核页数不变。`MINOR` 项只列为可选（不自动执行 preprint→published 升级；那是作者的选择）。

## Key rules

- **盲性即机制。** B 一旦见过 `.bib`，交叉核对就塌缩成单源阅读，威力归零。用隔离上下文执行
  它，做不到就如实 `blind:false`——绝不谎报。
- **A、B、C 都不编造字段。** `found:false` + note 胜过猜测。
- **非 arXiv 未命中不是伪造。** `@misc`/博客/技术报告/会议 URL 引用是正当的，arXiv/DBLP
  搜不到。B 必须仅凭题名+一作再试通用 web；C 给带 url 的未确认条目打
  `url_only_source_unqueried`，主 agent 在 Step 4 fetch 该条自己的 `url`。判 `MISMATCH`
  （伪造）必须**同时**：`url` 失效/矛盾 **且** 主 agent 自己的通用 web 搜索也失败——
  仅 `url` 失效永远不够。跳过这条就是本技能最危险的假阳性。
- **分片提取，主 agent 裁决。** A、B、C 产出记录与逐字段差分；每个
  `MATCH`/`MINOR`/`MISMATCH`/`NEEDS_WEBCHECK` 都由主 agent 在 Step 4 裁定；每处 `.bib` 修改
  前都必须由主 agent web 证实。分片提议，主 agent 的 fetch 处置。
- **只管书目，不管 context-fit。** 「是否支撑论文论点」超出本技能范围——那是写作审稿类技能
  （如 `paper-submission-audit`）的职责。投稿前建议与 `check-citations` 并用。
- **报告，不悄悄升级。** preprint-vs-published 与化妆性的 key/年份标签差异是 `MINOR`；
  列出来，把选择留给作者。

## 中间产物（审计留痕）

| 文件（在 `$CX_TMP`，默认 `.engine/tmp/`） | 产生者 | 内容 |
|---|---|---|
| `cx_cited_keys.txt` / `cx_cited_count.txt` | Step 1 | 被引 key 集 / 数量 |
| `cx_bbl_keys.txt` | Step 1 | `.bbl` 渲染 key 集（有编译产物时） |
| `cx_dedup_keys.txt` / `cx_keymap.tsv` | Step 1 | 序号集 / 序号→cite key 钉 |
| `cx_A_ourbib.json` | A | `.bib` 逐字提取记录 |
| `cx_B_web.json` | B | 联网独立重查记录（含 `blind` 作证与 `sources_tried`） |
| `cx_C_fielddiff.json` | C | 逐字段差分 + 路由旗标（审计用，不覆盖门） |
| `cx_manifest.tsv` | 门 | 覆盖 manifest（序号→key→题名哈希） |
| `cx_gate.json` | 门 | 机械裁决与逐字段证据（Step 4 的裁决输入） |
