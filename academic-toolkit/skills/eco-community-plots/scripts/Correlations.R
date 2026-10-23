
library(ggplot2)
library(dplyr)
library(tidyr)
library(ggpmisc)
library(cowplot)
library(gridExtra)
library(grid)

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

theme_set(eco_theme(90))   # 画布宽 90 mm：theme_classic(base_family = eco_font())
z <- eco_sizes(90)

data <- read.csv("envfactors_abundance.csv", header = TRUE)

# Okabe-Ito 分类色（按 Carrier 因子水平命名，两套 scale 共用一张映射）
carrier_pal <- eco_pal_named(data$Carrier)

plot_env_factor <- function(data, x_var, y_var = "Harm_toxic") {
  p13 <- ggplot(data, aes(x = .data[[x_var]], y = .data[[y_var]])) +
    geom_point(aes(fill=Carrier, color=Carrier), shape = 21,
               size = z$point_mm, stroke = z$line_mm, alpha = 0.7) +
    scale_color_manual(values=carrier_pal)+
    scale_fill_manual(values=carrier_pal)+
    theme(
      axis.ticks = element_blank(), 
      axis.title.y = element_blank()) +
    geom_smooth(aes(color = Carrier), method = 'lm', formula = y ~ x, se = TRUE, show.legend = FALSE) + ##拟合普通线性回归
    stat_poly_eq(aes(color = Carrier,
                     label = paste(after_stat(rr.label), after_stat(p.value.label), sep = '~`,`~')), #添加回归公式
                 formula = y ~ x, parse = TRUE, 
                 size = eco_text_mm(7), 
                 label.x.npc = 'right', label.y.npc = 'top')
  return(p13)
}

env_factors <- c("Temp", "pH", "Salinity","NO3","PO4","DOC")
plots_list <- lapply(env_factors, function(var) plot_env_factor(data, var))


for (i in 1:length(plots_list)) {
  plots_list[[i]] <- plots_list[[i]] + theme(legend.position = "none")
}

legend <- get_legend(plots_list[[1]] + theme(legend.position = "bottom"))


combined_plots <- grid.arrange(grobs = plots_list, ncol = 2, nrow = 3)


final_plot <- grid.arrange(combined_plots, legend,nrow = 1)


common_y_label <- textGrob("Total abundance of harmful and toxic algae", rot = 90, vjust=1,
                           gp = gpar(fontsize = eco_sizes(90)$axis_title))
p15 <- grid.arrange(common_y_label,widths = c(0.5, 8),final_plot, nrow = 1) 

# 成品 90 × 120 mm；导出带公共 y 轴标题与图例的最终拼版 p15
# width 必须写在 height 之前（check_dimensions 解析口径）
ggsave(plot = p15, "envfactors_harm_toxic0111.pdf", width = 90, height = 120,
       units = "mm", device = cairo_pdf)
