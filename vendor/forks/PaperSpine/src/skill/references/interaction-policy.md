# Interaction Authority and Local Delegation

This policy controls who may make a paper decision. It is independent of
`review_policy`: `balanced` and `strict` select review rigor, not permission to
act for the user.

## Current host authority

Use the same task's saved configuration, user choices and explicit delegation.
The host chooses tools, writing structure, execution order and ordinary local
repairs within that scope. Guided contribution/motivation/figure choices still
wait for the real user; explicit delegation permits only the decisions actually
delegated. Do not invent a user click or require another authorization form to
recognize an existing instruction. Normal local packaging follows the requested
delivery scope; it is not external submission.

Unknown author, ethics, funding and licensing facts cannot be guessed. Private
sharing, publication, fees and external submission require the relevant explicit
authorization. These limits do not stop unrelated safe local work. Read the
current public schema for recording actual choices; do not mutate derived state.

## Historical Runner compatibility

The remaining modes, typed grants, expiry/hash fields and decision receipts
describe the old Runner only. They are not additional prerequisites for the
current host and do not override the authority rules above or the main Skill.

### Legacy modes

`guided` is the default. Contribution, motivation, and every decision that
needs user authority remain an open typed Runner issue until the user answers.

`delegated_local_test` permits the current host Agent to make only the listed,
reversible local decisions after one explicit initial authorization. The grant
must be persisted in the run contract before J4 and must bind:

- the exact `task_id` and material `snapshot_sha256`;
- `requested_scope=manuscript|local_delivery` (never `submission_package`);
- a finite expiry and the exact authorized decision classes;
- `reversible=true` and `external_action_authorized=false`;
- a host/user actor with `authority_kind=authenticated_local_user_session` or
  `host_user_message`;
- `user_confirmation_sha256`, `authority_attestation_sha256`, and
  `grant_sha256`, each calculated over the canonical typed subject.

A producer-set Boolean such as `explicit_user_grant=true` is not authority by
itself. Missing actor evidence, an unknown field, a forged hash, expiry, task or
material drift, or scope drift fails before Runner revision mutation.

## Decision classes

The grant may contain only these typed classes:

- `contribution_selection`: choose an evidence-supported contribution within
  the current claim boundary;
- `motivation_selection`: choose an evidence-supported motivation aligned with
  that contribution;
- `figure_keep_or_transform`: keep a figure or make a reversible delivery-
  surface transform while preserving original bytes and provenance;
- `figure_omit`: omit a figure only when separately granted;
- `figure_supplement`: create/supplement a figure only when separately granted;
- `non_author_local_target_adaptation`: make non-author local packaging and
  target-mapping decisions already supported by the typed target ledger and
  independent review.

`figure_keep_or_transform` never implies omit or supplement. A transform keeps
the original content hash and records the derived asset hash. Target adaptation
cannot invent, omit, reclassify, or self-certify an obligation.

## Permanent human gates

No local delegation grants authority to guess or decide author name,
affiliation, ORCID, Funding, data-availability facts, licences, fees, submission
scope, or any external action. It cannot upload, submit, publish, transfer,
purchase, accept terms, or authorize a third-party disclosure. These remain
typed human gates, and unresolved facts may keep `submission_ready=false` and
`external_action_authorized=false` without blocking an independently complete
manuscript or compliant local delivery.

## Host-stage execution and receipts

After a valid initial grant, the current host performs J4-J11 on the same
ProductRunner task. Later academic answer commands are internal host/Agent
operations, not new user answers. Every exercised delegated choice produces a
fresh `paperspine5.delegated-decision-receipt` whose artifact ID begins
`delegated-decision.` and binds task, revision, stage, decision class, action,
requested scope, material snapshot, run-contract hash, grant ID/hash, choice
hash, evidence bindings, reversibility, and `external_action_authorized=false`.

The Runner snapshot's `interaction.decision_receipts` is the canonical list.
Product Web, flat output, Markdown, JSON, and CLI render the same list; they do
not mint or edit authority. Missing receipts or a colon/dot naming mismatch
fails closed.

The nested Product Web Agent remains an optional fail-closed fallback. Its
profile/output blocker cannot invalidate a valid host grant or prevent the
current host from submitting the same issue-bound typed answer.
