# Review Policy and Agent Autonomy

PaperSpine has two review policies. The policy changes process depth, not the
truth standard.

The default policy is editorially ambitious and procedurally light: the Agent
is trusted to design and revise the manuscript, while hard barriers are kept for
truth and deliverability. A longer audit trail is not evidence of a better
paper.

## Balanced (default)

Use for ordinary research writing, evidence-bounded rewrites, reports, early and
middle drafts, and most user-directed production work.

- Let the Agent choose the manuscript architecture, paragraph moves, emphasis,
  and revision order from the confirmed contribution and evidence.
- Require a compact section blueprint, primary-claim evidence links, one
  integrated review, a real PDF visual inspection, and usable final artifacts.
- Do not require a paragraph-by-paragraph rationale matrix, three reviewer
  personas, separate objection registers, or repeated receipts unless they help
  resolve an actual risk.
- CRITICAL scientific defects block. MAJOR findings block only when they affect
  a primary claim, figure/text identity, citation truth, or deliverable usability.
  MINOR/style findings are advisory.
- A gate may report `PASS_WITH_ADVISORIES`; this does not mean the advice must be
  converted into more forms before writing can continue.
- Judge manuscript completeness through one free-form editor synthesis, not a
  fixed scorecard. The synthesis must read the actual paper and may recommend
  any structure that fits the venue.
- `tier` changes research/process breadth only. It must not shorten the promised
  manuscript, remove an earned ending, or turn Results/Discussion into notes.

## Strict

Use when the user explicitly requests strict audit, submission certification,
regulatory/compliance review, or a high-stakes final package. Strict mode adds
the full rationale matrix, independent reviewer outputs/receipts,
`reviewer_audit.md`, and corresponding checks.

Strict mode still must not reward bureaucracy. An artifact passes because it
captures a useful decision or verifiable fact, not because it is long.

## Always Hard

Both policies block fabricated or unsupported primary facts, fake references,
broken citation linkage, unresolved method/figure identity conflicts, altered
user data without authorization, missing required author input at delivery, and
unreadable/nonportable final artifacts.

Missing a preferred heading, exceeding a default section count, or departing
from an example outline is not automatically a hard failure. Ask whether the
reader-facing intellectual job is complete and whether the venue permits the
chosen form.

## Policy Resolution

`paper_spine_config.json` may set `review_policy` to `balanced` or `strict`.
Missing/unknown values resolve to `balanced`. Do not ask an extra intake question
unless the user's requested outcome genuinely depends on strict certification.
