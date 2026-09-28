---
name: stat-result-validator
description: >
  Validate statistical research outputs for formulation quality, method-to-
  problem alignment, theory presence, experimental evidence, fair comparison,
  artifact completeness, and final-claim consistency.
metadata:
  category: domain
  trigger-keywords: "validation,audit,formulation,theory,comparison,claims,statistical sanity,quality gate"
  applicable-stages: "10,11,12,13,14,15,16,17,20"
  priority: "1"
---

# Stat Result Validator

## Overview

Use this skill after formulation, method proposal, theory, experimental
evaluation, comparison, and result synthesis. It checks whether the final result
is supported by a coherent statistical research chain.

## Artifact Checks

Required for all topics:

```text
progress/<TOPIC_ID>/step0_problem_formulation.md
progress/<TOPIC_ID>/step1_method_proposal.md
progress/<TOPIC_ID>/step2_theory_analysis.md
progress/<TOPIC_ID>/step3_experimental_evaluation.md
progress/<TOPIC_ID>/step4_comparison.md
progress/<TOPIC_ID>/step5_result_synthesis.md
progress/<TOPIC_ID>/step6_quality_audit.md
experiments/<TOPIC_ID>/config.yaml
experiments/<TOPIC_ID>/results/metrics.json
experiments/<TOPIC_ID>/results/run_manifest.json
experiments/<TOPIC_ID>/results/comparison_summary.md
experiments/<TOPIC_ID>/results/claim_verdicts.json
experiments/<TOPIC_ID>/report/paper.md
experiments/<TOPIC_ID>/README.md
```

Analysis-specific source files and raw outputs are determined by the experiment
plan and should live under `experiments/<TOPIC_ID>/src/` and
`experiments/<TOPIC_ID>/results/`.

## Formulation Checks

The formulation must define:

- Observed data and sampling regime
- Data model or data source
- Target parameter, decision, prediction, or risk
- Assumptions
- Claims or hypotheses
- Evaluation criteria
- Theory targets

Blocking failures:

- No target or estimand.
- Claims cannot be measured.
- Assumptions are absent or incompatible with the proposed method.
- Evaluation criteria do not answer the research question.

## Method Checks

Verify that:

- The proposed method addresses the formulated target.
- Baselines are meaningful.
- Ablations isolate important design choices.
- Diagnostics are specified for likely failure modes.
- Method outputs match the metrics and theory targets.

## Theory Checks

Theory may be rigorous or partial, but it must be explicit.

Check for:

- Definitions and assumptions.
- Proposition, theorem, derivation, counterexample, or clearly labeled
  heuristic analysis.
- Predicted empirical patterns.
- Limitations and regimes not covered.

Blocking failures:

- No theory section at all.
- Theory analyzes a different target than the formulation.
- Final claims are stronger than the theory supports.

## Experimental Evidence Checks

Check that:

- Experiments test the formulated claims.
- Conditions are aligned with assumptions and stress tests.
- Proposed method, baselines, and ablations are run on comparable conditions.
- Failure counts are recorded.
- Runtime reductions are recorded in `run_manifest.json`.
- Metrics are grouped at the right level.

## Comparison Checks

Verify that:

- Comparisons include proposed method vs baseline.
- Ablations are interpreted.
- Experimental patterns are compared with theoretical predictions.
- Disagreements between theory and experiments are discussed.
- Claim verdicts cite both theoretical and empirical support when available.

## Final Claim Checks

Every final claim must be traceable to:

```text
formulation -> method -> theory -> experiment -> comparison
```

Use:

- `PASS`: formulation, theory, experiments, and comparisons support the claims.
- `WARN`: usable but has limitations that must be disclosed.
- `FAIL`: missing formulation, theory, evidence, or fair comparison prevents a
  valid conclusion.

