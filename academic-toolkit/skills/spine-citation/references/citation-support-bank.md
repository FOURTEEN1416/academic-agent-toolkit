# Citation Support Bank

`citation_support_bank.md` is separate from exemplar learning. Exemplar papers
teach writing structure and target-scene rhetoric. Citation-support papers
support concrete literature statements in the user's Introduction, Related Work,
Discussion, limitations, applications, and background.

## Scope-Aware Counts

- `citation_target_count` defaults to `20`; generate at least
  `citation_target_count * 3` candidate rows before final selection (default
  pool `60`). Treat this as a baseline, not a completion proof: expand the
  deduplicated pool whenever a concrete coverage gap remains (closest work,
  methods, alternatives, or a claim with no anchor).
- Recency is a property of the field, not a universal quota. Prefer recent work
  where recency matters (`recent_threshold = current_year - 3` is a simple
  default) and retain relevant foundational or longitudinal evidence regardless
  of age. Explain material coverage gaps instead of padding rows to hit a
  percentage.
- When the user supplies a closed bibliography corpus, enumerate and deduplicate
  it; record when the corpus is exhausted instead of inventing sources.

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

Use this Markdown table (11 columns). The last three columns — `Source Channel`,
`Verified`, and `Verification Note` — are what let `citation_quality_audit.py`
and `artifact_check.py` accept non-DOI sources without inflating their score:

| Candidate ID | Reference/BibTeX | Year | Recency | Supports Section | Support Claim Sentence | Why This Paper Fits | Source | Source Channel | Verified | Verification Note |
|---|---|---|---|---|---|---|---|---|---|---|
| C001 | Vaswani et al. "Attention Is All You Need." arXiv:1706.03762 | 2017 | foundational | Related Work | Prior work established self-attention as a replacement for recurrence. | Foundational transformer paper the method builds on. | arXiv | arxiv | yes | Confirmed via arXiv abstract page; arXiv:1706.03762 title matches. |

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
- Mark uncertain sources as `[VERIFY]` (or `pending`) with the unresolved point
  stated; never let them support a final claim until verified. Final adopted
  external-source rows must record a stable identifier and the actual
  identity and claim-support checks.
- Deduplicate candidates by DOI, PMID, arXiv ID, BibTeX key, URL, or normalized
  citation; multiple claim uses of one source count once for coverage, recency,
  and diversity. Never clone rows.
- During drafting, select only the subset needed for coherent Introduction and
  Discussion paragraphs. Do not dump all candidates into the final paper.

## Output Location

Write:

```text
paper_rewriting_output/citation_support_bank.md
```

The bank is required before final writing in both `rewrite_existing` and
`build_from_materials`. Before any citation is used, establish its identity and
what it supports; already-verified bibliographic notes may feed the bank, but
they do not replace reconciling the final cited entries with the saved target.
