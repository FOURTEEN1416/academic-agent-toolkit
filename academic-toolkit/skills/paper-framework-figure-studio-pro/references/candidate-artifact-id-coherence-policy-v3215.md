# Candidate / Artifact ID Coherence Policy v3.2.15f

This policy is paper-agnostic and applies to every S2/S5 image-generation run.
It fixes candidate/image id drift across prompt indexes, generated rasters,
state files, artifacts, outputs, and checkpoint inventories.

## Source of truth

For S2 and S5, the source of truth for candidate identity is the row-level
`candidate_id` inside the active prompt-index:

- `outputs/S2-sketch-explore/prompt-index.json` for S2.
- `outputs/S5-candidate-image/prompt-index.json` for S5.

Default id families are only defaults used before a prompt-index exists:

- S2 sketch candidates: `C01` ... `C04`.
- S5 formal candidates: `F01` ... `F02`.

If a prompt-index uses another safe project-specific id, use that id exactly.
Do not convert S5 formal ids into `Cxx`, do not convert prompt-index ids into
raw numeric ids such as `01`, and do not derive ids from image display order
once a prompt-index exists.

## Required equality chain

For each candidate row, the same candidate id must appear in all of these
places when they exist:

1. `prompt-index.candidates[].candidate_id`.
2. `prompt_path` path segment: `.../candidates/<candidate_id>/...`.
3. `target_image_path` / `active_image_path` path segment: `.../candidates/<candidate_id>/...`.
4. `stage-manifest.json.candidate_ids`.
5. `substage_runs[stage][substage_id].candidate_ids`.
6. `candidate_run_registry.<stage_registry>.<candidate_id>.candidate_id`.
7. target image artifact `candidate_id` field and artifact id suffix.
8. `image_generation_events[].candidate_outputs` keys after registration.
9. S5 row-level `reference_image_paths` records when present.
10. checkpoint `required_image_paths`, `pending_future_image_paths`, and missing-image manifests.

A mismatch is a blocking state-validation error. The correct fix is to update
the stale registry/output/manifest to the prompt-index id, or rerun the upstream
preparation stage to produce a coherent prompt-index. Do not patch by hard-coding
paper names, task names, or one-off candidate ids.

## Prompt-index schema

The canonical prompt-index shape is an ordered list:

```json
{
  "schema_version": 2,
  "stage": "S2-SKETCH-EXPLORE or S5-CANDIDATE-IMAGE",
  "candidate_ids": ["C01"],
  "candidates": [
    {
      "candidate_id": "C01",
      "prompt_path": "outputs/.../candidates/C01/prompt-v01.md",
      "target_image_path": "outputs/.../candidates/C01/image-v01.png",
      "reference_image_paths": ["outputs/S2-sketch-explore/candidates/C01/image-v01.png"]
    }
  ],
  "candidate_map": {
    "C01": {
      "candidate_id": "C01",
      "prompt_path": "outputs/.../candidates/C01/prompt-v01.md",
      "target_image_path": "outputs/.../candidates/C01/image-v01.png"
    }
  }
}
```

Object-shaped `candidates` are accepted only for migration and must be
normalized internally into the ordered list plus `candidate_map`.

For S5 prompt-index rows, `reference_image_paths` must list relevant registered
S2 raster outputs. These paths are image inputs/references, not S5 target
outputs, and must remain project-run-relative. They may point to Cxx first-round
candidate paths while the S5 row keeps its own Fxx `candidate_id`,
`prompt_path`, and `target_image_path`.

If the active generator cannot accept reference images, S5 ignores
`reference_image_paths` automatically. The paths still remain part of the
prompt-index and checkpoint inventory because they document the intended S2
visual reference context.

## Image-generation mapping rule

When an image-generation runtime returns images in display order, map them to
prompt-index rows by the exact prompt-index order. Registration must mirror each
raster byte-for-byte into that row's `target_image_path`. The generated file
name returned by the runtime is provenance, not a candidate id.

## User-facing prompt wording

Suggested prompts should say `请使用 paper-framework-figure-studio-pro skill`.
They should not mention versioned archive filenames, compressed-package wording, or archive-source wording, because that makes users think the file name is part of the workflow contract.
