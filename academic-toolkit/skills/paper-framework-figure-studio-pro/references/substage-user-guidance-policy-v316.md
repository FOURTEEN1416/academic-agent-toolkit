# Substage User Guidance Policy v3.2.13

Only S2 and S5 have substages, and those substages are image-generation-only chunks.

- S1 writes the S2 prompt-index and guidance.
- S4 writes the S5 prompt-index and guidance.
- S3 writes S3 review/aggregate materials from S2 outputs as part of direction selection.
- S2/S5 image chunks must not provide audit, ranking, explanation, revision guidance, or next-step prose.

S5 terminal replies must end with:

```text
我的任务已经完成，剩下由人类来决策。
```
