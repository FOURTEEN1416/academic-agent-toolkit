# Supplement evidence index

Use `supplement_evidence_index.py` when a manuscript relies on supplementary
figures, tables, data, methods, or notes. The index is a bidirectional contract,
not a list of filenames.

For each claim-bearing supplementary item, record:

- the main-text claim ID and literal locator;
- the supplementary caption or section locator;
- the publication asset and the actual upload artifact, each with SHA-256;
- a rendered-surface summary and an independently saved semantic-review receipt;
- the item's scientific role (support, boundary case, robustness check, detailed
  method, or secondary result).

The checker verifies recorded claim links, literal locators, file hashes, semantic status fields and the presence of a review file. It does not itself inspect pixels or establish reviewer independence. An independent reviewer must actually compare the current supplementary content, captions and supported claims; retain that finding in the same task's review notes. A technically valid PDF or checker PASS is not scientific approval.

`submission_inventory` also records journal-required upload surfaces. A
required item in `needs_author` state blocks package completeness. A local PASS
never supplies author approval and never authorizes external submission.

Example:

```powershell
python src/scripts/supplement_evidence_index.py path/to/supplement_evidence_index.json `
  --write-report path/to/supplement_evidence_index_report.json
```
