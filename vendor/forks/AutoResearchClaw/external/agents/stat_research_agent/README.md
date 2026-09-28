# Statistical Research Domain Agent

Domain-specific agent pack for statistical research. This pack is intentionally
separate from the existing metabolic modelling `src/` suite.

The domain is statistics. The workflow is research-first:

```text
formulate problem
  -> propose method
  -> analyze theory
  -> evaluate experimentally
  -> compare
  -> synthesize results
  -> audit quality
```

The most important artifact is the formal problem formulation. Code and metrics
are downstream evidence, not the starting point.

## Domain Agent Format

```text
stat_research_agent/
  DOMAIN_AGENT.md
  agents/
    *.md
  skills/
    <skill-name>/SKILL.md
```

This mirrors the domain-specific agent style used by the existing project:

- `agents/*.md` define execution roles.
- `skills/*/SKILL.md` define reusable domain workflows.
- The domain manifest declares the entrypoint, agents, skills, artifacts, and
  operating rules.

## Agent vs Skill

```text
Agent = who does the work.
Skill = how that work should be done.
```

Agents can be delegated concrete work. Skills are reusable procedures that
agents use.

Example:

- `stat-problem-formulator` is an agent.
- `statistical-problem-formulation` is the skill it uses.

## Entrypoint

Use:

```text
skills/stat-research-orchestrator/SKILL.md
```

It coordinates:

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

## Agents

| Agent | Role |
|---|---|
| `stat-problem-formulator` | Formalize the statistical problem, target, assumptions, claims, and theory targets. |
| `stat-method-proposer` | Propose methods, baselines, diagnostics, oracle references, and ablations. |
| `stat-theory-analyzer` | Analyze identifiability, bias, variance, consistency, coverage, robustness, or limits. |
| `stat-experiment-designer` | Design and run experiments that test claims and theoretical predictions. |
| `stat-comparison-analyst` | Compare proposed methods against baselines, ablations, and theory. |
| `stat-result-synthesizer` | Write the final report, README, claims, and limitations. |
| `stat-quality-auditor` | Audit the whole formulation-method-theory-evidence chain. |

## Skills

| Skill | Purpose |
|---|---|
| `stat-research-orchestrator` | Full domain workflow. |
| `statistical-problem-formulation` | Formal notation, data model, target, assumptions, claims, criteria. |
| `statistical-method-design` | Methods, baselines, ablations, diagnostics, method-to-claim map. |
| `statistical-theory-analysis` | Theorems, derivations, proof sketches, predictions, limitations. |
| `statistical-experimental-evaluation` | Experiments, metrics, manifest, comparisons, failure accounting. |
| `stat-result-validator` | Quality gates and consistency checks. |

## Required Artifacts

```text
progress/<TOPIC_ID>/step0_problem_formulation.md
progress/<TOPIC_ID>/step1_method_proposal.md
progress/<TOPIC_ID>/step2_theory_analysis.md
progress/<TOPIC_ID>/step3_experimental_evaluation.md
progress/<TOPIC_ID>/step4_comparison.md
progress/<TOPIC_ID>/step5_result_synthesis.md
progress/<TOPIC_ID>/step6_quality_audit.md

experiments/<TOPIC_ID>/config.yaml
experiments/<TOPIC_ID>/src/
experiments/<TOPIC_ID>/results/metrics.json
experiments/<TOPIC_ID>/results/run_manifest.json
experiments/<TOPIC_ID>/results/comparison_summary.md
experiments/<TOPIC_ID>/results/claim_verdicts.json
experiments/<TOPIC_ID>/report/paper.md
experiments/<TOPIC_ID>/README.md
```

Topic-specific artifacts may be added when needed, such as raw interval tables,
decision logs, prediction files, diagnostic tables, ablation outputs, or
simulation task tables.

