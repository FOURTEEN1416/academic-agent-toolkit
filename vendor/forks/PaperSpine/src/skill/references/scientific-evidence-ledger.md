# Scientific Evidence Ledger

Use this playbook for journal, conference, and competition work. The ledger is
the machine-checkable bridge between user materials, analysis, Results, and the
confirmed contribution. It complements `evidence_bank.md`; it does not replace
the paper-facing rationale matrix.

## Lifecycle In The Real Research Workflow

1. **Material intake / existing-paper rewrite:** inventory source files and
   record their hashes or stable identifiers as `S###` records.
2. **Analysis planning:** register the intended claims (`C###`), methods
   (`M###`), outcomes (`O###`), and planned results (`R###`). Use
   `verification_state=planned` where experiments have not run.
3. **After analysis:** add numeric facts (`N###`), bind each result to claims,
   methods, outcomes, sources, conditions, and uncertainty. Never convert an
   absent result into a plausible number.
4. **Before drafting:** run the planning check. Unverified/planned records are
   allowed only if the prose does not present them as observed evidence.
5. **Before submission:** every record used in the final manuscript must be
   `verified`, `user_authoritative`, or `not_applicable`; set ledger status to
   `manuscript_ready` and run the final check.

## Required File

Write `paper_rewriting_output/scientific_evidence_ledger.json`:

```json
{
  "schema_version": "1.0",
  "status": "analysis_ready",
  "records": {
    "sources": [
      {
        "id": "S001",
        "kind": "user_material",
        "evidence_locator": "source_inventory.md#dataset-a",
        "sha256": "<source hash>",
        "verification_state": "user_authoritative"
      }
    ],
    "claims": [
      {
        "id": "C001",
        "text": "Bounded contribution claim",
        "boundary": "What this claim does not establish",
        "source_ids": ["S001"],
        "result_ids": ["R001"],
        "used_in_final": true
      }
    ],
    "numeric_facts": [
      {
        "id": "N001",
        "value": "0.031",
        "unit": "absolute accuracy gain",
        "source_ids": ["S001"],
        "result_ids": ["R001"],
        "verification_state": "user_authoritative",
        "evidence_locator": "results/table2.csv#row-3"
      }
    ],
    "methods": [
      {
        "id": "M001",
        "name": "Matched-budget evaluation",
        "source_ids": ["S001"],
        "result_ids": ["R001"],
        "verification_state": "user_authoritative",
        "evidence_locator": "methods/run_config.json"
      }
    ],
    "outcomes": [
      {
        "id": "O001",
        "name": "Accuracy",
        "definition": "Correct predictions divided by evaluated examples",
        "source_ids": ["S001"]
      }
    ],
    "results": [
      {
        "id": "R001",
        "claim_ids": ["C001"],
        "numeric_fact_ids": ["N001"],
        "method_ids": ["M001"],
        "outcome_ids": ["O001"],
        "source_ids": ["S001"],
        "conditions": "Dataset A standard split; matched backbone and budget",
        "uncertainty": "No external validation; confidence interval unavailable",
        "verification_state": "user_authoritative",
        "evidence_locator": "results/table2.csv#row-3"
      }
    ]
  }
}
```

`verified` requires `verified_by`. `user_authoritative` requires an
`evidence_locator`. Human verification and stable identifiers must remain
visible as state; passing a parser never makes an unverified source verified.

```bash
python scripts/scientific_evidence_check.py paper_rewriting_output --phase planning --markdown --write
python scripts/scientific_evidence_check.py paper_rewriting_output --phase final --markdown --write
```
