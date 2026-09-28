# S5 S2 Reference Image Input Policy v3.2.15f

This policy is paper-neutral and applies whenever S4 prepares S5 prompt packages and whenever S5 generates formal candidates.

## Core Rule

S4 must carry relevant registered S2 output images into the S5 handoff as reference-image inputs. These references are visual exploration signals only. They may inform layout essence, visual strengths, and known issues transferred through S3/S4 records, but they must not override the paper text, S0/S1/S3/S4 evidence, source-faithful prompt constraints, or the S3-selected refinement direction.

## S4 Prompt-Index Requirement

Every S5 prompt-index row must include a non-empty `reference_image_paths` list containing project-run-relative paths to relevant S2 raster outputs. Use paths from registered S2 candidate images, normally from `outputs/S2-sketch-explore/candidates/<candidate_id>/image-v01.png` or an equivalent registered active image path.

S4 must also record an S5 reference-image policy block in the prompt-index:

```json
{
  "s5_reference_image_input_policy": {
    "source_stage": "S2-SKETCH-EXPLORE",
    "row_field": "reference_image_paths",
    "use_when_supported": true,
    "ignore_when_unsupported": true,
    "semantic_authority": "reference images are visual preference/exploration signals only; paper/S0/S1/S3/S4 constraints remain authoritative"
  }
}
```

When S3 records explicit preferred first-round candidate IDs, S4 should include each row's preference-led or dominant-source S2 image first, then any absorbed/source-context S2 images that are relevant to that formal candidate. When there is no explicit user preference, S4 should derive relevant S2 references from S3 direction selection, absorbed sources, issue ledger, and exploration aggregate.

## S5 Generation Behavior

S5 must read each candidate row's `reference_image_paths` before generation.

- If the active image-generation route supports image inputs or reference images, provide those S2 images as visual references together with the candidate's text prompt.
- If the route does not support image inputs, cannot attach them safely, or the current runtime exposes only a text prompt interface, ignore the reference-image inputs automatically and continue with the text prompt.
- Ignoring unsupported reference-image inputs is not a workflow blocker and must not trigger a rerun, audit, ranking, repair loop, or post-S5 continuation.
- The generated S5 target images must still be mirrored to each prompt-index row's `target_image_path`.

## Provenance And Checkpoint

Image-generation provenance may record:

- `reference_image_paths`;
- `reference_image_input_status`: `supplied_to_generator`, `ignored_unsupported`, or `not_requested`;
- `reference_image_input_policy`: `use_when_supported_else_ignore`.

Checkpoint and validation logic must treat listed S2 reference images as required existing assets when their containing roots are included in a cumulative checkpoint. Missing listed reference images are a restore blocker for S4/S5 handoff because S5 would otherwise lose its declared visual reference inputs.

## Safety Boundaries

Reference images must not be treated as source evidence for unsupported modules, arrows, variables, topology, data sharing, or visual metaphors. If an S2 image visibly contains an error, S4 must transfer that issue into S5 negative constraints rather than copying the error as a reference target.
