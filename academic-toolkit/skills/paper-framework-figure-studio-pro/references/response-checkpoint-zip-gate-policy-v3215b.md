# Response Checkpoint Zip Gate Policy v3.2.15f

This policy is paper-neutral and applies to every workflow text reply, including reports, state/manifest writes, candidate matrices, prompt-index preparation, audits, repair logs, checkpoint reports, guidance, and handoff prompts.

## Rule

Before a workflow text reply is presented, the run must contain at least one validated cumulative checkpoint zip for the active or just-completed public stage. The checkpoint must be a project-start-to-current mirror, not a delta archive.

A user-facing cumulative checkpoint zip must include:

- `checkpoint-manifest.json`;
- `checkpoint-cumulative-integrity.json`;
- `checkpoint-integrity-audit.json`;
- cumulative `state/`, `inputs/`, and stage output roots through the active or just-completed stage;
- existing prompt packages, prompt-index files, candidate matrices, manifests, issue ledgers, repair logs, and handoff/guidance records;
- all already-generated and registered raster images plus their active stage-local mirrors;
- S2 raster images listed as S5 `reference_image_paths` in S5 prompt-index rows;
- pending future image target records when a text stage prepares a later image stage.

The manifest scope must be cumulative, and embedded integrity/audit status must be `PASS` or `complete_restore_ready` before the assistant may call the zip restore-ready or link it as a usable checkpoint.

## Required script gate

Use this fixed response-time gate or an equivalent generic check before a workflow text reply:

```bash
python scripts/figure_studio_response_checkpoint_zip_gate.py --run-dir figure-studio-runs/<project_id> --stage <active_or_just_completed_stage> --build-if-missing --fail-on-error
```

The gate must not use paper names, project-specific candidate IDs, fixed image counts, or fixed page counts. It derives stage roots from state, workflow plan, prompt-index records, and existing files.

## If no valid zip exists

1. Rebuild from cumulative roots and rerun the gate.
2. If text state is missing but the current conversation contains enough information to reconstruct it, write reconstruction notes and rebuilt state/manifests under the appropriate output roots, then rerun the normal cumulative checkpoint builder.
3. If generated raster images, external source files, or user approvals are missing, identify the exact missing prerequisite and redo the producing image/text stage or request the missing asset.
4. A fallback reconstruction zip may be written to preserve available files, but it must not be described as complete restore-ready until the normal metadata and integrity gate pass.

## Blocking condition

A stage or pure-text substage cannot close as recoverable, cannot hand off to the next image-generation stage, and cannot advertise a checkpoint link while the response checkpoint zip gate fails. `redo_required` and `conversation_reconstruction_required` are diagnostic blockers, not final restore states.
