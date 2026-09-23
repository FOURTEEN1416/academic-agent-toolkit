---
name: figure-aesthetics-craft
description: "图形质感技法集（来自科研绘图文章精编，2026-09-11 批次）：渐变色的合法语义与滥用边界、树图/网络图边色继承（免图例层级图）、AI 绘图代理的五条纪律与逐图提示模板、19 类顶刊构图参照片。触发词：更有质感、渐变色、边色继承、免图例、绘图纪律、审美、网络图边怎么配色、环形树图、桑基/维恩/背景条带。"
---

# Figure Aesthetics Craft（图形质感技法）

从外部审美输入（公众号科研绘图专题，2026-09-11 批次六篇）中提炼的**四组可执行技法**。定位：
paper-figure 管"画什么与配色语义"（选图三轴/semantic-palette），本技能管"怎么画得更有质感"——
二者互补不重叠；出图后质检走 `fig-critique`。

## 一、渐变色使用规范（来源：R 语言数据分析指南）

渐变只允许出现在两种位置，其余场景一律离散色：

1. **承载数值/强度语义**：桑基图流量强度、维恩图重叠度、热图色带——渐变方向必须与数值方向一致；
2. **非语义装饰层**：面板内渐变背景、轴标签区渐变条带（层次引导）——装饰不得抢数据焦点。

分类要素（组别/类别）**禁用渐变**，用离散色觉友好色（对接 paper-figure semantic-palette）。

技术要点（ggplot2）：
- 渐变落在图形外部（轴背景条带）必须 `coord_cartesian(clip = "off")` 关闭坐标裁剪，否则渐变被裁掉；
- 分组文本条带用 `legendry` 包实现；
- 参考图例见本技能图集（§五）03 号批次：渐变箱线/渐变条带/渐变维恩/渐变桑基四类。

## 二、层级网络/树图：边色继承 + 免图例（来源：SCIPainter）

圆形树状网络图（KEGG 富集等层级数据）的核心技法：

1. **边色继承末端节点**：边列表加 `edge_class` 列记录末端节点类别，`geom_edge_diagonal(aes(color = edge_class))`
   + `scale_edge_color_manual(values = <与节点完全同一套配色>)`——图自带图例，可删掉独立图例面板；
2. **边弱化**：`edge_width ≈ 0.6`、`alpha ≈ 0.5`、`lineend = "round"`，视觉焦点让给叶子节点；
3. **径向标签防裁剪三件套**：`theme_void()` + `coord_fixed(clip = "off")` + 大 `plot.margin`（如 55mm）；
4. **叶子标签角度公式**：`angle = -((-node_angle(x, y) + 90) %% 180) + 90`，位置按 1.06 倍半径外推、
   `hjust = "outward"`；节点大小可映射富集因子（`scale_size_continuous`）。
5. **配色警告**：原文手拍色卡（#80d52b 荧光绿/#fa0aa1 荧光洋红）**不过**色盲与印刷检查——换成本仓
   semantic-palette 色板后再用。完整可运行 R 代码见 `references/` 指引的来源批次存档。

## 三、Agent 绘图五纪律（来源：Codex + scientific-visualization 实践）

把绘图任务交给 AI agent 时的硬约束（逐图提示词模板见 `references/agent-figure-prompts.md`）：

1. **代码+数据一起给**，禁止让 agent 看图猜数值；
2. **合成/演示数据必须在图注显式申报**（"固定随机种子的合成演示"）；
3. **三件套导出**：PNG + 可编辑 SVG + 运行记录（随机种子/参数/原代码路径/修改记录）；
4. **导出后缩到目标阅读宽度复查**：字号、遮挡、背景、尺寸；
5. **不加不存在的统计结论**；颜色不承担全部区分任务（线型/形状冗余编码）。

依赖降级经验：外部 LaTeX/特殊字体缺失时改用 Matplotlib 自带数学文字（`mathtext`），保住可运行与矢量输出。

## 四、顶刊构图参照集（19 类）

Origin Learning Center 官方模板覆盖 19 类图型（3D 柱状/3D 曲面/面积/箱线小提琴/分类专用/柱状条形/
等高线云图/金融/函数/线+符号/地理地图/多面板/多坐标轴/饼环/极坐标/专业特种/统计/瀑布等），
批次图集已本地化——**吸收构图、不吸收其默认配色**（未经色觉/印刷校验）。

## 五、图集与来源

- 批次图集（103 张本地化图片 + 六篇全文）：`D:\Desktop\学术工作流\assets-local\reference-figures\公众号审美批次2026-09-11\`
  （**不在 git 内**；2026-09-12 收编入仓 gitignored 区；缺失时本技能正文技法仍完整可用，图集仅作视觉参照）；
- 逐篇要点与来源映射：该目录 `00_总览与美学要点提炼.md` 与各篇 `article.md`；
- 顶刊配色系列（LPH 等）可按期续收进同一目录；
- **顶刊海报 12 组 96 色提取+锁色相调色**（2026-09-12 收编）：数据快照 `references/top-journal-palette-96.json`
  与方法论 `references/palette-extraction-method.md`（已入 git）；原海报图与 HTML 对比查看器在
  `参考图/科研配色方案/`（仅本地）。调色值作候选输入，用前仍须过 paper-figure 色觉/打印校验。

## 六、STEP_MANIFEST 提示

被编排为引擎步骤时，按仓规 `engine.step_manifest.write_manifest` 登记 backend/inputFiles/
outputFiles（SHA-256）/commands；图件另受 figure_provenance 门禁约束。
