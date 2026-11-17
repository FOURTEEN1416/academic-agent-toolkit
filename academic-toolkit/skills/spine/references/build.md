# Build Stage

This file is the canonical stage playbook for the paper-spine orchestrator.

## Purpose

Build a manuscript from materials when no real draft exists yet. Shares the
same research, motivation, and rationale logic as the rewrite stage.

## Prerequisites

- `paper_spine_config.json`
- `materials_dir`
- Research outputs
- `citation_support_bank.md`
- `confirmed_motivation.md`

Start from this task's saved configuration, confirmed materials, motivation
choice, actual results and literature notes; reuse valid decisions and existing
files. Resolve specific evidence gaps before making dependent claims.

## First Pass

```bash
python scripts/material_inventory.py <materials_dir> --output-dir paper_rewriting_output
```

Create `source_inventory.md` before making claims. When the inventory contains
multiple versions of the same data, figure/table, code, or editable source,
preserve the user's explicit choice; otherwise select the newest candidate only
within the same confirmed scientific identity and declared materials roots, and
resolve uncertain identity before using an asset.

## Humanize Tier

If `humanize_tier` is set to `light`, `medium`, or `heavy`, follow the
`spine-humanize` skill and apply its tier-specific constraints. Verify that
facts, terminology, negation, causality, uncertainty and citation meaning are
unchanged; a clean-text no-op is an acceptable outcome when the draft is
already clear.

## Required Outputs

- `source_inventory.md`, `evidence_bank.md`, `figure_asset_map.md`, `claim_register.md`
- `section_blueprints.md`, `writing_rationale_matrix.md`
- Manuscript draft
- `final_paper/main.tex`, `latex_report.md`, `final_artifact_manifest.md`

## Writing Rationale Matrix

| Row ID | Manuscript Unit | Planned Function | Motivation Link | Reference/SOTA Pattern Learned | Target Scene or Venue Norm | User Evidence or Citation Anchor | Planned Text Move | Final Text Check |
|---|---|---|---|---|---|---|---|---|

Before drafting, read `references/writing-rationale-matrix.md` and apply its
full depth rules. Every non-trivial row must include concrete anchors from
confirmed motivation, SOTA/example pattern, target scene, evidence/citation,
and the planned text move. The first row must justify the whole-work framework.
After drafting, every `Final Text Check` value must start with `PASS` or
`FAIL`; do not write vague notes such as "done" or only a section location.

## Build Rules

- Treat images as potential figure assets.
- Do not fabricate missing experiments or results.
- Quote paths with spaces or non-ASCII chars.
- Use `output_language` from config.
- Select citations sentence by sentence.
- Draft from `section_blueprints.md` / `writing_rationale_matrix.md`, but keep
  their scaffolding internal: the manuscript body must never name supervisors,
  reviewers, review comments, an earlier draft, or narrate that the paper was
  reorganized to address feedback, and must never transcribe an `A -> B -> C`
  planning throughline as prose. `integrity_audit.py` hard-fails this. Judge
  passages by their scientific or transparency function: required AI-use
  disclosures and Methods-level review procedures stay in the manuscript.
- Tie every scientific value and result to its actual source; after an
  authorized analysis change, update those links and the affected claims
  together.
- Cite with `\cite{key}` linked to a bibliography; never type literal `[1]` text.
- Run integrity audit + structured review before LaTeX.
- Before rendering, run the LaTeX guard against the exact source that will be
  compiled; if serialization artifacts (for example doubled leading
  backslashes) appear, repair the source first — never repair the PDF after
  rendering.
- Compile `final_paper/main.tex` with a real LaTeX engine available in the
  environment; a source dump or screenshot is not a manuscript build. The
  resulting PDF must begin with `%PDF`, contain no literal TeX source markers,
  and have readable, complete page images.
- Build final LaTeX under `final_paper/`.
