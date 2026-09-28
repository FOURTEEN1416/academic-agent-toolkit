# State Footer Template v3.2.15f

全流程：S0-PAPER-FOUNDATION -> S1-FIGURE-STRATEGY -> S2-SKETCH-EXPLORE -> S3-DIRECTION-SELECT -> S4-CANDIDATE-BRIEF -> S5-CANDIDATE-IMAGE -> END

当前 step：`<CURRENT_STEP>`
默认下一步：`<DEFAULT_NEXT_STEP_OR_NONE>`

Every text step response must state the exact current public step ID, state that the public step has ended, state that the next public step has not been executed, and provide only the next copyable prompt. S1 prepares exactly four C01-C04 S2 prompt packages after eight-to-four style-combination selection. S4 prepares exactly two F01-F02 S5 prompt packages and row-level S2 reference image paths. S2 and S5 are image-generation-only stages and do not contain text review, candidate-level revision, review, or aggregate substages.

After S5, do not provide a next workflow prompt. Use this terminal line:

```text
我的任务已经完成，剩下由人类来决策。
```
