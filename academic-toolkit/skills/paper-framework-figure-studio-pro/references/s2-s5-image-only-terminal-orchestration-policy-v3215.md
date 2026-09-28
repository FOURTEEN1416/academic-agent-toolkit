# S2/S5 Image-Only Terminal Orchestration Policy v3.2.15f

This policy defines the active image-only stage behavior.

## Canonical workflow

```text
S0-PAPER-FOUNDATION
  ↓
S1-FIGURE-STRATEGY + S2 prompt-package preparation duties
  ↓
S2-SKETCH-EXPLORE / IMAGE_GENERATE only
  ↓
S3-DIRECTION-SELECT + S3 review/aggregate duties over S2 outputs
  ↓
S4-CANDIDATE-BRIEF + S5 prompt-package preparation duties
  ↓
S5-CANDIDATE-IMAGE / IMAGE_GENERATE only
  ↓
END — human decision boundary
```

## Invalid units

The following units are not valid public-stage substages in v3.2.15f:

- S2 text-planning substage.
- S2 candidate image rerun.
- S2 candidate review.
- S2 text aggregate checkpoint substage.
- S5 text-planning substage.
- S5 text review substage.
- S5 candidate image rerun.
- S5 candidate review.
- S5 text aggregate checkpoint substage.
- Any assistant workflow after S5.
- Any finalization, final selection, final audit, caption text outside the assistant workflow, or final rerun loop.
- Any inactive dynamic image-stage pattern/future-image-stage parity rule based on the inactive text-image substage model.

## Mandatory responsibility relocation

S1 MUST perform the S2 prompt-package preparation responsibilities before closing S1:

- sketch candidate registry;
- S2 prompt packages and prompt-index;
- layout/routing/edge contracts;
- source-grounded text whitelist;
- line-carried variable registry;
- semantic graph versus visual render graph split;
- core-module internal visual motif plan;
- prompt contradiction audit;
- S2 image-generation handoff prompt.

S3 MUST perform the S3 review/aggregate responsibilities over S2 outputs before or as part of direction selection:

- inspect registered S2 sketches;
- write issue-ledger and visual signal summaries;
- record semantic, connector, hierarchy, density, and core-visibility problems;
- create an S2 exploration aggregate inside the S3 report/checkpoint;
- select the refinement direction after this review.

S4 MUST perform the S5 prompt-package preparation responsibilities before closing S4:

- formal candidate matrix;
- S2 issue-to-S5 risk transfer;
- S2 reference-image input plan for S5, with row-level `reference_image_paths` pointing to relevant registered S2 raster outputs;
- S5 prompt packages and prompt-index;
- formal layout/routing/arrow contracts;
- formal visible text whitelist;
- line-carried variable registry;
- internal visual motif plan;
- prompt contradiction audit;
- S5 image-generation handoff prompt.


## Candidate id coherence

S2/S5 image-only stages must apply `references/candidate-artifact-id-coherence-policy-v3215.md`.
The prompt-index row-level `candidate_id` is the source of truth for:

- prompt paths;
- target image paths;
- stage manifests;
- substage `candidate_ids`;
- candidate registry keys;
- artifact ids and artifact `candidate_id` fields;
- image-generation event `candidate_outputs`;
- checkpoint image inventory.

Default families are `C01`-`C04` for S2 and `F01`-`F02` for S5. These defaults must not override a validated prompt-index with the same stage count.

## Image-only stage behavior

S2 and S5 are image-only public stages. They must execute prompt-index rows as row-atomic image-generation units. A row-atomic unit contains exactly one active `candidate_id`, one `prompt_path`, one `target_image_path`, and only that row's allowed reference inputs.

S2 and S5 must:

- read the already-prepared prompt-index;
- create or obey an image-call queue over every selected/non-skipped row;
- issue exactly one image-generation call per queue unit;
- for S5 only, read each row's `reference_image_paths` and use those S2 raster images as visual references when the active image route supports image inputs;
- for S5 only, ignore `reference_image_paths` automatically when the active image route cannot accept image inputs, without blocking generation or creating a review/rerun loop;
- generate only the requested raster candidates through the environment-locked image route: exactly 4 for S2 and exactly 2 for S5 unless the validated prompt-index defines a safe selected/non-skipped row set;
- preserve the exact prompt-index `candidate_id` for every generated image;
- mirror active generated images into the same prompt-index row's `target_image_path`;
- record generation provenance for each row-atomic event;
- treat the stage as incomplete until every selected/non-skipped row has a registered raster at its own `target_image_path`.

A single broad prompt, multi-image request, contact sheet, montage, collage, tiled output, sibling comparison panel, or all-candidate summary image cannot satisfy multiple prompt-index rows. A generated raster stored only in a default image location, or not mirrored to the row target path with the same candidate id, is an orphan and must not be considered an active candidate.

S2 and S5 must not:

- write text plans;
- write audits;
- write rankings;
- write rerun guidance;
- rerun or review images;
- create aggregate checkpoint narratives;
- create final captions or final handoff prompts;
- continue into any assistant workflow after S5.

## Terminal response rule

After S5 candidate generation, the assistant workflow is complete. If asked what comes after S5, the response must be:

```text
我的任务已经完成，剩下由人类来决策。
```
