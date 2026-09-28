# Paper-Grounded Style Extension v3.2.0

This extension supplements the local figure-style knowledge base with paper-serving schematic treatments. It is generic and may be used across research papers. The styles below are visual communication options, not evidence sources. A style can be selected only after the paper-supported module, connector, text, symbol, and core-detail contracts are known.

## Use Rules

- Choose styles by matching the paper's reader problem, topology, evidence structure, core mechanism, and arrow-risk profile.
- Do not choose a style because it looks novel if it weakens paper fidelity or hides a core contribution.
- Do not let style invent actors, data sharing, central coordinators, causal paths, feedback loops, formulas, or evaluation sources.
- A style is successful only when the reviewer can recover the paper's main mechanism faster and with fewer misunderstandings.

## Style Lenses

| Style lens | Best for papers with | Visual grammar | Strength | Avoid when |
| --- | --- | --- | --- | --- |
| `clean_flat_modular_backbone` | A clear method pipeline or architecture skeleton. | Large module cards, restrained color, few arrows, short labels. | Fastest first-glance and safest reconstruction. | Core contribution is hidden inside one module unless internals are added. |
| `swimlane_actor_artifact_flow` | Multiple actors, clients, agents, modalities, roles, or spaces. | Horizontal/vertical lanes, shared time axis, lane-specific colors. | Separates who owns which artifact and reduces false cross-actor arrows. | The paper has no meaningful actor/space separation. |
| `evidence_locked_contract_sheet` | High-risk lineage, filtering, evaluation, verification, or compliance claims. | Main flow plus compact ledger-like checks, gates, evidence badges. | Makes provenance and gating visible without long prose. | A figure should stay very sparse or no evidence/gating mechanism is central. |
| `loop_lifecycle_with_guarded_feedback` | Iterative optimization, training rounds, recurrent updates, active learning, planning loops. | Circular or rounded loop with explicit step order and guarded return edge. | Clarifies temporal/update semantics. | The paper does not support feedback or recurrence. |
| `dual_space_alignment_map` | Data/model/feature/latent/policy spaces that must be aligned or contrasted. | Two or three parallel regions with bridge modules and labeled relation types. | Helps reviewers see peer spaces without merging them incorrectly. | Only one space is primary or the relation is not source-supported. |
| `core_module_cutaway` | A named core module with non-droppable internal substeps. | Main module plus in-place cutaway, micro-chain, or side inset with new information. | Prevents empty-box representations. | The paper does not provide enough internal detail. |
| `problem_solution_bridge` | Papers whose contribution is best understood as fixing a specific failure mode. | Left context/problem cue, central mechanism bridge, right outcome. | Gives reviewers a memorable problem-to-method arc. | It overstates empirical improvement or invents a before/after claim. |
| `hierarchical_system_to_mechanism` | Whole-system figures needing one or two local mechanism reveals. | Large backbone, small anchored detail panels, strict area hierarchy. | Balances completeness and internal detail. | Detail panels would dominate or duplicate the backbone. |
| `separated_data_model_control_paths` | Methods with distinct data flow, model/state update, control/gating, and evaluation signals. | Three line-style families and separated routing corridors. | Reduces arrow ambiguity. | The paper does not distinguish these paths or too many styles would overload. |
| `compact_distribution_context` | Non-IID, class imbalance, domain shift, uncertainty, sampling, or data partition context. | Tiny distribution glyphs, small histograms, or grouped tokens in a subordinate context strip. | Shows setting without taking over the method. | Dataset/context is not central or would crowd core mechanisms. |
| `precision_blueprint_grid` | Technical architectures where alignment, ports, and update targets matter. | Light grid, orthogonal connectors, explicit ports, minimal decoration. | Good for exact source-target routing and connector audits. | A more intuitive narrative is needed for broad readers. |
| `scientific_editorial_overview` | Top-conference figures needing polish and broad readability. | Balanced panels, soft hierarchy, concise callouts, caption-friendly grouping. | High visual appeal without poster-like rendering. | If the figure needs strict port-level routing or dense formulas. |
| `mechanism_storyboard` | Methods with ordered phases or a clear local scenario that helps comprehension. | 3-5 numbered frames with repeated anchor objects. | Makes abstract steps concrete. | The story would introduce unsupported analogies or hide the full framework. |
| `minimal_math_anchor` | A central variable, objective, threshold, score, or weight is needed for correctness. | One or two formula tokens placed at the producing/consuming module. | Communicates technical precision without derivation. | The symbol is not necessary or not introduced in the source. |
| `robustness_stress_panel` | Papers where robustness/generalization across settings is a core claim with evidence. | Main mechanism plus small condition strip or result cue. | Shows why the method matters across settings. | It would overclaim results or distract from the mechanism. |

## Composition Recipes

### Sparse backbone + micro-internals

Use for first-round sketches when the paper has many modules but only a few core innovations. Draw the complete backbone with large simple cards; place tiny in-module chains only in core modules. Keep connector count low and rely on caption for secondary definitions.

### Split-space bridge with safe connectors

Use when the paper operates in two or more spaces, such as local/global, data/model, observed/latent, agent/environment, retrieval/generation, or training/inference. Put each space in a distinct region. Bridges require explicit evidence and line-style labels. Do not draw a bridge merely to make the regions visually connected.

### Main framework + new-information detail strip

Use when a complete overview needs one detail layer. The main framework remains the largest region. The strip may show internal substeps, a scoring/gating formula token, a state transition, or a small exemplar. It must not repeat the entire main flow.

### Controlled lifecycle loop

Use only when the paper defines rounds, iterations, recurrent refinement, or feedback. The loop must name the paper-supported return edge and its target. If no return edge is supported, use a linear path with a caption note about repeated rounds rather than drawing a loop.

### Contract-style arrow grammar

Use when arrow errors are likely. Build the prompt around a small allowed-arrow list, separate data/model/control/evaluation line styles, and explicit forbidden arrows. This style trades decoration for scientific safety.

## Reviewer-First-Glance Enhancers

- Use a single title-like takeaway inside or near the figure only if it is source-grounded and short.
- Give the eye 3-5 anchor stops; more stops require grouping or caption support.
- Keep the central method path visually dominant even when context is distinctive.
- Use visual landmarks sparingly: one core bridge, one gate, one alignment region, one cutaway, or one final output anchor is usually stronger than many equal icons.
- Make categories obvious by consistent shape and color, but do not use color as the only semantic cue.
- Prefer representative exemplars plus ellipsis over dense sample clouds.
- Use formulas as anchors, not as decoration.

## Style Selection Checklist

Before accepting a style for S1/S2/S5, answer:

1. Which paper-specific reader question does this style help answer?
2. Which paper-supported modules and paths become more legible?
3. Which connector or arrow risks are reduced by this style?
4. Which core internals are made visible, and where?
5. What information is intentionally moved to caption/legend?
6. What unsupported metaphor, icon, relation, or visual claim is explicitly forbidden?
