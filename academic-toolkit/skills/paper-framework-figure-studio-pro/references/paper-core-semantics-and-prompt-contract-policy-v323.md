# Paper-Core Semantics And Prompt Contract Synthesis Policy v3.2.3

> v3.2.13 override: the assistant workflow ends at S5. This policy applies only to S0-S5 responsibilities and cannot create a assistant stage after S5.


This policy is paper-agnostic. It applies to any research-paper framework figure, method overview, architecture diagram, pipeline figure, system/data-flow diagram, agent workflow, or mechanism explainer. It must never encode role names, module names, variables, datasets, method names, project IDs, file paths, or visual fixes from a particular target paper or uploaded example.

## Purpose

Image prompts must be generated from the current paper's own core thesis, algorithmic backbone, artifact lineage, and evidence-backed connector contract. A candidate card or style lens is not enough to authorize an image prompt. The text-preparation unit must first convert the paper foundation/deep-reading evidence into a generic visual contract, then write the image-only prompt from that contract.

This policy prevents two common failures:

- drawing repeated full workflows for paper-defined entity variants when those variants only differ in input role, condition, sample type, actor type, modality, or index;
- allowing the image model to invent shortcut arrows, control edges, feedback edges, or unsupported intermediate modules because the prompt describes a layout but not a strict semantic edge contract.

## Load Conditions

Load this policy whenever any of the following is true:

- S1 creates first-round sketch cards for a complete-framework or whole-method task;
- S1/S4 embedded prompt preparation compiles image-only prompts;
- S3 review of S2 outputs or `deleted_text_recheck` checks generated candidates;
- S4 transfers S2 risks into formal S5 candidate briefs;
- the current paper includes repeated actors, roles, branches, modalities, agents, entities, views, time steps, samples, model copies, datasets, spaces, or other equivalent entities.

## Required Paper-Core Semantics Lock

Before any image-only prompt is saved or shown, read `references/semantic-graph-prompt-contract-policy-v326.md`, then write a `paper_core_semantics_lock` from the current project's paper evidence. It must be derived from the paper body, algorithms, equations, tables, supplementary material, S0 foundation/deep-reading report, risk register, or author source clarification recorded in S0. It must not be filled from reusable examples or visual intuition.

Required fields:

| Field | Requirement |
| --- | --- |
| `figure_question` | The reviewer question the figure must answer in one sentence. |
| `paper_thesis` | The method/system contribution that the figure must make visually obvious. |
| `paper_defined_entities` | Entity/role/state/condition types defined by the current paper, with source anchors. Use the paper's terms only in the project outputs, not in reusable skill rules. |
| `canonical_backbone` | The minimum ordered operation/update backbone that makes the figure faithful. |
| `artifact_lineage` | Produced artifacts/states and their legal consumers. |
| `control_or_evaluation_signals` | Metrics, scores, gates, controllers, losses, selectors, or update weights and their legal sources/targets. |
| `topology_boundary` | What communicates, what is local, what is shared, what is not shared, and any forbidden coordination/resource implication. |
| `core_modules_and_internals` | Non-droppable modules plus the visible internal tokens needed to avoid empty boxes. |
| `caption_only_items` | Paper facts that support the figure but should not consume pixels. |
| `forbidden_visual_inferences` | Unsupported modules, arrows, hubs, shared resources, labels, or topology claims that the image model must not add. |

If any required field is missing or contradictory for the requested figure scope, block prompt preparation and route back to S0, S1, S4, or author clarification rather than inventing a diagram.

## Role-Flow Separation Gate

For every repeated or variant entity family, create a `role_flow_separation_table` before layout planning.

| Field | Requirement |
| --- | --- |
| `entity_family` | Paper-defined group, role set, actor set, branch set, modality set, time-step family, sample family, model family, or condition family. |
| `semantic_variants` | What differences the paper actually defines. |
| `shared_operations` | Operations all variants perform identically or nearly identically. |
| `variant_specific_operations` | Operations, inputs, outputs, constraints, or updates that differ by variant and have source anchors. |
| `visual_decision` | `context_chips`, `representative_flow`, `compact_comparison`, `separate_branch`, `caption_only`, or `remove`. |
| `why_not_repeated_full_flow` | Why duplicating the whole pipeline would be redundant, or why separate branches are truly necessary. |

Default decision: if multiple paper-defined variants share the same operation chain, draw one representative canonical flow and show the variants as compact context, grouped tokens, braces, mini-table, role strip, or caption note. Multiple full lanes/panels are allowed only when each lane has source-grounded variant-specific operations or when the user's requested figure is explicitly a comparison of those variants and the comparison cannot be made compactly.

A different label, index, color, actor icon, input quantity, or row position does not by itself justify another full pipeline. Distinct role semantics may justify visible role markers; they do not automatically justify cloned workflows.

## Edge Whitelist And Port-Binding Contract

Before image generation, compile a `semantic_graph_spec` and an `edge_whitelist_and_port_contract` from the paper-core semantics lock and the routing plan. The graph spec must separate internal IDs from visible labels: `node_id`, `edge_id`, and `port_id` are non-visible control identifiers, while `display_label` and `visible_edge_label` are the only fields eligible to appear in the figure. The image-only prompt must contain a concise no-extra-edges instruction that follows this contract.

For each allowed edge family, record:

- stable, unique internal edge ID;
- unique internal source element ID and source port/side;
- unique internal target element ID and target port/side;
- edge semantic type: data/artifact flow, model/state update, control/gating, evaluation/score, communication/exchange, dependency, containment, or callout;
- line style and arrowhead rule;
- relation evidence anchor;
- exact direction evidence anchor for directed arrows;
- maximum visible copies or compression cue;
- forbidden alternatives, including shortcut edges, reverse edges, cross-family edges, decorative edges, ambiguous merge/split, and edges into visually convenient but semantically wrong targets.

The image-only prompt must say, in paper-specific project terms: internal graph IDs must not be drawn; draw only the visible text whitelist and display labels; draw only the contracted edge families; do not add unlisted arrows or connectors; if an endpoint is unclear, omit the connector rather than invent a shortcut; keep control/evaluation edges visually distinct from artifact/model-flow edges when the paper distinguishes them.

Generated-image audits must inventory unexpected visible connectors. Any connector that is not in the contract, changes the source/target, changes a port-binding in a meaning-changing way, or implies an unsupported resource/topology/control path is at least `FLAG_MAJOR`; if it changes the paper logic, mark `BLOCKED`.

## Stage-Fidelity Style Gate

Style is a communication layer, not evidence. It must not override stage intent.

- S2 images are first-round framework candidates. Unless the user explicitly asks otherwise, S2 prompts should request clean formal publication-style schematic rendering while preserving exploratory diversity in layout, reader path, density, and detail strategy. Do not call S2 outputs final, selected, or manuscript-ready deliverables; they are formal-looking candidates that still require S3 direction selection and later S4/S5 refinement.
- S5 candidates may use cleaner publication-schematic rendering, but they must inherit S2/S3/S4 risk notes and must not reintroduce previously audited semantic, repetition, or edge failures.
- After S5, human decisions are outside this assistant workflow.

If a style descriptor increases ambiguity, encourages visual cloning, crowds connectors, or makes the image model likely to invent modules or arrows, reject or rewrite the descriptor even if the style is visually attractive.

## S5 Anti-Regression Requirement

S4 and S5 must carry forward a `known_failure_pattern_avoidance` record from S2 audits, user critiques, and risk registers. This record is generic in the skill package but project-specific in outputs. It must name failure categories such as unsupported connector, repeated equivalent full workflow, unverified label, invented module, submodule-dominant layout, detail-panel duplication, style-stage mismatch, or overcrowded routing.

S5 embedded prompt preparation must prove that each formal candidate either removes the failure pattern, contains it with a source-grounded justification, or is blocked. A formal candidate may not be considered prompt-ready merely because it is cleaner or more polished than the S2 sketch if it repeats the same semantic failure.

## Non-Hardcoding Boundary

Reusable skill files may mention only abstract categories such as paper-defined entity types, roles, actors, variants, operations, artifacts, signals, modules, branches, states, and edge families. They must not contain target-paper names, variables, role labels, specific module names, dataset names, example candidate failures, or fixed diagram structures as reusable rules.

Project outputs may use paper-specific terms only after they are extracted from the current paper/S0 evidence and recorded with source anchors. A rule is portable only when it describes how to derive those terms, not what those terms should be.


## v3.2.4 issue-ledger override

Use issue-ledger audit fields for S2/S5-related review outputs: record concrete issues, severity, rerun eligibility, high-priority issue status, downstream use, and caption burden. Hard contradictions become `BLOCKER_ISSUE` records. Do not use pass/fail labels as the sole selection verdict unless the user explicitly requests a filtering/ranking mode.
