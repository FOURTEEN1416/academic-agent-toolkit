# S2/S5 Row-Atomic Image Generation Guard Policy v3.2.15f

This policy prevents image-only stages from collapsing a multi-row prompt-index into one generated raster. It is generic and must not contain paper-specific names, module labels, datasets, paths, or candidate semantics.

## Core invariant

For any S2 or S5 image-only stage, the prompt-index selected/non-skipped row set is the source of truth.

Each active row is a separate image-generation unit:

- exactly one `candidate_id`;
- exactly one `prompt_path`;
- exactly one `target_image_path`;
- for S5 only, only that row's `reference_image_paths`;
- exactly one image-generation call/event for that row;
- exactly one active generated raster mirrored to that row's `target_image_path`.

A single image generation call cannot satisfy multiple prompt-index rows, even if the platform supports multiple outputs. Batch-style rendering, contact sheets, tiled comparisons, collages, montages, or all-candidate overview images are invalid target outputs for S2/S5 rows.

## Required execution order

Before S2/S5 image generation:

1. Load the prompt-index.
2. Filter to selected/non-skipped rows.
3. Build an `image-call-queue.json` or equivalent in-memory queue.
4. For each queue unit, lock `candidate_id`, `prompt_path`, and `target_image_path` before calling the image generator.

During generation:

1. Read only the current row's prompt package.
2. Do not activate sibling candidate IDs or titles.
3. Do not ask for multiple candidates in one image.
4. Call the environment-locked image route for this one row only.
5. Save/register the resulting raster to the current row's `target_image_path`.

After generation:

1. Verify every active row target path exists.
2. Verify candidate registry rows point to the same target paths.
3. Verify no pending orphan generated rasters remain outside prompt-index target paths.
4. Verify no identical raster file was reused for multiple candidate rows.
5. Refuse to advance to S3 or terminal S5 completion if any row is missing.

## Orphan raster rule

A generated raster is an orphan when it is not copied/mirrored into a prompt-index `target_image_path` with matching `candidate_id`. Orphan rasters may be mentioned in a repair log, but they are not active candidates, not valid S2/S5 outputs, and cannot be consumed by S3/S4/S5 unless explicitly registered to the correct row.

## Recommended guard command

Use the row guard before and after image-only stages:

```bash
python scripts/figure_studio_image_only_row_guard.py --run-dir figure-studio-runs/<project_id> --stage S2-SKETCH-EXPLORE --mode preflight --write-queue --fail-on-error
python scripts/figure_studio_image_only_row_guard.py --run-dir figure-studio-runs/<project_id> --stage S2-SKETCH-EXPLORE --mode postflight --require-state-provenance --fail-on-error
```

Use `S5-CANDIDATE-IMAGE` for S5.

## Failure response

If only one image was produced for a prompt-index containing multiple selected/non-skipped rows, the stage status is partial failure. Do not enter S3/S4 or claim terminal completion. Resume the image-only stage from the first missing row and complete all remaining row-atomic queue units.
