# Open Release Beta Integration Interface

This is the stable local interface for a PaperSpine5 main flow, host adapter,
or another Agent to add post-delivery open release. The transport is JSON over
CLI or the equivalent Python function; callers must consume `signals` and
structured gaps, not parse Markdown.

## Discovery

```bash
python scripts/open_release.py describe
python scripts/open_release.py invoke <open-release-invocation.json>
```

Source callers use `src/scripts/open_release.py`; installed Skill callers use
`scripts/open_release.py`. Python callers may import
`public_interface_descriptor()` and `invoke_open_release(request_path)`.

## Operations and state mapping

| Operation | Inputs | New output directory | State on success |
|---|---|---|---|
| `catalog` | none; domain/roles in options | no | `open_release_selection` |
| `preflight` | `plan` | no | `open_release_preflight` |
| `prepare` | `plan` | yes | `open_release_confirmation_pending` |
| `authorize` | `manifest`, `confirmation` | yes | `open_release_host_execution` |
| `record` | `ticket`, `receipts` | yes | `open_release_recorded` or `open_release_follow_up` |

Only `authorize` may return `signals.external_action_authorized=true`, and only
after artifact drift checks and a hash-bound final user confirmation. The module
still performs no network publish; the host executor consumes the ticket.

## Invocation example

```json
{
  "contract": "paperspine.open-release.invoke-request",
  "interface_version": "0.1-beta",
  "operation": "preflight",
  "project_root": ".",
  "inputs": {
    "plan": "paper_rewriting_output/open_release/open_release_plan.json"
  },
  "options": {}
}
```

All input and output paths must remain inside the invocation `project_root`.
Prepare/authorize/record output directories must be new or empty.

## UI model

Render the catalog as checkboxes with:

- platform label, artifact fit, recommendation and domain boundary;
- execution badge: CLI/API, Agent browser, or guided institutional;
- current status and exact missing capabilities;
- selected artifacts and sensitivity;
- maximum Agent action (`publish`, `submit_for_review`,
  `prepare_submission_package_only`, etc.).

The main UI should not offer the final confirm button until
`signals.can_request_final_confirmation` is true in the preflight audit. For a
partial release, both the plan and final confirmation must explicitly set
`allow_partial_release=true`; the confirmation may authorize only
`eligible_platforms`.

## Host access probes

The host owns access probes because it controls the user's computer and signed-
in browser. Add only non-secret evidence to the plan:

```json
{
  "platform": "github",
  "capability": "github_authenticated",
  "status": "available",
  "source": "host_probe",
  "checked_at": "2026-08-23T10:00:00Z",
  "evidence_note": "gh auth status succeeded; no token captured"
}
```

Use `platform="*"` only for a truly host-wide capability such as
`computer_control`. Never use a wildcard to claim account, organization,
eligibility, or publishing permissions.

## Final confirmation

`prepare` emits `open_release_confirmation_request.json`. The confirmation UI
must show the manifest SHA-256, eligible/blocked platforms, exact artifacts,
visibility, licenses, maximum Agent action, and permanence/moderation warnings.
It then writes a confirmation conforming to
`open-release-confirmation.schema.json`; never ask the user to hand-edit one.

`authorize` re-hashes the plan and artifacts. Any drift, new platform, or
unconfirmed partial release returns `BLOCKED` and leaves external authorization
false.

## Host execution and receipts

For every `ticket.actions[]` item, the host:

1. checks whether the `idempotency_key` already has a success receipt;
2. opens the official URL or approved CLI/API route on the user's computer;
3. uploads only the listed artifact IDs and applies only ticket metadata;
4. never exceeds `action_scope`;
5. pauses on new fees, licenses, terms, declarations, eligibility, institution
   approval, authentication, or changed files;
6. records one of `PUBLISHED`, `SUBMITTED_FOR_REVIEW`, `DRAFT_CREATED`,
   `PREPARED_FOR_INSTITUTIONAL_REVIEW`, `WAITING_USER`, `FAILED`, or `SKIPPED`.

Bind the receipt file to the ticket SHA-256 and run `record`. Public URL, DOI,
accession, and platform record ID may be stored; token, password, Cookie, and
session values may not.

## Schemas and catalog

- `contracts/open-release-invocation.schema.json`
- `contracts/open-release-plan.schema.json`
- `contracts/open-release-manifest.schema.json`
- `contracts/open-release-confirmation.schema.json`
- `contracts/open-release-agent-ticket.schema.json`
- `contracts/open-release-platform-receipts.schema.json`
- `contracts/open-release-result.schema.json`
- `open-release-platforms.json`

The catalog date is evidence for recommendation routing only. Immediately
before execution, the host Agent must re-check the selected platform's official
page for requirements that may have changed.

