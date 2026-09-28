# Candidate Issue Ledger And Caption Burden Policy v3.2.8 + v3.2.11 Issue Categories

After S5, human decisions are outside this assistant workflow.

## Core Rule

S2 and S5 are exploration/candidate stages. Their text reviews must produce a **paper-grounded issue ledger**, not a hard accept/reject verdict. The ledger records what may need attention; later human-guided stages decide how to use, rerun, combine, or discard a candidate.

Do not make `PASS`, `PASS_WITH_RISK`, `FAIL`, `BLOCKED`, `FLAG_MINOR`, `FLAG_MAJOR`, or similar labels the primary S2/S5 candidate conclusion by default. If a hard contradiction is visible, record it as a `BLOCKER_ISSUE` inside the issue ledger instead of silently removing the candidate from future consideration.

## Required Candidate Issue Ledger Schema

For every generated candidate image, write a candidate record with these fields:

```json
{
  "candidate_id": "<dynamic candidate id>",
  "candidate_image_path": "<project-relative path>",
  "audit_mode": "issue_inventory",
  "issues": [
    {
      "issue_id": "<stable id>",
      "severity": "minor | moderate | major | blocker",
      "category": "paper_semantics | symbol_text | connector_direction | artifact_lineage | core_visibility | layout_hierarchy | density | style_stage | caption_alignment | caption_burden | forbidden_assumption | symbol_as_box_error | edge_label_eligible_box_error | line_carried_variable_missing | visual_render_graph_violation | text_only_core_mechanism_error | bullet_list_substitution | over_decomposition | modularity_fragmentation | complex_internal_motif | unsupported_module_input | duplicate_edge | duplicate_workflow | excessive_background_context | flow_semantics_mismatch | prompt_rendering_contradiction | rerun_contract_drift | other",
      "description": "<concrete visual/text issue>",
      "evidence_basis": "<paper/S0/S1/S4/contract/image basis>",
      "rerun-eligibility": "easy | moderate | hard | not_rerunable | unknown",
      "must_fix_before_final": true,
      "downstream_use": "can_use_as_primary_direction | can_absorb_elements | needs_rerun_if_selected | avoid_as_final_basis | blocker_until_rerun"
    }
  ],
  "caption_alignment_issues": [],
  "caption_burden": "low | medium | high | unclear",
  "safe_caption_only_items": [],
  "must_be_visible_not_caption_only": [],
  "legend_or_caption_needed_for": [],
  "caption_risk_notes": [],
  "candidate_use_notes": "<how later stages may use this candidate>",
After S5, human decisions are outside this assistant workflow.
}
```

## Caption-Symbiosis Fields

S2/S5 issue ledgers must explicitly record whether a candidate can be explained by the eventual caption without overloading or contradicting the visual:

- `caption_alignment_issues`: mismatches between the candidate's panels, symbols, arrows, line styles, visual grouping, or reader order and the caption/legend plan.
- `caption_burden`: expected caption load if this candidate becomes the basis for the selected figure.
- `safe_caption_only_items`: details, caveats, numeric results, formula explanations, or implementation notes that are safe to keep out of image pixels and explain in caption/legend/body-reference text.
- `must_be_visible_not_caption_only`: core mechanisms, causal/algorithmic steps, artifact lineage, or non-droppable source-grounded concepts that must remain visible in the image and cannot be outsourced to caption prose.
- `legend_or_caption_needed_for`: arrow classes, colors, symbols, panels, or compressed repeated families that need a concise legend/caption sentence.
- `caption_risk_notes`: risks that the caption would have to work too hard, or would be tempted to compensate for an unresolved visual error.

A caption can explain compressed or omitted safe details, including edge-labeled symbols and merged micro-operations when the image remains semantically clear. A caption cannot fix false connectors, reversed arrows, forbidden topology, unsupported labels, edge-label-eligible variables drawn as standalone blocks, missing core visual anchors, text-only/bullet-only core mechanisms, or misleading area hierarchy.

## Severity And Rerunability Separation

Keep severity separate from rerun-eligibility. A visually small symbol error, a variable rendered as an unsupported box/chip, an edge-label-eligible metric turned into a node, a text-only core mechanism, a redundant duplicate edge, a fragmented module layout, a duplicated workflow, or an overly complex internal motif may be easy to rerun but still important for final correctness. A dense layout may be moderate severity and hard to rerun. A central-server, raw-data-sharing, or equivalent paper-contradicting visual relation is usually a blocker issue even if the drawing is otherwise attractive.

## Downstream Use

After S5, human decisions are outside this assistant workflow.

1. user preference;
2. paper-grounded direction fit;
3. candidate visual value;
4. issue severity;
5. rerun-eligibility;
6. caption burden;
7. high-priority-issue items.

This allows a candidate with rerunable issues to contribute layout grammar, reader path, visual hierarchy, or caption strategy without being prematurely discarded.

## Aggregate Behavior

S2/S5 embedded aggregate must preserve issue ledgers and may summarize issue counts, recurring risks, rerun-eligibility, and candidate-use notes. It must not convert the ledger into hard pass/fail rankings unless the user explicitly asks for a selection/ranking mode.
