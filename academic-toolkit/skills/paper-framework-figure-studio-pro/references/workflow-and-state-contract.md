# Workflow And State Contract v3.2.13

Public workflow:

```text
Bootstrap -> S0-PAPER-FOUNDATION -> S1-FIGURE-STRATEGY -> S2-SKETCH-EXPLORE -> S3-DIRECTION-SELECT -> S4-CANDIDATE-BRIEF -> S5-CANDIDATE-IMAGE -> END
```

S1 must include the S2 prompt-package preparation responsibilities. S3 must include the S3 review/aggregate responsibilities over S2 outputs. S4 must include the S5 prompt-package preparation responsibilities.

S2 and S5 are image-generation-only public stages. They must not write audit, ranking, explanatory, checkpoint-narrative, revision, caption, or next-step prose.

S5 is terminal. State schemas, manifests, checkpoint logic, and guidance registries must not create any assistant workflow after S5.
