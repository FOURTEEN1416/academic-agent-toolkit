---
name: zotero-obsidian-bridge
description: Use this skill when Zotero is the literature source of truth and the project KB should receive source notes under Sources/Papers plus project-linked synthesis in Knowledge and Writing.
version: 0.3.0
---

# Zotero Obsidian Bridge

Use this skill when papers live in Zotero and the project KB should receive project-local notes.

Default flow:

```text
Zotero -> Sources/Papers -> Knowledge -> Writing -> Maps/literature.canvas
```

Rules:
- one canonical paper note per paper under `Sources/Papers/`
- literature synthesis goes to `Knowledge/`
- writing-oriented outputs go to `Writing/`
- `Maps/literature.canvas` is the default derived graph artifact
- update `_system/registry.md`, `02-Index.md`, and today's `Daily/` after substantial ingestion

## Evidence extraction requirement

Core papers and papers with reusable claims should include an evidence record. Abstract-only or placeholder notes may stay in `To-Read` until there is enough evidence to extract a reusable claim.

```md
## Evidence Record

Evidence ID:
Source:
Source type: full paper | preprint | dataset | experiment artifact | project note | abstract-only | webpage placeholder
Supports:
Contradicts:
Method / dataset / metric:
Limitation:
Project relevance:
Claim strength: speculative | observed | supported | strong
```

Use `../research-ideation/references/research-contract.md` as the shared contract for Evidence Records and claim strength definitions.

Before synthesis lands in `Knowledge/` or `Writing/`, apply the shared Claim Promotion Gate:
- every promoted claim must point back to an Evidence Record ID,
- source type must be strong enough for the claim,
- abstract-only and webpage-placeholder items cannot support durable claims,
- allowed wording and forbidden stronger wording must be preserved when the claim may later enter a report, manuscript, or rebuttal.

When synthesis lands in `Knowledge/`, link the supporting paper notes explicitly. Do not promote literature synthesis that cannot point back to source notes.
