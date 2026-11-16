# Resume / Continue From Checkpoint

PaperSpine supports resuming from the first incomplete stage when a prior run
was interrupted.  Do **not** restart from scratch unless the user explicitly
asks for a clean run.

Use `execution-efficiency.md` to reuse valid work. On resume, recover saved choices
and the next action, not the whole historical loop. Reopen original method passages
when their content is no longer available; an unchanged hash or read marker cannot
replace the next action's actual constraints.

## Choose the existing authority first

For the current public host workflow, `SKILL.md` and `product-v1-workflow.md`
govern task opening and resumption: the Agent reading them is the host and
continues the same task from this conversation. The Runner loop below applies
only to an explicitly selected legacy Runner task.

If the user supplies a Product Web task or a current-host continuation request,
resume that exact task through the public host workflow in
`product-v1-workflow.md`. Use its installed host CLI when MCP tools are not
exposed. Read the public task snapshot and current configuration, choices,
feedback and artifacts; use `product-runner-host-route.md` only when the task
explicitly uses the legacy Runner. Do not infer the stage from a legacy folder
or create a new task because an optional nested Web Agent is unavailable.

`progress_check.py <actual-task-directory> --markdown` is an optional read-only
projection for a directory containing `task_record.json`. It is not a second
authority and its legacy `--gate` names do not submit ProductRunner answers.
Do not run the flat-output loop below on a Product Web task or manufacture a
`paper_rewriting_output/` tree beside it.

Only use the legacy loop below when the existing run genuinely uses the flat
`paper_rewriting_output/` layout and has no ProductRunner task authority. Use the
actual existing path, not a new folder relative to the current working directory.

## Anti-Skip Rule

Do not skip scientific work required by the saved workflow and the user's scope. When evidence is missing, establish what actually exists and perform only the work still needed before claiming the affected result complete. Do not:
- Fabricate results, confirmations or review records to fill a missing file
- Patch a downstream file so it claims unsupported upstream evidence
- Claim affected work complete with a "we'll fix it later" note
- Skip a stage because the user seems in a hurry
- Use `generate_artifacts.py`, `quick_generate.py`, `mock_artifacts.py`, or
  any bulk script to create placeholder intermediate files instead of running
  the real research, citation, planning, writing, or audit stage

A missing artifact means completion is not yet established from that file. Check the existing task, prior versions and actual outputs before deciding which scientific work must be recovered or performed; do not infer that the work was never run.

Writing a real missing manuscript section or repairing a producing script is
normal host work within the saved scope. Existing evidence can support the
repair without recreating historical administrative files. Reuse available method
knowledge; recover missing constraints from original passages and read changed task
facts or the relevant bridge file.

## ProductRunner resume loop

1. Read the same task's current snapshot and its bound issue/input packet.
2. Execute only the current stage's scholarly work with its routed playbook.
   Reuse unchanged valid results. A review requesting changes is a revision of
   this task, not a clean intake or permission to rewrite earlier evidence.
3. Submit through the issue's existing typed Runner tool with its current
   revision and issue binding. Use the normal user form where an actual user
   choice is required; a host answer must not impersonate that confirmation.
4. Read the returned state and continue the next incomplete stage. For review
   objections, follow the existing `revision_request` / `REVISION_REQUIRED`
   path in `product-runner-host-route.md`; do not substitute a prewritten PASS.
5. Verify actual paper artifacts and the same frontend's download before
   claiming delivery. A successful transport call alone is not a paper result.

For a completed local paper with new user feedback, use the existing task's
**请求修改** form or `paperspine5_runner_request_revision`, as described in
`product-runner-host-route.md`. Ordinary resume stays an idempotent recovery.
Select manuscript, figure, or reference-mapping scope from the actual change;
retain the previous download and follow the returned J8/J7/J6 issue. User
feedback is not an independent review and never authorizes copying an old PASS
onto revised files. New out-of-ledger materials use the existing same-task
add-materials/bootstrap route and therefore a genuinely new snapshot.

On a failure, classify its cause and make one corrective change before retrying;
never make a third materially identical attempt. Missing MCP exposure calls for
the installed host transport, not a different research workflow or a new login.

## Legacy flat-output resume loop

Resume is a loop, not a one-step patch:

1. Run `progress_check.py paper_rewriting_output --markdown --write` once for
   the current unchanged task revision/material snapshot.
2. Execute the reported `next_stage` by reading its `references/*.md` playbook.
3. Run `progress_check.py paper_rewriting_output --gate <stage_name>`.
4. If the gate passes, run the full progress check again.
5. Continue with the new `next_stage` until `final_audit` is complete.

When the gate leaves the same `next_stage`, classify the exact failure before
retrying. Make one concrete corrective change and retry once; never perform a
third materially identical attempt on the same input hashes. Follow
`execution-efficiency.md` for receipt reuse and blocker reporting.

Do not stop after fixing one missing stage unless:
- the workflow is BLOCKED on user confirmation;
- a required external tool is missing and the report states BLOCKED/FAIL;
- the user explicitly asks you to pause.

## Legacy flat-output rules

1. **Before continuing a legacy flat-output workflow**, run `progress_check.py`
   against its existing `paper_rewriting_output/` directory. Read the output
   (Markdown or JSON) to determine `next_stage`. Product Web tasks instead use
   the ProductRunner loop above.

2. **If `next_stage` is `intake`** and config already exists, verify the config
   is complete before re-entering intake.  If config is valid, advance to the
   next stage.

3. **If `next_stage` is `semantic_confirmation` and status is `BLOCKED`:**
   read `references/semantic-confirmation.md`, then present the existing
   `contribution_options_after_research.md` and
   `motivation_options_after_research.md` to the user. Do not rewrite the
   options merely to bypass the gate. Wait for explicit user confirmation
   before writing `confirmed_contribution.md` and `confirmed_motivation.md`.
   `motivation_confirmation` is accepted only as a legacy gate alias.

4. **For any other `next_stage`**, read the corresponding `references/*.md`
   playbook and execute that stage.  Do not re-run earlier stages whose
   artifacts already exist and are valid. Do not reread the playbook while the
   stage inputs and task revision are unchanged.

5. **When a stage completes**, run `progress_check.py --gate <stage_name>` to
   verify the stage's artifacts before moving to the next stage. If the gate
   fails, the stage is not complete — return to it.

6. **The `progress.md` file** (written by `progress_check.py --write`) is the
   authoritative resume map only for a genuinely legacy flat-output workflow.
   For Product Web tasks, `task_record.json` plus its hash-bound Runner artifacts
   are the authority and the progress script is a read-only projection of that
   state. The current host answers open academic issues directly through the
   typed Runner facade.

7. **Locate the authoritative artifacts before judging completion.** Check the existing task workspace, prior versions and referenced output paths. For a genuine legacy flat-output run, repair misplaced paths only after checking file identity and dependencies; do not discard valid work merely because it uses another layout.

   **Nested output directories require diagnosis.** Check which files are current, which are prior versions and which paths the manuscript references. Correct only confirmed misplaced files while preserving valid versions; a nested directory alone is not evidence of incomplete science.

   **Multiple final-paper directories require comparison.** Identify the current canonical source and delivered version by content, references and task records. Preserve previous versions; remove a duplicate only when its redundancy and the user's deletion scope are established.

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

## Legacy gate script

```bash
# Resume check (full progress scan)
python scripts/progress_check.py paper_rewriting_output --markdown --write

# Stage-level gate (after completing a stage)
python scripts/progress_check.py paper_rewriting_output --gate research
python scripts/progress_check.py paper_rewriting_output --gate citation
python scripts/progress_check.py paper_rewriting_output --gate semantic_confirmation
python scripts/progress_check.py paper_rewriting_output --gate planning
python scripts/progress_check.py paper_rewriting_output --gate drafting
python scripts/progress_check.py paper_rewriting_output --gate integrity_audit
python scripts/progress_check.py paper_rewriting_output --gate latex
python scripts/progress_check.py paper_rewriting_output --gate word --require
python scripts/progress_check.py paper_rewriting_output --gate final_audit
```

## Restart (Clean Run)

Only when the user explicitly requests a restart, resolve the exact task/output
scope and preserve the existing run unless the user authorized its removal.
Use the normal task creation route for a new Product Web run; never erase or
relabel an existing task store to force intake.
