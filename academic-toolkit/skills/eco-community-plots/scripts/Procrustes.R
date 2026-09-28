
#####  Procrustes analysis

library(vegan)
library(ggplot2)
library(RColorBrewer)


data1 <- read.csv("otutab_rare_plastisphere.txt", head=TRUE,sep="\t",row.names = 1)
data1 <- data1[which(rowSums(data1) > 0),]
#data <- data[which(rowSums(data) > 0),]
data1 <- t(data1)
pla.dist <- vegdist(data1,method = "bray")

data2 <- read.csv("otutab_rare_seawater.txt", head=TRUE,sep="\t",row.names = 1)
data2 <- data2[which(rowSums(data2) > 0),]
data2 <- t(data2)
seawater.dist <- vegdist(data2,method = "bray")

mantel(pla.dist,seawater.dist)

mds.pla <- monoMDS(pla.dist)
mds.seawater <- monoMDS(seawater.dist)

set.seed(123)
pro.pla.seawater <- procrustes(mds.pla,mds.seawater)

protest(mds.pla,mds.seawater)

Y <- data.frame(
  Seawater1 = pro.pla.seawater$Yrot[, 1],
  Seawater2 = pro.pla.seawater$Yrot[, 2],
  Plastisphere1 = pro.pla.seawater$X[, 1],
  Plastisphere2 = pro.pla.seawater$X[, 2]
)

Y$ID <- rownames(pro.pla.seawater$X)

X <- data.frame(pro.pla.seawater$rotation)

p1 <- ggplot(Y) +
  geom_segment(
    aes(
      x = Seawater1,
      y = Seawater2,
      xend = (Seawater1 + Plastisphere1) / 2,
      yend = (Seawater2 + Plastisphere2) / 2
    ),
    color = "#96B6C5",
    linewidth = 0.5
  ) +
  geom_segment(
    aes(
      x = (Seawater1 + Plastisphere1) / 2,
      y = (Seawater2 + Plastisphere2) / 2,
      xend = Plastisphere1,
      yend = Plastisphere2
    ),
    color = "#BD554E",
    linewidth = 0.5
  ) +
  geom_point(
    aes(Seawater1, Seawater2, fill = "Seawater"),
    size = 1.2,
    shape = 21,
    alpha = 0.8
  ) +
  geom_point(
    aes(Plastisphere1, Plastisphere2, fill = "Plastisphere"),
    size = 1.2,
    shape = 21,
    alpha = 0.8
  ) +
  scale_fill_manual(
    values = c(
      "Seawater" = "#96B6C5",
      "Plastisphere" = "#BD554E"
    )
  ) +
  theme(
    legend.position = c(0.75, 0.90),
    legend.title = element_blank(),
    legend.text = element_text(size = 8),
    legend.key.size = unit(0.3, "cm"),
    panel.grid = element_blank(),
    panel.background = element_rect(color = "black", fill = "transparent"),
    legend.key = element_rect(fill = "transparent"),
    axis.ticks.length = unit(0.4, "lines"),
    axis.ticks = element_line(color = "black"),
    axis.line = element_line(colour = "black"),
    axis.title.x = element_text(colour = "black", size = 8),
    axis.title.y = element_text(colour = "black", size = 8),
    axis.text = element_text(colour = "black", size = 8),
    plot.title = element_text(size = 10, colour = "black", hjust = 0, face = "bold")
  ) +
  labs(
    x = "Dimension 1",
    y = "Dimension 2",
    title = "Correlation between plastisphere and seawater"
  ) +
  geom_vline(xintercept = 0, color = "gray", linetype = 2, linewidth = 0.05) +
  geom_hline(yintercept = 0, color = "gray", linetype = 2, linewidth = 0.05) +
  geom_abline(intercept = 0, slope = X[1, 2] / X[1, 1], linewidth = 0.05) +
  geom_abline(intercept = 0, slope = X[2, 2] / X[2, 1], linewidth = 0.05) +
  annotate(
    "text",
    label = "Procrustes analysis:\n    M2 = 0.764, p-value = 0.001\nMantel test:\n    r = 0.344, p-value = 0.001",
    x = -2,
    y = 1.7,
    size = 2.5,
    hjust = 0
  )

p1


