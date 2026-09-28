# Reviewer-Aware Audit

`reviewer_audit.md` is the differentiator. Most rewriting pipelines optimize the
manuscript for the *author's* intent; this step re-reads the same manuscript
through the eyes of the **people who decide its fate** — the reviewers and the
handling editor. The goal is not to add more prose, but to surface, *before*
submission, the exact objections a reviewer will raise and to attach a concrete
preemptive fix to each one.

This playbook produces ONE file with THREE tables:

1. **Reviewer Value Map** — what each evaluation criterion buys you, and where
   our manuscript is currently weak on it.
2. **Reviewer Objection Register** — the concrete attacks a reviewer is likely
   to make, with a preemptive fix and a tracked status for each.
3. **Editorial Fit Map** — the editor-facing view: venue fit, desk-reject risk,
   and why an editor would send this out for review at all.

## Why this step exists

A manuscript is accepted by *people applying criteria*, not by a quality score.
The same paragraph that reads as "thorough" to the author reads as "padding" to
a reviewer who wants the contribution in the first column. Writing the
objections down turns silent rejection risk into an explicit checklist you can
close before a reviewer ever sees the paper. Each row below says **why** it
matters so the audit teaches, not just grades.

## How to populate the Objection Register

Do **not** invent objections from scratch. Reuse the existing three-reviewer
`structured_review` machinery — the same Methods/Reproducibility, Contribution,
and Clarity personas that drive `structured_review.py`. Run (or read the output
of) those three agents, then fold their CRITICAL/MAJOR findings into the
Objection Register. The mapping is direct:

- **Methods & Reproducibility Reviewer** → objections about technical soundness,
  evidence sufficiency, reproducibility, missing ablations/baselines.
- **Contribution Reviewer** → objections about novelty, significance,
  differentiation from prior work, citation credibility.
- **Clarity Reviewer** → objections about structure, unclear claims,
  figure/table legibility, venue-convention violations.

This keeps the audit grounded in the project's existing review agents instead of
producing a second, unanchored opinion. Each register row should trace back to a
specific reviewer finding so the editor synthesis stays consistent.

## Output location

Write:

```text
paper_rewriting_output/reviewer_audit.md
```

It is validated by `reviewer_audit_check.py`, which requires all three sections
present and non-empty: the value map must carry the six criterion rows, the
objection register must have at least one row with a Severity and a Preemptive
fix, and the editorial fit block must be present.

---

## Template

Copy the block below into `paper_rewriting_output/reviewer_audit.md` and fill
every cell. Keep the teaching column (`What reviewers/editors want` /
`What the reviewer may say`) honest — it is the part that makes the fix obvious.

### 1. Reviewer Value Map

Why each row: a reviewer scores the paper against these six axes. For every axis,
name what they actually want, point at the evidence we already have, state where
we are thin, and commit to one revision action. The six rows are fixed —
Novelty, Significance, Technical soundness, Evidence sufficiency, Clarity, and
Venue fit — because they are the criteria nearly every venue's review form asks
about.

| Reviewer criterion | What reviewers/editors want | Our manuscript evidence | Current weakness | Revision action |
|---|---|---|---|---|
| Novelty | A clearly stated, defensible delta versus the closest prior work — not "first to combine X and Y" but "X fails on Z; we fix Z". | Sec. 1 contribution bullets; Table 1 vs. baselines. | Delta is implied, not stated in one sentence the reviewer can quote. | Add a single "Unlike [closest work], we …" sentence to the intro and the abstract. |
| Significance | Evidence the problem matters and the gain is non-trivial to someone beyond the authors. | Motivating application in Sec. 1; effect size in Sec. 4. | Impact is asserted, not quantified against a real cost/benefit. | Quantify the stakes (who is affected, by how much) in the intro's second paragraph. |
| Technical soundness | Methods that are correct, justified, and free of unstated assumptions a reviewer can poke. | Method derivation Sec. 3; assumptions listed in 3.1. | One assumption (e.g. i.i.d. data) is used but never defended. | State and justify each assumption; add a sentence on when it fails. |
| Evidence sufficiency | Enough experiments/ablations to rule out the obvious "but did you try…" rebuttals. | Main results Table 2; ablation Table 3. | Missing the baseline/ablation the Methods reviewer will ask for first. | Add the missing baseline or explicitly scope it out with a reason. |
| Clarity | A paper a tired reviewer can follow once, top to bottom, without re-reading. | Section flow; figures with self-contained captions. | A key claim is split across two sections, forcing back-references. | Consolidate the claim and its support into one place; tighten the figure captions. |
| Venue fit | Topic, framing, and length that match what this venue publishes. | Target-venue analysis; reference profile. | Framing leans toward a different community than the target venue. | Reframe the intro/related work toward the target venue's vocabulary and canon. |

### 2. Reviewer Objection Register

Why each row: this is the adversarial core. Each row is a concrete attack a
reviewer is likely to make, written in *their* voice, plus the preemptive fix and
a status you can close before submission. Severity uses the same scale as
`structured_review` (CRITICAL / MAJOR / MINOR). Populate these rows from the
three reviewer agents above — every row should trace to a Methods, Contribution,
or Clarity finding.

| Likely objection | Where triggered | Severity | What the reviewer may say | Preemptive fix | Status |
|---|---|---|---|---|---|
| Contribution overlaps existing work | Sec. 1 / Related Work | CRITICAL | "This is incremental over [X]; the novel part is unclear." | Add explicit delta sentence + a comparison row in Table 1. | OPEN |
| Missing baseline / ablation | Sec. 4 Experiments | MAJOR | "Why no comparison against [standard baseline]?" | Add the baseline, or scope it out with a one-line justification. | OPEN |
| Unjustified assumption | Sec. 3 Method | MAJOR | "The i.i.d. assumption is unrealistic for this data." | State the assumption, justify it, note failure modes. | OPEN |
| Claim stronger than evidence | Abstract / Sec. 5 | MAJOR | "The abstract claims generality the experiments don't show." | Soften the claim to match the evidence, or add the evidence. | OPEN |
| Hard-to-read figure/table | Figures 2–3 | MINOR | "Figure 2 is unreadable; axes/units missing." | Re-export at higher DPI; add axis labels and a self-contained caption. | OPEN |

### 3. Editorial Fit Map

Why this block: the editor sees the paper *before* the reviewers and can
desk-reject it. This block answers the editor's three questions — does it fit the
venue, is it worth a reviewer's time, and is there an obvious reason to bounce it
now. A short bulleted block is fine; the point is to make desk-reject risks
explicit.

- **Venue fit:** State the target venue and one sentence on why this paper
  belongs there (scope, audience, typical methods). Flag any mismatch in topic,
  length, or formatting against the venue's guidelines.
- **Editor-facing value:** In one or two sentences, the reason an editor would
  send this out for review — the contribution an editor can defend to the board.
- **Desk-reject risks:** List the concrete things that trigger a desk reject —
  out-of-scope framing, over-length, missing required sections (ethics, data
  availability), formatting violations, or undisclosed overlap with prior work.
  For each, note whether it is resolved or still OPEN.
