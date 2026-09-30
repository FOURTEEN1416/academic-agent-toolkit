# Export Specifications

> **BASELINE — 单一真源 `academic.mplstyle` + 本技能导出差异项：** 先加载基线再叠下面差异；导出护栏（`savefig.bbox: standard`）随基线生效。

```python
# Academic Figure Skill Export Baseline — 基线(academic.mplstyle) + 导出差异项
import matplotlib as mpl
mpl.style.use(r"<repo>/academic-toolkit/skills/_utils/academic.mplstyle")
mpl.rcParams.update({
    "pdf.fonttype": 42,         # TrueType font embedding（本技能差异项）
    "svg.fonttype": "none",     # editable text in SVG（本技能差异项）
    "savefig.dpi": 300,         # 期刊 300dpi（基线 350）
    # savefig.bbox 沿用基线 standard：⛔ 禁 tight——axes 外文字会把 PDF
    # mediabox 撑爆成超长条（plot_utils 事故在案）；白边由 pad_inches 控制，
    # 期刊若要求去白边在排版层（LaTeX/includegraphics trim）处理
})

def save_cns_figure(fig, filename):
    """Standard Academic Figure Skill export: vector PDF + 300dpi PNG preview."""
    fig.savefig(f"{filename}.pdf", dpi=300)
    fig.savefig(f"{filename}.png", dpi=300)
```

```r
# Academic Figure Skill Export Baseline — COPY VERBATIM
save_cns_figure <- function(plot, filename, width_mm = 183, height_mm = NULL) {
  ggsave(paste0(filename, ".pdf"), plot, device = cairo_pdf,
         width = width_mm, height = height_mm, units = "mm", dpi = 300)
  png(paste0(filename, ".png"), width = width_mm, height = height_mm,
      units = "mm", res = 300, type = "cairo")
  print(plot)
  dev.off()
}
```

---

## Format Selection

| Content Type | Format | Notes |
|-------------|--------|-------|
| Line plots, scatter plots, bar charts, boxplots | PDF or SVG or EPS | Vector elements (lines, text, shapes) must remain vector |
| Heatmap color blocks, micrographs, photos | TIFF or PNG at ≥300 dpi | True raster content only |
| Mixed (scatter with >100K rasterized points on vector axes) | PDF with `rasterized=True` on the data layer | Keeps axes/labels as vector text |

**Always deliver:**
1. One vector master file (PDF preferred, or SVG/EPS if specified by journal)
2. One 300 dpi PNG preview (for quick viewing, chat sharing, manuscript drafts)

## Python Matplotlib Export

```python
# Vector master (submission-ready)
fig.savefig("figure.pdf", dpi=300)
# ⛔ 不要写 pdf.fonttype=42 这类带点的 kwargs（SyntaxError）——
#    fonttype/svg.fonttype 已由上方 rcParams 差异项定版

# Raster preview
fig.savefig("figure.png", dpi=300)

# For scatter plots with very large point counts:
ax.scatter(x, y, s=2, rasterized=True)  # rasterize data layer only
```

Key matplotlib rcParams（基线 `academic.mplstyle` + 本技能导出差异项，与文件头基线块同口径）:
```python
mpl.rcParams.update({
    "svg.fonttype": "none",     # Editable text in SVG
    "pdf.fonttype": 42,         # TrueType font embedding in PDF
    # savefig.bbox 沿用基线 standard（⛔ 禁 tight，mediabox 撑爆风险）
    "savefig.dpi": 300,
})
```

## R ggplot2 Export

```r
# Vector master
ggsave("figure.pdf", width = 89, height = 70, units = "mm",
       device = cairo_pdf, dpi = 300)

# Raster preview
ggsave("figure.png", width = 89, height = 70, units = "mm", dpi = 300)
```

## R ComplexHeatmap Export

```r
# Vector master
cairo_pdf("heatmap.pdf", width = 183/25.4, height = 120/25.4)
draw(ht)
dev.off()

# Raster preview
png("heatmap_preview.png", width = 183, height = 120, units = "mm", res = 300)
draw(ht)
dev.off()
```

## Resolution Requirements by Journal

| Journal Family | Line Art | Raster/Photo |
|---------------|----------|-------------|
| Nature | ≥600 dpi (line art), ≥300 dpi (photo) | ≥300 dpi |
| Cell | ≥600 dpi (line art), ≥300 dpi (photo) | ≥300 dpi |
| Science | ≥600 dpi (line art), ≥300 dpi (photo) | ≥300 dpi |

**Guideline:** When in doubt, export at 600 dpi for line art and 300 dpi for everything else.

## File Naming Convention

- Use descriptive names: `fig1_microbiome_heatmap.pdf` not `figure1.pdf`
- Match the numbering in your manuscript: `fig2a_volcano.pdf`, `fig2b_pathway.pdf`
- Supplementary figures: `figS1_quality_control.pdf`
