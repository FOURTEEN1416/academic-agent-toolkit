---
name: statistical-theory-analysis
description: >
  Analyze theoretical properties of statistical methods under the formal
  formulation: identifiability, bias, variance, consistency, asymptotics,
  coverage, error bounds, robustness, and limitations.
metadata:
  category: domain
  trigger-keywords: "theory,proof,consistency,asymptotic normality,bias,variance,coverage,error bound,identifiability,robustness"
  applicable-stages: "4,5,6,7,8,9,10"
  priority: "1"
---

# Statistical Theory Analysis

## Overview

Use this skill after method proposal and before final experimental comparison.
Theory is required as a stage even if the final output is a simulation paper.

## Theory Outputs

Depending on the topic, provide:

- Identifiability argument
- Bias or variance calculation
- Consistency statement
- Asymptotic distribution
- Coverage or calibration argument
- Risk or error bound
- Robustness analysis
- Sensitivity or impossibility result
- Counterexample showing failure outside assumptions

## Theorem Template

```markdown
## Proposition
Under assumptions A1-Ak, method M satisfies ...

## Proof Sketch
1. ...
2. ...
3. ...

## Interpretation
This predicts that ...

## Limitations
The result does not cover ...
```

## Experimental Predictions

Every theoretical claim should produce an empirical prediction when possible:

- Direction of metric change
- Condition under which the method should improve
- Stress condition under which it should fail
- Baseline it should outperform

