# Figure Story: Scientific Images as First-Class Evidence

Use this playbook whenever the paper contains existing scientific figures or
needs new/redesigned figures. Set `figure_policy` to `existing_only` or
`generate_or_redesign`; use `none` only for a genuinely text-only work.

The goal is not to decorate finished prose. A figure is a compressed argument:
the paper's contribution determines the figure question, the figure determines
the Results unit, and the actual rendered image can falsify the intended prose.

## 1. Understand the Existing Images Before Planning Prose

Render or open every existing figure at page scale and close scale with a
multimodal tool. For each complete figure and each panel, identify:

- the scientific question and the single dominant claim;
- the hero panel where the claim becomes visible;
- every panel's job (setup, mechanism, primary result, comparison, ablation,
  diagnostic, boundary, or interpretation);
- what is actually measured, inferred, or merely illustrated;
- visible methods, datasets, metrics, baselines, units, uncertainty, sample
  size, and statistical marks;
- the intended reading order and the conclusion a careful reader can earn;
- conflicts among the pixels, source data, caption, Results text, and planned
  contribution.

Do not infer the meaning of an image from its filename or caption alone. If an
existing figure contradicts prose or evidence, treat the visible conflict as a
scientific issue: correct the source figure, narrow the claim, or ask the user.

## 2. Make One Figure Decision

For each figure choose `keep`, `redesign`, or `create`.

- **keep:** the image already carries the required claim and is publication-ready;
- **redesign:** the evidence is valid but hierarchy, panel logic, legibility, or
  visual grammar prevents the claim from reading clearly;
- **create:** the contribution needs a visual argument that does not yet exist.

Reference figures teach persuasion mechanisms and visual grammar, never project
facts. Preserve real project evidence and the current paper's terminology.

## 3. Write the Single Figure Story Contract

Create `figure_requests.json`. This same contract is the storyboard, the
PaperFigure/FigMirror handoff, and the Results-to-figure trace; do not create a
second figure rationale form.

Each request contains the existing integration fields plus:

```json
{
  "decision": "redesign",
  "figure_role": "primary-result",
  "scientific_question": "Which condition changes the primary outcome?",
  "claim": "Condition A improves the primary outcome over the declared baseline.",
  "intended_conclusion": "The improvement is consistent across the main evaluation units.",
  "claim_boundary": "The figure does not establish mechanism or external generalization.",
  "results_units": ["R2: Primary comparison"],
  "hero_panel": "B",
  "panels": [
    {
      "panel_id": "B",
      "question": "Does the main comparison support the contribution?",
      "role": "primary result",
      "evidence_anchor": "scientific_evidence_ledger.json#FACT-012",
      "intended_reading": "A is higher than the baseline with the declared uncertainty."
    }
  ]
}
```

One dominant claim may require multiple panels, but multiple unrelated claims
require separate figures. `claim_boundary` is affirmative restraint, not timid
language: write the strongest conclusion the visible evidence earns.

Run:

```bash
python scripts/figure_story_check.py paper_rewriting_output --phase planning --markdown --write
```

## 4. Let the Figure Structure the Results

Write each major Results unit as question -> visible evidence -> bounded answer.
Use the hero panel as the anchor, then bring in supporting panels only for the
jobs declared in the contract. Do not narrate panels chronologically (`A shows`,
`B shows`, `C shows`) when the scientific claim provides a stronger structure.

The contract is a starting point, not finished prose. Develop the evidence into
a reader-guided unit: establish why the question comes next, surface the
decisive comparison or quantitative anchor, explain what changes in the paper's
argument, and bridge to the next question. Use this sequence flexibly; do not
force every result into the same paragraph template.

The introduction and discussion may not promise more than the figure and its
evidence anchors support. The caption is the second explanation layer: it must
identify panels, entities, measurements, uncertainty/statistics, and boundaries
without trying to repair an incoherent image.

## 5. Generate or Redesign Through PaperFigure

Route `redesign` and `create` requests through the existing PaperFigure/FigMirror
integration. The scientific-story fields must reach every candidate generation
request. Candidate diversity concerns how to communicate the same verified
story, not permission to change the scientific claim.

For `keep`, bind the project-owned `current_figure` in the same request and do
not create ceremonial A/B candidates. The integration records that asset as
`selected_candidate=existing`, retains its verified story, and carries it
through the same body contract and final-pixel audit. `redesign` also requires
`current_figure`, because the existing visual is the content and improvement
baseline even though only its new candidates may be selected.

Keep the candidate that makes the main conclusion fastest to see while retaining
the declared evidence density, panel jobs, and boundary. A beautiful candidate
that changes topology, labels, data, panel meaning, or statistical semantics
fails.

## 6. Re-read the Actual Final Image

After candidate confirmation, consume `figure_body_contract.json` as the only
PaperFigure-to-body interface. It binds the selected publication asset and
editable source by SHA-256 to the caption, LaTeX label, Results units, allowed
claim, intended conclusion, claim boundary, hero panel, and panel evidence
anchors. Do not recover these facts from filenames or rewrite them from memory.

Every assembled figure must be genuinely cited by the manuscript body with
`\ref`, `\autoref`, or `\cref`; a copied asset, caption, or `\label` without a
body reference is not integrated. Use the named Results units to decide where
the figure is interpreted, while retaining PaperSpine authority over prose.

After final assembly, render every figure again and inspect the pixels rather
than trusting the intended specification. Compare the final image against:

- dominant claim and intended conclusion;
- hero panel and every panel role;
- evidence anchors and data bindings;
- claim boundary;
- caption and corresponding Results unit.

Record `story_claim_alignment`, `panel_role_alignment`, and
`claim_boundary_respected` in `visual_audit_manifest.json`, including panel-level
receipts. The actual final image is authoritative. If it cannot support the
contract, revise the image or the manuscript and invalidate the old receipt.

Run the final contract check only after visual inspection:

```bash
python scripts/figure_story_check.py paper_rewriting_output --phase final --markdown --write
```

This gate should preserve agent autonomy: it checks whether the scientific
argument is complete and internally aligned, not whether the Agent filled a
preferred prose template or used a predetermined visual style.

The final check also verifies `figure_body_contract.json`, publication/editable
asset hashes, declared labels, and real body references. A changed asset or a
figure never referenced by the manuscript invalidates completion.

Figure assembly is an intermediate milestone. The integration remains at
`awaiting_paper_integration` after publishing the body contract and reaches
`complete` only after PaperSpine reports `is_complete=true` with all five
readiness dimensions green. Use the integration `workflow` command or local
`GET /api/workflow` to inspect the live chain from figure understanding through
the final pixel audit.

Finally read the assembled PDF in page order. A figure that is individually
correct but floats away from the Results unit that interprets it has not yet
completed its editorial job; reposition the float or repair the transition.
