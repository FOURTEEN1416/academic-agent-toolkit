# Stage Redo On Unrepairable Checkpoint Policy v3.2.15f

This policy is paper-agnostic and applies whenever cumulative checkpoint validation fails after bounded generic repair attempts.

## Mandatory behavior

A cumulative checkpoint must be complete. If missing assets cannot be restored by copying existing cumulative roots into a rebuilt archive, the workflow must redo the stage/substage that produced the missing assets. It may not close the stage, proceed to the next stage, or present a degraded archive as recoverable.

`redo_required` is only a transient blocker label. A valid workflow exit must be either:

- `PASS` / `complete_restore_ready`, after repair or redo has produced a complete cumulative checkpoint; or
- `blocked_waiting_for_prerequisite`, when a redo cannot be performed because a source file, generated raster, connector file, user approval, or image-generation route is missing.

## Generic redo mapping

The missing-asset report must derive redo responsibility from project state and manifests, not from hard-coded stage names or project domains. Generic examples:

- Missing generated raster listed in a prompt-index target path -> redo that image-generation stage/substage and rerun image-output registration.
- Missing prompt package or prompt-index -> redo the text stage that prepared the prompt packages.
- Missing review/selection record -> redo the review/selection text stage.
- Missing state/manifest/provenance file -> rebuild from the latest valid cumulative checkpoint or redo the stage that wrote the record.

## Handoff rule

A next-stage prompt may be offered only after the current stage has a validated cumulative checkpoint or after the user explicitly acknowledges that the prerequisite for redo is unavailable and asks to abandon/restart the workflow.
