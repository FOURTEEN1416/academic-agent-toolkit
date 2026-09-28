# Public-Stage Human Wait Barrier Policy v3.2.15f

This policy is mandatory for the top-level workflow orchestration. It is stronger than reviewer gates, checkpoint gates, and internal agent handoffs.

## Hard Barrier

After a public stage closes, the workflow must stop before the next public stage. The next public stage may start only after one of these is recorded:

- a later explicit user message requesting that exact next stage;
- a user decision that explicitly selects a source-allowed skip/default/automation path;
- a source-allowed explicit automation choice already recorded before the barrier.

Reviewer approval, specialist completion, internal handoff, checkpoint success, silent defaults, generated guidance, copyable prompts, and assistant-written next-step text do not satisfy the barrier.

## Stage Boundaries

- S0 may prepare the foundation and suggest S1; it must not execute S1.
- S1 may prepare C01-C04 S2 prompt packages and prompt-index; it must not generate S2 images.
- S2 may generate C01-C04 images only; it must not run S3 review, ranking, or selection.
- S3 may review/aggregate S2 outputs and select direction; it must not execute S4.
- S4 may prepare F01-F02 S5 prompt packages and prompt-index; it must not generate S5 images.
- S5 is terminal; after image generation the assistant workflow ends.

## User-Facing Closure

Every text public-stage closure for S0-S4 must state:

- the exact public stage that has ended;
- that the next public stage has not been executed;
- the copyable next prompt, if allowed.

If the orchestrator detects an attempt to cross a public-stage boundary without the required recorded user input or explicit source-allowed automation, it must stop and report the concrete missing barrier satisfaction. Internal agent orchestration inside the current public stage remains allowed, but it cannot replace the public-stage human wait.
