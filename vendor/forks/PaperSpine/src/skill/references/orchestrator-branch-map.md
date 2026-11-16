# Orchestrator Stage Map

PaperSpine is one contribution-governed host workflow. Read the relevant scientific methods before producing downstream work and reuse valid inputs from the same task. Proceed when the necessary evidence and authorized decisions are available; historical stage files and gate PASS receipts are not prerequisites for safe current-host drafting, rendering or correction.

## Current Host Work and Review

Develop the argument from authorized evidence and the saved contribution and
motivation choices. Apply the relevant research, exemplar-learning, writing and
format methods to an actual manuscript, then compile/export and inspect its
rendered pages. Give the independent reviewer that manuscript and its current
rendering so scientific, editorial and layout findings concern the real paper.
Fix or narrow unsupported claims and repair substantive writing or rendering
problems; regenerate affected outputs and recheck the changes. Reuse valid,
unchanged work. A clean first review does not require an invented revision.

The map below preserves the old Runner's stage keys and artifact contracts for
historical compatibility. Its numbered review-before-LaTeX order, named-file
gates and author-voice confirmation receipts do not prescribe the current host's
work order. Use the scientific methods they point to; a legacy gate is applicable
only when explicitly running that matching legacy contract.

## Legacy Runner 13-Stage Contract (Historical Compatibility)

1. **Intake** — write `paper_spine_config.json` and
   `paper_spine_config.md`. Gate: `intake`.
2. **Research** — index local sources, learn the target scene/examples/SOTA,
   and produce both `contribution_options_after_research.md` and
   `motivation_options_after_research.md`. Gate: `research`.
3. **Citation** — build and verify `citation_support_bank.md`. Gate: `citation`.
4. **Semantic confirmation** — the user confirms the contribution contract
   first and an aligned motivation second. Required artifacts:
   `confirmed_contribution.md`, `confirmed_motivation.md`. Gate:
   `semantic_confirmation`; `motivation_confirmation` is a compatibility alias.
5. **Author-voice preparation** — when configured, load
   `references/humanize.md`, validate the authorized author corpus, and freeze
   protected terms. Do not rewrite prose at this stage.
6. **Planning and drafting** — run `rewrite.md` or `build.md`. Planning creates
   `section_blueprints.md` and `results_validation.md` for journal,
   conference, or competition scenes, plus a linked S/C/N/M/O/R
   `scientific_evidence_ledger.json`. Strict mode additionally requires a
   contribution-linked `writing_rationale_matrix.md`. Gates: `planning`, then
   `drafting`. When existing data/figures/code/sources have multiple versions,
   the build branch records semantic identity and uses the deterministic
   newest-eligible asset receipt before evidence mapping.
7. **Authorial Voice Restoration** — after claims and evidence are frozen,
   perform the minimum necessary revision, or record a clean-text no-op. Then
   require semantic-invariant checks, an independent audit, and hash-bound
   author confirmation. Gate: `author_voice_restoration` when enabled.
8. **Structured review and integrity** — balanced mode performs one integrated,
   manuscript-grounded review; strict mode uses three independent core
   reviewers, `evidence_review.json` plus tool receipts, and
   `reviewer_audit.md`. Trigger optional retrieval/fact/judge lanes only when
   needed. Resolve real blockers, then run integrity and artifact audits. Gate:
   `integrity_audit`.
9. **LaTeX / PDF / Word** — assemble and guard deliverables, scrub the
   publication surface, then render and inspect every page and figure. Gates:
   `latex` and `word` unless Word is explicitly disabled.
10. **Submission package** — conditional. Build a current target profile,
   complete official nine-area rule coverage, run the writing precheck, then
   build a target-specific package plan, immutable upload bundle, manifest, and
   archive checksum. Assemble re-runs the rules and records final receipts.
   Gate: `submission` plus READY publication-cycle bundle authority.
   Main-flow and host callers use the versioned `publication_cycle.py
   describe/invoke` result signals; canonical-paper completion alone does not
   advance this stage.
11. **Translation package** — conditional. Gate: `translation`.
12. **Review response** — conditional atomic response/revision workflow with
   author intent, evidence, change locations, multi-round lineage, and readiness
   revalidation. Rejected papers may branch into a confirmed journal-transfer
   plan, destination rebuild, and new bundle. `READY_TO_REBUILD` routes back to
   destination planning/drafting/LaTeX/audit and is not a bundle-ready state.
13. **Final review of affected outputs** — check the current manuscript's evidence, citations, figures, rendered files and requested package. Reuse valid unchanged checks; repeat those invalidated by a change or unresolved concern. Report local scientific quality, submission readiness and external authorization separately, without requiring historical telemetry or all five legacy readiness dimensions.

After Stage 13, an **optional Open Release Beta** branch may recommend and
prepare external repositories for delivered artifacts. It is not part of paper
completion and cannot start an external action until a separate, hash-bound user
confirmation creates an exact host ticket. Guided medical/institutional targets
remain manual or review-bound even when their local preparation is complete.

## Legacy Stage Keys to Scientific Playbooks

Status labels in this lookup belong to the legacy Runner, not a new host queue.

| Stage Key | Status | Reference Playbook |
|---|---|---|
| `intake` | PENDING | `references/intake.md` |
| `research` | PENDING | `references/research.md` |
| `citation` | PENDING | `references/citation.md` |
| `semantic_confirmation` | BLOCKED/PENDING | `references/semantic-confirmation.md` |
| `planning` | PENDING | `references/rewrite.md` or `references/build.md`; also `references/results-validation.md` for evidence-bearing scenes |
| `build_from_materials` | PENDING | `references/build.md` |
| `rewrite_existing` | PENDING | `references/rewrite.md` |
| `drafting` | PENDING | `references/rewrite.md` or `references/build.md` |
| `author_voice_restoration` | OPTIONAL/PENDING/BLOCKED | `references/humanize.md`, `references/humanize-calibration.md` |
| `integrity_audit` | PENDING | `references/review-policy.md`, then `references/audit.md` |
| `latex` | PENDING | `references/latex.md` |
| `word` | PENDING | `references/latex.md` |
| `translation` | PENDING | `references/translate.md` |
| `submission` | PENDING | `references/publication-cycle.md`, `references/publication-target-profile.md`, `references/submission.md` |
| `revision` | PENDING | `references/publication-cycle.md`, `references/respond.md` |
| `transfer` | PENDING | `references/publication-cycle.md`, `references/journal-transfer.md` |
| `open_release` | OPTIONAL/BLOCKED/PENDING | `references/open-release.md`, `references/open-release-interface.md` |
| `final_audit` | PENDING | `references/audit.md` |

## Ownership And Return Routes

- Weak or unconfirmed contribution/motivation → semantic confirmation.
- Results unit with no contribution promise/evidence/boundary → planning.
- Broken S/C/N/M/O/R link or unresolved final verification state → planning or
  the owning analysis step.
- Unsupported primary claim → planning/drafting; a rationale matrix is checked
  only when strict mode or the user requires it.
- Unresolved integrated-review blocker → drafting; unlocated review opinion →
  evidence-grounded review; literature-provider failure presented as no-hit →
  research/retrieval receipt repair; strict-mode evidence-contract or objection
  register issues → structured review/reviewer audit.
- Logic-transfer or evidence-integrity blocker → owning research/planning/drafting stage.
- Broken labels/citations or missing Word/PDF → LaTeX stage.
- Page crop, blank page, or figure/legend/text conflict → LaTeX/visual stage;
  re-render after every change.
- Missing authorship/declaration state → metadata owner; do not fabricate it.
- Stale or unsupported target requirement → target-profile research; official
  author guidance governs compliance and published papers govern narrative preference.
- Missing author-only package fact or destination confirmation → publication
  cycle owner; report the precise submission/transfer limitation, reuse existing
  authorization, and keep the completed local manuscript available. Obtain only
  genuinely missing author facts or a new destination decision from the user.
- Rebuttal issue without source quote, confirmed intent, evidence, or locatable
  change → revision owner; never hide it in a summary or invent an experiment.
- New target after rejection → transfer owner; rebuild format, five-part
  narrative, and delivery package from the canonical paper.
- Missing platform login/computer control/role/eligibility → Open Release host
  probe or user/institution owner; return a structured recovery path and keep
  full one-click unavailable.
- Human/medical data without sensitivity classification, PHI removal, consent,
  ethics, DUA, or institutional authority → Open Release compliance owner; do
  not route it to a public generalist repository.
- Final audit failure → the earliest owning upstream stage; never patch only the
  final deliverable.

## Legacy Runner Gate Invocation

When executing the matching historical Runner contract, its gate command is:

```bash
python scripts/progress_check.py paper_rewriting_output --gate <stage_name>
```

For current host work, do not invent missing evidence or defer a scientific
validity problem behind a placeholder. Repair the actual problem at its source,
then verify the affected manuscript and exports. A final review reuses valid
checks and repeats those invalidated by changes or unresolved findings; it does
not manufacture missing legacy files or restart completed research.
