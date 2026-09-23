# Statistical Research Skills

Domain skills used by the statistical research agent.

## Skill Index

| Skill | Description |
|---|---|
| `stat-research-orchestrator` | Coordinates the full research workflow from formulation to audit. |
| `statistical-problem-formulation` | Formalizes observed data, data model, target, assumptions, claims, criteria, and theory targets. |
| `statistical-method-design` | Designs methods, baselines, diagnostics, variants, and ablations. |
| `statistical-theory-analysis` | Develops theoretical analysis, proof sketches, derivations, predictions, and limitations. |
| `statistical-experimental-evaluation` | Designs and runs experiments that test claims and theory. |
| `stat-result-validator` | Audits formulation, method, theory, evidence, comparison, and final claims. |

## Domain Workflow

```text
stat-research-orchestrator
  -> statistical-problem-formulation
  -> statistical-method-design
  -> statistical-theory-analysis
  -> statistical-experimental-evaluation
  -> stat-result-validator
```

## Notes

These are domain skills, not standalone workers. Agents use them to perform
specialized statistical research tasks.

