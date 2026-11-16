# Suite Map

PaperSpine is a single orchestrator skill. Each stage reads its playbook from
`references/*.md`:

The cross-stage completion path is `references/paper-spine-production-protocol.md`; it binds the stage playbooks to one current task and one semantic manuscript.

This is a method lookup, not a mandatory stage order. In the current host, use
the relevant methods to produce a real manuscript and its rendered pages before
independent review. Apply necessary scientific, editorial and rendering fixes,
regenerate affected outputs and recheck them; reuse valid unchanged work. The
old Runner's review-before-LaTeX order and named-file gates are historical
compatibility contracts, described in `orchestrator-branch-map.md`.

| Stage Playbook | Responsibility |
|---|---|
| `references/intake.md` | collect configuration |
| `references/research.md` | index local references, research target scene, and learn examples |
| `references/citation.md` | build citation support candidates |
| `references/semantic-confirmation.md` | confirm the contribution contract first and its aligned motivation second |
| `references/contribution.md` | define the contribution, evidence requirements, and claim boundary |
| `references/rewrite.md` | rewrite an existing draft |
| `references/build.md` | build from a materials folder |
| `references/asset-selection.md` | choose the newest identity-matched, project-local existing asset with a deterministic receipt |
| `references/results-validation.md` | map planned Results units to confirmed contribution promises before prose |
| `references/evidence-grounded-review.md` | select the minimum reviewer/persona set, bind every finding to manuscript/tool evidence, distinguish retrieval states, and calibrate AI findings against genuine human review |
| `references/reviewer-persona-registry.json` | replaceable, trigger-based reviewer persona registry; never self-mutates |
| `references/upstream-review-protocols.md` | inspected upstream commits/licenses and the clean-room protocol absorption matrix |
| `references/reviewer-audit.md` | review the actual manuscript and rendering, ground real objections, and verify affected work after necessary revision; an objection register is an optional record |
| `references/humanize.md` | restore the authorized author's scholarly voice behind semantic-invariant and no-op gates; legacy `humanize` trigger retained |
| `references/latex.md` | apply the applicable format, compile/export and inspect actual pages for review; regenerate affected outputs after revisions |
| `references/translate.md` | produce complete translation_zh/ with row-by-row translation |
| `references/audit.md` | recheck actual evidence, citations, reader-facing manuscript, rendering and requested delivery; preserve valid prior checks and report submission limitations separately |
| `references/update.md` | manual update commands plus opt-in, throttled launch-time automatic updates across four hosts |
| `references/publication-cycle.md` | shared authority and routing for submission, revision, and transfer |
| `references/publication-cycle-interface.md` | versioned JSON invocation/result contract for main-flow, host, and cross-Agent callers |
| `references/publication-target-profile.md` | official venue rules, nine-area hard-rule coverage, five-part narrative preferences, and package requirements |
| `references/submission.md` | immutable target-specific upload bundle |
| `references/respond.md` | atomic, evidence-bound multi-round rebuttal and revision |
| `references/journal-transfer.md` | candidate recommendation, confirmed destination, and full target rebuild |
| `references/open-release.md` | post-delivery platform recommendation, permission/compliance preflight, final authorization, and per-platform receipts |
| `references/open-release-interface.md` | Beta JSON contract for checkbox UI, host capability probes, exact-scope tickets, and execution receipt recording |
| `references/adaptive-shadow.md` | opt-in domain-neutral runtime receipts, closed obligation IR, one-surface audit, and immutable shadow revisions; never grants whole-paper READY |

> Historical worker skills (`paper-spine-ui`, `paper-spine-intake`, etc.) were
> removed in architecture convergence Stage 2b.  All stage logic now lives in
> `references/*.md` playbooks.

## Supplementary Deep-Revision Methods

These are detailed, optional sub-methods invoked from a stage playbook above, not
separate stages. Use them when the inputs they need (e.g. a deep-read journal
corpus) are available:

| Method | Invoked from | What it adds |
|---|---|---|
| `references/round1-literature-revision.md` | `rewrite.md` | motivation-thread extraction, move-guided section rewrite, numerical + cross-section audit |
| `references/round2-journal-revision.md` | current `draft` and `review` methods, with the saved workflow | CASPArS "Three R's" corpus-based style calibration and applicable style-conformity checks; use its scientific methods without requiring a fixed four-pass sequence |
| `references/round3-latex-polish.md` | `latex.md` | template-first Markdown→LaTeX conversion + native-English polishing |
| `references/round4-template-integration.md` | `latex.md` | journal-template integration, compile-and-fix, content-integrity verification |
