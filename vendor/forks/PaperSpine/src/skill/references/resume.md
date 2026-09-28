# Resume / Continue From Checkpoint

PaperSpine supports resuming from the first incomplete stage when a prior run
was interrupted.  Do **not** restart from scratch unless the user explicitly
asks for a clean run.

## Anti-Skip Rule

**No stage may be skipped.** When a stage's artifacts are missing, that stage
MUST be executed before any later stage. Do not:
- Hand-write a missing artifact to "fill the gap"
- Patch a downstream file to work around a missing upstream artifact
- Proceed with a "we'll fix it later" note
- Skip a stage because the user seems in a hurry
- Use `generate_artifacts.py`, `quick_generate.py`, `mock_artifacts.py`, or
  any bulk script to create placeholder intermediate files instead of running
  the real research, citation, planning, writing, or audit stage

A missing artifact means the stage that should have produced it was not run.
Run that stage. This is non-negotiable.

## Resume Loop

Resume is a loop, not a one-step patch:

1. Run `progress_check.py paper_rewriting_output --markdown --write`.
2. Execute the reported `next_stage` by reading its `references/*.md` playbook.
3. Run `progress_check.py paper_rewriting_output --gate <stage_name>`.
4. If the gate passes, run the full progress check again.
5. Continue with the new `next_stage` until `final_audit` is complete.

Do not stop after fixing one missing stage unless:
- the workflow is BLOCKED on user confirmation;
- a required external tool is missing and the report states BLOCKED/FAIL;
- the user explicitly asks you to pause.

## Rules

1. **Before starting any workflow**, run `progress_check.py` against
   `paper_rewriting_output/`.  Read the output (Markdown or JSON) to determine
   `next_stage`.

2. **If `next_stage` is `intake`** and config already exists, verify the config
   is complete before re-entering intake.  If config is valid, advance to the
   next stage.

3. **If `next_stage` is `motivation_confirmation` and status is `BLOCKED`:**
   stop and present the existing `motivation_options_after_research.md` to the
   user.  Do not rewrite the motivation options.  Wait for explicit user
   confirmation before writing `confirmed_motivation.md`.

4. **For any other `next_stage`**, read the corresponding `references/*.md`
   playbook and execute that stage.  Do not re-run earlier stages whose
   artifacts already exist and are valid.

5. **When a stage completes**, run `progress_check.py --gate <stage_name>` to
   verify the stage's artifacts before moving to the next stage. If the gate
   fails, the stage is not complete — return to it.

6. **The `progress.md` file** (written by `progress_check.py --write`) is the
   authoritative resume map.  Read it alongside the script output.

7. **Misplaced artifacts are not completion evidence.** If `final_paper/`,
   `writing_rationale_matrix.md`, `citation_support_bank.md`,
   `translation_zh/`, or other workflow artifacts appear next to
   `paper_rewriting_output/` instead of inside it, treat the run as incomplete.
   Rebuild or move the artifacts under `paper_rewriting_output/`; do not declare
   completion from outer-directory files.

   **Nested directories are a hard error.** If `paper_rewriting_output/`
   contains another `paper_rewriting_output/` inside it, artifacts were written
   one level too deep. Move all contents up one level and remove the inner
   directory. Do NOT declare completion while a nested directory exists.

   **Sibling final_paper is a hard error.** If `final_paper/` exists both in
   the parent directory (sibling to `paper_rewriting_output/`) and inside
   `paper_rewriting_output/`, keep only the copy inside and remove the sibling.

8. **Word is required by default.** If `paper_spine_config.json` does not set
   `word_output`, treat it as `docx`. Only an explicit `word_output=none`
   disables Word output.

9. **artifact_check.md FAIL or BLOCKED blocks completion.** If
   `artifact_check.md` reports `Status: FAIL` or `Status: BLOCKED`, the
   workflow is not complete. Do not declare `is_complete=true`. Return to the
   failing upstream stage (missing artifacts, weak rationale matrix, thin
   citation bank, or misplaced artifacts). Only when `artifact_check.py`
   exits 0 and the progress report shows `is_complete=true` may completion be
   declared.

10. **citation_bank_check FAIL blocks completion.** If `citation_bank_check.md`
    reports `Status: FAIL`, the citation support bank is not qualified. Return
    to the citation stage and fix weak rows before proceeding.

## Gate Script

```bash
# Resume check (full progress scan)
python scripts/progress_check.py paper_rewriting_output --markdown --write

# Stage-level gate (after completing a stage)
python scripts/progress_check.py paper_rewriting_output --gate research
python scripts/progress_check.py paper_rewriting_output --gate citation
python scripts/progress_check.py paper_rewriting_output --gate planning
python scripts/progress_check.py paper_rewriting_output --gate drafting
python scripts/progress_check.py paper_rewriting_output --gate integrity_audit
python scripts/progress_check.py paper_rewriting_output --gate latex
python scripts/progress_check.py paper_rewriting_output --gate word --require
python scripts/progress_check.py paper_rewriting_output --gate final_audit
```

## Restart (Clean Run)

Only when the user explicitly requests a restart, delete or rename the output
directory and begin from intake.
