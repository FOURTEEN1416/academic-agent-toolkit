---
name: statistical-problem-formulation
description: >
  Formulate statistical research problems with formal notation, target
  parameters, assumptions, hypotheses, evaluation criteria, and theory targets.
metadata:
  category: domain
  trigger-keywords: "problem formulation,statistical formulation,estimand,assumptions,data model,hypothesis,theory target"
  applicable-stages: "1,2,3,4,5"
  priority: "1"
---

# Statistical Problem Formulation

## Overview

Use this skill before any method design, theory, experiment, or report writing.
The goal is to transform a broad topic into a precise statistical problem.

## Required Formulation Elements

| Element | Questions |
|---|---|
| Observed data | What is observed? What is the sample size? Are samples iid, dependent, clustered, censored, or selected? |
| Data model | What family of distributions or data-generating processes is considered? |
| Target | What parameter, decision, prediction, or risk is the object of study? |
| Assumptions | What must hold for the target to be identifiable or the method to work? |
| Hypotheses | What claims should be supported, refuted, or made inconclusive? |
| Criteria | What metrics define success or failure? |
| Theory target | What property should be derived: bias, variance, consistency, rate, coverage, error bound, robustness, or impossibility? |

## Handoff Schema

The problem formulation should be precise enough to support this structured
handoff:

```yaml
topic_id: TXX
title: ""
research_question: ""
observed_data:
  notation: ""
  sampling: iid | dependent | clustered | time_series | selected | unknown
data_model:
  notation: ""
  family: ""
target:
  name: ""
  notation: ""
  type: estimand | decision | prediction | risk | descriptive_quantity
  truth_source: analytic | simulation | oracle | empirical_reference | not_applicable
assumptions:
  structural: []
  sampling: []
  regularity: []
  identifiability: []
claims:
  - id: C1
    statement: ""
    formal_statement: ""
evaluation_criteria:
  - name: ""
    direction: ""
theory_targets:
  - identifiability
  - bias
  - consistency
blocking_ambiguities: []
```

## Template

```markdown
# Problem Formulation

## Research Question
...

## Observed Data
Let ...

## Data-Generating Model
Assume ...

## Target / Estimand
Define ...

## Candidate Procedure Class
We consider procedures ...

## Assumptions
1. ...

## Claims / Hypotheses
- ...

## Evaluation Criteria
- ...

## Theoretical Questions
- ...

## Experimental Questions
- ...
```

## Quality Bar

A formulation passes only if another researcher could implement or analyze the
problem without guessing the target, assumptions, or success criteria.
