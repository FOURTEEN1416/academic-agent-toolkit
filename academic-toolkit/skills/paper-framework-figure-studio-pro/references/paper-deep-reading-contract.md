# Paper Deep Reading Contract

After S5, human decisions are outside this assistant workflow.

When the input includes a PDF, LaTeX source, full paper text, detailed method description, report, supplement, or equivalent material, S0 must produce a rich, accurate, source-grounded `paper-foundation-report.md`.

The report should include:

- problem, assumptions, and related-work gap;
- ordered method or algorithm steps;
- model architecture, components, modules, training flow, inference flow, and inputs/outputs;
- losses, objectives, equations, constraints, and terminology mapping;
- abbreviation integrity: for every paper-defined acronym, single-letter role, dataset/group symbol, module shorthand, or overloaded term, record its source-defined expansion, semantic scope, visual-safe label, ambiguity risk, and forbidden expansions that would contradict the paper;
- artifact lineage: when any paper artifact, generated data pool, sample set, memory, retrieval result, pseudo-label set, prototype bank, score, weight, teacher signal, validation proxy, reward, or intermediate representation feeds more than one downstream path, record an `artifact_lineage_table` with producer, consumer paths, lineage relation, visual encoding rule, forbidden visual inference, and evidence anchor;
- arrow semantics: source, target, meaning, and evidence anchor;
- figure-relevant inclusions, exclusions, uncertainty, and reviewer risk;
- framework-figure readiness issues that could require author supplementation, including missing core relations, unsupported lineage, contradictory terminology, opaque core-module internals, or complete-framework scope mismatch;
- core innovation modules and non-droppable core substeps.

After S5, human decisions are outside this assistant workflow.

S0 owns author supplementation. If the source material is too incomplete, ambiguous, or contradictory for the requested framework figure, S0 must write `outputs/S0-paper-foundation/author-supplement-request.md` and set `s0_foundation_readiness_state.foundation_readiness_status` to `S0_NEEDS_AUTHOR_SUPPLEMENT` or `S0_NOT_SUITABLE_FOR_COMPLETE_FRAMEWORK`. If the user provides additional information, S0 must update `paper-foundation-report.md`, write `outputs/S0-paper-foundation/supplement-integration-log.md`, and revise the readiness state before S1 runs. If the user declines supplementation or chooses to proceed anyway, S0 must record `proceed_with_known_risks=true` and preserve unresolved items in `outputs/S0-paper-foundation/framework-figure-risk-register.md`.

After S5, human decisions are outside this assistant workflow.

After S5, human decisions are outside this assistant workflow.



## Semantic Precision And Anti-Misimplementation Extraction

During S0 deep reading, every figure-relevant abstract phrase must be translated into an executable visual contract. Do not leave phrases such as "preserve role differences", "show different actors", "highlight heterogeneity", "reflect collaboration", or equivalent wording as unqualified prose. For each such phrase, extract:

- the source evidence anchor;
- the concrete mechanism, condition, boundary, parameter, input/output, or comparison that actually differs;
- whether the canonical workflow is shared or distinct;
- the safe visual representation;
- the explicit forbidden misimplementation.

Repeated entity families must populate the S0 `actor_or_condition_variation_matrix` and `role_visual_realization_contract`. If roles share the same workflow, S0 must say so directly and must forbid duplicated full pipelines. If source evidence supports true branch/parallel/comparison lanes, S0 must name the exact operation segment that differs and where the lanes merge or remain separate.

S1-FIGURE-STRATEGY must not perform a new source-sufficiency judgment. If S1 discovers that the S0 foundation is missing, stale, or internally inconsistent, it must stop and point to an explicit S0 rerun instead of asking author-supplement questions inside S1.

After S5, human decisions are outside this assistant workflow.
