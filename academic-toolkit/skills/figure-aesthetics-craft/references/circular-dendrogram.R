# ---------- 0. 安装并加载所需包 ----------
# install.packages(c("ggraph", "igraph", "tidygraph", "dplyr", "readr"))
library(ggraph)
library(igraph)
library(tidygraph)
library(dplyr)
library(readr)

# ============================================================
# 1. 自定义参数配置区
# ============================================================
input_file <- "kegg2.csv"
output_file <- "KEGG_circular_dendrogram.png"
output_svg <- "KEGG_circular_dendrogram.svg"

# --- 1.1 自定义配色（6 个 class）---
class_colors <- c(
  "Metabolism" = "#80d52b",                             # 紫色
  "Genetic Information Processing" = "#427f02",          # 绿色
  "Environmental Information Processing" = "#83c2e6",    # 金黄
  "Cellular Processes" = "#557bc7",                      # 珊瑚红
  "Organismal Systems" = "#e12afa",                      # 粉红
  "Human Diseases" = "#fa0aa1"                           # 青绿
)
root_color <- "#cbf2a8"          # 中心根节点颜色
size_min <- 2
size_max <- 12
label_size <- 2.5
class_label_size <- 3
root_label_size <- 3
text_color <- "grey30"

# ★★★新增：边（连线）参数★★★
edge_width <- 0.6                # 连线粗细
edge_alpha <- 0.5                # 连线透明度（0~1，越小越透明）
# 边的颜色将自动与末端节点一致，无需在此单独设置颜色

fig_width <- 14
fig_height <- 14
fig_dpi <- 300

# ============================================================
# 2. 数据读取与预处理
# ============================================================
df <- read_csv(input_file, show_col_types = FALSE) %>%
  select(class, pathway, ratio)
cat("共读取", nrow(df), "条通路数据，涵盖", length(unique(df$class)), "个大类\n")

# ============================================================
# 3. 构建三层树状图的边列表（edge list）
#    层级：kegg(根) → class → pathway
# ★★★关键改动：每条边增加 edge_class 列，记录末端节点所属的 class ★★★
# ============================================================
# --- 3.1 根节点到 class 的边 ---
# 末端是 class 节点，edge_class 就是该 class 本身
edge_root_class <- data.frame(
  from        = "kegg",
  to          = unique(df$class),
  edge_class  = unique(df$class),    # ★末端节点的 class
  stringsAsFactors = FALSE
)

# --- 3.2 class 到 pathway 的边 ---
# 末端是 pathway 节点，edge_class 是该 pathway 所属的 class
edge_class_path <- data.frame(
  from        = df$class,
  to          = df$pathway,
  edge_class  = df$class,            # ★末端节点所属的 class
  stringsAsFactors = FALSE
)

# --- 3.3 合并所有边 ---
edges <- rbind(edge_root_class, edge_class_path)

# ============================================================
# 4. 构建节点属性表
# ============================================================
nodes_root <- data.frame(
  name  = "kegg",
  type  = "root",
  class = NA_character_,
  ratio = NA_real_,
  stringsAsFactors = FALSE
)
nodes_class <- data.frame(
  name  = unique(df$class),
  type  = "class",
  class = unique(df$class),
  ratio = NA_real_,
  stringsAsFactors = FALSE
)
nodes_path <- df %>%
  mutate(type = "pathway") %>%
  select(name = pathway, type, class, ratio)

nodes <- rbind(nodes_root, nodes_class, nodes_path)

# --- 4.1 创建图对象（edges 中已包含 edge_class 属性）---
graph <- tbl_graph(nodes = nodes, edges = edges, directed = TRUE)
cat("图对象构建完成：", length(V(graph)), "个节点，", length(E(graph)), "条边\n")

# ============================================================
# 5. 绘制圆形树状图
# ============================================================
p <- ggraph(graph, layout = "dendrogram", circular = TRUE) +

  # --- 5.1 绘制边（连线）★★★颜色映射到末端节点的 class ★★★ ---
  # edge_class 是边列表中的属性，用 aes(color = edge_class) 绑定颜色
  geom_edge_diagonal(
    aes(color = edge_class),     # ★边的颜色 = 末端节点所属 class 的颜色
    width    = edge_width,
    alpha    = edge_alpha,
    lineend  = "round",
    show.legend = FALSE          # 不显示边的图例（与节点颜色一致，无需重复）
  ) +

  # --- 5.2 根节点（kegg）---
  geom_node_point(
    data = . %>% filter(type == "root"),
    aes(x = x, y = y),
    size  = 18,
    color = root_color,
    alpha = 0.55
  ) +

  # --- 5.3 class 节点（第二层大圆）---
  geom_node_point(
    data = . %>% filter(type == "class"),
    aes(x = x, y = y, color = class),
    size  = 12,
    alpha = 0.55,
    show.legend = FALSE
  ) +

  # --- 5.4 pathway 叶子节点（大小映射 ratio）---
  geom_node_point(
    data = . %>% filter(type == "pathway"),
    aes(x = x, y = y,
        size  = ratio,
        color = class),
    alpha = 0.5,
    show.legend = c(size = FALSE, color = FALSE)
  ) +
  scale_size_continuous(range = c(size_min, size_max)) +

  # --- 5.5 节点颜色映射 ---
  scale_color_manual(values = class_colors, na.value = root_color) +

  # ★★★新增：边的颜色映射（必须与节点用同一套配色，才能保证颜色一致）★★★
  # scale_edge_color_manual 是 ggraph 专门用于边颜色的标度函数
  scale_edge_color_manual(
    values  = class_colors,      # 使用与节点完全相同的配色方案
    na.value = "grey70"          # 兜底颜色（理论上不会触发）
  ) +

  # --- 5.6 根节点标签 ---
  geom_node_text(
    data = . %>% filter(type == "root"),
    aes(x = x, y = y, label = name),
    size = root_label_size,
    fontface = "bold",
    color = "white"
  ) +

  # --- 5.7 class 大类标签 ---
  geom_node_text(
    data = . %>% filter(type == "class"),
    aes(x = x, y = y, label = name, color = class),
    size = class_label_size,
    fontface = "bold",
    show.legend = FALSE
  ) +

  # --- 5.8 pathway 叶子标签（径向排列）---
  geom_node_text(
    data = . %>% filter(type == "pathway"),
    aes(x = 1.06 * x, y = 1.06 * y,
        label = name,
        angle = -((-node_angle(x, y) + 90) %% 180) + 90,
        color = class),
    size  = label_size,
    hjust = "outward",
    nudge_x = 0,
    show.legend = FALSE
  ) +

  # --- 5.9 主题 ---
  theme_void() +
  theme(plot.margin = margin(55, 55, 55, 55, unit = "mm")) +
  coord_fixed(clip = "off")

# ============================================================
# 6. 输出保存
# ============================================================
print(p)
ggsave(output_file, p, width = fig_width, height = fig_height,
       dpi = fig_dpi, bg = "white")
ggsave(output_svg, p, width = fig_width, height = fig_height,
       bg = "white")
