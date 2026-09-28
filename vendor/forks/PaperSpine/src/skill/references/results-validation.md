# Results-as-Validation

A Results section is not a metrics dump. Every major Results subsection exists to
**test a promise the paper made** — a contribution claim from the Abstract or
Introduction — and either confirm it or honestly fail it. If a number appears in
Results but maps to no contribution, the reader cannot tell whether the paper
delivered what it advertised. That gap is exactly where reviewers say "the
experiments do not support the claims."

`results_validation.md` forces the mapping to be explicit *before* you write the
Results prose, so each subsection is born already tied to a claim, an evidence
locus, and a stated limit on interpretation.

## The Core Rule

Each major Results subsection must validate **at least one contribution
promise**. A row that reports a metric with no contribution mapping is a
failure, not a stylistic preference — `results_validation_check.py` rejects any
row whose `Contribution Claim Tested` or `Result/Evidence` cell is empty.

This is the sharpest constraint in the rewrite: it converts "we ran experiments"
into "we proved each thing we claimed." If a contribution has no row, you either
forgot to test it or the claim is unsupported — both must be fixed before the
paper is honest.

## Required Table

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
- **Contribution Claim Tested** — the specific promise (label it C1, C2, … to
  match the Introduction's contribution list). WHY: this is the column that
  turns a metric into validation. Empty here means the experiment validates
  nothing — a hard failure.
- **Result/Evidence** — the concrete number, delta, or qualitative finding that
  settles the claim. WHY: forces you to name the evidence, not gesture at it.
  Empty here means there is no result behind the subsection — a hard failure.
- **Figure/Table** — where the reader sees it (Table 2, Fig. 4). WHY: an
  unanchored claim is unverifiable; every confirmed promise must point at a
  visible artifact.
- **Confirmatory Condition** — the exact regime under which the result holds
  (which split, budget, seed count, hardware). WHY: a result is only evidence
  *within its conditions*; stating them is what stops over-generalization.
- **Allowed Interpretation** — the strongest honest reading the evidence
  supports. WHY: writes the claim sentence you are licensed to make.
- **Interpretation NOT Allowed** — the tempting overclaim this row does **not**
  license. WHY: pre-commits you to the boundary so the Discussion cannot quietly
  inflate the result. Reviewers reward papers that police their own scope.

## How To Build It

1. List every contribution from the Abstract/Introduction (C1, C2, …).
2. For each contribution, find or design the Results subsection that tests it.
   Every contribution needs at least one row.
3. For each major Results subsection, fill the row. If a subsection cannot be
   mapped to any contribution, it is either filler (cut it) or an unannounced
   contribution (add it to the Introduction).
4. Fill the confirmatory condition and both interpretation columns. Leaving the
   interpretation columns empty is a warning, not a failure — but an empty
   `Interpretation NOT Allowed` is the single most common cause of reviewer
   "overclaiming" complaints, so fill it.

## Failure Modes The Check Catches

- **Metric-only row** — a number with an empty `Contribution Claim Tested`. The
  classic "we report accuracy because we can" row. Hard fail.
- **Empty evidence** — a claim with no `Result/Evidence`. A promise with nothing
  behind it. Hard fail.
- **Missing file or no data rows** — the validation step was skipped entirely.
  Hard fail.
- **Empty interpretation columns** — warning only, but fix before submission.

## Output Location

```text
paper_rewriting_output/results_validation.md
```

Required before final writing whenever the paper has a Results/Experiments
section. Validate with:

```text
python src/scripts/results_validation_check.py paper_rewriting_output --markdown --write
```

Exit 0 = every Results subsection validates a promise. Exit 1 = at least one
subsection reports a metric that proves nothing.
