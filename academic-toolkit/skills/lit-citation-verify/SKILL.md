---
name: lit-citation-verify
description: "Citation-verification principles and canonical sources. Use when asked how to verify references (guidance, not batch checking)."
tags: [Research, Academic, Citation, Reference]
version: 0.1.0
---

# Citation Verification Reference Guide

A reference guide for citation verification in academic paper writing, providing verification principles and best practices.

**Core Principle**: Proactively verify every citation during the writing process using programmatic or canonical scholarly sources first: arXiv, DOI/CrossRef, Semantic Scholar, publisher landing pages, and Zotero metadata. Google Scholar is useful for manual discovery, but it is not the canonical verification authority.

## Citation-Verification Family Guide (this repository)

Six citation-verification skills coexist in this repo. Use this guide to pick the right one:

| Skill | Use it for |
|---|---|
| `lit-citation-verify` (this skill) | Verification **principles** and canonical-source order; guidance, not batch checking |
| `lit-citation-verify-latex` | **Batch existence checking** of LaTeX `.tex` + `.bib` references (bibsleuth) |
| `check-citations` | `.bib` **multi-source verification** (CrossRef / Semantic Scholar / OpenAlex) for AI-hallucinated citations |
| `citation-crosscheck` | **Double-blind field-level diff** of `.bib` entries against independently re-fetched records (author order / year / venue / DOI), with a deterministic verifier gate and a side-by-side xlsx; no context-fit |
| `citation-check` | CUMCM（国赛）**GB/T 7714 格式与完整性**检查，面向中文竞赛论文 |
| `paper-citation-verify` | **Pre-submission citation completeness** checklist before journal/conference submission |

Routing hint: 原则/口径 → 本技能；LaTeX 批量核验 → `lit-citation-verify-latex`；`.bib` 三源分诊 → `check-citations`；字段级双盲核对（存疑条目/投稿终检） → `citation-crosscheck`；国赛 GB/T 终检 → `citation-check`；投稿前清单 → `paper-citation-verify`。

## Core Problems

Citation issues in academic papers seriously impact research integrity:

1. **Fake citations** - Citing non-existent papers (common issue with AI-generated citations)
2. **Incorrect information** - Mismatched authors, titles, years, etc.
3. **Inconsistent formatting** - Mixed citation formats
4. **Missing citations** - Referenced but uncited work

These issues can lead to:
- Paper rejection or retraction
- Damage to academic reputation
- Reviewers questioning research rigor

**Special risk with AI-assisted writing**: AI-generated citations have a high error rate (a ~40% figure is often quoted without a verifiable source — treat it as a caution, not a measured statistic); every citation must be verified against canonical scholarly sources (DOI / arXiv / CrossRef / Semantic Scholar / publisher / Zotero).

## Verification Principles

This skill provides verification principles based on canonical scholarly metadata and claim-level checking:

### 1. Proactive Verification (Verify During Writing)

**Core idea**: Verify immediately when adding a citation, rather than checking after writing is complete.

- Resolve a canonical identifier first each time a citation is needed: DOI, arXiv ID, publisher page, or a verified Zotero item
- Confirm the paper's metadata against CrossRef / arXiv / Semantic Scholar / publisher metadata
- Use WebSearch or Google Scholar only as a fallback for manual discovery when canonical lookup fails
- Add to bibliography only after verification passes

### 2. Canonical Metadata Verification

Preferred authority order:
1. DOI / publisher landing page
2. arXiv ID or arXiv landing page
3. CrossRef
4. Semantic Scholar
5. Zotero metadata imported from a verified identifier
6. Google Scholar only for manual discovery or fallback lookup

**Verification steps**:
1. Find a DOI, arXiv ID, publisher URL, or verified Zotero item.
2. Confirm title, first author, year, venue, and identifier.
3. Fetch BibTeX from CrossRef, arXiv, publisher metadata, Zotero, or another programmatic source when possible.
4. If only Google Scholar can find the item, mark it as manual verification and do not treat the BibTeX as final until metadata is checked elsewhere.

### 3. Information Matching Verification

**Information that must match**:
- Title (minor differences allowed, e.g., capitalization)
- Authors (at least the first author must match)
- Year (±1 year difference allowed, considering preprints)
- Publication venue (conference/journal name)

### 4. Claim Verification

**Key principle**: When citing a specific claim, you must confirm the claim actually appears in the paper.

- Use WebSearch to access the paper PDF
- Search for relevant keywords
- Confirm the accuracy of the claim
- Record the section/page where the claim appears

## Verification Workflow

### Integration into Writing Process

```
Need a citation during writing
    ↓
Find DOI / arXiv ID / publisher page / verified Zotero item
    ↓
Verify metadata with CrossRef / arXiv / Semantic Scholar / publisher / Zotero
    ↓
Confirm paper details
    ↓
Get BibTeX
    ↓
(If citing a specific claim) Verify the claim
    ↓
Add to bibliography
```

**Key point**: Verification is part of the writing process, not a separate post-processing step.

## Usage Guide

### How to use this skill

This is a principles reference, not an automated pipeline: there is **no auto-trigger** in this repository. Apply these principles manually inside this repository's paper-writing and citation-management workflows.

**Manual reference**: Refer to this skill when you need detailed verification principles; for batch checking, route to the sibling skills listed in the family guide below.

### Verification Step Example

**Scenario**: Need to cite the Transformer paper

```
Step 1: Canonical lookup
Query: arXiv ID 1706.03762 (or DOI 10.48550/arXiv.1706.03762)
Result: ✅ "Attention is All You Need", arXiv preprint 2017, published at NeurIPS 2017

Step 2: Metadata confirmation (CrossRef / arXiv / Semantic Scholar / publisher)
- Title: "Attention is All You Need"
- Authors: Vaswani, Ashish; Shazeer, Noam; Parmar, Niki; ...
- Year: 2017
- Venue: NeurIPS (NIPS)

Step 3: Get BibTeX programmatically
- Fetch from arXiv / CrossRef / publisher metadata / verified Zotero item

Step 4: Add to bibliography
- Paste into .bib file
- Use \cite{vaswani2017attention} in the paper

Fallback (only if no canonical source resolves the item):
- Use WebSearch / Google Scholar for manual discovery
- Mark the entry as manually verified; do NOT treat its BibTeX as final
  until the metadata is checked against a canonical source
```

### Handling Verification Failures

**If the paper cannot be verified through canonical sources**:

1. **Check spelling** - Is the title or author name correct?
2. **Try different queries** - Use different keyword combinations
3. **Find alternative sources** - Try arXiv, DOI, CrossRef, Semantic Scholar, publisher pages, or Zotero
4. **Mark as pending** - Use `[CITATION NEEDED]` marker
5. **Notify the user** - Clearly state the citation cannot be verified

**If information doesn't match**:

1. **Confirm the source** - Did you find the correct paper?
2. **Check versions** - Preprint vs. published version
3. **Update information** - Use the most accurate version
4. **Record discrepancies** - Note the reason for differences

## Best Practices

### Preventing Fake Citations

1. **Never generate citations from memory** - AI-generated citations have a high error rate
2. **Resolve canonical identifiers first** - DOI / arXiv / CrossRef / Semantic Scholar / publisher / Zotero
3. **Use WebSearch / Google Scholar only as fallback** - for manual discovery when canonical lookup fails
4. **Verify promptly** - Verify when adding citations, don't wait until finished

### Handling Verification Failures

1. **Don't guess** - If you can't find the paper, don't fabricate information
2. **Mark clearly** - Use `[CITATION NEEDED]` to mark explicitly
3. **Notify the user** - Clearly state which citations cannot be verified
4. **Provide reasons** - Explain why verification failed (not found, info mismatch, etc.)

### Improving Verification Accuracy

1. **Complete queries** - Include title, author, year
2. **Check citation count** - Citation count is a weak auxiliary credibility signal (e.g., from Google Scholar); never treat it as verification itself
3. **Confirm venue** - Verify conference/journal name is correct
4. **Verify claims** - When citing specific claims, confirm they exist in the paper

### Common Pitfalls

❌ **Wrong approach**:
- Generating BibTeX from memory
- Skipping canonical-source verification
- Assuming a paper exists
- Not marking unverifiable citations

✅ **Correct approach**:
- Resolve a canonical identifier (DOI / arXiv / CrossRef / Semantic Scholar / publisher / Zotero) for every citation
- Confirm metadata matches before adding
- Fetch BibTeX from programmatic sources; treat Google Scholar BibTeX as unverified until checked elsewhere
- Clearly mark unverifiable citations

## Claim-Stance Verification (supported / mentioned / contrasted)

Existence + metadata checks are necessary but not sufficient for load-bearing citations. For every key citation (one that supports a core claim of your paper), additionally ask: **do later studies support, merely mention, or contradict it?**

- **supported** — later work reproduces or explicitly backs the cited conclusion
- **mentioned** — cited as background only; no supporting or contradicting evidence in the citing context
- **contrasted** — later work reports opposite results or documents a limitation of the cited claim

### Without Scite credentials (default in this repo — manual verification guide)

1. For each key citation, find citing papers via WebSearch / Google Scholar / OpenAlex (`cited_by` / citing-works lookup).
2. Read the **citing sentence**, not the abstract: look for "consistent with", "we confirm", "however, X found the opposite", "fails to replicate".
3. Record a `stance` column (supported/mentioned/contrasted) plus the evidence (citing sentence + its DOI) in your literature table.

Worked examples (manual judgements on real papers — verify the citing context yourself before reusing):

| Key citation | Citing work | Stance | Evidence (citing context) |
|---|---|---|---|
| Vaswani et al., 2017, *Attention Is All You Need* (arXiv:1706.03762) | Devlin et al., 2019, *BERT* (arXiv:1810.04805) | **supported** | BERT builds on the Transformer encoder and reports SOTA results, backing the original architecture's effectiveness |
| Vaswani et al., 2017 | Beltagy et al., 2020, *Longformer* (arXiv:2004.05150) | **contrasted** | Documents that vanilla self-attention does not scale to long sequences — a limitation challenge to the original design's applicability |
| Devlin et al., 2019, *BERT* | Liu et al., 2019, *RoBERTa* (arXiv:1907.11692) | **mentioned → supported** | Reuses the BERT architecture unchanged, varies only training recipe, and reports better results — supports the architecture while surpassing the original training setup |

> The table above is a worked example of manual stance verification, not API output. Never fill stance columns from memory; cite the actual sentence you read.

### With a Scite key / MCP (optional enhancement — never a hard dependency)

Scite Citation Statement API (follow Scite's current official docs for the exact contract):

- Tally: `GET https://api.scite.ai/tally/{doi}` → counts of `{supporting, contradicting, mentioning, unclassified}`
- Statements: `GET https://api.scite.ai/statements?doi={doi}` → per-citing-statement records incl. predicate
- Auth: header `Authorization: Bearer <SCITE_API_KEY>` (or inject via your MCP tool config)

```python
# Optional enhancement when a Scite key is configured
import requests

def scite_tally(doi: str, api_key: str | None = None) -> dict:
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    resp = requests.get(f"https://api.scite.ai/tally/{doi}", headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()

# Reading the result:
#   contradicting > 0  -> read the contradicting statements before citing as settled
#   supporting high    -> may phrase as "supported by later work"
#   mostly mentioning  -> do NOT phrase as "extensively validated"
```

- No key / API unreachable → fall back to the manual guide above; **do not fabricate stance data**.

## Summary

**Core Principle**: Proactively verify every citation during the writing process against canonical scholarly sources (DOI / arXiv / CrossRef / Semantic Scholar / publisher / Zotero). WebSearch and Google Scholar are fallbacks for manual discovery only, never the primary verification authority.

**Key Steps**:
1. Resolve a canonical identifier (DOI / arXiv ID / publisher page / verified Zotero item)
2. Confirm metadata against CrossRef / arXiv / Semantic Scholar / publisher
3. Confirm details
4. Get BibTeX from a programmatic source
5. Verify claims (if needed)
6. Add to bibliography

**Failure handling**: When verification fails, mark as `[CITATION NEEDED]` and clearly notify the user.

**Integration**: Apply these principles manually within this repository's paper-writing and citation workflows; see the Citation-Verification Family Guide above for which sibling skill performs batch checking.
