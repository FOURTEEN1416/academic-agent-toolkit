
library(ggplot2)
library(dplyr)
library(tidyr)
library(ggpmisc)
library(cowplot)
library(gridExtra)
library(grid)

data <- read.csv("envfactors_abundance.csv", header = TRUE)

plot_env_factor <- function(data, x_var, y_var = "Harm_toxic") {
  p13 <- ggplot(data, aes_string(x = x_var, y = y_var)) +
    geom_point(aes(fill=Carrier), shape = 21, size = 1, alpha = 0.7) +
    geom_point(aes(color=Carrier), alpha = 0.7) +
    scale_color_manual(values=c("#BD554E","#96B6C5","#9CAFAA","#F2C18D","#7F9F80","#B5C18E","#DD5F60","#FFDA78","#F2B379","#DD8CBC"))+
    scale_fill_manual(values=c("#BD554E","#96B6C5","#9CAFAA","#F2C18D","#7F9F80","#B5C18E","#DD5F60","#FFDA78","#F2B379","#DD8CBC"))+
    theme_bw()+
    theme(
      axis.title.x = element_text(size = 8),
      axis.ticks = element_blank(), 
      axis.text.x = element_text(size = 8), 
      axis.text.y = element_text(size = 8),  
      axis.title.y = element_blank()) +
    geom_smooth(aes(color = Carrier), method = 'lm', formula = y ~ x, se = TRUE, show.legend = FALSE) + ##拟合普通线性回归
    stat_poly_eq(aes(color = Carrier,
                     label = paste(..rr.label.., stat(p.value.label), sep = '~`,`~')), #添加回归公式
                 formula = y ~ x, parse = TRUE, 
                 size = 3, 
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

common_y_label <- textGrob("Total abundance of harmful and toxic algae", rot = 90, vjust=1, gp = gpar(fontsize = 8))
p15 <- grid.arrange(common_y_label,widths = c(0.5, 8),final_plot, nrow = 1) 

ggsave(plot = combined_plots,"envfactors_harm_toxic0111.pdf", width =90, height =120, units = c("mm"), dpi = 300)







