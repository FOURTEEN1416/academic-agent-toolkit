# Tutorials — Nature Figure Making

End-to-end walkthroughs for the most common publication figure types.
All examples use helpers from [api.md](api.md) and patterns from [common-patterns.md](common-patterns.md).

---

## Tutorial 1: Grouped bar chart (multi-metric comparison)

**Goal**: Several methods compared across multiple metrics. Legend in a dedicated panel.
When methods belong to related families, use one coherent baseline family plus one coherent hero family.

```python
import os
import numpy as np
import matplotlib.pyplot as plt
# 引用 plot_utils.save_fig（与 SKILL.md 推荐写法一致）
# 如果运行环境没准备 _utils，按 SKILL.md 顶部脚本先复制 plot_utils.py 到 _utils/
try:
    from _utils.plot_utils import save_fig
except ImportError:
    def save_fig(fig, path):  # fallback：本地 inline 实现
        import os
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        fig.savefig(path, dpi=300, bbox_inches='tight'); plt.close(fig)
from matplotlib import gridspec

# --- Style ---
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['Arial']
plt.rcParams['svg.fonttype'] = 'none'
plt.rcParams['font.size'] = 24
plt.rcParams['axes.spines.right'] = False
plt.rcParams['axes.spines.top'] = False
plt.rcParams['axes.linewidth'] = 3

# --- Data ---
methods = ['ResNet1d18', 'ResNet1d34', 'ECGFounder', 'CSFM-Tiny', 'CSFM-Base', 'CSFM-Large']
colors  = ['#484878', '#7884B4', '#B4C0E4', '#E4E4F0', '#E4CCD8', '#F0C0CC']
metrics = ['Metric 1', 'Metric 2', 'Metric 3']
mean = {
    'Metric 1': np.array([0.81, 0.83, 0.86, 0.89, 0.91, 0.92]),
    'Metric 2': np.array([0.63, 0.67, 0.71, 0.74, 0.77, 0.79]),
    'Metric 3': np.array([0.41, 0.45, 0.49, 0.53, 0.56, 0.58]),
}
std  = {k: v * 0.03 for k, v in mean.items()}  # placeholder

# --- Figure ---
fig = plt.figure(figsize=(28, 6))
gs = gridspec.GridSpec(1, len(metrics) + 1)  # +1 for legend panel

handles, labels = None, None
for col, metric in enumerate(metrics):
    ax = fig.add_subplot(gs[col])
    bars = ax.bar(
        range(len(methods)),
        mean[metric],
        yerr=std[metric],
        capsize=5,
        color=colors,
        label=methods,
        error_kw={'elinewidth': 2, 'capthick': 2},
    )
    if col == 0:
        handles, labels = ax.get_legend_handles_labels()
    ax.set_xticks([])
    y_vals = mean[metric]
    margin = (y_vals.max() - y_vals.min()) * 0.15
    ax.set_ylim([y_vals.min() - margin, y_vals.max() + margin])
    ax.set_ylabel(metric, fontsize=32)

# Legend-only panel
ax_leg = fig.add_subplot(gs[-1])
ax_leg.legend(handles, labels, fontsize=28, loc='center', frameon=False)
ax_leg.set_axis_off()

fig.tight_layout(pad=2)
os.makedirs('./figures', exist_ok=True)
save_fig(fig, './figures/comparison.pdf')
```

---

## Tutorial 2: Ablation bar chart (alpha-graduated, horizontal)

**Goal**: Same method with components progressively added; alpha encodes completeness.

```python
import os
import numpy as np
import matplotlib.pyplot as plt
# 引用 plot_utils.save_fig（与 SKILL.md 推荐写法一致）
# 如果运行环境没准备 _utils，按 SKILL.md 顶部脚本先复制 plot_utils.py 到 _utils/
try:
    from _utils.plot_utils import save_fig
except ImportError:
    def save_fig(fig, path):  # fallback：本地 inline 实现
        import os
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        fig.savefig(path, dpi=300, bbox_inches='tight'); plt.close(fig)

plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['Arial']
plt.rcParams['svg.fonttype'] = 'none'
plt.rcParams['font.size'] = 24
plt.rcParams['axes.spines.right'] = False
plt.rcParams['axes.spines.top'] = False
plt.rcParams['axes.linewidth'] = 3

configs = ['None', '+ Module A', '+ Module B', '+ Module C', 'Full']
values  = np.array([0.72, 0.78, 0.81, 0.84, 0.88])
stds    = np.array([0.02, 0.02, 0.01, 0.01, 0.01])

n = len(configs)
blue_rgb = (0.215686, 0.458824, 0.729412)   # #3775BA
alphas = np.linspace(0.2, 1.0, n)
colors = [(blue_rgb[0], blue_rgb[1], blue_rgb[2], a) for a in alphas]

fig, ax = plt.subplots(figsize=(12, 6))
ax.barh(range(n), values, xerr=stds,
        color=colors, ecolor='k', capsize=5)
ax.set_yticks(range(n))
ax.set_yticklabels(configs)
ax.set_xlim([values.min() - 0.05, values.max() + 0.03])
ax.set_xlabel('Score', fontsize=32)

fig.tight_layout(pad=2)
os.makedirs('./figures', exist_ok=True)
save_fig(fig, './figures/ablation.pdf')
```

---

## Tutorial 3: Multi-panel trend with shared legend

**Goal**: Two trend panels (e.g., train/val curves) and a legend-only third panel.

```python
import os
import numpy as np
import matplotlib.pyplot as plt
# 引用 plot_utils.save_fig（与 SKILL.md 推荐写法一致）
# 如果运行环境没准备 _utils，按 SKILL.md 顶部脚本先复制 plot_utils.py 到 _utils/
try:
    from _utils.plot_utils import save_fig
except ImportError:
    def save_fig(fig, path):  # fallback：本地 inline 实现
        import os
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        fig.savefig(path, dpi=300, bbox_inches='tight'); plt.close(fig)

plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['Arial']
plt.rcParams['svg.fonttype'] = 'none'
plt.rcParams['font.size'] = 15
plt.rcParams['axes.spines.right'] = False
plt.rcParams['axes.spines.top'] = False
plt.rcParams['axes.linewidth'] = 2

methods = ['Baseline', 'CSFM-Tiny', 'CSFM-Base', 'CSFM-Large']
colors  = ['#7884B4', '#E4E4F0', '#E4CCD8', '#F0C0CC']
x = np.arange(0, 100, 5)

fig, axes = plt.subplots(1, 3, figsize=(18, 5))

for panel_idx, (ax, panel_name) in enumerate(zip(axes[:2], ['Training', 'Validation'])):
    for method, color in zip(methods, colors):
        y = 0.48 + 0.42 * (1 - np.exp(-x / 30)) + np.random.randn(len(x)) * 0.01
        if method == 'Baseline':
            y -= 0.03
        elif method == 'CSFM-Tiny':
            y += 0.00
        elif method == 'CSFM-Base':
            y += 0.02
        elif method == 'CSFM-Large':
            y += 0.03
        ax.plot(x, y, color=color, lw=2.5, marker='o', markersize=6, label=method)
    ax.set_title(panel_name, fontsize=18)
    ax.set_xlabel('Epoch', fontsize=16)
    ax.set_ylabel('Loss', fontsize=16)
    if panel_idx == 0:
        handles, labels = ax.get_legend_handles_labels()

# Legend-only panel
axes[2].legend(handles, labels, fontsize=14, loc='center', frameon=False)
axes[2].set_axis_off()

fig.tight_layout(pad=2)
os.makedirs('./figures', exist_ok=True)
save_fig(fig, './figures/trends.pdf')
```

---

## Tutorial 4: Heatmap with dual colormaps (positive/negative columns)

**Goal**: Score matrix where positive = Reds, negative = Blues_r. Cell text auto-contrasted.

```python
import os
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
# 引用 plot_utils.save_fig（与 SKILL.md 推荐写法一致）
# 如果运行环境没准备 _utils，按 SKILL.md 顶部脚本先复制 plot_utils.py 到 _utils/
try:
    from _utils.plot_utils import save_fig
except ImportError:
    def save_fig(fig, path):  # fallback：本地 inline 实现
        import os
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        fig.savefig(path, dpi=300, bbox_inches='tight'); plt.close(fig)

plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['Arial']
plt.rcParams['svg.fonttype'] = 'none'
plt.rcParams['font.size'] = 16
plt.rcParams['axes.spines.right'] = False
plt.rcParams['axes.spines.top'] = False
plt.rcParams['axes.linewidth'] = 2

# matrix: rows = methods, cols = metrics (alternating positive/negative directions)
methods = ['Method A', 'Method B', 'Method C', 'Method D']
metrics = ['Score (+)', 'Error (-)', 'F1 (+)', 'Loss (-)']
matrix  = np.array([
    [0.88,  0.12,  0.85,  0.20],
    [0.81,  0.18,  0.78,  0.28],
    [0.75,  0.25,  0.72,  0.35],
    [0.70,  0.30,  0.68,  0.40],
])

fig, ax = plt.subplots(figsize=(10, 6))
n_rows, n_cols = matrix.shape
vmin, vmax = matrix.min(0), matrix.max(0)

for j in range(n_cols):
    is_positive = (j % 2 == 0)
    cmap = plt.cm.Reds if is_positive else plt.cm.Blues_r
    cmap = cmap.copy()
    norm = mpl.colors.Normalize(
        vmin=0 if is_positive else vmax[j],
        vmax=vmax[j] if is_positive else 0
    )
    ax.imshow(matrix[:, j:j+1], cmap=cmap, norm=norm,
              aspect='auto', extent=[j-0.5, j+0.5, 0, n_rows], origin='lower')

for (i, j), val in np.ndenumerate(matrix):
    is_positive = (j % 2 == 0)
    cmap = plt.cm.Reds if is_positive else plt.cm.Blues_r
    norm = mpl.colors.Normalize(vmin=0 if is_positive else vmax[j],
                                 vmax=vmax[j] if is_positive else 0)
    r, g, b, _ = cmap(norm(val))
    lum = 0.299*r + 0.587*g + 0.114*b
    color = 'white' if lum < 0.5 else 'black'
    ax.text(j, i + 0.5, f'{val:.2f}', ha='center', va='center',
            fontsize=13, color=color)

ax.set_xlim(-0.5, n_cols - 0.5)
ax.set_xticks(np.arange(n_cols))
ax.set_xticklabels(metrics, rotation=30, ha='right', fontsize=14)
ax.tick_params(axis='x', bottom=False, top=False, length=0)
ax.set_yticks(np.arange(n_rows) + 0.5)
ax.set_yticklabels(methods, fontsize=14)
ax.set_frame_on(False)
ax.invert_yaxis()

fig.tight_layout(pad=2)
os.makedirs('./figures', exist_ok=True)
save_fig(fig, './figures/heatmap.pdf')
```

---

## Related files

- [skill.md](../skill.md) — When to use this skill
- [api.md](api.md) — Reusable helper implementations
- [common-patterns.md](common-patterns.md) — Layout and encoding patterns used above
- [design-theory.md](design-theory.md) — Why these choices exist
- [chart-types.md](chart-types.md) — Radar, 3D sphere, scatter, fill_between


---

<!-- modex-3 同源吸收 P3（2026-09-22）：以下段落自 modex-3-skills 上游对应文件增量合入，宿主中性化后与上文并行生效。 -->

# Tutorials — publication layout with the real shared helpers

These runnable examples use **synthetic demonstration data**, not evidence for a paper.
Replace it with verified project data. They demonstrate layout, not mandatory chart types.
Prepare `_utils/plot_utils.py` using SKILL.md; missing helpers are a setup error, not permission to bypass guards.
All examples preserve the project's selected palette through `setup_style(palette='nature')`.
Use the default skill's `setup_style()` for the default style. Never combine both in one script.

## 1. Three related metrics, with a separate legend cell

The fourth cell belongs to the legend; it must not overwrite the third metric.
Bar lengths use a zero baseline, and error ranges are included in the limits.
For real data, derive the displayed uncertainty from repeated experiments and describe its meaning in the caption.

```python
import numpy as np
import matplotlib.pyplot as plt
from _utils.plot_utils import setup_style, PALETTE, save_fig, set_paper_placement, dynamic_limits

setup_style(palette='nature')
methods = ['Method A', 'Method B', 'Method C', 'Method D']
metrics = ['Accuracy', 'Recall', 'F1']
means = np.array([[.81, .83, .86, .89], [.63, .67, .71, .74], [.71, .73, .78, .80]])
sd = np.full_like(means, .015)  # synthetic SD, not a claimed confidence interval
fig, axes = plt.subplots(2, 2, figsize=(6.5, 4.8), layout='constrained')
set_paper_placement(fig, width_fraction=.9)
for i, ax in enumerate(axes.flat[:3]):
    bars = ax.bar(np.arange(4), means[i], yerr=sd[i], color=PALETTE[:4],
                  capsize=2, label=methods)
    if i == 0:
        handles, labels = ax.get_legend_handles_labels()
    ax.set_xticks([])
    ax.set_ylabel(metrics[i])
    dynamic_limits(ax, y=np.r_[means[i] - sd[i], means[i] + sd[i]], include_zero=True)
axes.flat[3].set_axis_off()
axes.flat[3].legend(handles, labels, loc='center', frameon=False)
save_fig(fig, 'figures/fig_comparison.pdf')
```

## 2. Ordered component comparison

Do not truncate a bar baseline to magnify a small difference. If differences need emphasis,
use a dot-and-interval chart with an explicitly labelled scale instead.

```python
import numpy as np
import matplotlib.pyplot as plt
from _utils.plot_utils import setup_style, PALETTE, save_fig, set_paper_placement, dynamic_limits

setup_style(palette='nature')
configs = ['Base', '+ A', '+ B', 'Full']
values = np.array([.72, .78, .81, .88])
sd = np.array([.02, .02, .01, .01])  # synthetic SD
fig, ax = plt.subplots(figsize=(6, 3.5), layout='constrained')
set_paper_placement(fig, width_fraction=.9)
ax.barh(configs, values, xerr=sd, color=PALETTE[0], capsize=2)
dynamic_limits(ax, x=np.r_[values - sd, values + sd], include_zero=True)
ax.set_xlabel('Score')
save_fig(fig, 'figures/fig_components.pdf')
```

## 3. Repeated-experiment trajectories

Only two related panels, one separate legend row. The shaded range below is mean ± sample SD;
never invent uncertainty for a single deterministic run. Do not label every time point.

```python
import numpy as np
import matplotlib.pyplot as plt
from _utils.plot_utils import setup_style, PALETTE, save_fig, set_paper_placement, uncertainty_band

setup_style(palette='nature')
rng = np.random.default_rng(7)  # reproducible synthetic demo
x = np.arange(40)
fig = plt.figure(figsize=(6.5, 3.8), layout='constrained')
set_paper_placement(fig, width_fraction=.9)
gs = fig.add_gridspec(2, 2, height_ratios=[1, .16])
axes = [fig.add_subplot(gs[0, i]) for i in range(2)]
for panel, ax in enumerate(axes):
    for i, name in enumerate(['Method A', 'Method B']):
        runs = np.exp(-x[None, :] / (9 + i * 5)) + rng.normal(0, .025, (12, len(x))) + .05 * panel
        mean, sd = runs.mean(0), runs.std(0, ddof=1)
        ax.plot(x, mean, color=PALETTE[i], label=name)
        uncertainty_band(ax, x, mean - sd, mean + sd, color=PALETTE[i])
    ax.set_xlabel('Iteration')
    ax.set_ylabel('Loss')
    ax.set_title(['(a) Training', '(b) Validation'][panel], loc='left')
legend_ax = fig.add_subplot(gs[1, :])
legend_ax.set_axis_off()
legend_ax.legend(*axes[0].get_legend_handles_labels(), loc='center', ncol=2, frameon=False)
save_fig(fig, 'figures/fig_trends.pdf')
```

## 4. Vector heatmap with legible cell text

A single common unit and normalization permits comparisons across cells. For heterogeneous metrics,
use explicitly labelled per-metric scales or separate panels; do not reverse Normalize's vmin/vmax.
Reverse the colormap if necessary. Constant-valued and masked matrices are handled by the helper.
A sequential ramp here is derived from the selected palette, including grayscale.

```python
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from _utils.plot_utils import setup_style, PALETTE, draw_vector_heatmap, save_fig, set_paper_placement

setup_style(palette='nature')
data = np.array([[.88, .82, .85], [.81, .78, .80], [.75, .72, .74], [.70, .68, .69]])
ramp = LinearSegmentedColormap.from_list('project_ramp', ['#FFFFFF', PALETTE[0]])
fig, ax = plt.subplots(figsize=(6, 3.8), layout='constrained')
set_paper_placement(fig, width_fraction=.9)
draw_vector_heatmap(ax, data, xlabels=['Task 1', 'Task 2', 'Task 3'],
                    ylabels=['A', 'B', 'C', 'D'], cmap=ramp, vmin=0, vmax=1,
                    annot='auto', cbar_label='Score')
save_fig(fig, 'figures/fig_heatmap.pdf')
```
