# Humanize Stage

This file is the canonical stage playbook for the paper-spine orchestrator.

## Purpose

Reduce measurable AIGC detector risk signals while preserving factual accuracy
and the author's meaning. Applies tier-specific writing constraints.

## Important Disclaimers

- Do **not** promise that a manuscript will pass any specific AIGC detector.
- Do **not** output a fabricated "AI rate" or percentage.
- Platform references are risk mappings, not descriptions of internal algorithms.

## Platform Selection

Read the appropriate platform reference based on the target detector:
- CNKI → `references/platform-cnki.md`
- Weipu → `references/platform-weipu.md`
- Unknown / general → `references/platform-general.md`

These map platform-level risk dimensions to the machine-checkable metrics
that `humanize_check.py` measures (D1–D5).

## Tier-Based Required Dimensions

| Tier | Required | Advisory |
|------|----------|----------|
| `light` | D1, D4 | D2, D3, D5 |
| `medium` | D1, D2, D3, D4 | D5 |
| `heavy` | D1–D5 | (none) |
| `none` | (structural only) | D1–D5 |

## Required Output: humanize_matrix.md

| Row ID | Manuscript Unit | AI Pattern Found | Detection Dim | Severity | Applied Change | Expected Effect | Teaching Note |
|---|---|---|---|---|---|---|---|

## Verification

```bash
python scripts/humanize_check.py paper_rewriting_output --markdown --write
```

Produces `humanize_report.md` with D1–D5 measured results. The report splits
findings into Required Findings (blocking) and Advisory Findings (non-blocking).

## Three-Round Revision Loop

At most 3 rounds. In each round, fix required dimensions' FAIL/WARNING findings.
Advisory findings: review but do not over-rewrite.

## Target-Journal Style Conformity (optional deeper method)

AIGC reduction (D1–D5) is about detector-risk signals; matching the *target
journal's* voice is a separate axis. When the deep-read journal corpus and
`journal-style-analysis.md` (JS templates) are available, apply the CASPArS
"Three R's" calibration in `references/round2-journal-revision.md`
(R1 Recalibration → R2 Replacement → R3 Redevelopment) to align word frequency,
hedging/connector choice, claim-strength distribution, and sentence rhythm with
the corpus, and build its Style Conformity Checklist. Record the analysis in
`restructuring_notes.md`. This complements, and does not replace, the humanize
metrics above.

## Humanize Threshold Overrides

Individual detection thresholds can be overridden via `paper_spine_config.json`
under the `humanize_thresholds` key.  This allows gradual calibration from real
platform back-tests without modifying the script source.

These thresholds control **local risk scanning** only — they do not represent
any vendor's internal algorithm and do not guarantee a platform pass.

Example:

```json
{
  "humanize_tier": "medium",
  "humanize_thresholds": {
    "sentence_length_cv_warning": 0.30,
    "max_connector_density": 7
  }
}
```

Invalid keys, non-numeric values, or negative values produce a warning in the
report and are ignored (the built-in default is used instead).

## Calibration

When real platform detection scores are available, read
`references/humanize-calibration.md` and record runs in
`humanize_calibration/platform_runs.md`. Do not change thresholds from a single
result.
