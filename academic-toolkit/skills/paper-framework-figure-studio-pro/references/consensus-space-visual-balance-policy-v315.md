# Consensus-Space Visual Balance Policy v3.1.6

Use this policy when a target paper's contribution depends on two or more peer spaces, peer model paths, or peer consensus mechanisms. It is especially important for papers whose novelty is a coupling across spaces, roles, model families, objectives, evaluators, or update loops.

## Trigger Conditions

Apply this policy when S0 or S1 finds any of these patterns:

- the paper explicitly says the method establishes consensus in more than one space;
- the method has one generated artifact used in two core roles, such as training data and evaluation proxy;
- an update or aggregation mechanism depends on scores, weights, rewards, validation, retrieval, or generated outputs;
- two or more model families, agents, modules, objectives, or representations are updated or aligned together;
- a core contribution would be misleading if one peer path is shown as only a small output box or caption note.

## Required Planning Fields

S1 sketch cards and S4 formal candidate briefs must add these fields when this policy applies:

- `consensus_space_priority_map`: list each paper-primary space/path, its paper evidence, and whether it is primary, co-primary, or context-only for the candidate.
- `visual_weight_plan`: expected relative canvas area, centrality, contrast, and reader-order treatment for each peer space/path.
- `area_budget_by_region`: approximate canvas percentage for core mechanisms, co-primary mechanisms, lineage bridges, context/constraints, and caption-only information.
- `must_show_for_each_space`: minimum visible anchors for each space/path.
- `redundancy_budget`: allowed repetition and the planned compression method for repeated entities.
- `semantic_uniqueness_plan`: the primary visual carrier for each peer space/path and the distinct role of any allowed repetition.
- `no_duplicate_explanation_plan`: how repeated paths, rows, examples, symbols, and legend definitions will be compressed without visually demoting any paper-primary mechanism.
- `missing_information_risk`: what important mechanism would be lost if the prompt spends space on repeated rows, large legends, decorative story panels, or redundant labels.

If any of these fields are missing, S2 or S5 should stop and request rerun of the preceding text stage rather than generating images.

Context and constraint areas are budgeted separately from core mechanisms. A setting strip, topology sketch, access/role-boundary cue, resource-sharing constraint, or role legend may be necessary, but it must not crowd out visible internals of the paper's core algorithm. In S2 complete-paper sketches and formal complete-paper candidates, context/constraint regions should normally stay at or below 15-20% of the canvas unless the paper's core contribution is the context/topology itself. If the planned context exceeds 25%, S1/S4 must write an explicit justification and identify which core mechanism area is still protected.

## Visual Weight Rule

Peer-primary spaces must receive comparable visual status in overview candidates. Comparable does not mean equal pixel area, but it does require:

- clear title or lane labels for each peer space;
- visible anchors for each space's core mechanism;
- a reader path that reaches each peer space before the figure feels complete;
- no peer space reduced to a tiny side note, icon-only badge, or caption-only claim.

Scoped candidates are allowed, but their title and explanation must declare the scope. For example, a single-module, retrieval-only, verifier-only, generator-only, evaluation-only, or update-only sketch may focus on that mechanism, but it must not be treated as the complete method overview when the target paper claims a coupled method. It should include only a small context link to the omitted paper-primary path.

When the user asked for a complete paper framework/method overview diagram, scoped candidates are auxiliary non-candidate exploration tools, not part of the required output. In the default 8-sketch S2 batch, all 8 required sketches must be eligible complete-paper overview candidates and zero scoped probes may count toward the required batch. A scoped probe may contribute a visual sublanguage to S3 only when the user explicitly authorized auxiliary probes, and S3 must expand or merge that idea back into a complete coverage plan before S4.

## Anti-Redundancy Rule

Repeated rows are useful only when they show a pattern. They become harmful when they consume space that should show missing mechanism. Compress repeated rows by:

- drawing one exemplar row plus an ellipsis;
- grouping repeated neighbor models into a cluster;
- using a small count badge instead of redrawing every entity/classifier/sample;
- moving repeated legend definitions to caption/legend text;
- showing a single representative generated-data token when multiple copies have the same meaning.

Do not repeat the same labels, arrows, or icons in both a main panel and an inset unless the repetition is a minimal orientation anchor. Use the saved space to show the missing high-value transition.

Do not spend one paper-primary space's area budget explaining an already visible idea again. Repetition often makes one path look precise only because it is repeated, while another co-primary path loses visible mechanism anchors. Use the saved space for missing high-value transitions, and move definitions or caveats to caption/legend text.

Do not let background/context rows grow because they are visually easy to draw. A large context row is justified only when it adds a distinct paper relation that cannot be carried by a compact role strip, mini-map, legend, or caption. If a context row mainly says "there are entities" or "there is no coordinator", compress it and spend the recovered area on core internal mechanism.

## Information Priority

When space is limited, preserve these before decorative or repeated elements:

1. The producer of a score, weight, selected/generated artifact, supervision signal, or update.
2. The transformation chain that turns that object into an action.
3. The target of the action, especially if two models are updated.
4. The constraint that prevents a false interpretation, such as an S0-forbidden sharing, access, evaluation-source, coordination, or causal assumption.
5. Only then add extra legend items, repeated rows, and surface style details.

## Non-Normative Example Pattern: Dual Data/Model Consensus

This example shows how to instantiate the generic rule for a paper whose novelty couples data-space consensus with model-space consensus. Do not copy these labels by default. Replace them with the target paper's own spaces, modules, variables, evidence, and actions.

Data-side anchors might include:

- heterogeneous local data roles, domains, entities, or sources;
- correction, retrieval, augmentation, filtering, selection, validation, supervision, or equivalent paper-defined artifact improvement;
- generator, simulator, retriever, annotator, or optimizer training from accepted data;
- generated, retrieved, mixed, or reruned artifacts;
- the mixing, selection, or assembly step that creates the training input.

Model-side anchors might include:

- validation, proxy, reward, query, benchmark, held-out, or generated evidence used to judge peers;
- evaluation, scoring, ranking, agreement, disagreement, or confidence computation;
- weight, gate, selection, routing, voting, or normalization transformation;
- aggregation, alignment, distillation, update, rerun, or coordination action;
- every affected model family, module, agent, representation, or objective when the paper updates more than one.

If an S2/S5 candidate omits most anchors for a paper-primary space while still presenting itself as the whole framework, mark `<space>_underweighted=true` and rerun the candidate prompt or previous text contract.

If an S2 candidate omits most anchors for a paper-primary space and declares itself scoped, it is allowed only if the batch budget still contains enough complete-paper candidates and the prompt includes a global context mini-map. It remains ineligible as a direct final framework direction until S3 supplies an expansion plan.

## Prompt Requirements

S2/S5 prompts should explicitly say:

- which spaces/paths are paper-primary or co-primary;
- the maximum intended visual weight of context/background regions;
- which anchors must be visible for each peer space;
- which repeated rows must be compressed;
- which details are moved to caption/legend;
- how the candidate's `semantic_uniqueness_plan` and `no_duplicate_explanation_plan` prevent explaining the same idea twice;
- that no paper-primary space/path or mechanism may be reduced to a small decorative box if it is a core contribution.

## Audit Use

After S5, human decisions are outside this assistant workflow.
