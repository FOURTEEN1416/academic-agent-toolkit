# Cumulative Restore Checkpoint Policy v3.2.9

Every checkpoint is a cumulative restore bundle from S0/project start through the current public stage/internal substage.
This rule applies to stage-final checkpoints and to every intermediate chunk/substage checkpoint.

Asset classes:

- `required_existing_assets`: all files already produced or registered and required to restore the current state;
- `required_existing_images`: all already-generated raster assets in included roots or registries;
- `pending_future_assets`: planned outputs that have not yet been generated and therefore must not block restore;
- `optional_history_assets`: prior manifests/checksums or nonessential history.

After S5, human decisions are outside this assistant workflow.

After writing the zip or split parts, reopen the archive member list and verify every required existing asset is present. Missing required existing assets require generic repair; if repair cannot recover them, redo the producing stage/substage and rebuild until PASS.

## Mandatory cumulative integrity guard

Every checkpoint archive must include `checkpoint-manifest.json` and `checkpoint-cumulative-integrity.json`.
The integrity report must verify that:

1. the checkpoint scope is cumulative;
2. the manifest's included roots cover every completed/current root through the current stage/substage;
3. every existing file under those roots appears in the zip or zip-part union;
4. every generated/registered required raster asset appears in the zip or zip-part union;
5. not-yet-generated planned outputs are recorded as pending, not as missing required files;
6. no previous completed/current output root with existing files is absent from the archive.

If the integrity report fails, the workflow must rebuild the checkpoint from cumulative roots and rerun the guard. If it still fails, the checkpoint must be recorded as `redo_required`, not `complete_restore_ready`.
