---
name: matplotlib
description: "Low-level plotting library for full customization. Use when you need fine-grained control over every plot element, axes, and layout."
allowed-tools: Read Write Bash
license: https://github.com/matplotlib/matplotlib/tree/main/LICENSE
compatibility: Requires Python 3.11+ and Matplotlib 3.11.2. Bundled examples also use NumPy and SciPy; pandas examples need pandas, and Jupyter widgets need ipympl. Installation needs network access; local plotting needs no credentials.
metadata:
  version: "1.4"
  last-reviewed: "2026-10-01"
  skill-author: K-Dense Inc.
---

# Matplotlib

## 执行与产出

使用当前执行会话完成本步工作；产物路径按当前步骤合同。程序采集真实操作、输入输出、版本与运行清单，模型只负责实质成果和领域质量。

建议额外记录：数据文件、脚本路径、matplotlib 版本、导出格式与 DPI。图表溯源门禁 figure_provenance 要求图有来源证据。

## Overview

Matplotlib is Python's foundational visualization library for creating static, animated, and interactive plots. This skill provides guidance on using matplotlib effectively, covering both the pyplot interface (MATLAB-style) and the object-oriented API (Figure/Axes), along with best practices for creating publication-quality visualizations.

## When to Use This Skill

This skill should be used when:
- Creating any type of plot or chart (line, scatter, bar, histogram, heatmap, contour, etc.)
- Generating scientific or statistical visualizations
- Customizing plot appearance (colors, styles, labels, legends)
- Creating multi-panel figures with subplots
- Exporting visualizations to various formats (PNG, PDF, SVG, etc.)
- Building interactive plots or animations
- Working with 3D visualizations
- Integrating plots into Jupyter notebooks or GUI applications

## Setup

For project work, install Matplotlib with uv:

```bash
uv add "matplotlib==3.11.2" numpy scipy
```

For notebook interactivity:

```bash
uv add "matplotlib==3.11.2" ipympl
```

Then enable the widget backend in Jupyter with `%matplotlib widget` or `%matplotlib ipympl`.

Targets Matplotlib 3.11.2 (Python 3.11+), reviewed 2026-10-01. The bundled scripts and representative examples were executed using Agg and PNG/PDF/SVG output. GUI windows, Jupyter widgets, and external LaTeX are environment-dependent and were not exercised. Fragment examples assume imports and named data; adapt and validate them before use. Check the [3.11 API changes](https://matplotlib.org/stable/api/prev_api_changes/api_changes_3.11.0.html) when migrating older code: use `tick_labels` and `orientation` for box plots, `mpl.colormaps[name]` for colormaps, and label contour lines rather than `contourf`.

File output needs no GUI. Use `MPLBACKEND=Agg` for batch scripts, or select Agg before importing pyplot. Interactive output requires an installed GUI toolkit such as PySide6 (`QtAgg`) or working Tk (`TkAgg`); `plt.ioff()` does not remove GUI thread requirements. See [backends](https://matplotlib.org/stable/users/explain/figure/backends.html).

## Core Concepts

### The Matplotlib Hierarchy

Matplotlib uses a hierarchical structure of objects:

1. **Figure** - The top-level container for all plot elements
2. **Axes** - The actual plotting area where data is displayed (one Figure can contain multiple Axes)
3. **Artist** - Everything visible on the figure (lines, text, ticks, etc.)
4. **Axis** - The number line objects (x-axis, y-axis) that handle ticks and labels

### Two Interfaces

**1. pyplot Interface (Implicit, MATLAB-style)**
```python
import matplotlib.pyplot as plt

plt.plot([1, 2, 3, 4])
plt.ylabel('some numbers')
plt.show()
```
- Convenient for quick, simple plots
- Maintains state automatically
- Good for interactive work and simple scripts

**2. Object-Oriented Interface (Explicit)**
```python
import matplotlib.pyplot as plt

fig, ax = plt.subplots()
ax.plot([1, 2, 3, 4])
ax.set_ylabel('some numbers')
plt.show()
```
- **Recommended for most use cases**
- More explicit control over figure and axes
- Better for complex figures with multiple subplots
- Easier to maintain and debug

## Common Workflows

### 1. Basic Plot Creation

**Single plot workflow:**
```python
import matplotlib.pyplot as plt
import numpy as np

# Create figure and axes (OO interface - RECOMMENDED)
fig, ax = plt.subplots(figsize=(10, 6))

# Generate and plot data
x = np.linspace(0, 2*np.pi, 100)
ax.plot(x, np.sin(x), label='sin(x)')
ax.plot(x, np.cos(x), label='cos(x)')

# Customize
ax.set_xlabel('x')
ax.set_ylabel('y')
ax.set_title('Trigonometric Functions')
ax.legend()
ax.grid(True, alpha=0.3)

# Save and/or display
fig.savefig('plot.png', dpi=300)
plt.show()
```

### 2. Multiple Subplots

**Creating subplot layouts:**
```python
# Method 1: Regular grid
fig, axes = plt.subplots(2, 2, figsize=(12, 10))
axes[0, 0].plot(x, y1)
axes[0, 1].scatter(x, y2)
axes[1, 0].bar(categories, values)
axes[1, 1].hist(data, bins=30)

# Method 2: Mosaic layout (more flexible)
fig, axes = plt.subplot_mosaic([['left', 'right_top'],
                                 ['left', 'right_bottom']],
                                figsize=(10, 8))
axes['left'].plot(x, y)
axes['right_top'].scatter(x, y)
axes['right_bottom'].hist(data)

# Method 3: GridSpec (maximum control)
from matplotlib.gridspec import GridSpec
fig = plt.figure(figsize=(12, 8))
gs = GridSpec(3, 3, figure=fig)
ax1 = fig.add_subplot(gs[0, :])  # Top row, all columns
ax2 = fig.add_subplot(gs[1:, 0])  # Bottom two rows, first column
ax3 = fig.add_subplot(gs[1:, 1:])  # Bottom two rows, last two columns
```

### 3. Plot Types and Use Cases

**Line plots** - Time series, continuous data, trends
```python
ax.plot(x, y, linewidth=2, linestyle='--', marker='o', color='blue')
```

**Scatter plots** - Relationships between variables, correlations
```python
ax.scatter(x, y, s=sizes, c=colors, alpha=0.6, cmap='viridis')
```

**Bar charts** - Categorical comparisons
```python
ax.bar(categories, values, color='steelblue', edgecolor='black')
# For horizontal bars:
ax.barh(categories, values)
```

**Histograms** - Distributions
```python
ax.hist(data, bins=30, edgecolor='black', alpha=0.7)
```

**Heatmaps** - Matrix data, correlations
```python
im = ax.imshow(matrix, cmap='viridis', aspect='auto', interpolation='nearest')
plt.colorbar(im, ax=ax)
```

**Contour plots** - 3D data on 2D plane
```python
contour = ax.contour(X, Y, Z, levels=10)
ax.clabel(contour, inline=True, fontsize=8)
```

**Box plots** - Statistical distributions
```python
ax.boxplot([data1, data2, data3], tick_labels=['A', 'B', 'C'])
```

**Violin plots** - Distribution densities
```python
ax.violinplot([data1, data2, data3], positions=[1, 2, 3])
```

For comprehensive plot type examples and variations, refer to `references/plot_types.md`.

### 4. Styling and Customization

**Color specification methods:**
- Named colors: `'red'`, `'blue'`, `'steelblue'`
- Hex codes: `'#FF5733'`
- RGB tuples: `(0.1, 0.2, 0.3)`
- Colormaps: `cmap='viridis'`, `cmap='plasma'`, `cmap='coolwarm'`

**Using style sheets:**
```python
# 仓库产图基线（论文/竞赛/交付图必须从它出发）：
plt.style.use(r"<repo>/academic-toolkit/skills/_utils/academic.mplstyle")

# matplotlib 内置风格（'ggplot', 'bmh', 'fivethirtyeight', 'seaborn-v0_8-*' 等，
# 见 plt.style.available）仅限屏幕预览与交互探索——
# ⛔ 禁止用于论文/交付图：灰底网格、默认色环、screen 字号是"AI 默认味"的直观来源
```

**Customizing with rcParams:**
```python
# 覆盖前先加载基线 academic.mplstyle；下面的值就是基线值（示例用），
# 需要偏离时在这里覆盖并写明理由（如期刊印刷尺度差异档见 fig-academic）。
plt.rcParams['font.size'] = 11
plt.rcParams['axes.labelsize'] = 12
plt.rcParams['axes.titlesize'] = 13
plt.rcParams['xtick.labelsize'] = 10
plt.rcParams['ytick.labelsize'] = 10
plt.rcParams['legend.fontsize'] = 10
plt.rcParams['figure.titlesize'] = 13
```

**Text and annotations:**
```python
ax.text(x, y, 'annotation', fontsize=12, ha='center')
ax.annotate('important point', xy=(x, y), xytext=(x+1, y+1),
            arrowprops=dict(arrowstyle='->', color='red'))
```

For detailed styling options and colormap guidelines, see `references/styling_guide.md`.

### 5. Saving Figures

**Export to various formats:**
```python
# 仓库交付正解：基线已定版护栏（savefig.bbox=standard + pad_inches=0.1），直接存即可
fig.savefig('figure.pdf')                      # 矢量主图（论文/交付）
fig.savefig('figure.png', dpi=300)             # 位图预览

# bbox_inches='tight' 仅限交互预览/屏幕截图——
# ⛔ 交付链路禁用：图内 axes 外标注会把 PDF mediabox 撑爆成超长条
#    （仓库事故在案，故基线锁 standard；白边用 pad_inches 控制）
fig.savefig('preview.png', dpi=150, bbox_inches='tight')

# Transparent background（预览用）
fig.savefig('figure.png', dpi=300, transparent=True)
```

**Important parameters:**
- `dpi`: Raster pixels per inch; choose from required pixel size and final print size（300 dpi 是印刷常用起点，不是通用 publication 要求）
- `bbox_inches='tight'`: Crops to artist bounds, changing final physical/pixel dimensions — ⛔ 交付链路禁用（mediabox 撑爆风险），基线护栏为 standard
- `facecolor='white'`: Ensures white background (useful for transparent themes)
- `transparent=True`: Makes axes/figure backgrounds transparent; explicit facecolors can override this

固定尺寸出图：用 constrained layout 并省去 tight 裁剪（若所用 style 设了
`savefig.bbox`，在 `mpl.rc_context` 里临时设回 `savefig.bbox=None`）。PNG 像素尺寸
≈ `figsize * dpi`；PDF/SVG 保持矢量（除非含图像或栅格化 artist）。DPI 不会给源数据
增加信息量。批量脚本在 `show` 之前 `fig.savefig(...)`，循环内每个图 `plt.close(fig)`。
导出后按最终使用尺寸检查：裁切、缺字形、对比度、图例可读性。

### 6. Working with 3D Plots

```python
fig = plt.figure(figsize=(10, 8))
ax = fig.add_subplot(111, projection='3d')

# Surface plot
ax.plot_surface(X, Y, Z, cmap='viridis')

# 3D scatter
ax.scatter(x, y, z, c=colors, marker='o')

# 3D line plot
ax.plot(x, y, z, linewidth=2)

# Labels
ax.set_xlabel('X Label')
ax.set_ylabel('Y Label')
ax.set_zlabel('Z Label')
```

## Best Practices

### 1. Interface Selection
- **Use the object-oriented interface** (fig, ax = plt.subplots()) for production code
- Reserve pyplot interface for quick interactive exploration only
- Always create figures explicitly rather than relying on implicit state

### 2. Figure Size and DPI
- Set figsize at creation: `fig, ax = plt.subplots(figsize=(10, 6))`
- Choose DPI and final dimensions together; 300 dpi is a common starting point for print, not a universal publication requirement.

### 3. Layout Management
- Prefer `fig, ax = plt.subplots(layout="constrained")` for automatic spacing.
- Do not combine layout engines: `tight_layout()` disables constrained layout. Neither engine replaces visual inspection of the exported figure.

### 4. Colormap Selection
- **Sequential** (viridis, plasma, inferno): Ordered data with consistent progression
- **Diverging** (coolwarm, RdBu): Data with meaningful center point (e.g., zero)
- **Qualitative**: Categorical/nominal data — ⛔ 禁用 `tab10`/`Set3` 等默认定性色环（matplotlib 出厂色，"AI 味"来源）；分类数据用 `academic.mplstyle` 定版 cycler，高可及性需求用 Okabe-Ito
- Avoid rainbow colormaps (jet) - they are not perceptually uniform
- 可比的热图/图像面板使用**同一归一化与显式极限**：只共用 `cmap` 不代表颜色有相同数值含义。colorbar 标注单位并披露截断（`extend`）。diverging 数据用有意义的中心（必要时 `TwoSlopeNorm`）；`LogNorm` 只接受正值——零/负/缺失值要显式处理，不得静默替换。

### 5. Accessibility
- Use colorblind-friendly colormaps (viridis, cividis)
- Add patterns/hatching for bar charts in addition to colors
- Ensure sufficient contrast between elements
- Include descriptive labels and legends

### 6. Performance
- For dense artists in PDF/SVG, use `rasterized=True`; PNG is already raster. Rasterization mainly reduces vector file size, not the number of input points.
- Use appropriate data reduction before plotting (e.g., downsample dense time series)
- Use blitting only when the backend supports it and return all changed artists.

### 7. Scientific Checks
- 校验单位、形状、成对缺失值处理与 x 值排序；被剔除的观测要保留断口，不得跨缺口静默连线。
- `errorbar` 接受的是非负误差**尺寸**（标量、`(N,)` 或 `(2, N)` 先下后上），不是区间端点；`fill_between` 接收的才是下/上端点。SD、SEM、CI 在上游算好并声明种类、样本量、抽样单元与方法——Matplotlib 不会替你推断不确定性。
- 箱线图须默认 1.5 IQR；离群点（fliers）不等于数据错误。小提琴形状依赖带宽；3.11 会忽略 masked/nonfinite 观测——排除量要统计并披露，画前逐组校验（空组/单点组先行处理）。
- 共享 colorbar 要求共享 norm 与单位。科学图像的朝向、像素范围与空间长宽比必须服从数据，而不是服从美观。

### 8. Code Organization
```python
# Good practice: Clear structure
def create_analysis_plot(data, title):
    """Create standardized analysis plot."""
    fig, ax = plt.subplots(figsize=(10, 6), constrained_layout=True)

    # Plot data
    ax.plot(data['x'], data['y'], linewidth=2)

    # Customize
    ax.set_xlabel('X Axis Label', fontsize=12)
    ax.set_ylabel('Y Axis Label', fontsize=12)
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)

    return fig, ax

# Use the function
fig, ax = create_analysis_plot(my_data, 'My Analysis')
fig.savefig('analysis.png', dpi=300)
```

## Quick Reference Scripts

This skill includes helper scripts in the `scripts/` directory:

### `plot_template.py`
Template script using reproducible synthetic data. Bar errors are sample SD across 12 synthetic replicates; box and violin plots use supplied groups. Replace these with actual data and declared uncertainty. Commands below run from the skill root.

**Usage:**
```bash
MPLBACKEND=Agg uv run --isolated --with "matplotlib==3.11.2" --with numpy --with scipy python scripts/plot_template.py --no-show --output plot.png
```

### `style_configurator.py`
Interactive utility to configure matplotlib style preferences and generate custom style sheets.

**Usage:**
```bash
MPLBACKEND=Agg uv run --isolated --with "matplotlib==3.11.2" --with numpy python scripts/style_configurator.py --preset dark --output dark.mplstyle --preview --no-show
```

## Detailed References

For comprehensive information, consult the reference documents:

- **`references/plot_types.md`** - Complete catalog of plot types with code examples and use cases
- **`references/styling_guide.md`** - Detailed styling options, colormaps, and customization
- **`references/api_reference.md`** - Core classes and methods reference
- **`references/common_issues.md`** - Troubleshooting guide for common problems

## Integration with Other Tools

Matplotlib integrates well with:
- **NumPy/Pandas** - Direct plotting from arrays and DataFrames
- **Seaborn** - High-level statistical visualizations built on matplotlib
- **Jupyter** - Interactive plotting with `%matplotlib inline` or `%matplotlib widget`
- **GUI frameworks** - Embedding in Tkinter, Qt, wxPython applications

## Common Gotchas

1. **Overlapping elements**: Use one layout engine, then inspect the export
2. **State confusion**: Use OO interface to avoid pyplot state machine issues
3. **Memory issues with many figures**: Close figures explicitly with `plt.close(fig)`
4. **Font warnings**: Install the requested font or choose an available fallback; do not hide missing-glyph warnings
5. **DPI confusion**: Remember that figsize is in inches, not pixels: `pixels = dpi * inches`

## Additional Resources

- Official documentation: https://matplotlib.org/
- Gallery: https://matplotlib.org/stable/gallery/index.html
- Cheatsheets: https://matplotlib.org/cheatsheets/
- Tutorials: https://matplotlib.org/stable/tutorials/index.html

