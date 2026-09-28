# Restore Repair-Or-Redo Policy v3.2.15f

This policy is paper-agnostic. It applies whenever the workflow writes, validates, repairs, selects, or links a checkpoint artifact.

## Non-negotiable close rule

A public stage or internal substage that is expected to save a checkpoint cannot close on a missing, delta-only, or incomplete cumulative checkpoint. The workflow must either:

1. repair the checkpoint from already-existing cumulative roots, registries, prompt indexes, image registrations, and state; or
2. redo the producing stage/substage that failed to create the required asset, then rebuild and revalidate the checkpoint.

A failure diagnostic such as `restore_repair_required_stage_redo` may be written into logs, but it is not a final stage status. The assistant must not proceed to the next workflow stage, suggest the next image-generation stage, or present a checkpoint as recoverable until the checkpoint guard passes.

## Required metadata

Every user-facing cumulative checkpoint must contain all three metadata members:

- `checkpoint-manifest.json`
- `checkpoint-cumulative-integrity.json`
- `checkpoint-integrity-audit.json`

The saved integrity/audit reports must show PASS or `complete_restore_ready` semantics. Planned future images are allowed only as `pending_future_images`; already-generated or registered raster paths are required restore assets.

## Generic redo trigger

If repair cannot find a required existing asset, the remedy is not to hide the gap or downgrade the checkpoint. The workflow must identify the producing stage/substage from state, manifest, prompt-index, artifact records, or path ownership and redo that stage/substage. This rule is generic and must not hard-code project ids, paper topics, candidate ids, candidate counts, page counts, or image totals.

## Conversation reconstruction fallback

When a response checkpoint zip is missing and the file system lacks state/manifests that the assistant can still reconstruct from the active conversation, reconstruct that text state into run outputs first, then rebuild the normal cumulative checkpoint and rerun the gate. A fallback zip that merely preserves available files is allowed only as a diagnostic artifact and must be labeled `conversation_reconstruction_required` or equivalent; it is not a usable restore checkpoint.
