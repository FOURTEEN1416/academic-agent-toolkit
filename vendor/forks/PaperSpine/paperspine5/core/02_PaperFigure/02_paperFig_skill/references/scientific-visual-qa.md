# Scientific and visual QA

## Scientific correctness

Verify every final result panel:

- source file and code path are recorded;
- sample count matches filtering;
- metric definition matches the paper/project;
- pairing/grouping is correct;
- error bars and intervals are defined;
- statistical tests match assumptions;
- units and transformations are correct;
- category order and labels are accurate;
- axes do not exaggerate or invert conclusions;
- highlighted examples are representative or explicitly selected.

Schematic panels must be labeled or clearly identifiable as schematics. Do
not present schematic arrows or illustrative values as measurements.

## Visual correctness

At page view inspect:

- reading order and hero panel;
- balance, margins, and alignment;
- consistent page/figure titles;
- coherent palette and entity identity;
- visual density appropriate to the claim.

At close view inspect:

- clipped panel letters, labels, color bars, or annotations;
- legend/title and label/tick collisions;
- font-size consistency;
- line/marker visibility;
- raster sharpness;
- empty or degenerate groups;
- heatmap ranges and color-bar labels;
- arrow endpoints and residual paths in architectures;
- correct scientific notation, symbols, and units.

## Export standard

- Keep measured data plots vector-native in PDF/SVG and export a 300 dpi PNG.
- Default schematic delivery is a publication PNG plus editable PPTX from the
  `img2ppt_hybrid` route. Preserve and audit the source image, native text and
  connector authority, real-object replacement manifest, post-conversion
  artifact, QA, and lineage; prohibit a full-slide screenshot masquerading as
  editability.
- For an explicit `high_resolution_raster` route, deliver PNG/TIFF at the
  declared physical size and at least 300 effective PPI (72 PPI is the absolute
  configured floor, not the quality target). Preserve the text-free master,
  optional overlapping tile redraws, editable annotation JSON, stitch
  manifest, QA, and lineage.
- Do not claim that mechanically splitting an existing raster adds detail;
  tiled mode requires independent redraw/refinement before stitching.
- Use PDF/SVG schematic output only when `direct_vector` was explicitly
  selected or the venue requires it.
- Use embedded TrueType fonts or venue-compatible font settings.
- Rasterize only dense marks, not labels and axes.
- Preserve transparency only when downstream software supports it.
- Test the exact final page/column size, not only a large development canvas.

## Programmatic checks

Use `scripts/validate_research_figures.py` to verify:

- PDF readability and expected page count;
- non-empty page rendering;
- raster dimensions and visual variance;
- required text presence when supplied;
- manifest paths and required outputs;
- machine-readable QA report generation.

Programmatic PASS does not replace visual inspection.

## Completion gate

Do not deliver when:

- a final result panel still uses placeholder/random data;
- a figure cannot be traced to code/data;
- a reference source is invented or unverified;
- panels repeat the same evidence without purpose;
- labels or units disagree with the source analysis;
- any page has clipping, overlap, corruption, or unreadable detail;
- the architecture does not match the actual model.
