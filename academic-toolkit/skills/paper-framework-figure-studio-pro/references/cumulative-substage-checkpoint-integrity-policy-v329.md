# Cumulative Substage Checkpoint Integrity Policy v3.2.9

This policy is project-agnostic. It applies to every checkpoint-producing public stage, internal substage, chunk checkpoint, stage-final checkpoint, rerun checkpoint, and future image stage that uses the framework-figure workflow. It must not depend on a specific paper, project id, candidate naming scheme, image count, or stage-local filename.

## Core invariant

Every checkpoint is a cumulative restore bundle from the workflow start through the current public stage or internal substage. A checkpoint is invalid if it only contains the current substage output directory while omitting already-existing prior workflow outputs needed to restore the current state.

This invariant applies equally to text-only checkpoints, dynamic image-stage embedded prompt preparation checkpoints, image-generation checkpoints, audit checkpoints, aggregate checkpoints, and stage-final checkpoints. A chunk checkpoint is still cumulative; "chunk" means smaller logical save point, not current-substage-only save.

## Required pre-write inventory

Before writing a checkpoint, the runner must build a generic inventory from:

- workflow state and workflow stage order;
- included roots from the start of the workflow through the current stage;
- current run-directory files under included roots;
- registered active artifacts and generated image events;
- current candidate registries and prompt/image indices;
- previous complete restore checkpoints discovered from `checkpoint_bundles`.

The inventory must be dynamic. It must not hard-code stage names beyond the workflow registry, expected image counts, candidate IDs, prompt filenames, or project-specific paths.

## Previous-checkpoint payload guard

After a previous stage or substage has produced a `complete_restore_ready` checkpoint, every later checkpoint must preserve its project-run payload members that still fall inside the current included roots. Prior checkpoint metadata files such as `checkpoint-manifest.json`, `checkpoint-missing-images.json`, `checkpoint-missing-assets.json`, and `checkpoint-integrity-audit.json` are not inherited; the new checkpoint writes its own metadata.

The checkpoint writer may satisfy this guard by including files from the current run directory or, when necessary, by recovering missing prior payload members directly from previous complete checkpoint zips. This recovery must be generic and path-based, not task-specific.

## Build-validate-repack loop

Checkpoint creation must follow this loop:

```text
1. build cumulative inventory from current run state and previous complete checkpoints
2. pack checkpoint from included roots and recovered prior payload members
3. reopen the zip or zip-part union
4. validate required existing assets, required generated images, and previous-checkpoint payload subset
5. if validation fails and recoverable prior payload exists, repack with recovered payload
6. repeat until valid or record redo_required with exact missing paths
```

A workflow response must not call a checkpoint `complete_restore_ready` unless this loop passes. If validation fails after recovery attempts, the checkpoint may be written only as `redo_required` and the response must surface the missing paths and the next recovery action.

## Mandatory checkpoint-integrity audit member

Every checkpoint zip or zip-part union must include root member:

```text
checkpoint-integrity-audit.json
```

This audit records, at minimum:

- stage and checkpoint type;
- cumulative `checkpoint_stage_list`;
- included roots;
- prior checkpoint payload count;
- recovered prior payload count;
- any prior payload still missing after write;
- required existing asset/image missing counts;
- final verdict.

## Substage-page hard gate

Every substage page that writes or advertises a checkpoint must check the archive after writing. It must not merely report the path of a zip it just created. If the archive is not cumulative, the substage page must either rebuild/repack it or report `redo_required` and not advance to the next public step.

After S5, human decisions are outside this assistant workflow.
