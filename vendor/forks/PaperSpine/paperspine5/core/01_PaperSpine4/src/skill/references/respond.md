# Review, Revision, and Rebuttal Cycle

Use this mode for editorial decisions, reviewer comments, minor/major revision,
reject-and-resubmit, or follow-up review rounds. Read `publication-cycle.md`
and reuse/refresh the current target profile.

## Output layout

```text
paper_rewriting_output/publication_cycle/revisions/<round-id>/
├── review_round.json
├── rebuttal_check.md
├── reviewer_comments_extracted.md
├── response_matrix.md
├── response_letter.md
├── revision_change_log.md
└── review_round.snapshot.json
```

Target-required revised/marked manuscripts, new figures/tables, supplements,
or forms then enter a new `submission_package_plan.json` and READY bundle.

## Source and atomic-comment contract

1. Preserve the editor/reviewer source files and SHA-256.
2. Classify the decision as `minor_revision`, `major_revision`, or
   `reject_and_resubmit`.
3. Split every editor/reviewer passage into atomic issues. Use `E.C1`, `R1.C1`,
   etc.; use child IDs such as `R1.C1.1` when one original bullet contains
   independent asks. Preserve each atomic quote verbatim and hash it.
4. Show the atomic list to the author when segmentation or intent is ambiguous.
   No issue may disappear inside a summary.

For every issue record:

- issue type and response strategy (`accept`, `clarify`, `defend`,
  `experiment`, `partial`, `cannot_complete`);
- confirmed author position and constraints;
- verified evidence, including new results/analysis when claimed;
- locatable manuscript/figure/table changes and their verification status;
- final reviewer-facing response.

Use an outline-first response: acknowledge only when natural, answer the issue
directly, give evidence or the honest constraint, then point to the exact
revision. Do not invent experiments, data, citations, author promises, or line
numbers. A respectful disagreement is better than a fabricated concession.

## Minor versus major revision

- **Minor revision:** revalidate every PaperSpine readiness dimension and mark
  an actually unaffected dimension `not_affected`. Changed artifacts still need
  real receipts.
- **Major revision / reject-and-resubmit:** scientific identity, Results,
  figures, citations, metadata, and portable artifacts may all have changed.
  Re-run all five dimensions and require `passed`; do not reuse prior final
  receipts. Re-run integrated editorial review and the final publication
  surface check before packaging.

New or changed experiments must return to the evidence ledger, Results
validation, figure story/body contract, citations, and final renders. A response
letter cannot make an unverified experiment real.

## Multi-round chain

`round_number > 1` must bind the previous `review_round.json` path and SHA-256.
Add follow-up comments as new atomic IDs while preserving earlier rounds; do not
rewrite history to make the discussion look cleaner.

## Validate and render

```bash
python scripts/publication_cycle.py rebuttal-check \
  paper_rewriting_output/publication_cycle/revisions/<round-id>/review_round.json \
  --markdown --write

python scripts/publication_cycle.py rebuttal-render \
  paper_rewriting_output/publication_cycle/revisions/<round-id>/review_round.json \
  paper_rewriting_output/publication_cycle/revisions/<round-id>/rendered \
  --markdown
```

The renderer uses only author-approved fields from `review_round.json`; it does
not add rhetoric or promises. Convert the rendered letter to the target's
required Word/PDF/portal format, validate it, and include it in a target-driven
bundle. `respond_check.py` remains a compatibility check for legacy Markdown
packages; `publication_cycle.py rebuttal-check` is authoritative for atomic
coverage, author intent, evidence, multi-round lineage, and revalidation.
