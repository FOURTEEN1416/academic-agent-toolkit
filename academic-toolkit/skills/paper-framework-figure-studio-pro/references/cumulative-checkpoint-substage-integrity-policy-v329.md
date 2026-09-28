# Cumulative Substage Checkpoint Integrity Policy v3.2.9

This policy is paper-agnostic and project-agnostic. It applies to every checkpoint-producing public stage, dynamic internal substage, rerun/review unit, aggregate unit, and future image stage once that stage is declared in workflow state. It must not encode a specific paper, project id, candidate id, image count, file name convention, or domain-specific module.

## Core rule

Every checkpoint zip or split-part checkpoint is a cumulative restore bundle from the beginning of the workflow through the current public stage/internal substage. A checkpoint is never a current-stage-only, current-substage-only, or delta-only artifact.

A checkpoint-producing response/page may call a checkpoint `complete_restore_ready` only after post-write archive validation proves that every required existing asset in the cumulative scope is present in the zip member union.

## Required checkpoint page section

Every text-only stage page or substage page that creates, references, or closes with a checkpoint must include a machine-readable or plainly auditable `checkpoint_integrity` section containing:

- `cumulative_required: true`
- `checkpoint_scope`: cumulative from workflow start through current stage/substage
- `current_stage` and, when applicable, `current_substage_id`
- `predecessor_checkpoint_ref` or `predecessor_checkpoint_unavailable_reason`
- `included_roots`
- `stage_coverage` derived from workflow state/manifests, not hard-coded
- `required_existing_asset_count`
- `required_existing_image_count`
- `pending_future_asset_count` and/or `pending_future_image_count`
- `post_write_validation_status`
- `rebuild_attempt_count`
- `checkpoint_status`: `complete_restore_ready` or `redo_required` diagnostics that trigger step redo
- paths for `checkpoint-manifest.json`, `checkpoint-missing-assets.json`, and `checkpoint-missing-images.json` when present

The page must not present a checkpoint link as cumulative or restore-ready if this section is missing or incomplete.

## Generic cumulative inventory

The inventory must be built from project state, workflow plan, stage/substage manifests, prompt indexes, candidate registries, image-generation records, artifact records, rerun lineage, finalization records, and existing files under cumulative included roots.

The inventory must not assume:

- a fixed number of candidates;
- fixed candidate IDs;
- fixed image names;
- fixed stage output filenames beyond declared artifact roles and actual manifests;
- a particular paper method, module, dataset, or variable name.

Planned future assets and not-yet-generated images from a text-prepare stage are `pending_future_assets` or `pending_future_images`. They are not restore blockers.

## Bounded rebuild-and-revalidate loop

Checkpoint creation must follow this generic loop:

1. Build cumulative inventory from the current run directory and state.
2. Write checkpoint manifest into the checkpoint metadata directory.
3. Pack every required existing asset under cumulative included roots, excluding prior checkpoint zips to avoid recursive nesting.
4. Reopen the zip or split-part union and compare member paths against the required existing asset inventory.
5. If missing entries are found, rebuild from the same cumulative inventory after writing missing manifests and updated checkpoint manifest.
6. Revalidate the rebuilt zip member union.
7. Repeat only up to the configured attempt limit. The default is three total validation attempts.
8. If entries remain missing, write a `redo_required` diagnostic with exact missing manifests, redo the affected stage, and rebuild; do not describe it as complete.

The loop is a guardrail, not a permission to hide failure. A blocked checkpoint is acceptable only when it truthfully records what is missing and how to restore it.

## Predecessor inheritance audit

When a previous checkpoint exists, the current checkpoint page must compare its cumulative scope against the predecessor checkpoint manifest or zip member union where available:

- predecessor-required assets that still exist in the run directory remain required in the new checkpoint;
- predecessor-pending future assets remain pending unless now generated or explicitly invalidated by state/rewind records;
- predecessor missing manifests must not be silently dropped unless the missing asset has been restored, marked stale, or removed through an explicit cleanup/rewind record.

If predecessor checkpoint metadata is unavailable, the page must say so and rely on run-directory inventory plus state/manifests.

## Substage-specific requirement without hardcoding

Dynamic substage workflows often produce checkpoint zips before the public stage closes. These chunk checkpoints must use the same cumulative rule as stage-final checkpoints. The fact that a substage name contains embedded prompt preparation, `IMAGE_GENERATE`, embedded image review, `deleted candidate revision unit`, `deleted_text_recheck`, or embedded aggregate does not change the checkpoint scope.

A substage checkpoint that contains only that substage's prompt package, image outputs, audit report, or guidance file is invalid as a restore checkpoint unless the whole workflow truly has no previous assets.

## Validator behavior

The validator must fail any checkpoint when:

- required files under earlier included roots are absent from the zip member union;
- the zip lacks `checkpoint-manifest.json`;
- `checkpoint-manifest.json` claims cumulative scope but `stage_coverage` excludes earlier completed/current stages without explicit cleanup/rewind evidence;
- the substage page says `complete_restore_ready` but the manifest says incomplete or blocked;
- missing required existing images are not listed in `checkpoint-missing-images.json`;
- missing required existing non-image assets are not listed in `checkpoint-missing-assets.json`.

The validator must not fail merely because planned future images or assets do not yet exist.

## User-facing wording

Use precise wording:

- `complete_restore_ready`: all required existing assets were packed and verified.
- `redo_required`: some required existing assets/images are missing from the checkpoint; exact restore paths are listed.
- `pending_future_*`: planned future assets that do not yet exist and do not block restore.

Do not use vague phrases such as "checkpoint created" to imply completeness when validation has not run.
