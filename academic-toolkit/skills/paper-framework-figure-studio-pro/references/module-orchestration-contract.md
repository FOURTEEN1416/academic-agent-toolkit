# Module Orchestration Contract

> v3.2.15f override: the assistant workflow ends at S5. This policy applies only to S0-S5 responsibilities and cannot create an assistant stage after S5.


Use only the reference modules needed for the current step.

- S0-PAPER-FOUNDATION: `references/s0-paper-foundation-template.md`.
- S1-FIGURE-STRATEGY and S2-SKETCH-EXPLORE: `references/modules/s1-s2-strategy-and-sketch.md`.
- S3-DIRECTION-SELECT through S5-CANDIDATE-IMAGE: `references/modules/s3-to-s5-candidates.md`.

Always keep `references/s0-foundation-readiness-and-candidate-status-policy-v316.md` available when S0 foundation readiness, author supplementation, S2/S3 flagged sketch review, or S4 prompt-risk transfer affects the current step. Do not load inactive strict S2/S5 connector-table policies as a user-selectable contract option.

Load `references/s2-s5-image-only-terminal-orchestration-policy-v3215.md` whenever entering or resuming S2/S5. It controls the active image-only behavior. Inactive dynamic substage material must not reintroduce candidate-level rerun, standalone audit, or aggregate substages.

Load `references/candidate-artifact-id-coherence-policy-v3215.md` whenever reading or writing prompt-index, candidate registry, generated image records, artifact records, status files, checkpoint inventories, or user-facing image-generation guidance. Prompt-index `candidate_id` is the source of truth once it exists.

Load `references/substage-user-guidance-policy-v316.md` only for compatibility with existing state guidance. Do not use it to offer contract-setting choices or post-S5 continuation.

Load `references/continue-next-action-policy-v316.md` whenever the user asks to continue, resume, run the saved next prompt, or otherwise gives an ambiguous continuation request. Resolve the next action from `state/project-state.json`, `next_prompt_registry`, `substage_guidance_registry`, and file scans before relying on conversation memory.


Active route:

```text
After S5, human decisions are outside this assistant workflow.
```

After S5, human decisions are outside this assistant workflow.
