

library(ggplot2)
library(ggpmisc)
library(ggsci)
library(reshape)
library(ggpubr)
library(rstatix)

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

theme_set(eco_theme(128))   # 画布宽 128 mm：theme_classic(base_family = eco_font())
z <- eco_sizes(128)

mydata<- read.csv("harm_toxic_species_enrich.csv",row.names = 1)

mydata1<-scale(mydata)
write.csv(mydata1, "enrich_species_zscore.csv", quote = F, row.names = T)

mydata1<- read.csv("enrich_species_zscore.csv")

group <- read.csv("metadata_stamp.csv", check.names = FALSE)
dat = as.data.frame(melt(mydata1, id.vars=c("sample")))
head(dat)

dat$group <- group$group
df <- dat %>% group_by(variable) %>% pairwise_wilcox_test(value ~ group, detailed = T)
df[which(df$p < 0.05& df$estimate>0),'level'] <- 'enriched'
df[which(df$p < 0.05& df$estimate<0),'level'] <- 'depleted'
df[which(df$p >=0.05),'level'] <- 'ns'
write.csv(df, "enrich_species_compare_zscore1.csv", quote = F, row.names = F)

# Okabe-Ito 富集方向语义：enriched=朱红、depleted=蓝、ns=中性灰


diff=read.csv("enrich_species_compare_zscore_filter.csv", header=T) 

head(diff)

#固定x轴顺序
order_list <- c("Chaetoceros.socialis", "Cylindrotheca.closterium", "Halamphora.coffeiformis", "Nitzschia.longissima",
                "Pseudo.nitzschia.cuspidata","Skeletonema.marinoi","Thalassiosira.allenii",
                "Chrysochromulina.leadbeateri","Cyclotella.meneghiniana","Dinophysis.acuminata",
                
                "Gymnodinium.catenatum","Heterocapsa.triquetra","Plagioselmis.prolonga",
                "Protodinium.simplex","Prymnesium.polylepis",
                "Pseudo.nitzschia.australis","Pseudocochlodinium.profundisulcus",
                
                "Teleaulax.acuta")


diff$variable <- factor(diff$variable, levels = rev(order_list))

p2 <- ggplot(diff,aes(variable, estimate)) +
  xlab("") +
  ylab("Difference (%)") +
  theme(legend.position="top",
        axis.line.y=element_blank(),
        axis.ticks.y=element_blank()) +
  scale_x_discrete(limits=levels(diff$variable)) +
  coord_flip()


# 隔行底色按实际行数生成（不再写死 17 行）
for (i in seq_len(nrow(diff))) 
  p2 <- p2 + annotate('rect', xmin=i+0.5, xmax=i+1.5, ymin=-Inf, ymax=Inf, 
                      fill=ifelse(i %% 2 == 0, 'white', 'gray95'))

p2 <- p2 +   geom_errorbar(aes(ymin=conf.low, ymax=conf.high, color = level), 
                           position=position_dodge(0.8), width=0, linewidth= 1.5 * z$line_mm) +
  geom_point(aes(color = level), shape= 19, size=1.8 * z$point_mm) +
  geom_text(aes(variable, y = conf.low + 0.2, label = p.adj.signif, color = level),
            size = eco_text_mm(6), show.legend = F)+
  scale_color_manual(values = eco_sign_pal) +
  geom_hline(aes(yintercept=0), linetype='dashed', color='black') 
  

p2

# 成品 128 × 110 mm；width 必须写在 height 之前（check_dimensions 解析口径）
ggsave(plot = p2, "enrich_harm_toxic_species.pdf", width = 128, height = 110,
       units = "mm", device = cairo_pdf)
