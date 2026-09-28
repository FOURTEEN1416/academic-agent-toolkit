# Suite Map

PaperSpine is a single orchestrator skill. Each stage reads its playbook from
`references/*.md`:

| Stage Playbook | Responsibility |
|---|---|
| `references/intake.md` | collect configuration |
| `references/research.md` | index local references, research target scene, and learn examples |
| `references/citation.md` | build citation support candidates |
| `references/semantic-confirmation.md` | confirm the contribution contract first and its aligned motivation second |
| `references/contribution.md` | define the contribution, evidence requirements, and claim boundary |
| `references/rewrite.md` | rewrite an existing draft |
| `references/build.md` | build from a materials folder |
| `references/results-validation.md` | map planned Results units to confirmed contribution promises before prose |
| `references/reviewer-audit.md` | convert structured reviewer findings into a pre-LaTeX objection register |
| `references/humanize.md` | reduce AI detection patterns via tiered stylistic constraints |
| `references/latex.md` | assemble and guard LaTeX |
| `references/translate.md` | produce complete translation_zh/ with row-by-row translation |
| `references/audit.md` | re-check completeness, integrity, semantic gates, reviewer audit, and translation coverage |
| `references/update.md` | manual update commands plus opt-in, throttled launch-time automatic updates across four hosts |
| `references/publication-cycle.md` | shared authority and routing for submission, revision, and transfer |
| `references/publication-cycle-interface.md` | versioned JSON invocation/result contract for main-flow, host, and cross-Agent callers |
| `references/publication-target-profile.md` | official venue rules, five-part narrative preferences, and package requirements |
| `references/submission.md` | immutable target-specific upload bundle |
| `references/respond.md` | atomic, evidence-bound multi-round rebuttal and revision |
| `references/journal-transfer.md` | candidate recommendation, confirmed destination, and full target rebuild |

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
| `references/round2-journal-revision.md` | `humanize.md` | CASPArS "Three R's" corpus-based style calibration + Style Conformity Checklist |
| `references/round3-latex-polish.md` | `latex.md` | template-first Markdown→LaTeX conversion + native-English polishing |
| `references/round4-template-integration.md` | `latex.md` | journal-template integration, compile-and-fix, content-integrity verification |
