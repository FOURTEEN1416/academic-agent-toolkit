# Cumulative Checkpoint Integrity Guard Policy v3.2.9

This policy is paper-agnostic. It applies to every project, paper, and dynamic substage that writes a checkpoint bundle.
It must not contain or infer any paper-specific module name, dataset name, variable name, candidate id, image count, or task-specific file list.

## Core rule

Every checkpoint, including intermediate chunk/substage checkpoints, must be a cumulative restore bundle from project start through the current public stage or internal substage.
A checkpoint is never allowed to be a current-substage-only delta unless it is explicitly marked as non-restore supplemental history and is not called a checkpoint.

## Required substage-page checks

For every text substage page or image substage page that writes or reports a checkpoint, the page must run and record a cumulative checkpoint integrity check before telling the user the checkpoint is usable.
After S5, human decisions are outside this assistant workflow.

The substage page must verify, in a saved report and in the stage/substage manifest, all of the following:

1. `checkpoint_scope` states a cumulative restore scope.
2. `included_roots` covers static state/input roots and every completed/current output root through the current stage/substage.
3. every already-existing file under those roots is present in the zip or zip-part union;
4. every already-generated/registered raster asset that should exist is present;
5. planned but not-yet-generated outputs are classified as `pending_future_assets` or `pending_future_images`, not missing restore blockers;
6. the archive contains `checkpoint-manifest.json` and `checkpoint-cumulative-integrity.json`;
7. the integrity report status is `PASS` before the response may call the bundle `complete_restore_ready`.


## Stage-local generated image paths

Generated raster candidates and selected images should be required at their active stage-local registry paths once their image-generation unit has succeeded. A checkpoint may include additional provenance escrow copies, but it must not rely on an escrow-only location as the active candidate path when the stage registry says the active image is under the stage output tree. If a generated image is present in an external generator folder or escrow but missing from the active stage-local path, the guard should report the active path as missing or the registration as incomplete rather than silently treating the escrow copy as equivalent.

The exact active paths, candidate ids, and image counts must still be discovered from state, manifests, registries, and image-generation events. This rule is about path role and restore semantics, not about any particular filename scheme.

## No hard-coded expectations

The checkpoint guard must derive expected roots and required files from:

- `project-state.json`, workflow plan, and active stage/substage records;
- registered artifacts and image-generation events;
- existing project-run-relative folders under cumulative roots;
- candidate/prompt/rerun/final registries when present.

It must not hard-code:

- paper-specific names or variables;
- fixed candidate IDs;
- fixed image counts;
- expected filenames for a particular run;
- fixed stage numbers beyond the reusable workflow order available in the state/skill constants.

## Rerun loop

If the guard fails, the workflow must not proceed as though the checkpoint is complete.
The builder should rebuild the checkpoint from the cumulative roots and rerun the guard, up to the configured local retry limit.
If the guard still fails, the checkpoint must be marked `redo_required` and the response must list the missing roots/assets and exact rerun instruction.

Generic pseudocode:

```python
for attempt in range(max_retries):
    build_checkpoint_from_cumulative_roots()
    report = validate_cumulative_checkpoint()
    write_report("checkpoint-cumulative-integrity.json", report)
    rebuild_or_update_archive_to_include_integrity_report()
    if report["status"] == "PASS":
        mark_checkpoint_complete_restore_ready()
        break
else:
    write_redo_required_diagnostic_and_redo_affected_stage()
    emit_missing_asset_or_root_manifest()
```

## Response contract

Whenever a substage response names a checkpoint link, it must also state whether the saved guard report passed.
If the guard did not pass, the response must avoid wording such as “complete restore checkpoint”, “cumulative checkpoint”, or `complete_restore_ready`.

## v3.2.15f response-gate addendum

Before any user-facing response links a checkpoint as a cumulative or complete restore bundle, the workflow must validate the linked archive or split-archive union. The archive must include `checkpoint-manifest.json` and `checkpoint-cumulative-integrity.json`, and the embedded integrity status must pass. If validation fails, rebuild generically from cumulative roots and rerun the guard, or write a `redo_required` diagnostic, redo the affected stage, and avoid presenting any failed bundle as usable.

This addendum does not change the no-hard-coding rule: the guard must still derive expected roots, assets, and registered raster paths from state, manifests, prompt-index rows, artifact records, image events, and existing files.
