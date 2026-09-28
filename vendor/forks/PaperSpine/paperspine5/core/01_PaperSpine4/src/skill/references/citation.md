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

| Candidate ID | Source ID | Claim Use ID | Reference/BibTeX | Year | Recency | Supports Section | Support Claim Sentence | Why This Paper Fits | Source | Source Channel | Verified | Verification Note |
|---|---|---|---|---|---|---|---|---|---|---|---|---|

## Literature Contracts

Resolve `literature_scope` before collection:

- `open_literature`: use when the task permits literature discovery or needs a
  new SOTA/field map. Build a broad candidate pool; `target * 3` is a discovery
  default and recency is an important coverage signal.
- `closed_corpus`: use for evidence-bounded rewrites that may cite only supplied
  materials. Deduplicate and exhaust the available bibliography. Require at
  least the planned final citation target when available; if the corpus is
  smaller, add `CLOSED_CORPUS_EXHAUSTIVE` and report the actual total. Do not
  block writing merely because the fixed corpus is old or smaller than 3x.

`auto` resolves a `rewrite_existing` task with `specified_paths` or an explicit
local-only/no-network requirement to `closed_corpus`; otherwise it resolves to
`open_literature`.

## Shared Rules

- `Source ID` identifies the paper; `Claim Use ID` identifies one manuscript
  use. A source may support multiple claims, but it contributes only once to
  source-coverage, recency, and diversity quotas.
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
3. **Coverage check:** distinguish `unique_source_count` from
   `claim_use_count`. In open-literature mode, an unfillable target is
   `SOURCE_COVERAGE_BLOCKED`. In closed-corpus mode, record
   `CLOSED_CORPUS_EXHAUSTIVE`, actual coverage, and any recency limitation;
   never duplicate use rows to pad either mode.
4. **Curation:** Keep only rows that are usable for drafting. Do not proceed to
   planning/drafting while external-source rows still have blank or placeholder
   verification fields.

## Scripts

```bash
python scripts/citation_bank_check.py paper_rewriting_output/citation_support_bank.md --target-count 20 --scope open_literature --markdown
python scripts/citation_bank_check.py paper_rewriting_output/citation_support_bank.md --target-count 20 --scope closed_corpus --markdown
python scripts/citation_quality_audit.py paper_rewriting_output --write
python scripts/citation_verification_en.py paper_rewriting_output/citation_support_bank.md --markdown --write
```
