# Publication Cycle Integration Interface

Read this reference when PaperSpine, PaperSpine5, a host adapter, or another
Agent needs to call the target-submission, revision, or transfer module. The
stable interface is a local JSON request/result contract; callers must not
parse human-facing Markdown or CLI prose to infer workflow state.

## Discovery and transport

```bash
python scripts/publication_cycle.py describe
python scripts/publication_cycle.py invoke <publication-cycle-invocation.json>
```

Source-tree callers use `src/scripts/publication_cycle.py`. Installed Skill
callers use `scripts/publication_cycle.py`. Python callers may import
`public_interface_descriptor()` and `invoke_publication_cycle(request_path)`
from the same module, but the JSON CLI is preferred across component and host
boundaries because it does not depend on a shared Python package path.

Schemas:

- `references/contracts/publication-cycle-invocation.schema.json`
- `references/contracts/publication-cycle-result.schema.json`

## Request

All paths are resolved relative to the invocation JSON and must remain inside
its declared `project_root`. A nested `submission_package_plan.json`,
`review_round.json`, or `transfer_request.json` may narrow that root, but may
not expand beyond it.

```json
{
  "contract": "paperspine.publication-cycle.invoke-request",
  "interface_version": "1.0",
  "operation": "assemble",
  "project_root": ".",
  "inputs": {
    "profile": "publication_cycle/targets/journal-a/publication_target_profile.json",
    "plan": "publication_cycle/targets/journal-a/submission_package_plan.json"
  },
  "outputs": {
    "directory": "submission_package/journal-a/2026-08-23-v1"
  },
  "options": {
    "write_report": false
  }
}
```

Operations:

| Operation | Required inputs | Output directory | Success outcome |
|---|---|---|---|
| `profile_check` | `profile` | no | `PROFILE_VALID` |
| `assemble` | `profile`, `plan` | yes, new/empty | `BUNDLE_READY` |
| `rebuttal_check` | `review_round` | no | `REBUTTAL_VALID` |
| `rebuttal_render` | `review_round` | yes, new/empty | `REBUTTAL_READY` |
| `transfer_plan` | `origin_profile`, `destination_profile`, `transfer_request` | yes, new/empty | `READY_TO_REBUILD` |

`options.write_report=true` writes a Markdown check beside the profile or
review-round input for the two check-only operations. Generated output
directories are immutable run directories; do not reuse a non-empty one.

## Result

Every invocation writes one JSON object to stdout and exits `0` only when
`ok=true`. The caller should consume these fields:

| Field | Integration meaning |
|---|---|
| `outcome` | Operation-specific success or `BLOCKED`. |
| `stage` | Stable stage to map into the main state machine. |
| `blocking_findings` | Exact reasons to route back to an owner. |
| `input_receipts` | Project-relative paths, SHA-256, and byte sizes of consumed contracts. |
| `artifacts` | Project-relative paths, SHA-256, and byte sizes of generated files. |
| `signals` | Boolean integration gates; consume these instead of interpreting filenames. |
| `next_action` | Owning component/person and the next required action. |
| `authority_boundary` | External submission, fees, licenses, author-only facts, and scientific-identity changes remain unauthorized. |
| `audit` | Full operation-specific validation payload for diagnostics. |

Only these booleans advance the corresponding main-flow state:

- submission: `ok && signals.submission_bundle_ready`;
- revision materials: `ok && signals.rebuttal_materials_ready`;
- transfer branch: `ok && signals.destination_rebuild_ready`.

`signals.external_action_authorized` is always `false`. A successful local
operation never authorizes clicking submit/resubmit/transfer, accepting an APC,
choosing a license, or asserting author-only declarations.

## Main-flow placement

### Submission

```text
PaperSpine canonical paper + five readiness dimensions complete
  → profile_check
  → main flow applies target format and all five narrative preferences
  → main flow prepares/validates every required attachment and author confirmation
  → assemble
  → BUNDLE_READY + immutable ZIP + checksum
  → user separately authorizes external submission
```

The target bundle is not ready merely because `progress_check.py` reports
`is_complete=true`. The caller must retain both authorities: canonical-paper
readiness and target-bundle readiness.

### Minor or major revision

```text
decision letter preserved and atomized
  → main flow confirms author intent, implements changes, and reruns required gates
  → rebuttal_check
  → rebuttal_render
  → main flow assembles the revised manuscript + rebuttal delivery bundle
  → user separately authorizes external resubmission
```

Major revision and reject-and-resubmit require all five readiness dimensions
to pass. Minor revision may mark a genuinely unaffected dimension
`not_affected`, but unresolved or pending evidence remains blocking.

### Rejection and transfer

```text
canonical paper identity frozen
  → main flow researches contrasting candidates and records user preferences
  → user confirms destination (and reshape actions when applicable)
  → transfer_plan
  → READY_TO_REBUILD
  → return to target-specific planning/drafting/LaTeX/audit
  → rebuild format + all five narrative parts + every destination material
  → assemble a new immutable destination bundle
```

`READY_TO_REBUILD` is deliberately not `BUNDLE_READY`: it authorizes local
destination reconstruction only. Never mutate or rename the previous target's
bundle to represent a transfer.

## Owner routing on failure

- stale/unsupported official rule or incomplete five-part preference → target-profile research;
- manuscript format, figure, attachment, or validation-receipt failure → main PaperSpine production/audit owner;
- authorship, declarations, exclusivity, destination choice, or response position → user/author confirmation;
- unverified reviewer evidence or unlocated manuscript change → revision owner;
- `redirect` fit verdict → journal recommendation branch, not drafting;
- escaped paths, stale hashes, or non-empty immutable output → integration caller fixes its request/run directory.

The caller may surface `blocking_findings` to the user, but it must preserve the
request JSON and returned hashes as the recoverable state authority. Chat text
is not a substitute for those artifacts.
