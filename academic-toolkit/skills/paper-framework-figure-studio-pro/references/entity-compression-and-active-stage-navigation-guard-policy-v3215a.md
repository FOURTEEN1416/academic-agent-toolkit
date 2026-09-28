# Entity Compression And Active-Stage Navigation Guard Policy v3.2.15f

This policy is generic. It must not encode any target-paper domain, project name, task type, variable name, dataset, method name, or deployment assumption. It governs two reusable failure modes: repeated entity families becoming redundant full workflows, and next-step prompt suggestions drifting away from the active workflow state.

## 1. Entity-Variant Compression Guard

Before S1 or S4 writes any image-generation prompt package, it must classify each repeated entity family found in the current sources or project state.

### Entity Variant Classification

Every repeated entity family must be assigned one of these generic classes:

| Class | Meaning | May expand into multiple full process lanes |
|---|---|---:|
| `context_marker` | A label, condition, category, identity, state, or input/status marker around the method. | no |
| `shared_process_instance` | Multiple entities use the same source-supported process structure. | no |
| `true_process_branch` | The source explicitly states different operations, relations, or input-output contracts. | yes |
| `comparison_target` | The candidate's source-grounded purpose is to compare alternatives or conditions. | yes |
| `nonvisual_context` | Information that belongs in notes, caption support, or text outside the main structure. | no |

Only `true_process_branch` and `comparison_target` may create multiple full process lanes. All `context_marker` and `shared_process_instance` families must be compressed into compact markers around one canonical process unless the source explicitly supports distinct branches.

Required S1/S4 field:

```json
{
  "entity_variant_classification": [
    {
      "entity_family": "<project-derived family name>",
      "classification": "context_marker | shared_process_instance | true_process_branch | comparison_target | nonvisual_context",
      "may_expand_to_full_workflow": false,
      "source_grounded_reason": "<evidence anchor or project contract reference>"
    }
  ]
}
```

## 2. Process Instance Budget

S1/S4 prompt packages must declare a process instance budget for the candidate before image generation.

Default: `max_full_process_instances = 1`.

Extra visible full process instances require source-grounded evidence that they represent different operations, different input-output contracts, different phases, or an explicit comparison objective.

Required S1/S4 field:

```json
{
  "process_instance_budget": {
    "max_full_process_instances": 1,
    "primary_process_steps": [
      {
        "step_id": "P1",
        "max_visible_instances": 1,
        "extra_instances_allowed_only_if": [
          "source states different operation",
          "source states different input-output contract",
          "source states different temporal phase",
          "figure objective is explicit comparison"
        ]
      }
    ],
    "compression_methods_allowed": [
      "chips",
      "legend entries",
      "small grouped tokens",
      "brace labels",
      "ellipsis",
      "stacked miniature markers"
    ],
    "forbidden_without_evidence": [
      "one full process per entity family member",
      "parallel cloned process chains",
      "repeated full lanes with the same module sequence"
    ]
  }
}
```

## 3. Multiplicity Positive Lock

Negative constraints are not sufficient. Every high-risk duplicate-process constraint must include a positive rendering instruction.

Required positive lock language in prompt packages when repeated entities exist:

```text
Draw exactly one canonical process unless the source explicitly supports distinct branches. Show repeated entity families only as compact markers, grouped tokens, braces, legends, or ellipses. There must be only one visible instance of each primary process step unless justified by the process instance budget.
```

A prompt package is blocked if it says only what not to draw but does not state the replacement structure.

## 4. Variant-To-Lane Risk Audit

S1/S4 must scan each prompt package for lane-inducing language before writing prompt-index files. Examples include generic phrases such as row, lane, parallel, per-type, per-role, per-condition, per-entity, for each, separate process, separate pipeline, stacked process, and multiple similar workflows.

If repeated entities are classified as `context_marker` or `shared_process_instance`, lane-inducing language is blocked unless immediately constrained by a positive lock: markers only, one canonical process, no separate process lanes.

Required S1/S4 field:

```json
{
  "variant_to_lane_risk_audit": {
    "lane_inducing_phrases_found": [],
    "risk_level": "low | medium | high",
    "required_rewrite": false,
    "mitigation": "one canonical process plus compact markers"
  }
}
```

## 5. Adversarial Generation Risk Audit

Prompt audit must not stop at checking whether a rule appears in text. It must check likely image-generation misreadings and mitigation coverage.

Required S1/S4 field:

```json
{
  "adversarial_generation_risk_audit": {
    "likely_misreadings": [
      "repeated entity markers may become parallel full process lanes",
      "attribute labels may become standalone modules",
      "optional inputs may become mandatory main inputs",
      "context legend may become part of the main process"
    ],
    "mitigations": [
      "one canonical process",
      "one visible instance per primary step",
      "markers only for repeated entity families",
      "optional elements rendered as small annotations, not full branches"
    ],
    "residual_risk": "low | medium | high",
    "verdict": "pass | rewrite_required | block"
  }
}
```

If residual risk is high, S1/S4 must rewrite the prompt package before image-only handoff.

## 6. Source-Grounded Scope And Multiplicity

Do not add a visual object, boundary, connection, lane, resource, or visibility relation merely because it is common in a domain or common in prior examples. Draw only what the current source and project contracts support. If the source does not support an extra global object, a cross-boundary connection, a visibility upgrade, or a separate repeated process, remove it or compress it into a caption/legend-level cue.

## 7. Conversation-Aware Stage Navigation

Next-step prompt suggestions are controlled by navigation state, not restore state alone.

`restore_state` answers: what files can be restored from checkpoints.
`navigation_state` answers: what stage should the user run next.

When suggesting a next prompt, resolve `navigation_state` using this priority:

1. Explicit public stage execution in the current conversation.
2. Tool-visible generation events or produced artifacts in the current conversation.
3. Latest stage manifest / prompt-index status.
4. Latest checkpoint.
5. Older conversation memory only as a fallback.

S2 and S5 are image-only stages and may not create a cumulative text checkpoint. If an image-only stage completed in the current conversation, treat it as complete for navigation even when the newest cumulative checkpoint belongs to an earlier text stage.

Required navigation field when generating a next-step prompt:

```json
{
  "navigation_state": {
    "latest_user_requested_stage": "<stage_id>",
    "latest_assistant_completed_stage": "<stage_id>",
    "image_only_stage_completed_in_conversation": false,
    "checkpoint_may_lag": false,
    "canonical_next_stage": "<stage_id_or_null>",
    "terminal": false,
    "evidence": []
  }
}
```

## 8. Active Stage Specification Only

User-facing next-step prompts must be generated from the active stage transition table, not from inactive-stage descriptions, noncanonical stage names, or memory of earlier workflow versions.

Canonical transitions:

```json
{
  "S0-PAPER-FOUNDATION": "S1-FIGURE-STRATEGY",
  "S1-FIGURE-STRATEGY": "S2-SKETCH-EXPLORE",
  "S2-SKETCH-EXPLORE": "S3-DIRECTION-SELECT",
  "S3-DIRECTION-SELECT": "S4-CANDIDATE-BRIEF",
  "S4-CANDIDATE-BRIEF": "S5-CANDIDATE-IMAGE",
  "S5-CANDIDATE-IMAGE": null
}
```

Before exposing a next-step prompt, validate:

- detected next stage equals the canonical next stage;
- image-only stages do not contain review, ranking, audit, selection, critique, or text-planning actions;
- terminal stages do not produce a next-step prompt;
- noncanonical stage wording is absent from the user-facing prompt.

If validation fails, regenerate the prompt from the active transition table.

## 9. Accountability For Assistant-Suggested Prompt Drift

If a user submits a prompt that appears derived from the assistant's previous suggested prompt, and that prompt is invalid under the current workflow, the assistant must acknowledge that the earlier suggestion used outdated or invalid stage wording, provide the corrected canonical prompt, and not frame the issue primarily as user error.

## 10. Active-Document Hygiene

Active skill files must contain current stage responsibilities only. Non-active workflow wording must not be used to generate user-facing next-step prompts. If active files contain noncanonical stage names or non-active responsibility descriptions, documentation lint should fail before packaging.


## S0 Precision Contract Consumption

Before S1/S4 creates `entity_variant_classification`, `process_instance_budget`, `multiplicity_positive_lock`, or `variant_to_lane_risk_audit`, it must read the S0 semantic precision contract when present. Any S0 `full_flow_repetition_allowed: false` or equivalent forbidden lock must be treated as a hard negative prompt constraint. A later candidate may not convert compact role/context markers into duplicated full lanes unless a source-grounded repair changes the variation decision.
