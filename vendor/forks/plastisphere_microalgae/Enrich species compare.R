

library(ggplot2)
library(ggpmisc)
library(ggsci)
library(reshape)
library(ggpubr)
library(rstatix)

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

lccol3 =c("#96B6C5", "#999999", "#BD554E")


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
  theme(panel.background=element_rect(fill='transparent'),
        panel.grid=element_blank(),
        legend.position="top",
        axis.line.y=element_blank(),
        axis.ticks.y=element_blank(),
        axis.ticks = element_line(color='black'),
        axis.line = element_line(colour = "black"),
        axis.title.x=element_text(colour='black', size=9),
        axis.text=element_text(colour='black',size=9),
        plot.title=element_text(size=10,face="bold",colour="black",hjust=0.5)) +
  scale_x_discrete(limits=levels(diff$variable)) +
  coord_flip()


for (i in 1:17) 
  p2 <- p2 + annotate('rect', xmin=i+0.5, xmax=i+1.5, ymin=-Inf, ymax=Inf, 
                      fill=ifelse(i %% 2 == 0, 'white', 'gray95'))

p2 <- p2 +   geom_errorbar(aes(ymin=conf.low, ymax=conf.high, color = level), 
                           position=position_dodge(0.8), width=0, size= 0.6) +
  geom_point(aes(color = level), shape= 19, size=2.6) +
  geom_text(aes(variable, y = conf.low + 0.2, label = p.adj.signif, color = level), show.legend = F)+
  scale_color_manual(values= lccol3, limits = c("depleted", "ns", "enriched")) +
  geom_hline(aes(yintercept=0), linetype='dashed', color='black') 
  

p2

ggsave(plot = p2, "enrich_harm_toxic_species.pdf", width = 128, height =110, units = c("mm"), dpi = 300)

