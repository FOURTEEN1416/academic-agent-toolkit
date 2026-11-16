# Results-as-Validation

Results should explain what the evidence answers. A contribution may be tested
and supported or honestly fail; descriptive findings, sample availability and
negative results can also earn space without becoming new contribution claims.
Connect the actual result to its scientific purpose and interpretation boundary
in the manuscript or existing planning notes before making a stronger claim.

## The Core Rule

Each major Results subsection must have a clear scientific purpose linked to the study question: testing a contribution, reporting a descriptive or negative finding, documenting validation, or explaining sample and measurement availability. Map that purpose to actual evidence and an interpretation boundary. A table checker can flag missing cells but cannot determine the subsection's scientific validity.

This mapping makes the relationship between the paper's claims and results explicit. For every substantive contribution, identify its supporting evidence or state that it remains untested; do not describe a claim as proved merely because a table row exists.

## Apply this directly to the current manuscript

For each major Results unit, identify its question/purpose, actual evidence and
locator, relevant conditions, strongest supported interpretation and important
limits. Check these against the corresponding title, abstract, introduction and
discussion claims. A numerical improvement alone does not identify its causal
source; conditions and controls determine what is supported. Keep useful negative
findings and denominators even when they do not confirm the proposed contribution.

For gated or selective methods, explain scoring, admission, action execution
and subsequent evaluation as distinct stages. Identify the observations
available at each decision and align time indices across equations, diagrams
and prose; distinguish past or smoothed admission scores from later outcomes.
Give each rate's numerator, denominator and conditioning population, and explain
overlap or priority if categories are presented as a partition. Use faithful
reaggregation and plotting of existing data/results to clarify these distinctions
within the saved research scope. Keep the same denominator, symbol and event timing
in figure, caption and prose; an admission weight is not an unrelated fallback gate.
When a conditional rate could be mistaken for overall benefit, retain the relevant
available comparator or explicitly limit the claim; not every method caption needs
an extra metric. Correct actual meanings, not just matching words.

Use the current draft, figure notes and existing result sources for this mapping;
do not copy them into another mandatory table. A missing scientific link calls for
better explanation or narrower claims. A missing helper cell/file alone does not
establish that the result or evidence is missing. Apply the column meanings below
as scientific questions, not as a form-completion prerequisite.

## Historical table/checker compatibility

The remaining filenames, C/S/N/M/O/R bindings and planning gate describe a legacy
Runner contract. Use them only when maintaining that actual tool. They do not
require a new table, ledger or permission before current-host drafting.

### Legacy table

Write this Markdown table to `paper_rewriting_output/results_validation.md`:

| Results Unit | Contribution Claim Tested | Result/Evidence | Figure/Table | Confirmatory Condition | Allowed Interpretation | Interpretation NOT Allowed |
|---|---|---|---|---|---|---|
| 4.2 Main accuracy vs. SOTA | C1: our method beats prior SOTA on benchmark X | +3.1 acc over best baseline (88.4 vs 85.3) | Table 2 | Holds only on X's standard split; same backbone, same epochs | Method improves accuracy under matched-budget training on X | Do NOT claim general superiority on unseen domains or larger budgets |
| 4.3 Ablation of module M | C2: module M is the source of the gain | Removing M drops acc 88.4 to 85.9 | Table 3 | Single dataset, single seed-averaged run | M contributes the majority of the C1 gain | Do NOT claim M is necessary for other architectures |
| 4.4 Efficiency | C3: method is cheaper at inference | 1.7x fewer FLOPs at equal accuracy | Fig. 4 | Measured on one GPU, batch=1 | Lower inference cost at matched accuracy | Do NOT claim training-time savings (not measured) |

## Why Each Column Exists

- **Results Unit** — the actual subsection heading/number. Anchors the row to a
  real place in the manuscript so a reviewer (and the check) can confirm the
  subsection exists and earns its space.
- **Contribution or scientific purpose addressed** — identify the claim, study question, descriptive result, validation role or transparency need. An empty mapping requires clarification; it does not establish that the underlying work validates nothing.
- **Result/Evidence** — the concrete number, delta, or qualitative finding that
  settles the claim. WHY: forces you to name the evidence, not gesture at it.
  Empty here means there is no result behind the subsection — a hard failure.
- **Evidence locator** — identify the actual figure, table, result passage, source observation or derivation. The reader must be able to trace the claim; not every valid result requires a separate figure or table.
- **Confirmatory Condition** — the exact regime under which the result holds
  (which split, budget, seed count, hardware). WHY: a result is only evidence
  *within its conditions*; stating them is what stops over-generalization.
- **Allowed Interpretation** — the strongest honest reading the evidence
  supports. WHY: writes the claim sentence you are licensed to make.
- **Interpretation NOT Allowed** — the tempting overclaim this row does **not**
  license. WHY: pre-commits you to the boundary so the Discussion cannot quietly
  inflate the result. Reviewers reward papers that police their own scope.

## How To Build It

1. Derive C1, C2, … from the user-confirmed Core contribution, its evidence
   requirements, and claim boundary in `confirmed_contribution.md`.
2. For each contribution, find or design the Results subsection that tests it.
   Every contribution needs at least one row.
3. Before writing each major Results subsection, identify its contribution, study-question or transparency role. Retain useful descriptive context, negative findings, denominators, missingness and limitations. Remove content only when it has no relevant scientific purpose, and add a new contribution claim only when the evidence supports it.
4. Fill the confirmatory condition and both interpretation columns. Leaving the
   interpretation columns empty is a warning, not a failure — but an empty
   `Interpretation NOT Allowed` is the single most common cause of reviewer
   "overclaiming" complaints, so fill it.

## Failure Modes The Check Catches

- **Metric-only row** — a number with an empty `Contribution Claim Tested`. The
  classic "we report accuracy because we can" row. Hard fail.
- **Empty evidence** — a claim with no `Result/Evidence`. A promise with nothing
  behind it. Hard fail.
- **Missing file or no data rows** — the mapping is not established in this file. Inspect existing manuscript notes and actual results before deciding whether mapping or underlying scientific work is missing.
- **Empty interpretation columns** — warning only, but fix before submission.

## Output Location

```text
paper_rewriting_output/results_validation.md
```

Required by the planning gate for journal, conference, and competition scenes.
Each row's evidence must also resolve through `scientific_evidence_ledger.json`
to explicit S/C/N/M/O/R records; this table explains the contribution logic,
while the ledger preserves scientific granularity and verification state.
Validate before drafting with:

```text
python src/scripts/results_validation_check.py paper_rewriting_output --markdown --write
```

Exit 0 means the inspected table satisfies this helper's structural checks. It does not prove that all manuscript subsections are covered or that their evidence supports their claims. Exit 1 reports a table-check failure that requires diagnosis, not a verdict that the underlying results are scientifically meaningless.
