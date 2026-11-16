# PaperSpine5 shared host runtime

`paperspine5_runtime.py` is the host execution bridge. It imports the canonical
Product Kernel, ProductRunner 0.2, and the legacy coordinator facade from
`03_联合开发/src`, exposes them through MCP stdio, and writes HostBridge
0.4.0 JSON envelopes (0.2.0 and 0.3.0 are compatibility protocols).

The runtime never contains a second business implementation of the paper or
figure engines. Installed host adapters use `PAPERSPINE5_PROJECT_ROOT` or
`config/local-project.json`; the standalone `paper-spine` distribution embeds
the same allowlisted core under `_paperspine5/` and resolves it without a plugin.

The 31 tools add no-job create, read-only legacy import, task list/get,
revisioned non-Runner command submission, and a token/CSRF-bound Web-first
product workspace with status/stop/reuse. Seven typed ProductRunner tools expose
snapshot/bootstrap/add-materials/J3 answer/academic-stage answer/host-materialized
answer/resume through
the registered facade; generic `runner.*` envelopes are rejected. J4–J11 answers
carry actual JSON evidence in `payload.input_artifacts`, never a trusted map.
Verified artifact views and a fail-closed typed readiness projection remain
Kernel-owned.
All official Product mutations use a server-derived runtime/task writer owner;
MCP, HostBridge, and Web clients cannot select or override `writer_id`. Graceful
runtime close releases owned leases, while crashed owners remain fenced by TTL.
The command-line `bridge` mode is a one-request process: after its JSON response
is flushed, `main()` closes that process's cached Kernel/Runner and releases only
the task leases recorded for its private runtime owner. A second one-shot bridge
process can therefore continue the task immediately, while a lease held by a
still-running foreign process remains `RUNNER_WRITER_LEASE_HELD` and is never
stolen during cleanup.
Older job-path tools are explicitly legacy;
schema 1.1 Product Kernel tasks cannot be mutated through them. Current suite
identity is `0.4.0-alpha.1-dev / development / local-dev-unverified`; this is an
internal development source whose ProductRunner 0.2 exposes cumulative,
domain-neutral J1–J11 collaboration stages. Domain/subfield/venue/track content
comes from runtime research Agents; the runtime carries only orchestration and
authority gates. `target_package_ready` is local-only and external action stays
unauthorized. W8 has not run, so maturity and P0 remain blocked.

When a persisted task is bound to an installed predecessor build, the runtime
does not relax ProductRunner's normal exact-build check. It lazily loads the
installed suite verifier only for that cross-build snapshot/resume request and
resolves authority across the independent Plugin and Standalone Skill updater
control roots (`PAPERSPINE5_PLUGIN_UPDATE_CONTROL_ROOT` /
`PAPERSPINE5_SKILL_UPDATE_CONTROL_ROOT`, otherwise their user update roots).
The environment can only relocate each typed control root; it cannot select or
weaken an authority. A successor migration is exposed only when exactly one
surface fully binds the requested target and current `project_root`. Plugin
requires its committed activation/cache chain; Skill requires its committed
state/history/receipt chain, projection tree, exact `installed-suite.json`
pointer, controlled predecessor suites, and current managed-suite bytes. Zero
or multiple exact matches fail closed.
The explicit resume then uses the Kernel's sealed same-revision successor
transaction; it preserves the existing task/run/material snapshot/revision,
stage, and artifact ledger and never authorizes an external action. Normal
same-build fixtures and requests do not need release tooling or updater state.

At J10/J11 the existing `paperspine5_runner_answer_host_materialized_stage`
accepts the exact `answer.payload={"requested_scope":"local_delivery"}` and
`review=null`. Its normal task/revision/issue/resume-token/command envelope is
unchanged. Only this exact compact shape generates the original J10 inputs;
mixed, empty or malformed explicit payloads are not repaired into evidence.
The host reads accepted E6 claim scope, current J8 head/surfaces, J9 closure and
typed target findings. Unknown/author-only facts stay unknown; an accepted
narrow review (including exact-byte native page-review reuse) is not a new
scientific, citation, journal-compliance or visual review. The original
publication/readiness compilers remain the authority.

Before any package write, the host verifies current source/PDF/DOCX/page bytes,
paths, the complete explicit legacy request when used, and the dependency
inventory. It recursively follows static active TeX dependencies, including
local `.cls`, `.sty`, `.bst` and `.bib`; only absent simple system package/style
names are left to the TeX installation. Relative `../shared` paths may remain
inside the task workspace and retain their archive layout. Dynamic/unbraced,
missing, ambiguous, escaping or symlink dependencies fail closed. This is not
an arbitrary TeX/Python-project interpreter. Accepted final-mapping editable
sources and explicitly referenced registered editable/preview auxiliaries are
included with their immutable relative paths; unrelated source/material folders
are never scanned. The host creates a deterministic ZIP, verifies every member
and CRC, and only then marks the local package manifest PASS and registers a
`paperspine5.local-package-archive` descriptor as `bundle_archive`. Its ZIP byte
hash differs from the descriptor's canonical Runner hash. Member roles add
`editable-figure-source` and `editable-figure-dependency`; all existing descriptor
fields remain unchanged. Generation revision may precede its current accepted
Runner pointer revision. A same-stage
retry reuses an already verified archive while its manuscript and dependency
bytes are unchanged, so the package base artifact does not drift merely because
Runner created a new blocked revision. Missing, changed, escaping, or non-file
package inputs fail closed. The package remains local-only and does not authorize
submission, upload, or sending.

Implementation/verification: `local_package_files.py`,
`test_local_package_preparation.py`, and
`03_联合开发/LOCAL_PACKAGE_PREPARATION.md`. Current-host discovery exposes the
compact branch in the existing tool schema; it adds no new tool or credentials.

Quick checks:

```powershell
python 06_插件化/runtime/paperspine5_runtime.py health
python 06_插件化/runtime/paperspine5_runtime.py bridge < request.json
python 06_插件化/runtime/paperspine5_runtime.py web --project-root . --user-data-root <isolated-output-root> --ready-file <isolated-output-root>/.paperspine5-web/workspace.json
```

### Current-host CLI (canonical Skill, no MCP installation required)

The installed canonical `paper-spine/scripts/paperspine5_web.py` also exposes
`host tools`, `host snapshot`, and `host call`. These commands use the existing
runtime MCP dispatcher and public tool schemas, not a second academic API.
Use the same existing output/user-data root and task ID shown by Product Web:

```text
python -B <paper-spine>/scripts/paperspine5_web.py host tools --tool paperspine5_runner_answer_academic_stage
python -B <paper-spine>/scripts/paperspine5_web.py host snapshot --output-dir <same-user-data-root> --task-id <actual-task-id>
python -B <paper-spine>/scripts/paperspine5_web.py host call --output-dir <same-user-data-root> --task-id <actual-task-id> --tool <existing-paperspine5_runner-tool> --arguments-file <agent-arguments.json>
```

`host tools` without `--tool` returns the exact runtime tool inventory, including
`paperspine5_runner_answer_host_materialized_stage`. Development checks may add
`--project-root <source-suite>`; normal installed use resolves the verified suite
pointer. `host snapshot` returns the real Runner `snapshot` and existing Kernel
`task` record (run/workspace paths), rejecting a task/revision, successor-link or
artifact-pointer change between these reads. These are optimistic sequential
reads, not a new atomic snapshot contract: Runner has no `active_run_id` field
to compare; the task record supplies that anchor. The snapshot build is the
executing runtime's build, while a pending-successor task manifest may still
identify its predecessor. That legitimate mismatch is not hidden or rewritten.
The snapshot includes the current build, private issue/input schema,
run-relative artifact pointers and opaque **product issue** resume token. These are Agent
inputs, not user-facing form content or Codex login credentials. The UI handoff
is only a readable continuation request with task/root context; copying it does
not run a command or advance the task.
Host-command JSON uses ASCII escapes on stdout/stderr so Windows PowerShell
capture preserves Chinese and non-BMP paths; JSON decoding restores exact values.

`host call` accepts only same-task `paperspine5_runner_*` tools. The JSON file
contains the existing MCP tool arguments; `--arguments-file -` instead reads
private stdin. The adapter supplies only the explicit task/root binding, rejects
conflicting bindings, and forwards command ID, expected revision, issue token,
answer, and separate review unchanged. It never synthesizes a decision, revision,
review, author fact, external authorization, or academic evidence. J9 `block`
and J10 `review=null` retain their runtime meanings. J5 user confirmation remains
Web-owned. Each invocation starts a Python transport process (not a Codex child),
reads no Web session receipt or login credential, and releases only its owned
runtime lease at EOF. It does not require Web to be running. A transport failure
is not evidence of non-commit: read the same task/command state before deciding
on any retry. This CLI never retries automatically.

The existing runtime's default actor includes its process-owned writer identity.
Therefore an omitted-actor command repeated from a different process can return
an idempotency conflict rather than replay success. The adapter does not invent
a stable actor to conceal that distinction. A caller-supplied genuine stable
actor retains ordinary replay semantics; either way no blind retry is performed.
Exit zero means the runtime returned a non-error response, not that an academic
stage passed: a committed blocked result must still be read as blocked.

`01_PaperSpine4/tests/test_current_host_cli.py` runs real disposable Kernel/Runner
CLI processes for schema discovery, configuration, J4 acceptance, explicit-actor idempotency,
and stale/token/writer/external/task/root rejection. Host review forwarding is
separately labeled as a synthetic transport test, not an independent page review
or an installed paper completion claim.

`web` is the persistent standalone service mode. It binds only to loopback,
creates a random session plus CSRF token, writes a private local ready receipt,
and serves the same Product Kernel/Runner UI used by MCP hosts. The user-facing
launcher starts this mode with `CREATE_NO_WINDOW`/`pythonw` on Windows and never
falls back to a terminal wizard. When no explicit data root is supplied, the
runtime probes the platform application-data location and fails with
`USER_DATA_ROOT_UNWRITABLE` if no writable root exists instead of silently using
an invalid default.

The canonical J4–J11 path is current-host orchestration: the host that is already
running canonical `paper-spine` performs the open academic stage and submits a
task/revision/issue/token-bound answer through
`paperspine5_runner_answer_academic_stage`. Product Web reads and resumes that
same Runner task, while flat output is a read-only projection of its persisted
record. A valid J4 host answer is accepted only when the academic orchestrator
materializes the typed direction/target receipts and advances the same task to
`awaiting_contribution`; `/agent/start` is not required for this path.

For J8, J9, and J10, an already authenticated current host may instead call
`paperspine5_runner_answer_host_materialized_stage`. This explicit route starts
no nested Codex process and never reads or copies login credentials. It checks
the sole current issue/token/revision/stage, strips Runner-reserved assertions,
re-reads task-contained manuscript and page bytes through the same Product Web
materializers, and submits through the same ProductRunner CAS facade. J8 and J9
require the exact public host-independent-review contract and reject a stale,
extra-field, or mismatched review without mutation. J8 rejects a blocked review;
J9 persists a genuine block as `REVISION_REQUIRED` and returns to J8. J10 requires
`review=null`. The host derives producer/reviewer attestations from the stable
idempotency command and always forces external action authorization to false.

J9/J10 resolve source/PDF/Word from the **persisted** J8
`manuscript_revision.artifacts[role]`, not fixed input names supplied by a client.
Versioned IDs and both `paperspine5.local-file-artifact` and
`paperspine5.local-file-byte-evidence` are supported. Resolution checks the
current head's self-hash/task/revision, exact canonical bundle (including the
existing deterministic legacy rebind), typed revision and role ID/hash,
registered pointer bytes, manifest identity/type/media, actual file bytes,
and `source_bytes_sha256` where present. The old fixed IDs are allowed only for
legacy cumulative inputs without a typed revision and only with exact current
head bindings; an invalid typed revision never falls back to aliases.
J10 package entries and source-dependent predicates retain the resolved IDs;
J9 review scopes and re-review diffs retain the actual role identities. Neither
path adds alias artifacts, changes old J8 evidence, or changes review decisions.
After a blocked J10 attempt advances only the task revision, its exact accepted
head pointer may still name an earlier revision. At `awaiting_package` only,
the Host accepts that state-selected retained pointer, deterministically rebinds
the cumulative candidate back to it, and requires exact accepted bundle and
role/manifest hashes before verifying every file/page byte. It does not treat
an arbitrary old PASS as current. The Runner independently resolves retained J7
and head pointers for figure projection and sealed-successor mapping revalidation.
The original head/review bytes and subjects remain unchanged until normal later
acceptance. `test_local_package_recovery.py` covers same-build blocked retry and
blocked retry through formal same-task successor, mapping revalidation and real
HTTP artifact/download adapters; unknown readiness still prevents downloading.
See `test_canonical_role_resolution.py` for synthetic on-disk positive and
fail-closed J9/J10 coverage; these tests do not establish live product readiness.

At J7 `create`, JSON input artifacts are evidence manifests, not image bytes.
The host must first place each PNG/JPEG/SVG below the current task's
`run_root/runner/.staging/figure-candidates/` subtree and call
`paperspine5_runner_register_figure_candidate` (HostBridge
`runner_register_figure_candidate`) with only the returned task binding's
relative staged path, figure/candidate IDs, expected SHA-256 and size. The
runtime injects writer ownership; ProductRunner verifies containment,
link/reparse safety, media bytes, current build/task/revision/J7 and material
snapshot, then derives the CAS identity and receipt without advancing the
stage. The J7 answer uses the returned manifest and candidate binding plus a
real independent comparison. A JSON wrapper carrying `primary_display` or any
other path is not a candidate and is rejected before the transition.
The Product page may receive historical and current ledger views together. For
the same opaque artifact ID it deterministically keeps a fresh previewable view
over a stale staged view regardless of response order; a stale fallback may be
replaced by a later fresh view but never the reverse. The content endpoint still
performs the authoritative same-session/current-revision/path/hash/media checks.
Selection/highlight keeps using the logical candidate SHA stored in figure
intent. Authenticated byte fetch instead compares the response ETag with the
chosen fresh receipt's own SHA-256; a candidate input-manifest SHA is not a
binary content hash. Missing/invalid receipt hashes and mismatched ETags remain
fail-closed UI errors.

At J8, `paperspine5_runner_register_final_mapping` (HostBridge
`runner_register_final_mapping`) passes the dedicated closed registration
contract to ProductRunner; it does not accept an authority or a caller-created
consumption wrapper. The Runner reopens the frozen approved plan, current J7
winner and independent comparison, registered image bytes, and staged bounded
auxiliaries. Every selected figure needs a current-build validated mapping
before a new Runner J8 transition. A formal successor requires re-registration
and fresh validation without rewriting the historical plan. At J9/J10 the same
API is restricted to sealed, already-consumed maps: no first registration,
changed science or changed auxiliary bytes. The current-build outer proof keeps
the canonical head's original scientific consumption digest. New plans consume
the canonical PaperSpine Skill method, not a cross-project table. Comparison HTML
is opaque evidence only; Product Web uses verified images and a safe DOM
projection, never executable user HTML. See
[`FIGURE_FINAL_MAPPING.md`](../../03_联合开发/FIGURE_FINAL_MAPPING.md).

J5 is the intentional exception to host-owned completion. The host/Web Agent
submits only evidence-bound `contribution-candidate-preparation`; it cannot send
user decisions, an author identity, or `confirmed_at`. Runner persists a
`contribution.confirmation.required` issue. The ordinary loopback Product Web
shows the candidates and its authenticated session identity, then server-binds
that identity and the confirmation timestamp in one atomic transition to J6.
There is no MCP confirmation tool. Invalid identity/provenance, wrong payload
envelopes, stale confirmations, and browser interruption do not advance the
Runner or freeze new academic base inputs.

`web_agent_runtime.py` remains an optional local Web collaboration fallback.
The browser can start one task/revision/issue-bound job or answer one displayed
natural-language question. The worker runs hidden, reads the installed
standalone `paper-spine` Skill explicitly, disables plugins and MCP servers, and
returns a schema-bound candidate. Only the host adapter may submit that
candidate through the existing ProductRunner CAS facade. The worker never owns
business state, never grants external action, and fails closed on binding
mismatch, timeout, malformed output, or Runner rejection. Its auditable local
job records live below the configured user-data root in
`.paperspine5-web-agent/jobs/`.

Agent material transport is reference-only. The host context exposes every
binary/image as `source_id` plus path, SHA-256, size, and semantic role; binary
bytes, data URLs, and base64 are forbidden in prompts, stdout, JSON, and stage
payloads. This preserves the complete figure inventory without serializing
images into the Agent transcript. Producer/reviewer logs have a 2 MiB hard
budget and structured result files have a 4 MiB hard budget. A limit or the
known rollout JSON truncation marker stops that child once, performs no
transport retry or Runner submission, and writes a typed
`paperspine5.web-agent-resource-blocker` receipt. Product Web renders that
receipt as an unchanged-revision blocker rather than a generic success or a
submitted academic receipt.

Child-profile authentication uses an empty task-local `CODEX_HOME` plus the OS
credential store selected explicitly with
`cli_auth_credentials_store="keyring"`. This keeps authentication outside the
model-readable workspace while `--ephemeral`, task-local SQLite,
`--ignore-user-config`, disabled plugins/MCP, and no history preserve process
and rollout isolation. A user whose current CLI login exists only in
`~/.codex/auth.json` must perform a one-time OS-keyring login before using the
optional nested fallback:

```powershell
codex login -c 'cli_auth_credentials_store="keyring"'
```

The runtime never copies, parses, links, or falls back to that file. Child-profile
authentication has a separate typed failure. An exact CLI
response containing both `401 Unauthorized` and the missing bearer/basic-auth
diagnostic stops after the first host invocation and writes
`paperspine5.web-agent-runtime-blocker` with
`code=AGENT_PROFILE_ISOLATION_UNAVAILABLE`. The receipt states that no parent
profile fallback, retry, or Runner submission occurred. This is a platform
blocker, not manuscript or delivery completion.

If Runner commits a blocked stage result, the public job status carries
`committed_blocked=true`; the Web UI reports that the gate still needs repair
instead of calling it passed. When that committed block creates a new revision
at the same stage, the host carries forward only the user's explicit answer and
its question context. It never reuses the old producer candidate or review
across revisions.

A producer result whose outer schema is valid but whose nested
`stage_payload_json` is malformed is treated as a transport-format defect, not a
new user decision. The host runs one task/revision/issue-bound format-repair
process without repeating research or mutating Runner state. A retry of a job
created by an older runtime resumes directly from that malformed candidate.
Ambiguous recovery still fails closed.

The host, not the producer, owns independent review execution. J4, J6, J8,
and J9 producer candidates are followed by a separate sequential Codex
reviewer process. For J9 the producer supplies only task-relative rendered-page
paths. Before attaching those pages, the host reopens the Runner-owned current
manuscript-head and source/PDF/DOCX base-input pointers, verifies pointer bytes,
manifest hashes, and actual file bytes, and removes the transport metadata
before submission. Only the separate reviewer can determine the
`paperspine5.publication-review` result: pass or `REVISION_REQUIRED` with exact
objections. A producer cannot self-sign or claim objection closure.

At J6 the material/external source hashes remain evidence-bearing producer
inputs, while contribution hashes, authority-source hashes, and graph snapshots
are orchestrator-derived bindings. The producer uses zero sentinels for those
derived fields; the host binds them to current Runner authority before the
independent reviewer evaluates semantics. The reviewer therefore does not
reject a candidate solely because an orchestrator-derived field was still a
sentinel in the isolated producer output.

At J10 the readiness-obligation manifest hash is likewise host-derived. The
producer supplies the validated manifest body with a zero sentinel, and the
host canonicalizes and binds its SHA-256 before ProductRunner verification.
This avoids serializer-order dependence without relaxing the exact five-tier
readiness and package checks. Public Web job failures expose the specific
Runner/host error in the UI so a repairable gate defect is not reduced to a
generic failure banner.

For `manuscript` and `local_delivery`, J10/J11 completion is scoped: a valid
canonical manuscript, independent review, non-author target adaptation,
page-complete PDF/Word, and local package can set manuscript/delivery readiness
and requested-scope completion even while author-only facts stay open. Every
hard local-delivery target obligation remains mapped and
`target_compliance_valid=true`. J4 types every official hard rule; the host
derives stable obligation IDs, J9's independent result covers every local rule,
and the host binds each finding to the current target and PDF receipt before
Runner submission. J10 overwrites any producer-supplied ledger with the same
host-derived ledger. An unsatisfied finding may leave the manuscript layer true
but always keeps delivery/local scope false. Only an evidence-bound typed author-only
obligation may remain above the local layer. Those blockers remain attached to
submission/external layers; submission readiness and external authorization
stay false. `submission_package` still requires the real author facts and their
remaining target mappings.

The J8 host independently opens the DOCX ZIP and validates its main-document
image relationships. A figure-active Word surface must provide a typed
one-to-one transport from the selected canonical source artifacts to visible
`word/media/*.png` objects, with source and output hashes, Word-only conversion
scope, and the same page-render evidence used by Word QA. Canonical PDF figures
remain byte-preserved, but any embedded `word/media/*.pdf` blocks the
image-complete/delivery gate because it can render as a blank frame in Microsoft
Word. The resulting `paperspine5.word-figure-media-receipt/1.0` is host-derived
and rechecked at package compilation; a producer assertion alone cannot pass it.

J8 also rejects a source file whose command lines begin with doubled LaTeX
slashes (for example `\\\\documentclass`). This catches serialized/raw TeX
being handed to the manuscript surface before it can be wrapped in a PDF
fallback; the producer must regenerate the UTF-8 source and real rendered PDF
through the Skill build path. Coverage is exercised by
`test_web_agent_runtime.py::test_j8_rejects_doubled_latex_command_slashes`.
It also requires every figure environment to have a label and an independent
prose reference (`\\ref`, `\\figrefwhole`, or `\\figpanelref`); detached figures
are rejected before review. The regression suite covers this guard and now
passes 40 tests.

J10 resolves only active TeX dependencies after stripping unescaped `%`
comments. It never creates a compatibility bibliography for a commented
command. In a `finally` boundary it removes only task-local allowlisted
`soffice_profile_*`/`soffice_convert_*` scratch roots and then requires the
workspace to be fully enumerable; unrelated or unreadable residue fails closed.

Each producer and reviewer command uses `--ephemeral`, `--ignore-user-config`,
`--strict-config`, `history.persistence="none"`, and a task-local empty
`CODEX_HOME` at `<task-workspace>/.paperspine5-agent-state/codex-home`;
`sqlite_home` remains `<task-workspace>/.paperspine5-agent-state/sqlite`. The
runtime explicitly selects OS-keyring authentication and never copies an
`auth.json` credential into that boundary. A file-only login therefore returns
the typed runtime blocker and the UI asks for the one-time keyring login; this is
not retried automatically. The earlier parent-`CODEX_HOME` probe reproduced
historical `data:image`/EOF output, hit the 2 MiB cap, produced no schema result,
and observed parent session changes, so parent-profile fallback remains
forbidden. A successful nested-Web E2E claim requires a real keyring-authenticated
producer and reviewer run; source/config tests alone do not grant it. The
current host may still answer the same open Runner issue through the canonical
host route.

At J7 the Web Agent may use a material-ledger file SHA-256 only as a transport
assertion. The host reopens the exact ledger object, registers the immutable
figure input, binds every asset to the current issue revision, and atomically
rewrites `current_asset` / `candidate_assets`, the comparison's complete
`reviewed_asset_hashes`, and `selected_sha256` to the Runner canonical input
hashes. Host-only `material_coverage` is consumed before submission, and an
empty `candidate_assets` member is removed for `keep`, so the resulting answer
contains only the exact public J7 fields. Assertion drift, incomplete comparison
scope, or an ambiguous winner fails before the Runner mutation.

## Host-owned figure correction review

The production runtime injects the same-bundle FigMirror correction executor
into ProductRunner and injects `ProductWebAgentRuntime.review_figure_correction`
as the independent reviewer. The callback runs only after PaperSpine has an
output artifact, pixel/invariant evidence, and a target-size legibility receipt.
It renders and attaches the exact source/output images to a separate ephemeral,
no-user-config reviewer process, then validates task, revision, material,
operation, source/overlay/output, pixel/invariant, and legibility hashes before
minting the host-owned review. Caller-forged, same-actor, stale, blocked, or
hash-drifted results fail without advancing Runner state.

Reviewer scratch is created under the owning Runner command staging subtree and
is removed deterministically on success and failure; the callback never retains
image/context/log/result scratch as an audit substitute. Only the signed typed
review, PaperSpine correction/legibility receipts, and final CAS artifact remain.
Product tests prove the callback and J7→J8 bindings in disposable tasks. They do
not establish fresh installed dual-entry readiness.
