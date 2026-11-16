# Existing Scientific Asset Selection

Use this playbook when the project already contains multiple versions of data,
figures/tables, plotting code, analysis code, or editable/source assets.

## Authority and default

An explicit user-selected path always wins. Otherwise, select the candidate
with the newest filesystem `mtime_ns`, but only after the Agent has established
that the candidate has the same scientific identity and asset kind and that it
is inside a declared project/materials root. A newer unrelated file must never
win merely because of its timestamp.

Inventory timestamps first:

```bash
python scripts/material_inventory.py <materials-dir> --output-dir paper_rewriting_output
```

Then write `asset_selection_request.json` using
`references/contracts/asset-selection-request.schema.json`. Each candidate
must repeat the selection's `scientific_identity` and `asset_kind`; this is the
machine-checkable record of the Agent's semantic/identity decision, not a
filename guess. Run:

```bash
python scripts/asset_selection.py paper_rewriting_output/asset_selection_request.json \
  --output-dir paper_rewriting_output --json
```

The selector records every candidate path, raw `mtime_ns`, UTC timestamp,
size, SHA-256, eligibility/exclusion reasons, selection reason, and tie-break. Equal mtimes
are resolved by lexical project-relative path so the result is reproducible.
Candidates outside `project_root` or all `allowed_roots` are ineligible;
explicit selection of an ineligible asset blocks the receipt.

Keep `asset_selection_receipt.json/.md` with `source_inventory`. If scientific
identity is uncertain, do not relabel candidates to force a green receipt;
inspect the data/code/figure and resolve the identity first.

Before final completion, revalidate the stored decision against the current
files:

```bash
python scripts/asset_selection.py paper_rewriting_output/asset_selection_request.json \
  --verify-receipt paper_rewriting_output/asset_selection_receipt.json --json
```

Any changed candidate hash, timestamp, eligibility, or selected path invalidates
the receipt. `progress_check.py --gate final_audit` performs this verification
automatically whenever either the request or receipt exists.
