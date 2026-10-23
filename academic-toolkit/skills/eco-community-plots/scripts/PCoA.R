
### 的PCoA
rm(list=ls())

library(vegan)
library(ape)
library(ggplot2)
library(grid)
library(digest)

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

theme_set(eco_theme(100))   # 画布宽 100 mm：theme_classic(base_family = eco_font())

groups <- read.csv("metadata.csv", header = T, row.names = 1)
comm <- read.csv("otutab.csv", row.names = 1)


df = t(comm)
data <- vegdist(df, method = "bray")
pcoa<- pcoa(data, correction = "none", rn = NULL)

#### 计算PC1和PC2
PCA1 = pcoa$vectors[,1]
PCA2 = pcoa$vectors[,2]

# Okabe-Ito 前两色：蓝=主组、橙=对照组（色盲安全最强对比对）
cbbPalette <- eco_pal(2)

plotdata <- data.frame(rownames(pcoa$vectors),PCA1,PCA2,groups$Carrier,groups$Region)
#设置行名称
colnames(plotdata) <-c("sample","PCA1","PCA2","Carrier")
## 转换PC比例
pca1 <-floor(pcoa$values$Relative_eig[1]*100)
pca2 <-floor(pcoa$values$Relative_eig[2]*100)
plotdata$Carrier <- factor(plotdata$Carrier,levels = c("Plastisphere","Seawater"))



library(dplyr)
yf <- plotdata
yd1 <- yf %>% group_by(Carrier) %>% summarise(Max = max(PCA1))
yd2 <- yf %>% group_by(Carrier) %>% summarise(Max = max(PCA2))
yd1$Max <- yd1$Max + max(yd1$Max)*0.1
yd2$Max <- yd2$Max + max(yd2$Max)*0.1

fit1 <- aov(PCA1~Carrier,data = plotdata)

library(multcomp)
tuk1<-glht(fit1,linfct=mcp(Carrier="Tukey"))
res1 <- cld(tuk1,level=0.05)

fit2 <- aov(PCA2~Carrier,data = plotdata)
tuk2<-glht(fit2,linfct=mcp(Carrier="Tukey"))
res2 <- cld(tuk2,level=0.05)


test <- data.frame(PCA1 = res1$mcletters$Letters,PCA2 = res2$mcletters$Letters,
                   yd1 = yd1$Max,yd2 = yd2$Max,Carrier = yd1$Carrier)
test$Carrier <- factor(test$Carrier,levels = c("Plastisphere","Seawater"))

box1 <- ggplot(plotdata,aes(Carrier,PCA1)) +
  geom_boxplot(aes(fill = Carrier),alpha = 0.8,
               linewidth = eco_sizes(100)$line_mm) +
  geom_text(data = test,aes(x = Carrier,y = yd1,label = PCA1),
            size = eco_text_mm(8),color = "black",fontface = "bold") +
  coord_flip() +
  scale_fill_manual(values=cbbPalette) +
  theme(axis.title = element_blank(),
        axis.text.x = element_blank(),
        legend.position = "none")


box2 <- ggplot(plotdata,aes(Carrier,PCA2)) +
  geom_boxplot(aes(fill = Carrier),alpha = 0.8,
               linewidth = eco_sizes(100)$line_mm) +
  geom_text(data = test,aes(x = Carrier,y = yd2,label = PCA2),
            size = eco_text_mm(8),color = "black",fontface = "bold") +
  scale_fill_manual(values=cbbPalette) +
  theme(axis.title = element_blank(),
        axis.text.x = element_text(angle = 45, vjust = 1, hjust = 1),
        axis.text.y = element_blank(),
        legend.position = "none")




p2<-ggplot(plotdata, aes(PCA1, PCA2)) +

  geom_point(aes(color=Carrier),
             size=eco_sizes(100)$point_mm,
             alpha = 0.8)+
  stat_ellipse(aes(color=Carrier),linetype = 1,
               linewidth = 1.5 * eco_sizes(100)$line_mm,  alpha = 0.5)+
  scale_color_manual(values=cbbPalette)+
  xlab(paste("PCoA1 ( ",pca1,"%"," )",sep="")) +
  ylab(paste("PCoA2 ( ",pca2,"%"," )",sep="")) +
  geom_vline(aes(xintercept = 0),linetype="dotted")+
  geom_hline(aes(yintercept = 0),linetype="dotted")+
  theme(legend.position = c(0.76,0.18),
        legend.key = element_blank()) +
  guides(fill = guide_legend(ncol = 1))
p2



###PERMANOVA计算R2
otu.adonis=adonis2(data~Carrier,data = groups,distance = "bray")
R2=otu.adonis$R2[1]
pvalue=otu.adonis$`Pr(>F)`[1]
adonis<-paste("PERMANOVA:\nR2=",round(R2,4),
              "\nP-value=",pvalue)

p4 <- ggplot(plotdata, aes(PCA1, PCA2)) +
  geom_text(aes(x = -0.5,y = 0.6,label = adonis),
            size = eco_text_mm(8)) +
  xlab("") + ylab("") +
  theme(axis.title = element_blank(),
        axis.line = element_blank(),
        axis.ticks = element_blank(),
        axis.text = element_blank())

p4

library(patchwork)


pcoa <- box1 + p4 + p2 + box2 +
  plot_layout(heights = c(1,4),widths = c(4,1),ncol = 2,nrow = 2)
pcoa


# 成品 100 × 106 mm；width 必须写在 height 之前（check_dimensions 解析口径）
ggsave(plot = pcoa, "PCoA_carrier.pdf", width = 100, height = 106,
       units = "mm", device = cairo_pdf)
