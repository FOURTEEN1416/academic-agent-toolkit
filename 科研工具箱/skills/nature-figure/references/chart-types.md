# Chart Types — Nature Figure Making

Specialized chart patterns beyond basic bars and trends.
Each section includes the key code pattern extracted from production scripts.

---

## Radar / Polar Chart

Used when comparing multiple methods across many benchmarks simultaneously.

```python
import numpy as np
import matplotlib.pyplot as plt

def plot_radar(methods, colors, subtask_names, value_matrix,
               benchmark_radii, display_range=(45, 90)):
    """
    Parameters
    ----------
    methods        : list[str]    — one curve per method
    colors         : list[str]
    subtask_names  : list[str]    — one spoke per subtask (may contain '\\n')
    value_matrix   : np.ndarray  — shape (n_subtasks, n_methods)
    benchmark_radii: dict         — {benchmark_name: [tick1, tick2, ...]} for normalization
    display_range  : (r_min, r_max) — polar radial display window
    """
    r_lo, r_hi = display_range
    n_subtasks = len(subtask_names)
    n_methods  = len(methods)

    fig = plt.figure(figsize=(12, 10))
    ax  = fig.add_subplot(111, projection='polar')

    # Evenly spaced angles, clockwise from top
    angles = np.linspace(2 * np.pi, 0, n_subtasks, endpoint=False)
    angles_closed = np.append(angles, angles[0])

    def _normalize(val, bench):
        radii_list = benchmark_radii.get(bench, [0, 100])
        span = max(radii_list) - min(radii_list)
        if span <= 0:
            return (r_lo + r_hi) / 2
        frac = np.clip((val - min(radii_list)) / span, 0, 1)
        return r_lo + (r_hi - r_lo) * frac

    subtask_benchmarks = [s.split('\\n', 1)[-1] if '\\n' in s else s
                          for s in subtask_names]

    # Draw data polygons
    for m in range(n_methods):
        norm_vals = np.array([_normalize(value_matrix[i, m], subtask_benchmarks[i])
                              for i in range(n_subtasks)])
        closed = np.append(norm_vals, norm_vals[0])
        ax.plot(angles_closed, closed, color=colors[m], lw=2, label=methods[m])
        ax.fill(angles_closed, closed, color=colors[m], alpha=0.05)
        ax.scatter(angles, norm_vals, color=colors[m], s=18, zorder=5)

    # Style
    ax.set_ylim(r_lo, r_hi)
    ax.set_theta_zero_location('N')
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.grid(False)

    # Outer boundary ring
    ax.plot(angles_closed, np.full_like(angles_closed, r_hi),
            color='k', lw=0.8, zorder=4)

    # Radial spokes
    for a in angles:
        ax.plot([a, a], [r_lo, r_hi], color='gray', lw=0.5, zorder=4)

    # Benchmark-level contour polygons
    max_levels = max(len(v) for v in benchmark_radii.values())
    for k in range(max_levels):
        disp = np.array([_normalize(benchmark_radii.get(b, [0,100])[
                            min(k, len(benchmark_radii.get(b,[0,100]))-1)], b)
                         for b in subtask_benchmarks])
        ax.plot(angles_closed, np.append(disp, disp[0]),
                color='k', lw=0.6, zorder=4)

    ax.set_yticks([r_hi])
    ax.set_yticklabels([])
    ax.set_xticks(angles)
    ax.set_xticklabels([])

    # Spoke labels (outside outer ring)
    for angle, label in zip(angles, subtask_names):
        r_label = r_hi + 8 + 10 * abs(np.sin(angle))
        ax.text(angle, r_label, label, fontsize=14,
                ha='center', va='center',
                transform=ax.transData, clip_on=False)

    ax.legend(loc='upper right', bbox_to_anchor=(1.40, 0.05),
              fontsize=15, frameon=False)
    return fig, ax
```

**Key settings:**
- `ax.set_theta_zero_location('N')` — top-start convention
- Remove all default spines/grid; draw custom spokes + contour polygons manually
- Normalize each spoke independently using per-benchmark tick lists
- Legend placed **outside** the plot at `bbox_to_anchor=(1.40, 0.05)`

---

## 3D Sphere / Conceptual Illustration

Used for geometric conceptual diagrams (e.g., embedding space visualization).

```python
import numpy as np
import matplotlib.pyplot as plt

def draw_shaded_sphere(ax, light_dir=(-0.5, 0.5, 0.8),
                       resolution=512, alpha=1.0,
                       extent=(-1, 1, -1, 1)):
    """Draw a 2D shaded disk that mimics a 3D sphere using ray-casting."""
    xs = np.linspace(extent[0], extent[1], resolution)
    ys = np.linspace(extent[2], extent[3], resolution)
    x, y = np.meshgrid(xs, ys)
    r2 = x**2 + y**2
    mask = r2 <= 1.0

    z = np.zeros_like(x)
    z[mask] = np.sqrt(1.0 - r2[mask])

    # Surface normals
    nx, ny, nz = x.copy(), y.copy(), z.copy()
    nrm = np.sqrt(nx**2 + ny**2 + nz**2) + 1e-6
    nx, ny, nz = nx/nrm, ny/nrm, nz/nrm

    # Lambertian shading
    ld = np.array(light_dir, dtype=float)
    ld /= np.linalg.norm(ld)
    intensity = np.maximum(0, nx*ld[0] + ny*ld[1] + nz*ld[2])

    img = np.ones_like(x)
    img[mask] = np.clip(0.2 + 0.9 * intensity[mask], 0, 1)

    ax.imshow(img, cmap='gray',
              extent=list(extent),
              vmin=0, vmax=1, alpha=alpha)
    ax.set_axis_off()
    return ax


def plot_3d_scatter_with_arrows(ax, points, grad_vectors,
                                point_color='#0c2458', arrow_color='#b64342'):
    """3D scatter plot with gradient arrow annotations."""
    from mpl_toolkits.mplot3d import proj3d
    from matplotlib.patches import FancyArrowPatch

    class Arrow3D(FancyArrowPatch):
        def __init__(self, xs, ys, zs, *args, **kwargs):
            super().__init__((0,0), (0,0), *args, **kwargs)
            self._verts3d = xs, ys, zs
        def do_3d_projection(self, renderer=None):
            xs, ys, zs = proj3d.proj_transform(*self._verts3d, self.axes.get_proj())
            self.set_positions((xs[0], ys[0]), (xs[1], ys[1]))
            return np.min(zs)

    ax.scatter(points[:, 0], points[:, 1], points[:, 2],
               s=80, color=point_color, alpha=0.5)
    for p, g in zip(points, grad_vectors):
        arrow = Arrow3D([p[0], p[0]+g[0]], [p[1], p[1]+g[1]], [p[2], p[2]+g[2]],
                        mutation_scale=16, lw=4, arrowstyle='->',
                        color=arrow_color, alpha=0.8)
        ax.add_artist(arrow)

    # Clean 3D axes
    ax.grid(False)
    ax.xaxis.pane.set_visible(False)
    ax.yaxis.pane.set_visible(False)
    ax.zaxis.pane.set_visible(False)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_zticks([])
```

---

## Scatter Plot with Color-Coded Clusters

```python
def make_scatter(ax, x, y, labels_or_colors,
                 size=50, alpha=0.7, edgecolors='none'):
    """Single or multi-cluster scatter."""
    import numpy as np
    ax.scatter(x, y, c=labels_or_colors, s=size,
               alpha=alpha, edgecolors=edgecolors)
    ax.set_axis_off()   # for conceptual diagrams; remove for data plots
```

---

## Fill-Between Area Chart (Stacked trend)

Used for cumulative publication counts, stacked contributions, etc.

```python
# Filled area (stacked) with hatch for print safety
ax.fill_between(x, 0, y_bottom,
                color='#ffa8a6', label='Category A')
ax.fill_between(x, 0, y_top,
                color='#9BC8FA',
                hatch='///',               # hatch for grayscale print
                edgecolor='black',
                label='Category B')
# Erase border artifacts
ax.fill_between(x, 0, y_top,
                facecolor='none',
                edgecolor='white',
                linewidth=2)

# Overlay the trend line for exact values
ax.plot(x, y_top, lw=3, color='#13457E')
ax.plot(x, y_bottom, lw=3, color='#850c0a')
```

---

## Log-Scale Bar Chart

```python
ax.set_yscale('log')
ymin, ymax = ax.get_ylim()
ax.set_ylim(ymin, ymax * 20)   # expand top for annotations

# Annotate values above bars
for i, val in enumerate(values):
    ax.text(i, val * 1.1, f'{val:.3f}',
            ha='center', va='bottom', fontsize=16)
```

---

## GridSpec Multi-Panel Layout

```python
from matplotlib import gridspec

# 2-row, 4-column layout
fig = plt.figure(figsize=(36, 12))
gs = gridspec.GridSpec(2, 4)

ax_top_left  = fig.add_subplot(gs[0, 0])
ax_top_right = fig.add_subplot(gs[0, 1:3])   # span columns 1-2
ax_legend    = fig.add_subplot(gs[0, 3])     # legend panel
ax_bottom    = fig.add_subplot(gs[1, :])     # full-width bottom
```

---

## Scientific Notation on Y-Axis

```python
ax.ticklabel_format(axis='y', style='sci', scilimits=(0, 0))
```

---

## Custom Spine Positioning

```python
# Move bottom spine to y=0 (for negative values)
ax.spines['bottom'].set_position(('data', 0))
ax.xaxis.set_ticks_position('bottom')
ax.spines['left'].set_bounds(0, y_max)
```

---

## Related files

- [skill.md](../skill.md) — When to use this skill
- [api.md](api.md) — PALETTE and core helper signatures
- [common-patterns.md](common-patterns.md) — Bar, trend, and layout patterns
- [design-theory.md](design-theory.md) — Rationale and color theory
- [tutorials.md](tutorials.md) — Full end-to-end walkthroughs


---

<!-- modex-3 同源吸收 P3（2026-09-22）：以下段落自 modex-3-skills 上游对应文件增量合入，宿主中性化后与上文并行生效。 -->

# Specialized Chart Types

These are structural references, not mandatory chart choices. Apply [SKILL.md](../SKILL.md)
and the shared print contract to every example. All sample values below are synthetic.
Read real data in generated paper scripts; preserve project colors and scientific meaning.

## Radar / polar comparison

Use only when normalized dimensions and their directions are meaningfully comparable.
Document normalization and bounds; do not silently clip out-of-range observations or
invent missing benchmark limits. For many methods or long labels, a dot plot or heatmap
can be clearer. A radar chart is not required just for visual variety.

This example reserves a real legend row and uses polar tick labels instead of floating
text outside the figure. Radar/polar geometry still needs final visual review.

```python

# layout-regression: polar-legend
import numpy as np
import matplotlib.pyplot as plt
from _utils.plot_utils import setup_style, set_paper_placement, save_fig, PALETTE

def plot_radar(methods, dimensions, normalized_values):
    """Values are (n_dimensions, n_methods), already justified on a [0, 1] scale."""
    values = np.asarray(normalized_values, dtype=float)
    if len(dimensions) < 3 or not methods:
        raise ValueError('Radar requires at least three dimensions and one method')
    if values.shape != (len(dimensions), len(methods)):
        raise ValueError('Radar labels and values must have matching dimensions')
    if not np.isfinite(values).all() or (values < 0).any() or (values > 1).any():
        raise ValueError('Supply finite normalized values in [0, 1]; do not clip measurements')
    fig = plt.figure(figsize=(5.7, 5.6), layout='constrained')
    set_paper_placement(fig)
    gs = fig.add_gridspec(2, 1, height_ratios=[0.16, 1])
    legend_ax = fig.add_subplot(gs[0, 0])
    ax = fig.add_subplot(gs[1, 0], projection='polar')
    angles = np.linspace(0, 2 * np.pi, len(dimensions), endpoint=False)
    closed_angles = np.r_[angles, angles[0]]
    for index, name in enumerate(methods):
        closed_values = np.r_[values[:, index], values[0, index]]
        color = PALETTE[index % len(PALETTE)]
        ax.plot(closed_angles, closed_values, color=color,
                linestyle=['-', '--', ':', '-.'][index % 4], label=name)
    ax.set_theta_zero_location('N')
    ax.set_theta_direction(-1)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.25, 0.5, 1])  # Sparse reference ticks; retain the full [0, 1] scale.
    ax.set_rlabel_position(180)  # This example has a clear lower inner region; recheck real data.
    ax.set_xticks(angles, dimensions)
    ax.tick_params(axis='x', pad=24)
    legend_ax.legend(*ax.get_legend_handles_labels(), loc='center',
                     ncol=min(len(methods), 3), frameon=False)
    legend_ax.set_axis_off()
    return fig, ax

setup_style(palette='nature')
fig, ax = plot_radar(['Method A', 'Method B'],
                    ['Accuracy', 'Speed', 'Stability', 'Efficiency'],
                    [[0.72, 0.64], [0.66, 0.78], [0.85, 0.68], [0.60, 0.73]])
save_fig(fig, 'figures/fig_layout_polar.pdf')
plt.close(fig)
```

## 3D geometry or conceptual illustrations

A geometric illustration may use sparse labels and short formulas; quantitative 3D data
need visible scales, axis names and units. Do not hide every tick by default.
Choose the view to separate relevant objects; a dense projection may need a second view.
Do not annotate every point or place conclusions inside the scene.

```python

# points and vectors are real, aligned (n, 3) arrays.
ax.scatter(points[:, 0], points[:, 1], points[:, 2], color=PALETTE[0])
ax.quiver(points[:, 0], points[:, 1], points[:, 2],
          vectors[:, 0], vectors[:, 1], vectors[:, 2],
          color=PALETTE[1], normalize=False)

# Use physical axis names/units from the model; review the chosen projection.
```

Do not rely on 2D label relocation for 3D geometry; verify the rendered camera view.
For conceptual geometry without numerical results, identify objects with only necessary names/formulas.

## Scatter plots

```python
ax.scatter(x, y, c=series_colors, s=30, alpha=0.65)
ax.set_xlabel(x_name_with_unit)
ax.set_ylabel(y_name_with_unit)
```

Keep a scale or a justified direct encoding. Do not hide axes on measured data merely to resemble an illustration.
For dense clouds, transparency, aggregation or marginal panels may help; do not drop inconvenient points.
A geometric/schematic plate may omit numeric ticks when a scale bar or other context is sufficient.

## Stacked trends

Use cumulative boundaries correctly. Do not draw every component from zero and cover the previous
layer, or erase boundaries with white overpainting.

```python

# x and nonnegative components are read from real data.
components = np.asarray(components, dtype=float)
if components.ndim != 2 or components.shape[1] != len(x):
    raise ValueError('Each component must align with x')
if not np.isfinite(components).all() or (components < 0).any():
    raise ValueError('This stacked-area recipe requires finite nonnegative components')
ax.stackplot(x, components, labels=component_names,
             colors=[PALETTE[i % len(PALETTE)] for i in range(len(components))], alpha=0.65)

# Place the component legend in a reserved lane; use another recipe for signed contributions.
```

## Log-scale values

Use a log scale only for positive data with a meaningful ratio interpretation. If values span
many orders of magnitude, points/intervals often avoid the misleading zero baseline of log bars.
Do not multiply the upper limit by 20 just to make room for annotations.

```python
values = np.asarray(values, dtype=float)
if not np.isfinite(values).all() or (values <= 0).any():
    raise ValueError('Log-scale values must be finite and positive')
ax.plot(np.arange(len(values)), values, 'o', color=PALETTE[0])
ax.set_yscale('log')
ax.set_xticks(np.arange(len(values)), category_names)

# Include real interval endpoints if present; check ticks at final print size.
```

## Asymmetric GridSpec layout

Give the important comparison more room, without fixing every paper to one architecture.

```python
fig = plt.figure(figsize=(6.4, 4.8), layout='constrained')
set_paper_placement(fig)
gs = fig.add_gridspec(3, 2, height_ratios=[0.18, 1, 1.1])
legend_ax = fig.add_subplot(gs[0, :])
left = fig.add_subplot(gs[1, 0])
right = fig.add_subplot(gs[1, 1])
summary = fig.add_subplot(gs[2, :])
legend_ax.set_axis_off()

# Populate every data cell from actual results; legend_ax is not a data cell.
```

## Scientific notation and spines

```python

# Linear numeric axes only; preserve readable scale factors and units.
ax.ticklabel_format(axis='y', style='sci', scilimits=(0, 0))
```

A spine at zero can help signed data, but must not cross numeric labels or hide negative ranges.
Prefer an unobtrusive zero reference line when moving a spine would confuse the reader.
