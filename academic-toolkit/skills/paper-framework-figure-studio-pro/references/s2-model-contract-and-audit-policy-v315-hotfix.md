# S2 Model Contract And Audit Policy v3.2.0 + v3.2.11 Edge-Label/Internal-Motif Addendum

After S5, human decisions are outside this assistant workflow.

## Core Rule

S2 is allowed to explore visual rhetoric, layout grammar, story surface, density, and reader path. It is not allowed to explore a different model.

A first-round candidate may simplify visual detail, but it must remain a paper-faithful visual homomorphism of the source-grounded model:

- required paper modules remain present or explicitly scoped out;
- required artifact producers remain the same;
- required connector directions remain the same and have relation/direction evidence;
- required dependency edges remain visibly present when the contract says they must be drawn;
- connector instance counts remain within the contracted min/max cardinality;
- forbidden edges, merges, splits, and feedback loops remain absent;
- repeated artifact copies are either avoided or explicitly marked as same-instance, sampled-subset, same-distribution, or conceptual proxies;
- carried variables and metrics stay on contracted edges/ports/forks/merges unless an artifact-glyph exception is recorded;
- required core modules show internal visual motifs rather than title-only boxes or bullet lists;
- model-space, data-space, and context roles are not swapped.

If the generated sketch's graph is not isomorphic enough to the paper model at the planned abstraction level, it is a semantic failure even when it looks visually promising.

## S1 Model Contract Requirements

Every S1 sketch candidate card must include these fields in addition to connector provenance and lineage locks:

- `sketch_model_contract`: the candidate's source-grounded model skeleton as nodes and legal edges.
- `sketch_required_node_inventory`: required visible nodes with node ID, paper meaning, source evidence anchor, required/optional status, and whether the item should be a visual node, an edge/port label, a labeled fork/merge, a justified artifact glyph, or caption-only.
- `sketch_optional_context_nodes`: context-only nodes/glyphs/labels that may orient the reader but must not behave as producers or consumers in the method graph.
- `sketch_layout_skeleton_contract`: the intended spatial grammar, lane/panel order, and reader path, including which regions are core, bridge, context, and caption-only.
- `sketch_port_binding_table`: allowed input/output ports for high-risk nodes such as source-defined producers, selectors, generators, samplers, evaluators, aggregators, memories, score modules, update modules, or any paper-defined component whose incoming/outgoing relation can be misread.
- `sketch_adjacency_allowlist`: the only node adjacencies and connector endpoints that may appear in the generated sketch; every directed edge must include relation evidence and exact direction evidence.
- `sketch_forbidden_topology`: forbidden structural patterns such as unsupported hubs, artifact-sharing bridges, feedback loops, pre-module merges, unregistered cross-lane shortcuts, shared-resource branches, or any role/topology pattern that S0 or the target paper rules out.
- `sketch_simplification_contract`: what may be collapsed, replaced by an icon, moved to a mini-map, written on a connector/port, or carried by caption, and what must remain as visible pixels.
- `sketch_edge_cardinality_contract`: min/max visible instances for each connector and whether parallel duplicates are forbidden.
- `sketch_dependency_edge_must_show`: dependencies that must be drawn as visible arrows with clear arrowheads at the correct target port.
- `sketch_compound_input_policy`: whether each multi-input module uses direct input arrows, one merge gate, or a grouped label only.
- `sketch_artifact_replica_policy`: whether repeated artifact copies are allowed and how primary/replica semantics are marked.
- `sketch_visible_edge_inventory_template`: the post-generation edge inventory S2 must fill before accepting the sketch.
- `sketch_line_carried_variable_registry`: carried variables/metrics/weights/parameters and their connector/port/fork/merge labels.
- `sketch_internal_visual_motif_plan`: required visual micro-motifs inside source-grounded core compound modules.
- `sketch_source_audit_ledger`: the pre-image evidence ledger for visible nodes, text, symbols, formulas, style semantics, connectors, arrows, and detail panels.
- `sketch_detail_panel_new_information_plan`: parent anchor, new source-grounded information, non-repetition proof, foreign-module exclusion, and callout-vs-data-flow line style for each detail panel or zoom.
- `sketch_model_fidelity_audit_plan`: exact post-generation checks that determine pass, rerun, regenerate, or return-to-S1.

If any of these fields are missing for a candidate, S2 must not generate that sketch. Rerun S1 first.

## Contract Sheet Before Image Generation

Before calling the environment-locked image-generation route in S2, compile each S1 card into a short `s2_pre_image_contract_sheet` entry. It must be concise enough to guide the model and strict enough for audit:

```text
Candidate ID:
Sketch scope:
Required visual node inventory and edge-label terms:
Allowed edges with relation evidence and direction evidence:
Required dependency edges:
Edge cardinality:
Allowed ports:
Compound input encoding and line-carried variable labels:
Artifact primary/replica rules and artifact-glyph exceptions:
Forbidden topology:
Area budget and internal motif budget:
Prompt-ready verdict:
```

The selected image prompt must be derived from this contract sheet, not from a loose prose description. Avoid open instructions such as "show the complete workflow", "connect the modules", "show interactions", or "add arrows to indicate flow" unless the allowed edges and forbidden arrows are listed immediately after them. The prompt must prefer omitting uncertain connectors over inventing plausible-looking arrows.

## Node And Port Binding

For every high-risk module, S1 must bind ports before S2:

```text
node_id:
  allowed_inputs:
  allowed_outputs:
  forbidden_inputs:
  forbidden_outputs:
  internal_visual_motifs_required:
```

The generated sketch must route connectors to those ports. If the image-generation model attaches an arrow to the wrong side, to the wrong module, through a label, or to an unrelated icon such that a reader could infer a different input/output relation, audit fails.

## Layout Skeleton Contract

The layout skeleton is not merely aesthetic. It protects model meaning. S1/S2 must state:

- reader order;
- primary lane/panel order;
- which lane carries data-space operations;
- which lane carries model-space operations;
- where lineage bridges may cross lanes;
- where context is allowed;
- which visual neighbor relations are purely spatial and must not be interpreted as arrows.

For multi-space or multi-path papers, a generated sketch fails if the layout swaps spaces, lets context become the main body, makes a bridge look like a producer, or hides a paper-primary path/space as a decorative footer.

## S2 Prompt Compilation Rule

The S2 prompt must include a compact form of:

- required modules and their order;
- allowed arrows with source and target;
- required arrows that must be visibly drawn;
- maximum visible instances for each high-risk arrow;
- forbidden arrows and forbidden topology;
- module port constraints for high-risk nodes;
- compound input encoding for every multi-input module;
- line-carried variable rendering for every pass-through artifact, metric, weight, parameter, and pseudo-output;
- internal visual motifs required for every core compound module;
- instruction not to satisfy core internals with bullet lists;
- primary versus replica marking for any repeated artifact;
- allowed simplifications;
- instruction to omit uncertain connectors;
- instruction not to add decorative or explanatory arrows.

The prompt should reduce candidate complexity before it relaxes model fidelity. If the contracted model cannot fit in the selected first-round surface, simplify visual style, reduce repeated entities, or use a mini-map. Do not simplify by dropping a core producer, reversing a connector, or hiding required internal substeps.

## Post-Generation Model Fidelity Audit

After each S2 image, audit these items before saving/registering it as a usable candidate:

- `node_inventory_pass`: required visual nodes are visible or validly scoped out; edge/port-label terms are not promoted to unapproved nodes.
- `edge_allowlist_pass`: every visible arrow has a matching allowed edge.
- `edge_cardinality_pass`: each connector appears no fewer or more times than allowed; parallel duplicates fail unless explicitly contracted.
- `dependency_visibility_pass`: every must-show dependency edge is visible, continuous enough to read, and has an arrowhead at the contracted target port.
- `edge_direction_pass`: every visible arrow points in the contracted direction.
- `port_binding_pass`: high-risk module inputs/outputs attach to legal ports.
- `forbidden_topology_pass`: no S0-forbidden hub, artifact-sharing bridge, shared-resource branch, unsupported feedback, unregistered merge/split, or decorative connector changes the model.
- `lineage_pass`: high-risk artifacts have legal incoming producers and legal outgoing consumers.
- `compound_input_pass`: multi-input modules use the contracted representation and do not turn grouped labels into unregistered semantic nodes or duplicate direct arrows.
- `artifact_replica_pass`: repeated artifact copies are marked as primary/replica/proxy as contracted and do not imply extra producers, extra pools, same-instance reuse, shared evaluation sources, or other S0-forbidden lineage relations.
- `core_internal_pass`: core modules are not empty, title-only, or bullet-list-only boxes when internal visual motifs are required.
- `edge_label_first_pass`: carried variables/metrics/weights/parameters are drawn on contracted edges/ports/forks/merges rather than as unapproved standalone chips/boxes.
- `area_budget_pass`: context/background does not crowd out core model structure.
- `scope_label_pass`: scoped probes are visibly scoped and include required mini-map/context.

If `edge_allowlist_pass`, `edge_cardinality_pass`, `dependency_visibility_pass`, `edge_direction_pass`, `port_binding_pass`, `forbidden_topology_pass`, `lineage_pass`, `compound_input_pass`, `artifact_replica_pass`, or `edge_label_first_pass` fails, do not mark the sketch as clean. By default, assign a flagged/blocked status and carry the risk into the report. Regenerate only when the user pre-authorized one S2 rerun before generation; that rerun overwrites the candidate's registered active image path and is followed by one terminal review. Rerun S1 when the prompt contract itself is broken. If `core_internal_pass`, `edge_label_first_pass`, or `area_budget_pass` fails and rerun was not pre-authorized or already used, keep the sketch only as a flagged candidate.

## S2 Completion Rule

S2 should prefer completing with the required number of clean `PASS` sketches, or `REVISED_PASS` sketches only when rerun was pre-authorized. If the image generator cannot satisfy a candidate, the sketch may still be registered with `FLAG_MINOR`, `FLAG_MAJOR`, or `BLOCKED` status under `references/s0-foundation-readiness-and-candidate-status-policy-v316.md`. Flagged sketches can travel to S3 only with their risk notes. `FLAG_MAJOR` sketches are visual-direction references, not clean model evidence; `BLOCKED` sketches should not be selected unless the user explicitly overrides.

If the available image generator repeatedly ignores the contract for a candidate, do not keep asking for the same image. Simplify the contract or return to S1. The workflow should prefer fewer, clearer legal arrows over a visually rich but false model.

## Portable Use Across Papers

This policy applies to any paper figure with a method graph, architecture, pipeline, multi-agent flow, retrieval chain, planner/verifier loop, generated or retrieved artifact, memory, scoring module, optimizer, topology constraint, deployment setting, or other paper-defined role/flow structure.

The general rule is: first lock the paper model, then draw a sketch. A sketch that looks good but changes the model is not an exploration result; it is a failed sample.


## v3.2.4 issue-ledger override

Use issue-ledger audit fields for S2/S5-related review outputs: record concrete issues, severity, rerun eligibility, high-priority issue status, downstream use, and caption burden. Hard contradictions become `BLOCKER_ISSUE` records. Do not use pass/fail labels as the sole selection verdict unless the user explicitly requests a filtering/ranking mode.
