---
name: stat-research-orchestrator
description: >
  Orchestrate a statistical research pipeline centered on formal problem
  formulation, method proposal, theoretical analysis, experimental evaluation,
  comparison, and final result synthesis.
metadata:
  category: domain
  trigger-keywords: "statistics,statistical research,problem formulation,method proposal,theory,experiments,comparison,results"
  applicable-stages: "1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,20"
  priority: "1"
---

# Statistical Research Orchestrator

## Overview

Coordinates the full statistical research pipeline. This is not a code-first
benchmark workflow. The pipeline begins with formal problem formulation and
requires theory before final comparisons and conclusions.

## Full Pipeline

```text
Topic prompt / topic file / dataset description
  -> [stat-problem-formulator]   formal problem, notation, assumptions, targets
  -> [stat-method-proposer]      proposed method, baselines, diagnostics, ablations
  -> [stat-theory-analyzer]      theoretical properties, proof sketches, predictions
  -> [stat-experiment-designer]  experiments, code, metrics, manifest
  -> [stat-comparison-analyst]   method comparison, theory-vs-experiment check
  -> [stat-result-synthesizer]   final report, conclusions, limitations
  -> [stat-quality-auditor]      formulation/theory/evidence audit
```

## Workflow

### Step 0: Invoke stat-problem-formulator

Provide the topic source and any requirements. Wait for:

```text
progress/<TOPIC_ID>/step0_problem_formulation.md
```

Read:

- Formal data model
- Target parameter or decision target
- Assumptions
- Hypotheses or claims
- Evaluation criteria
- Theory targets

Do not proceed if the target or assumptions are undefined.

### Step 1: Invoke stat-method-proposer

Provide the problem formulation. Wait for:

```text
progress/<TOPIC_ID>/step1_method_proposal.md
```

Read:

- Proposed method
- Baselines
- Oracle references, if any
- Ablations
- Diagnostics
- Implementation requirements

### Step 2: Invoke stat-theory-analyzer

Provide the formulation and method proposal. Wait for:

```text
progress/<TOPIC_ID>/step2_theory_analysis.md
```

Read:

- Theoretical claims
- Required assumptions
- Proof sketches or derivations
- Predicted empirical patterns
- Limitations

Theory can be partial, but the report must honestly label what is proven,
heuristic, or only experimentally supported.

### Step 3: Invoke stat-experiment-designer

Provide formulation, method, and theory. Wait for:

```text
progress/<TOPIC_ID>/step3_experimental_evaluation.md
```

Read:

- Config path
- Code paths
- Metrics
- Manifest
- Raw results
- Runtime deviations

### Step 4: Invoke stat-comparison-analyst

Provide theory predictions and experiment outputs. Wait for:

```text
progress/<TOPIC_ID>/step4_comparison.md
```

Read:

- Comparison summary
- Figures and tables
- Claim verdicts
- Theory-experiment agreements and disagreements

### Step 5: Invoke stat-result-synthesizer

Provide all previous artifacts. Wait for:

```text
progress/<TOPIC_ID>/step5_result_synthesis.md
```

Read:

- Paper path
- README path
- Final claims
- Limitations

### Step 6: Invoke stat-quality-auditor

Audit the whole research chain:

- Was the problem formulated formally?
- Does the method address that formulation?
- Is there theory or an explicit reason theory is limited?
- Do experiments test theoretical predictions?
- Are comparisons fair?
- Are final conclusions supported?

Wait for:

```text
progress/<TOPIC_ID>/step6_quality_audit.md
```

## Progress File Specification

### `progress/<TOPIC_ID>/step0_problem_formulation.md`

```markdown
# Step 0: Problem Formulation
## Status: PASS / FAIL
## Topic ID: <TOPIC_ID>
## Research Question
...
## Formal Data Model
...
## Target / Estimand
...
## Assumptions
- ...
## Claims / Hypotheses
- ...
## Evaluation Criteria
- ...
## Theory Targets
- ...
## Blocking Ambiguities
- ...
```

### `progress/<TOPIC_ID>/step1_method_proposal.md`

```markdown
# Step 1: Method Proposal
## Status: PASS / FAIL
## Proposed Method
...
## Baselines
- ...
## Diagnostics
- ...
## Ablations
- ...
## Method-to-Claim Map
- ...
```

### `progress/<TOPIC_ID>/step2_theory_analysis.md`

```markdown
# Step 2: Theoretical Analysis
## Status: PASS / PARTIAL / FAIL
## Definitions
...
## Main Claims
- ...
## Proof Sketches
- ...
## Assumptions Required
- ...
## Predicted Empirical Patterns
- ...
## Limitations
- ...
```

### `progress/<TOPIC_ID>/step3_experimental_evaluation.md`

```markdown
# Step 3: Experimental Evaluation
## Status: PASS / FAIL
## Config
experiments/<TOPIC_ID>/config.yaml
## Code
- ...
## Experiments
- ...
## Metrics
experiments/<TOPIC_ID>/results/metrics.json
## Manifest
experiments/<TOPIC_ID>/results/run_manifest.json
## Warnings
- ...
```

### `progress/<TOPIC_ID>/step4_comparison.md`

```markdown
# Step 4: Comparison
## Status: PASS / FAIL
## Baseline Comparisons
- ...
## Ablation Findings
- ...
## Theory vs Experiment
- ...
## Claim Verdicts
experiments/<TOPIC_ID>/results/claim_verdicts.json
```

### `progress/<TOPIC_ID>/step5_result_synthesis.md`

```markdown
# Step 5: Result Synthesis
## Status: PASS / FAIL
## Paper
experiments/<TOPIC_ID>/report/paper.md
## README
experiments/<TOPIC_ID>/README.md
## Final Claims
- ...
## Limitations
- ...
```

### `progress/<TOPIC_ID>/step6_quality_audit.md`

```markdown
# Step 6: Quality Audit
## Status: PASS / WARN / FAIL
## Formulation Check
- ...
## Theory Check
- ...
## Experiment Check
- ...
## Comparison Check
- ...
## Blocking Issues
- ...
```

## Key Conventions

- Formulation is the gatekeeper. Do not write code before the target,
  assumptions, and evaluation criteria are explicit.
- Theory is required as a pipeline stage. If no theorem is possible, write a
  clear heuristic or negative analysis and explain why.
- Experiments should test theoretical predictions, not merely produce numbers.
- Comparisons must include meaningful baselines or ablations.
- Final results must connect formulation, method, theory, experiments, and
  comparison.

