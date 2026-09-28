# ChatGPT Web Checkpoint Bundle Policy v3.2.9

Every checkpoint zip or split checkpoint part must be a cumulative restore snapshot from S0/project start through the current public stage/internal substage. This includes dynamic substage checkpoints such as text-prepare, image-generate, text-audit, rerun, review, and aggregate units.

Include:

- `project-state.json` and state/history registries;
- all outputs under completed/current stage roots;
- prompt packages, audits, manifests, candidate folders, substage guidance, and next-prompt registries;
- After S5, human decisions are outside this assistant workflow.
- `checkpoint-manifest.json`, `checkpoint-cumulative-integrity.json`, and checksum/restore metadata when available.

Do not hard-code image counts, candidate IDs, expected filenames, paper-specific variable names, or stage-specific image totals. Planned but not-yet-generated images are `pending_future_images`, not missing required images.

After writing the zip, reopen its member list and verify every required existing asset is present. Also run the cumulative integrity guard: every already-existing cumulative root through the current stage/substage must have its files present in the archive member union. If any required existing asset or cumulative root is missing, write exact repair diagnostics, redo the producing stage/substage if generic rebuild cannot recover the required files, then rebuild the cumulative checkpoint until the guard passes. Do not close the stage or present the archive as recoverable while required assets are missing.

A ChatGPT web response may call a checkpoint `complete_restore_ready` only when the saved integrity report is `PASS`.
