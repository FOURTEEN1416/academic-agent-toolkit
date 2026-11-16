---

name: paper-write-nature

description: "Draft a Nature-style LaTeX paper with hourglass structure, reader-first logic, and publication-quality English. Use when the target venue is a Nature-family journal. 区别于 paper-write：本技能用 Nature 沙漏结构与期刊写作规范，ML 会议稿改用 paper-write；Word(docx) 输出改用 paper-write-nature-docx；仅重构个别章节（作者已有 claims/figures）用 paper-sections-nature。"
argument-hint: [venue-or-section]

allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Agent, WebSearch, WebFetch

---



# Nature-Style Paper Writing



Draft a Nature-quality LaTeX paper based on: **$ARGUMENTS**

> **分工**：已有成稿的语言层润色/翻译用 `paper-polish-nature`；本技能负责结构起草与全文生成（沙漏架构与章节职责见下，为该架构的权威表述）。



## Constants



- **TARGET_VENUE = `Nature`** — Override via Additional Parameters. Supported: Nature, Nature Methods, Nature Machine Intelligence, Communications journals.

- **MAX_PAGES** — Nature Article: ~5 pages main text + Methods. Override via Additional Parameters.

- **ANONYMOUS = false** — Nature uses non-anonymous submission.

- **DBLP_BIBTEX = true** — Fetch real BibTeX from DBLP/CrossRef. Never fabricate.

- **CUSTOM_REQUIREMENTS** — Highest priority.

- **REVIEWER_SCRIPT** — External reviewer script.

- **SCHOLAR_SCRIPT = `tools/scholar_fetch.py`** — Scholar fetch client for real BibTeX retrieval (AMiner/Semantic Scholar/DBLP/CrossRef/OpenAlex).



## Inputs



1. PAPER_PLAN.md — outline with claims-evidence matrix, figure plan

2. RESULTS.md — structured experiment results

3. figures/ — SVGs/PDFs + latex_includes.tex

4. Existing .bib file (or will create)



If no PAPER_PLAN.md, generate minimal outline from available docs.



## Core Architecture



### 1. Identify Paper Type First



Before writing, determine the paper type:



- **Research paper**: why the phenomenon matters → what was done → what was found → what it means

- **Methods paper**: does the method work → is it reproducible → is it better under fair comparison

- **Hypothesis-based**: establish or rule out a causal explanation

- **Algorithmic/device**: propose procedure/tool/system → show reliable and advantageous performance



Do not use one narrative logic for all paper types.



### 2. Reader-First Writing Order



Write for the reader's cognitive sequence:

1. Is this relevant to me? (Introduction hook)

2. What is new here? (Contribution statement)

3. Do I trust it? (Results + Methods)

4. Can I reuse it? (Methods detail + Data Availability)

5. What does it mean? (Discussion + boundaries)



### 3. Productive Writing Order



For research articles, write in this order:

1. **Results** — anchor everything in evidence

2. **Introduction** — frame the gap now that you know the findings

3. **Title** — crystallize the contribution

4. **Discussion** — interpret and bound

5. **Materials and Methods** — reproducibility

6. **Abstract** — mini-paper summary last



### 4. Hourglass Structure



- **Introduction**: open broadly → narrow to specific gap → state question/hypothesis

- **Discussion/Conclusion**: widen again → connect findings to literature → explain how gap was filled



### 5. Paragraph Architecture: Claim-Evidence-Boundary



Every paragraph follows:

- **Claim**: one controlling idea (topic sentence)

- **Evidence**: data, comparison, explanation, literature support

- **Boundary**: limitation, scope, or transition to next claim



## Section Responsibilities



### Title

- ≤ 75 characters including spaces (Nature guideline)

- Searchable, specific, restrained, defensible

- Pattern: `[Core entity] in/through/by [mechanism or context]`

- No vague hooks, no unverified "first"



### Abstract (150–200 words)

Mini-paper structure: context/problem → gap → approach → key result with numbers → implication



### Introduction (~600–800 words for Nature)

- Hook: why the topic matters broadly

- Known: what is established

- Gap: what remains unresolved

- Aim: what this study asks/does

- Value: brief indication of approach and significance

- Do NOT summarize Results or Conclusion here

- Short paragraphs OK (Nature style allows 3–4 sentence paragraphs)



### Results

- Past tense: report what was observed

- Orient reader to figure/table → state main observation → quantitative detail → patterns

- Results = what happened, NOT what it means

- Each result paragraph tied to a specific figure or table

- **Figure numbers MUST be cited explicitly (every paragraph names its "Fig. N"), but VARY the citation pattern — don't open every figure with the same "Fig. N shows/presents…" skeleton.** Rotate: parenthetical ("…dropped 4.2% (Fig. 3)"), sentence-start, verb-led ("Comparing the curves in Fig. 4…"), figure-as-subject (when it carries a real quantitative finding). The number always appears; only the sentence structure rotates. Adjacent figures must not use the same pattern.

- Active voice preferred: "We observed..." not "It was observed that..."



### Discussion

- Restate main finding → plausible explanations → compare with earlier work → limitations → implications → future work

- Short rule: Results = what we observed; Discussion = how we understand it and when it may fail

- Three-part close: contribution → key evidence → implication with boundary



### Materials and Methods

- Specific, complete, transparent, reproducible

- Another group must determine: ethical conformity, materials/conditions, key parameters, data processing, statistical tests, software versions

- Never: "under standard conditions", "using routine methods", "data were analyzed statistically"



### Data Availability Statement

Generate using Nature data policy principles:

- Map each dataset to access route: public repository, controlled access, within supplement, reused source, third-party restricted

- Prefer DOI/accession numbers over personal websites

- Pattern: "The [data type] generated in this study have been deposited in [repository] under accession code [XXX]. Source data are provided with this paper."

- Flag "available upon request" as weak unless legally/ethically required



## Failure Mode Diagnosis



Before editing any section, diagnose the main problem in priority order:



1. **Paper type** — wrong narrative logic for this paper type?

2. **Section job** — section not fulfilling its rhetorical responsibility?

3. **Paragraph logic** — claim without evidence? evidence without claim? missing boundary?

4. **Sentence polish** — clutter, passive voice, overclaim?



Fix from top down. Do not polish sentences while reasoning is broken.



## Nature-Specific Style Rules



### Sentence control

- Each sentence ≤ 30 words

- One core subject-verb proposition per sentence

- Split overloaded sentences rather than polishing cosmetically

- Active voice preferred: "We show..." not "It is shown that..."



### Paragraph control

- Short paragraphs OK (3–5 sentences typical for Nature)

- Each paragraph: one controlling idea + support

- Thematic linking, not repetitive "This suggests..." openings



### De-AI Polish Rules



Remove or replace these AI-typical words:

- "delve" → "examine", "investigate"

- "pivotal" → "important", "central"

- "landscape" → "field", "area"

- "multifaceted" → "complex"

- "underscores" → "shows", "highlights"

- "leveraging" → "using"

- "novel" (overused) → "new", or remove if claim is clear from context

- "groundbreaking" → remove or use specific evidence

- "paradigm shift" → describe the actual change

- "in conclusion" → just state the conclusion directly



### Hedging (Academic Phrasebank patterns)

- "These results suggest that..."

- "A possible explanation is that..."

- "This discrepancy may reflect..."

- "To our knowledge, this is the first..."

- "Further work is needed to determine whether..."



### Transitions

- Contrast: "However,", "By contrast,", "Nevertheless,"

- Addition: "Moreover,", "Furthermore,", "In addition,"

- Cause: "Consequently,", "As a result,", "Therefore,"

- Concession: "Although...,", "Despite...,", "Notwithstanding,"



### Limitations acknowledgment

- "These results should be interpreted with caution because..."

- "A limitation of this study is that..."

- "The generalizability of these findings is limited by..."



## ⛔⛔⛔ Output Contract (highest priority)



**Mandatory output depends on `params.output_format`**:



- **PDF mode**: `paper/main.tex` (≥ 5KB) + `paper/sections/*.tex` + `paper/references.bib`

- **docx mode**: `paper/main.md` (single file, ≥ 5KB). Do NOT create `paper/main.tex`. docx 模式请改用 paper-write-nature-docx。




产出结构、存在性和最低完整性由 `finish` 按模板中的 `output_contract` 自动核验；修复返回的具体问题，不复制执行验证脚本。

**If verification fails, complete the missing files instead of exiting**.



## 执行与产出

使用当前执行会话完成本步工作；产物路径按当前步骤合同。程序采集真实操作、输入输出、版本与运行清单，模型只负责实质成果和领域质量。

建议额外记录：模板来源哈希、BibTeX 条目数、引用格式。

## Workflow
### Step 1: Read inputs and plan



Read PAPER_PLAN.md, RESULTS.md, figures/. Identify paper type and writing order.



**⛔ MANDATORY: Read `figures/latex_includes.tex` first and build a FIGURE EMBEDDING PLAN before writing any section.**



```bash

echo "=== Figures available ==="

ls -la figures/*.pdf figures/*.png 2>/dev/null

echo ""

echo "=== latex_includes.tex content (figure→PDF mapping) ==="

cat figures/latex_includes.tex 2>/dev/null || echo "⚠ No latex_includes.tex — figures may not be wired up"

```



Build mapping: **every figure block in `latex_includes.tex` must be copied into an appropriate section**. Sources:

- `paper-figure-nature` step writes data figure blocks (fig_*.pdf)

- `paper-figure-drawio` step appends architecture/flow/pipeline figure blocks (fig_roadmap.pdf, fig_flow_*.pdf, tikz_*.pdf, etc.)



**⛔ Use figure blocks from `latex_includes.tex` — do NOT write `\includegraphics` from scratch.** Path convention: `figures/xxx.pdf` (relative to repo root) or `../figures/xxx.pdf` (relative to paper/sections/).



**⛔ Every figure block from `latex_includes.tex` MUST appear in some section file** — both data figures (Results section) and DrawIO architecture diagrams (Methods/Overview sections). Missing any figure = audit fail.



### Step 2: Draft Results first



Write Results section anchored to figures and data. Each paragraph: orient → observe → quantify → pattern.



**⛔ Cross-section context + figure-data binding (prevents the "two-layers" disconnect):**

- **After finishing each section**, append a 3-5 line card to `_writing_context.md` in the workspace root (core claim / key numbers / newly defined symbols & terms / figures discussed); re-read it before the next section so Introduction/Discussion/Methods carry forward the Results' conclusions, reuse defined terms (don't redefine), and keep every metric's number consistent across the paper — see `<chapter_context_card>` in `shared-scripts/writing_rules.md`.

- **Before writing the analysis for any figure**, follow `<figure_data_binding>`: identify *what quantity the figure plots* from `latex_includes.tex`/FIGURE_MANIFEST → locate its real values in `RESULTS.md`/`figures/all_results.json` → use only those real numbers. **Never guess numbers from the plot's shape/position, never fabricate coordinates.**



### Step 3: Draft Introduction



Frame the gap now that findings are known. Hourglass: broad → narrow → specific aim.



### Step 4: Draft Title



Crystallize contribution in ≤ 75 characters.



### Step 5: Draft Discussion



Interpret findings, compare with literature, acknowledge limitations, state implications.



### Step 6: Draft Methods



Complete, reproducible, specific. Include statistical tests, software versions, parameters.



### Step 7: Draft Abstract



150–200 words. Context → gap → approach → key result → implication.



### Step 8: Data Availability + Author Contributions



Generate Data Availability statement. Add Author Contributions template.



### Step 9: Self-review



Run failure mode diagnosis on each section. Check:

- [ ] Hourglass structure intact

- [ ] Each paragraph has claim-evidence-boundary

- [ ] No AI-typical language remaining

- [ ] Active voice dominant

- [ ] Sentences ≤ 30 words

- [ ] Title ≤ 75 characters

- [ ] Abstract 150–200 words

- [ ] No fabricated references

- [ ] Hedging appropriate (no overclaim)

- [ ] Data Availability complete



### Step 10: References + Compile



**⛔ References — retrieve real entries, NEVER fabricate.** Do NOT write BibTeX from memory.

Follow the `<references_workflow>` in `shared-scripts/writing_rules.md`: for every cited key,

restore it to search keywords and fetch real BibTeX via `$SCHOLAR_SCRIPT` (AMiner + Semantic

Scholar + DBLP + CrossRef + OpenAlex), e.g.:

```bash

PYTHON=""; for _c in "$MH_PYTHON" python python3; do [ -z "$_c" ] && continue; if $_c -c "import sys" >/dev/null 2>&1; then PYTHON="$_c"; break; fi; done; [ -z "$PYTHON" ] && PYTHON=python

# extract cited keys → _tmp/_cited_keys.txt, then:

while IFS= read -r key; do

    query=$(echo "$key" | sed 's/^TODO__//; s/_/ /g')

    echo "--- Fetching: $key (query: $query) ---"

    $PYTHON "$SCHOLAR_SCRIPT" bibtex "$query" --max 3

    sleep 0.5

done < _tmp/_cited_keys.txt

```

Copy the correct entry's `bibtex` field into `paper/references.bib`. If a source truly cannot be

found, flag it `note = {[VERIFY] ...}` — never invent a DOI/title/authors to fill the gap.



Then save to `paper/main.tex` with proper Nature formatting and compile.



## Related Files



| File | Open when |

|------|-----------|

| [references/section-moves.md](references/section-moves.md) | Section-specific move patterns and phrase families |

| [references/style-guardrails.md](references/style-guardrails.md) | Academic style checks, hedging, transitions |

| `shared-scripts/writing_rules.md` | General LaTeX writing rules |

| `shared-scripts/compile_check.sh` | Compilation verification |



## Key Rules



- ⛔ Never fabricate references — use DBLP/CrossRef or flag with [VERIFY]

- ⛔ Never upgrade association to causation

- ⛔ Never let AI draft the core scientific argument from scratch

- ⛔ No `plt.title()` in figures — captions in LaTeX only

- Language serves argument — do not polish sentences while reasoning is broken

- Write with empathy for the reader: relevance → novelty → trust → reuse → meaning

- If the draft is structurally rough, reconstruct logic first, prose second

- Nature allows short paragraphs — do not pad for length

- Direct claims with evidence, not hedged-to-meaninglessness





---



## ⛔ Figure embedding verification (MUST pass before finishing — file existence + actual `\includegraphics` reference both required)

已并入共享脚本 `paper_write_audit.sh`（paper-write 族单一实现）。**怎么跑**：

```bash
bash _utils/paper_write_audit.sh --mode latex   # 本目录无 _utils 时: bash skills/shared-scripts/paper_write_audit.sh --mode latex
```

**怎么读结果**：任何 `MISSING:` / `❌` 行或 `Total missing embeddings > 0` 都表示有图未嵌入或缺件——逐项补齐后重跑至 0；`⛔ DO NOT finish until missing = 0.`。该脚本同时执行下方 FIGURE_MANIFEST audit 与 universal paper audit；审计留痕由程序采集，不再手写 AUDIT_REPORT 审计文件；有引擎 finish 时以 output_contract/`paper_write_gate` 自动核验为准，本脚本为无引擎合同场景的兜底预检。



---



## ⛔ FIGURE_MANIFEST audit (run before finishing — must produce + embed every planned figure)

已并入共享脚本 `paper_write_audit.sh`（见上节，随 `bash _utils/paper_write_audit.sh --mode latex` 一并执行）。**怎么读结果**：`✅ FIGURE_MANIFEST fully embedded` = 通过；`❌ MANIFEST: ...` / `⛔ FIGURE_MANIFEST audit failed (N missing)` = 计划图缺文件或未嵌入正文——补产/补嵌后重跑。判据与原内联版逐项一致（计划图清单取自 PROBLEM_ANALYSIS/PAPER_PLAN/MODELING_REPORT/TOPIC_PLAN 的 FIGURE_MANIFEST 块，检查 .pdf/.png 存在且被 paper/sections/ 或 paper/main.tex 引用）。



## ⛔ Universal paper-stage audit (shared across all writing steps)

已并入共享脚本 `paper_write_audit.sh`（见上节，随 `bash _utils/paper_write_audit.sh --mode latex` 一并执行；内部调 `_utils/facts_audit.py --stage paper`，无 `PROBLEM_FACTS.json` 时自动走简化模式）。检查项：[13] 正文结论与 results.json 一致；[14] 事件源归属。**怎么读结果**：输出 `❌ Universal paper-stage audit failed` = 修正正文/results.json 后重跑。审计输出由程序采集留痕，不再手写 AUDIT_REPORT 审计文件。



