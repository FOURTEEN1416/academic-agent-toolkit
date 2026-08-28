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
