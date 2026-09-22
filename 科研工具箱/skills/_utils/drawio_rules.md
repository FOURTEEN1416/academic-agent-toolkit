# DrawIO 绘图规范

Claude 生成 DrawIO 技术路线图/流程图/架构图时参考此文件。

## 工具链

- `draw.io.exe`（已打包在 `runtime/draw.io/`，PATH 已注入）
- 导出：`draw.io.exe --export --format pdf --crop --output figures/xxx.pdf figures/xxx.drawio`
- ⛔ 必须加 `--crop` 裁剪白边

## ⛔ 零容忍规则（CLI headless 导出踩坑总结）

1. **禁止 `shadow=1`**：CLI 导出时 shadow 导致节点不渲染
2. **禁止 XML 注释 `<!-- -->`**：浪费 token，可能导致解析错误
3. **只使用 CLI 稳定的标准形状**：矩形/圆角矩形、ellipse、rhombus、parallelogram、cylinder、hexagon、swimlane 与 `mxgraph.arrows2.arrow` 已验证可用；禁止 `shape=callout` 等不稳定或依赖在线图库的复杂形状。形状用于表达语义，不为“丰富”而堆砌
4. **换行用 HTML**：`html=1` 模式下用 `&lt;br&gt;` 换行，所有节点必须有 `html=1`。⛔ 包括 edge 上的标签文字节点（如判断分支的"是/否"标签）——如果标签的 value 里包含 `&lt;font&gt;` 等 HTML 标签但 style 里没有 `html=1`，导出后会显示原始 HTML 代码而不是渲染后的文字
5. **ID 全局唯一**，不能重复
6. **XML 转义**：`<>&"` → `&lt;&gt;&amp;&quot;`
7. **每个 edge 必须有子元素**：`<mxGeometry relative="1" as="geometry"/>` 不能自闭合
8. **中文直接写 UTF-8**
9. **页面背景透明**：`mxGraphModel` 加 `background=none`，并设 `page="0"` 去掉页面边框，避免导出 PDF 有灰色背景
10. **按复杂度选引擎**：简单分层架构、模块边界、数据流水线可用 DrawIO；需要大量跨层精确连线、LaTeX 推导、坐标/角度或复杂网络布局时改用 TikZ。不要仅凭文件名决定引擎
11. **图内不写标题**：标题由 LaTeX `\caption{}` 统一管理，DrawIO 图内不要放标题文字节点（避免标题重复、字体不一致）
12. **先留连线通道再放节点**：主流向优先直行；跨区边放在专门的顶部、底部或侧边通道，用 waypoints 绕开节点。若两个区块只需要表达“对应关系”，可用同行/同列对齐、共享容器或编号映射，避免无信息增量的长线
13. **版式由信息拓扑决定**：三栏只是“阶段—内容—方法”恰好同时存在时的一个候选，不是技术路线图默认。分支子问题、共享模型内核、双循环、角色交接、层级分解应分别使用分支汇合、控制回路、泳道或分层版式

## DrawIO vs TikZ vs GPT Image 完整分工表

所有 20 种非数据图的推荐工具一览。规划阶段直接查此表。

| # | 图类型 | DrawIO | TikZ | GPT Image | 选择理由 |
|---|--------|--------|------|-----------|---------|
| 1 | 技术路线图 | ✅ 首选 | | | 分阶段分组框+粗箭头，连线简单 |
| 2 | 论文结构图 | ✅ 首选 | | | 章节层次+箭头，类似技术路线图 |
| 3 | 子问题求解流程图 | ✅ 首选 | | | 纵向步骤+判断分支，连线只走上下 |
| 4 | 算法流程图（带公式） | | ✅ 首选 | | 需要 LaTeX 公式渲染（如 $\Delta f < \epsilon$） |
| 5 | 算法流程图（无公式） | ✅ 可用 | ✅ 可用 | | 无公式时 DrawIO 更快；有判断分支多时 TikZ 更精确 |
| 6 | 数据处理 Pipeline | ✅ 首选 | | | 横向多阶段卡片，连线简单 |
| 7 | 模型架构图（神经网络/集成学习） | | ✅ 首选 | | 需要跨层精确连线，DrawIO CLI 连线会穿过节点 |
| 8 | 概念框架图（简单分层） | ✅ 首选 | | | 嵌套色块+层间大箭头，无跨层连线 |
| 9 | 概念框架图（复杂连线） | | ✅ 首选 | | 有跨层箭头+标注系数，需要精确路由 |
| 10 | 变量关系/因果路径图 | | ✅ 首选 | | 需要精确控制箭头路径+标注系数/显著性 |
| 11 | 指标体系层次图 | ✅ 首选 | | | 目标层→准则层→指标层的树形结构，连线只走纵向 |
| 12 | 模型选择决策树 | ✅ 首选 | | | 树形分支结构，连线简单 |
| 13 | 场景示意图（物理/工程） | | | ✅ 首选 | 需要写实渲染（无人机/传感器/交通等），代码画不出来 |
| 14 | 几何示意图 | | ✅ 首选 | | 需要精确坐标、虚线、角度标注、数学变量 |
| 15 | 网络拓扑图（≤15节点） | ✅ 可用 | ✅ 可用 | | 节点少时 DrawIO 够用；需要精确布局时用 TikZ |
| 16 | 网络拓扑图（>15节点） | | ✅ 首选 | | 节点多时需要算法布局（spring/kamada_kawai），或用 matplotlib networkx |
| 17 | 网络路径图（标注最优路线） | | ✅ 首选 | | 需要在图上精确标注路径+权重，DrawIO 手动排太麻烦 |
| 18 | 甘特图/调度方案图 | ✅ 可用 | | | 调度类赛题的结果展示；竞赛工作安排不需要画图。简单甘特图用 DrawIO，复杂调度用 matplotlib |
| 19 | 灵敏度分析示意图（定性） | ✅ 可用 | ✅ 可用 | | 简单箭头标注用 DrawIO；带公式用 TikZ |
| 20 | 方法对比矩阵图 | ✅ 首选 | | | 表格/矩阵形式，DrawIO 画格子方便 |

**速查规则：**
- 需要 LaTeX 公式 → TikZ
- 需要跨区精确连线（箭头不能穿过节点） → TikZ
- 需要写实场景渲染 → GPT Image
- 其余（分层/分组/树形/流程/卡片） → DrawIO

## ⛔ 通用设计规范（所有 DrawIO 图必须遵守）

以下规范适用于所有类型的 DrawIO 图（技术路线图/流程图/框架图/指标体系图等）。

### 容器与层次

- 只有“责任主体/数据域/时间阶段”本身重要时才使用 swimlane；普通分组可用无标题浅底框、虚线边界或留白，不要每个节点都套泳道
- 同一层级保持相同视觉语法，主次通过边框、留白、字号和位置区分，不依赖每阶段换一种颜色
- 容器标题使用短语，不机械加“第 N 阶段”；子节点可用 `parent="容器id"` + 相对坐标，容器内留白至少 16px

### 节点设计

- 节点只保留识别该步骤所需的信息：短标题足够时用单行；需要补充输入/输出或方法含义时才加第二行。不要为了“双行率”制造灰色废话
- 关键/核心节点通过位置、较大面积或 1.8-2.2px 边框突出；论文图默认不使用 ★、✓ 等界面化图标
- 汇总/输出节点使用与全图协调的轻微强调，不把绿色固定等同“通过”、红色固定等同“稳健”
  - ⛔ **输出节点只写“做什么/得到什么量”，禁止写具体求解结果数值或宣告式结论**。技术路线图/流程图是画**方法与步骤**的框架，不是结果展示区；“结论成立、验证通过、显著优于、效果最佳”等判断也必须放在正文或结果图表中。
    - ✅ 正确：`求解得到临界时刻 t*`、`输出最优螺距 p_min`、`时间二分求根（精度 1e-6 s）`（算法参数属方法，可留）
    - ❌ 错误：`输出：t*=412.473838 s`、`p_min=45.033745 cm`、`误差=7.01e-8`（完整精度结果值不许进节点——既喧宾夺主，又常与正文精度对不上、连带触发数字溯源审计）
- **负面/异常节点**：用红色边框（`strokeColor=#b85450`）标注，如"虹吸效应""普通面板回归"
- **普通节点**：白底 + 阶段主色边框（`fillColor=#FFFFFF;strokeColor=阶段色`）

### 连线规范

- **用 source/target 属性连线**：`edge="1" source="n1" target="n2"`；需要绕行时在 geometry 中添加 waypoints，不依赖自动路由猜测
- **同容器内连线**：`parent="容器id"`，连线颜色与容器主色一致
- **跨容器过渡箭头**：`parent="1"`，主路径通常 1.8-2.2px；只有阶段断点或汇合主干才可更粗
- **决策分支**：只有真实条件才用菱形；边标签写条件结果或数学含义，不强制绿色“是”/红色“否”

### ⛔ 连线路由规则（7 条，防止连线穿过节点）

1. **禁止多条边共享同一路径**：如果两条边连接同一对节点，必须从不同位置出入。用 `exitY=0.3` 和 `exitY=0.7` 区分，不要都走 0.5
2. **双向连接用对侧**：A→B 从 A 的右侧出（`exitX=1`），进 B 的左侧（`entryX=0`）；B→A 反过来
3. **必须显式指定 exitX/exitY/entryX/entryY**：每条边的 style 里都要写这 4 个属性，不要让 DrawIO 自动猜
4. **连线必须绕开中间节点**：画边之前先看源和目标之间有没有其他节点挡着，有的话用 waypoints 绕行，留 20-30px 间距
5. **先规划布局再画线**：把节点按流向分层/分列排好，留出连线通道（150-200px 间距），再画边
6. **复杂路由用多个 waypoints**：一个拐点不够就用 2-3 个，形成 L 形或 U 形路径，每个方向变化都需要一个 waypoint
7. **连接点选自然方向**：上下流向从底部出（`exitY=1`）顶部进（`entryY=0`）；左右流向从右侧出（`exitX=1`）左侧进（`entryX=0`）。不要用角落连接点（如 `exitX=1,exitY=1`）

**画完后自检**：有没有边穿过非源/目标的节点？有没有两条边重叠？有没有用了角落连接点？

### 整体布局

- **画布按拓扑自适应**：正文单栏图通常宽 760-1200px；优先得到 4:3～16:9 的横向或近方形构图，避免被 `height` 上限压成小图
- **区块间距 24-48px**，跨区连线另留 24px 以上通道；密集图先换方向、换版式或拆图
- **节点尺寸按最终文字边界计算**：中文/英文宽度只是粗估，导出后必须按论文插入尺寸复核；单行通常 30-38px，双行 44-60px
- **同行节点等距分布**：计算容器宽度，均匀分配
- **⛔ 节点必须居中分布**：如果一行只有 3 个节点但容器宽度能放 4 个，节点要居中排列，不要左对齐留大片空白。计算方法：`左边距 = (容器宽度 - 节点总宽度 - 节点间距总和) / 2`。最后一行（结论/输出）尤其容易出现左对齐问题，必须检查

### 配色族——同族内一致，跨项目可稳定变化

颜色只承担分组、路径或状态中的一种任务；全图通常使用中性底色 + 1 个主色 + 最多 2 个强调色。必须能在灰度打印中靠形状、边型或标签继续辨认。

| 配色族 | 主色 / 强调色 | 中性底色 | 适合气质 |
|---|---|---|---|
| ink-slate | `#40566F` / `#7A93AC` | `#F3F5F7` | 克制、工程、通用 |
| teal-sand | `#3F7C78` / `#C39A63` | `#F4F1EA` | 系统、资源、环境 |
| indigo-amber | `#59638F` / `#D29A45` | `#F5F3EE` | 优化、决策、调度 |
| sage-terracotta | `#708A72` / `#B97862` | `#F4F2ED` | 生态、社会、空间 |
| plum-bluegray | `#745F78` / `#6F8799` | `#F5F3F5` | 统计、评价、框架 |
| mono-print | `#3F454B` / `#7B838B` | `#F7F7F5` | 黑白打印、正式论文 |

- 由工作区路径 + 图文件名产生的稳定种子，只在语义同样合适的配色族/方向候选中选择；不要用不受控随机数。
- 同一项目中相邻图的 `layout_family + orientation + palette_family` 不得完全重复，决定写入 `figures/diagram_design_ledger.json`。
- 普通节点用白底或极浅底 + 1.0-1.4px 边框；核心节点 1.8-2.2px；主路径 1.8-2.2px，次路径/反馈 1.2-1.6px。

⛔ 节点数量控制：每个阶段/容器内最多 2 行节点，每行最多 4 个。总节点数不超过 30 个。宁可精简也不要塞太多——杂乱比简洁更差。

### swimlane 容器样式模板

```xml
<mxCell id="S1" value="&lt;b&gt;第一阶段：阶段名称&lt;/b&gt;"
  style="swimlane;startSize=22;fillColor=#EBF3FB;strokeColor=#B8D4F0;strokeWidth=1.5;rounded=1;html=1;fontSize=11;fontStyle=1;swimlaneLine=0;arcSize=4;"
  vertex="1" parent="1">
  <mxGeometry x="30" y="10" width="920" height="80" as="geometry"/>
</mxCell>
```

### 节点样式模板

```xml
<!-- 普通节点（白底+阶段色边框+双行文字） -->
<mxCell id="n1" value="&lt;b&gt;主标题&lt;/b&gt;&lt;br&gt;&lt;font style=&quot;font-size:8px;color:#666;&quot;&gt;灰色副标题说明&lt;/font&gt;"
  style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#6c8ebf;strokeWidth=1.5;fontSize=9;fontStyle=1;"
  vertex="1" parent="S1">
  <mxGeometry x="15" y="28" width="175" height="42" as="geometry"/>
</mxCell>

<!-- 核心节点（加粗边框+浅色填充+★标记） -->
<mxCell id="n_core" value="&lt;b&gt;★ 核心模型名称&lt;/b&gt;&lt;br&gt;&lt;font style=&quot;font-size:8px;color:#666;&quot;&gt;关键参数说明&lt;/font&gt;"
  style="rounded=1;whiteSpace=wrap;html=1;fillColor=#e1d5e7;strokeColor=#9673a6;strokeWidth=2.5;fontSize=9;fontStyle=1;"
  vertex="1" parent="S4">
  <mxGeometry x="225" y="28" width="200" height="48" as="geometry"/>
</mxCell>

<!-- 汇总节点：只写待输出的量名，不写最终数值或结论 -->
<mxCell id="n_out" value="&lt;b&gt;输出临界时刻与最小螺距&lt;/b&gt;"
  style="rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#40566F;strokeWidth=1.8;fontSize=10;fontStyle=1;"
  vertex="1" parent="S3">
  <mxGeometry x="660" y="28" width="155" height="48" as="geometry"/>
</mxCell>
```

### 连线样式模板

```xml
<!-- 同容器内连线（用 source/target） -->
<mxCell id="e1" edge="1" source="n1" target="n2" parent="S1"
  style="rounded=1;html=1;strokeWidth=1.5;strokeColor=#6c8ebf;endArrow=classic;endFill=1;">
  <mxGeometry relative="1" as="geometry"/>
</mxCell>

<!-- 跨容器过渡箭头（粗灰色） -->
<mxCell id="arr12" edge="1" parent="1"
  style="rounded=1;html=1;strokeWidth=4;strokeColor=#C0C0C0;endArrow=block;endFill=1;endSize=8;">
  <mxGeometry relative="1" as="geometry">
    <mxPoint x="490" y="88" as="sourcePoint"/>
    <mxPoint x="490" y="105" as="targetPoint"/>
  </mxGeometry>
</mxCell>
```

## 语义版式族（先选拓扑，不选模板）

先从规划文档提取真实依赖，再选择能够最短、最准确表达它的版式。一个项目的技术路线图、求解流程图和架构图应使用不同的版式族，除非它们的拓扑确实相同。

| 版式族 | 识别信号 | 推荐结构 | 不适用情形 |
|---|---|---|---|
| stage-band | 3–6 个严格前后阶段，无明显分支 | 横向阶段带或折返带 | 多子问题共享公共模型 |
| branch-merge | 公共输入/模型后分成多个子问题，最后汇总 | 公共内核 → 并行分支 → 结果汇合 | 单一路径 |
| dual-loop | 外层参数搜索 + 内层求解/校准，或预测—校正 | 主流程 + 一条清晰反馈轨 | 没有真实迭代 |
| swimlane | 不同角色、数据域、算法模块之间发生交接 | 横/纵泳道 + 跨泳道消息 | 只有单一主体 |
| layered-stack | 输入、模型、求解、输出存在稳定层级 | 分层架构，层间主箭头 | 强时间顺序或大量回路 |
| hub-spoke | 一个共享核心连接多个相对独立模块 | 中心内核 + 周边模块，按方向分组 | 模块间强串行依赖 |
| tree-radial | 层级分解、指标体系或分类决策 | 树形、鱼骨或径向层级 | 时间流程 |
| matrix-flow | 问题 × 方法、阶段 × 证据等二维映射 | 矩阵主体 + 一条主流程 | 只有单维关系 |
| horizontal-pipeline | 数据依次经过多个变换，接口清楚 | 左→右 pipeline，输入输出形状明确 | 多回路控制系统 |

### 稳定差异化，不用随机套壳

1. `layout_family` 由真实拓扑唯一决定或缩小到 2 个等价候选。
2. 等价候选的 `orientation / palette_family / corner_style / container_style` 用“工作区绝对路径 + 图文件名”的 SHA-256 短哈希稳定选择；重试不会换脸，不同工作区通常得到不同组合。
3. 写入 `figures/diagram_design_ledger.json`，至少包含：
   `file, layout_family, orientation, palette_family, semantic_shapes, seed, rationale`。
4. 生成下一张图前读取 ledger；若组合已用，优先换 orientation 或 palette，而不是扭曲信息拓扑。
5. `_utils/example_roadmap_hex.drawio` 与 `_utils/example_flow.drawio` 只供学习已验证的 mxCell/XML/waypoint 语法。其余旧示例不再作为生成参考；禁止复制示例的固定坐标、节点数量、阶段名称与配色序列。

### 形状语法

- rounded rectangle：普通处理/模型模块；rectangle：边界、汇总或正式输出。
- parallelogram：输入/输出；cylinder：真实数据存储；rhombus：真实布尔或多分支判断。
- ellipse：开始/结束或汇聚点；hexagon：准备/配置步骤，仅在含义匹配时使用。
- 同一张图中每种形状只表达一种含义；常规论文图控制在 3 种节点形状以内。
- 一条纯线性流程是合法的。若没有真实判断、并行或迭代，不得添加菱形、fork 或回环装饰。


## 实践检查清单


生成每张 .drawio 后必须逐条自检：

- [ ] **字号检查**：最小字号 ≥ 10px，普通节点 ≥ 11px，标题 ≥ 12px
- [ ] **重叠检查**：相邻节点边界框不交叉，间距 ≥ 8px
- [ ] **对齐检查**：同行节点 y 坐标一致，同列节点 x 坐标一致
- [ ] **版式忠实性**：图的版式族与 DESIGN BRIEF 一致；只有选择三栏/泳道时才检查列对齐，分支、树形、控制回路不套三栏规则
- [ ] **连线遮挡检查**：无连线穿过节点或文字
- [ ] **文字溢出检查**：节点完全包含文字，中文节点 width ≥ 字数×14+30px，英文节点 width ≥ 字符数×8+30px。⛔ 如果节点内有换行（`<br>`），height 需要额外加 16px/行
- [ ] **样式一致性**：同类节点 fillColor/strokeColor/fontSize 统一
- [ ] **容器检查**：子节点 parent 指向正确的容器 id，坐标是相对坐标
- [ ] **edge 检查**：每个 edge 有 `<mxGeometry relative="1" as="geometry"/>`
- [ ] **无 shadow**：确认没有 `shadow=1`
- [ ] **无 XML 注释**：确认没有 `<!-- -->`
- [ ] **html=1 检查**：所有 mxCell（包括 edge 标签节点）的 style 里都有 `html=1`。如果 value 包含 `&lt;font&gt;`/`&lt;b&gt;`/`&lt;br&gt;` 但没有 `html=1`，导出后会显示原始 HTML 代码
- [ ] **紧凑度**：信息组之间留出稳定节奏和连线通道；不得靠压小字号塞入，也不得出现大片无语义空白
- [ ] **填充度**：子分组框/节点必须填满层宽度，不留大片空白。两个分组框之间间距 15px
- [ ] **居中检查**：每行节点数少于容器能容纳的最大数量时，节点必须居中分布，不要左对齐。特别检查最后一行（结论/输出阶段）
- [ ] **尺寸控制**：DrawIO 图不需要限制高度，LaTeX 插入时用 `keepaspectratio` + `height` 双约束自动处理。专注于内容完整、节点不遮挡即可

## 技术路线图 vs 求解流程图（⛔ 必须区分）

| | 技术路线图 | 求解流程图 |
|---|---|---|
| 视角 | 全局——整篇论文从问题到结论 | 局部——单个子问题从输入到输出 |
| 内容 | 多个阶段，每阶段多个节点，展示整体求解思路 | 一个问题的具体步骤、判断分支、数据流向 |
| 放置 | 问题重述章节末尾 | 各子问题章节开头 |
| 数量 | 通常整篇论文 1 张 | 只按 FIGURE_MANIFEST 生成；未规划的子问题流程图不补画 |

**布局不限制**——Claude 可以根据具体赛题内容自由发挥布局和视觉设计（纵向/横向/混合/分区/嵌套都可以），只要遵守：
1. 零容忍规则（无 shadow、无 XML 注释、无特殊形状等）
2. 通用设计规范（语义形状、source/target 连线、最终字号和低饱和配色）
3. 连线路由规则（不穿过节点、显式指定 exitX/exitY）
4. 图内不写标题（由 LaTeX caption 管理）

⛔ 唯一的硬限制：技术路线图和求解流程图不能长得一样——技术路线图要体现"全局多阶段"的视觉层次，求解流程图要体现"单问题步骤链"的逻辑流向。

### 求解流程图语义要求

求解流程图的复杂度必须来自真实算法，不来自装饰：

1. 真实存在阈值判断、可行性判定或停止条件时才使用菱形，并给每条出边写明确条件。
2. 真实存在并行计算、模型对比或独立分支时才分叉；否则保持一条清晰主线。
3. 真实存在迭代、参数回代或误差校正时才画回路，并让回路沿边界通道绕行。
4. 输入、处理、判断、存储和输出用形状/标签区分即可，不强制五种颜色。
5. 单行节点能说清时不加副标题；第二行只补充必要输入、输出或数学含义。

**⛔ 求解流程图绝对不要画右侧工具/方法注释栏**（"工具与方法"那种独立侧栏是技术路线图专属）。求解流程图应该简洁，只展示求解步骤和逻辑分支，**禁止**在右侧放 pandas/matplotlib/SciPy/numpy 等工具标签。

**⛔ 也不要把工具/库名（如 SciPy minimize、Python DEAP、scikit-learn 等）写进节点副标题。** 副标题只描述**步骤本身做什么**（输入/输出/方法的物理或数学含义），不写技术实现。例子：
- ❌ 错：「优化圆弧半径比 / SciPy minimize」
- ❌ 错：「需求热力分析 / scikit-learn KDE」
- ✅ 对：「优化圆弧半径比 / 最短路径目标函数」
- ✅ 对：「需求热力分析 / 核密度估计识别热点」

`_utils/example_flow.drawio` 仅演示“确有分叉、判断和循环”时的 XML 与 waypoint 写法，不是每张流程图的最低结构。

## 技术路线图生成流程

### Step 1: 读取规划文档确定内容

```bash
cat PROBLEM_ANALYSIS.md 2>/dev/null || cat TOPIC_PLAN.md 2>/dev/null || cat PAPER_PLAN.md 2>/dev/null
```

### Step 2: 确定阶段结构

从规划文档生成节点和边的简表，并判断属于 stage-band、branch-merge、dual-loop、swimlane、layered-stack、hub-spoke、tree-radial、matrix-flow 或 horizontal-pipeline。阶段名称必须来自当前题目，不使用“提出问题—分析问题—解决问题—研究成果”作为默认占位。

### Step 3: 生成 .drawio XML

按选定版式族生成；需要容器时使用相对坐标，不需要分组时保持扁平、清晰的顶层节点。

### Step 4: 导出 PDF

```bash
draw.io.exe --export --format pdf --crop --output figures/fig_roadmap.pdf figures/fig_roadmap.drawio
```

### Step 5: 验证 PDF 非空

```bash
ls -la figures/fig_roadmap.pdf
```

如果导出失败，检查：shadow=1？XML 注释？特殊形状？ID 重复？标签未闭合？

## 官方资料依据

- Draw.io 布局：<https://www.drawio.com/docs/manual/layouts/>（flow/tree/radial/organic 等布局应按图类型选择）
- Arrange Layout：<https://www.drawio.com/docs/manual/editor/menus/arrange-layout-menu/>（同一图连续套布局不会稳定复现，因此本项目使用稳定设计签名）
- Connector waypoints：<https://www.drawio.com/docs/manual/connectors/waypoints-connectors/>（复杂连线应使用 waypoints，而不是只依赖 line jump）
- Swimlane diagrams：<https://www.drawio.com/docs/diagram-types/swimlane-diagrams/>（泳道用于跨角色/职责流程，不是通用装饰容器）
- Template diagrams：<https://www.drawio.com/docs/manual/templates/>（模板是可搜索的起点；本项目只复用语法与组件，不复制固定信息拓扑）
- Custom template libraries：<https://www.drawio.com/docs/manual/templates/custom-template-libraries/>（若以后做可视化模板库，应保存可组合的片段和样式，而非整张论文图套壳）
