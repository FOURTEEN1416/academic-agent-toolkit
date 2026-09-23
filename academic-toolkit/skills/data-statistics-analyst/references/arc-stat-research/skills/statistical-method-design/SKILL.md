---
name: statistical-method-design
description: >
  Design statistical methods, baselines, diagnostics, variants, and ablations
  that directly address a formal problem formulation.
metadata:
  category: domain
  trigger-keywords: "method proposal,estimator,algorithm,baseline,ablation,diagnostic,statistical method"
  applicable-stages: "3,4,5,6,7,8"
  priority: "1"
---

# Statistical Method Design

## Overview

Use this skill after formal problem formulation. The method should be a response
to the formal target and assumptions, not a generic collection of techniques.

## Required Method Proposal

For each method:

- Name
- Problem it solves
- Formula or algorithm
- Inputs and outputs
- Tuning parameters
- Required assumptions
- Diagnostics
- Expected failure modes
- Computational cost
- Relation to baselines

## Baselines and Ablations

Always define meaningful baselines:

- Classical or standard method
- Naive or unadjusted method
- Oracle or idealized reference when available
- Robust variant
- Ablation removing the key design feature

## Method-to-Claim Map

Every method must connect to at least one claim:

```yaml
method_to_claim_map:
  proposed_method:
    claims: [C1, C2]
    expected_evidence: "lower risk under stress condition"
    theory_target: "consistency under assumptions A1-A3"
```

