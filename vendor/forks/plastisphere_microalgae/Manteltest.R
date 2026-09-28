
library(dplyr)
library(linkET)
library(ggplot2)

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
  scale_fill_gradientn(colours = RColorBrewer::brewer.pal(11, "RdBu")) +
  scale_size_manual(values = c(0.5, 1, 2)) +
  scale_colour_manual(values = c("#D95F02","#bcb9bd","#1B9E77")) +
  guides(size = guide_legend(title = "Mantel's r",
                             override.aes = list(colour = "grey35"), 
                             order = 2),
         colour = guide_legend(title = "P-value", 
                               override.aes = list(size = 3), 
                               order = 1),
         fill = guide_colorbar(title = "Spearman’s r", order = 3)) 

p33

ggsave("Mantel0111.pdf" , plot = p33, width = 138, height =98, units = c("mm"),dpi= 600,)


