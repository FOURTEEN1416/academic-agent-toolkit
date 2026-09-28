# Continue / Next Action Policy v3.2.13

Use the canonical step order: S0 -> S1 -> S2 -> S3 -> S4 -> S5 -> END.

- S1 must prepare the S2 prompt-index before closing.
- S3 must review/aggregate S2 exploration images before selecting a direction.
- S4 must prepare the S5 prompt-index before closing.
- S2 and S5 are image-generation-only public stages.
- S5 is terminal; no assistant workflow follows it.

When S5 is complete or the user asks what remains after S5, respond exactly:

```text
我的任务已经完成，剩下由人类来决策。
```
