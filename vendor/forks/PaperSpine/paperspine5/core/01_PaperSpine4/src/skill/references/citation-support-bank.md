# Citation Support Bank

`citation_support_bank.md` is separate from exemplar learning. Exemplar papers
teach writing structure and target-scene rhetoric. Citation-support papers
support concrete literature statements in the user's Introduction, Related Work,
Discussion, limitations, applications, and background.

## Scope-Aware Counts

- `citation_target_count` defaults to `20`.
- In `open_literature`, generate about `citation_target_count * 3` unique
  bibliographic sources before final selection. The default pool is `60`.
- In `closed_corpus`, enumerate and deduplicate the supplied bibliography. Aim
  to cover the final citation target, but use `CLOSED_CORPUS_EXHAUSTIVE` when the
  complete corpus is smaller. Corpus size and age are disclosures, not reasons
  to fabricate sources or stop an otherwise supportable rewrite.
- For open literature, about 80% of unique sources should be recent. Use:
  `recent_threshold = current_year - 3`; in 2026, papers from 2023 onward are
  recent.

## Paper Types To Search

Include papers from the same field, similar adjacent fields, foundational
methods, datasets/benchmarks, evaluation methodology, and application papers.
Do not restrict the bank to the same narrow method. A good Introduction and
Discussion usually need a mix of:

- direct task/SOTA papers,
- broader field surveys or reviews,
- foundational technique papers,
- benchmark or dataset papers,
- application or domain-impact papers,
- limitation, robustness, reproducibility, or ethics papers where relevant.

## Required Table

Use this Markdown table. `Source ID` is the bibliographic identity; `Claim Use
ID` is one place the source supports. The last three columns — `Source Channel`,
`Verified`, and `Verification Note` — are what let `citation_quality_audit.py`
and `artifact_check.py` accept non-DOI sources without inflating their score:

| Candidate ID | Source ID | Claim Use ID | Reference/BibTeX | Year | Recency | Supports Section | Support Claim Sentence | Why This Paper Fits | Source | Source Channel | Verified | Verification Note |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C001 | S001 | U001 | Vaswani et al. "Attention Is All You Need." arXiv:1706.03762 | 2017 | foundational | Related Work | Prior work established self-attention as a replacement for recurrence. | Foundational transformer paper the method builds on. | arXiv | arxiv | yes | Confirmed via arXiv abstract page; arXiv:1706.03762 title matches. |

Rules:

- Each row must contain one reference format: BibTeX, DOI, URL, arXiv ID, or
  enough bibliographic metadata for the user to verify.
- Each row must include one or two manuscript-ready support sentences. Example:
  `Prior work has shown that ...`, `Recent studies in ... motivate ...`, or
  `This supports the Discussion claim that ...`.
- The support sentence must not invent a result that is not visible from the
  source metadata, abstract, or user-provided PDF/text.
- Fill `Source Channel` for every row: `MCP-CNKI`, `MCP-IEEE`, `MCP-PubMed`,
  `MCP-Crossref`, `web`, `arxiv`, `publisher`, `local`, or `unknown`.
- For external channels (`web`, `MCP-*`, `Crossref`, `PubMed`, `Scholar`,
  `Semantic Scholar`, `IEEE`, `CNKI`, `WOS`, `arxiv`, `publisher`), do not leave
  verification blank: `Verified` must be `yes`, `verified`, `pass`, or `true`,
  and `Verification Note` must record a **stable identifier** (DOI, arXiv ID, or
  URL) plus how it was checked. A `Verified=yes` flag with no identifier is
  treated as self-attestation only and will not reach `verified` status.
- Mark uncertain sources as `[VERIFY]` and do not use them in final writing
  until verified. Do not use `[VERIFY]`, `TODO`, `TBD`, `pending`, or empty
  verification values for external-source rows.
- During drafting, select only the subset needed for coherent Introduction and
  Discussion paragraphs. Do not dump all candidates into the final paper.
- Deduplicate by DOI, PMID, arXiv ID, BibTeX key, URL, or normalized citation.
  Multiple claim uses count once for source coverage, recency, and diversity.
  In open-literature mode, record `SOURCE_COVERAGE_BLOCKED` if retrieval cannot
  meet the target. In closed-corpus mode, record `CLOSED_CORPUS_EXHAUSTIVE` and
  the actual source count. Never clone rows.

## Output Location

Write:

```text
paper_rewriting_output/citation_support_bank.md
```

The bank is required before final writing in both `rewrite_existing` and
`build_from_materials`.
