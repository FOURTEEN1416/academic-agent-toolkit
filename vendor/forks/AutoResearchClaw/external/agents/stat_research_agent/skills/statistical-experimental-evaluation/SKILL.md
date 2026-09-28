---
name: statistical-experimental-evaluation
description: >
  Design and run statistical experiments that test the formal problem,
  proposed methods, theoretical predictions, baselines, and ablations.
metadata:
  category: domain
  trigger-keywords: "experiment,simulation,evaluation,comparison,baseline,ablation,metrics,diagnostics,statistical evidence"
  applicable-stages: "7,8,9,10,11,12,13,14"
  priority: "1"
---

# Statistical Experimental Evaluation

## Overview

Use this skill after formulation, method proposal, and theory. Experiments
should test specific claims and theoretical predictions.

## Experiment Plan

Define:

- Conditions or data-generating processes
- Real data source or synthetic data generator
- Sample sizes, folds, repetitions, seeds, or resamples
- Proposed method
- Baselines
- Ablations
- Diagnostics
- Metrics
- Failure accounting

## Required Artifacts

```text
experiments/<TOPIC_ID>/config.yaml
experiments/<TOPIC_ID>/src/
experiments/<TOPIC_ID>/results/metrics.json
experiments/<TOPIC_ID>/results/run_manifest.json
experiments/<TOPIC_ID>/results/comparison_summary.md
experiments/<TOPIC_ID>/results/claim_verdicts.json
experiments/<TOPIC_ID>/report/paper.md
experiments/<TOPIC_ID>/README.md
```

## Evidence Schema

Use a row-oriented metric format:

```json
{
  "topic_id": "TXX",
  "metric_rows": [
    {
      "claim_id": "C1",
      "method": "proposed_method",
      "baseline": "standard_method",
      "condition": "stress_condition",
      "metric": "risk",
      "value": 0.12,
      "status": "ok"
    }
  ]
}
```

Claim verdicts should connect theory and experiments:

```json
[
  {
    "claim_id": "C1",
    "verdict": "supported",
    "theory_support": "Proposition 1 under A1-A3",
    "experimental_support": "Proposed method has lower risk in conditions X-Y",
    "comparison": "Outperforms baseline B on metric M",
    "limitations": "Finite sample only; assumption A2 not tested"
  }
]
```

## Evidence Rules

- A metric must map to a formulated claim.
- A comparison must use the same data conditions across methods.
- Failed runs must be counted.
- Runtime reductions must be recorded.
- Results must be interpreted against theoretical predictions.
