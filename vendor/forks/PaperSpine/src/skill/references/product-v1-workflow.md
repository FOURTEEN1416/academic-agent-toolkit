# Public host workflow and task files

Use one paper-spine Skill, one task ID and the same user-data/core/event database
as Web. The host's normal tools do the scientific work; P2 public MCP calls
record task facts. No Runner academic answer or installed legacy MCP connection
is required for the default host CLI.

## Invocation update preflight

Use the current installed Skill's verified Python to run:

```text
python scripts/paperspine_update.py --preflight --yes
```

For a managed suite this chooses the current Windows x64, Linux glibc x86_64,
macOS Apple Silicon or macOS Intel bundle from the official update channel.
`--preflight --check-only` checks without installing; `--source <channel.json>`
and `--control-root <directory>` are explicit local/testing overrides. The
existing opt-in `--auto` interval mode remains compatible. A saved explicit
opt-out is respected; an unreachable update source does not stop an already
working installation. Installation/validation failures are reported rather than
presented as success. Preserve the task/profile binding; reread the installed
Skill after an upgrade and use the new verified suite for subsequent launches.
An already running old Web process must be stopped gracefully at a saved boundary
and relaunched on the same profile; do not point a second server at live data.

## CLI entry and profile selection

Start or reuse the public Web with the installed Skill's Python launcher:

```text
python scripts/paperspine5_web.py launch
python scripts/paperspine5_web.py status
python scripts/paperspine5_web.py host tools --tool paperspine_open_task
python scripts/paperspine5_web.py host snapshot --summary --task-id "<same-task-id>"
```

On Windows prefer the installed `launch_paperspine_ui.ps1`; it resolves `PAPERSPINE5_PYTHON`, a bundled vendor runtime when present, or a verified Python.

The public launcher and MCP share the same local profile. First launch uses
the normal local default only if it is empty; later launches and host calls
reuse the remembered profile. `launch --profile-root "<existing-profile>"
--remember` selects an existing profile as the local default. This
remembers a directory preference, not a new task or copy of its database.
Launch is service-only by default (`--no-open` is explicit compatibility). After
opening/resuming the exact task, open its returned task URL once in the user's
chosen browser; in Codex prefer the available in-app browser unless overridden.
Do not open a root homepage externally and a task page in the host. Reuse the
chosen tab. `--open-browser` is an explicit external-browser opt-in, never a second
opening path. Printing a URL is not
a handoff. Starting Web does not start another scientific Agent.

The launcher/profile identifies a shared Web service, not the current paper.
Resolve the folder named by the user; “current folder” explicitly selects the
conversation working directory. Reuse a task only when its saved material roots
match this paper, or the user explicitly identifies it. Never select the latest
task, a browser tab or another paper merely because it uses the same profile.
Separate papers use separate task IDs. Generated `workspace_root/paper/` files
and external authorized material roots need not be the same directory.

For a genuinely new task the current Agent calls `paperspine_open_task`, supplying
a meaningful title and one-sentence description in its payload. Prefill known
settings as a proposal, open the same-task URL, and wait for Web configuration
and material confirmation before dependent scholarly work. Initial file-name
inventory does not substitute for the user's material choice. Reuse valid saved
configuration on an ordinary resume; a user-requested fresh test starts fresh.

If launcher/tools/page access fails, fix the concrete cause in this installation
and retry the same profile. Never switch to a legacy Runner or nearby source
tree. Existing confirmed scope permits independent local corrections during a
Web outage; missing configuration or pending choices still block dependent work.
Do not manufacture saved state or delegate scientific execution to the server.

For an existing development Web without product-config.json, an integrator
may bind its exact existing paths once with `launch --profile-root <profile>
--user-data-root <existing-user-root> --core-root <existing-core>
--domain-database <existing-events.db> --remember --no-open`. All three existing
paths are required; this saves their locations without copying or reconstructing
task data. Stop the exact old server before changing its code. A live runtime
with different bindings is reported, not replaced or duplicated. Normal paper
work should subsequently use the saved profile, without development paths.

The launcher invokes the Skill's `scripts/paperspine5_web.py` with a verified Python runtime. `--python-executable` or `PAPERSPINE5_PYTHON` may select an
already working interpreter. It does not install packages, change global MCP
configuration or request a new host login.

For a saved product profile, these commands read its existing
`data/product-config.json` (or `product-config.json`) and active core pointer:

```text
python scripts/paperspine5_web.py host tools --profile-root "<existing-profile>"
python scripts/paperspine5_web.py host snapshot --profile-root "<existing-profile>" --task-id "<same-task-id>"
python scripts/paperspine5_web.py host call --profile-root "<existing-profile>" --task-id "<same-task-id>" --tool paperspine_get_task --arguments-file "<arguments.json>"
```

The arguments file for `paperspine_get_task` can be `{}` when `--task-id` is
provided. For tools whose MCP schema wraps input in `request`, preserve that
wrapper. Use `host tools --tool <name>` to read a schema when first needed;
reuse it within the unchanged installation. Rediscover after a code update or
schema-related error, not before every call to the same tool.
`--arguments-file -` reads stdin, keeping paper input out of command-line text.
Output is JSON and failures have a nonzero exit status, including domain errors
returned inside an otherwise successful MCP message. There is no automatic retry.

Use the exact public tool name returned by `host tools`, including `paperspine_`.
For a task-relative artifact `source`, omit optional media type, byte size and
hash when the schema allows the product to derive them. `package_scope` belongs
only to `delivery_package`. Inspect the specific schema before adding fields.
A directory-write or interpreter error is an environment failure, not evidence
that the Skill was not installed. Read stderr and repair that concrete cause;
do not switch to source paths or reinstall as the default recovery action.

For a source/development runtime without a saved profile, pass the exact paths
already used by Web. `--project-root` selects the product code; `--core-root`
preserves the current task core identity and may intentionally be different:

```text
python scripts/paperspine5_web.py host snapshot --project-root "<product-source>" --user-data-root "<same-user-data>" --core-root "<same-core>" --domain-database "<same-events-db>" --task-id "<same-task-id>"
```

Use the same binding options for `host tools` and `host call`. `--output-dir`
remains an alias for `--user-data-root`; it is the product data root, **not** the
paper output directory. `--contracts-root` is optional when contracts are under
the selected product code. Equivalent environment variables are
`PAPERSPINE5_PROFILE_ROOT`, `PAPERSPINE5_PROJECT_ROOT`, `PAPERSPINE5_USER_DATA_ROOT`,
`PAPERSPINE5_CORE_ROOT`, `PAPERSPINE5_DOMAIN_DATABASE` and
`PAPERSPINE5_CONTRACTS_ROOT`. Explicit paths conflicting with a saved profile
fail rather than silently selecting another task store.

Without a profile or explicit event path, the existing runtime convention is
`<user-data>/registry/application.sqlite3`. If the existing Web uses another
path, pass it explicitly. The CLI does not create a replacement event database
under a populated user-data root when that path is missing. It does not run the
release install/prepare/migration protocol to make a source core look installed.

These commands start a short-lived P2 MCP server transport sharing the selected
profile; the transport itself is not another scientific Agent or Web server.
The current host Agent uses the public `paperspine_open_task` call when this
conversation has no task, and uses the same task's calls to record configuration
or stage progress. Use the **existing Web origin** plus the task's
`skill_bridge.web_path` to show configuration/choices; the host browser tool
opens that URL. If browser control is unavailable, provide the exact task URL.
Opening a URL is not proof that the user made a choice or downloaded a file.
For execution, the configuration view must report `source: "web_user"`,
`user_confirmed: true`, and `readiness.ready: true`. A configuration written
by the host is a proposal and cannot authorize Runner work.

Old token-bound Web launch/status remain available only with `--legacy-runner`;
`api` retains that old token-bound surface. The default launcher and host calls
use the public facade. Do not choose the legacy option for normal paper work.

## Read current choices without replaying the full history

Use `host snapshot --summary` for a quick resume and read only the relevant
configuration, choice or feedback file. Each bridge JSON carries `task_version`.
Compare versions of files used together with `00_task_state.json` and the
current task snapshot. If they differ, reread the changed views or use one
public task snapshot; never combine a stale selection with a new file binding.
The bridge is derived from events and is not a directory-wide atomic snapshot.

Retain the last consumed event `sequence` in the continuation note. Read
`paperspine_list_task_events` with `after_sequence` set to that value to get
only newer events; omitting it defaults to zero and returns all history. A first
resume can inspect the current task without fetching the whole event log.
Task versions and event sequence numbers are different cursors: do not infer
one from the other. For bounded waits, pass the last observed task version to
the actual wait-tool schema, then reread the saved choice when a change arrives.
Do not interpret a timeout as user input or repeatedly scan the transcript.

Keep a short continuation note at a real stage boundary, interruption or finish:
task/profile, observed task version and event cursor, current scientific files,
pending input or actual failure, and the next useful action. When a later state
supersedes an old blocker, retire that instruction in the note. On recovery,
current public task facts take precedence over the note; the note only supplies
scientific context that those facts cannot express. A stale note is not a reason
to repeat an old review, package repair or user choice.

A compact task/chat summary may omit an in-flight or recently completed tool.
Absence of a tool in that summary does not establish host inactivity. Before
interrupting or taking over, check actual execution completion/error or the
existing host run status; do not infer a stall from an unchanged summary alone.
Keep one scientific writer responsible at a time. During a browser-user replay,
express ordinary preferences through Web. If a concrete product defect requires
developer help, identify that intervention and resume the same task afterward;
do not count the intervention as an unaided user action or inject a selection.

## Same-task calls

Start with `paperspine_get_task`, read actual configuration/material roots,
`progress.current_milestone` when present, pending choices and feedback.
Use `paperspine_list_task_events` to recover context. Reading a task does not
authorize creating/importing another one. `paperspine_open_task` is for a truly
new user task or an explicit resume of the same existing ID; retain the previous
paper, choices and materials. A missing task may mean the wrong event database.
A "new task" is created by the current host conversation itself: the Agent that
read the Skill calls `paperspine_open_task` now. It is a product task record, not
a new host session, so never tell the user to open another conversation first.

For a mutation, keep its actual `request` shape from the public schema. For
example a milestone request contains `schema_version`, `task_id`, a stable
`command_id`, the current **public `task_version`** as `expected_version`, and
`payload` with the stage, factual `summary` and actual `artifact_ids`. Do not
substitute legacy Runner revision for the public version. Read current state
after a conflict; do not silently replay a decision against different inputs.

### Keep workbench progress aligned with actual work

Before each next substantive segment or stage, the host MUST check that the
previous segment is already represented in this same task's workbench. Read the
current snapshot, publish completed files that should be visible, then record
actual work with `paperspine_commit_milestone`. Read back its task ID, stage,
summary, artifact IDs and pending choices before beginning dependent work. If
the saved checkpoint already matches, reuse it. This also applies within a stage
when a real deliverable has been produced, and immediately on resume; it is not
a call after every sentence or tool invocation. For example, record `research` while studying evidence and `draft`
when writing the manuscript. Publish actual files with
`paperspine_publish_artifact`, then reference their returned IDs in the milestone.
A saved file or an artifact's `stage` labels that file only; neither changes the
task's current stage. This is why a finished local manuscript can coexist with
an unchanged research page if the host omits the progress call.

Use the discovered schema with this shape (replace all example values):

```json
{"request":{"schema_version":"1.1","task_id":"<same-task-id>","command_id":"<unique-stage-update>","expected_version":6,"payload":{"stage":"draft","summary":"Manuscript draft saved; independent review remains pending.","artifact_ids":["<published-manuscript-id>"]}}}
```

Read the latest public `task_version` after publishing; `6` above is only an
example. Use an empty artifact list when recording ongoing work without a
published output. Verify the returned projection and the same task's next
snapshot/`00_task_state.json` show the intended stage. If they disagree, check
the task/profile binding and the command result; do not recreate the paper or
hand-edit generated workflow JSON. A milestone records progress, not scientific
approval: retain actual choices, independent review and delivery requirements.

### Select research materials; keep partial failures local

List names in the user's authorized root first and identify the files needed for
the paper. Use exact forward-slash relative file paths, not globs or directories:

```json
{"request":{"schema_version":"1.1","task_id":"<same-task-id>","command_id":"<unique-material-selection>","expected_version":6,"payload":{"replace":true,"grants":[{"grant_id":"research-inputs","uri":"<user-selected-absolute-folder>","scope":"read_only","include_paths":["results/observations.csv","draft.docx","figures/figure1.pdf"]}]}}}
```

Use `replace: true` only when this selection intentionally replaces earlier
roots; omitted/false preserves them. Omit `include_paths` on a repeated grant to
reuse its saved selection. Without a prior selection the compatibility scan
reads the root while excluding common development caches and the task's own
output tree. Do not rely on that fallback for a mixed project directory.
Newly generated manuscripts must not silently become input materials on rescan.

Read `material_inventory.entries` and `scan_issues` after registration. Successful
files are retained even when another file is locked, missing, changes while read,
or cannot be copied. `materials.read_failed` includes the concrete file/OS cause;
it is a warning for an individual file, not proof that the whole root is unreadable.
When an already read file fails, a hash-verified last successful task copy can be
retained with `materials.saved_copy_retained`; use it as the saved version, never
claim that the current source was reread. An empty inventory is not successful scientific reading. Explain the missing
inputs, use actual readable evidence, and continue unaffected work. Only work
that requires the unavailable evidence waits. Invalid roots or paths outside the
authorized root remain errors; do not bypass them. Saved research configuration
remains valid; material changes can still invalidate conclusions based on changed
inputs, which must be checked before claiming current review/delivery readiness.
Never silently claim an unreadable file was read or reinstall to fix a file lock.

After a configuration, choice or feedback save, Web displays a persistent reminder
to return to the host conversation. It also reminds at an actual recorded phase
transition. The copied continuation message keeps the current task binding. This
is a handoff, not an automatic wake-up: if the host is still waiting, it consumes
the saved event normally; if its turn ended, the user sends that same-task message.

### Show the configuration node again

Web edits configuration only while the host's current stage is `intake`.
If the user asks to change or reconfirm settings during later work, use the
existing `paperspine_commit_milestone` with `payload.stage: "intake"`, a factual
summary of the requested configuration work, and actual applicable artifact IDs
(an empty list when none apply). This preserves the task and previous settings;
it does not claim a research result. Open the same task URL and await its actual
configuration save. A `target_boundary` choice is not a replacement for this.
Do not reopen configuration simply to repeat an already valid user choice.

Use `paperspine_request_decision` for motivation/contribution and figure
options. Provide understandable labels and risks, optional descriptions, and
task-relative `files` for real candidate/figure previews where supported by the
current public schema. The public API exports these facts to the choice files;
Web records the user's selection. Read the selected option and comments before
continuing. Reuse prior valid choices; never generate an academic Runner answer
as a proxy for a user's ordinary figure choice.

A direction option can explain both what the work contributes and why it matters.
When its saved choice and comments settle both, reuse that semantic decision;
ask a separate motivation question only when a real scientific choice remains.
Keep individual figure/panel choices and feedback distinct; revise is not adoption.

For option `files`, use exact, forward-slash task-relative paths to supported
files under `paper/figures/` or `paper/figure-candidates/`. Revision subdirectories
inside these roots are supported. A similarly named directory elsewhere in the
manuscript tree, an artifact ID or a bare filename is not the same path. Keep the
originals and place the intended previews in the discovered roots when needed.

After writing candidates, refresh the same public task and read the bridge's
`04_figure_choice.json`. Its `candidate_files` entries whose `source` is
`skill_bridge_candidate` provide the discovered `relative_path` values. The list
also contains published figure artifacts; an artifact's presence alone does not
establish a matching selectable file. No new Runner plan or reference workspace
is needed for ordinary candidate discovery.

Discovery does not require `paperspine_publish_artifact`. Place previews once in
the returned workspace's discovered directories. Publish only when a formal
current artifact or review/delivery binding is needed, rather than registering
every exploratory candidate merely to display it. Reuse unchanged publications.
For an uncertain write, inspect the task/events and replay the same command ID
and exact payload when appropriate; do not mint a new ID to repeat the effect.

The request checks provided file references using the same discovery boundary as
Web. A `validation_failed` response identifies unmatched paths and how to correct
them before a choice card is recorded. Correct the producing path or request and
continue the same task; this is an ordinary recoverable tool error, not a scientific
failure or a new user approval. On a version conflict, reread the actual task and
saved choice first. Do not overwrite a choice that arrived while correcting a
preview. Validated references still need actual browser rendering/selection checks.

### Wait for the user's saved input

Use the attached host wait while the user works in Web, with the explicit same
profile/task and last observed task version:

```text
python scripts/paperspine5_web.py host wait --profile-root "<same-profile>" --task-id "<same-task-id>" --after-version <observed-task-version>
```

This keeps one stdio/MCP session and calls `paperspine_wait_for_task_change`
for up to 50 seconds per API wait (`--wait-seconds`, default 50). Normal
`changed=false` replies continue inside the process. Run it through the host's
execution tool; when that tool yields a running session, continue waiting on
that same session. Stay responsive to conversation and do independent authorized
work where practical. Interrupt the running process to cancel; inspect real errors.

On a real change the command exits with the original API result. Inspect its
task and the exact pending configuration/choice, including saved comments.
If that input is still pending, run the command again with the returned
`task_version`; an unrelated event does not supply an answer. The same-task Web
save remains the confirmation boundary. Once the input is valid, continue the
scientific work. Cancel the wait if the user cancels or redirects the task.

Direct MCP or `host call` keeps its bounded behavior: on `changed=false`, wait
again from the returned version without ending the host turn. The attached
command is a foreground wait, not a subscription that wakes a finished host
turn. After a real interruption, resume from `host snapshot` and the pending
input in the same task.

## Another host can continue the same paper

Opening a history card only displays saved task data; it does not wake an AI or
switch an active host's task. The user can send the copied handoff to the original
or a new authorized host. Bind the exact task ID, service and explicit user-data,
core and event-database paths (or an equivalent verified profile), not a remembered
unrelated profile. Re-read the latest task and workflow views, actual artifacts and
relevant work notes. Missing unwritten history is unknown, not shared model memory.
Reuse valid choices and results; do not recreate the task or redo research. Keep
one scientific writer at a time. A new host still obeys its own permissions.
Separate browser drafts are not shared: only saved data for the same service and
task is synchronized. A health indicator is not evidence that an AI is executing.

## One paper directory

Read the returned `workspace_root`; do not calculate task folders from IDs.
Normal host file tools write beneath `<workspace_root>/paper/`:

- `paper/figures/` and `paper/figure-candidates/`: actual current/reference/candidate
  files, including PDF previews and editable source. Web automatically discovers
  supported files. Keep recognizable names and prior versions.
- Other paper files: manuscript sources, citations, selected analysis scripts
  and existing/new results, real review notes, rendered PDF/DOCX and packages.
  Organize subdirectories to fit the paper; no ceremonial directory set is required.
- `paper/workflow/`: product-generated readable handoff files. Do not write task
  state, configuration, user selections or feedback directly into these JSONs.

Read `00_task_state.json` first, then `01_configuration.json`, `02_materials.json`,
`03_motivation_choice.json`, `04_figure_choice.json`, `05_review_feedback.json` or
`06_delivery_manifest.json` as needed. These are views of the same public task.
When a view is stale, reread the public task so the product refreshes it; do not
hand-edit its values or rebuild state with internal Python/database calls.

Publish files through `paperspine_publish_artifact` using, for example,
`source: {"relative_path": "paper/manuscript.pdf"}`. Omit `grant_id` for this
task's own output when that current public schema supports task-relative import;
the product checks the path and computes hash/size. A grant ID remains relevant
to explicitly authorized external input directories. Do not relocate your own
paper output outside the workspace merely to authorize it again. If connected
tools still require this old behavior, report the concrete source/schema drift
to the integrator; do not fabricate hashes or change the task.

For artifact writes, `host call --tool paperspine_publish_artifact --summary ...`
returns a compact successful host receipt retaining version, events and replay
facts. Default output remains complete. Summary changes no public command,
idempotency or error; read a relevant bridge file or snapshot for actual choices.

Public sources and working notes belong in this task's paper directory. Use
`research_note` for source snapshots, analysis notes, and contribution/motivation
rationale, at their actual stage and with the correct media type and provenance.
Independent notes coexist under distinct artifact IDs; they do not need to be
combined or assigned manuscript document IDs just to stay visible. Publish useful
intermediate results when needed, not every scratch file. A rationale interprets
the saved choice; it does not replace the user's configuration or decision record.
`manuscript_source` means the editable source of a manuscript document, not every
Markdown file that contributes to writing. Its document/version rules below also
apply outside the draft stage; a different filename, artifact ID or stage does
not make it a separate document. Keep that type for actual manuscript sources.
`AuthorizeMaterials` grants access to additional external input directories;
do not use it to reauthorize this workspace or relocate public sources for a grant.

Artifact type describes the file's role, not just its extension. Publish the
current manuscript PDF as `pdf`; publish a faithful Word-to-PDF review preview
as `review_packet` with `media_type: "application/pdf"`. A figure stored as PDF
is a `figure`. Publishing another `pdf` for the same document replaces that
document's current PDF, even when its artifact ID or stage differs. After publishing, read the task and confirm
that the intended manuscript, previews and both package variants are fresh.

For separate manuscript documents (main text, supplement, response letter),
publish their manuscript_source/PDF/DOCX/TeX/bibliography artifacts with distinct
stable `document_id` values such as `main`, `supplement`, and `response`.
Reuse that identity across formats and revisions. An explicit `document_id` is
authoritative, including when correcting a previous classification. If omitted
and `supersedes_artifact_ids` names existing same-type artifacts in this task,
the publication inherits their unique document identity, including from historical
artifacts; an old target without `document_id` has the legacy identity `main`.
For example, replacing a supplement DOCX this way retains `supplement` and leaves
the current main DOCX fresh. Multiple target identities require an explicit
`document_id`; the existing repairable validation error is returned before file
import or event writes. Missing, invalid, self or cross-type target IDs remain
validation errors; they never trigger a fallback or get silently ignored.

A new publication without replacement targets still defaults to `main` for
compatibility; filenames do not distinguish documents. A new edition automatically
replaces only its own document and format, in addition to its explicit replacement
targets. The resolved identity is saved in new events; older events are not
rewritten or reclassified on replay. To recover a wrongly classified existing
artifact, republish its verified bytes with the correct explicit identity; keep
the same task and preserve history. This correction remains authoritative even
when replacement targets have a different historical identity.

When a corrected figure, source note or review preview replaces an older one,
publish its new immutable ID with `supersedes_artifact_ids: ["<old-id>"]` using
the current public schema. Targets must already exist in this task and have
the same artifact type. Distinct figure panels and package variants coexist;
their filenames do not imply replacement. The old bytes remain available as
history. An already published corrected file can declare this relationship by
republishing its own ID and unchanged bytes. Read back the current set, then
republish still-valid packages after checking their contents and obtain real
independent review of the resulting current files. Never relabel an erroneous
old figure as another artifact type to hide it from review.

## Research, figure review and completion

Read [research.md](research.md) when deciding whether research/analysis is needed.
For `required`, execute the requested appropriate research/analysis and retain
real methods and results. For `agent_decide`, examine the question, materials and
evidence gaps, explain the decision and perform useful analysis within the saved
scope; this mode is not a default to avoid analysis.
For `materials_only`, public literature learning, venue and reference-figure
reading, source extraction/consistency checks and rendering existing results are
allowed; new statistical outcomes, experiments, models and analysis reruns are
not. Accept supplied results and good figures without requiring every raw array.
Resolve specific contradictions without discarding unrelated valid work.
Use [journal-learning.md](journal-learning.md) for the saved two-set learning
counts, reference-count preference and mechanism-figure choice. Read these values
from the actual saved configuration; do not inject them into task state yourself.

At figure planning, reference reading and final assembly, use the scientific
sections of [figure-story.md](figure-story.md) and
[figure-reference-mapping.md](figure-reference-mapping.md) as scoped by the main
Skill. Actually inspect the reference and current images, panels, typography,
palette, layout, captions and body links. Their old Master/attestation/Runner
schemas are not prerequisites for normal host drawing or Web previews.

Independent review must read the actual current manuscript, citations, figures
and rendered PDF/DOCX in an independent review context, meaning a different
Agent/context from the writer-host; the writer-host itself remains the current
conversation and does not move or restart. Save its actual review
notes under the same task's `paper/` and use the public review entry below;
neither a field nor an empty findings array proves review.
Provide the current `pdf`, `docx`, `tex`, `figure` and `bibliography` artifacts
that actually exist, including standalone figures as well as their appearance
in the PDF. Tell the reviewer the scientific/editorial scope and how to submit
their own findings in the initial handoff. Check uncovered artifact IDs against
the current set; do not request a blanket PASS or author-sign an omitted review.
Correct errors in producing source/method, rerender affected files and re-review.
Do not wait for a legacy completed-package stage to fix known paper errors.

### Independent review CLI entry

Normal P2 MCP processes do not expose `paperspine_submit_review`. The **actual
independent reviewer** explicitly supplies their existing runtime identity:

```text
python scripts/paperspine5_web.py host tools --profile-root "<same-profile>" --trusted-reviewer-id "<actual-reviewer-runtime-id>" --tool paperspine_submit_review
python scripts/paperspine5_web.py host snapshot --profile-root "<same-profile>" --task-id "<same-task-id>"
python scripts/paperspine5_web.py host call --profile-root "<same-profile>" --trusted-reviewer-id "<actual-reviewer-runtime-id>" --task-id "<same-task-id>" --tool paperspine_submit_review --arguments-file "<actual-review-request.json>"
```

For a development runtime replace `--profile-root` with the same explicit
project/user-data/core/events options above. The CLI passes the identity only
to P2's process option `--reviewer-id`; it does not derive it from the writer's
principal, the task, a saved profile or the review JSON. This is the existing
MCP runtime trust mechanism, not a new identity service or proof of independence.
The writer must not enable this option on its own behalf to impersonate a
reviewer. No HTTP reviewer credential or global MCP change is needed for stdio.

Read the actual tool schema and its current command contract. Preserve the
`request` wrapper, current public task version and real findings/artifact
references; do not add identity fields to the request body. Only the reviewer
who performed the review submits it. Tool visibility alone is not a completed
review. If no independent reviewer is available, retain that explicit review
limitation while continuing safe local drafting/corrections; do not invent one.

With the current public 1.1 review schema, publish the actual report as a
`review_packet` artifact, then let its independent reviewer submit
`payload.decision` (`pass` or `block`) and `payload.report_artifact_id` alongside
the actual `reviewed_artifact_ids` and findings. Read the current task after report
publication before submitting the review, because publication changes its version.
Review the exact published file for each listed ID, including each main and
supplement document. If inspecting a working copy, compare its bytes with that
published artifact before assigning the ID; a matching name or page count is not
enough. When the schema accepts `reviewed_hashes`, the reviewer can supply the
hashes of the files actually inspected for a direct mismatch check. This remains
optional and does not create a new user form. Never substitute a different
artifact ID merely because its bytes happen to match.
The product binds the report and reviewed file versions; it does not read the report
or determine scientific merit. Open the review page and check the conclusion,
reviewer, applicable files/version and report link. Historical reviews without
these fields remain honest incomplete records; do not infer a PASS from zero findings
or attach a guessed report. The actual reviewer may supplement their own retained
review after checking that its findings and file versions still apply.

Build actual authorized packages with ordinary host tools, publish them, and use
`paperspine_prepare_delivery` with requested formats. Download published artifacts
through the same Web task. Verify the resulting file at the browser's actual
save destination, using a known browser setting or user-provided path; do not
assume the operating system's default Downloads folder. Check that its bytes
match the published artifact. A download-tool error alone does not prove that
no file was saved; retain the error and check the actual result before retrying
or asking the user to repeat the download. Distinguish actual file delivery from scientific and
submission readiness. On feedback reread the task and feedback file, preserve
the old paper and continue in this task. Unknown author/ethics facts restrict
submission claims, not safe local improvement. No automatic external action.

Publish the current scientific outputs before packaging their exact reviewed
bytes. A later source/figure publication can make an earlier package stale;
rebuild or revalidate the affected package instead of bypassing that protection.
Check the current import constraints before compressing a large workspace:
the current public importer accepts ZIP packages up to 128 MiB. Keep the current
PDF and editable dependencies directly accessible in the outer archive; placing
every current file solely inside another compressed archive is not sufficient.
An inner archive can retain bulky history when permitted. Keep scientific
supplements separate from operational logs and preserve private/local boundaries.
Build from the current deliverable set and its reusable data, sources, dependencies
and feedback. Leave redundant historical binary exports and caches in the original
task instead of copying every revision into every ZIP. State the included scope;
do not silently drop required scientific results, editable assets or selected
supplements to meet a size limit. Preserve the original history. Reuse a valid
package when its required inputs are unchanged.

Before publishing a candidate package, inspect
`host tools --tool paperspine_check_delivery` and call that read-only tool with
`request: {"task_id": "<same-task>", "package_path": "paper/<candidate.zip>",
"required_formats": ["pdf", "tex"]}` using the formats actually requested.
It reuses the import/archive and current-review checks and reports candidate
issues, missing published formats, uncovered current artifact IDs and the sampled
task version. It neither publishes nor reviews anything and never grants readiness.
Fix concrete archive issues; complete outstanding output publication and actual
independent review, then recheck if those inputs changed. If `snapshot_changed`
is true, reread current facts before relying on that diagnostic. Only the normal
`paperspine_prepare_delivery` decides delivery after the real files are ready.

## Explicit legacy read compatibility

Only when diagnosing/recovering an old Kernel-only task, the prior host transport
remains available with `--legacy-runner`:

```text
python scripts/paperspine5_web.py host snapshot --legacy-runner --project-root "<old-core>" --output-dir "<same-user-data>" --task-id "<same-task-id>"
```

It exposes old state; it does not migrate a task or create a replacement. Do not
use its J4–J10 answers as the normal writing/choice workflow. The new public CLI
never silently falls back to this transport on an error.

## Focused task handoff, figure substeps and delivery

Open the task-specific URL returned by the public task/decision in the user's
chosen browser and wait until the actual configuration or choice controls render.
The recent-task list is a recovery aid, not a required extra navigation step.
Keep the task ID/profile and saved choices through any stale-tab recovery.

For a public 1.1 figure decision, optional payload.figure carries figure_id and
label, optional panel_id/panel_label, reference_files/current_files and optional
replaces_decision_id. Reference/current paths use the same discovered file
allowlist as candidate files. Stable figure+panel identity groups revisions;
omitting panel_id means an integrated figure. The new choice cannot replace a
different explicit figure/panel. User feedback remains in the same public
decision/feedback tools and local bridge, with no separate workflow authority.
Do not backfill identities into old task state or guess them from source scopes.

The figure stage displays current figures/panels as fixed two-column rows: this
study on the left, corresponding references on the right. Use explicit figure_id
and panel_id for genuine subfigures; candidate A/B/C is not panel A/B/C. Keep
reference and prebuilt-comparison files distinct. An unresolved mapping must be
shown as missing/shared, never guessed from matching array lengths.

For precise per-file pairing and original-paper links, the host may write optional
`paper/figures/reference-pairs.json` (or the same filename in figure-candidates)
alongside real assets. This descriptive metadata is not task state, a selection or
a quality gate; do not edit workflow JSON. Minimal example (use actual paths):

```json
{"pairs":[{"figure_file":"paper/figures/1A.png","reference_file":"paper/figure-candidates/1A参考图.png","source_pdf":"paper/references/article.pdf","page":6,"figure_label":"Figure 2"}]}
```

Use real local downloaded PDFs under `paper/references/` and verified original
http(s) URLs; omit unavailable fields and use `source_url` only for a real original-paper URL. The page only
opens existing authorized PDFs or user-clicked URLs; it does not fetch references
or expose arbitrary material files. Missing metadata does not block paper work.
Matching names such as `1A.png` / `1A参考图.png` can display as a pair. A unique
paper-prefix/page filename can offer a clearly labelled local-source locator,
not proof that the paper was read. Preserve full integrated figures when separate
panel assets do not exist; do not fabricate panel crops or user approvals.

Publish the manuscript and requested editable version as clearly typed artifacts,
with their actual filenames. Make the shareable paper package distinct from
the full local workspace; its label must say if raw materials are included.
Use existing artifact types according to the current schema. The page promotes
paper outputs and groups supporting files; it does not determine scientific
readiness by file count. Verify PDF and package downloads through a real browser
click and actual saved bytes; a browser handoff message alone is not a disk check.

For delivery_package publication in schema 1.1, declare package_scope as shareable
or local_workspace after inspecting its contents. The page uses this explicit
field for package grouping; filenames do not establish sharing permission. Old
packages with no declaration remain downloadable with an unspecified-scope label.

## Keep execution focused and resumable

Reuse schemas and methods already read while unchanged. Use host snapshot
--summary for a quick task check. After one task read establishes scope and
method selection, a long shipped resource can be read with
host methods --local --task-id <same-task> --resource <exact-path> --format text
--start-line 1 --max-lines 100
and follow the returned next line with --expect-sha256 <returned-source-hash>.
The text frame includes the source range, character count and END marker. Require
the complete frame before treating that page as received; a missing END means
retry a smaller --max-chars page. A page at source EOF is not proof of having
read earlier pages. Read all relevant source sections before applying them;
if a single line cannot fit, use the reported local path to read it completely.
Save large extraction,
analysis or review output as files and return paths plus the relevant findings,
rather than full repeated snapshots. A short method index never replaces reading
the applicable method. `--local` reads only the installed method without MCP or
a task read; task ID is context only and no configuration, current version or
authority is inferred. Ordinary file tools can read its indicated local source.
Task-based selection without `--local` retains its current snapshot behavior.

During user choices, use the attached `host wait` above with the last observed
version; reread the required choice after an event. Continue independent
work concurrently where practical. Keep timeout distinct from saved input and
read a saved value promptly; no periodic transcript reread or artificial polling
receipt is needed. At resumption retain the current task, source files, pending
choice and next action so the next context need not replay the full history.

## Apply the saved work type

Read `configuration.workflow` before choosing the next scientific action. The
journey below provides reusable steps, not a requirement to restart every task
at intake or to produce a new manuscript for a review-only request.

| Saved workflow | Actual work and expected result |
|---|---|
| `build_from_materials` | Build the argument and manuscript from granted materials and justified research; use the applicable journey steps below. |
| `rewrite_existing` | Read the existing manuscript's argument, evidence and useful prose first. Revise its actual weaknesses using the selected target and learning papers; preserve valid results and explain substantive changes. |
| `audit` | Check the supplied paper's claims, numbers, citations, figures and files against their sources. Deliver located findings and corrections needed; do not silently replace the paper with a rewrite. |
| `review` | Have an independent reviewer assess the current paper's contribution, methods, argument, venue fit and rendered figures/files. Deliver the actual review; do not manufacture a new draft or author choice to complete it. |
| `revise` | Read the current feedback and retained prior version. Address each distinct issue with a supported change or reasoned response, identify the changed passage/figure, regenerate affected outputs and review them. Preserve unaffected valid work. |
| `transfer` | Compare the new target's current article requirements and learning PDFs with the existing paper. Adapt framing, structure, citation style, layout and package as needed; retain valid science and usable same-field learning. |

Reuse the same task's valid configuration, contribution and figure selections.
Request a new choice only when the user requests one or an actual proposed change
needs a decision; a different workflow label alone does not invalidate them.
For revision, keep the original comments and a concise issue-to-change/response
map in the existing notes. Do not lose an issue in a summary or claim an experiment
was performed because a reviewer requested it. Apply the saved research scope to
every mode. A reviewer's suggestion is not authorization for new analyses.

Use [assertive scientific writing](assertive-scientific-writing.md)
for `author_voice_restoration`, and [manuscript assembly](manuscript-format.md)
for `output_language`, including multilingual deliverables. Apply only the
requested transformations; optional settings must affect the actual work, not
merely remain saved in Web. Missing historical Runner files do not change the
selected workflow or require the old receipt chains.
