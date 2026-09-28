# Contribution-First

This is the keystone of PaperSpine V4. A paper is accepted or rejected on its **contribution** — the one defensible thing it adds to the field — not on how polished its prose is. Motivation explains *why a reader should care*; contribution states *what this paper actually delivers and is willing to be judged on*. The two are not the same, and V4 refuses to let motivation quietly stand in for a contribution.

## The Contribution-First Hard Rule

> **No `confirmed_contribution.md`, no substantive writing. Motivation supports the contribution, not replaces it.**

Concretely:

- `paper_rewriting_output/confirmed_contribution.md` must exist and pass `contribution_check.py` **before** any section drafting, blueprinting, or rewriting begins.
- `confirmed_motivation.md` answers "why does this problem matter?"; `confirmed_contribution.md` answers "what does *this paper* establish that did not exist before, and how strongly can we claim it?" A motivation with no contribution is a literature review; a contribution with no motivation is a result nobody asked for. You need both, and the contribution governs.
- Every later artifact (section blueprints, writing-rationale matrix, the manuscript itself) must trace back to the single Core contribution statement here. If a paragraph does not advance, support, or bound that statement, it does not belong.

WHY this is a hard gate: the most common failure mode in generated papers is fluent text that improves every sentence while never committing to a claim a reviewer can accept or reject. Forcing the contribution to be written, typed, and bounded *first* makes the whole paper answerable to one testable promise.

## The Artifact: `confirmed_contribution.md`

Save at `paper_rewriting_output/confirmed_contribution.md`. It has **four required sections**. Each row exists to force a specific decision; the "WHY" tells you what goes wrong if the cell is vague or empty. Do not leave cells as `TODO`, `TBD`, `...`, or template placeholders — `contribution_check.py` treats those as failures, because an unfilled cell means the decision was never actually made.

```markdown
# Confirmed Contribution

## Core Contribution

| Field | Content |
|---|---|
| Main contribution statement | The single sentence the whole paper defends. One claim, specific, falsifiable. |
| Contribution type | new method / new dataset / new theory / new empirical finding / new system / new analysis-or-benchmark / new application. Pick the dominant one. |
| One-sentence reviewer payoff | If the reviewer remembers one thing, it is this. Phrase as the value to the field, not the activity performed. |

## Why This Contribution Is Needed

| Field | Content |
|---|---|
| Field problem | The broad problem the field cares about. Why the area exists. |
| Specific gap | The precise missing capability/knowledge this paper fills. Not "X is understudied" — name the exact hole. |
| Concrete challenge | What makes the gap hard to close (the technical/empirical obstacle that explains why it is still open). |
| Why prior work leaves it unresolved | Name the closest prior approaches and the specific reason each one does not already solve the gap. |

## How This Paper Responds

| Field | Content |
|---|---|
| Design response | The core idea/mechanism that addresses the gap. The "how", tied directly to the challenge above. |
| Evidence required | What evidence a skeptical reviewer would demand to believe the Core contribution. List it before checking what you have. |
| Evidence available | The evidence you actually have (experiments, proofs, datasets, ablations) that meets the "required" list. |
| Evidence missing | The gap between required and available. If non-empty, the Core contribution must be softened or more work is needed. Honest entry here prevents over-claiming. |

## Claim Boundary

| Field | Content |
|---|---|
| Strong claims allowed | Claims fully backed by Evidence available. State them at full strength. |
| Claims to soften or avoid | Claims the evidence cannot carry. Hedge ("suggests", "in this setting") or cut. |
| Novelty risk | The most likely "this was already done by X" objection, and your honest answer. |
| Significance risk | The most likely "so what / too narrow" objection, and your honest answer. |
```

WHY four sections in this order: a contribution is only real if it is **needed** (section 2), **answered with evidence** (section 3), and **bounded so it does not over-claim** (section 4). Section 1 is the promise; 2-4 are what make the promise survive review. The `Evidence missing` and `Claim boundary` fields are the parts authors skip and reviewers punish — V4 makes them mandatory.

---

## Per-Section Writing Checklists

These fold the Contribution-First logic into each manuscript section. They are checklists, not separate artifacts: every item should be traceable to a field in `confirmed_contribution.md`.

### CHECKLIST — Introduction argument ladder

The Introduction is the contribution's argument, staged as a ladder. Each rung narrows toward the claim; skipping a rung is the most common reason an intro "reads fine but says nothing".

- [ ] **Problem** — establish the field problem (`Why This Contribution Is Needed → Field problem`). Why the area matters.
- [ ] **Progress** — what prior work already achieved. Be fair; this is what makes the gap credible.
- [ ] **Gap** — the specific gap left open (`→ Specific gap`) plus the concrete challenge that keeps it open. This is the pivot of the whole intro.
- [ ] **RQ** — turn the gap into a precise research question or objective the paper will answer.
- [ ] **Contribution promise** — state the Core contribution (`Core Contribution → Main contribution statement`) as the paper's answer to the RQ.
- [ ] **Evidence preview** — name the evidence that will back the promise (`How This Paper Responds → Evidence available`), so the promise is not naked.
- [ ] **Reader payoff** — close on the reviewer payoff (`Core Contribution → One-sentence reviewer payoff`): what the reader gains by accepting the contribution.

WHY a ladder: each rung must be necessary for the next. If the gap does not follow from the progress, or the RQ does not follow from the gap, the contribution will feel unmotivated no matter how good the prose is.

### CHECKLIST — Method credibility

Methods do not just describe; they make the Design response *believable*. Each design choice should answer a "why this and not the obvious alternative?".

- [ ] Every major design choice maps to the `Concrete challenge` it overcomes (not "we used X" but "X because the challenge is Y").
- [ ] Inputs, architecture/derivation, and objective are each justified, not merely stated.
- [ ] Evaluation design (splits, baselines, metrics) is chosen to produce exactly the `Evidence required`, not whatever is convenient.
- [ ] Reproducibility load-bearing details are present (settings, data provenance, hyperparameters) so a reviewer cannot dismiss the result as unverifiable.
- [ ] Nothing in Methods quietly assumes a claim listed under `Claims to soften or avoid`.

### CHECKLIST — Results as validation

Results are not a metric dump; they are the courtroom where the contribution is tested. Each subsection validates one promise.

- [ ] Each Results subsection maps to one item in `Evidence required` and tests one Introduction promise.
- [ ] Each subsection states: question → evidence (figure/metric) → comparison → interpretation → what it does/does not prove.
- [ ] The headline result directly substantiates the `Main contribution statement` at the strength claimed in `Strong claims allowed`.
- [ ] Anything in `Evidence missing` is visibly *not* claimed here. No silent upgrades from "suggests" to "proves".

Pointer sentence to write before drafting each Results subsection:

```text
This subsection tests the contribution promise that [promise] by showing [evidence], which supports [claim at allowed strength] but does not claim more than [boundary].
```

### CHECKLIST — Discussion insight and mechanism

Discussion converts results into *understanding*. A weak discussion restates numbers; a strong one explains the mechanism and places the contribution.

- [ ] Restate the answer (the contribution), not the procedure.
- [ ] Explain the **mechanism**: *why* the design response produced the result — the insight, not just the outcome.
- [ ] Attribute the effect: what each key design choice contributed (ties back to Method credibility).
- [ ] Position against prior work named in `Why prior work leaves it unresolved` — show the gap is now closed.
- [ ] State limitations from `Evidence missing` / `Claim boundary` without dissolving the central claim.
- [ ] Close on `Significance risk` answered: the field-level implication, not a generic "this is useful".

### CHECKLIST — Abstract contribution contract (5 steps)

The abstract is a contract: it promises exactly the contribution the paper delivers, in order. Five sentences, five jobs.

1. **Problem + stakes** — the field problem and why it matters (`Field problem`).
2. **Gap** — the specific unresolved gap (`Specific gap` + why prior work falls short).
3. **Contribution** — the Core contribution as the response (`Main contribution statement` + `Design response`).
4. **Evidence** — the strongest supporting result (`Evidence available`), stated at allowed strength.
5. **Payoff** — the reviewer payoff / field implication (`One-sentence reviewer payoff`), bounded so it does not over-claim.

WHY a contract: if the abstract promises more than `Strong claims allowed`, the paper is already over-claiming on line one. The abstract must be checkable against `confirmed_contribution.md` field by field.

---

## How To Use It

1. Draft `confirmed_contribution.md` filling all four sections; resolve `Evidence missing` honestly before locking the Core statement.
2. Run `python src/scripts/contribution_check.py paper_rewriting_output` until it passes (exit 0).
3. Only then proceed to motivation thread, section blueprints, and writing — each tracing back to the Core contribution.
4. Re-run the check whenever the claim or evidence changes; a shifted contribution invalidates downstream sections.
