# Nature Figure Design Theory

Typography, color theory, layout rationale, and export policy for Nature-style figures.

---

## 1) Typography

### Font stack
- **Nature standard**: `font.family = 'sans-serif'`, `font.sans-serif = ['Arial']`
- **Fallback**: `['Arial', 'Helvetica', 'DejaVu Sans', 'sans-serif']`
- SVG/PDF editable text: always `svg.fonttype = 'none'`
- LaTeX math: `text.usetex = True` only when LaTeX installed and math-rich

### Font size hierarchy

| Context | font.size | axes.linewidth |
|---------|-----------|---------------|
| Dense multi-panel (publication width) | 7–9 | 0.8–1.2 |
| Large comparison bar panels (>28in wide) | 24 | 3 |
| Compact subfigures | 15–16 | 2 |
| Axis labels on large panels | 32–54 | — |
| In-bar annotations | 32–36 | — |

---

## 2) Axes & Spines

- Keep only left + bottom spines (minimalist, Nature-approved)
- No grid lines by default; sparse y-ticks guide the eye
- Frameless legends everywhere (`legend.frameon = False`)

---

## 3) Color Theory

### Semantic mapping
- Blue = proposed method (hero)
- Green = positive variants/improvements
- Red/pink = baselines/contrast
- Neutral = reference/background

### Unified-family rule (NMI-style)
Publication figures should read as **one figure**, not six unrelated plots:
- Keep related baselines in one cool family
- Keep method variants (Tiny/Base/Large) in one hero family
- Reserve green/red for arrows, gains, drops, thresholds
- Never remap same method to different hue in another panel
- When in doubt, reduce saturation before adding categories

### Ablation alpha encoding
Single color with varying alpha for component ablation:
```python
alphas = np.linspace(0.2, 1.0, n_variants)
# alpha=1.0 → full method, alpha=0.2 → minimal/ablated
```

### Modality-specific discipline
- **Imaging**: grayscale context + 1–2 fluorescent accents on black
- **Schematic/material**: derive palette from physical objects, reuse softened versions in plots
- **Clinical**: dark baseline, restrained warm/cool follow-up hues, pale background bands
- **Genomics**: neutral grey scaffolds + small number of biologically meaningful highlights

---

## 4) Layout and Composition

### Figure sizes

| Type | Typical figsize |
|------|----------------|
| Journal-width composite | (7.0–7.4, 5.5–7.8) |
| Multi-metric bar | (28–45, 6–12) |
| Compact single bar | (9–16, 5–8) |
| Trend multi-panel | (14, 4) or (9, 8) |
| Heatmap single | (8–20, 5–9) |

### Panel labels and gutters
- Small bold lowercase (a, b, c) near top-left edge
- Tight gutters; increase when dark/light modalities touch
- Extra bottom clearance for dense captions
- No decorative panel boxes — alignment and whitespace carry structure

### Legend economy
- Direct labels when regions/lines are spatially stable
- Shared legend strip above a row rather than per-panel repeats
- Dense categorical: embedded text over detached legend
- If legend exists: frameless, visually quieter than data

### Dynamic y-axis
Never fixed 0–100 when values sit in narrow band. Tighten to data range.

---

## 5) Export Policy

- **SVG primary** (editable text with `svg.fonttype='none'`)
- **PDF secondary** (LaTeX embedding)
- DPI 300 standard, 600 for dense bar panels
- `tight_layout(pad=0.5)` default; `pad=0.3` for compact multi-panel
- `bbox_inches='tight'` on all saves
- Always `plt.close(fig)` after saving

---

## 6) Reproduction Checklist

- [ ] Mandatory first lines: font.family, font.sans-serif, svg.fonttype='none'
- [ ] Save as SVG primary + PDF secondary
- [ ] Top/right spines off; frameless legend
- [ ] Architecture chosen: grid, schematic-led, image plate, or asymmetric hero
- [ ] Font size ≥ 16 base (24 for large bars)
- [ ] Colors from Nature semantic palette
- [ ] Black background only for imaging plates
- [ ] Y-limits tightened to data range
- [ ] `tight_layout(pad=0.5)` before save
- [ ] `plt.close(fig)` after save


---

<!-- modex-3 同源吸收 P3（2026-09-22）：以下段落自 modex-3-skills 上游对应文件增量合入，宿主中性化后与上文并行生效。 -->

# Nature Figure Design Theory

This reference explains the shared contract in [SKILL.md](../SKILL.md). It is a design aid,
not a claim that every Nature journal mandates one layout, palette, or font size.

## Typography and placement

Initialize with `setup_style(palette='nature')`; preserve the shared Chinese fallback fonts.
Do not replace the font list with Arial-only settings or enable external LaTeX solely for styling.
Use `set_paper_placement` with the real PDF/Word insertion constraints.

Normal text must remain at least 8pt at final size (runtime target 8.25pt).
Choose source canvas and font tiers together; do not use 28–45 inch canvases or huge source fonts
as a template. Dense figures need a reserved legend/colorbar lane, more height or related groups.
After changing height, recalculate placement because a page-height cap can also reduce width.

## Axes and meaningful scales

Left/bottom spines and restrained grids suit many line/bar/scatter plots.
Use the frame and scale appropriate for heatmaps, polar plots or geometric illustrations.
A legend-only cell has no numeric axes; a data panel still needs scale, meaning and applicable units.
Direct labels can replace a legend only when they unambiguously identify every series.

Line/point limits may follow the data, including uncertainty endpoints.
Bars normally retain a zero baseline; never tighten their axis to exaggerate a small difference.
Log axes need positive data and clearly identified units; do not add arbitrary headroom for paragraphs.

## Color semantics

Explicit user choices are authoritative, including black-and-white.
Nature's default hues are a fallback, not mandatory blue/green/red roles.
Keep each method's color consistent across panels, reinforced by line styles or hatches where useful.
Use `COLORS['text']` for ordinary text, not pastel series fills.
Contrast is assessed against the actual composited background, at least 4.5:1 for normal text.

Transparency can encode ordered variants or measured uncertainty, but must not erase distinctions.
Do not fabricate error bands; state whether the interval is SD, SE or CI in the appropriate caption/body.
Colorful labels and white strokes are not a repair for text covering data.

## Layout

Choose rows, columns or asymmetric panels from the scientific relationship, not a fixed recipe.
Comparable experiments should keep consistent encodings; novelty is not a quality criterion.
Panel labels are short and clear, usually left-aligned titles.
Give legends, colorbars and dense value columns real space instead of out-of-canvas anchors.

Use one layout system. For multi-panel figures, prefer constrained layout plus GridSpec.
Do not call `tight_layout` or `subplots_adjust` on a constrained/compressed figure.
For deliberately manual positioning set `fig._mh_manual_layout=True` and verify the whole canvas.
Shared legend helpers reserve their own space; do not subsequently reset those margins.

`bar_label`, `adjustText`, `auto_legend` and `loc='best'` offer candidate positions,
not a guarantee. Final-size checks must include adjacent panels, titles, error bars, markers and boundaries.
Use an independent zoom panel when an inset would hide required evidence.

## Export and verification

Use `save_fig` through the initialized shared runtime: PDF for LaTeX, required high-resolution PNG
for Word-only projects. SVG may be an additional editable source, not a compulsory duplicate deliverable.
Vector text is not improved by higher DPI; DPI matters for raster layers.
Do not override export with `bbox_inches='tight'` to conceal misplaced content.

Run the common code/output checks and review the final rendering.
A confirmed overlap or clipping is not a stylistic warning. An ambiguous complex background needs
review, not a fabricated pass/fail. Optional paid review remains opt-in and snapshot-cached.
Close figures after saving.

## Checklist

- [ ] Shared setup and actual placement recorded; chosen project palette retained
- [ ] Necessary scales, units, methods and uncertainty definitions remain available
- [ ] Layout fits the content; no chart-type or arbitrary canvas-size quota
- [ ] Labels keep their correct data/category associations
- [ ] Legend, colorbar and value lanes fit within the canvas and do not overlap data
- [ ] Final fonts, contrast and boundaries verified after layout settles
- [ ] Failed output is repaired within the bounded retry policy, not certified by an API name
