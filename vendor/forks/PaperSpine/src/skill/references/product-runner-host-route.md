# Canonical ProductRunner Host Route

This is the normal orchestration route for both a natural-language request such
as "use these materials to make my paper" and an explicit `$paper-spine`
invocation. The current host is the stage worker. Do not require a nested Codex
process or Product Web `/agent/start` call before the paper can advance.

## Installed host transport when MCP tools are not exposed

Use the installed Skill's existing launcher; do not import private helpers or
write a case-specific HTTP/MCP bridge. Paths below are relative to the installed
Skill. `<output-root>` is the existing task's output/user-data root from the
frontend continuation request, **not** the material folder or a guessed legacy
directory. `<task-id>` is the same persisted task selected in that frontend.

```bash
python scripts/paperspine5_web.py host snapshot --profile-root "<existing-profile>" --task-id "<task-id>"
python scripts/paperspine5_web.py host tools --profile-root "<existing-profile>"
python scripts/paperspine5_web.py host call --profile-root "<existing-profile>" --tool "<actual-public-tool>" --arguments-file "<private-arguments.json>"
```

Binding-spec-backed r12/r13 runs still use the same host-materialized route. When the task root contains a real canonical binding spec file, derive the canonical bundle with `compile_canonical_artifacts(project_root, binding_spec_path, ...)` first, then stage the resulting host answer with `host_canonical_files.binding_spec_path` pointing at that real file. Do not substitute the schema file for the binding spec, and do not handwrite canonical bundle JSON.

Select the existing `paperspine5_runner_*` tool required by the current issue;
the example tool is not a shortcut around earlier stages. Read its actual schema
with `host tools --tool <name>` and the snapshot's bound current-stage packet.
The command returns the Runner projection under `snapshot` and the existing
Kernel record under `task`; resolve run-relative input pointers against that
record's actual `run_root`, not a constructed directory. A generic next action
does not replace the stage playbook: for J9 use the host-materialized review and
revision route below, including genuine independent review and its objections.
Prepare arguments from genuine work and the current revision/issue/token. The
CLI binds task/output identity but does not fill scientific answers, reviews,
command IDs or expected revisions. Keep raw schemas, arguments and credentials
off ordinary user-facing pages. `--arguments-file -` accepts private stdin.

This transport calls the bundled runtime's MCP dispatcher in a Python process;
it does not start a Codex child, copy login credentials, or need a Web session.
The same Runner owns state, validation and review/revision transitions. After
a rejected or uncertain call, inspect the same task's state before retrying;
never assume a lost reply means no commit or repeat a mutation blindly.

The current public fallback supports opening or resuming a task through the existing profile. When no task exists, read the actual public tool schema and use paperspine_open_task; otherwise resume the same task ID. Launch the same profile's Web for configuration and choices, then read back the saved values. Web does not start scientific work, and continuing a paper does not require a new Codex login. Use the explicit legacy route only when maintaining a historical Runner task.

## One identity, one task

1. Call `paperspine5_health` once and retain the reported suite build identity.
   Never substitute a component, cached Skill, or flat-output version.
2. Call `paperspine5_list_tasks`. Resume the user-selected/current matching task
   when one exists; otherwise call `paperspine5_create_task` once with the exact
   user-authorized read-only material roots and a unique `command_id`.
3. Keep the same `task_id`, same suite build identity, and same material
   snapshot for every subsequent host tool call. Read the material ledger and
   `snapshot_sha256` from `paperspine5_runner_snapshot`; never rescan materials
   into an unbound second workflow.
4. Call `paperspine5_open_product_workspace` with that same `task_id`. Product
   Web is a view and resume surface for the same task, not a separate writer.
   Its task/build/material identity must agree with the host snapshot.

Natural-language and explicit `$paper-spine` entries normalize to these exact
steps. They must not select different Skills, builds, task stores, Web
workspaces, or material snapshots.

## Bootstrap and typed stage loop

### Public bootstrap and J3 input contracts

`actor` is optional on every public `paperspine5_runner_*` MCP tool. For an
ordinary guided call, omit it and let the runtime derive its internal system
actor. If a host supplies `actor`, the object requires both `actor_id` (the
safe identifier pattern `^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$`) and `surface`,
whose exact values are `codex`, `claude-code`, `dsh`, `standalone-skill`,
`web`, `mcp`, `cli`, or `system`. `authority_kind` is needed only for
`delegated_local_test`; it must be `authenticated_local_user_session` or
`host_user_message` and must match the grant's `granting_actor` exactly.

Every persisted `configuration.required` issue now carries
`answer_tool=paperspine5_runner_answer_issue`, the complete `answer_schema`,
and a full guided `answer_example`. The MCP tool's `answer` schema and Product
Web's internal form contract are byte-for-structure equal to that schema.
These are private host/API fields, not ordinary user-facing page content.
Use them directly as the stage worker; do not search Skill/plugin
implementation files or probe server errors for enum/key discovery. A complete
guided answer is:

```json
{
  "workflow": "build_from_materials",
  "scene": "journal",
  "target": {"status": "unknown", "name": null},
  "output_language": "en",
  "author_voice_restoration": "off",
  "requested_scope": "local_delivery",
  "interaction": {"mode": "guided", "grant": null},
  "deliverables": ["latex", "pdf", "word"],
  "network_policy": {
    "allow_network": false,
    "allow_external_upload": false
  },
  "privacy": {"allow_external_processing": false},
  "budget": {
    "time_minutes": null,
    "token_limit": null,
    "cost_limit": null
  }
}
```

The exact enums are visible in `answer_schema`: workflows are
`build_from_materials|rewrite_existing|audit|review|revise|transfer`; scenes
are `journal|conference|report|review|competition|other`; output languages are
`en|zh|multilingual|other`; deliverables are the non-empty unique subset of
`latex|pdf|word`; author-voice modes are `off|standard|strict`; scopes are
`manuscript|local_delivery|submission_package`; and interaction is `guided` or
`delegated_local_test`. The external-upload key is nested exactly at
`network_policy.allow_external_upload` and must be `false`. J3 has no top-level
`external_action_authorized` input; the resulting snapshot/run contract always
keeps it false.

The example's offline setting is not a universal research policy. Bind the
actual user's network choice: authorized public-literature research does not
authorize uploading private materials, and an explicit offline request remains
binding. Do not silently copy a closed-corpus case's policy into a new task.

Every `academic.input.required` issue uses the same pattern:
`answer_tool=paperspine5_runner_answer_academic_stage`, a schema specialized
with `const` bindings for the current `task_id`, `issue_id`, revision and
stage, a schema-valid shape `answer_example`, an example note, and
`external_action_authorized=false`. The generic MCP academic-answer schema is
the unspecialized projection of that same contract authority. Product Web
uses it internally and refuses to submit if any current binding or the
external-action lock is absent. Render user-readable forms and evidence, never
the raw schema, example JSON, session identifiers, or identity attestations.
Do not inspect an installed Skill/runtime directory for J4-J11
field discovery.

At J4, `payload.sources[].content_sha256` is not a hash of a URL or a prose
summary. For source ID `S`, supply the actual frozen JSON content object at
`payload.input_artifacts["source:S"]` (unless that exact artifact is already a
current Runner base input), canonicalize it as sorted-key compact UTF-8 JSON
with exactly one trailing newline, and put its SHA-256 in the source receipt.

Identity provenance uses a deliberately different namespace. An identity has
exactly these six public fields: `principal_id`, `session_id`, `run_id`,
`independence_group`, `provenance_sha256`, and `attestation_input_id`.
`provenance_sha256` is SHA-256 of sorted-key compact UTF-8 JSON containing only
the first four immutable fields, with **no trailing newline**. The complete
six-field identity object must also be present, equal after canonical JSON
normalization, at `payload.input_artifacts[attestation_input_id]` (or already
be a current immutable base input). Producer and independent reviewer may not
share any of the four immutable fields. The J4 schema and bound example expose
the exact preimage, newline distinction, full attestation shape, and
independence rule. Identity/conflict validation failures are transaction
failures: revision, open issue, cumulative inputs, and academic base artifacts
remain unchanged, so a corrected answer may retry the same issue with a new
command ID.

Ordinary Product Web has no raw academic JSON editor. The current host submits
the typed envelope through its private tool/API contract; it does not ask the
researcher to supply machine fields. A nested envelope inside `payload` or
wrong identity provenance is rejected without advancing revision or freezing
base inputs.

1. Read `paperspine5_runner_snapshot`. If it is uninitialized, call
   `paperspine5_runner_bootstrap` with the current revision and one unique
   `command_id`; omit `actor` for an ordinary guided call.
2. Answer a persisted configuration issue with
   `paperspine5_runner_answer_issue`; then call `paperspine5_runner_resume` to
   open J4. Never call generic resume while an issue is still awaiting an
   answer.
   `guided` is the default. `delegated_local_test` is accepted only through the
   exact typed, user-origin grant in `interaction-policy.md`; review rigor is
   not permission.
3. For every `academic.input.required` issue from J4 through J11, perform the
   work for exactly the current stage using its PaperSpine playbook and the
   Runner-bound materials/artifacts. Read the issue's bound `answer_schema`
   and use `answer_example` only as a shape (replace evidence and recompute all
   content/provenance hashes). Build one complete
   `paperspine5.academic-stage-answer/1.0` object containing:

   - a unique `answer_id`;
   - the current `task_id`, `expected_revision`, `stage`, and `issue_id`;
   - the stage payload only, without host-owned trust fields;
   - `external_action_authorized=false`.

4. Call `paperspine5_runner_answer_academic_stage` with the same task and issue,
   the opaque `resume_token` from the current snapshot, the complete answer,
   current `expected_revision`, actor context, and a unique `command_id`.
   Never guess or persist a token outside this call, and never use a token as
   evidence of user authorization.
5. Reload the Runner snapshot after every answer. Continue only from the
   returned revision/stage. A CAS conflict requires a fresh snapshot, not an
   overwrite or a second task.

### J5 two-phase confirmation

At `awaiting_contribution`, the current host may submit only
`paperspine5.contribution-candidate-preparation/1.0`: the three current
authority bindings plus evidence-bounded candidate objects. It must not supply
`decisions`, `author_identity`, `confirmed_at`, or a blocker override. A valid
preparation remains at J5 and creates a persisted
`contribution.confirmation.required` issue whose candidates are visible in the
ordinary Product Web form.

Do not answer that issue through an MCP academic-answer tool and do not turn a
host/Agent identity into an author identity. The authenticated local Web
session shows only whether the current local session is verified, accepts one
accept/revise/reject choice and reason per candidate, and server-binds that
same private session identity plus `confirmed_at`. Do not display raw
principal/session/provenance fields in the form. The Runner combines those
values with the persisted preparation
inside one CAS transaction. Browser interruption leaves the confirmation issue
recoverable; an invalid or stale confirmation leaves revision and artifacts
unchanged. Only the accepted confirmation advances to J6.

### J6 exact claim-graph edge contract

At `awaiting_claim_graph`, read the bound schema as the executable wire
contract. A node has the exact required fields `node_id`, `node_type`,
`statement_sha256`, `source_artifact_id`, `source_sha256`, `locator`, `status`,
and `core`; a retained claim sets `node_type=claim`, `core=true`, and
`status=verified`. Every edge object contains exactly:

```json
{"from":"<existing node_id>","relation":"<licensed relation>","to":"<existing node_id>"}
```

`from_node_id`, `edge_type`, `to_node_id`, `source`, `target`, and other aliases
are not accepted. Direction and endpoint types are literal. For a historical graph consumer, use its exact edge schema. In the current host,
check each core claim's applicable evidence, results, citation context, warrant,
limits, boundaries and counterevidence; do not invent a support node or require
reciprocal JSON edges merely to complete a graph:

| Claim → support | Support → claim | Required support node type |
| --- | --- | --- |
| `supported_by` | `supports` | `evidence` |
| `grounded_in` | `grounds` | `result` |
| `cited_context` or scientific-only `cited_support` | `supports_context` | `citation` |
| `limited_by` | `limits` | `limitation` |
| `warranted_by` | `warrants` | `warrant` |
| `bounded_by` | `bounds` | `boundary` |
| `challenged_by` | `challenges` | `counterevidence` |

For example, the evidence pair is
`{"from":"claim-1","relation":"supported_by","to":"evidence-1"}` plus
`{"from":"evidence-1","relation":"supports","to":"claim-1"}`. Repeat the
same typed directions for every core claim; do not submit only the inverse
edge. Target rules and advisory exemplars use `cited_context` /
`supports_context`; `cited_support` is reserved for a scientific citation that
actually supports the claim.

Runner-derived subject, contribution-decision hash, derived-authority source
hashes, graph snapshot, and challenger snapshot may use the documented zero
sentinel in a producer candidate; non-derived material/source hashes must bind
the actual current base artifacts. Structural edge errors are rejected before
revision mutation with the exact field/relation/direction error. A
schema-valid but semantically incomplete support set remains at J6 with an
audited typed blocker; its corrected retry uses the new open issue, while the
previously frozen J4/J5 authority pointers remain available unless explicitly
invalidated by source mutation.

### J7 exact figure asset, comparison, and winner contract

At `awaiting_figure_intent`, use the current issue's bound schema rather than
inferring keys from a prior blocker. `intent` has exactly `mode`, `producer_id`,
`decision_basis_artifact_ids`, and `figures`. The decision basis is a non-empty
unique subset of `direction_authority`, `target_authority`, and
`claim_evidence`; these are frozen W4 artifact IDs, not prose labels or
candidate assets.

Every non-zero figure contains `figure_id`, one or more
`panels: [{"panel_id":"..."}]`, and mode-specific exact asset bindings:

- `keep` requires `current_asset`;
- `redesign` requires `current_asset`, non-empty `candidate_assets`, and
  `independent_comparison`;
- `create` requires non-empty `candidate_assets` and
  `independent_comparison`;
- `zero` requires an empty `figures` array and is invalid when the current
  material ledger contains active manuscript figures.

Each asset is exactly
`{"artifact_id":"...","sha256":"<64 lowercase hex>","revision_id":"<current revision>"}`.
Bare `candidate_artifact_ids`, paths, and IDs without hashes are not asset
bindings. For an object supplied in `payload.input_artifacts`, its binding hash
is SHA-256 over UTF-8 JSON with keys sorted, compact `,` / `:` separators, and
one trailing LF; the current issue example contains an internally consistent
candidate object and hash. Material-file assertions are verified and converted
by the Product Web host to this same Runner input-object binding before the
public answer is submitted. An independent comparison is exactly:

```json
{
  "reviewer_id": "independent-figure-reviewer",
  "producer_ids": ["figure-producer"],
  "status": "PASS",
  "reviewed_asset_hashes": ["<every exact current/candidate SHA-256>"],
  "decision": "candidate_wins",
  "selected_sha256": "<exact winning candidate SHA-256>"
}
```

The reviewer must not alias the figure producer or any `producer_ids` entry.
For `create`, `decision` is `candidate_wins`. For `redesign`, use
`redesign_wins` with a selected candidate, or `keep_original` /
`no_clear_winner` with the exact original SHA-256. `winner`,
`selected_candidate`, `comparison_artifact_id`, and other guessed aliases are
invalid. `reviewed_asset_hashes` must equal the complete current/candidate hash
set, and `selected_sha256` is the winner binding. The public example is an
internally hash-bound non-zero `create` shape, but its illustrative candidate
and placeholder identities must be replaced with current evidence before a
scientific submission. Structural field/alias errors are
rejected before revision mutation; scientifically blocked comparison outcomes
remain audited J7 blockers.

### TeX main-text fragment resolution

A populated material root may contain the scientific manuscript, template
documentation, and a detached TeX fragment together. Never copy the materials
to a sanitized/projection directory and never create a replacement task merely
because more than one `.tex` file exists. ProductRunner selects the primary
manuscript from complete-document scientific structure, not from
`documentclass` alone, while keeping every original source byte and the same
material `snapshot_sha256`.

If J4 returns `MANUSCRIPT_FRAGMENT_RESOLUTION_REQUIRED`, reload that same task
and issue. Inspect the ledger-bound fragment bytes. Only when the fragment has
active section structure, substantive scientific prose, and resolved
scientific figure dependencies may the current host submit
`payload.material_semantic_resolution_requests`. Each item is
`paperspine5.material-semantic-resolution-request/1.0` and must contain the
current `task_id`, material `snapshot_sha256`, source ID/path/SHA-256,
`requested_role=main_text_fragment`, these exact ordered `basis_codes`:
`active_section_structure`, `resolved_scientific_figure_dependency`,
`substantive_scientific_prose`, a `resolver` with
`actor_kind=host_evidence_classifier`, `external_action_authorized=false`, and
`request_sha256` over the exact request without that self-hash field. Do not
derive the role from a filename such as `Supplementary file.tex` or from a
free-text reason. ProductRunner recomputes the evidence from immutable material
bytes and persists the accepted resolution in `materials.figure-set`.

A missing decision remains a typed J4 blocker. A forged/stale request fails
before revision mutation. A valid retry advances the same task and snapshot;
Product Web, `task_record.json`, and flat progress remain projections of that
one Runner state. Never use a second task or material copy as a workaround.

With a valid local delegation grant, the configuration answer is the one
user-origin operation. Each later J4-J11 academic answer is an internal current-
host operation with its own provenance. Any contribution, motivation, figure,
or non-author target choice exercised under that grant must publish a fresh
`delegated-decision.` receipt into `snapshot.interaction.decision_receipts`.
Product Web, flat output, Markdown, JSON, and CLI must display that exact list.
Author facts, submission scope, licences/fees, and external actions stay human
gates and cannot be delegated.

At J8, a figure-active Word surface is not complete merely because its DOCX
package contains six media members. Preserve canonical PDF figure bytes for the
paper/PDF surface, convert only the Word intermediate to PNG, and submit the
typed `paperspine5.word-figure-media-receipt` through the current Word surface
receipt. It must bind every selected figure ID and source hash one-to-one to a
reader-visible `word/media/*.png` hash and to the same page-complete Word render.
Any embedded PDF media or missing mapping blocks J8/J9 and local delivery.

### User feedback after a completed local paper

At `target_package_ready`, ordinary `runner_resume` only recovers the same
completed task; it does not start a revision. For explicit user feedback, use
the frontend's **请求修改** form, or discover
`paperspine5_runner_request_revision` with `host tools --tool` and call it on
the same task with `command_id`, fresh `expected_revision`, the actual
`feedback` (1–8000 characters), and the necessary `scope`:
`manuscript` (J8), `figures` (J7 under the unchanged approved plan), or
`figure_mapping` (J6 for a new reference/story mapping, then J7).

The returned `user_revision_request` is user intent, not independent review.
Do not put it into `initial_review`, invent reviewer objections, or preserve an
old PASS as the verdict on changed bytes. Continue the returned issue through
the existing stage tools; preserve the old source/render files, write the
revision in a new local directory, and obtain a new independent J9 before J10.
The same frontend retains the last completed package as a clearly labelled
previous version while current readiness is incomplete.

New reference files outside the existing material ledger require the existing
`paperspine5_runner_add_materials` route with the newly authorized read-only
directory, then bootstrap/configuration on this same task. This is a genuine
new material snapshot and returns to J2; it is not an incremental J6 shortcut.
Keep the previous package pin and reuse unchanged valid analysis with its exact
inputs/code, but do not label the new reference as an old ledger source or edit
sealed material directories. No separate task or isolated Codex login is needed.

### J9 blocked review and canonical revision

For J8/J9 local-file work, use `paperspine5_runner_answer_host_materialized_stage`
with the current issue/revision/token; J9 supplies all current PDF and Word page
paths in `host_review_pages` and a separately obtained independent review.
Do not manufacture PASS: `decision=block` with real objections is committed as
`REVISION_REQUIRED` and returns the same task to J8 with immutable prior review
context. A malformed or stale review remains blocked rather than becoming a
revision approval.

At returned J8, preserve the old files and create new `.tex`, PDF, DOCX and page
paths with changed canonical bytes. Supply one `revision_response` per exact
prior `objection_id`, including its actual `evidence_locator` and
`change_summary`. Do not change the material snapshot for manuscript-only
repair. The next host-materialized J9 builds the consumed top-level
`initial_review`, `revision_diff`, and `re_review`; it preserves the original
review and binds every changed artifact and head. Only independent re-review
can close the objections. Non-empty `closure_revisions` is not a supported
shortcut. Show the user objections, changes and rendered files, not these
machine contracts or attestations. J10/readiness and external authorization
remain separate gates.

Unknown author identity, affiliation, ORCID, Funding, or data URL facts remain
unknown. They may keep submission/external readiness false, but do not block a
separate evidence-complete local manuscript when the current stage contract
does not require them.

This exception never removes target adaptation from local delivery. The frozen
target obligation ledger must classify each item with typed
`readiness_scope=local_delivery|author_only_submission`, bind that classification
to current `target_authority` bytes and an evidence locator, and use a fixed
author-fact key for the latter scope. Every hard non-author obligation still
needs an exact current-artifact mapping and `target_compliance_valid=true`.
J4 gives every official hard rule a typed readiness scope and evidence locator;
the host derives stable `target-rule:<authority_rule_id>` IDs. J9's independent
review result must cover every local-delivery rule, after which the host binds
each finding to the current target authority and PDF surface hash. A producer
cannot invent or reclassify the ledger, nor compensate `unsatisfied` with a
reason, mapping status, or readiness predicate. Reason strings and blanket
omission of target obligations/mappings are invalid.

### J10 local package from the accepted manuscript and review

At `awaiting_package`, use the same
`paperspine5_runner_answer_host_materialized_stage` tool and a fresh bound
answer/issue/revision/token. For the ordinary first local package, its exact
`answer.payload` is:

```json
{"requested_scope":"local_delivery"}
```

The separate tool argument `review` is JSON `null`. This is a request to prepare
and validate the local package, not an academic PASS or an author confirmation.
Read `host tools --tool paperspine5_runner_answer_host_materialized_stage` to
confirm support in the active installed build. Do not send this compact request
to the generic academic-answer tool, copy the empty J10 example objects, import
private runtime helpers, or add `stage_payload` as a second envelope. Preserve
the user's requested scope; do not lower it merely to obtain a passing result.

The host reloads the accepted canonical manuscript, claim/evidence inputs,
independent review, rendered surfaces and frozen target rules. It prepares the
existing package/readiness fields from those inputs, retains unknown or stale
findings, and checks the actual archive before issuing a package PASS. It does
not turn a bounded reader review into external citation verification, complete
journal compliance or a new scientific review. Unknown author facts remain
unknown and external actions remain unauthorized. A blocked result must be
resolved at its actual evidence/file owner, not by filling every predicate true.

The local source package must contain the canonical PDF/DOCX/TeX, active local
TeX dependencies (including nested inputs), and the editable figure sources
bound to the accepted final mappings. Do not include an entire materials tree
or private raw data by convenience. If an editable source needs additional
dependencies, they must be explicitly supported by the registered source
information; existence of an SVG alone does not prove an editable/reproducible
figure package. Missing, changed, conflicting or out-of-workspace inputs need a
real correction before packaging, not removal from the promised deliverables.

After the response, reload the same task. Use its ordinary frontend download
link, verify the downloaded archive against the registered artifact, inspect
the member list and open the promised reader/source files. Report package
availability, scientific quality, journal compliance and submission authority
separately. A generated ZIP or a successful API response is not proof of an
actual browser download or of the user's final quality acceptance.

## Nested Agent and blocker boundary

The Product Web nested Agent is an optional fail-closed fallback. A nested Web
Agent blocker such as `AGENT_PROFILE_ISOLATION_UNAVAILABLE` or
`AGENT_OUTPUT_LIMIT` records that the fallback did not submit anything; it is
not a Runner academic answer and must not be converted into one. Reload the
same open issue and let the current host perform the stage through its routed
entry: J8/J9/J10 local-file, review and package work uses
`paperspine5_runner_answer_host_materialized_stage` as described above; other
academic stages use `paperspine5_runner_answer_academic_stage`. Keep the 2 MiB log cap, no-retry,
no-parent-profile-fallback, and unchanged-Runner guarantees for that optional
path. Producer and reviewer children use an empty task-local `CODEX_HOME` and
explicit OS-keyring authentication; they never copy, link, parse, or fall back
to the parent `auth.json`. If the current Codex login is file-only, a person may
perform a one-time `codex login -c 'cli_auth_credentials_store="keyring"'` and
retry the unchanged issue. Until a real producer and reviewer both succeed in
that boundary, keyring configuration is only a safe reachability repair, not a
Web E2E PASS.

## Web and flat-output parity

Product Web reads and resumes the same Runner task. It may display status,
materials, artifacts, layered readiness, and local package links, but does not
mint a parallel academic authority.

When a ProductRunner `task_record.json` exists, flat output is a read-only
projection of the same task record and hash-bound Runner artifacts.
`progress_check.py` may verify or render that projection, but the host must not
hand-write flat files to advance a gate, create a second revision history, or
replace the Runner's material snapshot. PDF/DOCX and package paths reported on
any surface must resolve to the same Runner-registered artifact hashes.
