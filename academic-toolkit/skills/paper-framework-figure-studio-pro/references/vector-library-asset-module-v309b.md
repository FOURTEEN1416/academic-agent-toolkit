# Vector Library Asset Module v3.0.9b

This module documents the vector-library assets copied into v3.0.9b. Use it when S4 chooses icon families and when S5 prompts need clean visual objects. In v3.1.6, icon choice is governed by paper meaning and explanatory power first; ease of SVG/PPT redrawing is secondary.

## Package Paths

- Asset root: `assets/vector-library/iclr_reference_library/`
- Index root: `references/vector-library/`
- Canonical icon index: `references/vector-library/icon_canonical_index.jsonl`
- Alias index: `references/vector-library/icon_alias_index.jsonl`
- PPT primitive family index: `references/vector-library/neural_network_ppt_primitive_family_index.json`
- PPT primitive index: `references/vector-library/neural_network_ppt_primitive_index.jsonl`
- Paper-derived motif index: `references/vector-library/paper_derived_motif_index.jsonl`
- Design pattern index: `references/vector-library/design_pattern_library_index.jsonl`
- Layout pattern index: `references/vector-library/layout_pattern_index.jsonl`
- Style taxonomy: `references/vector-library/skill_b_ready_bundle/style_feature_taxonomy.json`
- Starter style token: `references/vector-library/style_tokens/iclr_clean_flat_modular_v1.json`
- v0.6 deep-read/reference-transfer addenda: `references/vector-library/v0.6-deepread/`

## Included Asset Groups

- `icons/`: raw, tight-bbox, and PPT-safe SVG icon variants from the final library.
- `curated_icons/`: curated source-grounded icons when present.
- `icon_cards/`: per-icon metadata cards.
- `neural_network_ppt_primitives/`: PPT-safe neural-network and AI diagram primitives plus cards.
- `paper_derived_icon_cards/`: paper-derived motif metadata cards.
- `paper_derived_icon_refinement/`: refined motif support materials.
- `pptx_icon_catalog/`: browsing/catalog support materials when present.

## Library Coverage

- 691 canonical icons.
- 2313 alias rows.
- 501 neural-network/PPT primitives.
- 100 paper-derived motifs.
- 31 layout patterns.
- 31 design pattern records.
- 2805 high-confidence visual/layout reference rows in the source summary.

## PPT Primitive Families

- `encoder_decoder_architectures`
- `diffusion_model_diagrams`
- `transformer_llm`
- `advanced_rag_memory`
- `agent_tool_planning`
- `attention_context_kv`
- `loss_metric_curves`
- `probability_distribution_plots`
- `state_space_recurrent`
- `tensor_and_matrix`
- `vlm_vla_robotics`
- `atomic_nn_parts`
- `llm_reasoning_decoding`
- `model_compression_serving`
- `cnn_and_vision`
- `frequency_probability`
- `neural_skeleton`
- `ppt_connectors_annotations`
- `training_systems`
- `generative_world_models`
- `gnn_geometric_reasoning`
- `multimodal_fusion_advanced`
- `vision_foundation_models`
- `attention_variants`
- `data_preprocessing_labeling`
- `safety_alignment_eval`
- `scientific_ai_operators`
- `diffusion_generative`
- `graph_geometric`
- `multimodal_fusion`
- `peft_adapter_modules`
- `rl_agent_primitives`
- `training_eval_panels`

## Query Procedure

1. Start from the target paper's semantic role: architecture, pipeline, graph, retrieval, data map, qualitative walkthrough, evidence, or mechanism.
2. Search `icon_alias_index.jsonl` for common wording from the paper, then map to `concept_id` and `icon_id`.
3. Read matching rows in `icon_canonical_index.jsonl` for `recommended_use`, `avoid_use`, `files`, `ports`, and `vector_quality`.
4. For larger model fragments, search `neural_network_ppt_primitive_index.jsonl` by family, tags, aliases, or primitive title.
5. Use `layout_pattern_index.jsonl` and `design_pattern_library_index.jsonl` to choose layout grammar and pattern intent.
6. Use copied SVG files as prompt-grounding references or later manual drawing references only when they express the target paper concept well; do not treat them as target-paper evidence and do not output them as S5 target images.

## Transfer Boundary

The library transfers visual/layout/design structure only. It does not transfer source-paper claims, paper-specific module labels, datasets, metrics, numeric results, theorems, equations, or unsupported symbols.

When a candidate uses a library asset, record:

- `asset_source`: package-relative SVG/index path;
- `semantic_role`: why the icon/primitive is appropriate for the target paper;
- `explanatory_gain`: why this icon/primitive expresses the paper better than a generic shape;
- `target_evidence_anchor`: where the concept appears in the target paper;
- `transfer_boundary`: what is not being borrowed.
