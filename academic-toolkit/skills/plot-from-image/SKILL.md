---
name: plot-from-image
description: "有参考图时反推字体、取色、比例与坐标，产出可复现的绘图代码。触发词：照着这张图画、复现这张图、模仿这个配色和字体、从图片提取绘图参数。"
---

# Plot From Image

Reproduce a paper figure by analyzing the image and leveraging accumulated style knowledge.

## Workflow

### 1. Measure Proportions

```python
python3 -c "from PIL import Image; img=Image.open('fig.png'); print(img.size, f'AR={img.size[0]/img.size[1]:.2f}')"
```

Set `figsize=(FW, FH)` so `FW/FH` matches the original AR exactly. Keep `FW` at or below 8 in for a 5.5 in single-column placement: `save_fig` raises source text to hold the 8.25 pt print floor, so wider canvases inflate every label.

### 2. Match to Existing Style

Check if the figure matches a pre-built style (fastest path):

| Figure type | Check for |
|-------------|-----------|
| Grouped/paired bar | `bar_paired_delta` or `bar_grouped_hatch` |
| Line with shaded bands | `line_confidence_band` |
| Line with cut lines or reference | `line_training_curve` |
| Loss curve + zoom panel | `line_loss_with_inset` |
| Scattered clusters | `scatter_tsne_cluster` |
| Broken x-axis | `scatter_broken_axis` |
| Polygon web chart | `radar_dual_series` |

If matched → read `academic-toolkit/skills/plot-from-data/references/<name>.md` for the chart-type parameters (colors, spines, layout) → adapt `academic-toolkit/skills/plot-from-data/scripts/<script>.py`.

The eight figure templates are thin shells: they import `setup_style`, `save_fig` and `set_paper_placement` from `academic-toolkit/skills/_utils/plot_utils.py` and keep only chart-type syntax. Do not re-add `plt.rcParams`, per-element `fontsize=`, or `bbox_inches='tight'` — typography, the print-size floor and save guards belong to the shared library. When a script is copied outside the repo, put `academic-toolkit/skills` on `PYTHONPATH` (the in-repo copy resolves it from `__file__`).

### 3. If No Match → Analyze From Scratch

Read `academic-toolkit/skills/plot-from-image/references/reproduction_guide.md` for the full analysis checklist covering:
- Font family detection — record it for fidelity notes only; rendering is owned by `setup_style`
- Spine & tick style (L-shape, 4-sided, arrows, in/out direction)
- Color identification (tab10 vs custom)
- Grid style (dashed, dotted, none)
- Special elements (insets, broken axes, radar grids, annotation boxes)

### 4. Build & Iterate

```
Write script → python3 <script>.py → visually compare → fix proportions/colors → re-run
```

End every script with `set_paper_placement(fig)` + `save_fig(fig, 'figures/fig_<name>.png')`. `save_fig` writes the file, raises source text to the print-size floor and refuses exports with text-over-data occlusion or clipped labels.

Key iteration checklist:
- [ ] AR matches original (measure with PIL)
- [ ] Typography from the shared library: no `rcParams`/`fontsize`/`bbox_inches` overrides in the script
- [ ] Colors within ±10 RGB of original
- [ ] Spine style matches (L vs 4-sided)
- [ ] Tick direction matches (in vs out)
- [ ] Grid style matches
- [ ] Legend placement matches
- [ ] Annotations/labels position matches
- [ ] `save_fig` completes without occlusion/clipping errors

## Accumulated Experience

From 9 reproduced figures across 7 papers, key lessons:

- **Smooth training curves**: use EMA with `alpha=0.95-0.97` before plotting, not raw noisy data
- **Radar labels**: keep category labels outside the value labels (`label_r = 1.30`, `ylim = 1.50`); the print-size floor enlarges value labels, so 1.10-1.15 collides with them
- **Inset figures**: measure left/right panel pixel ratio from original → set `add_axes` widths accordingly
- **Broken axis**: use two subplots with `wspace=0.05`, break symbol only at bottom spine
- **t-SNE labels**: in-plot annotation boxes are rejected by the occlusion gate (text over markers); identify clusters with the legend instead
- **Confidence bands**: `fill_between` with `alpha=0.18-0.22`, same color as line

## Resources

- **Analysis guide**: `academic-toolkit/skills/plot-from-image/references/reproduction_guide.md` — step-by-step checklist for new images
- **Style library**: `academic-toolkit/skills/plot-from-data/references/` — 13 style cards
- **Script templates**: `academic-toolkit/skills/plot-from-data/scripts/` — 8 figure scripts + 1 table script (`table_classwise_iou.py`)
- **Originals**: `vendor/forks/paper-plot-skills/originals/` — reference figures used in development (read-only)
