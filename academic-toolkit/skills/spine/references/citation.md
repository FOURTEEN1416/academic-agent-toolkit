# Citation Stage

This file is the canonical stage playbook for the paper-spine orchestrator.

## Literature Scope Contract

A rewrite workflow, a local material path, or a materials-only research scope
does not by itself close public literature; only an explicit user restriction
does. When the user explicitly restricts usable literature to supplied sources,
treat the task as a closed corpus: deduplicate and exhaust the supplied
bibliography, and record that the corpus is exhausted instead of inventing
sources. Otherwise collect from open literature to cover the actual claims.

## Purpose

Build a verified citation support bank that can support literature statements
in the user's manuscript. This is separate from exemplar learning.

## Literature Retrieval Priority Protocol

1. **Literature MCP tools (preferred).** If the host has MCP servers, use them
   first. Record the source channel per citation: `MCP-CNKI`, `MCP-IEEE`,
   `MCP-PubMed`, `MCP-Crossref`, `web`, `local`, or `unknown`.
2. **Host WebSearch / browsing tools (fallback).** Mark Source Channel as `web`.
3. **Local files.** Mark Source Channel as `local`.
4. **MCP is an enhancement, not a dependency.** Build the bank from web/local
   sources when no MCP is available.

## Required Output

`paper_rewriting_output/citation_support_bank.md` with this table:

| Candidate ID | Reference/BibTeX | Year | Recency | Supports Section | Support Claim Sentence | Why This Paper Fits | Source | Source Channel | Verified | Verification Note |
|---|---|---|---|---|---|---|---|---|---|---|

## Rules

- Generate at least `citation_target_count * 3` candidates (default: 60) as a
  baseline pool; expand it whenever a concrete coverage gap remains. The saved
  target is not an age quota: prefer recent work where recency matters
  (`current_year - 3` is a simple threshold) and retain relevant foundational
  evidence regardless of age. Explain material coverage gaps instead of padding.
- One source may support several claims, but it counts once toward coverage,
  recency, and diversity. Deduplicate by DOI, arXiv ID, BibTeX key, URL, or
  normalized citation; never clone rows.
- Each row pairs one paper with one or two support sentences.
- Fill `Source Channel` for every row: `MCP-CNKI`, `MCP-IEEE`, `web`, `local`, `unknown`.
- For external channels (`web`, `MCP-*`, `Crossref`, `PubMed`, `Scholar`,
  `Semantic Scholar`, `IEEE`, `CNKI`, `WOS`), do not leave verification blank:
  `Verified` must be `yes`, `verified`, `pass`, or `true`, and
  `Verification Note` must state how the item was checked (DOI match, title
  match, Crossref/PubMed page, publisher page, database record, or local PDF
  metadata).
- If external verification cannot be completed, keep the row out of the usable
  candidate bank or mark `Source Channel` as `unknown` and return to the
  retrieval/verification step before drafting.
- For local-only rows, use `Source Channel=local`; `Verified` may be blank, but
  add a note when the local file has DOI/title metadata.
- Do not use `[VERIFY]`, `TODO`, `TBD`, `pending`, or empty verification values
  for external-source rows. `artifact_check.py` treats those as FAIL.
- The bank is a candidate pool; final writing selects a coherent subset.

## Flow

1. **Collection pass:** Build the initial pool with `Source Channel` filled for
   every row.
2. **Verification pass:** Verify every external-source row and fill `Verified`
   plus `Verification Note`. Run `citation_quality_audit.py` and
   `citation_verification_en.py` where applicable.
3. **Coverage check:** distinguish distinct sources from claim uses. Resolve a
   final-target shortfall by finding and integrating relevant, verified support;
   do not silently reduce the requested coverage. If an explicit corpus
   restriction or venue rule prevents it, report the conflict and the actual
   coverage.
4. **Curation:** Keep only rows that are usable for drafting. Do not proceed to
   planning/drafting while external-source rows still have blank or placeholder
   verification fields.

## Scripts

```bash
python scripts/citation_bank_check.py paper_rewriting_output/citation_support_bank.md --target-count 20 --markdown
python scripts/citation_quality_audit.py paper_rewriting_output --write
python scripts/citation_verification_en.py paper_rewriting_output/citation_support_bank.md --markdown --write
```

## Candidate-Bank Diagnostics

Resolve the target from the saved `citation_target_count` (or a counted
target-venue sample when available) and compare it with the distinct entries
actually cited in the current manuscript — not with the bank size, the number
of use rows, or uncited BibTeX entries. A bank check does not perform this
final comparison. If the manuscript falls short, locate useful missing
literature and integrate the supported points; report a genuine scope/venue
conflict rather than treating a diagnostic PASS as meeting the preference.
