# =====================================================================
# _eco_style.R — eco-community-plots 的 R 侧样式真源
# =====================================================================
# 六个模板脚本统一 source() 本文件；脚本内只允许写差异项（图例位置、轴标题留白、
# 显著性注释放哪）。字体族 / 字号阶梯 / 线宽 / 刻度长 / 语义色板一律从这里取，
# 不得在脚本里另立第二套口径。
#
# 【口径指针（只写指针，不复制正文）】
#   · 字号公式：academic-toolkit/skills/_utils/academic.mplstyle（文件头【字号口径】）
#       画时字号 = 印刷目标字号 × figsize宽 ÷ 嵌入显示宽 W_in
#     python 侧同源实现见 academic-toolkit/skills/_utils/plot_utils.py
#     （PAGE_MAX_W_IN / MIN_LEGIBLE_PT / nature_rcparams()）
#   · R 侧排版与字号下限：academic-toolkit/skills/fig-academic/references/typography.md
#   · R 导出设备：academic-toolkit/skills/fig-academic/references/r-rendering.md
#   · 语义色板：academic-toolkit/skills/paper-figure/references/semantic-palette.md
#
# 【为什么本技能的 base_size 恒为 8.25 pt】
#   六个模板按成品毫米尺寸 1:1 导出（58–138 mm 全在 5.5 in = 139.7 mm 上限内），
#   嵌入显示宽 = 画布宽 ⇒ 缩放比 = 1 ⇒ 画时字号 = 印刷目标字号；
#   公式给出 8.25 × w_in ÷ w_in = 8.25 pt。将来画布宽 > 139.7 mm 时自动放大。
#
# 【字号阶梯（印刷 pt）】基准 8.25：轴标题 8.25 / 刻度与图例 7.0 / 图题 9.9。
#   刻度与图例的 7.0 pt 即 typography.md 的 CJK 印刷下限；纯拉丁图可降到 6.5，
#   但不得低于 5 pt。
# 【线宽】轴线 0.45 mm（≈1.29 pt）；刻度长 1.09 mm（≈3.09 pt）；
#   数据点直径 1.45 mm（≈4.1 pt）。换算自 plot_utils.nature_rcparams 的等比系数。
# =====================================================================

# ---- 字体族回退链（与 academic.mplstyle 的 CJK 链同序）----
eco_font_chain <- c(
  "Noto Sans SC", "NotoSansSC", "SimHei", "Microsoft YaHei",
  "PingFang SC", "Heiti SC", "WenQuanYi Micro Hei",
  "Arial", "Helvetica", "DejaVu Sans"
)

# 返回第一个本机可用的族名；可用 ECO_FONT_FAMILY 环境变量强制指定。
eco_font <- function(chain = eco_font_chain) {
  forced <- Sys.getenv("ECO_FONT_FAMILY", "")
  if (nzchar(forced)) return(forced)
  installed <- character(0)
  if (requireNamespace("systemfonts", quietly = TRUE)) {
    installed <- unique(systemfonts::system_fonts()$family)
  }
  if (!length(installed) && requireNamespace("sysfonts", quietly = TRUE)) {
    installed <- unique(sysfonts::font_families())
  }
  if (!length(installed)) installed <- names(grDevices::pdfFonts())
  hit <- chain[chain %in% installed]
  if (length(hit)) hit[[1]] else "sans"
}

# ---- 画布宽 → 基准字号（印刷 pt；公式见文件头）----
eco_base_size <- function(width_mm) {
  w_in <- width_mm / 25.4
  w_disp <- min(5.5, w_in)          # PAGE_MAX_W_IN
  8.25 * w_in / w_disp              # NATURE_TARGET_PT
}

# 返回该画布宽下的整套排版量（字号 pt / 线宽 mm / 刻度长 mm / 点径 mm）
eco_sizes <- function(width_mm) {
  base <- eco_base_size(width_mm)
  list(
    base        = base,
    axis_title  = base,
    axis_text   = max(7.0, base * 0.85),
    legend_text = max(7.0, base * 0.85),
    plot_title  = base * 1.2,
    line_mm     = max(0.6, base * 2.5 / 16) * 25.4 / 72,
    tick_mm     = base * 6 / 16 * 25.4 / 72,
    point_mm    = max(3.0, base * 8 / 16) * 25.4 / 72
  )
}

# ---- 主题：theme_classic + CJK 字体族 + 统一基础尺寸 ----
eco_theme <- function(width_mm, family = eco_font()) {
  z <- eco_sizes(width_mm)
  ggplot2::theme_classic(base_size = z$base, base_family = family) +
    ggplot2::theme(
      axis.title        = ggplot2::element_text(size = z$axis_title, colour = "black"),
      axis.text         = ggplot2::element_text(size = z$axis_text, colour = "black"),
      legend.title      = ggplot2::element_text(size = z$axis_title, colour = "black"),
      legend.text       = ggplot2::element_text(size = z$legend_text, colour = "black"),
      plot.title        = ggplot2::element_text(size = z$plot_title, face = "bold"),
      strip.text        = ggplot2::element_text(size = z$axis_text, face = "bold"),
      axis.line         = ggplot2::element_line(colour = "black", linewidth = z$line_mm),
      axis.ticks        = ggplot2::element_line(colour = "black", linewidth = z$line_mm),
      axis.ticks.length = grid::unit(z$tick_mm, "mm"),
      panel.grid        = ggplot2::element_blank(),
      legend.background = ggplot2::element_blank(),
      legend.key        = ggplot2::element_blank()
    )
}

# 脚本里的用法：theme_set(eco_theme(<成品宽 mm>))，width_mm 必须与 ggsave 的成品宽一致。
# CJK 字体默认走 cairo_pdf 原生嵌入（无需额外调用）；只有需要 showtext 转曲时，
# 才在 source() 之后自行 showtext::showtext_auto(TRUE)。

# ggplot2 的 geom_text(size=) 以 mm 计（fontsize = size × 2.845）；这里按 pt 传入
eco_text_mm <- function(pt) pt * 25.4 / 72.27

# ---- Okabe-Ito 语义色板（色盲安全；前两色为最强对比对）----
# 完整 8 色取自 paper-figure/references/semantic-palette.md §5.1 与
# fig-visualization-advisor/references/plot_recipes.md 的同一组定义。
eco_okabe <- c(
  blue       = "#0072B2",   # 主数据 / 下调 / 本队方法
  orange     = "#E69F00",   # 对照组 / 第二组
  green      = "#009E73",   # 改进 / 第三组
  vermillion = "#D55E00",   # 强调 / 上调
  sky        = "#56B4E9",
  purple     = "#CC79A7",
  yellow     = "#F0E442",
  black      = "#000000"
)

# 中性墨色：箭头/注记/趋势线用，避免与分组色抢视线
eco_ink <- "#263238"

# 富集方向语义（enrich_species_compare.R）
eco_sign_pal <- c(enriched = "#D55E00", depleted = "#0072B2", ns = "0.55")

# 显著性分级语义（Manteltest.R 的 P-value 图例）
eco_pval_pal <- c("< 0.01" = "#D55E00", "0.01 - 0.05" = "#E69F00", ">= 0.05" = "0.55")

# n 组分类色；>8 组必须再加 shape/linetype 冗余编码（单图系列建议 ≤6）
eco_pal <- function(n) {
  base <- unname(eco_okabe)
  if (n <= length(base)) return(base[seq_len(n)])
  warning("Okabe-Ito 只有 8 个可辨色；超过 8 组请加 shape/linetype 冗余编码。", call. = FALSE)
  grDevices::colorRampPalette(base)(n)
}

# 按因子水平命名，保证 scale_*_manual(values = eco_pal_named(x)) 与图例顺序一致
eco_pal_named <- function(x) {
  lv <- levels(factor(x))
  stats::setNames(eco_pal(length(lv)), lv)
}
