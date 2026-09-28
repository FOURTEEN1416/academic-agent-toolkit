# S4 Formal Candidate Brief Template v3.2.15f

This template is for S4-CANDIDATE-BRIEF. It prepares exactly two S5 formal candidate prompts and prompt-index entries. S5 is image-generation-only and terminal; human selection after S5 is outside the assistant workflow.

## Candidate ID Coherence

- The prompt-index row `candidate_id` is the source of truth for each S5 formal candidate.
- Default S5 candidate IDs are `F01` and `F02`.
- Do not rewrite formal candidate IDs as `C01`, `C02`, numeric IDs, or runtime-generated image names.
- For every row, keep this equality chain coherent:
  - `candidate_id`
  - `prompt_path`
  - `target_image_path`
  - candidate registry key
  - artifact `candidate_id`
  - active image path
  - checkpoint image inventory entry

Example default S5 row:

```json
{
  "candidate_id": "F01",
  "prompt_path": "outputs/S5-candidate-image/candidates/F01/prompt-v01.md",
  "target_image_path": "outputs/S5-candidate-image/candidates/F01/image-v01.png"
}
```

## S4 Two-Candidate Matrix Fields

For complete-paper / framework / method-overview tasks, prepare exactly two generic formal candidate briefs. Each brief should include:

| Field | Required content |
|---|---|
| candidate_id | Exact formal candidate ID, `F01` or `F02` |
| prompt_path | Prompt package path containing the same candidate ID segment |
| target_image_path | Target image path containing the same candidate ID segment |
| visual treatment | Clean formal schematic treatment, not paper-specific hardcoding |
| reader path | 3-5 anchor path for first-glance comprehension |
| figure-caption symbiosis plan | What the figure shows versus what surrounding text/caption should explain outside the image |
| issue-ledger transfer | S2 issues converted into S5 negative constraints |
| prompt-risk transfer | Forbidden topology, wrong edge directions, variable-as-block risks, unsupported modules |
| edge / port contract | Source, target, direction, label policy, and forbidden alternatives |
| visible text whitelist | Short labels and symbols allowed in the figure |
| internal motif plan | Pictorial micro-chain for core composite modules |
| density budget | Explicit compression for repeated entities, samples, rows, panels, legends, arrows, whitespace, and context insets |
| S0 semantic precision locks | Carry-forward of `role_visual_realization_contract`, `process_instance_budget`, and `forbidden_misimplementation_locks`; especially whether repeated roles/conditions may or may not become full lanes |
| layout density / area budget | Compact-balanced canvas plan with primary method occupancy, context inset cap, legend/note cap, and center-of-gravity check; physical-layout exception only when source-supported |
| palette strategy | Human-aesthetic palette with paper-supported color semantics |
| palette anti-AI rules | No generic blue/purple gradients, neon saturation, glossy orb/glass effects, bokeh, poster lighting, or decorative rainbow ramps |
| color accessibility note | Contrast and grayscale-legibility note |
| generation note | S5 only generates images and ends the assistant workflow |

## Strict Prompt Contract Checklist

For every S5 prompt package, record and pass before prompt-index finalization:

- edge-support ledger for every connector, including upstream/downstream evidence anchors;
- connector multiplicity audit: one bundled connector between two block-level modules unless distinct labeled quantities are source-supported;
- edge-label-first variable placement: transferred variables on connectors, ports, forks, merges, or tags;
- modularity-not-fragmentation gate: primary modules remain coherent containers, not scattered micro-blocks;
- simple internal motif gate: submodule diagrams use common, minimal conventions that reviewers can read quickly;
- redundancy gate: no duplicate workflow in a main block and an inset; no repeated full workflow lanes without distinct source-supported meaning;
- S0 semantic precision gate: no vague S0 phrase may be treated as drawing permission; repeated roles/conditions follow the S0 role-realization decision and duplicate full pipelines remain forbidden unless source-supported;
- background/context budget gate: context remains small and the method framework remains dominant;
- layout density and mainline balance gate: compact-balanced manuscript density, no empty quadrants, no top-heavy context panels, no scattered micro-block islands, and primary method content centered and dominant;
- audit/repair cycle log, maximum five cycles.
- data consumer/transformer ledger and false relay data-flow audit.

Every image-generation prompt must include these hard constraints inside the prompt text itself.

## Prompt-Index Generation Checklist

- Write `outputs/S5-candidate-image/prompt-index.json` before S4 closes.
- Use list-shaped `candidates[]` rows plus `candidate_map` compatibility if produced by script.
- Validate that each `prompt_path` exists.
- Validate that each `target_image_path` parent directory matches the same `candidate_id`.
- Validate that stage manifest/substage plan candidate IDs come from prompt-index, not from a separate default renumbering.

## S5 Handoff Text

Suggested handoff prompts should say:

```text
请使用 paper-framework-figure-studio-pro skill，根据当前状态和 prompt-index，执行 S5-CANDIDATE-IMAGE 的 IMAGE_GENERATE。
```

Do not mention versioned ZIP filenames in suggested prompts.
