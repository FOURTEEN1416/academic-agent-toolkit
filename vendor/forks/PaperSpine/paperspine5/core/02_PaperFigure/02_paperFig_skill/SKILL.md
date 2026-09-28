---
name: paperFig
description: "Design, implement, revise, and validate publication-quality scientific figures from references, existing plotting code, and real project data. Trace every figure to source code and inputs; deconstruct reference figures; plan the scientific story and multi-panel structure; build complex model architecture and statistical panels; enforce a consistent visual system; and render-verify PDF/SVG/PNG outputs. Use for 科研配图, 论文配图, 找图的源代码, 参考图复刻与改造, 模型框架图, 多面板主图, figure redesign, or standardizing a research-figure process."
---

# paperFig

Create scientifically faithful, publication-quality figures through a
repeatable process from evidence inventory to final render QA.

This skill governs the **research-figure process only**. It does not include
anonymization, data perturbation, synthetic replacement, identifier removal,
or privacy guarantees. If the user separately requests those operations,
treat them as an additional workflow with an explicit data-release contract;
do not silently mix them into ordinary scientific plotting.

## Mandatory routing

Read the following references before acting:

- `references/research-figure-process.md` for the phase-by-phase workflow.
- `references/reference-deconstruction.md` before imitating or adapting a
  reference figure.
- `references/architecture-and-multipanel-design.md` for model diagrams or
  compound figures.
- `references/scientific-visual-qa.md` before final generation and delivery.

Use the PDF skill whenever a PDF is read, created, or reviewed. Use the
spreadsheets skill when the main source is an XLSX workbook requiring
inspection or transformation.

## Trigger conditions

Use this skill when the user asks to:

- create or improve scientific, academic, or paper figures;
- locate the plotting code and data behind figures in a PDF or directory;
- reproduce the visual logic of public reference figures with project data;
- build a model architecture, Transformer diagram, mechanism schematic, or
  evidence-backed workflow panel;
- redesign benchmark, ablation, transfer, interpretability, or mechanism
  figures;
- assemble a consistent multi-figure suite or reference-vs-redraw atlas;
- standardize an existing plotting project into a reusable process.

Do not use it for generic illustration, ordinary photo editing, UI design, or
privacy/anonymization as the primary objective.

## Core principles

1. **Scientific truth before aesthetics.** Preserve actual data, statistics,
   units, pairing, uncertainty, sample size, ordering, and analysis logic.
2. **Reference mechanism, not superficial copying.** Identify why the
   reference persuades and transfer that mechanism to the new scientific
   claim.
3. **Source traceability.** Every final panel must map to plotting code and
   data inputs, or be explicitly marked as a schematic.
4. **One panel, one job.** Each panel answers a distinct scientific question.
5. **Complexity must be earned.** Dense figures need a clear reading path and
   evidence hierarchy; decorative complexity is not rigor.
6. **Render verification is mandatory.** A script that runs is not a finished
   figure until the exported artifact has been visually inspected.

## Inputs

Discover these from the project before asking the user:

- reference PDF/images and local citation/index notes;
- existing paper figures, drafts, and rejected variants;
- plotting scripts, notebooks, helper modules, and style files;
- CSV/TSV/XLSX/JSON/NPY/NPZ inputs and generated caches;
- model source code for architecture details;
- paper section, claim, or result that the figure must support;
- target venue, column width, page size, and output formats.

Ask only when a missing choice materially changes the scientific story, such
as which result is primary or whether a panel is schematic versus measured.

## Workflow

### 1. Inventory figures, code, and data

Run:

```powershell
python scripts/inspect_figure_project.py --root "<project-root>" --output "<work-dir>/source-map.md"
```

Manually verify important mappings. Filename similarity is only a candidate;
imports, data reads, `savefig` paths, and visual comparison are stronger
evidence.

Create or update a figure manifest based on
`assets/figure_manifest.example.json`. Every requested figure records:

- figure/panel ID;
- scientific question and intended conclusion;
- public reference(s);
- existing figure(s);
- plotting source;
- data inputs;
- statistical transformation;
- output files;
- verification status.

For tabular medical sources that match the FigMirror `clinical-cbc` contract,
run `figmirror.py render-data-study` before candidate finalization. Treat its
`data_profile.json`, `analysis_summary.csv`, and `data_binding.json` as derived
evidence, not replacements for the read-only source workbook. Never infer
units, reference intervals, clinical thresholds, or repeated-person identity
when the workbook does not provide them.

### 2. Deconstruct the references

Follow `references/reference-deconstruction.md`.

For each reference, document:

- what claim the figure carries;
- reading order and panel hierarchy;
- data-to-mark mapping;
- evidence density and use of full distributions;
- color and annotation logic;
- what should be transferred, adapted, or rejected.

Do not copy labels, biological content, or decorative forms that do not serve
the project's claim.

### 3. Write the figure design brief

Before coding, define:

- one-sentence figure claim;
- panel list and question answered by each panel;
- main evidence panel and supporting panels;
- data source and statistical unit for every panel;
- visual grammar for every panel;
- consistent palette and entity mapping;
- target dimensions and export formats.

If the figure cannot be explained as a short evidence chain, simplify or
reorder it before adding detail.

### 4. Build from actual project sources

Reuse and refactor existing plotting code rather than retyping calculations.
Read model source code when drawing architecture. Use the actual project data
unless the user explicitly asks for a schematic prototype.

Preserve:

- paired observations and group structure;
- exact analysis definitions;
- uncertainty and statistical tests;
- meaningful units and axis transforms;
- sorting/ranking rules;
- local-signal alignment;
- color identity across the figure suite.

Never substitute arbitrary random data in a final scientific result figure.
Random data is acceptable only for a clearly labeled layout prototype.

### 5. Design architecture and multi-panel figures

Follow `references/architecture-and-multipanel-design.md`.

The primary architecture panel must expose the real computation. For a
Transformer, show token/input construction, positional information,
LayerNorm, multi-head attention, residual Add/Norm, feed-forward layers,
repeat count, shapes when known, and output heads. For other models, show the
equivalent actual modules rather than forcing a Transformer template.

Tie architecture contributions to measured evidence when appropriate:

- input/channel evidence;
- ablation cost;
- local reconstruction track;
- scale or attention utilization;
- objective decomposition;
- efficiency or robustness.

### 6. Apply a unified visual system

Use one typography system, one panel-letter convention, stable margins,
consistent entity colors, and a controlled palette. Keep measured data plots
vector-native through Matplotlib/SVG/PDF. For new schematics, use the current
FigMirror default `img2ppt_hybrid`: audit the AI source before conversion,
rebuild scientific text, arrows, frames, and rule-based nodes as native
PowerPoint objects, replace declared complex objects with real text-free image
assets, then run post-conversion scientific and visual review. Choose
`high_resolution_raster` when a raster-first image is the explicit delivery
fit, and `direct_vector` when the venue or collaboration contract requires live
vector objects. These routes change the editable medium, not the scientific
story or the obligation to inspect final pixels.

Retain real names and units when scientifically relevant. Do not remove or
generalize them merely for visual tidiness.

### 7. Export and validate

Follow `references/scientific-visual-qa.md`.

Run:

```powershell
python scripts/validate_research_figures.py `
  --pdf "<output.pdf>" `
  --render-dir "<work-dir>/rendered" `
  --expected-pages <n> `
  --report "<output-dir>/FIGURE_QA.json"
```

Visually inspect every page or figure. Inspect the densest architecture figure
and at least one data-heavy figure at full resolution.

Revise until there are no clipped labels, overlapping legends, inconsistent
units, missing panel letters, empty groups, misleading scales, unreadable
references, or rasterization defects.

## Deliverables

Provide the artifacts appropriate to the request:

- data figures: final vector PDF/SVG plus 300 dpi PNG;
- schematics by default: publication PNG plus editable PPTX, retained source
  assets, conversion manifests, scientific/visual QA, and lineage;
- raster-first PNG/TIFF plus editable annotation source when
  `high_resolution_raster` was explicitly selected;
- vector PDF/SVG when `direct_vector` was explicitly selected;
- complete plotting source code;
- figure manifest and source map;
- design brief or rationale for major figures;
- machine-readable QA report;
- optional reference-vs-redraw comparison PDF when requested.

Keep earlier variants unless the user explicitly asks to replace them.

## Completion standard

The task is complete only when:

- each final panel has a verified scientific purpose;
- code and data provenance are recorded;
- values, statistics, labels, and units match the source analysis;
- reference influence is explained rather than merely copied;
- the visual hierarchy is clear at page view and details are legible close up;
- output files compile/render successfully;
- the final response links all deliverables with absolute paths.
