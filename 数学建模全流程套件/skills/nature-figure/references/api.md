# API Reference — Nature Figure Making

Constants, helper function signatures, and validation rules for Nature-style figures.

---

## Constants

### PALETTE (Nature default)

```python
PALETTE = {
    "blue_main":      "#0F4D92",   # deep blue — hero method
    "blue_secondary": "#3775BA",   # medium blue — second method
    "green_1": "#DDF3DE",          # light positive
    "green_2": "#AADCA9",          # mid positive
    "green_3": "#8BCF8B",          # strong positive
    "red_1":   "#F6CFCB",          # light baseline
    "red_2":   "#E9A6A1",          # mid baseline
    "red_strong": "#B64342",       # strong baseline/negative
    "neutral_light": "#CFCECE",
    "neutral_mid":   "#767676",
    "neutral_dark":  "#4D4D4D",
    "neutral_black": "#272727",
    "gold":   "#FFD700",
    "teal":   "#42949E",
    "violet": "#9A4D8E",
    "magenta":"#EA84DD",
}

DEFAULT_COLORS = [
    PALETTE["blue_main"],
    PALETTE["green_3"],
    PALETTE["red_strong"],
    PALETTE["teal"],
    PALETTE["violet"],
    PALETTE["neutral_light"],
]
```

### PALETTE_NMI_PASTEL (unified-family figures)

```python
PALETTE_NMI_PASTEL = {
    "baseline_dark": "#484878",
    "baseline_mid":  "#7884B4",
    "baseline_soft": "#B4C0E4",
    "ours_tiny":  "#E4E4F0",
    "ours_base":  "#E4CCD8",
    "ours_large": "#F0C0CC",
    "bg_lilac": "#E0E0F0",
    "bg_aqua":  "#E0F0F0",
    "bg_peach": "#F0E0D0",
    "neutral_light": "#D8D8D8",
    "neutral_mid":   "#A8A8A8",
    "neutral_dark":  "#606060",
    "delta_up":   "#2E9E44",
    "delta_down": "#E53935",
}

DEFAULT_COLORS_NMI_PASTEL = [
    "#484878", "#7884B4", "#B4C0E4",
    "#E4E4F0", "#E4CCD8", "#F0C0CC",
]
```

### Domain-specific palettes

```python
PALETTE_NATURE_IMAGING = {
    "bg": "#000000", "context": "#B8B8B8",
    "cyan": "#22D7E6", "magenta": "#FF2AD4", "white": "#FFFFFF",
}

PALETTE_NATURE_MATERIAL = {
    "aqua": "#77D7D1", "teal": "#33B5A5",
    "lilac": "#B9A7E8", "violet": "#7C6CCF",
    "callout_red": "#E53935", "neutral": "#D9D9D9",
}

PALETTE_NATURE_CLINICAL = {
    "baseline": "#272727", "week6": "#E28E2C",
    "week13": "#D24B40", "week26": "#5B8FD6",
    "year1": "#7BAA5B", "year2": "#C45AD6",
    "group_band": "#F2E6D9",
}

PALETTE_NATURE_GENOMICS = {
    "neutral_light": "#D8D8D8", "neutral_mid": "#8F8F8F",
    "wave1": "#D9544D", "wave2": "#5B7FCA",
    "wave3": "#B89BD9", "outline": "#4D4D4D",
}
```

---

## Helper Function Signatures

### apply_publication_style(font_size=16, axes_linewidth=2.5, use_tex=False)

Apply Nature-style rcParams. Call once before creating any figures.

Presets:
- Large bar panels: `apply_publication_style(font_size=24, axes_linewidth=3)`
- Compact figures: `apply_publication_style(font_size=15, axes_linewidth=2)`
- Dense multi-panels: `apply_publication_style(font_size=8, axes_linewidth=1)`

### add_panel_label(ax, label, x=-0.06, y=1.02, fontsize=14, color='black', fontweight='bold')

Place Nature-style panel label (a, b, c) near top-left edge.
For dark plates: `add_panel_label(ax, 'a', x=0.01, y=0.98, color='white')`

### is_dark(hex_color, threshold=128) → bool

Return True if hex color is dark (use white text on it).

### style_dark_image_ax(ax, facecolor='black') → ax

Prepare axes for microscopy/rendering plates. Removes ticks and spines.

### make_grouped_bar(ax, categories, series, labels, ylabel, colors, annotate, bar_width, error_kw) → list[BarContainer]

Grouped bar chart. `categories`: x-axis names (K). `series`: list of arrays (each K). `colors` defaults to DEFAULT_COLORS.

### make_trend(ax, x, y_series, labels, colors, ylabel, xlabel, show_shadow, shadow_alpha, lw, marker, markersize)

Multi-line trend plot. `show_shadow=True` fills ±std if y_series contains 2D arrays.

### make_forest_plot(ax, labels, estimates, ci_low, ci_high, colors, ref, xlabel, xlim, marker, markersize, lw)

Forest plot for clinical/statistical panels. Vertical reference line at `ref`.

### make_heatmap(ax, matrix, x_labels, y_labels, cmap, cbar_label, annotate, fmt, fontsize)

2D heatmap with optional colorbar and cell annotations. Auto text contrast.

### finalize_figure(fig, out_path, formats=None, dpi=300, pad=2, bbox_inches=None, close=True) → list[str]

Apply tight_layout and save. `formats=['svg', 'pdf']` for Nature standard.

---

## Validation Rules

- `make_grouped_bar`: `len(categories)` == length of each array in `series`
- `make_trend`: each array in `y_series` same length as `x`
- `make_heatmap`: `matrix` 2D; `x_labels` length == `matrix.shape[1]`; `y_labels` length == `matrix.shape[0]`
- `finalize_figure`: supported formats — `png`, `pdf`, `svg`, `eps`, `jpg`, `tif`

---

## Conventions

- Save under `./figures/`; `finalize_figure` creates parent dirs
- Headless/batch: `matplotlib.use('Agg')` before importing pyplot
- Always `plt.close(fig)` after saving
- One baseline family + one hero family per figure; reserve green/red for delta cues
- SVG primary, PDF secondary — never PNG alone when text needs adjustment
