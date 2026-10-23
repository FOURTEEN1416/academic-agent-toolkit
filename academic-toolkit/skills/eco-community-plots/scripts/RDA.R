####RDA环境因子群落结构统计检验可视化

rm(list=ls())
library(vegan)
library(ggplot2)
library(dplyr)
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

theme_set(eco_theme(58))   # 主图/显著性图均为 58–68 mm 画布：theme_classic(base_family = eco_font())
z <- eco_sizes(58)


data=read.csv("sum_g_seawater.csv",row.names = 1)
env=read.csv("envfactors_seawater.csv",row.names = 1)

B.rda=rda(t(data),env[-1],scale = T)

B.rda.data=data.frame(B.rda$CCA$u[,1:2],
                      env$Treat)

colnames(B.rda.data)=c("RDA1","RDA2","group")
head(B.rda.data,n=3)

B.rda.env <- B.rda$CCA$biplot[,1:2]
B.rda.env <- as.data.frame(B.rda.env)
head(B.rda.env,n=3)

yanse <- eco_pal_named(B.rda.data$group)

scale_factor <- 0.5
p1=ggplot(data=B.rda.data,aes(RDA1,RDA2))+
  geom_point(aes(fill=group),size=z$point_mm,shape = 21)+
  scale_fill_manual(values = yanse)+
  labs(#title = "B RDA plot",
   
       x=paste("RDA1",round(B.rda$CCA$eig[1]/sum(B.rda$CCA$eig)*100,2)," %"),
       y=paste("RDA2",round(B.rda$CCA$eig[2]/sum(B.rda$CCA$eig)*100,2)," %"))+
  geom_hline(yintercept = 0,lty=3)+
  geom_vline(xintercept = 0,lty=3)+
  geom_segment(data=B.rda.env,aes(x=0,y=0,xend=B.rda.env[,1]*scale_factor*0.7,yend=B.rda.env[,2]*scale_factor*0.7),
               colour=eco_ink,linewidth=1.5*z$line_mm,
               arrow=arrow(angle = 35,length=unit(0.3,"cm")))+ #箭头线条颜色
  geom_text(data=B.rda.env,aes(x=B.rda.env[,1]*scale_factor,
                               y=B.rda.env[,2]*scale_factor,
                               label=rownames(B.rda.env)),
            size=eco_text_mm(7),colour=eco_ink,
            hjust=(1-sign(B.rda.env[,1]))/2,
            angle=(180/pi)*atan(B.rda.env[,2]/B.rda.env[,1]))


p1 <- p1 + theme(legend.position="none")
p1

# 成品 58 × 58 mm；width 必须写在 height 之前（check_dimensions 解析口径）
ggsave(plot = p1, "RDA_seawater.pdf", width = 58, height = 58,
       units = "mm", device = cairo_pdf)

#统计
B.sum=summary(B.rda)
B.sum$constr.chi/B.sum$tot.chi 
B.sum$unconst.chi/B.sum$tot.chi

cor_data=data.frame(row.names = c("Explained","Unexplained"),
                    B=c(B.sum$constr.chi/B.sum$tot.chi,B.sum$unconst.chi/B.sum$tot.chi))
cor_data$group=rownames(cor_data)
head(cor_data,n=3) 
cor_data <- data.frame(cor_data)
cor_data=arrange(cor_data,B)
head(cor_data,n=3) 
labs<-paste0(cor_data$group,"\n(",round(cor_data$B/sum(cor_data$B)*100,2),"%)")
# 饼图仅作交互速览，不产出文件（批处理下不生成 Rplots.pdf）
if (interactive()) {
  pie(cor_data$B,labels=labs,init.angle = 90,col=brewer.pal(nrow(cor_data),"Reds"),border="black")
}

#anova.cca检验
B.perm=permutest(B.rda,permu=999) 
B.perm 

B.ef=envfit(B.rda,env[-1],permu=999)
B.ef$vectors$r
B.ef$vectors$pvals

cor_com=data.frame(tax=rownames(B.rda.env),B.r=B.ef$vectors$r,B.p=B.ef$vectors$pvals)
cor_com=arrange(cor_com,B.r)
head(cor_com,n=3)

cor_com[c(3)]=cor_com[c(3)]>0.05

#envfit检验可视化
cor_com$tax = factor(cor_com$tax,order = T,levels = row.names(cor_com))#按R2值排序

p2 <- ggplot(cor_com, aes(x =tax, y = B.r)) +
  geom_bar(stat = 'identity', width = 0.8,color="black",fill=eco_okabe[["blue"]]) +
  geom_text(aes(y = B.r+0.005, label = ifelse(B.p==TRUE,"","*")),
            size = eco_text_mm(8)) +
  #xlab("Environmental factor")+
  ylab(expression(R^"2"))+
  scale_y_continuous(expand = c(0,0))+
  theme(axis.text.x = element_text(angle = 45, vjust = 0.5, hjust = 0.5))

p2

# 成品 60 × 68 mm
ggsave(plot = p2, "boxplot_seawater.pdf", width = 60, height = 68,
       units = "mm", device = cairo_pdf)



#####  plastisphere
data=read.csv("sum_g_plas.csv",row.names = 1)
env=read.csv("envfactors_plas.csv",row.names = 1)

B.rda=rda(t(data),env[-1],scale = T)
B.rda.data=data.frame(B.rda$CCA$u[,1:2],env$Treat)

colnames(B.rda.data)=c("RDA1","RDA2","group")
head(B.rda.data,n=3)

B.rda.spe=data.frame(B.rda$CCA$v[,1:2])
B.rda.spe=as.data.frame(B.rda.spe)
B.rda.spe$Species<-rownames(B.rda.spe)
head(B.rda.spe,n=3)

B.rda.env <- B.rda$CCA$biplot[,1:2]
B.rda.env <- as.data.frame(B.rda.env)
head(B.rda.env,n=3)

yanse <- eco_pal_named(B.rda.data$group)

scale_factor <- 0.6
p3=ggplot(data=B.rda.data,aes(RDA1,RDA2))+
  geom_point(aes(fill=group),size=z$point_mm,shape = 21)+
  scale_fill_manual(values = yanse)+
  labs(#title = "B RDA plot",
    x=paste("RDA1",round(B.rda$CCA$eig[1]/sum(B.rda$CCA$eig)*100,2)," %"),
    y=paste("RDA2",round(B.rda$CCA$eig[2]/sum(B.rda$CCA$eig)*100,2)," %"))+
  geom_hline(yintercept = 0,lty=3)+
  geom_vline(xintercept = 0,lty=3)+
  geom_segment(data=B.rda.env,aes(x=0,y=0,xend=B.rda.env[,1]*scale_factor*0.9,yend=B.rda.env[,2]*scale_factor*0.9),
               colour=eco_ink,alpha=0.7,linewidth=1.5*z$line_mm,
               arrow=arrow(angle = 35,length=unit(0.3,"cm")))+
  
  geom_text(data=B.rda.env,aes(x=B.rda.env[,1]*scale_factor,
                               y=B.rda.env[,2]*scale_factor,
                               label=rownames(B.rda.env)),
            size=eco_text_mm(7),colour=eco_ink, alpha=0.7,
            hjust=(1-sign(B.rda.env[,1]))/2,angle=(180/pi)*atan(B.rda.env[,2]/B.rda.env[,1]))
p3 <- p3 + theme(legend.position="none")

p3

# 成品 58 × 58 mm
ggsave(plot = p3, "RDA_Plas.pdf", width = 58, height = 58,
       units = "mm", device = cairo_pdf)

#统计
B.sum=summary(B.rda)
B.sum$constr.chi/B.sum$tot.chi 
B.sum$unconst.chi/B.sum$tot.chi

cor_data=data.frame(row.names = c("Explained","Unexplained"),
                    B=c(B.sum$constr.chi/B.sum$tot.chi,B.sum$unconst.chi/B.sum$tot.chi))
cor_data$group=rownames(cor_data)
head(cor_data,n=3) 
cor_data <- data.frame(cor_data)
cor_data=arrange(cor_data,B)
head(cor_data,n=3) 
labs<-paste0(cor_data$group,"\n(",round(cor_data$B/sum(cor_data$B)*100,2),"%)")
if (interactive()) {
  pie(cor_data$B,labels=labs,init.angle = 90,col=brewer.pal(nrow(cor_data),"Reds"),border="black")
}

#anova.cca检验
B.perm=permutest(B.rda,permu=999) 
B.perm 
B.ef=envfit(B.rda,env[-1],permu=999)
B.ef$vectors$r
B.ef$vectors$pvals

cor_com=data.frame(tax=rownames(B.rda.env),B.r=B.ef$vectors$r,B.p=B.ef$vectors$pvals)
cor_com=arrange(cor_com,B.r)
head(cor_com,n=3)

cor_com[c(3)]=cor_com[c(3)]>0.05

#envfit检验可视化
cor_com$tax = factor(cor_com$tax,order = T,levels = row.names(cor_com))#按R2值排序
p4 <- ggplot(cor_com, aes(x =tax, y = B.r)) +
  geom_bar(stat = 'identity', width = 0.8,color="black",fill=eco_okabe[["orange"]], alpha=0.7) +
  geom_text(aes(y = B.r+0.005, label = ifelse(B.p==TRUE,"","*")),
            size = eco_text_mm(8)) +
  ylab(expression(R^"2"))+
  scale_y_continuous(expand = c(0,0))+
  theme(axis.text.x = element_text(angle = 45, vjust = 0.5, hjust = 0.5))

p4

# 成品 60 × 68 mm
ggsave(plot = p4, "boxplot_plastisphere.pdf", width = 60, height = 68,
       units = "mm", device = cairo_pdf)
