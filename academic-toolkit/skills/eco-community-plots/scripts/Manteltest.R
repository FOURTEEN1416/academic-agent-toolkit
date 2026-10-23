
library(dplyr)
library(linkET)
library(ggplot2)

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

theme_set(eco_theme(138))   # 画布宽 138 mm：theme_classic(base_family = eco_font())

df <- read.table("otutab_mantel.txt",header = T,row.names = 1)
env <- read.table("envfactors.txt",header = T,row.names = 1)
df <- as.data.frame(df) 
env <- as.data.frame(env) 

df_mantel <- mantel_test(df, env,
                        spec_select = list(Plastisphere= 74: 148,
                                           Ambient = 1:74)
                      ) %>% 
  mutate(rd = cut(r, breaks = c(-Inf, 0.2, 0.4, Inf), 
                  labels = c("< 0.2", "0.2 - 0.4", ">= 0.4")), 
         pd = cut(p, breaks = c(-Inf, 0.01, 0.05, Inf),
                  labels = c("< 0.01", "0.01 - 0.05", ">= 0.05")))


p33<-qcorrplot(correlate(env, method = "spearman"), type = "lower", diag = FALSE) +# 计算环境数据的相关性并绘制热图
  geom_square() +
  geom_couple(aes(colour = pd, size = rd), 
              data = df_mantel, 
              curvature = 0.1) +
  # 连续相关热图保留发散色带（不分类型板；深红=正相关、深蓝=负相关）
  scale_fill_gradientn(colours = RColorBrewer::brewer.pal(11, "RdBu")) +
  scale_size_manual(values = c(0.5, 1, 2)) +
  # 显著性分级用 Okabe-Ito 语义色：强≈朱红、中≈橙、不显著≈中性灰
  scale_colour_manual(values = eco_pval_pal) +
  guides(size = guide_legend(title = "Mantel's r",
                             override.aes = list(colour = "grey35"), 
                             order = 2),
         colour = guide_legend(title = "P-value", 
                               override.aes = list(size = 3), 
                               order = 1),
         fill = guide_colorbar(title = "Spearman’s r", order = 3)) 

p33

# 成品 138 × 98 mm；width 必须写在 height 之前（check_dimensions 解析口径）
ggsave("Mantel0111.pdf", plot = p33, width = 138, height = 98,
       units = "mm", device = cairo_pdf)
