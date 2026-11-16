# Target-Specific Submission Bundle

Use this mode when the user requests submission materials, a delivery package,
attachments, figures/tables, source files, or an upload ZIP.

## Existing ProductRunner task

For the current host workflow, use the existing public task, its saved target and scope, the actual files under `paper/`, and the current publish/prepare-delivery tools. Historical ProductRunner records may inform recovery, but do not route normal packaging back through J10 or create another completion authority. The host owns the scientific work and actual preview/download checks.

`local_delivery` is not an upload-ready submission request. Preserve unknown
author/ethics facts and submission restrictions without blocking safe local
work. All applicable non-author local requirements still need genuine evidence;
neither an archive nor a reader-review PASS establishes full journal compliance.
Read `publication-target-profile.md` when actual target research/adaptation is
required, not to repeat unchanged research solely because the stage is J10.

## Build the portable local package

Create a clean package copy from the current semantic source and selected assets.
Preserve the source-relative directory structure, or deliberately rewrite its
dependency paths in that copy. Include the bibliography, used class/style/CSL,
layout filters, editable figures, permitted plotting inputs/scripts and a build
command with the required working directory and tool versions. Shareable data
remain limited to the user's authorized scope; original private materials are
not automatically package dependencies.

Build from the package copy before archiving, then extract the actual ZIP into a
new temporary directory and run the documented build there. Check that local
inputs resolve within the extracted package and that no absolute paths, parent
paths or environment search paths reach back into the working project. TeX
`-recorder` output can reveal the files the build actually read; installed engine
packages/fonts are runtime dependencies to document, not private project files
to collect indiscriminately. Fix missing paths in the producing package and
compare the rebuilt manuscript with the reviewed source/output. ZIP membership,
file hashes and the old working directory's successful build do not prove this.

After revision, regenerate the affected PDF/DOCX and both requested packages
from the same revised source. Reuse unchanged valid assets and checks; a
metadata/ethics limitation affects submission claims, whereas a broken source
path is a local deliverability defect to repair. If rebuilding requires an
unavailable tool, preserve the package and report the precise unverified
rebuild scope without calling it portable or submission-ready.

## Historical submission assembler

The remaining layout and assembler instructions apply to the legacy
publication-cycle workflow without ProductRunner authority, or to separately
requested submission-specific artifacts. Read `publication-cycle.md` and
`publication-target-profile.md` before that workflow. Its upload-ready gates do
not redefine the existing task's local-delivery scope.

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
   comparable papers. Complete the nine-area structured rule coverage and run
   `profile-check`; unresolved official rules remain `pending` and block.
2. Analyze the canonical manuscript and match every applicable target
   requirement to a source or generated artifact in
   `submission_package_plan.json`.
3. Produce the actual files. Use the target's accepted format, not a generic
   default. Convert from the canonical source, then render and compare content.
4. Validate each file with the relevant PaperSpine/PaperFigure/host tool and
   record receipt path + SHA-256 in the plan.
5. When the main text relies on supplementary evidence, create
   `supplement_evidence_index.json` and run `supplement_evidence_index.py`.
   Each claim-bearing item must link a literal main-text locator, its real
   supplement caption/section, the publication asset, the upload artifact, and
   a semantic pixel-review receipt. A valid PDF cannot offset a caption/pixel
   mismatch. Record journal-required upload surfaces in `submission_inventory`.
6. Set `compliance_inputs.manuscript_path` to the current project-local `.tex`,
   `.md`, or `.txt` authority used for deterministic counts, add bibliography
   paths when references live in separate `.bib` files, and run `rules-check
   --phase writing` before final formatting.
7. Obtain explicit confirmation for target selection, author identity/order,
   declarations, and no simultaneous submission.
8. Assemble the immutable bundle. The script copies only project-local files,
   rejects stale profiles/path escape/placeholders/old-target terms, and creates
   the upload ZIP only when every applicable required item is ready and the
   final structured journal-rule recheck passes.

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
- `compliance_inputs.manuscript_path` must resolve to the current analyzable
  manuscript source under `project_root`; optional bibliography paths obey the
  same boundary.
- All sources and receipts stay inside `project_root`.
- Every applicable required/conditional requirement has one plan item.
- `ready` means the file exists, has an accepted extension, has no unresolved
  placeholders, and has at least one hash-bound validation receipt.
- `needs_author` prevents claiming readiness for the affected submission requirement. It does not prevent an explicitly limited local manuscript or workspace archive.
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
SHA-256 matches. The immutable directory also contains hash-bound
`journal_rules_final.json/.md`; any hard rule that is failed, pending, or needs
author confirmation prevents ZIP creation. Preparing the ZIP does not authorize
external submission.
