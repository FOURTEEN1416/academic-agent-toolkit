# Checkpoint Response And Repair Gate Policy v3.2.15f

This policy is paper-agnostic. It applies whenever the workflow writes code, creates checkpoints, reports checkpoint links, or prepares cross-session restore artifacts.

## Response gate

A response must not present a zip as a cumulative or complete restore checkpoint unless the archive, or split-archive union, contains both:

- `checkpoint-manifest.json`
- `checkpoint-cumulative-integrity.json`

and the saved integrity/audit reports pass. The archive must also contain `checkpoint-integrity-audit.json`.

The assistant must not choose a checkpoint solely because it has the largest sequence number or newest-looking filename. It must validate the checkpoint contents first. Current-stage-only or current-substage-only bundles must be named supplemental/delta artifacts, not `stage-final` checkpoints.

## Generic rebuild loop

If validation finds missing cumulative roots, missing already-existing assets, missing registered raster outputs, missing active stage-local image mirrors, or missing integrity metadata, the builder must rebuild the checkpoint from cumulative roots and rerun the guard up to the configured retry limit.

The rebuild process must derive expected files from project state, workflow output roots, stage manifests, prompt-index rows, artifact records, image generation events, and existing files. It must not hard-code paper names, module names, variables, candidate IDs, image counts, page counts, or fixed run filenames.

## Code-writing requirement

Any new or modified helper code that writes candidate matrices, prompt-index files, image registrations, or checkpoints must be accompanied by a generic validation command or unit-style smoke test. The test must show that dynamic candidate IDs and dynamic counts are derived from input data rather than hard-coded for one project.

## Failure handling: repair-or-redo, no incomplete final state

`redo_required` is a transient diagnostic state only. It is not an acceptable stage-close state and must not be offered to the user as a restore checkpoint.

If the guard cannot repair the checkpoint within the bounded retry limit, the workflow must:

1. Write exact missing-asset reports.
2. Identify the producing stage/substage for each missing required asset from state, manifests, prompt-index rows, image-registration records, and artifact manifests.
3. Redo the producing stage/substage needed to recreate the missing assets, then rerun image/output registration if the missing assets are generated rasters.
4. Rebuild the cumulative checkpoint and rerun the guard.
5. Repeat repair/redo/rebuild until the cumulative checkpoint validates as PASS.

The workflow must not proceed to the next public stage, close the current stage as recoverable, or link a `stage-final` checkpoint while any required existing asset, registered raster, prompt package, state file, or integrity metadata is missing. If redo is blocked because the original source file, generated image, or user approval is unavailable, the workflow must stop and request exactly that missing prerequisite; it must not label the checkpoint as usable.

Stage redo routing must remain generic. Examples: missing prompt-index/prompt packages require redoing the text stage that prepared them; missing registered images require redoing the image stage that produced them and then rerunning registration; missing review/selection records require redoing the corresponding review stage. Do not hard-code project names, paper topics, candidate IDs, candidate counts, or image page counts.

## Response-time checkpoint zip requirement

Every workflow text reply must be preceded by a response-time cumulative checkpoint zip gate. The recommended generic command is:

```bash
python scripts/figure_studio_response_checkpoint_zip_gate.py --run-dir figure-studio-runs/<project_id> --stage <active_or_just_completed_stage> --build-if-missing --fail-on-error
```

The gate verifies that at least one zip contains cumulative roots plus `checkpoint-manifest.json`, `checkpoint-cumulative-integrity.json`, and `checkpoint-integrity-audit.json`. If no valid zip exists, rebuild from cumulative roots. If text state is absent but recoverable from the current conversation, write reconstruction notes/state into outputs and rebuild. If generated raster or source assets are absent, redo/request the exact missing prerequisite instead of presenting an incomplete checkpoint.
