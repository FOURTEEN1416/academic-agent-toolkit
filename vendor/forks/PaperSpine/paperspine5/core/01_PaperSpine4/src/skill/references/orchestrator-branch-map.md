# Orchestrator Stage Map

PaperSpine is one contribution-governed orchestrator. Stage artifacts are
upstream contracts, not paperwork created after prose. A downstream stage may
start only after its owning gate passes.

## Canonical 12-Stage Order

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
5. **Humanize policy** — when configured, load `references/humanize.md` as a
   cross-cutting writing constraint. It does not override semantic contracts.
6. **Planning and drafting** — run `rewrite.md` or `build.md`. Planning creates
   `section_blueprints.md` and `results_validation.md` for journal,
   conference, or competition scenes, plus a linked S/C/N/M/O/R
   `scientific_evidence_ledger.json`. Strict mode additionally requires a
   contribution-linked `writing_rationale_matrix.md`. Gates: `planning`, then
   `drafting`.
7. **Structured review and integrity** — balanced mode performs one integrated
   review; strict mode uses three independent reviewers and
   `reviewer_audit.md`. Resolve real blockers, then run integrity and artifact
   audits. Gate: `integrity_audit`.
8. **LaTeX / PDF / Word** — assemble and guard deliverables, scrub the
   publication surface, then render and inspect every page and figure. Gates:
   `latex` and `word` unless Word is explicitly disabled.
9. **Submission package** — conditional. Build a current target profile,
   target-specific package plan, immutable upload bundle, manifest, and archive
   checksum. Gate: `submission` plus READY publication-cycle bundle authority.
   Main-flow and host callers use the versioned `publication_cycle.py
   describe/invoke` result signals; canonical-paper completion alone does not
   advance this stage.
10. **Translation package** — conditional. Gate: `translation`.
11. **Review response** — conditional atomic response/revision workflow with
   author intent, evidence, change locations, multi-round lineage, and readiness
   revalidation. Rejected papers may branch into a confirmed journal-transfer
   plan, destination rebuild, and new bundle. `READY_TO_REBUILD` routes back to
   destination planning/drafting/LaTeX/audit and is not a bundle-ready state.
12. **Final audit** — re-run all semantic, evidence, reviewer, integrity,
   citation, visual, metadata, publication-surface, telemetry, and delivery
   checks. Gate: `final_audit`; all five readiness dimensions must pass.

## Stage To Playbook Reference

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
| `integrity_audit` | PENDING | `references/review-policy.md`, then `references/audit.md` |
| `latex` | PENDING | `references/latex.md` |
| `word` | PENDING | `references/latex.md` |
| `translation` | PENDING | `references/translate.md` |
| `submission` | PENDING | `references/publication-cycle.md`, `references/publication-target-profile.md`, `references/submission.md` |
| `revision` | PENDING | `references/publication-cycle.md`, `references/respond.md` |
| `transfer` | PENDING | `references/publication-cycle.md`, `references/journal-transfer.md` |
| `final_audit` | PENDING | `references/audit.md` |

## Ownership And Return Routes

- Weak or unconfirmed contribution/motivation → semantic confirmation.
- Results unit with no contribution promise/evidence/boundary → planning.
- Broken S/C/N/M/O/R link or unresolved final verification state → planning or
  the owning analysis step.
- Unsupported primary claim → planning/drafting; a rationale matrix is checked
  only when strict mode or the user requires it.
- Unresolved integrated-review blocker → drafting; strict-mode reviewer
  objection register issues → structured review/reviewer audit.
- Logic-transfer or evidence-integrity blocker → owning research/planning/drafting stage.
- Broken labels/citations or missing Word/PDF → LaTeX stage.
- Page crop, blank page, or figure/legend/text conflict → LaTeX/visual stage;
  re-render after every change.
- Missing authorship/declaration state → metadata owner; do not fabricate it.
- Stale or unsupported target requirement → target-profile research; official
  author guidance governs compliance and published papers govern narrative preference.
- Missing author-only package fact or destination confirmation → publication
  cycle owner; keep the bundle/transfer BLOCKED and ask the user.
- Rebuttal issue without source quote, confirmed intent, evidence, or locatable
  change → revision owner; never hide it in a summary or invent an experiment.
- New target after rejection → transfer owner; rebuild format, five-part
  narrative, and delivery package from the canonical paper.
- Final audit failure → the earliest owning upstream stage; never patch only the
  final deliverable.

## Anti-Skip Rule

Do not hand-write a missing downstream artifact, add placeholders, or proceed on
the promise that an upstream contract can be fixed later. Run:

```bash
python scripts/progress_check.py paper_rewriting_output --gate <stage_name>
```

The final audit re-runs earlier checks as defense in depth. It is not the owner
of contribution, Results-validation, or reviewer-audit decisions.
