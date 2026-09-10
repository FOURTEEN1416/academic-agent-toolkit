# TikZ 学术图样式族参考

本文件提供“视觉语法”，不是可直接套用的固定模板。先依据 `tikz_rules.md` 写图契约，再选择一个主样式族；只有信息关系确实需要时才叠加第二个样式族。颜色、方向、节点数量和尺寸均由当前论文决定。

`G1/F1/A1` 等代码只用于 `FIGURE_MANIFEST` 和生成过程，不写进论文图面或图注。

## 选择矩阵

| 样式族 | 主要回答的问题 | 视觉语法 | 图内注释预算 | 常用 TikZ 机制 | 常见误用 |
|---|---|---|---|---|---|
| G1 几何构造 | 点、线、角、曲线如何构成模型 | 坐标场景、辅助线、角标、局部强调 | 对象符号 + 1–2 个短公式 | `calc`, `angles`, `quotes`, `intersections` | 旁边拼一列推导卡片 |
| G2 机理关系 | 量如何通过物理/数学关系作用 | 单一对象场景、向量、力/流/通量、边界 | 短对象名、方向、关键守恒式 | `arrows.meta`, `decorations.pathmorphing` | 把机理图画成通用流程图 |
| F1 流程判断 | 执行顺序、分支和循环是什么 | 单向主链、判断节点、外围回路 | 动作短语、成对条件标签 | `positioning`, `matrix` | 菱形无出口条件、反馈穿主链 |
| A1 系统架构 | 系统边界、组件、接口和数据流是什么 | 边界容器、分层组件、端口、外部实体 | 组件名、接口名、流向 | `fit`, `backgrounds`, `positioning` | 每个模块同形同色、边界与数据流混淆 |
| C1 因果影响 | 哪些变量影响哪些结果、方向如何 | 有向无环层次、正负/强弱冗余编码 | 变量名、方向/系数 | XeLaTeX: `positioning`/`matrix`; LuaLaTeX: `graphdrawing` | 用位置暗示不存在的因果 |
| N1 网络拓扑 | 多对象之间的连接、路径或群组是什么 | 节点—边网络、社群边界、主路径强调 | 节点简称、少量边标签 | `graphs`, `fit`; LuaLaTeX 可加 `graphdrawing` | 手摆稠密节点、线交叉失控 |
| T1 时间/状态 | 状态如何随时间或事件迁移 | 时间轴或状态机、事件锚点、回退边 | 时间/事件、状态名 | `chains`, `positioning`, `arrows.meta` | 把时间轴画成等价流程框 |
| M1 矩阵/泳道 | 两个维度如何交叉、职责如何分配 | 对齐行列、泳道、共享汇聚点 | 行列标题、格内短语 | `matrix`, `fit` | 用散乱绝对坐标模拟表格 |
| U1 可行域/不确定性 | 边界、区间、集合与敏感区在哪里 | 坐标轴、区域、包络、带状范围 | 约束式、区域符号、阈值 | TikZ `patterns`/`intersections`；PGFPlots 可选 `fillbetween` | 用颜色代替边界/图案 |
| P1 对比图组 | 两个方案、尺度或阶段差异在哪里 | 共享坐标/图例的 (a)(b) 面板 | 每面板少量差异标注 | `subcaption` + 独立 TikZ 图 | 因内容放不下而随意左右拼图 |

## 组合规则

- 默认一个主样式族；组合时最多再加一个辅助族，例如 `G1 + U1` 表示“几何构造 + 可行区域”。
- `P1` 不是兜底排版。只有比较、尺度切换或互补观察确有必要时才能使用多面板。
- `F1/A1/C1/N1` 的边含义不同：流程边表示执行，架构边表示接口/数据，因果边表示影响，网络边表示连接；不得只换标题而复用同一图。
- 几何或机理图默认是单一连续场景。短说明和公式贴近对应对象，完整推导放正文或图注。
- 当前编译器为 XeLaTeX 时，不直接使用依赖 LuaTeX 的自动 graph drawing；先用相对布局/矩阵，稠密到无法人工可靠排布时再拆图或显式切换工具链。

## 共享样式接口

源码可定义项目级语义接口，但不复制固定色值：

```latex
% 色值由当前论文决定
\definecolor{paperInk}{HTML}{...}
\definecolor{paperGuide}{HTML}{...}
\definecolor{paperAccent}{HTML}{...}
\definecolor{paperPanel}{HTML}{...}

object/.style={draw=paperInk, fill=paperPanel, text=black, ...},
relation/.style={-{Stealth}, draw=paperInk, ...},
guide/.style={draw=paperGuide, dashed, ...},
emphasis/.style={draw=paperAccent, line width=..., ...}
```

接口名称表达语义，不表达颜色。禁止 `blueBox`、`redArrow` 一类把样式绑定到色相的名称。

## 注释与结果策略

图契约应明确：

```text
style_family: G1 / F1 / A1 / ...
annotation_policy: minimal / explanatory / comparative
result_policy: none / symbolic / data-encoded
final_width: column / text / full-page
print_mode: color / grayscale / both
```

- `minimal`：对象符号、方向和 1–2 个短公式；适合几何与机理示意。
- `explanatory`：允许每个结构节点一个短动作或对象名；适合流程与架构。
- `comparative`：只标差异，不重复两边共有内容；适合对比图组。
- `none`：不放求解结果；`symbolic`：只放关系式；`data-encoded`：数值本身由坐标、长度、颜色或区域编码。机理示意默认 `none` 或 `symbolic`。

## 最终验收

所有样式族共用同一验收底线：最终论文尺寸可读、灰度仍可理解、边不穿节点、标签不遮挡、图中含义与正文一致。静态门禁只能发现高置信度错误；旋转、作用域、复杂路径和视觉平衡必须以编译 PDF 的逐页渲染为准。
