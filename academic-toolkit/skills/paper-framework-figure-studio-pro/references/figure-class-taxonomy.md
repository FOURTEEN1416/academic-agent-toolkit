# Framework Figure Taxonomy

Use this taxonomy before writing prompts or generating images. Routing is multi-label first, then primary subtype selection.

## Core Subtypes

| Subtype | Reader Question | Best Paper Slot | Required Decisions |
|---|---|---|---|
| Method framework | What is the proposed method, and why are its parts organized this way? | intro / method | modules, novelty highlight, data/control flow, output |
| Architecture | Which components interact, and what is trained or inferred? | method / system | boundaries, interfaces, parameters, losses, inference path |
| Pipeline / process | What happens step by step? | method / system | temporal order, steps, state updates, feedback loops |
| Agent workflow | What does the agent observe, decide, call, verify, and update? | method / agent system | planner, model/tool calls, memory, verifier, loop |
| System/data flow | Where do data, users, tools, and model components move? | system / method | lanes, data stores, services, latency or control boundaries |
| Mechanism intuition | Why does the central idea work? | intro / method / analysis | cause-effect chain, variable roles, constraints |
| Case walkthrough | How does one example move through the framework? | intro / qualitative / appendix | example states, before/after, step labels |
| Evidence-linked framework | How does the framework connect to evidence or ablations? | results / rebuttal | evidence cards, comparison boundary, claim mapping |
| Failure-aware framework | Where can the system fail, and what boundary should reweb-displays understand? | analysis / limitation / rebuttal | failure modes, triggers, affected modules, mitigation |

## v3.0.9b Vector-Library Subtype Crosswalk

The integrated vector library adds source-grounded subtype labels. Use them as additional routing tags, then map them back to the core subtype that best serves the target paper:

| Vector-Library Label | Usual Local Mapping | Use When |
|---|---|---|
| `method_architecture` | Method framework / Architecture | modules, training/inference, system boundaries, or model blocks matter |
| `retrieval_flow` | Agent workflow / System-data flow / Pipeline | query, context, retrieval, memory, tool, or answer flow matters |
| `graph_or_network` | Architecture / Mechanism intuition | nodes, dependencies, causal relations, GNNs, or graph reasoning matter |
| `data_or_embedding_map` | Mechanism intuition / Evidence-linked framework | latent space, distribution shift, clustering, or representation geometry matters |
| `qualitative_example` | Case walkthrough | one example's state transition or before/after behavior matters |
| `evidence_chart` | Evidence-linked framework | ablation, metric, benchmark, or result support should be linked to the framework |

## Routing Axes

- Reader question: identity, sequence, interaction, mechanism, example behavior, evidence support.
- Logical gap: problem-to-method, method-to-mechanism, mechanism-to-result, result-to-claim.
- Layout skeleton: left-to-right pipeline, layered stack, hub-and-spoke architecture, swimlanes, modular grid, loop, before/after split.
- Density: intro overview, method technical, appendix dense, rebuttal conservative.
- Paper slot: intro, method, system, analysis, appendix, rebuttal, slides.
- Multi-label status: record all applicable labels, then select a primary subtype.

## Default Primary-Subtype Rule

- For method sections, default to `method_framework` plus `architecture` or `pipeline_process`.
- For agentic systems, default to `agent_workflow` plus `system_data_flow`.
- For intro figures, default to `method_framework` plus `mechanism_intuition`.
- For qualitative examples, default to `case_walkthrough` plus `pipeline_process`.
- For rebuttals, default to `evidence-linked framework` or `failure-aware framework`.

Do not lock the primary subtype from prose alone when visual comparison would help. Recommend a candidate board using the step count policy: S1-FIGURE-STRATEGY prepares at least 8 S2 candidate cards; S2-SKETCH-EXPLORE defaults to 8 formal publication-style first-round candidates; S5-CANDIDATE-IMAGE defaults to 6 unbiased formal candidates arranged as `2 structurally different directions x 3 visual communication style treatments`, total max 8. Uploaded style references only inform S1-FIGURE-STRATEGY type advice and must not automatically create preference-informed extras.


