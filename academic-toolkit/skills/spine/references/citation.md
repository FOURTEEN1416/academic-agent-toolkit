# Citation Stage

This file is the canonical stage playbook for the paper-spine orchestrator.

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

- Generate at least `citation_target_count * 3` candidates (default: 60).
- About 80% should be recent (2023 or later in 2026).
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
3. **Curation:** Keep only rows that are usable for drafting. Do not proceed to
   planning/drafting while external-source rows still have blank or placeholder
   verification fields.

## Scripts

```bash
python scripts/citation_bank_check.py paper_rewriting_output/citation_support_bank.md --target-count 20 --markdown
python scripts/citation_quality_audit.py paper_rewriting_output --write
python scripts/citation_verification_en.py paper_rewriting_output/citation_support_bank.md --markdown --write
```
