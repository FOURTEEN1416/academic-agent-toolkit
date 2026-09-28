> 原始抓取件：firecrawl_scrape 2026-09-11，URL https://mp.weixin.qq.com/s/RX8kDQXO038s4fbp8GEshw

# 如何轻松绘制漂亮的树状网络图？

Original 莫北 莫北
SCIPainter
Sep 4, 2026, 10:00 PM

推荐公众号奥智生物，分享前沿组学技术、实用生信技能、数据挖掘思路

（注：文首账号互推卡片略）

前段时间，看到一个用于展示KEGG富集分析结果的圆形树状网络图，如下图，我觉得还挺好看的！

![Image](https://mmbiz.qpic.cn/sz_mmbiz_png/S8BTv76IG5BKYYhicwZUicicWalOQsZXgXAY0pIjpf8hvo4xN6cicLO14LlWN0AHtcepliad8icguPH8QrdW693KwxtV7RiafIiabCQv7Gd1vG4R220/640?wx_fmt=png&from=appmsg&watermark=1#imgIndex=0)

那么，如何轻松复现出这般好看的圆形树状网络图？接下来，以一份具体的数据为例，看下如何使用豆包 + Rstudio 完成绘制吧！

## 01 数据准备

示例数据主要需要3列即可，如下图，B列对应KEGG_A_class，C列对应KEGG Pathway，D列对应富集因子。注意，这里的示例数据来自OmicShare KEGG富集分析工具的分析结果！

![Image](https://mmbiz.qpic.cn/sz_mmbiz_png/S8BTv76IG5BszricRT676CpaZRpLcWEKAZQoXrPXAxchtLIyczGic0ZWmzI2TrKXr3ibZKt7FvbcAMvdKzLib5LppVyEP35yU40CJJrB4l5DawI/640?wx_fmt=png&from=appmsg&watermark=1#imgIndex=1)

## 02 绘图测试

打开工具页面，点击+号图标将示例数据和图片上传到附件，并输入提示词，如下图。

![Image](https://mmbiz.qpic.cn/mmbiz_png/S8BTv76IG5CMEXWkH7L3nJicNmiceHpPVFXJ6JhYaaXTGlgzbcZXwzibWNowhnyES7cRl5icy206yh24xkJ0gZJvWyjTF9zfqaKGD1x53AsB7cs/640?wx_fmt=png&from=appmsg&watermark=1#imgIndex=2)

尝试输入绘图提示词：使用附件中 "kegg2.csv" 文件，绘制附件中 "Rplot1.svg" 这样的树状图，给出 R 语言绘图代码，要求代码中包含自定义配色部分，并在关键步骤添加中文注释

很快，豆包给出了带有详细注释的绘图代码，如下图，代码块下方的为关键代码说明和使用方法。

![Image](https://mmbiz.qpic.cn/mmbiz_png/S8BTv76IG5C4WkIeQDRVLicniaY9c1M2trRnIbazQ976EFIY5TibBZlzy29Ij0zMqslWWL6fGLt1snEDiaN2CnmJ9FgKMnDLVEpR0gjHoicicKaGM/640?wx_fmt=png&from=appmsg&watermark=1#imgIndex=3)

![Image](https://mmbiz.qpic.cn/sz_mmbiz_png/S8BTv76IG5Cp93Smep24mBSBh30StBNiclPwZf0B8ATEibeQDEziaVCNkPFuK5ULwsJbdNbfx1DOntFHTQJHdmyl5HRMPP12nXpvI6MQMyuh8Y/640?wx_fmt=png&from=appmsg&watermark=1#imgIndex=4)

将生成的代码复制粘贴到Rstudio的脚本编辑器中进行测试，如下图，注意在读入数据前，将示例数据文件所在文件夹设置为"工作目录"。

![Image](https://mmbiz.qpic.cn/mmbiz_png/S8BTv76IG5Dk0gqXTDAQUdDu85TAU1ROedLZYsrSkBC85pjr74QpNRHIKKhEgUGmX2JKOP80rjgqSBGrnIVQYwJUTP0Oib6GhvFkPu2TYj4g/640?wx_fmt=png&from=appmsg&watermark=1#imgIndex=5)

初始的分析绘图结果如下：

![Image](https://mmbiz.qpic.cn/sz_mmbiz_png/S8BTv76IG5ARP5jehThmJmO1M4Qd4EhwPqtuoZEFI2rBibGzib4BMRtBMTjGDWFTgzp813SZeuia2IL2Oq450UdTvhCAbPNMkic2WpbQgnTQWg4/640?wx_fmt=png&from=appmsg&watermark=1#imgIndex=6)

## 03 图形调整

初始结果图表已基本满足我们的需求，不过图中网络图的边为灰色，我们可以通过豆包继续对上文的代码进行优化，使网络图边的颜色与相连的 "末端" 节点相同。

尝试输入绘图提示词：基于上文给出的 R 代码，添加自定义调整边（连线）颜色的部分代码，使边的颜色与相连的 "末端" 节点相同

![Image](https://mmbiz.qpic.cn/sz_mmbiz_png/S8BTv76IG5BP6nKqXib8BuQJyIicDN52sPjJBSP8s2gYBJmQCV9n0I45ShQrD7mpia8hCRLfyf0QhbdVib4EQ6R8Xu3uwdxuwPBia5bd173nyZfo/640?wx_fmt=png&from=appmsg&watermark=1#imgIndex=7)

![Image](https://mmbiz.qpic.cn/mmbiz_png/S8BTv76IG5DSBYmj0Xbl8aR6etPxhpQRq4FK71v0sUJscib2TiaWjicecxGXYmEKYZdAXelzwUQOo65kFD8c3H7FvEE39NrZ9l849bMlLep7cI/640?wx_fmt=png&from=appmsg&watermark=1#imgIndex=8)

继续将生成的代码复制粘贴到Rstudio的脚本编辑器中进行测试，绘图效果如下图。

![Image](https://mmbiz.qpic.cn/mmbiz_png/S8BTv76IG5AYBX5xW2yH4qibibib6JevCr23d6N1niaWJVPvM3Drx9MTFsLWR9YeaY7UYeBjv5QwogChkY1rmqXMpWE7dnic1MiaKEXYic9SzPP4LQ/640?wx_fmt=png&from=appmsg&watermark=1#imgIndex=9)

当然，如果对原文的配色不满意，我们也可以尝试自定义其他配色，如下图。

![Image](https://mmbiz.qpic.cn/sz_mmbiz_png/S8BTv76IG5BGibibftC2pQ2iaWQu6lmQ7PhJjwzdet3c7DDSZysQFxzicZwJWP68I705B0aNCjSXlepYIZYgez38nqObKGF9ljSPd4O503fTQ2o/640?wx_fmt=png&from=appmsg&watermark=1#imgIndex=10)

最终的绘图效果如下图：

![Image](https://mmbiz.qpic.cn/mmbiz_png/S8BTv76IG5CKwDl8aiaIYuF9d4IFcATMdYqq8WZDpPmsawTWOmiadVTVaRjlgMm24DpPnIiaFFORhuZ6lzFgiaGbZb7qy4CoSMrqicicBNia23Fqp0/640?wx_fmt=png&from=appmsg&watermark=1#imgIndex=11)

调整后的绘图代码如下：

```r
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
```

好了，本次的豆包复现圆形树状网络图实操教程就分享到这里啦！

（注：文末为基迪奥生物服务推广与版权声明，属商业物料，未收录。*未经许可，不得以任何方式复制或抄袭本篇文章之部分或全部内容。版权所有，侵权必究。— SCIPainter 分享科研绘图技能与工具）
