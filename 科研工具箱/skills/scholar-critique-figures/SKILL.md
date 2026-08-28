---
name: critique-figures
user_invocable: true
description: Critique academic figures for format, colorblind safety, legibility, overplotting, and category count. Use when reviewing figures before submission.
---

# critique-figures — Figure Quality Review

Systematically review academic figures and flag common issues that hurt readability, accessibility, and print quality.

## When to Use

- "check my figures", "critique figures", "review figures before submission"
- Before submitting a paper to a journal or conference
- Called by the `presubmit-checks` skill as one of its checks (future)

## Workflow

### 1. Find figures

Search in this order:

1. User-provided path(s) — file or directory
2. If a manuscript is present, resolve figure files referenced by `\includegraphics`, `\includesvg`, `\includestandalone`, and figure-related `\input` commands in the TeX tree
3. If no manuscript is found, fall back to `figures/`, `fig/`, then a recursive search for figure files in the paper directory (exclude `node_modules`, `.git`, and build artifacts)

Only ask the user to confirm the figure list if multiple candidate manuscripts are found or the resolved figure set looks suspiciously broad.

### 2. Programmatic pre-checks

Run these checks per figure using Bash:

#### File format / resolution check

Classify each figure as:

- **Vector-native**: `.pdf`, `.svg`, `.eps`
- **Raster**: `.png`, `.jpg`, `.jpeg`, `.tiff`, `.gif`, `.bmp`
- **Mixed**: vector container with raster components

Do not decide acceptability from extension alone.

- **Flag** raster figures if the content is primarily plots or charts, line art, diagrams or schematics, network visualizations, or other text-heavy graphics. For these figure types, raster export is usually the wrong format even at high DPI.
- **Recommendation**: "Regenerate this figure as a vector export (PDF, SVG, or EPS)."

Raster is acceptable when the content is inherently image-based, such as microscopy, medical imaging, satellite or photographic imagery, screenshots, or other pixel-native data products.

- **Warn** if an acceptable raster figure appears too low-resolution at its likely final print size
- **Recommendation**: "Use a higher-resolution export. As a rule of thumb, photographic content should usually be at least ~300 DPI at final size, and line art or text-heavy raster content should usually be at least ~600 DPI."

#### Bitmap-in-PDF check

For `.pdf` figures only, run:

```bash
pdfimages -list <figure.pdf>
```

Interpretation:

- No embedded images: **Pass**
- Embedded images present: the PDF contains raster components
- Do not treat embedded images alone as a failure; many good figures mix vector text or axes with raster panels

Only **flag** if the PDF appears to be essentially a raster wrapper rather than a genuinely mixed figure.

- **Flag**: "This PDF appears to be mostly a raster image wrapped in a PDF container."
- **Recommendation**: "Regenerate the figure from source code to produce native vector output, or use a clearly intentional high-resolution raster format."

If `pdfimages` is not installed, note this and skip the check (do not fail the whole review).

### 3. Vision checks

Read each figure image using the Read tool and evaluate the following. For each check, provide a clear pass/flag verdict with explanation.

**Subpanels**: Many academic figures contain multiple panels (a, b, c, ...). When a figure has subpanels, evaluate each panel individually — one panel may have issues while others are fine. Reference specific panels in flags (e.g., "panel (c) is overplotted"). Also check that panels are clearly labeled (a, b, c or A, B, C) — unlabeled panels make it hard to reference from the text.

#### Colorblind risk

Examine the colors used to distinguish data categories or encode information.

- **Flag** if red and green are used as primary distinguishing colors (the most common form of color vision deficiency is red-green)
- **Flag** if the figure relies solely on color to distinguish elements (no pattern, shape, or label differences)
- **Recommendation**: "Use a colorblind-safe palette (e.g., Okabe-Ito, viridis, cividis). Add redundant encoding — vary shapes, line styles, or patterns in addition to color."

#### Too many categories

Count the number of distinct categorical colors or legend entries.

- **Flag** if there are more than 5-6 distinct categories encoded by color
- **Recommendation**: "Reduce the number of categories displayed simultaneously. Consider grouping minor categories into 'Other', using small multiples (facets), or highlighting only the key categories while graying out the rest."

#### Font legibility

Assess whether text elements (axis labels, tick labels, legend text, annotations) are legible at the figure's likely print size (typically a single column ~3.5 in or double column ~7 in).

- **Flag** if any text appears too small to read comfortably — a rough threshold is below ~8 pt at final print size
- **Flag** if text is noticeably smaller than typical body text
- **Recommendation**: "Increase font sizes for [specific elements]. As a rule of thumb, the smallest text in a figure should be no smaller than the caption font size."

#### Overplotted scatterplot

If the figure is a scatterplot (or similar point-based plot):

- **Flag** if there are so many overlapping points that the underlying structure or density is impossible to discern
- **Recommendation**: "Consider replacing with a 2D histogram (heatmap), hexbin plot, or density contour plot to reveal structure. If a scatterplot is preferred, use alpha transparency and/or smaller point sizes."

#### Dynamite plot

A "dynamite plot" is a bar chart with error bars used to show point estimates and uncertainty. It hides individual data points and the underlying distribution, and the bar's visual metaphor of physical accumulation is misleading (especially with non-zero baselines or log scales).

- **Flag** if the figure uses bar charts with error bars to display summary statistics of continuous data
- **Recommendation**: "Consider replacing with a dot plot (point-range plot), strip plot, or violin plot. These show the same point estimate and uncertainty while revealing the underlying distribution. Show individual data points when feasible."

### 4. Report

Present a per-figure report in this format:

```
## Figure: <filename>

| Check | Verdict | Notes |
|-------|---------|-------|
| File format / resolution | PASS / WARN / FLAG | ... |
| Raster-components-in-PDF | PASS / FLAG / SKIP | ... |
| Colorblind risk | PASS / FLAG | ... |
| Category count | PASS / FLAG | ... |
| Font legibility | PASS / FLAG | ... |
| Overplotted scatter | PASS / FLAG / N/A | ... |
| Dynamite plot | PASS / FLAG / N/A | ... |

**Recommendations:**
- ...
```

After all figures, provide a summary count: N figures reviewed, N flags total.

## Rules

- **Report only** — do not modify figures or source code
- For each flag, always provide a concrete, actionable recommendation
- If the user provides or mentions source code for a figure, use it to inform the analysis, but do not search the codebase for source code unprompted
- Run all checks on all figures even if one check or figure fails
- Use **WARN** for borderline cases or acceptable raster figures with likely resolution concerns; reserve **FLAG** for genuine problems
- Be calibrated — don't flag things that aren't actually problems. "Possibly fine but worth checking" is a valid verdict for borderline cases
- If a figure contains photographic/imaging content (microscopy, satellite, medical), raster format is expected — do not flag the format
