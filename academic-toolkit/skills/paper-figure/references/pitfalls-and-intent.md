# 选图论证三轴 + 十八坑拦截清单（收编自 SciPilot）

> 来源：[Haojae/scipilot-figure-skill](https://github.com/Haojae/scipilot-figure-skill)（本地 fork：FOURTEEN1416/scipilot-figure-skill）
> `references/chart_selection.md` + `references/viz_pitfalls.md`，pinned commit `43098dd`（2026-06-15），License MIT。
> 本地适应性改写（2026-09-11），见同目录 UPSTREAM.md。
> 定位：本文件回答"**画图前的判断**"——该不该画、画什么、怎么不被审稿人抓坑。
> 与现有资产分工：`figure_exemplars.md` 管"按方法/数据形态的图型套餐"；`figure_style_guide.md` 管防丑检查；
> [semantic-palette.md](semantic-palette.md) 管"什么角色用什么色"；[composition-patterns.md](composition-patterns.md) 管构图。

## 一、决策三轴（画图前必答，出自 chart_selection.md）

每次规划一张数据图，先答三个问题：

### 轴 1：变量数量与类型（数据结构）

| 组合 | 该看什么 |
|---|---|
| 1×连续 | 分布 |
| 1×分类 | 占比 |
| 1×分类 + 1×连续 | 组间比较 |
| 2×连续 | 关系 |
| 1×时间 + 1×连续 | 趋势 |
| 多个连续 | 相关 |
| 二维矩阵（n×m 数值） | 模式 |
| 嵌套分组（A 下分 B） | 层次 |

### 轴 2：论证意图（最易被忽略的一轴）

**同一批数据，论点不同 = 图不同**。先问"这张图要说服读者相信什么"：

| 意图 | 图型 |
|---|---|
| 分布（"这组数据长什么样"） | 直方图 / KDE / 箱线 |
| 比较（"A 比 B 高"） | 箱线 / 柱状带误差 / 小提琴 |
| 关系（"X 越大 Y 越大"） | 散点 + 回归 |
| 趋势（"随时间/剂量变化"） | 折线 + 误差带 |
| 构成（"总和分几份"） | 堆叠柱状（⛔ 不要饼图） |
| 相关（"哪些变量相关"） | 相关性热力图 / pairplot |
| 差异显著性（"组间差异是否显著"） | 箱线 + 显著性标注 |
| 不确定性（"估计有多准"） | 误差棒 / 置信带 |

> 竞赛语境（本仓）：FIGURE_MANIFEST 规划每张图时的"选择理由"栏，应写**轴 2 的论证意图**而不是只写图型名——"展示 P2 峰值随含水率下降的趋势（趋势→折线+置信带）"而非"折线图"。

### 轴 3：数据规模（样本量分级）

| 每组样本量 | 规则 |
|---|---|
| n ≥ 30 | 箱线/柱状（带误差）/小提琴均可 |
| 10 ≤ n < 30 | 优先箱线/小提琴；柱状必须叠加原始点 |
| 3 ≤ n < 10 | **直接散点/stripplot**；箱线慎用（四分位估计不可靠） |
| n < 3 | ⛔ 禁画箱线/小提琴——统计估计无意义，直接展示每个点 |
| 总量 > 10⁴ | 散点 alpha=0.1-0.3 防 overplotting，或 hexbin/2D KDE |

## 二、十八坑拦截清单（出自 viz_pitfalls.md，审稿人视角）

出图后**逐条自查**；发现命中任意一条，先说明问题再改，不要交稿。配套兜底：`figure_check.sh`（静态质检）+ vision 质检（`data_fig_vision_check.py --review`）。

| # | 坑 | 审稿人视角一句话 | 正确做法 |
|---|---|---|---|
| P1 | 均值柱掩盖分布与样本量 | n=3 和 n=300 画出来一样高；双峰/偏态/outlier 全被均值吃掉 | n≥10 箱线/小提琴+叠加原始点；n<10 直接散点；必须用柱则叠 stripplot+误差棒注明 SD/SEM |
| P2 | 双 Y 轴 | 两轴尺度可任意调，"重合/分歧"是作图者捏造的 | 同量纲共轴；异量纲看相关→散点；看趋势→上下双子图共享 x 或标准化 |
| P3 | 饼图 / 3D 图 | 人眼对长度的辨别比角度精确 3 倍；3D 视角扭曲所有数值 | 占比→横向排序柱状；分解→堆叠柱；3D 数据→2D 热力图+colorbar |
| P4 | Y 轴不当截断 | 经典误导："升 2%"看着像"翻倍" | 比例/准确率从 0 起步；跨数量级用 log 轴；必须截断→画断裂标记+图注说明 |
| P5 | 连续色阶无 colorbar | 读者不知道"深红"是多少；多图"深红"不一致 | 颜色映射数值必配 colorbar+label；多图比较锁定 vmin/vmax |
| P6 | 离散点连成折线 | 折线暗示连续关系，分类连线无数学意义 | 分类用柱/散点；只有 x 真连续（时间/剂量梯度）才连线 |
| P7 | 过度用色 | 颜色超过 8 种读者记不住 | ≤8 色且语义映射（见 [semantic-palette.md](semantic-palette.md)）；多余类别并入"其他"。竞赛数据图口径更严：数据系列色 ≤6（paper-figure SKILL.md / figure_style_guide.md，62 篇获奖论文统计）；TikZ 结构图 ≤3 含黑灰 |
| P8 | 图例缺失或不清 | 读者要猜每条线是什么 | 每条线/每色都有图例；标签直接标注在元素旁优于远端图例 |
| P9 | 误差类型不交代 | SD/SEM/CI 含义完全不同 | 误差棒类型在图注写明；n 也要写 |
| P10 | 过度装饰（chartjunk） | 网格线/边框/阴影稀释核心信息 | 去掉不承载信息的元素；干净版面=可信 |
| P11 | 分辨率/格式不达标 | 位图 <300dpi 印刷发糊 | 线图/散点→PDF/SVG 矢量；真位图（热力图色块/照片）≥300dpi |
| P12 | 一图多论点 | 3 秒看不出主结论 = 失败 | 一图一论点；多个论点拆子图（panel a/b/c） |
| P13 | 红绿对比不做色盲检查 | ~8% 男性红绿色盲 | 红绿避免作唯一区分；过色盲模拟（本库色盲安全约束） |
| P14 | rainbow / jet 色图 | 色带非感知均匀，人为制造边界 | 用感知均匀色图（viridis 系/单色渐变；本库密度色带规范见 [semantic-palette.md](semantic-palette.md) §5.1） |
| P15 | 显著性符号滥用 | ***/ns 满天飞显得不诚实 | 只标关键对比；报告具体 p 值与效应量；ns 就诚实写 ns |
| P16 | 缺字乱码（中文/负号变方框） | 画的时候看不出、导出/换机器才暴露 | 中文字体显式注册（本库 `_utils/NotoSansSC-Regular.ttf` addfont 方案）；`axes.unicode_minus=False` |
| P17 | 文字裁切与图例遮盖 | 导出后标签被切/图例压数据 | constrained_layout；导出前程序自检 bbox；图例压数据用独立图例面板（[composition-patterns.md](composition-patterns.md) 模式二） |
| P18 | 多面板编号不对齐 | panel (a)(b)(c) 位置/字号不一致 | 统一编号位置与字号；对齐用网格而非目测 |

> P16-P18 是"画时看不出、导出才暴露"的渲染类坑——**必须程序自检（`figure_check.sh`）+ AI 读图复核（vision 工具）双兜底**，禁止"肉眼看 PNG 没问题"就放行。

## Related

- `../SKILL.md` — 本技能入口（Output Contract / Workflow / 外部规范红线）
- [semantic-palette.md](semantic-palette.md) — 语义调色板（P7/P13/P14 的色彩侧落地）
- [composition-patterns.md](composition-patterns.md) — 构图五模式（P12/P17/P18 的布局侧落地）
- `../../_utils/figure_exemplars.md` — 按方法/数据形态的图型套餐（轴 1 的展开）
