# Typography & Font Specifications

> **BASELINE — 单一真源：`academic-toolkit/skills/_utils/academic.mplstyle`**（本仓唯一 rcParams 真源，含字号阶梯、CJK 字体链、定版色板与理由）。
> Python 产图先加载它，再叠加本技能的差异项；不要把本文件的值当独立真源抄进脚本。
> ⛔ 旧版「仅拉丁字体链」基线已废除：含中文标签的图必须沿用基线 CJK 链（Noto Sans SC → SimHei → Microsoft YaHei…），否则中文渲染为 □。

```python
# Academic Figure Skill Typography Baseline — 真源在 academic.mplstyle，先加载再叠差异项
import matplotlib as mpl
mpl.style.use(r"<repo>/academic-toolkit/skills/_utils/academic.mplstyle")

# —— 本技能差异项（期刊印刷尺度，比基线 A4 屏幕口径更小；仅当确认全图无 CJK 字符
#    时才可覆盖字体链——含中文标签请删除下面 font.sans-serif 一行）——
mpl.rcParams.update({
    "font.size": 8,
    "axes.titlesize": 8,
    "axes.labelsize": 8,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "legend.fontsize": 8,
    "figure.titlesize": 9,
    "font.sans-serif": ["Arial", "Helvetica", "Liberation Sans"],  # 纯英文图专用
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.linewidth": 0.6,
    "xtick.direction": "out",
    "ytick.direction": "out",
    "xtick.major.width": 0.6,
    "ytick.major.width": 0.6,
    "legend.frameon": False,
})
# 差异依据：期刊单栏 89mm / 双栏 183mm 成品宽比竞赛 A4 版心窄，字号取印刷尺度
# 7-9pt。字号与画布缩放比换算铁律（嵌入宽反推 figsize）见
# plot_utils.py 注释区——缩放比 ≠ 1 时画时字号必须 = 印刷目标 ÷ 缩放比。
```

```r
# Academic Figure Skill Typography Baseline — COPY VERBATIM, place at TOP of script
library(ggplot2)
theme_cns <- theme_bw(base_size = 8, base_family = "Arial") +
  theme(
    axis.title = element_text(size = 8),
    axis.text = element_text(size = 7, color = "#333333"),
    legend.title = element_text(size = 8, face = "bold"),
    legend.text = element_text(size = 7),
    strip.text = element_text(size = 8, face = "bold"),
    panel.grid = element_blank(),
    legend.background = element_blank(),
    legend.key = element_blank()
  )
```

---

## Font Family

Always sans-serif. **Pure-Latin figures:** Arial, Helvetica; fallback Liberation Sans.
**Any CJK label (中文轴名/图例/刻度):** do NOT override the font chain — use the baseline CJK chain from `academic.mplstyle` (Noto Sans SC → SimHei → Microsoft YaHei, bundled font at `skills/_utils/NotoSansSC-Regular.ttf`). Latin-only chains render CJK as □.

## Font Size Floor

No text element below 5 pt at final print dimensions. Axis ticks: 5-6 pt. Labels: 6-7 pt. Panel labels: 8-9 pt bold.
**CJK floor:** Chinese glyphs are denser than Latin — tick/label text containing Chinese must be ≥ 7 pt at final print size (5-6 pt Chinese is unreadable in print and reads as AI-generated noise).

## R ggplot2 Setup

> R 不消费 mplstyle（matplotlib 专属）；`theme_cns` 仍是 R 侧基线。但 CJK 规则同样适用：含中文标签时 `base_family` 必须换中文字体并配 `showtext` + `cairo_pdf()`，禁止 Arial-only。

```r
library(ggplot2)

theme_cns <- theme_bw(base_size = 7, base_family = "Arial") +
  theme(
    axis.title = element_text(size = 8),
    axis.text = element_text(size = 6),
    legend.title = element_text(size = 7, face = "bold"),
    legend.text = element_text(size = 6),
    strip.text = element_text(size = 8, face = "bold")
  )
```

## R ComplexHeatmap Setup

```r
library(ComplexHeatmap)
library(grid)

ht_opt(
  heatmap_column_names_gp = gpar(fontfamily = "Arial", fontsize = 6),
  heatmap_row_names_gp = gpar(fontfamily = "Arial", fontsize = 6),
  legend_title_gp = gpar(fontfamily = "Arial", fontsize = 7, fontface = "bold"),
  legend_labels_gp = gpar(fontfamily = "Arial", fontsize = 6)
)
```

## Cross-platform Font Notes

- Windows: Arial is installed by default
- macOS: Helvetica is installed by default; Arial is also available
- Linux: Neither Arial nor Helvetica is guaranteed. Use `Liberation Sans` or install `fonts-liberation` / `msttcorefonts`
- For R on Linux: use `showtext` package to register and embed fonts; export with `cairo_pdf()` device
- Always embed fonts in PDF output: `pdf.fonttype: 42` (matplotlib), `cairo_pdf()` (R)
