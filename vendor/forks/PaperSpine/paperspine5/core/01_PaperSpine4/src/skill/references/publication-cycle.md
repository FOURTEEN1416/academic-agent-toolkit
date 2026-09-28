# Publication Cycle

Use this playbook after a manuscript has a stable scientific identity. It owns
three post-draft/post-delivery modes without creating another PaperSpine skill:

1. `submission` — build a target-specific, upload-ready delivery bundle;
2. `revision` — answer minor/major revision decisions through a traceable rebuttal round;
3. `transfer` — recommend and confirm a new venue, then rebuild the manuscript and package for it.

The modes share one target profile and one rule: current official author
instructions are the hard source for submission requirements. Recent published
papers teach journal-specific narrative preferences; they do not override the
official guide.

## Route

| Request | Read next |
|---|---|
| Submission, delivery materials, attachments, upload ZIP | `submission.md` |
| Minor/major revision, response letter, rebuttal | `respond.md` |
| Rejection, resubmission, journal transfer | `journal-transfer.md` |
| Create or refresh a venue profile | `publication-target-profile.md` |
| Machine-readable field definitions | `publication-cycle-contracts.md` |
| Main-flow, host, or cross-Agent integration | `publication-cycle-interface.md` |

## Shared authority

- The canonical manuscript, confirmed contribution, evidence ledger, figure
  story/body contract, citations, metadata, and five readiness receipts remain
  scientific truth.
- `publication_target_profile.json` is the current venue-requirement truth.
- `submission_package_plan.json`, `review_round.json`, and
  `transfer_request.json` bind paper-specific decisions to that truth.
- A generated Markdown report is evidence only for the exact source hashes it
  records. A previous target's package is never authority for a new target.

## Readiness boundary

`progress_check.py is_complete=true` means the canonical paper passed the five
PaperSpine dimensions. It does not mean a requested journal package is ready.
For a real delivery bundle, also require `bundle_manifest.json status=READY`,
the archive SHA-256 receipt, and no pending author confirmations.

For a rebuttal, require `publication_cycle.py rebuttal-check` PASS for the
current round. For transfer, require `transfer_delta.json
status=READY_TO_REBUILD`, then complete a new manuscript render and a new READY
bundle for the destination.

Main-flow callers must use `publication_cycle.py describe/invoke` and consume
the versioned result `signals`; they must not infer state by parsing Markdown or
the older command-line wording. `READY_TO_REBUILD` is a return to target
planning/drafting/LaTeX/audit, not a destination bundle completion signal.

## Authorization boundary

The module may research, recommend, transform local files, render, validate,
and prepare an upload archive. It must not click the final submit/transfer
button, accept publishing charges, select license terms, or make author
declarations without the user's separate authorization. Unknown author-only
facts remain pending and block the bundle; never infer them from manuscript
prose.

