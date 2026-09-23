# Evidence-based quality checks and bounded repair

Use the current step's authorized artifacts and active source tree. Stale drafts,
unused figures, comments and illustrative code do not describe the final paper.
This contract takes precedence over legacy size, sentence-count and repeated-check
examples. Do not reinterpret a stylistic preference as mathematical evidence.

## Three outcomes

- **Verified failure**: a missing/corrupt required artifact, a concrete data contradiction,
  an unsatisfied capability with runtime evidence, a real missing glyph or substantial
  overflow, an abstract on multiple pages, a forbidden TOC, or a stale final PDF snapshot.
  Report the file/location, expected condition and observation; fix only that scope.
- **Needs evidence / advisory**: algorithm keywords not found, a derived number absent
  from raw JSON, an unknown static expression, unusually many/few formulas, prose style,
  short captions, compact layouts, or an unlogged reference. Investigate during the
  existing relevant review. Do not call it proven correct, fabricated, or a hard failure
  solely from these proxies. Keep uncertainty explicit; do not alter correct results.
- **Check unavailable**: missing dependency, parser crash, timeout, network restriction.
  Preserve the artifact and diagnostic. Restore the checking environment, not the paper.
  Do not independently repeat a paid generation call for this condition.

## Semantic review and freshness

A textual DATA_CHECK_PASSED / MODELING_OK / METHOD_CHECK marker is not fresh proof.
Review calculations against actual data, including rounding, units and derived formulas.
Write an acknowledgment only after review, then record the current file fingerprint with
the runtime-provided paper_data_check.py --mode pdf|docx|table --workspace . --record-review.
Never write a receipt manually. Unchanged verified snapshots can reuse the review;
changes to the relevant source, data or checker invalidate it. Legacy markers receive
one focused confirmation, not repeated full-stage regeneration. Missing provenance
requires explanation or verification, not deleting genuine derived results.

## Stage ownership

Modeling: mathematical meaning, assumptions, variables and per-question capabilities.
Code: actual implementation, reproducibility, feasibility and result evidence.
Figures: generated artifact readability, contrast, bounds and relevant data.
Writing: chapter content and lightweight source checks; no repeated full compilation.
Final compilation/export: final pages, fonts, missing glyphs, image readability,
abstract/TOC and file-bound report. After any late repair, recheck the final artifacts.

The same ownership applies to collaborative and automatic full steps. A focused
request keeps its authorized scope; it must not trigger an unrelated whole-stage run.
Do not recreate facts/capability/figure checks inside a writing session. Read existing
verified evidence; if it exposes a real upstream defect, report it with its scope.

## Receipts and bounded validation

- Structured task_notification.status and task_updated.patch.status are terminal
  receipts. A model result is the end of a turn, not proof that background work or
  product checks passed. A task that failed and was genuinely repaired is different
  from a task whose outcome is still unknown. Never invent a receipt from prose.
- Use existing validation scripts, not a new giant all-number/all-code audit for
  every run. Follow the current checklist. Distinguish rounded displays, exact
  calculations, units, derived quantities and extreme floating-point values.
- A short main.tex that includes complete chapters is valid. Source-file count,
  byte count, assumption count, paragraph length and formula count alone are not
  grounds to pad or rewrite. Check active included content and actual capabilities.
- A figure/table may be explained before, after, or in a referenced discussion;
  related figures may share an explanation. Do not force 120 characters between
  every pair. Missing substantive interpretation is reviewed in context.
- Keep detailed failed/unavailable check results when updating a final PDF snapshot.
  Hash/page-count consistency alone never means the paper passed all checks.
- On check unavailable, preserve files and stop paid content repair. Restore the
  checker or dependency and rerun only the affected check. Do not suppress the
  diagnostic or mark an unverified required check as passed.

Batch related corrections. Do not run the same checker twice on unchanged files in one
review round. Use the workflow's existing bounded retry budget; an unchanged failure
after a focused repair needs a clear diagnostic, not an independent infinite loop.
