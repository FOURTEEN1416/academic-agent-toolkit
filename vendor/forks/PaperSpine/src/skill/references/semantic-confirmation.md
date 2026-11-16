# Semantic Confirmation

This is the canonical writing-before-writing gate. It converts research into a
user-approved semantic contract with two ordered parts:

1. **Confirmed contribution — governing contract.** What the paper adds, which
   gap and challenge make it necessary, what evidence validates it, and what
   claim boundary applies.
2. **Confirmed motivation — supporting rationale.** Why that contribution
   matters to the field and target venue. Motivation may sharpen the framing;
   it may not replace or silently enlarge the contribution.

Use the existing confirmed contribution and motivation before making dependent writing choices. Resolve a genuinely missing or changed decision through the current public task, but do not require two historical files or a legacy checker to inspect, plan, review or safely continue the paper.

## Inputs

- `sota_gap_map.md`
- `research_dossier.md`
- `exemplar_learning_dossier.md`
- `contribution_options_after_research.md`
- `motivation_options_after_research.md`
- user evidence indexed by the research stage

## Research-Generated Options

`contribution_options_after_research.md` must present 3-5 genuinely different
contribution contracts, not cosmetic phrasings:

| Option | Main Contribution | Contribution Type | Specific Gap and Challenge | Evidence Required | Evidence Available | Evidence Missing | Claim Boundary | Reviewer Payoff | Main Risk |
|---|---|---|---|---|---|---|---|---|---|

Each motivation option must name the contribution option it supports. An option
that requires evidence the user does not have must either weaken its claim or
state the missing work explicitly.

## Decision Authority Gate

In `guided` mode, stop and ask the user to choose, revise, combine, or replace
the proposed contracts. Confirmation is ordered:

1. Lock the contribution and its evidence/claim boundary.
2. Lock a motivation that explains the need and significance of that exact
   contribution.

The user may confirm both in one response, but PaperSpine must record them as
two separate artifacts so later checks can distinguish "what is established"
from "why it matters".

In `delegated_local_test`, the current host may select an evidence-supported
contribution and motivation without another user question only when the exact
task/material/local-scope grant contains both `contribution_selection` and
`motivation_selection`. The choices must stay inside the evidence/claim
boundary and each must produce its own hash-bound `delegated-decision.` receipt.
The delegated-decision principal replaces author identity for this operation;
never invent author facts. Any missing/expired/drifted grant returns to the
guided typed issue before revision mutation.

After valid guided confirmation or valid delegated receipts:

- create `confirmed_contribution.md` using `references/contribution.md`;
- create `confirmed_motivation.md` using
  `references/motivation-thread-writing.md`;
- ensure every prioritized motivation claim fits within the contribution's
  `Strong claims allowed` and every avoided claim is consistent with its claim
  boundary.

## Gate

```bash
python scripts/contribution_check.py paper_rewriting_output --markdown --write
python scripts/progress_check.py paper_rewriting_output --gate semantic_confirmation
```

`motivation_confirmation` remains a compatibility alias for the second command,
but new documentation and automation must use `semantic_confirmation`.

If a check exposes a real claim, evidence or user-choice gap, resolve that gap before making dependent assertions. Continue independent, safe work in the same task; a missing legacy artifact or command failure alone does not prohibit all planning or prose.
