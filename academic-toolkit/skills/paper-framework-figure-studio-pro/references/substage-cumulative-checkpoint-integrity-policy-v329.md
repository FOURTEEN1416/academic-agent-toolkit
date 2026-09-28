# Substage Cumulative Checkpoint Integrity Policy v3.2.9

This policy is generic and paper-agnostic. It applies to every workflow that uses
After S5, human decisions are outside this assistant workflow.
inactive dynamic image-stage pattern-style custom image stages, and future dynamic text/image stages.

## Non-negotiable rule

A checkpoint created from any substage page is never allowed to be a delta or
current-substage-only archive. Its filename may say `chunk`, `substage`,
`text-prepare`, `image-generate`, `audit`, or `aggregate`, but its contents must
be a cumulative restore snapshot from project state and inputs through the
current public stage or internal substage.

The rule is independent of the paper, task, candidate names, candidate counts,
image names, stage labels, or project id.

## Required cumulative scope discovery

Checkpoint scope must be discovered from machine-readable project state and
manifests, not from hand-coded stage names or prompt text. The builder must:

1. read the active project state file;
2. discover workflow order and output roots from the state workflow plan;
3. include `state/` and `inputs/`;
4. include every output root from completed stages and from the current public
   stage up to the active substage;
5. include all already-existing files under those roots;
6. include generated/registered raster assets that already exist or are marked
   as produced in state, image-generation records, rerun lineages, candidate
   registries, or final-run records;
7. classify future planned but not-yet-generated outputs as pending future
   assets, not missing restore blockers.

Never determine completeness from hard-coded image counts, candidate IDs,
expected filenames, or a fixed sequence such as a particular paper's stage set.

## Mandatory substage page check

Every substage page that writes, links, or registers a checkpoint must run a
checkpoint integrity guard before presenting that checkpoint as usable. The
substage page must write or update a `checkpoint-integrity-report.json` or an
equivalent audit record containing:

- current public stage and optional internal substage id;
- discovered cumulative root list;
- required existing asset count;
- archive member count;
- per-root coverage for every discovered root;
- missing required existing assets, if any;
- pending future assets, if tracked;
- final status: `complete_restore_ready` or `redo_required` diagnostics that trigger step redo.

A checkpoint may be described as complete or restore-ready only when the guard
status is `complete_restore_ready`.

## Loop-and-rebuild behavior

When the guard detects that a single checkpoint zip is missing required existing
assets, the builder should run a bounded validate → rebuild → validate loop:

1. validate archive members against the cumulative inventory;
2. if incomplete and rerun is enabled, rebuild the zip from the cumulative
   inventory rather than from the current substage folder alone;
3. validate the rebuilt zip;
4. repeat up to the configured maximum attempt count;
5. if still incomplete, write exact diagnostics, redo the producing stage/substage, and rebuild until PASS; provide exact
   missing project-run-relative zip paths.

This loop must be bounded. It must not silently claim success after failure.
For split checkpoints, recreate the split set from source or redo the producing stage/substage;
do not patch only one part unless the split policy explicitly supports it.

## Guard script reference

The skill package includes a generic helper:

```bash
python scripts/figure_studio_checkpoint_guard.py \
  --run-dir <project_run_dir> \
  --current-stage <current_public_stage_id> \
  --substage-id <optional_internal_substage_id> \
  --zip <checkpoint_zip_path> \
  --report-path <checkpoint_dir>/checkpoint-integrity-report.json \
  --rerun \
  --max-attempts 2
```

The command is illustrative and generic. It must be parameterized from state,
manifest paths, and runtime configuration. Do not paste project-specific ids,
paper terms, candidate ids, or expected image names into the policy.

## Substage status interaction

If a substage checkpoint fails cumulative integrity:

- do not mark the substage checkpoint `complete_restore_ready`;
- do not use it as the restore handoff for a new session;
- write a missing-assets report;
- either rebuild the checkpoint through the bounded loop or mark the checkpoint
  incomplete with explicit recovery instructions;
- do not advance to a downstream public stage when a required stage-final
  checkpoint is incomplete.

## Relationship to embedded prompt preparation checkpoints

embedded prompt preparation subtasks often know future target image paths before images exist.
Those target images are pending future assets. Their absence does not make the
checkpoint incomplete. However, all existing prompt packages, prompt indexes,
briefs, manifests, audits, guidance files, and earlier-stage outputs must be
inside the checkpoint.

## Relationship to IMAGE_GENERATE checkpoints

After an image-generation substage, generated raster outputs are no longer
future assets. Once registered, generated, or materialized on disk inside the
cumulative scope, they are required existing assets and must be present in the
checkpoint.
