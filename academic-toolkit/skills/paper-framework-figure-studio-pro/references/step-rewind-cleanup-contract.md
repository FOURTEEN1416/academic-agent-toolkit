# Step Rewind Cleanup Contract

If a user returns to an earlier or current step and that step will be executed again, cleanup is mandatory before execution by default.

This default also applies after interruption. If the user says a previous turn was interrupted and asks to enter/run/execute/start the current or an earlier step again, mentioning "interrupted" or "涓柇" alone does not preserve partial outputs. Treat the request as cleanup + rerun unless the same user turn explicitly asks to continue from the interrupted point, resume without cleanup, keep existing generated artifacts, or only finish missing items.

Explicit interrupted-resume exception: skip cleanup only when all of the following are true:

- the target is the same `current_step`, not an earlier-step backjump;
- the user explicitly asks for resume/continue/no-cleanup behavior;
- the step attempt is incomplete or the agent can identify missing same-step outputs;
- existing same-step artifacts can be inspected and judged valid enough to continue.

If any condition is unclear, if the user says rerun/重新执行/重跑/覆盖/删除后再来, or if the existing artifacts are inconsistent, use the default cleanup + rerun route.

Cleanup scope is the covered span from `target_step` through the previous `current_step`, inclusive.

Cleanup must:

- delete covered output directories and canonical files;
- remove covered active artifact records;
- remove covered image generation events;
- refresh pending outputs and active artifact roles;
- preserve `state/project-state.json`;
- preserve a cleanup event audit trail.

If the user only asks a status/history question, status check, or explanation, inspect state/history without cleanup.

Rerun mode may read a same-step artifact as rerun input, but downstream active outputs after the reruned step must be cleaned because they depended on the earlier artifact.

When the explicit interrupted-resume exception is used, record a resume note/event in `state/project-state.json` or the current step report, list preserved same-step artifacts, list missing items to finish, and do not change downstream outputs unless the resumed stage writes a new completed result that invalidates them.

## Post-S5 Boundary Removed In v3.2.13

After S5, human decisions are outside this assistant workflow.

- After S5, human decisions are outside this assistant workflow.
- After S5, human decisions are outside this assistant workflow.
- After S5, human decisions are outside this assistant workflow.
- write a cleanup event to `state/project-state.json`;
- After S5, human decisions are outside this assistant workflow.

## Post-S5 Boundary Removed In v3.2.13

After S5, human decisions are outside this assistant workflow.

In this mode:

- After S5, human decisions are outside this assistant workflow.
- After S5, human decisions are outside this assistant workflow.
- After S5, human decisions are outside this assistant workflow.
- After S5, human decisions are outside this assistant workflow.
- After S5, human decisions are outside this assistant workflow.
- After S5, human decisions are outside this assistant workflow.

After S5, human decisions are outside this assistant workflow.
