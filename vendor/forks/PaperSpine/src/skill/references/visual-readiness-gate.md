# Visual Readiness Gate

## Current host visual inspection

Inspect the actual requested PDFs and Word/faithful Word renders at the paths
used by this task. Source validity or a successful build does not prove visual
validity. No alias copy, manifest or receipt is required merely to start review.

At final assembly inspect every page, then read the page sequence. Check title,
author/header boundaries, clipping, missing glyphs, page occupancy, reading order,
references, captions, tables and figure placement. Inspect each complete figure
and its panels against its source, scientific job, data/units, evidence boundary,
body reference and actual saved selection. Check the smallest labels at physical
output size independently in PDF and Word; DPI is not a label-size measurement.

Open the relevant external-reference/current and prototype/final comparisons,
and old/new comparison for revisions. These have distinct purposes as defined in
figure-reference-mapping.md; an old own figure or original-design sentinel cannot
prove published-reference learning. Keep the actual inspected paths and concrete
findings in the existing notes or review report, without duplicating forms.

Correct the producing source and re-render affected outputs. A change that
reflows the document calls for checking every affected page; an unrelated task
event or one figure's local change does not reset all scientific review. Preserve
valid findings and choices. If a renderer or source is unavailable, state the
specific unverified scope and continue unaffected work; do not invent a visual PASS.

## Historical manifest/checker compatibility

The remaining aliases, schemas and commands apply only to an explicitly used
legacy output tree. Current inspection uses the actual task paths and checks
above; read the substantive visual checks below without creating legacy forms.

TeX validity is not visual validity. Run this gate only after the current
`main.pdf` has been copied to `paper.pdf` and all final figure assets are in
place.

## Prepare

```bash
python scripts/visual_readiness_check.py paper_rewriting_output --prepare --markdown --write
```

This renders every PDF page and every renderable figure, records hashes, and
creates `visual_audit_manifest.json` with pending receipts. Preparation is not
a pass.

## Inspect Every Render

Use the host's image-view or multimodal inspection capability on every file
listed in the manifest. Do not infer visual correctness from TeX source, file
existence, or a figure QA summary.

For every page, record PASS/FAIL with a concrete note for:

- title, author, and header boundaries;
- clipping at all four edges;
- blank or float-only pages;
- avoidable large blank regions, unbalanced columns and stranded headings;
- text/figure readability.

A blank or nearly blank page, an avoidable page with only a small remnant of text,
or a large unexplained void in the middle of a manuscript is a visual failure.
Do not solve it by shrinking all text: first repair float placement, figure/table
size, paragraph breaks, section order or the correct venue surface. Record the
page and cause, regenerate the producing source, and inspect the complete affected
sequence again.

Then read the pages in sequence. Check whether each main figure appears near the
Results unit that needs it, whether float order interrupts the argument, and
whether the reader encounters Discussion before the supporting visual evidence.
Use judgment rather than a fixed distance rule; repair layout when sequence
obscures the story.

For every figure, inspect the complete image and all panels. Record PASS/FAIL
for method names, panel labels, baselines, metrics, datasets, and
caption/Results alignment. When `figure_requests.json` provides a scientific
story, also compare the actual pixels with its dominant claim, hero panel,
declared panel jobs, evidence anchors, intended conclusion, and claim boundary;
record `story_claim_alignment`, `panel_role_alignment`, and
`claim_boundary_respected`, plus panel-level receipts. A visible conflict such as a different method name
inside the figure is a submission blocker even when the filename and caption
look correct. Add panels and any issue evidence to the manifest; never silently
edit a scientific label when the source evidence is unclear.

Inspect the actual full canvas, axes and panel backgrounds. Prefer white or transparent scientific canvases; use another background only when the user, venue or scientific encoding justifies it. Check contrast, consistency and preservation of meaningful colour. A neutral-background probe is an aid for the selected design, not a universal requirement that every canvas, axes or panel background be pure white; record justified exceptions in the existing visual notes.

When `figure_body_contract.json` exists, treat its SHA-256-bound publication
asset, editable source, label, Results mapping, claim, and boundary as the
assembly interface. Final readiness additionally requires the manuscript body
to reference every declared label; file presence alone is insufficient.

When a final figure mapping exists, open its side-by-side comparison surface.
The lawful reference/original sentinel and current publication figure must be
simultaneously visible, and the current preview source hash must equal the body
publication asset. Do not accept a one-image carousel or a machine `status`
field as evidence that the comparison was actually visible.

Complete `review.reviewer`, `reviewer_type`, `reviewed_at`, and set all checks,
item statuses, and overall review status to `pass` only after actual inspection.

## Validate

```bash
python scripts/visual_readiness_check.py paper_rewriting_output --markdown --write
```

Any changed PDF/TeX/figure hash invalidates the receipt and requires render +
inspection again. An unavailable renderer, missing page, unrendered SVG,
unresolved conflict, or pending check keeps `visual_ready=false`.
