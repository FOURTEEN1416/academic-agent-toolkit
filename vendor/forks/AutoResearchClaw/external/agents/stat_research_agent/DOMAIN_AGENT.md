---
name: statistical-research-agent
domain: statistics
description: >
  Domain-specific agent pack for statistical research. It formulates statistical
  problems, proposes methods, analyzes theory, designs experiments, compares
  evidence, synthesizes results, and audits final claims.
entrypoint_skill: stat-research-orchestrator
version: 0.1.0
---

# Statistical Research Agent

## Domain

Statistics, including:

- Statistical problem formulation
- Estimation and inference
- Hypothesis testing
- Causal inference
- Prediction and validation
- Robustness and sensitivity
- Simulation and empirical method evaluation
- Statistical theory and proof sketches

## Entrypoint Skill

```text
skills/stat-research-orchestrator/SKILL.md
```

## Agents

```yaml
agents:
  - name: stat-problem-formulator
    path: agents/stat-problem-formulator.md
    role: Formalize data model, target, assumptions, claims, and theory targets.
  - name: stat-method-proposer
    path: agents/stat-method-proposer.md
    role: Propose methods, baselines, diagnostics, and ablations.
  - name: stat-theory-analyzer
    path: agents/stat-theory-analyzer.md
    role: Analyze theoretical properties and predicted empirical behavior.
  - name: stat-experiment-designer
    path: agents/stat-experiment-designer.md
    role: Design and run experiments that test claims and theory.
  - name: stat-comparison-analyst
    path: agents/stat-comparison-analyst.md
    role: Compare methods, baselines, ablations, and theory predictions.
  - name: stat-result-synthesizer
    path: agents/stat-result-synthesizer.md
    role: Synthesize final report, claims, limitations, and reproducibility notes.
  - name: stat-quality-auditor
    path: agents/stat-quality-auditor.md
    role: Audit formulation, method, theory, evidence, and final claims.
```

## Skills

```yaml
skills:
  - name: stat-research-orchestrator
    path: skills/stat-research-orchestrator/SKILL.md
  - name: statistical-problem-formulation
    path: skills/statistical-problem-formulation/SKILL.md
  - name: statistical-method-design
    path: skills/statistical-method-design/SKILL.md
  - name: statistical-theory-analysis
    path: skills/statistical-theory-analysis/SKILL.md
  - name: statistical-experimental-evaluation
    path: skills/statistical-experimental-evaluation/SKILL.md
  - name: stat-result-validator
    path: skills/stat-result-validator/SKILL.md
```

## Operating Rules

- Formal problem formulation is mandatory and comes first.
- Theory is mandatory as a stage, even if it is partial or heuristic.
- Experiments must test formulated claims and theoretical predictions.
- Comparisons must include meaningful baselines or ablations.
- Final claims must trace to formulation, method, theory, experiment, and
  comparison.

