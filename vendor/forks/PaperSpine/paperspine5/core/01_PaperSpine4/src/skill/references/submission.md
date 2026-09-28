# Target-Specific Submission Bundle

Use this mode when the user requests submission materials, a delivery package,
attachments, figures/tables, source files, or an upload ZIP. Read
`publication-cycle.md` and `publication-target-profile.md` first.

## Output layout

```text
paper_rewriting_output/publication_cycle/targets/<target-slug>/
├── publication_target_profile.json
├── target_profile_check.md
├── submission_package_plan.json
└── bundles/<immutable-bundle-id>/
    ├── target_profile.snapshot.json
    ├── package_plan.snapshot.json
    ├── upload/                         # only files intended for the portal
    ├── bundle_manifest.json
    ├── bundle_manifest.md
    ├── submission_bundle.zip           # generated only when READY
    └── submission_bundle.sha256
```

Never reuse a non-empty bundle directory. A new build gets a new ID so prior
submissions remain auditable.

## Workflow

1. Build/refresh the target profile from the live official guide and recent
   comparable papers. Run `profile-check`.
2. Analyze the canonical manuscript and match every applicable target
   requirement to a source or generated artifact in
   `submission_package_plan.json`.
3. Produce the actual files. Use the target's accepted format, not a generic
   default. Convert from the canonical source, then render and compare content.
4. Validate each file with the relevant PaperSpine/PaperFigure/host tool and
   record receipt path + SHA-256 in the plan.
5. Obtain explicit confirmation for target selection, author identity/order,
   declarations, and no simultaneous submission.
6. Assemble the immutable bundle. The script copies only project-local files,
   rejects stale profiles/path escape/placeholders/old-target terms, and creates
   the upload ZIP only when every applicable required item is ready.

## Artifact production

- **Manuscript:** regenerate in the required Word/LaTeX/PDF template. Compile or
  render, then verify sections, citations, equations, figures, tables, and
  scientific values against the canonical source.
- **Title/blinded files:** derive both from the same author metadata. The
  blinded version must remove the target's prohibited identity signals; the
  full title page preserves them.
- **Cover letter/highlights:** derive fit and contributions from the target
  profile and confirmed paper identity. Do not inherit the old journal name or
  generic Elsevier-style limits when the live target says otherwise.
- **Figures/tables/graphical abstract:** use the PaperFigure body contract and
  final pixel receipts. Convert to the target's allowed extension, dimensions,
  color space, resolution, and file separation. Do not upscale a low-resolution
  source and call it compliant.
- **Supplement/checklists/declarations:** include only what the paper and target
  require. Reporting checklists must point to real manuscript pages/sections.
  Ethics, consent, funding, conflicts, CRediT, author order, APC/license choices,
  and AI-use disclosures require author-supplied or author-confirmed facts.
- **Source archive:** prepare a clean copy, not an in-place destructive cleanup.
  Remove unused/draft/private files, keep every used class/style/bibliography/
  figure dependency, compile the copy, and compare its rendered result.

The legacy `submission_check.py` remains useful for normalized cover-letter and
highlights drafts, and `word_guard.py`, `latex_guard.py`, visual checks, and
PaperFigure QA remain file-level validators. The target profile and bundle
manifest are authoritative for overall package completeness.

## Plan invariants

- `target_profile_sha256` must match the current profile.
- All sources and receipts stay inside `project_root`.
- Every applicable required/conditional requirement has one plan item.
- `ready` means the file exists, has an accepted extension, has no unresolved
  placeholders, and has at least one hash-bound validation receipt.
- `needs_author` is honest but blocks the archive.
- `not_applicable` is allowed only when the profile condition says so.
- `forbidden_target_terms` lists previous venues that must not leak into the
  transferred package.

## Assemble

```bash
python scripts/publication_cycle.py assemble \
  <target>/publication_target_profile.json \
  <target>/submission_package_plan.json \
  <target>/bundles/<immutable-bundle-id> \
  --markdown
```

Deliver as upload-ready only when the command exits 0,
`bundle_manifest.json status=READY`, the ZIP exists, and the recorded archive
SHA-256 matches. Preparing the ZIP does not authorize external submission.
