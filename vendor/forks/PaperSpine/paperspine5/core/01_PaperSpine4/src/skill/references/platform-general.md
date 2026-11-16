# External Detector Observation (Legacy Compatibility)

This reference is retained so older configurations with
`detection_platform=general` remain readable. It is not a detector-optimization
profile and does not define a manuscript readiness gate.

Use `references/humanize.md` for the canonical Authorial Voice Restoration
workflow. That workflow restores the author's own scholarly voice after claims
and evidence are frozen, while preserving numbers, units, citations, formulas,
protected terms, negation, causal direction, modality, uncertainty, and claim
strength.

If the author voluntarily supplies a third-party detector result, record it as
an external observation with the tool name, date, manuscript hash, and report
path. Do not tune prose to the score, infer authorship from it, fabricate an AI
percentage, or use it to pass or fail the paper. Evaluation and adoption rules
are in `references/humanize-calibration.md`.
