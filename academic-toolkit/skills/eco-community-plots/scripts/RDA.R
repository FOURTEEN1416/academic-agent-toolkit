
####RDA环境因子群落结构统计检验可视化

rm(list=ls()) 
library(pacman)
library(ggprism)


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

yanse<-c("#96B6C5","#80C4E9","#EA906C","#B3E2CD","#FDCDAC","cyan3")

scale_factor <- 0.5
p1=ggplot(data=B.rda.data,aes(RDA1,RDA2))+
  geom_point(aes(fill=group),size=1.6,shape = 21)+
  scale_fill_manual(values = yanse)+
  labs(#title = "B RDA plot",
   
       x=paste("RDA1",round(B.rda$CCA$eig[1]/sum(B.rda$CCA$eig)*100,2)," %"),
       y=paste("RDA2",round(B.rda$CCA$eig[2]/sum(B.rda$CCA$eig)*100,2)," %"))+
  geom_hline(yintercept = 0,lty=3)+
  geom_vline(xintercept = 0,lty=3)+
  geom_segment(data=B.rda.env,aes(x=0,y=0,xend=B.rda.env[,1]*scale_factor*0.7,yend=B.rda.env[,2]*scale_factor*0.7),
               colour="#4D869C",size=0.8,arrow=arrow(angle = 35,length=unit(0.3,"cm")))+ #箭头线条颜色
  geom_text(data=B.rda.env,aes(x=B.rda.env[,1]*scale_factor, 
                               y=B.rda.env[,2]*scale_factor,
                               label=rownames(B.rda.env)),size=3,colour="#4D869C", #环境因子颜色
            hjust=(1-sign(B.rda.env[,1]))/2,
            angle=(180/pi)*atan(B.rda.env[,2]/B.rda.env[,1]))+
  ggprism::theme_prism()


p1 <- p1 +theme(legend.position="none", 
                axis.title.y = element_text(size = 8, color = "black",  vjust = 1.9, hjust = 0.5, angle = 90),  # 纵坐标轴标题的外观
                axis.title.x = element_text(size = 8, color = "black",  vjust = 1.9, hjust = 0.5, angle = 0),  # 横坐标轴标题的外观
                #legend.title = element_text(color = "black", size = 10, face = "bold"),  # Legend title appearance
                #legend.text = element_text(color = "black", size = 10, face = "bold"), 
                axis.line = element_line(size = 0.5), # 调整坐标轴线条的粗细
                axis.ticks.length = unit(0.1, "cm") ,
                axis.ticks.x = element_line(size = 0.5),  # 只调整 x 轴刻度线的粗细
                axis.ticks.y = element_line(size = 0.5),    # 只调整 y 轴刻度线的粗细
                axis.text.x = element_text(size = 8, color = "black",  vjust = 0.5, hjust = 0.5, angle = 0),  # X-axis labels appearance
                axis.text.y = element_text(size = 8, color = "black",  vjust = 0.5, hjust = 0.5, angle = 0)) 


p1

ggsave(plot = p1, "RDA_seawater.pdf", height = 58, width = 58, units = "mm") 

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
pie(cor_data$B,labels=labs,init.angle = 90,col=brewer.pal(nrow(cor_data),"Reds"),boder="black")

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

p2 <- ggplot(cor_com, aes(x =tax, y = B.r),size=1) +
  geom_bar(stat = 'identity', width = 0.8,color="black",fill="#96B6C5") +
  scale_fill_manual(guide = FALSE)+
  geom_text(aes(y = B.r+0.005, label = ifelse(B.p==TRUE,"","*")),
            size = 6) +
  #xlab("Environmental factor")+
  ylab(expression(R^"2"))+
  scale_y_continuous(expand = c(0,0))+
  ggprism::theme_prism()+
  theme(#axis.text.x = element_text(angle = 45),
        axis.title.y = element_text(size = 8, color = "black",  vjust = 1.9, hjust = 0.5, angle = 90),  # 纵坐标轴标题的外观
        axis.title.x = element_text(size = 8, color = "black",  vjust = 1.9, hjust = 0.5, angle = 0),  # 横坐标轴标题的外观
        #legend.title = element_text(color = "black", size = 10, face = "bold"),  # Legend title appearance
        #legend.text = element_text(color = "black", size = 10, face = "bold"), 
        axis.line = element_line(size = 0.5), 
        axis.ticks.length = unit(0.1, "cm") ,
        axis.ticks.x = element_line(size = 0.5),  
        axis.ticks.y = element_line(size = 0.5),    
        axis.text.x = element_text(size = 8, color = "black",  vjust = 0.5, hjust = 0.5, angle = 45),  # X-axis labels appearance
        axis.text.y = element_text(size = 8, color = "black",  vjust = 0.5, hjust = 0.5, angle = 0)
        )

p2

ggsave(plot = p2, "boxplot_seawater.pdf", height = 60, width = 68, units = "mm") 



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

yanse<-c("#BD554E","#80C4E9","#EA906C","#B3E2CD","#FDCDAC","cyan3")

scale_factor <- 0.6
p3=ggplot(data=B.rda.data,aes(RDA1,RDA2))+
  geom_point(aes(fill=group),size=1.6,shape = 21)+
  scale_color_manual(values=yanse)+
  scale_fill_manual(values = yanse)+
  labs(#title = "B RDA plot",
    x=paste("RDA1",round(B.rda$CCA$eig[1]/sum(B.rda$CCA$eig)*100,2)," %"),
    y=paste("RDA2",round(B.rda$CCA$eig[2]/sum(B.rda$CCA$eig)*100,2)," %"))+
  geom_hline(yintercept = 0,lty=3)+
  geom_vline(xintercept = 0,lty=3)+
  geom_segment(data=B.rda.env,aes(x=0,y=0,xend=B.rda.env[,1]*scale_factor*0.9,yend=B.rda.env[,2]*scale_factor*0.9),
               colour="#BD554E",alpha=0.7,size=0.8,arrow=arrow(angle = 35,length=unit(0.3,"cm")))+ 
  
  geom_text(data=B.rda.env,aes(x=B.rda.env[,1]*scale_factor,
                               y=B.rda.env[,2]*scale_factor,
                               label=rownames(B.rda.env)),size=3,colour="#BD554E", alpha=0.7,
            hjust=(1-sign(B.rda.env[,1]))/2,angle=(180/pi)*atan(B.rda.env[,2]/B.rda.env[,1]))+
  ggprism::theme_prism()
p3 <-p3+theme(legend.position="none",
              axis.title.y = element_text(size = 8, color = "black",  vjust = 1.9, hjust = 0.5, angle = 90), 
              axis.title.x = element_text(size = 8, color = "black",  vjust = 1.9, hjust = 0.5, angle = 0), 
              axis.line = element_line(size = 0.5), 
              axis.ticks.length = unit(0.1, "cm") ,
              axis.ticks.x = element_line(size = 0.5), 
              axis.ticks.y = element_line(size = 0.5),   
              axis.text.x = element_text(size = 8, color = "black",  vjust = 0.5, hjust = 0.5, angle = 0),  # X-axis labels appearance
              axis.text.y = element_text(size = 8, color = "black",  vjust = 0.5, hjust = 0.5, angle = 0)) 

p3

ggsave(plot = p3, "RDA_Plas.pdf", height = 58, width = 58, units = "mm")

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
pie(cor_data$B,labels=labs,init.angle = 90,col=brewer.pal(nrow(cor_data),"Reds"),boder="black")

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
p4 <- ggplot(cor_com, aes(x =tax, y = B.r),size=2) +
  geom_bar(stat = 'identity', width = 0.8,color="black",fill="#BD554E", alpha=0.7) +
  scale_fill_manual(guide = FALSE)+
  geom_text(aes(y = B.r+0.005, label = ifelse(B.p==TRUE,"","*")),
            size = 6) +
  ylab(expression(R^"2"))+
  scale_y_continuous(expand = c(0,0))+
  ggprism::theme_prism()+
  theme(#axis.text.x = element_text(angle = 45),
    axis.title.y = element_text(size = 8, color = "black",  vjust = 1.9, hjust = 0.5, angle = 90),  # 纵坐标轴标题的外观
    axis.title.x = element_text(size = 8, color = "black",  vjust = 1.9, hjust = 0.5, angle = 0),  # 横坐标轴标题的外观
    axis.line = element_line(size = 0.5), 
    axis.ticks.length = unit(0.1, "cm") ,
    axis.ticks.x = element_line(size = 0.5),  
    axis.ticks.y = element_line(size = 0.5),  
    axis.text.x = element_text(size = 8, color = "black",  vjust = 0.5, hjust = 0.5, angle = 45),  # X-axis labels appearance
    axis.text.y = element_text(size = 8, color = "black",  vjust = 0.5, hjust = 0.5, angle = 0))

p4

ggsave(plot = p4, "boxplot_plastisphere.pdf", height = 60, width = 68, units = "mm") 
