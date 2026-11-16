# Publication Cycle

For the current host, retain the same public task and its saved scope, files,
choices and feedback. Use submission.md for local packaging and respond.md for
revision. The legacy ProductRunner route applies only when that runner is
explicitly in use; normal local delivery does not require J10 receipts. The upload-ready bundle and author-confirmation rules
below apply to a submission package, not to every safe local paper download.
Do not silently change the requested scope or infer unknown author facts.

Use this playbook after a manuscript has a stable scientific identity. It owns
four post-draft/post-delivery modes without creating another PaperSpine skill:

1. `submission` — build a target-specific, upload-ready delivery bundle;
2. `revision` — answer minor/major revision decisions through a traceable rebuttal round;
3. `transfer` — recommend and confirm a new venue, then rebuild the manuscript and package for it.
4. `open_release` (Beta) — after delivery, recommend repositories/platforms,
   preflight permissions and compliance, obtain a separate hash-bound release
   confirmation, and hand exact actions to the host Agent.

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
| Open source, archive, preprint, register, or upload after delivery | `open-release.md` |
| Create or refresh a venue profile | `publication-target-profile.md` |
| Machine-readable field definitions | `publication-cycle-contracts.md` |
| Main-flow, host, or cross-Agent integration | `publication-cycle-interface.md` |
| Open-release main-flow/host integration | `open-release-interface.md` |

## Shared authority

- The canonical manuscript, confirmed contribution, evidence ledger, figure
  story/body contract, citations, metadata, and five readiness receipts remain
  scientific truth.
- `publication_target_profile.json` is the current venue-requirement truth.
- `submission_package_plan.json`, `review_round.json`, and
  `transfer_request.json` bind paper-specific decisions to that truth.
- A generated Markdown report is evidence only for the exact source hashes it
  records. A previous target's package is never authority for a new target.
- Formal title/abstract/body/figure/table/reference/attachment limits and
  required sections/materials live in the profile's structured `compliance`
  contract. Missing or pending official coverage blocks readiness; recent-paper
  patterns can only create advisory rules.

## Readiness boundary

`progress_check.py is_complete=true` means the canonical paper passed the five
PaperSpine dimensions. It does not mean a requested journal package is ready.
For a real delivery bundle, also require `bundle_manifest.json status=READY`,
the archive SHA-256 receipt, `journal_rules_final.json status=PASS`, and no
pending author confirmations. Writing-stage prechecks help the Agent revise
early, but `assemble` re-evaluates the current source and package plan.

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

Open Release is a deliberately separate authority layer. Its local `prepare`
also authorizes nothing. Only `open_release.py authorize` may create an exact,
hash-bound host ticket after a final user confirmation; new fees, licenses,
terms, declarations, eligibility, institutional authority, or changed artifacts
invalidate that scope and require another confirmation.
