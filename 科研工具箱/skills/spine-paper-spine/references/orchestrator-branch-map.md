# Orchestrator Stage Map

PaperSpine is a single main-orchestrator skill with staged playbooks under
`references/`. The orchestrator reads the relevant playbook for each stage,
verifies its artifacts, and routes back when a required artifact is weak or
missing.

## Stage Order

1. `references/intake.md`: write `paper_spine_config.json` and
   `paper_spine_config.md`. Gate: `intake`.
2. `references/research.md`: ingest local references, collect official
   requirements, learn target examples/SOTA, and propose motivation options.
   Gate: `research`.
3. `references/citation.md`: build `citation_support_bank.md` for literature
   statements in Introduction/Discussion/background. Gate: `citation`.
4. User confirmation: write `confirmed_motivation.md` only after the user
   chooses or revises the motivation. Gate: `motivation_confirmation`
   (BLOCKED until user confirms).
5. Humanize (conditional): apply tier-specific stylistic constraints when
   `humanize_tier` is `light`, `medium`, or `heavy`. No separate gate; applied
   during writing.
6. `references/rewrite.md` or `references/build.md`: produce section
   blueprints, `writing_rationale_matrix.md`, and draft `final_paper/main.tex`.
   Gates: `planning` (blueprints + rationale), `drafting` (main.tex).
7. Integrity audit: run `integrity_audit.py` and `artifact_check.py` to verify
   logic transfer, revision depth, artifact completeness, and intermediate
   format before LaTeX assembly. Gate: `integrity_audit`.
8. `references/latex.md`: assemble LaTeX, compile PDF when possible, and
   produce Word (.docx). Gates: `latex` and `word` unless `word_output` is
   explicitly `none`.
9. Translation (conditional): produce `translation_zh/` package when
   `translation_package` is `zh`. Gate: `translation`.
10. Submission (conditional): produce `submission_package/` when requested.
    Gate: `submission`.
11. Final audit: verify `citation_quality_audit.md`,
    `final_artifact_manifest.md`, `artifact_check.md`, and Word report before
    declaring complete. Gate: `final_audit`.

## Stage To Playbook Reference

When `progress_check.py` reports a PENDING stage, read the corresponding
playbook:

| Stage Key | Status | Reference Playbook |
|---|---|---|
| `intake` | PENDING | `references/intake.md` |
| `research` | PENDING | `references/research.md` |
| `citation` | PENDING | `references/citation.md` |
| `motivation_confirmation` | BLOCKED | Stop; present options to user and wait for confirmation |
| `motivation_confirmation` | PENDING | `references/research.md` |
| `planning` | PENDING | `references/rewrite.md` or `references/build.md` |
| `build_from_materials` | PENDING | `references/build.md` |
| `rewrite_existing` | PENDING | `references/rewrite.md` |
| `drafting` | PENDING | `references/rewrite.md` or `references/build.md` |
| `integrity_audit` | PENDING | `references/audit.md` |
| `latex` | PENDING | `references/latex.md` |
| `word` | PENDING | `references/latex.md` |
| `translation` | PENDING | `references/translate.md` |
| `submission` | PENDING | `references/submission.md` |
| `final_audit` | PENDING | `references/audit.md` |

## Anti-Skip Rule

**No stage may be skipped.** Each stage produces specific artifacts that later
stages depend on. Before starting a stage, verify the previous stage's gate
passes:

```bash
python scripts/progress_check.py paper_rewriting_output --gate <stage_name>
```

If the gate fails, route back to the stage that should have produced the missing
artifact. Do not:

- Hand-write the missing file
- Add a `TODO`, `[VERIFY]`, or placeholder to downstream output
- Proceed with the claim that it "can be fixed later"
- Use bulk placeholder generators instead of the real stage workflow

## Loop Rule

If a stage output fails audit, route back to that stage. Do not patch the final
paper directly when the missing artifact should have been created earlier.

Examples:

- Missing local source paths: return to `references/research.md`.
- Too few or unverified citation candidates: return to `references/citation.md`.
- Shallow writing matrix: return to `references/rewrite.md` or
  `references/build.md`.
- Broken labels/citations in LaTeX: return to `references/latex.md`.
- Missing or corrupt Word output: return to `references/latex.md`.

## Word Output

Word (.docx) is a standard required artifact produced by the LaTeX stage. It is
not optional unless `word_output` is explicitly set to `none` in config. The
audit stage checks Word output with `word_guard.py` and requires PASS.
