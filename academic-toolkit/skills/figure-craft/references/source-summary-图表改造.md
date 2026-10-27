# 图表改造 Skill 总结（本轮返工沉淀，2026-09-23）

> 真源脚本：`work/figstyle_v2.py`（v2.2）。本文件是可复用的改造方法论总结，
> 适用边界：**版面级**图重绘（数值只来自原图数字化/表转录，不重算）。

## 一、色板裁决

| 规则 | 落地 |
|------|------|
| 蓝色系禁深色（藏蓝 AI 感） | `COOL.DEEP` 重锚 **#00B4AD**（亮青绿），旧 #19667F 废止并移入 legacy |
| 向第五色系（亮青绿族）靠拢 | `COOL_SEQ = [#00B4AD, #2CC8BC, M1, MMAIN, M4]` 全程无藏蓝 |
| #00B4AD 太亮不能当小字 | 文字/图例墨色单设 `AQUA_INK = #0F7E78`（白底对比度≈6.5）；DEEP 只作线/填充 |
| 禁大面积纯色平涂 | 一切填充必须走"质感三件套"（见二）；渐变色直接从 `palette_v6.json` 真源取（T4=底色渐变、T2=卡片渐变底、TACC=荧光描边角色正为此设） |
| 暖色系 | `WARM: T4 #FEE6A9 / T3 #FED3A1 / T2 #FEBDAA / TMAIN #FEB8B5 / TACC #FDA574`，与仓库 v6 色板同族 |

## 二、质感三件套铁律（对参考论文逐像素取色后确立）

每个图形元素 = **浅渐变填充 + 同族加深描边 + 外扩荧光层**，缺一即"纯色平涂"被打回：

```python
gradient_bar(ax, x0, y0, w, h, color, *, horizontal=False, fade=0.78, lw=..., glow=0.30, zorder=...)
# imshow 竖向/横向渐变(color→lighten(color,fade))，clip 到 Rectangle 边框，
# 另叠一条 linewidth+2.6、alpha=glow 的 halo 矩形做荧光

gradient_area(ax, x, y, color, *, baseline=0.0, max_alpha=0.5, zorder=1)
# PathPatch 闭合多边形 + imshow alpha 渐隐；baseline 可为标量或数组（差值带），方向按均值自动翻转

fade_area_x(ax, x_curve, y, color, *, max_alpha=0.38, zorder=1)   # 垂直剖面：沿 x 水平淡出
glow_scatter(ax, x, y, color, *, s=42, alpha=0.26, scale=2.8)     # 大半径半透明垫一层再画真实点
glow_line(ax, x, y, color, *, lw=1.8, alpha=0.22)                 # lw+2.8 底衬线
```

参考构造基准：`图表参考论文.pdf` p05 的"层容器"架构（底层渐变容器 → 描边 → 内嵌文字），流程图/框架图按此重绘而非截图 raster。

## 三、图型多样化手册（"柱形图折线图太多"的解法）

| 原图型 | 改法 | 本轮实例 |
|--------|------|----------|
| 柱状图（排序对比） | **棒棒糖点图**：vlines 细杆 + glow_scatter 头 + 数值标注 | p1 fig13 |
| 分组柱状 | **得分点阵**：按系列 vlines(alpha 0.5) + glow_scatter | p2 fig15 |
| 水平条形 | `gradient_bar(horizontal=True, fade=0.62)` | p2 fig11/fig17 |
| 双线折线对比 | **差值渐变带**：gradient_area(baseline=另一条线) | p1 fig12、fig14 |
| 置信带 | gradient_area(TACC, baseline=fit-band) + 图例 Rectangle 手柄 | p1 fig5 |
| 垂直剖面 | fade_area_x 水平淡出 + glow_line | p1 fig4 |
| 密度/分布 | violin lighten 填充 + PathCollection 荧光轮廓；boxplot 同理 | p1 fig6/fig8 |
| ROC/PR | AUC 区域 gradient_area | p2 fig12 |
| FD  fundamental-diagram | 容量面 gradient_area + 边界 glow | p2 fig08/fig10 |
| 每问框架图 | **砍量**：论文二流程图 13→2，结论进 caption | 驳回D轮 |

保留柱形的唯一条件：必须 gradient_bar+glow 全套（终版仅 2 个柱状，均达标）。

## 四、验收门禁管线（收口必跑，全绿才算过）

1. 重绘图脚本 `rng=default_rng(42)` 确定性重生成 → 数值零改动核对
2. `xelatex×2`，`grep -c "^!" main.log` = 0；fitz 扫 `\uffff` notdef=0
3. 硬门禁：`学术工作流/academic-toolkit/skills/shared-scripts/figure_pdf_quality_check.py figures --paper paper`（插入后 ≥8pt、对比度 ≥4.5）+ `figure_text_budget.py figures`（图内解释性文字移 caption）
   - ⚠ 路径雷：shared-scripts 在 `academic-toolkit/` 下，旧 `科研工具箱/` 路径已失效
4. **驱动 Agent 视觉全页复审**（montage + 关键页单独渲染），文字门禁抓不到的（标题互碰、图例丢手柄、面板挤压）只能靠看图
5. 图型改动后同步正文措辞（如"柱状图的形态"→"得分点阵的对比"）

## 五、matplotlib 坑清单（本轮实测）

- 基类 `Patch` 抽象 → 图例手柄用零尺寸 `Rectangle((x,y),0,0)`
- violin body 复制：`PathCollection([pc.get_paths()[0]])`，不是 PolyCollection
- boxplot box 是 PathPatch（无 get_xy）：`PathPatch(p.get_path(), transform=p.get_transform())`
- CJK：`font.family='serif'+serif链` 回退失效，必须 `font.family=[列表]`；含中文串禁 `$...$` mathtext（方框），单位用 Unicode 上标（veh·h⁻¹）
- 缺字形集 `∈ ⊮ ∃ ∀ ∗ ‖` 渲染 U+FFFF；λ τ θ µ Ω 正常
- Bash heredoc 会折叠 `\\`：含反斜杠的代码一律 Write/Edit 落盘再执行
- refactor 后回查图例：gradient_bar 替换原 bar 时 Rectangle 手柄易丢（fig17 实测）

## 六、边界与诚实遗留

- 图内文字预算：解释性标注移 caption 或删冗余；面板题互碰需二次收窄后**重看图**再宣称 PASS
- 灰度打印下浅色渐变头偏弱（p1 fig13a）——靠描边+数值标注缓解，如实声明
- 编造红线：无出处的"真实资料区间"类评审要求可拒绝整改（超版面级边界）

## 七、参数速查附录（真源 = `work/figstyle_v2.py` v2.2，行号按该版本；换版本以脚本为准，本表仅迁移参考）

### 7.1 字号阶梯（L30–35，按"插入文档后 ≥8pt"反推，画布约 6.1 in）

`FS_TITLE 11.0 / FS_LABEL 10.5 / FS_TICK 9.5 / FS_LEGEND 9.5 / FS_ANNO 9.0 / FS_NOTE 8.5`
字体回退链（L24）：`Times New Roman → Noto Serif SC → Source Han Serif SC → SimSun → DejaVu Serif`。

### 7.2 辅助函数全签名（含默认值）

```python
gradient_box(ax, x, y, w, h, pastel, *, vertical=True, rounding=0.12,
             glow=0.30, lw=1.3, zorder=2, alpha_top=0.62)   # L119 流程图/卡片三件套：
    # halo = FancyBboxPatch(linewidth=lw+3.2, alpha=glow)；填充 lighten(fill, 0.62)→fill
gradient_bar(ax, x0, y0, w, h, color, *, horizontal=False, fade=0.78,
             lw=1.0, glow=0.30, zorder=3)                    # L161 halo lw+2.6
gradient_area(ax, x, y, color, *, baseline=0.0, max_alpha=0.5, zorder=1)  # L187 淡端 alpha=0.02
fade_area_x(ax, x_curve, y, color, *, max_alpha=0.38, zorder=1)           # L212 向 x=0 渐隐
glow_scatter(ax, x, y, color, *, s=42, alpha=0.26, scale=2.8, zorder=3)  # L231
glow_line(ax, x, y, color, *, lw=1.8, alpha=0.22, zorder=3)              # L237 底衬 lw+2.8
lighten(hexv, t) / deepen(hexv, t=0.45) / ink_of(hexv)                   # 浅化/加深/取同族墨色
```

### 7.3 轴与网格（`apply` L243）

左+下 spine `#8A8A8A` lw 0.8；top/right 默认不可见（boxed 才开，`#C9C9C9` lw 0.6）；网格 `GRID #EBE8E3` lw 0.6 zorder 0；`set_axisbelow(True)`；图例 framealpha 0.92、edgecolor NEU、直角框。
**画幅纪律**：宽高比约 2.2:1 近横幅，禁近正方形+图外巨图例（参考论文构造基准）。

### 7.4 PASTEL 框色对（L95–102，逐像素取自参考论文 p5/p17）

yellow `#F7E8C3/#D89060` · orange `#F6DCC8/#C97A46` · blue(青绿族) `#DCF5F1/#3ECFBE` · green `#E2F0DC/#78A878` · rose `#F2DCDC/#C08478` · gray `#EFEDE8/#9A968A`

### 7.5 序列与线型（L73–80）

- `WARM_SEQ`（时间/位置越远越浅）：`#A3490D → #C74C53 → #FEB8B5 → #FED3A1 → #FEE6A9`
- `COOL_SEQ`（无藏蓝）：`#00B4AD → #2CC8BC → #2BC3F1 → #6FCDFD → #9FE698`
- 数据线主色 `PC = [#00B4AD, #2BC3F1, #C74C53, #FDA574]`（族深端，浅色禁作细线）
- 线型循环 `LS_SEQ = ["-", (0,(4,1.5)), (0,(1,1)), (0,(3,1,1,1))]`——多系列须"颜色+线型"双编码

### 7.6 标题纪律（`panel_title` L275）

单面板图**禁止**图内标题（结论进 caption）；`panel_title` 仅用于多面板 (a)(b) 小标题（FS_TITLE 11，pad 6）。
