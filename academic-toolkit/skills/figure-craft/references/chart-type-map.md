# 图型选型与多样化手册（chart-type-map）

> 泛化自一轮真实返工（评审意见"柱形图折线图太多、纯色平涂"）的逐图改法台账。
> 原则：**先问数据语义，再选图型**；换图型是"表达升级"，不是"装饰"。

## 一、选型决策树（数据语义 → 候选图型）

| 数据想表达什么 | 首选 | 次选 | 慎用 |
|----------------|------|------|------|
| 多方案排序对比（离散类目） | 棒棒糖点图 | 渐变条（水平）/ 点阵 | 纯色柱状（>5 根即单调） |
| 两方案逐点差异 | 差值渐变带 | 成对点+连线 | 双线并排柱 |
| 趋势 + 不确定性 |  glow_line + 渐变置信带 | 误差棒折线 | 无带裸折线 |
| 分布/离散度 | violin/box + 荧光轮廓 | 蜂群/雨云图 | 只画均值柱 |
| 分类阈值权衡 | ROC/PR + AUC 渐变区 | 成本曲线 | 多表罗列 |
| 容量/权衡面（如 FD 基本图） | 容量面渐变区 + 边界 glow | 等高线 | 表格 |
| 时间/位置序列强度 | 序列色渐变（深→浅） | heatmap | 彩虹 cmap |
| 流程/架构 | 层容器卡片（gradient_box） | drawio/HTML 矢量 | 截图 raster |
| 占比 | 堆叠渐变条 / 排序条 | donut | 3D 饼 |

## 二、改法配方（原图型 → 升级图型，figstyle 落地）

| 原图型 | 改法 | 关键调用 |
|--------|------|----------|
| 柱状图（排序对比） | **棒棒糖点图**：细杆 + 荧光头 + 数值标注 | `ax.vlines(names,0,vals,color,linewidth=1.4,alpha=0.5)` + `glow_scatter` + `ax.text` 数值 |
| 分组柱状 | **得分点阵**：按系列细杆 + 荧光点 | 每系列 `vlines(alpha≈0.5)` + `glow_scatter`，系列色取 `PC[i]` |
| 水平条形 | **渐变条** | `gradient_bar(..., horizontal=True, fade=0.62)` |
| 垂直条形（确需保留） | **渐变柱全套** | `gradient_bar`（含 halo），禁 `ax.bar` 平涂 |
| 双线折线对比 | **差值渐变带** | `gradient_area(x, y1, color, baseline=y2)`（方向自动翻转） |
| 置信带 | 渐变带 + 图例手柄 | `gradient_area(WARM.TACC, baseline=fit±band)` + `Rectangle` 手柄 |
| 垂直剖面/廓线 | 水平淡出面 | `fade_area_x(x_profile, y, color)` + `glow_line` |
| 密度/分布 | violin/box 荧光轮廓 | body 复制：violin 用 `PathCollection([pc.get_paths()[0]])`，box 用 `PathPatch(p.get_path(), transform=p.get_transform())`，`lighten` 填充 + 描边 |
| ROC/PR | AUC 区域渐变 | `gradient_area` 沿曲线 |
| 框架/流程图 | **层容器**：渐变容器→描边→内嵌文字 | `gradient_box(ax,x,y,w,h,PASTEL[key])` + `ax.text(…, ink_of(fill))` |
| 多问流程冗余 | **砍量**：流程图合并同类项，结论进 caption | 一图一主张 |

## 三、图型纪律

1. **一图一主张**：单面板图禁图内标题（`panel_title` 仅用于多面板 (a)(b) 小标）。
2. **画幅**：宽高比约 2.2:1 近横幅；禁近正方形 + 图外巨图例。原生画布宽≈上页显示宽
   （缩放比 0.9–1.1，`figure_check.sh` 按长宽比分档机检）。
3. **双编码**：多系列必须"颜色 + 线型/标记"双编码（`PC` × `LS_SEQ`），灰度打印仍可读。
4. **保留柱形的唯一条件**：`gradient_bar` + glow 全套；否则一律换图型。
5. 换图型后**同步正文措辞**（"柱状图的形态"→"得分点阵的对比"）。

## 四、规划参照（包内资产）

- `assets/figure_exemplars.md`：图型规划启发式、领域签名图触发表、TikZ 放置规则、数量配比。
- `assets/figure_recipes_{basic,advanced,competition,empirical,academic}.md`：分难度配方菜单
  （菜单而非约束，允许 `(custom)`）。
