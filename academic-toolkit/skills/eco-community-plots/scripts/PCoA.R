

### 的PCoA
rm(list=ls())

library(vegan)
library(ape)
library(ggplot2)
library(grid)
library(digest)


groups <- read.csv("metadata.csv", header = T, row.names = 1)
comm <- read.csv("otutab.csv", row.names = 1)


df = t(comm)
data <- vegdist(df, method = "bray")
pcoa<- pcoa(data, correction = "none", rn = NULL)

#### 计算PC1和PC2
PCA1 = pcoa$vectors[,1]
PCA2 = pcoa$vectors[,2]

cbbPalette <- c("#BD554E","#96B6C5")

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
res1 <- cld(tuk1,alpah=0.05)

fit2 <- aov(PCA2~Carrier,data = plotdata)
tuk2<-glht(fit2,linfct=mcp(Carrier="Tukey"))
res2 <- cld(tuk2,alpah=0.05)


test <- data.frame(PCA1 = res1$mcletters$Letters,PCA2 = res2$mcletters$Letters,
                   yd1 = yd1$Max,yd2 = yd2$Max,Carrier = yd1$Carrier)
test$Carrier <- factor(test$Carrier,levels = c("Plastisphere","Seawater"))

box1 <- ggplot(plotdata,aes(Carrier,PCA1)) +
  geom_boxplot(aes(fill = Carrier),alpha = 0.8) +
  geom_text(data = test,aes(x = Carrier,y = yd1,label = PCA1),
            size = 3,color = "black",fontface = "bold") +
  coord_flip() +
  scale_fill_manual(values=cbbPalette) +
  theme_bw()+
  theme(axis.ticks.length = unit(0.1,"lines"), 
        axis.ticks = element_line(color='black'),
        axis.line = element_line(colour = "black"), 
        axis.title.x=element_blank(),
        axis.title.y=element_blank(),
        axis.text.y=element_text(colour='black',size=8),
        axis.text.x=element_blank(),
        legend.position = "none")


box2 <- ggplot(plotdata,aes(Carrier,PCA2)) +
  geom_boxplot(aes(fill = Carrier),alpha = 0.8) +
  geom_text(data = test,aes(x = Carrier,y = yd2,label = PCA2),
            size = 3,color = "black",fontface = "bold") +
  scale_fill_manual(values=cbbPalette) +
  theme_bw()+
  theme(axis.ticks.length = unit(0.1,"lines"), 
        axis.ticks = element_line(color='black'),
        axis.line = element_line(colour = "black"), 
        axis.title.x=element_blank(),
        axis.title.y=element_blank(),
        axis.text.x=element_text(colour='black',size=8,angle = 45,
                                 vjust = 1,hjust = 1),
        axis.text.y=element_blank(),
        legend.position = "none")





p2<-ggplot(plotdata, aes(PCA1, PCA2)) +

  geom_point(aes(color=Carrier),
             size=2,
             alpha = 0.8)+
  stat_ellipse(aes(color=Carrier),linetype = 1, linewidth = 0.5,  alpha = 0.5)+
  scale_fill_manual(values=cbbPalette)+scale_color_manual(values=cbbPalette)+
  scale_shape_manual(values = c(15,19))+
  xlab(paste("PCoA1 ( ",pca1,"%"," )",sep="")) + 
  ylab(paste("PCoA2 ( ",pca2,"%"," )",sep="")) +
  theme(text=element_text(size=8))+
  geom_vline(aes(xintercept = 0),linetype="dotted")+
  geom_hline(aes(yintercept = 0),linetype="dotted")+
  theme(panel.background = element_rect(fill='white', colour='black'),
        panel.grid=element_blank(), 
        axis.title = element_text(color='black',size=9),
        axis.ticks.length = unit(0.1,"lines"), axis.ticks = element_line(color='black'),
        axis.line = element_line(colour = "black"), 
        axis.title.x=element_text(colour='black', size=8,vjust = 12),
        axis.title.y=element_text(colour='black', size=8,vjust = -8),
        axis.text=element_text(colour='black',size=8),
        legend.title=element_text(size = 8,face = "bold"),
        legend.text=element_text(size=8),
        legend.key=element_blank(),legend.position = c(0.76,0.18),
        #legend.background = element_rect(colour = "black"),
        legend.key.height=unit(0.1,"cm")) +
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
            size = 2) +
  theme_bw() +
  xlab("") + ylab("") +
  theme(panel.grid=element_blank(), 
        axis.title = element_blank(),
        axis.line = element_blank(),
        axis.ticks = element_blank(),
        axis.text = element_blank())

p4

library(patchwork)


pcoa <- box1 + p4 + p2 + box2 + 
  plot_layout(heights = c(1,4),widths = c(4,1),ncol = 2,nrow = 2)
pcoa


ggsave(plot = pcoa, "PCoA_carrier.pdf", height = 100, width = 106, units = "mm")












