# Complete-Framework Candidate Eligibility Policy v3.2.1

Use this policy whenever the user requests a publication-ready method/framework diagram, whole-method framework, complete-paper framework, overall training-cycle diagram, system/framework overview, or any figure that must fully reflect the paper framework.

This policy is intentionally paper-agnostic. It works with `references/visual-information-economy-and-repetition-control-policy-v322.md`: full framework coverage must not be implemented by copying the same workflow across repeated actors or panels. It prevents scoped mechanism probes, style probes, or evidence-context probes from being counted as required complete-framework candidates while preserving optional auxiliary probes when the user explicitly asks for them.

## Load Condition

Load this policy in S1-FIGURE-STRATEGY and S2-SKETCH-EXPLORE embedded prompt preparation when any of the following is true:

- `figure_intent=complete_paper_framework`;
- the user asks for a method/framework diagram, architecture diagram, pipeline diagram, workflow diagram, whole-method overview, whole-paper overview, publication-ready framework figure, or complete training-cycle diagram;
- the user says the candidates must fully reflect the framework or must not be partial;
- S0/S1 identifies multiple paper-primary mechanisms, spaces, actors, paths, or update loops that are jointly necessary for the figure.

## Complete-Framework Intent Hard Override

When this policy is active, set:

```text
figure_intent = complete_paper_framework
required_s2_complete_candidate_count >= 8
scoped_candidate_count_in_required_batch = 0
```

Every required S2 candidate card must be a complete framework candidate. Complete coverage should be achieved through one clear framework backbone plus compressed repeated instances, not through repeated full pipelines. A candidate may emphasize one core mechanism, space, actor group, or visual rhetoric, but it must still visibly include the framework backbone and every paper-primary mechanism/path needed to understand the method.

Scoped mechanism probes, evidence-context probes, style probes, local module explainers, and context-only sketches are forbidden inside the required S2 candidate batch unless the user explicitly authorizes scoped probes. Even when authorized, scoped probes must be recorded under `auxiliary_non_candidate_probes` and must not count toward the required candidate count.

## Required Candidate Eligibility Gate

Before closing S1, audit every required S2 candidate card. A required candidate is eligible only if all conditions below pass:

1. `figure_intent=complete_paper_framework`.
2. `candidate_scope` is `complete_method_overview` or `complete_story_overview`.
3. `coverage_status` is `complete_compact` or `complete_with_caption_support`.
4. `complete_overview_gate` is present and names the visible framework backbone, all paper-primary paths/spaces, required core modules, and caption-only omissions.
5. `framework_backbone_lock` is present and lists the minimum visible modules/states/output-update targets that preserve whole-framework meaning.
6. `core_detail_display_matrix` covers every S0/S1 paper-primary mechanism and gives each one a visible input/evidence token, internal operation/substep, output/action token, and display mode.
7. No core mechanism is reduced to an opaque box, a tiny label, or a caption-only mention.
8. The title/explanation does not describe the candidate as a scoped probe, local mechanism sketch, style probe, context rail, partial view, mechanism-only inset, or incomplete view.
9. The candidate does not set `coverage_status=scoped_not_complete` and does not need an expansion/merge plan before it could become the final framework direction.

If fewer than the required number of candidates pass, S1 must rewrite or replace failing candidates before closing. S1 must not close with a required batch that contains scoped candidates under complete-framework intent.

## Emphasis Is Not Scope Reduction

Mechanism emphasis means visual hierarchy, larger detail carrier, clearer callout treatment, or richer in-place internal detail for the emphasized mechanism.

Mechanism emphasis must not remove, hide, or collapse other paper-primary mechanisms or paths. It also must not add redundant replicas of the emphasized mechanism; use in-place detail or one connected detail carrier instead. Use paper-agnostic labels generated from the current S0/S1 evidence, such as:

- `complete_overview_with_signature_mechanism_emphasis`;
- `complete_overview_with_primary_data_path_emphasis`;
- `complete_overview_with_primary_model_update_emphasis`;
- `complete_overview_with_system_boundary_or_access/boundary constraint_emphasis`.

Do not hard-code mechanism names from a previous paper into the reusable skill. The concrete emphasis label for a project must be derived only from that project's S0/S1 evidence.

Do not use labels such as `scoped mechanism probe`, `context rail only`, `local mechanism sketch`, or `incomplete mechanism view` inside the required S2 candidate batch.

## Auxiliary Non-Candidate Probe Rule

A scoped probe may be created only when the user explicitly asks for scoped probes, mechanism-only exploration, or auxiliary visual-language probes. It must be placed in a separate section named `auxiliary_non_candidate_probes`.

Each auxiliary probe must:

- declare `coverage_status=scoped_not_complete`;
- state the exact local scope and omissions;
- include a compact context mini-map if it is later useful for merging;
- state that it is not eligible for S2 required-batch counting;
- After S5, human decisions are outside this assistant workflow.

## S1 Closeout Completeness Audit

Before S1 can close under complete-framework intent, produce or save a compact `s2_required_candidate_eligibility_audit` table with columns:

- candidate ID;
- candidate scope;
- coverage status;
- core mechanisms visibly included;
- complete overview gate status;
- core detail matrix status;
- eligible for required S2 batch: yes/no;
- rerun action if no.

S1 may close only when the required complete-candidate count is satisfied and every required candidate is marked eligible.

## S1-embedded S2 preparation Preflight

Before preparing S2 prompt packages, S2 embedded prompt preparation must read the S1 candidate cards and run the eligibility preflight. If a required candidate is scoped, incomplete, or missing complete-framework fields, S2 must block image-prompt preparation and ask the user to rerun/rerun S1. S2 must not silently generate or prompt a partial candidate as if it were complete.

## Non-Hardcoding And Portability

This policy must remain target-paper agnostic. It must not include paper-specific module names, dataset names, author names, project IDs, local file paths, or runtime absolute paths. Paper-specific mechanisms are supplied only by S0/S1 project artifacts and user-source clarification.
