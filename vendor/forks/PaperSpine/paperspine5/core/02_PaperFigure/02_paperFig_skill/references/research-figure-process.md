# Research figure process

## Phase 0 - Define the scientific job

Write one sentence each for:

- the scientific question;
- the conclusion the reader should reach;
- the evidence that makes that conclusion credible;
- the comparison, mechanism, or uncertainty that must remain visible.

Classify the intended artifact:

- architecture or method overview;
- benchmark/performance comparison;
- ablation/component audit;
- transfer/generalization;
- interpretation/local evidence;
- mechanism/causal chain;
- supplementary diagnostic;
- reference-vs-redraw design atlas.

Do not start with chart types. Start with the scientific decision the reader
must make.

## Phase 1 - Inventory and provenance

Scan the project and build a source map. Verify:

- which script produces each PDF/PNG/SVG;
- which files are read by that script;
- where metric definitions and preprocessing live;
- whether an image is a measured result, a schematic, or a manual composite;
- whether multiple scripts calculate nominally identical metrics differently.

Record unresolved mappings. Do not infer data provenance from appearance alone.

## Phase 2 - Reference analysis

Read the reference figure at two scales:

1. page view: hierarchy, main panel, reading order, visual balance;
2. close view: encodings, uncertainty, annotation, labels, axes, legends.

Extract the reference's persuasion mechanism, not just its geometry. Examples:

- full-population scatter plus y=x line makes paired improvement visible;
- a ranked landscape prevents cherry-picking;
- an architecture linked to real output tracks connects method to evidence;
- a component wheel plus task-level distributions makes ablation systematic;
- a local track plus attribution supports mechanistic interpretation.

## Phase 3 - Design brief

For every panel specify:

| Field | Required content |
|---|---|
| Panel ID | Stable letter/identifier |
| Question | One scientific question |
| Data | Exact file/table/array and statistical unit |
| Transform | Filter, aggregate, normalization, statistical test |
| Visual grammar | Scatter, violin, heatmap, track, schematic, etc. |
| Intended reading | What pattern the reader should inspect |
| Dependencies | Shared legend, palette, order, or axes |

Identify the hero panel. Supporting panels should explain, validate, or bound
the hero claim.

## Phase 4 - Data and code binding

Prefer refactoring the verified original plotting script. Separate:

- data loading;
- calculation/statistics;
- figure specification;
- rendering/export.

Store derived arrays or tidy tables when they materially improve
reproducibility. Do not duplicate metric calculations in several figure files
without a shared helper.

Check:

- sample counts after filtering;
- missing-data handling;
- paired versus unpaired analysis;
- confidence interval or error-bar definition;
- multiple-comparison correction;
- units and scale transformations;
- stable sorting and category order;
- deterministic seeds for stochastic layout only.

## Phase 5 - Figure construction

Build in passes:

1. **Skeleton:** page size, grids, panel hierarchy, approximate titles.
2. **Data-bound:** real arrays and statistics in every result panel.
3. **Scientific annotations:** units, n, tests, thresholds, directions.
4. **Visual polish:** typography, palette, spacing, legend consolidation.
5. **Export:** data figures as vector PDF/SVG plus requested raster versions;
   schematics through the selected FigMirror route. The default
   `img2ppt_hybrid` exports publication PNG plus editable PPTX after source and
   reconstruction review. Use high-resolution PNG/TIFF plus editable
   annotation source for an explicit raster-first route, or PDF/SVG for an
   explicit `direct_vector` route.

At the skeleton stage, placeholder data may be used only when visibly marked
as layout-only and replaced before final export.

## Phase 6 - Scientific audit

Cross-check plotted values against source summaries or independent
recalculations. Spot-check at least:

- one central tendency;
- one extreme or top-ranked item;
- one paired difference;
- one uncertainty interval;
- one local track coordinate/peak;
- one architecture shape/module label.

## Phase 7 - Visual audit

Render all final artifacts. Review at page view and close view. Revise rather
than accepting minor collisions; small defects compound in dense paper figures.

## Phase 8 - Handoff

Deliver the final files, source map, code, manifest, rationale, and QA report.
State any unresolved data/code mapping or scientific assumption explicitly.
