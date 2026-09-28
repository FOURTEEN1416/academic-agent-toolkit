# Narrative / Architecture / Visual Signature Policy

## Purpose

Create compact signatures that summarize each paper and each figure for retrieval and comparison.

## Paper Story Signature

Required fields:

- `reader_question`
- `problem_type`
- `gap_type`
- `core_insight`
- `contribution_type`
- `story_arc`: one of `problem_to_method`, `mechanism_first`, `example_first`, `architecture_first`, `evidence_first`, `failure_to_guardrail`, `comparison_first`
- `desired_reviewer_effect`
- `main_claims`
- `evidence_roles`
- `caption_burden`
- `allowed_reorganization`

## Model Architecture Signature

Required fields:

- `model_family`
- `modality`
- `topology_family`
- `module_roles`
- `training_flow`
- `inference_flow`
- `data_flow_pattern`
- `control_flow_pattern`
- `feedback_loops`
- `loss_or_objective_signals`
- `memory_retrieval_tool_use`
- `main_stage_outputs`
- `expected_module_count`
- `complexity_level`

## Figure Signature

Required fields:

- `figure_subtype`
- `paper_slot`
- `reader_path`
- `layout_grammar`
- `panel_rhythm`
- `module_grouping_strategy`
- `stage_output_visibility`
- `icon_landmarks`
- `arrow_grammar`
- `evidence_treatment`
- `symbol_density`
- `text_density`
- `style_family`
- `vector_buildability`
- `ppt_editability`

## Similarity Semantics

Two figures can be good references even if:

- their colors differ;
- their exact model domains differ;
- their icon sets differ.

They are strong references when they share:

- reader question;
- architecture topology;
- module role sequence;
- stage-output visibility strategy;
- density and reviewer-first clarity.
