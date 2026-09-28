# Rebuild Guidelines

Use this reference when reconstructing a scientific, technical, or academic diagram from a PNG/JPG/screenshot into editable Microsoft Visio `.vsdx` content.

The goal is visual and semantic equivalence using native Visio shapes, text, connectors, groups, and styles. Do not treat any example below as a fixed domain template. Use `.vsdx` as the editable source, then export SVG/PDF/PPTX deliverables from that source.

## Reference Analysis

Capture these properties before drawing:

- Canvas aspect ratio, page margins, and whitespace distribution.
- Major regions: bands, panels, columns, rows, insets, legends, captions.
- Reading order: left-to-right, top-to-bottom, radial, cyclic, or feedback loop.
- Text hierarchy: figure title, panel title, module label, axis label, equation, caption, note.
- Connector semantics: solid arrows, dashed arrows, inhibition lines, braces, loops, feedback paths, summation nodes.
- Repeated motifs: stacked frames, process blocks, neural-network layers, tables, graphs, charts, heatmaps, timelines, molecule-like nodes, icons.
- Style tokens: font family, font size bands, accent colors, fill opacity, line weights, corner radii, dash patterns.
- Output needs: `.vsdx` editability, SVG vector handoff, PDF review/print, PPTX slide handoff.
- Editability risks: tiny text, dense textures, screenshots embedded inside shapes, equations, image-like scientific data.

## Panel Inventory Template

For a complex figure, write a short inventory before coding. Keep it specific to the user's reference image, not to any previous project.

```text
Canvas: landscape or portrait; approximate aspect ratio; main whitespace pattern.
Global structure: top band / bottom band / left workflow / right modules / multi-panel grid.
Panel A: title, accent color, role, main internal objects, incoming/outgoing arrows.
Panel B: title, accent color, role, main internal objects, incoming/outgoing arrows.
Panel C: title, accent color, role, main internal objects, incoming/outgoing arrows.
Panel bounds: approximate top-left x/y/w/h or four corner points for every major panel.
Shared elements: legends, captions, separators, equations, repeated labels.
Critical text: labels that must be preserved exactly.
Approximation targets: dense details that can be represented by native simplified motifs.
Output formats: `.vsdx` only by default for fast Chinese technical-bid flowcharts; add PNG/SVG/PDF/PPTX only when requested.
```

This inventory is the contract for the drawing script. If an item is not in the inventory, it is likely to be omitted or drawn inconsistently.

## Common Figure Archetypes

Choose the closest archetype before drawing:

- **Pipeline or workflow**: ordered process boxes, arrows, inputs, outputs, optional feedback.
- **Model architecture**: repeated blocks, encoders/decoders, latent variables, modules, loss paths.
- **Algorithm schematic**: data structures, operations, equations, constraints, branching logic.
- **Multi-panel methods figure**: several modules with different colors and local legends.
- **Graph or network figure**: nodes, edges, weights, message passing, clusters, highlighted paths.
- **Matrix or heatmap figure**: grids, color scales, row/column labels, aggregation arrows.
- **Chart-heavy figure**: mini plots, axes, trends, bars, curves, distributions, annotations.
- **System diagram**: components, interfaces, data stores, users, protocols, deployment zones.
- **Chinese technical-bid flowchart**: compact Chinese process boxes, tree or branched workflow connectors, repeated supervision/procurement/quality/schedule/change-management labels, and strict page-size or typography requirements.

The archetype only guides layout and helper functions. The actual labels, colors, and structure must come from the user's reference image.

## Coordinate Strategy

Use a reference coordinate system in pixels or normalized units, then convert to Visio page inches:

```powershell
$PageW = 9.25
$PageH = 6.49
$RefW = 1448.0
$RefH = 1086.0
function VX([double]$x) { $PageW * $x / $RefW }
function VY([double]$y) { $PageH - ($PageH * $y / $RefH) }
```

Draw from top-left bounds as `RectTL(x, y, w, h)` so the script remains readable against screenshots.

For Chinese labels in Windows PowerShell scripts, encode text with `UE '\uXXXX...'` or explicit code points instead of raw CJK literals. This avoids mojibake and parser failures in Windows PowerShell. If the preview shows `?` characters or a script fails before Visio opens, inspect encoding first.

## Panel Calibration and Anti-Overlap

For dense multi-panel figures, do not draw every object directly in the global page coordinate system. Calibrate in two levels:

1. Calibrate the full canvas from the reference image size to the Visio page size.
2. Calibrate each major panel from its top-left bounds or four detected corner points.

Draw the internals of each panel in local normalized coordinates:

```powershell
function RX([double]$x0, [double]$w0, [double]$u) { $x0 + $w0 * $u }
function RY([double]$y0, [double]$h0, [double]$v) { $y0 + $h0 * $v }

# u/v are 0-1 local panel coordinates.
RectRel $panelX $panelY $panelW $panelH 0.10 0.20 0.35 0.12 'Module'
```

Use four corner points and a perspective or affine mapping only when the reference is skewed, photographed, or cropped at an angle. For screenshots and exported PDFs, top-left bounds are usually enough.

Before delivery, inspect the preview for:

- child shapes crossing outside the parent panel;
- panel bounding boxes colliding with adjacent panels;
- arrows or labels running through unrelated modules;
- lower rows drifting into the next panel after font changes or export.

## Visual Matching Heuristics

- Match structure before decoration. Panel placement, reading order, and flow arrows matter more than texture detail.
- Preserve semantic grouping. Containers, modules, legends, charts, and subgraphs should be separate editable groups.
- Use local panel coordinates for nested diagrams so internal edits cannot drift into neighboring panels.
- Preserve scientific labels exactly when legible. If text is unreadable, use a close placeholder and report the limitation.
- Use simplified native motifs for dense image-like content: stacked rounded rectangles, small dots, mini heatmaps, line charts, bar charts, tables, and graph nodes.
- Keep equations editable as text when practical. Use plain text approximations if Visio equation objects are unavailable.
- Use color as semantic grouping, not decoration. Reuse one accent per panel or module unless the reference clearly uses another scheme.
- Prefer native approximations over screenshots for cubes, graphs, heatmaps, icons, and small charts. The target is editability plus visual equivalence.
- If the reference contains many tiny repeated elements, create 2-3 reusable helper functions rather than hand placing each occurrence.
- Do not force a previous project's palette, module names, or layout onto a new reference.

## Output Format Strategy

- Keep `.vsdx` as the editable master and export all other formats from the saved Visio page.
- Use PNG as a visual preview only when requested or when visual verification is necessary. Skip preview export in fast Chinese technical-bid VSDX-only mode.
- Use SVG when the user needs vector graphics for manuscripts, web pages, or post-processing in vector tools.
- Use PDF for review, print, or submission preview. Export from the Visio document after save.
- Use PPTX for presentation handoff. Prefer a PowerPoint slide containing a full-slide SVG render of the Visio page; report that this is a slide render, not guaranteed native PowerPoint shape decomposition.
- Do not regenerate separate drawings per format. Differences between formats should come from export behavior, not divergent source artwork.

## Scientific Figure Style Tokens

Use these defaults unless the reference clearly differs:

- Font: Times New Roman for manuscript-style figures; Arial or Helvetica for clean technical UI-style diagrams.
- Main border: 0.9-1.2 pt.
- Internal border: 0.5-0.8 pt.
- Rounded rectangle radius: small, usually 4-8 px equivalent.
- Arrowheads: consistent filled end arrows for forward flow; dashed lines for feedback, optional paths, or constraints.
- Backgrounds: white or very pale panel tints.
- Captions: black, bold, centered; keep below the relevant panel or figure band.
- Accent colors: muted blue, green, orange, purple, cyan, or gray families; avoid over-saturated fills unless present in the reference.

## Chinese Technical-Bid Flowchart Tokens

Use these defaults when the user provides engineering bid, supervision, procurement, quality, schedule, or change-management flowchart screenshots and does not request a different style:

- Font: SimSun/宋体, 12 pt, not bold.
- Box shape: straight-corner rectangle by default; use rounded corners only when the user chooses original-image reproduction or explicitly requests rounded boxes.
- Box fill: `RGB(198,216,240)`.
- Box border: `RGB(0,176,240)`, 1 pt.
- Connector color: `RGB(0,170,240)`, 1 pt.
- Arrowhead: Visio end arrow type `5` (`05`), medium end arrow size `2`, connector line weight 1 pt.
- Page size: default flowchart page must not exceed `165mm x 235mm` (`6.49in x 9.25in`). Use portrait or landscape according to the reference aspect ratio, but keep the larger dimension within 235 mm and the smaller dimension within 165 mm.
- Default deliverable: save exactly one final `.vsdx` file. Do not create backup files, preview images, or secondary formats unless the user explicitly requests them.
- Batch mode: when the user sends multiple screenshots, says "continue drawing", or asks to process a series, create one `.vsdx` per reference using the same style profile.
- Batch naming: use simple sequential names such as `1.vsdx`, `2.vsdx`, `3.vsdx`; choose the next unused number and do not overwrite an existing `.vsdx` unless the user explicitly asks. Add matching preview names only when preview export is requested.
- Batch response: keep the final reply short with verified `.vsdx` file links and package inspection results unless the user asks for more explanation.

When the screenshot style conflicts with the default technical-bid style, ask the user before drawing whether to use the default style or reproduce the original image style. If the user chooses default, preserve semantic hierarchy, text labels, connector topology, and page proportions first; do not copy screenshot-only decorations such as different colors, rounded corners, bold text, or arrow styles.

## Reconstruction Order

1. Page size and canvas background.
2. Major bands, panel boxes, captions, and separators.
3. Panel calibration: record bounds for every major panel and subpanel.
4. Main dataflow arrows and module containers.
5. Text-bearing process boxes in panel-local coordinates.
6. Repeated motifs: stacks, cubes, graphs, heatmaps, mini charts, tables, icons.
7. Equations, legends, axis labels, small annotations.
8. Grouping, font normalization, overlap check, package inspection, optional preview export, and requested SVG/PDF/PPTX export.

Do not optimize small graphics before the panel grid and arrows are correct.

## Avoid These Failure Modes

- Inserting the whole reference image as the final page.
- Copying examples from this skill instead of analyzing the user's actual reference.
- Using a single ungrouped mass of hundreds of shapes with no structure.
- Recoloring by global color replacement when modules share colors with different meanings.
- Leaving Visio locked in the background after a timeout.
- Claiming success after a script times out without checking file timestamp or package contents.
- Letting text overflow boxes after changing fonts.
- Drawing all nested panel internals in global coordinates, which can create shifted rows and cross-panel overlap.
- Losing semantic editability by converting equations, graph nodes, tables, or charts into pasted crops.
- Making all modules the same palette when the reference uses color to distinguish submodules.
- Exporting SVG/PDF/PPTX from a stale file before saving the final `.vsdx`.
- Embedding raw Chinese text directly in `.ps1` scripts on Windows PowerShell when escaped Unicode is safer.
- Reporting a requested output path without checking the file actually exists in the output directory.

## Verification Rubric

Score the result before delivery:

- Structure: panel locations and flow match the reference.
- Semantics: every named module, caption, and important label exists as editable text.
- Style: colors, line weights, typography, and spacing are consistent.
- Layout: major panels and their children stay within calibrated bounds without visible overlap.
- Editability: no full-page image; major objects are native shapes.
- Outputs: the saved `.vsdx` exists; requested PNG/SVG/PDF/PPTX files, if any, are non-empty and were exported from the same saved `.vsdx`.
- Robustness: for new fast flowcharts, the final `.vsdx` exists and package checks are recorded. Create backups only when editing an existing user file or when the user asks for backups.
- Windows CJK safety: generated scripts avoid raw Chinese literals or otherwise prove they run without encoding errors.
- Batch flowchart verification: final file names are taken from the real output directory, and package inspection reports no `visio/media` full-page reference image.

If any category is weak, either fix it or state the limitation explicitly.

## Delivery Expectations

Final response should include:

- Target `.vsdx` path.
- Backup path if a backup was explicitly created.
- Preview path if a preview was explicitly exported.
- SVG/PDF/PPTX paths if requested.
- Whether the `.vsdx` file is native editable Visio shapes.
- Any caveats: unreadable labels, skipped verification, PPTX render limitations, or Visio automation issues.

For fast Chinese technical-bid batch work, use a shorter delivery format: verified `.vsdx` file paths plus native/package inspection status. Do not include backup or preview paths when those files were intentionally skipped.
