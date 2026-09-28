# Paper-Derived Semantic Backbone And Non-Hardcoded Compression Policy v3.2.3

This policy is paper-agnostic. It must never encode method names, actor names, module names, datasets, project IDs, paths, or example-specific labels from any current or previous paper. All concrete names used in a project output must be extracted from that project's paper, S0 deep-reading/foundation report, author source clarification, S1/S4 contracts that cite source evidence, or user preference when it only changes style/emphasis.

After S5, human decisions are outside this assistant workflow.

## Why This Policy Exists

Framework figures often fail when a style template, layout archetype, or generated candidate silently replaces the paper's actual contribution. Typical failures include repeated full lanes for actor types that only differ by context, prompt-level connector lists copied from an example paper, polished blueprint output in a rough-sketch exploration stage, and generated arrows or modules that look plausible but have no source evidence.

The reusable skill must therefore derive the figure contract from the current paper's semantic backbone before choosing a layout or prompt. Do not encode the current paper's roles, modules, or edges as skill-level rules.

## Required Semantic Spine Contract

Before any S2/S5 image-only prompt is shown or saved, the text-preparation unit must write and audit a `paper_semantic_spine_contract` with these fields:

| Field | Requirement |
| --- | --- |
| `source_priority` | The current paper text, equations, algorithms, tables/figures when allowed, supplement, S0 deep-reading/foundation report, and author source clarification are sources of truth. Generated images, style boards, and earlier visual candidates are never scientific evidence. |
| `figure_thesis` | One sentence stating what the current figure must make the reviewer understand about this paper. |
| `core_claims_to_show` | Paper-primary mechanisms, spaces, paths, states, actors, constraints, or update targets that must be visible for this figure role. Names are project-derived only. |
| `canonical_workflow_spine` | The minimal ordered chain or graph of source-supported states/operations that preserves the paper's method meaning. Use project-specific labels only in project artifacts. |
| `actor_or_condition_variation_matrix` | Repeated entities or conditions; what differs between them; whether the difference changes the workflow, only changes inputs/context, or belongs in caption/legend. |
| `shared_vs_distinct_flow_decision` | For every repeated entity/condition family, choose one of: `representative_shared_flow`, `branch_only_where_distinct`, `parallel_lanes_required`, `comparison_lanes_required`, `topology_or_context_inset_only`, or `caption_only`. Record source evidence and why. |
| `edge_source_contract` | A project-derived connector allowlist with source element, target element, semantic relation, arrowhead direction, target port, cardinality, and evidence anchor. This table is generated from the current paper/S0/S1/S4; the reusable skill must not provide paper-specific edges. |
| `style_stage_contract` | The required rendering mode for the current stage and user preference, including whether S2 must be rough exploratory sketch, whether a polished schematic is allowed, and what text/density limits apply. |
| `known_false_inferences` | Misreadings the figure must prevent, based on paper evidence, S0 risk register, previous audits, or user critique. |

If this contract is absent, incomplete, or based mainly on a layout/style idea rather than source evidence, prompt preparation must block or rerun the text contract before image generation.



## S0 Semantic Precision Source Rule

S1/S4 semantic spine preparation must consume the S0 semantic precision contract when it exists:

```text
outputs/S0-paper-foundation/s0-semantic-precision-contract.json
```

The S0 contract is the upstream source for role/actor/condition variation decisions. S1/S4 must not reinterpret vague S0 language such as "preserve role differences" as permission to duplicate full pipelines. If S0 says a repeated entity family shares the canonical workflow or forbids full-flow repetition, the prompt package must preserve that restriction unless a later source-grounded repair explicitly updates the S0/S3/S4 record.

If S0 contains a high-risk vague directive but the semantic precision contract is missing or incomplete, S1/S4 must stop and rerun or repair S0 before preparing image prompts.

## Non-Hardcoded Role And Process Representation

Do not write reusable rules for a specific paper's actor labels, module names, or edges. Instead, apply this decision procedure to the current project's `actor_or_condition_variation_matrix`:

1. If repeated entities share the same source-supported operation sequence and differ only by input availability, initial condition, local context, access/boundary constraint, modality, index, or quantity, draw one representative shared flow and encode the differences as compact role/context chips, a small table, grouped tokens, braces, ellipses, or caption text.
2. If repeated entities share common prefixes/suffixes but diverge in a source-supported operation, draw the common part once, branch only at the distinct operation, then merge again when the source-supported workflow reconverges.
3. If the paper's contribution is a direct comparison between roles/conditions/modes and the differences cannot be understood through a shared flow, parallel lanes are allowed, but only for the distinct segments that add source-grounded information. Common segments must still be compressed.
4. If exact multiplicity, topology, sequence length, or instance layout is part of the paper's claim, show it as a compact context/topology inset or controlled comparison, not as repeated full pipelines unless the full pipeline itself differs by instance.
5. If the reason for repetition is merely visual symmetry, candidate diversity, or a style-board pattern, collapse it.

A generated image or prompt fails when it repeats full workflows for multiple entities without a source-grounded distinct-flow decision proving that each copy changes the reader's understanding.

## Project-Derived Edge Whitelist And Port Binding

A reusable policy may require an edge whitelist, but must not contain the current paper's edge list. For each project, S2/S5 text preparation must derive `edge_source_contract` from source evidence.

The image-only prompt must include a concise project-specific allowed-edge section when arrows matter:

```text
Allowed directed connectors are only the connectors listed in the current prompt package's edge_source_contract. Do not invent additional arrows, shortcuts, feedback loops, exchange lines, or decorative connectors. If a relation is only an association, draw a non-arrow grouping or omit the connector.
```

For high-risk connectors, the prompt must specify ports and cardinality in natural language: one arrow per connector family unless the project-derived contract allows multiple instances; arrowhead must land on the target module/state; compound inputs must use the contracted representation (`direct_ports`, `merge_gate`, or `grouped_label_only`).

During audit, every visible connector must match the current project's edge contract. If a visible connector cannot be matched with low ambiguity, mark the candidate `FLAG_MAJOR` or `BLOCKED` according to severity.

## S2 Sketch-Mode Style Contract

S2 explores design hypotheses. By default, S2 image prompts should request a formal publication-style schematic surface: clean academic layout, crisp hierarchy, readable labels, precise connector routing, and restrained color. Do not request glossy poster, photorealistic, cinematic, dense dashboard, or decorative rendering in S2. If the user selects a rougher compatible style, still preserve source-grounded structure, arrow safety, and paper-serving diversity.

If the user explicitly requested hand-drawn/sketch style, S2/S5 prompts and audits must carry a `style_stage_contract` and block outputs that turn into polished vector schematics unless the user later changes preference.

S5 may be cleaner and closer to publication style, but it must not inherit S2 visual faults. It must preserve the user-selected direction only after a semantic fault scrub.

## Post-S5 Boundary Removed In v3.2.13

After S5, human decisions are outside this assistant workflow.

- `carry_forward_visual_choices`: layout grammar, grouping, emphasis, rough style, icon family, or other visual traits that are compatible with evidence;
- `carry_forward_semantic_choices`: only those modules, labels, connectors, and repetitions that match the paper-derived contracts;
- `exclude_or_rerun_faults`: unsupported modules, invented labels, wrong arrows, duplicated equivalent lanes, misleading topology, repeated labels/legends, and style mismatches observed in earlier generated images.

After S5, human decisions are outside this assistant workflow.

## Prompt Audit Additions

Add these checks to `prompt_hallucination_audit` for S2/S5:

- `semantic_spine_check`: the prompt's layout and reader path follow the current paper's `figure_thesis` and `canonical_workflow_spine`, not a generic template.
- `role_variation_check`: repeated actors/conditions are represented according to the `shared_vs_distinct_flow_decision`; no full-flow repetition appears without a source-grounded reason.
- `edge_contract_check`: the prompt's connectors are exactly the current project's derived edge contract; no example-paper edge whitelist or reusable fixed connector sequence is present.
- `style_stage_check`: S2 is rough exploratory unless an explicit current-project reason allows a cleaner style; user-requested sketch/hand-drawn style is preserved.
- `candidate_inheritance_check`: selected prior images are treated only as visual references; audited semantic faults are excluded.

A prompt cannot be `PROMPT_READY` if any of these checks fail.

## Image Audit Additions

S2/S5 image audits must mark `FLAG_MAJOR` or `BLOCKED` when the image:

- repeats equivalent full pipelines or lanes that the current project's role/condition matrix classified as shared or context-only;
- adds a module, state, label, score, test/evaluation object, data pool, coordinator, or interaction not present in the source-grounded contract;
- draws a directed connector outside the project-derived edge contract, connects to the wrong port, duplicates an edge beyond cardinality, or changes the source/target relation;
- uses a polished/production schematic style when the active stage contract required rough sketch or hand-drawn exploration;
- makes an attractive but false visual interpretation appear more central than the paper's actual mechanism.

If rerun is authorized, the rerun instruction must target the contract violation directly: replace repeated lanes with the contracted shared/branched representation, remove unsupported edges/modules, and restore the stage style contract. Do not merely shrink, rearrange, or caption-patch a false topology.

## Portability Guard

Never add target-paper examples to this policy. When a project needs concrete role names, module names, variables, edge lists, or forbidden false inferences, put them in that project's S0/S1/S2/S3/S4/S5 artifacts, not in the reusable skill package.


## v3.2.4 issue-ledger override

Use issue-ledger audit fields for S2/S5-related review outputs: record concrete issues, severity, rerun eligibility, high-priority issue status, downstream use, and caption burden. Hard contradictions become `BLOCKER_ISSUE` records. Do not use pass/fail labels as the sole selection verdict unless the user explicitly requests a filtering/ranking mode.
