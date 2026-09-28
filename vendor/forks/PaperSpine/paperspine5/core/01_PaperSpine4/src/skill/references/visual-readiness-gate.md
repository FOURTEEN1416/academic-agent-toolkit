# Visual Readiness Gate

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
- text/figure readability.

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

When `figure_body_contract.json` exists, treat its SHA-256-bound publication
asset, editable source, label, Results mapping, claim, and boundary as the
assembly interface. Final readiness additionally requires the manuscript body
to reference every declared label; file presence alone is insufficient.

Complete `review.reviewer`, `reviewer_type`, `reviewed_at`, and set all checks,
item statuses, and overall review status to `pass` only after actual inspection.

## Validate

```bash
python scripts/visual_readiness_check.py paper_rewriting_output --markdown --write
```

Any changed PDF/TeX/figure hash invalidates the receipt and requires render +
inspection again. An unavailable renderer, missing page, unrendered SVG,
unresolved conflict, or pending check keeps `visual_ready=false`.
