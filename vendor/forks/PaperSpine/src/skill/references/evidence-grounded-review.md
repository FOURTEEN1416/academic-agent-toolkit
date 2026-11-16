# Evidence-Grounded Review Protocol

Use this playbook for the integrity-audit review. It turns reviewer prose into
traceable findings without turning PaperSpine into a fixed multi-agent product.

## Controlling rule

Every actionable review finding must carry all four links below:

1. a precise manuscript locator (page/line/paragraph/figure/table/equation or
   supplement/appendix coordinate) plus a short manuscript quote, or an
   exhaustive absence-scan receipt for a claim that required content is absent;
2. the reviewer/persona that raised it and that review pass's receipt;
3. the read/search/annotation tool receipts used to reach it, with measured
   tokens and wall time when the host exposes them;
4. a concrete recommendation, confidence, severity, and disposition.

An unlocated opinion is an advisory note, not a scientific/editorial blocker.
Packaging, compilation, or other technical PASS states never compensate for a
grounded unresolved scientific blocker.

The machine contract is
`references/contracts/evidence-review.schema.json`; semantic enforcement is
implemented by `scripts/evidence_grounded_review.py`.

## Conservative persona selection

Read `reviewer-persona-registry.json`. It is a replaceable registry, not a list
of roles that always run.

- `balanced`: one Editor reads the manuscript and rendered paper. Activate an
  additional specialist only for a concrete risk.
- `strict`: run Methods, Contribution, and Clarity independently, then Editor.
- `open_literature`: activate Literature. Activate Historian only for an actual
  history/trajectory question and Baseline Scout only for a closest-baseline,
  dataset, or evaluation-gap question. Do not add any of them in a declared
  closed corpus.
- Activate Fact Checker for suspicious first/best/general/causal claims.
- Activate Critic only when manuscript, literature, and factual lanes must be
  joined. Activate Judge only for a material conflict between independent
  reviews or models.

Generate the review plan and explicit cost ceiling:

```bash
python scripts/evidence_grounded_review.py plan paper_rewriting_output \
  --manuscript paper_rewriting_output/final_paper/main.tex
```

The budget is a ceiling, not a quota. Stop when the coverage question is
answered; do not spend tokens merely to hit a minimum number of agents, searches,
or annotations. Record actual usage, not estimates, in each tool receipt. When
the host exposes no usage, write `telemetry_status=unavailable`; never encode an
unknown quantity as a measured zero.

## Evidence lanes and search states

Keep three lanes distinct:

- paper-original evidence: what the manuscript actually says or shows;
- project evidence: data/code/ledger support owned by the paper;
- external literature: retrieved papers used for novelty, baseline, history, or
  factual positioning.

For literature tools, use the explicit states `not_started`, `partial`,
`retrieved`/`verified`, `no_hit`, and `provider_failure`. A provider failure is
degraded coverage. A zero-result query is only a search receipt, not proof that
no prior work exists. Novelty, positioning, baseline, or historical findings
cannot be CRITICAL/MAJOR without retrieved external evidence.

Use problem, method, and temporal query rounds when open literature is allowed.
Persist provider, query, date/time, result count, identifiers/URLs, and failure
details. The current PaperSpine citation/audit rules remain authoritative for
bibliographic truth.

## Synthesis and clustering

Cluster duplicate findings for reading efficiency, but retain every source
finding ID and reviewer receipt. Never delete a unique, grounded high-severity
finding because most reviewers did not mention it. Consensus may increase
priority; disagreement must remain visible to the Editor or conditional Judge.

`PASS` is invalid while any CRITICAL/MAJOR finding remains `open` or
`needs_author`. `BLOCKED` must name its blocker finding IDs.

Validate before reviewer-audit synthesis:

```bash
python scripts/evidence_grounded_review.py validate \
  paper_rewriting_output/evidence_review.json \
  --manuscript paper_rewriting_output/final_paper/main.tex \
  --markdown --write
```

In a requested strict review, preserve traceable findings and check their structure and evidence. Safe local rendering may proceed so reviewers can inspect the actual files. Do not require historical evidence_review JSON or checker PASS before the current host can assemble and examine the manuscript.

## Human-review calibration

When genuine human reviews are available, compare them with the AI review:

```bash
python scripts/evidence_grounded_review.py calibrate ai_review.json human_review.json \
  --output calibration_delta.json
```

Prefer explicit human-to-AI finding links. The deterministic lexical fallback
is conservative and marks every inferred alignment as requiring human
confirmation; it must not be described as a validated semantic match.

Calibration reports coverage, misses, false alarms, severity-weighted recall,
persona noise, selection failures, and prompt failures. It never mutates the
persona registry. Aggregate recurring suggestions across papers with
`aggregate --min-support 2`, then require held-out evaluation and explicit
adoption (for PaperSpine rules, use SkillOpt-Sleep).

## Human authority

AI reviewer output is author-side decision support. It cannot impersonate an
assigned peer reviewer, replace a human editorial decision, or authorize an
external submission action.
