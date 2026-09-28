# Source-Faithful Image Prompt Audit And Symbol Disambiguation Policy v3.2.15f

This policy is mandatory whenever S1 prepares S2 prompt packages, S4 prepares S5 prompt packages, or any upstream text stage creates image-generation instructions for a paper framework figure.

## Non-contradiction rule

No image-generation prompt may include an entity, module, role, variable, metric, formula, symbol, visible label, connector, arrow direction, port, fork/merge, topology, data flow, model flow, control flow, evaluation flow, generation relation, aggregation relation, training relation, or visual metaphor that contradicts the paper, supplement, user-provided source material, S0 deep-reading report, or risk register.

## Evidence or strict inference only

Every planned visible entity and every planned relation/line must be classified as exactly one of:

- `direct_source`: explicitly supported by a source anchor such as paper section, equation, algorithm, table, figure caption, supplement, user material, or S0 foundation report;
- `strict_logical_inference`: not directly drawn, but derived from source-supported premises through a short recorded inference chain;
- `revise`: currently ambiguous or underspecified and must be rewritten before image handoff;
- `remove`: unsupported, decorative, misleading, or contradictory and must be deleted before image handoff.

`revise` and `remove` entries block S2/S5 handoff. Visual convenience, common diagram conventions, or likely image-model behavior are not evidence.

For S5, S2 output images listed in `reference_image_paths` are visual
exploration/preference references only. They are not source evidence for new
modules, arrows, variables, topology, raw-data movement, or visual metaphors.
If an S2 reference image contains a visible problem, S4 must transfer the issue
into S5 negative constraints instead of treating the erroneous visual element as
authoritative.

## Symbol and label disambiguation

Symbols must not be mixed or overloaded. The same glyph, letter, color, line style, edge label, icon, or visual token must not refer to multiple paper concepts unless the prompt explicitly defines a source-supported aggregate/group and confirms no semantic loss. Distinct paper concepts must not be collapsed into one symbol if that changes a reviewer’s interpretation.

Variables, metrics, weights, thresholds, probabilities, losses, accuracies, model parameters, and pass-through artifacts are edge-label-eligible by default. They should appear on connectors, ports, forks, merges, or compact tags rather than as peer module boxes unless a source-supported exception is recorded.

Every carried item must also name its true consumer or transformer. Do not draw a false relay data-flow through a visually intermediate module that does not consume, transform, filter, store, route, evaluate, update, or emit that item. If A produces `x` and C consumes `x` while B does not use `x`, do not draw A->B labeled `x` or A->B->C as if B relays it; route the label to the true consumer/transformer, attach it to a true input/port/tag, or move it to caption/legend.



## S0 Semantic Precision Consistency

S1/S4 prompt audits must compare planned role/actor/condition representation against `outputs/S0-paper-foundation/s0-semantic-precision-contract.json`. A prompt contradicts the source-faithfulness audit if it turns an S0 compact-marker/shared-flow decision into duplicated full workflows, lanes, or repeated complete pipelines. Vague S0 wording is not evidence for multiplicity; only the S0 semantic precision contract and source-grounded repair records can authorize branch-only, parallel, or comparison lanes.

## Prompt package outputs

Each S1/S4 prompt package must include:

- `source_faithfulness_audit` for visible entities and relation/line plans;
- `strict_logical_inference_ledger` for inferred relations;
- `symbol_disambiguation_audit` for glyphs, variables, labels, color semantics, line styles, and visual tokens;
- `data_consumer_transformer_ledger` and `false_relay_data_flow_audit` for carried items and connector endpoints;
- `prompt_contradiction_audit` that blocks handoff on contradictions, unsupported arrows, reversed directions, symbol collisions, label drift, or violation of S0 semantic precision locks.
- `s0_semantic_precision_consistency_audit` for role/actor/condition representation, process instance budget, and forbidden misimplementation locks.

The audit/repair loop is bounded to five cycles. If blockers remain, stop at a textual checkpoint plus residual-risk ledger rather than entering S2/S5 image-only generation.
