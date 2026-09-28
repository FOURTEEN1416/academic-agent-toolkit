# S0 Semantic Precision And Role-Variation Lock Policy v3.2.15f

This policy is paper-neutral. It exists to prevent vague S0 analysis phrases from becoming wrong drawing instructions in S1/S2/S4/S5. Project-specific role names, method names, datasets, equations, and edge lists must be written only in the project run outputs, not in this reusable policy.

After S5, human decisions are outside this assistant workflow.

## Core Rule

S0 must not leave figure-relevant statements as broad prose such as "preserve role differences", "show different actors", "highlight heterogeneity", "reflect interactions", "keep module distinction", or equivalent language without a concrete visual contract.

Every such statement must be normalized into an explicit `meaning -> visual implementation -> forbidden interpretation -> downstream carry-forward` record before S0 can close as ready for S1.

A vague statement is not allowed to function as a drawing instruction by itself. If S0 cannot disambiguate it from the source material, S0 must record a major risk or request author supplementation instead of passing the ambiguity to S1.

## Required S0 Semantic Precision Outputs

S0 must write the required semantic precision content in `outputs/S0-paper-foundation/paper-foundation-report.md` and mirror it in machine-readable form at:

```text
outputs/S0-paper-foundation/s0-semantic-precision-contract.json
```

The JSON contract must be paper-specific and must include:

| Field | Requirement |
| --- | --- |
| `schema_version` | Integer schema version. |
| `policy_id` | `s0-semantic-precision-and-role-variation-lock-v3215f`. |
| `ambiguous_directive_normalization` | Table of any vague or high-risk S0 phrases, each rewritten as concrete semantics, visual-safe instruction, forbidden interpretations, and evidence anchor. |
| `actor_or_condition_variation_matrix` | Repeated roles, actors, clients, agents, modalities, conditions, data sources, modes, domains, or instances; what differs; whether their workflow differs; where any divergence begins and ends. |
| `role_visual_realization_contract` | For each repeated entity family, the exact representation: shared canonical process with compact markers, branch-only segment, comparison lanes, topology/context inset, caption-only, or other evidence-supported representation. |
| `process_instance_budget` | Default canonical process count and any allowed repeated full-process instances with source evidence. |
| `forbidden_misimplementation_locks` | Explicit negative constraints that later prompts must preserve. |
| `downstream_s1_s4_carry_forward` | Exact fields S1/S4 must consume, including prompt constraints and audit checks. |

The markdown report may present this as tables, but the JSON contract is the machine-readable source for validators and downstream repair.

## Ambiguous Directive Normalization

For every figure-relevant S0 sentence that uses an abstract verb or preservation phrase, create a normalization row with these fields:

```json
{
  "source_phrase": "project-specific phrase from the S0 analysis",
  "source_evidence_anchor": "paper section/equation/algorithm/table/user supplement anchor",
  "concrete_meaning": "what must be understood scientifically",
  "visual_safe_instruction": "how to draw it without changing the source meaning",
  "forbidden_interpretations": ["wrong drawing or prompt behavior that must not occur"],
  "downstream_fields": ["field names S1/S4 must copy or enforce"]
}
```

The row must answer: does this phrase mean a separate process, a local branch, a compact role marker, a boundary condition, a different parameter, a different input/output, a comparison target, or caption-only context?

If the row cannot answer that question from source evidence, S0 must mark the issue as `major` or `blocking` in the risk register.

## Role / Actor / Condition Variation Decision

Repeated roles, actors, clients, agents, modalities, data sources, domains, tasks, views, sites, or conditions are high-risk because image prompts often convert them into duplicated pipelines. S0 must classify each repeated entity family.

Allowed values for `visual_representation`:

- `representative_shared_flow`: draw one canonical workflow/process; place role or condition differences as compact chips, boundary badges, grouped tokens, labels, braces, mini table, or legend.
- `branch_only_where_distinct`: draw common prefix/suffix once; branch only around source-supported distinct operations; merge again when the workflow reconverges.
- `parallel_lanes_required`: draw multiple lanes only because source evidence shows different operation sequences or input-output contracts across the roles.
- `comparison_lanes_required`: draw comparison lanes only when the paper contribution is the comparison itself and the differences cannot be understood with compact markers.
- `topology_or_context_inset_only`: show multiplicity/topology/context in a small inset; do not duplicate the full method workflow.
- `caption_only`: keep the difference in caption or legend because drawing it would overstate its mechanistic role.

If a family is classified as `representative_shared_flow`, `topology_or_context_inset_only`, or `caption_only`, S0 must explicitly set full-flow repetition to `false` and write a negative lock such as: the role distinction must not be implemented as one full pipeline per role.

## Positive And Negative Contract Pair

Every high-risk role/difference statement must have both:

1. a positive drawing instruction, e.g. "use one shared workflow and attach role badges at the input boundary"; and
2. a negative drawing instruction, e.g. "do not create one complete duplicated process per role".

The negative instruction is mandatory because image prompts often over-expand abstract preservation language.

## S0-to-S1 Consumption Rule

S1 must consume `s0-semantic-precision-contract.json` before preparing candidate cards or S2 prompt packages. S1 must not reinterpret S0 vague language independently. If the contract says full-flow repetition is forbidden, S1 prompt packages must include that prohibition in each affected candidate. If S1 wants a different representation, it must explicitly repair or rerun S0 with source evidence.

S4 must carry the same restrictions into formal S5 prompt packages unless S3/S4 records a source-grounded repair that changes the representation decision.

## Prompt-Blocking Conditions

S1/S4 prompt preparation must block if any of the following is true:

- S0 contains a high-risk vague directive but no normalization row.
- A role/entity family is listed but lacks a visual representation decision.
- A repeated family has a shared canonical workflow but full-flow repetition is allowed without source evidence.
- A positive instruction exists without a forbidden interpretation lock.
- A prompt asks for multiple full lanes or repeated workflows while the S0 contract classifies the family as shared/context-only/caption-only.

## Minimal Example Pattern, Not A Paper-Specific Rule

Bad S0 output pattern:

```text
Preserve role differences in the figure.
```

Good S0 output pattern:

```text
Role-difference contract: the roles share the same canonical process. Draw one shared process. Encode each role as compact boundary chips and a small legend. Do not draw one complete process/lane per role unless later source evidence shows distinct operations.
```

The example above is only a generic pattern. It must not be copied with project-specific names into the reusable skill package.

## Validation Hook

Use the paper-neutral validator when S0 closes or before S1 consumes an existing S0 package:

```bash
python scripts/figure_studio_s0_precision_guard.py --run-dir figure-studio-runs/<project_id> --fail-on-error
```

A passing validator does not prove scientific correctness; it proves that S0 converted high-risk vague directives into concrete, auditable visual contracts before downstream prompt generation.
