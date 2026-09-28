# Contribution-Type Visual Priority Policy v3.2.15f

This policy is mandatory whenever S1 prepares first-round framework strategies, S3 reviews generated candidates, or S4 prepares formal image prompts. It is paper-neutral and must not encode any project-specific method, dataset, variable, topology, or user preference as a reusable rule.

## Core Rule

A research-paper framework figure should organize its main visual path around the paper's primary contribution type, not around whichever entities or variables are easiest to draw.

The figure's first job is to help reviewers quickly understand the reader-critical contribution mechanism: what problem condition exists, what the paper adds, how the core modules cooperate, and why the design matters. Data, variables, losses, weights, metrics, and temporary artifacts should support that explanation rather than dominate it unless the contribution itself is data-centered.

## Contribution-Type Gate

S1 and S4 must classify the paper's primary contribution before writing image prompts:

- `method_process`: training strategy, optimization procedure, algorithmic sequence, feedback loop, or coordination mechanism;
- `architecture_module`: model structure, network component, module interaction, or representation layer;
- `system_interaction`: distributed system, protocol, actor interaction, communication topology, or execution environment;
- `model_state_update`: state evolution, parameter update, memory update, convergence cycle, or multi-round learning loop;
- `data_dataset_database_pipeline`: dataset construction, database/data management, retrieval, data generation, data governance, data cleaning, or data-processing pipeline;
- `evaluation_benchmark`: benchmark protocol, evaluation suite, metric design, or experiment orchestration;
- `hybrid`: multiple contribution layers where one primary reader question must still be chosen as the visual mainline.

The prompt package must record:

```yaml
contribution_type_visual_priority:
  primary_type: method_process | architecture_module | system_interaction | model_state_update | data_dataset_database_pipeline | evaluation_benchmark | hybrid
  secondary_types: []
  primary_reader_question: <one reviewer question the figure must answer first>
  visual_mainline_decision: mechanism_process | architecture_module_map | role_interaction | model_state_cycle | data_flow_pipeline | evaluation_protocol | hybrid_layered
  data_flow_mainline_justification: source_supported | not_primary | prohibited_without_source | hybrid_supporting_layer
  support_evidence_anchor: <paper/S0/S1/S3/S4/user-source anchor>
  required_supporting_data_labels: []
  max_data_label_budget: <small integer or caption_only>
```

## When Data Flow May Be The Mainline

Data flow may be the main visual backbone only when source evidence shows that the contribution is explicitly about data construction, database/data management, retrieval, data generation, data governance, data cleaning, or data-processing pipeline design.

If the contribution is primarily a method process, model architecture, system interaction, optimization mechanism, aggregation rule, or model-state update, data-related elements must normally be downgraded to one of these roles:

- edge label;
- port label;
- fork/merge tag;
- compact local note;
- small supporting layer;
- caption-supported item;
- omitted when not reviewer-critical.

Do not use a data-flow pipeline as the default layout for method papers merely because input data exists, datasets are named, or intermediate variables are available.

## Main Node And Label Rules

Main modules should name mechanisms, actions, states, roles, or source-defined components. Avoid making the primary modules a list of variables, datasets, losses, metrics, or intermediate artifacts unless those items are themselves the contribution objects.

Good main-node roles include:

- selection, alignment, generation, verification, adaptation, aggregation, update;
- encoder, predictor, memory, generator, client, server, coordinator, evaluator;
- round state, local model, global model, consensus state, retrieval index, benchmark task when source-supported.

Edge-label-eligible items include:

- datasets and samples used only as inputs;
- pseudo-labels, features, scores, thresholds, losses, gradients, weights, accuracies, model parameters;
- temporary artifacts, masks, confidence values, routing keys, and update quantities.

## Candidate Diversity Requirement

S1 first-round candidates must vary the reader question or narrative lens, not only the visual layout. A valid four-candidate set should test complementary ways to explain the paper, such as:

- end-to-end contribution process;
- core mechanism close-up within the full framework;
- actor or system interaction;
- model-state or multi-round update cycle;
- architecture/module map;
- problem-to-solution causal path;
- data-flow pipeline only when source-justified.

Reject or rewrite any candidate whose difference is mostly decorative, color-only, or simply a rotated version of the same data pipeline.

## Layout And Whitespace Sanity

Prompt packages must state that whitespace supports the reading path. The figure should not contain oversized side panels, duplicated legends, variable inventories, dense callout blocks, or empty regions that imply false importance.

Use 4-6 major visual modules by default for framework overviews. More modules require a recorded reason tied to source-defined primary components or reader-critical mechanism steps. If data labels or variables would force crowded layout, move them to edges, ports, tags, caption, or remove them.

## Required Audit Findings

During S1/S4 preparation, record blockers or repair items when:

- `visual_mainline_mismatch`: the visual backbone does not match the contribution type or primary reader question;
- `data_flow_overdominance`: data-flow elements dominate a non-data-centered contribution;
- `variable_inventory_layout`: variables, metrics, losses, or datasets become the apparent main modules;
- `supporting_data_overlabeling`: data labels exceed what reviewers need to understand the innovation;
- `unbalanced_whitespace`: layout spacing makes support material look more important than the core contribution;
- `reader_question_unclear`: the candidate cannot state the one reviewer question it answers first.

During S3 review, carry these findings into the issue ledger and transfer them into S4 negative constraints. A user preference for a visually appealing candidate does not waive this policy; it only becomes a preference signal after source-grounded repairs.

## Prompt Block Requirement

Every S2/S5 image prompt must include a compact instruction equivalent to:

```text
Design the figure around the paper's primary contribution type and primary reader question. Do not default to a data-flow diagram unless the contribution is explicitly about dataset construction, database/data management, retrieval, data generation, data governance, or data-pipeline design. Use data labels only when they clarify the innovation mechanism. Variables, losses, thresholds, weights, metrics, and temporary artifacts should appear as edge labels, port labels, small tags, compact notes, or caption-supported annotations rather than peer-level main modules. Keep 4-6 major visual modules by default, preserve balanced whitespace, and ensure every arrow has a clear semantic role.
```
