
#####  Procrustes analysis

library(vegan)
library(ggplot2)
library(RColorBrewer)

# ---- 统一样式入口：字体链 / base_size / 色板唯一来源 scripts/_eco_style.R ----
# 定位本脚本目录：RStudio source() 走 sys.frame(1)$ofile，Rscript 走 --file=，
# 都拿不到时退回当前工作目录（此时请把 _eco_style.R 放在工作目录）。
.eco_ofile <- tryCatch(sys.frame(1)$ofile, error = function(e) NULL)
.eco_here <- if (!is.null(.eco_ofile) && nzchar(.eco_ofile)) {
  dirname(normalizePath(.eco_ofile))
} else {
  .eco_args <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
  if (length(.eco_args)) dirname(normalizePath(sub("^--file=", "", .eco_args[1]))) else getwd()
}
source(file.path(.eco_here, "_eco_style.R"))

theme_set(eco_theme(58))   # 画布宽 58 mm：theme_classic(base_family = eco_font())
z <- eco_sizes(58)

data1 <- read.csv("otutab_rare_plastisphere.txt", head=TRUE,sep="\t",row.names = 1)
data1 <- data1[which(rowSums(data1) > 0),]
#data <- data[which(rowSums(data) > 0),]
data1 <- t(data1)
pla.dist <- vegdist(data1,method = "bray")

data2 <- read.csv("otutab_rare_seawater.txt", head=TRUE,sep="\t",row.names = 1)
data2 <- data2[which(rowSums(data2) > 0),]
data2 <- t(data2)
seawater.dist <- vegdist(data2,method = "bray")

mantel_res <- mantel(pla.dist,seawater.dist)

mds.pla <- monoMDS(pla.dist)
mds.seawater <- monoMDS(seawater.dist)

set.seed(123)
pro.pla.seawater <- procrustes(mds.pla,mds.seawater)

protest_res <- protest(mds.pla,mds.seawater)

Y <- data.frame(
  Seawater1 = pro.pla.seawater$Yrot[, 1],
  Seawater2 = pro.pla.seawater$Yrot[, 2],
  Plastisphere1 = pro.pla.seawater$X[, 1],
  Plastisphere2 = pro.pla.seawater$X[, 2]
)

Y$ID <- rownames(pro.pla.seawater$X)

X <- data.frame(pro.pla.seawater$rotation)

# 分组色与 PCoA 模板一致：Plastisphere=蓝、Seawater=橙（Okabe-Ito）
pal <- c(Plastisphere = eco_okabe[["blue"]], Seawater = eco_okabe[["orange"]])

# 统计量从本次计算取，不抄上游数字
ann <- sprintf(
  "Procrustes analysis:\n    M2 = %.3f, p-value = %.3f\nMantel test:\n    r = %.3f, p-value = %.3f",
  protest_res$ss, protest_res$signif, mantel_res$statistic, mantel_res$signif
)

p1 <- ggplot(Y) +
  geom_segment(
    aes(
      x = Seawater1,
      y = Seawater2,
      xend = (Seawater1 + Plastisphere1) / 2,
      yend = (Seawater2 + Plastisphere2) / 2
    ),
    color = pal[["Seawater"]],
    linewidth = z$line_mm
  ) +
  geom_segment(
    aes(
      x = (Seawater1 + Plastisphere1) / 2,
      y = (Seawater2 + Plastisphere2) / 2,
      xend = Plastisphere1,
      yend = Plastisphere2
    ),
    color = pal[["Plastisphere"]],
    linewidth = z$line_mm
  ) +
  geom_point(
    aes(Seawater1, Seawater2, fill = "Seawater"),
    size = z$point_mm,
    shape = 21,
    alpha = 0.8
  ) +
  geom_point(
    aes(Plastisphere1, Plastisphere2, fill = "Plastisphere"),
    size = z$point_mm,
    shape = 21,
    alpha = 0.8
  ) +
  scale_fill_manual(values = pal) +
  theme(
    legend.position = c(0.75, 0.90),
    legend.title = element_blank()
  ) +
  # 图题交由图注承担（58 mm 画布放不下整句标题）
  labs(
    x = "Dimension 1",
    y = "Dimension 2"
  ) +
  geom_vline(xintercept = 0, color = "gray", linetype = 2, linewidth = z$line_mm) +
  geom_hline(yintercept = 0, color = "gray", linetype = 2, linewidth = z$line_mm) +
  geom_abline(intercept = 0, slope = X[1, 2] / X[1, 1], linewidth = z$line_mm) +
  geom_abline(intercept = 0, slope = X[2, 2] / X[2, 1], linewidth = z$line_mm) +
  annotate(
    "text",
    label = ann,
    x = -Inf,
    y = Inf,
    hjust = -0.05,
    vjust = 1.1,
    size = eco_text_mm(7),
    colour = eco_ink
  )

p1

# 成品 58 × 58 mm；width 必须写在 height 之前（check_dimensions 解析口径）
ggsave(plot = p1, "Procrustes_plastisphere_seawater.pdf", width = 58, height = 58,
       units = "mm", device = cairo_pdf)
