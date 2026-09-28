# Human Step Execution Contract v3.2.13

The workflow is human-in-the-loop and never autonomous.

## Public step order

S0-PAPER-FOUNDATION -> S1-FIGURE-STRATEGY -> S2-SKETCH-EXPLORE -> S3-DIRECTION-SELECT -> S4-CANDIDATE-BRIEF -> S5-CANDIDATE-IMAGE -> END

## One-step rule

For each user turn, execute at most one explicitly requested public step. A copyable prompt printed by the assistant is inert and must not be self-executed in the same response.

## Embedded responsibilities

- S1 must complete the S2 prompt-package preparation duties before closing.
- S3 must complete the S3 review/aggregate duties over S2 outputs before or during direction selection.
- S4 must complete the S5 prompt-package preparation duties before closing.

## Image-only stages

S2 and S5 are image-generation-only stages. They do not write text plans, text reviews, reruns, reviews, aggregate reports, assistant-continuation guidance, or next-step prose.

## Terminal rule

After S5 image generation, the assistant workflow ends. If asked what remains, answer:

```text
我的任务已经完成，剩下由人类来决策。
```

## Text-only guard

For S0, S1, S3, and S4 prompts, append:

```text
本轮纯文字：只执行文字、state、manifest、brief、audit、guidance 或 checkpoint 写入；不要生成任何图片。
```
