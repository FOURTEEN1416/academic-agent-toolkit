# Cumulative Checkpoint Response Gate Policy v3.2.15f

A checkpoint link shown to a user must be a validated cumulative restore bundle, not merely the newest zip file in a checkpoint directory.

## Response gate

Before linking a checkpoint in any user-facing reply:

1. Open the zip, or the full split-part set.
2. Verify `checkpoint-manifest.json` exists.
3. Verify `checkpoint-cumulative-integrity.json` exists.
4. Verify `checkpoint-integrity-audit.json` exists.
5. Verify the manifest scope is cumulative.
6. Verify the embedded integrity status is `PASS` or `complete_restore_ready`.
7. Verify all existing files under the cumulative roots through the closed stage are present in the archive member union.
7. If the archive fails, do not link it as a stage-final checkpoint. Rebuild it from cumulative roots. If rebuilding cannot recover all required assets, redo the producing stage/substage for the missing assets, then rebuild and validate again. Only a PASS archive may be linked.

## Stage-specific notes

- S3 checkpoints must include the S2 generated-image registry and the registered S2 raster images that S3 reviewed.
- S4 checkpoints must include S0-S4 outputs and the S5 prompt-index/prompt packages as pending future images.
- Delta bundles may be useful internally, but they must not be named or presented as `stage-final` cumulative checkpoints.

## No incomplete checkpoint terminal state

A failed cumulative checkpoint validation is a step redo trigger, not an acceptable terminal checkpoint state. The workflow must repair missing files or redo the stage that should have produced them. User-facing checkpoint links require `complete_restore_ready`; `redo_required` diagnostics are not restore bundles.

The validation derives roots, members, and required assets from workflow state, manifests, registries, and existing files. It must not depend on paper-specific filenames, candidate counts, project IDs, or image page counts.

## No-final-incomplete rule

The string `redo_required` may appear only in a diagnostic report while the workflow is blocked. It must trigger redo of the relevant producing stage/substage or an explicit request for missing prerequisites. It must never be used as a final checkpoint status, a recoverable-stage status, or a reason to continue to the next public stage.

## Every workflow text reply must pass the zip gate

For every pure-text workflow response, including reports, prompt-index preparation, candidate matrices, audits, repair logs, checkpoint summaries, and handoff prompts, the assistant must ensure at least one complete cumulative checkpoint zip exists for the active or just-completed stage. Run:

```bash
python scripts/figure_studio_response_checkpoint_zip_gate.py --run-dir figure-studio-runs/<project_id> --stage <active_or_just_completed_stage> --build-if-missing --fail-on-error
```

If the gate cannot validate a complete restore-ready zip, the reply must not claim the stage is recoverable or hand off to an image-only next stage. Reconstruct missing text state from current conversation history when possible, or redo/request missing generated rasters and source files when reconstruction is impossible.
