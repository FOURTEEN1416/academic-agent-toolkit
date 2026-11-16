# Open Release Beta

Use this playbook only after the requested paper/delivery package is stable.
It adds a post-delivery release branch for code, data, figures, preprints,
protocols, registries, and domain repositories. It does not replace journal
submission and it is never an automatic continuation of `BUNDLE_READY`.

The Beta's one-click promise means: one user selection and one final
confirmation can authorize the host Agent to execute every currently eligible
platform action on the user's computer. It does **not** mean PaperSpine can
bypass platform login, author eligibility, institutional authority, curation,
moderation, fees, license choice, ethics approval, or controlled-access rules.

## Interface

```bash
python scripts/open_release.py describe
python scripts/open_release.py catalog --domain medicine --artifact-role clinical_signals
python scripts/open_release.py invoke <open-release-invocation.json>
```

Cross-component callers must read `open-release-interface.md` and the JSON
Schemas under `references/contracts/`. The platform catalog is
`open-release-platforms.json`. Official platform requirements must be rechecked
before a real release because account, policy, file, and eligibility rules can
change after the catalog date.

## Required route

1. **Select.** Infer only domain and artifact types from the paper. Show the
   platform recommendations and boundaries, then let the user check platforms.
   A recommendation is not consent to publish.
2. **Bind artifacts.** Build `open_release_plan.json` with project-relative
   paths, roles, sensitivity labels, selected platforms, metadata, user/author
   declarations, licenses, and non-secret access evidence. Never put a token,
   password, Cookie, session value, or private key in the plan.
3. **Probe permissions.** The host performs read-only checks on the user's
   computer (installed CLI, authenticated CLI, signed-in browser session,
   organization role, platform eligibility). Store only
   `capability/status/source/checked_at`, never the secret or Cookie.
4. **Preflight.** Run `preflight`. Surface every platform independently as
   `READY_FOR_FINAL_CONFIRMATION`, `READY_FOR_GUIDED_HANDOFF`,
   `NEEDS_LOGIN_OR_PERMISSION`, `NEEDS_ELIGIBILITY`, `NEEDS_COMPLIANCE`,
   `NEEDS_METADATA`, `NEEDS_ARTIFACT`, or `BLOCKED`.
5. **Prepare.** Run `prepare` into a new immutable run directory. It writes a
   hash-bound manifest, action list, confirmation request, and human summary.
   It performs no network publish.
6. **Final user confirmation.** Show exact platforms, file hashes, visibility,
   license, and each platform's maximum Agent action. The user must create a
   `paperspine.open-release.confirmation` bound to the manifest SHA-256.
7. **Authorize.** Run `authorize`. It re-hashes every artifact. Only a matching
   confirmation creates `agent_release_ticket.json` and sets
   `signals.external_action_authorized=true`.
8. **Host execution.** The host Agent uses the user's computer and the exact
   ticket. It pauses on any new fee, license, terms, declaration, eligibility,
   institutional approval, artifact drift, or request to expose credentials.
9. **Record.** The host writes one structured receipt per authorized platform;
   run `record` to preserve public URLs, DOI/accession IDs, review states,
   failures, and waiting-user states without converting partial success into a
   false global success.

## Permission feedback is a product surface

Missing access is not a generic exception. Return the gap's platform, code,
category, Chinese explanation, recovery owner/action/URL, and whether retry is
possible. The main UI should prominently state `完整一键开源 Beta 不可用`
when no safe platform is ready, or `完整一键开源暂不可用，可按授权发布已就绪平台`
when partial release is possible.

Never silently skip a checked platform. Never ask the user to paste a token into
chat or JSON. If a browser session is missing, route the user to login in their
own browser. If an organization or institutional role is missing, identify the
role rather than asking for a stronger personal token.

## Medical and human-data routing

Medical publication is artifact-specific:

| Artifact | Preferred route | Hard boundary |
|---|---|---|
| Unpublished medical manuscript | medRxiv when eligible | ethics/consent declarations and platform screening; not for an already accepted/published paper |
| Eligible accepted biomedical manuscript | PMC/NIHMS or Europe PMC Plus | funder/journal eligibility and author review; not a general manuscript upload target |
| Trial registration/results | ClinicalTrials.gov PRS | Sponsor Organization account and Responsible Party authority; no participant-level dataset |
| Functional genomics | NCBI GEO | controlled human data routes to dbGaP/controlled SRA |
| Raw sequencing reads | NCBI SRA | public human data require explicit consent; otherwise use the controlled route |
| Controlled human genotype/phenotype | dbGaP | PI, institutional signing official, consent groups, IRB/ethics and data-use governance |
| Physiological signals/clinical resource/software/model | PhysioNet | PHI removed, co-authors approve, editorial review, open/restricted/credentialed license route |
| BIDS neuroimaging | OpenNeuro | BIDS validation, defacing or explicit consent, no GDPR-protected dataset, CC0 |
| Proteomics | PRIDE/ProteomeXchange | account, PX submission tooling, sample/file metadata and validation |
| Experimental molecular structure | wwPDB OneDep | accepted experimental methods, format/validation, depositor review |
| Protocol | protocols.io | protocol ownership/workspace publish permission |
| General deidentified data | Dryad, Figshare, Zenodo, OSF | repository-specific anonymization, license, curation, embargo, and permanence rules |

If the built-in catalog does not cover the user's discipline or artifact, use
FAIRsharing and re3data for current repository discovery, research the selected
repository's official requirements, and do not invent a generic upload route.

## Safety and idempotency

- Prepare and authorize directories are immutable run directories.
- Artifacts must remain inside `project_root`; symlinks are rejected.
- Obvious secret-bearing files and secret patterns hard-block preflight without
  printing the secret value.
- Identifiable, confidential, restricted, or unknown-sensitivity artifacts
  cannot be sent to public repositories.
- The ticket binds plan, manifest, confirmation, platforms, metadata, action
  scope, and artifact hashes. Changed files require a fresh confirmation.
- Each platform action has an `idempotency_key`. Before retry, read the final
  receipt and do not recreate an already-successful record.

## Completion boundary

`FULL_BETA_READY` means preflight is ready for final confirmation. It is not a
publication. `AGENT_RELEASE_AUTHORIZED` means the host may perform the ticket's
exact external actions. It is not evidence those actions succeeded.
`RELEASE_RECORDED` means every authorized platform returned an accepted receipt
state; `PARTIAL_RELEASE_RECORDED` must remain visibly partial.

