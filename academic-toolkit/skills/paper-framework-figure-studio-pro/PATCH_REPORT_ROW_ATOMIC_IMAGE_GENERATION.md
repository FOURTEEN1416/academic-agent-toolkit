# Patch Report: Row-Atomic S2/S5 Image Generation Guard

## Scope

Generic hotfix for `paper-framework-figure-studio-pro` v3.2.15f. Version metadata remains `3.2.15f`.

## Problem prevented

Image-only S2/S5 stages could be mis-executed as a single broad image-generation call, leaving only one orphan raster while multiple selected/non-skipped prompt-index rows remained unresolved.

## Generic fix

This patch makes S2/S5 target image generation row-atomic:

- one prompt-index row per image-generation call;
- one `candidate_id`, one `prompt_path`, one `target_image_path` per call;
- no multi-row composite, montage, contact sheet, or all-candidate overview image;
- stage completion is blocked until every selected/non-skipped row has a registered raster at its own target path;
- orphan rasters do not count as candidate outputs.

## Modified files

- `SKILL.md`
- `metadata.json`
- `scripts/figure_studio_core/constants.py`
- `scripts/figure_studio_core/substages.py`
- `scripts/figure_studio_core/image_outputs.py`
- `scripts/figure_studio_core/prompt_handoff.py`
- `references/s2-s5-image-only-terminal-orchestration-policy-v3215.md`

## Added files

- `references/s2-s5-row-atomic-image-generation-guard-policy-v3215f.md`
- `scripts/figure_studio_image_only_row_guard.py`

## Validation

- Python script compilation: PASS
- Architecture audit: PASS
- Release absolute-path/cache scan: PASS
- Row-atomic preflight queue generation: PASS
- Multi-image generation-event rejection: PASS
