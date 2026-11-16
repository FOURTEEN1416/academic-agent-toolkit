---
name: meta-research-summarizer
description: "Summarizes papers, web articles, reports, and dense sources into citable briefs. Use when summarizing research material."
license: MIT
metadata:
  version: 1.0.0
  author: Alireza Rezvani
  category: product
  updated: 2026-03-16
---

# Research Summarizer

> Read less. Understand more. Cite correctly.

Structured research summarization workflow that turns dense source material into actionable briefs. Built for product managers, analysts, founders, and anyone who reads more than they should have to.

Not a generic "summarize this" — a repeatable framework that extracts what matters, compares across sources, and formats citations properly.

---

## Scope — Distinct From the research/ Domain

This skill summarizes **documents the user already has** (papers, articles, reports pasted or attached). It performs no web search and needs no MCP server. It is NOT:

- `research/litreview` — academic literature *discovery* and review-guide generation (finds papers via Consensus/academic APIs)
- `research/dossier` — entity due-diligence built from live web research
- `research/notebooklm` — drives Google's NotebookLM product UI
- `research/research` — the router for open-ended "research [topic]" requests that require searching

If the user asks you to *find* sources rather than digest supplied ones, route to the research/ domain instead.

---

## When This Skill Activates

Recognize these patterns from the user:

- "Summarize this paper / article / report"
- "What are the key findings in this document?"
- "Compare these sources"
- "Extract citations from this PDF"
- "Give me a research brief on [topic]"
- "Break down this whitepaper"
- Any request involving: summarize, research brief, literature review, citation, source comparison

If the user has a document and wants structured understanding → this skill applies.

---

## Workflow

When dispatched by the engine, write the brief to the current action's declared outputs (for `deep_research`: `RESEARCH_SUMMARY.md`). Do not invent a different filename or repeat the earlier literature-search step. Source citations and limitations remain required.

### Workflow 1 — Single Source Summary

1. **Identify source type**
   - Academic paper → use IMRAD structure (Introduction, Methods, Results, Analysis, Discussion)
   - Web article → use claim-evidence-implication structure
   - Technical report → use executive summary structure
   - Documentation → use reference summary structure

2. **Scaffold the brief** — 脚本 `scripts/format_summary.py` 未随本仓集成；直接按下方内联模板手写脚手架（按 source type 选 academic/article/report/executive 结构），再从源材料填入每一节:
   ```
   Title: [exact title]
   Author(s): [names]
   Date: [publication date]
   Source Type: [paper | article | report | documentation]

   ## Key Thesis
   [1-2 sentences: the central argument or finding]

   ## Key Findings
   1. [Finding with supporting evidence]
   2. [Finding with supporting evidence]
   3. [Finding with supporting evidence]

   ## Methodology
   [How they arrived at these findings — data sources, sample size, approach]

   ## Limitations
   - [What the source doesn't cover or gets wrong]

   ## Actionable Takeaways
   - [What to do with this information]

   ## Notable Quotes
   > "[Direct quote]" (p. X)
   ```

3. **Assess quality**
   - Source credibility (peer-reviewed, reputable outlet, primary vs secondary)
   - Evidence strength (data-backed, anecdotal, theoretical)
   - Recency (when published, still relevant?)
   - Bias indicators (funding source, author affiliation, methodology gaps)

### Workflow 2 — Multi-Source Comparison

1. **Collect sources** (2-5 documents)
2. **Summarize each** using the single-source workflow above
3. **Build comparison matrix**

   ```
   | Dimension        | Source A        | Source B        | Source C        |
   |------------------|-----------------|-----------------|-----------------|
   | Central Thesis   | ...             | ...             | ...             |
   | Methodology      | ...             | ...             | ...             |
   | Key Finding      | ...             | ...             | ...             |
   | Sample/Scope     | ...             | ...             | ...             |
   | Credibility      | High/Med/Low    | High/Med/Low    | High/Med/Low    |
   ```

4. **Synthesize**
   - Where do sources agree? (convergent findings = stronger signal)
   - Where do they disagree? (divergent findings = needs investigation)
   - What gaps exist across all sources?
   - What's the weight of evidence for each position?

5. **Produce synthesis brief**
   ```
   ## Consensus Findings
   [What most sources agree on]

   ## Contested Points
   [Where sources disagree, with strongest evidence for each side]

   ## Gaps
   [What none of the sources address]

   ## Recommendation
   [Based on weight of evidence, what should the reader believe/do?]
   ```

### Workflow 3 — Citation Extraction

1. **Run the extractor** — 脚本 `scripts/extract_citations.py` 未随本仓集成；人工按 DOI / URL / author-year / numbered 四类模式逐条识别引用并去重
2. **Review and format** the extracted list in the requested style (APA 7 default); manually catch citations the regex missed
3. **Classify citations** by type:
   - Primary sources (original research, data)
   - Secondary sources (reviews, meta-analyses, commentary)
   - Tertiary sources (textbooks, encyclopedias)
4. **Output** sorted bibliography with classification tags

Supported citation formats:
- **APA 7** (default) — social sciences, business
- **IEEE** — engineering, computer science
- **Chicago** — humanities, history
- **Harvard** — general academic
- **MLA 9** — arts, humanities

---

## Tooling

> **脚本未随本仓集成（2026-11-16）：** 下列 `scripts/extract_citations.py`、`scripts/format_summary.py` 均未随仓（已入 asset_gap_register.json）；usage 块仅作上游接口参考，实际按上文人工流程执行。

### `scripts/extract_citations.py`

CLI utility for extracting and formatting citations from text.

**Features:**
- Regex-based citation detection (DOI, URL, author-year, numbered references)
- Multiple output formats (APA, IEEE, Chicago, Harvard, MLA)
- JSON export for integration with reference managers
- Deduplication of repeated citations

**Usage:**
```bash
# Extract citations from a file (APA format, default)
python3 scripts/extract_citations.py document.txt

# Specify format
python3 scripts/extract_citations.py document.txt --format ieee

# JSON output
python3 scripts/extract_citations.py document.txt --format apa --output json

# From stdin
cat paper.txt | python3 scripts/extract_citations.py --stdin
```

### `scripts/format_summary.py`

CLI utility that emits **blank structured summary scaffolds** — you (the model) fill them in from the source. It does not analyze content itself.

**Features:**
- 6 templates: academic, article, report, executive, comparison, literature
- Configurable scaffold depth (brief, standard, detailed)
- Text and JSON output for downstream tooling

**Usage:**
```bash
# Generate structured summary template
python3 scripts/format_summary.py --template academic

# Brief executive summary format
python3 scripts/format_summary.py --template executive --length brief

# All templates listed
python3 scripts/format_summary.py --list-templates

# JSON output
python3 scripts/format_summary.py --template article --output json
```

---

## Quality Assessment Framework

Rate every source on four dimensions:

| Dimension | High | Medium | Low |
|-----------|------|--------|-----|
| **Credibility** | Peer-reviewed, established author | Reputable outlet, known author | Blog, unknown author, no review |
| **Evidence** | Large sample, rigorous method | Moderate data, sound approach | Anecdotal, no data, opinion |
| **Recency** | Published within 2 years | 2-5 years old | 5+ years, may be outdated |
| **Objectivity** | No conflicts, balanced view | Minor affiliations disclosed | Funded by interested party, one-sided |

**Overall Rating:**
- 4 Highs = Strong source — cite with confidence
- 2+ Mediums = Adequate source — cite with caveats
- 2+ Lows = Weak source — verify independently before citing

---

## Summary Templates

See `references/summary-templates.md` for:
- Academic paper summary template (IMRAD)
- Web article summary template (claim-evidence-implication)
- Technical report template (executive summary)
- Comparative analysis template (matrix + synthesis)
- Literature review template (thematic organization)

See `references/citation-formats.md` for:
- APA 7 formatting rules and examples
- IEEE formatting rules and examples
- Chicago, Harvard, MLA quick reference

---

## Proactive Triggers

Flag these without being asked:

- **Source has no date** → Note it. Undated sources lose credibility points.
- **Source contradicts other sources** → Highlight the contradiction explicitly. Don't paper over disagreements.
- **Source is behind a paywall** → Note limited access. Suggest alternatives if known.
- **User provides only one source for a compare** → Ask for at least one more. Comparison needs 2+.
- **Citations are incomplete** → Flag missing fields (year, author, title). Don't invent metadata.
- **Source is 5+ years old in a fast-moving field** → Warn about potential obsolescence.

---

上游参考：https://github.com/alirezarezvani/claude-skills（本仓以 `skills/` 原地使用，不提供任何宿主安装步骤；上游的多工具转换与包管理器安装不适用于本仓）。

---

## Verification Loop

Before delivering any brief, check:

1. Every Key Finding cites a location in the source (section, page, or quote) — no unanchored claims.
2. Citation count check — 脚本 `scripts/extract_citations.py` 未随仓时人工核对：输出参考文献条数与正文提取到的引用条数一致（发现缺口即排查）。
3. Each source carries a 4-dimension quality rating (table above); weak sources are flagged, not silently included.
4. For comparisons: the matrix has one row per dimension and one column per source — no source skipped.
5. Nothing was invented: missing metadata is marked "not stated", never filled in.

---

## Related Skills

- **meta-entity-dossier** — Entity due-diligence from live web research. Complementary — use research-summarizer for digesting documents already in hand, meta-entity-dossier for building entity background from live sources.
- **meta-topic-pulse** — Multi-source recency research. Complementary — use research-summarizer to condense sources you already have, meta-topic-pulse to gather what's currently being said.
- **citation-check** — Citation compliance checking. Complementary — research-summarizer extracts and formats citations, citation-check verifies them against the source list.
