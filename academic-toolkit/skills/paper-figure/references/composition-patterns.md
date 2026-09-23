# 构图五模式：出版级图表布局手法（收编自 figures4papers）

> 来源：[figures4papers](https://github.com/ChenLiu-1996/figures4papers)
> `scientific-figure-making/references/common-patterns.md`，pinned commit `3c181f8`，
> License CC BY-NC-4.0。本地适应性改写（2026-09-09），见同目录 UPSTREAM.md。
> 该源从其仓库 18 个真实顶会/期刊图项目（figure_* 目录）归纳，与本库
> `figure_style_guide.md`（防丑检查）互补：那边管"检查什么"，这里管"怎么构图"。

## 模式一：超宽画布多指标面板

**何时用**：一张图并排比较 3~4 个指标 × 多个方法（竞赛论文"多指标对比总图"最常见的翻车场景——纵向挤成一团）。

```python
fig, axes = plt.subplots(1, 4, figsize=(28, 6))   # 宽高比 3~4 : 1
```

**📏 期刊栏宽锚点（2026-09-11 收编自 fig-academic @`1df9940`，Apache-2.0）**：单栏 **89mm**（3.5in）、双栏 **183mm**（7.2in）是 Nature 系/CNS 通用口径，也是"最终印刷宽度"的权威取值来源——1×4 连排在 183mm 双栏下每格仅 ~43mm<45mm，按前置条件应改 2×2。竞赛论文（单栏版心 ~150mm）同理先量后连排。

**⛔ 印刷宽度前置条件（2026-09-10 增，先于上式判断）**：上游 (28,6) 级画布是屏幕/海报审图口径，直接缩进版面会翻车——28 in 缩到双栏 ~170mm 后每格仅 ~40mm、单栏 85mm 更窄，字号必跌破 7-9pt 可读下限。**仅当"最终印刷宽度 ÷ 面板数 ≥ 45mm"时才用 1×N 连排**；不满足就改 2×2 或 1×2 堆叠（本技能 SKILL.md 既有守卫"每 panel ≥ 0.45\textwidth"是同一约束的 LaTeX 侧表达）。竞赛论文（单栏版心）实际很少满足 45mm/格，连排前先算这一步。

**为什么**：读者从左到右扫读指标叙事，y 轴与图例保持可读；纵向拥挤是审稿人"看不清"吐槽的头号来源。子图间字号/线宽/语义色必须一致（一致性优先于逐轴装饰）。

## 模式二：独立图例面板

**何时用**：曲线/分组多到图例会压住数据区时。本库 `figure_check.sh` 与 vision 质检都会抓"图例压数据"，此模式是根治手法。

```python
ax_leg = fig.add_subplot(grid_spec[-1])   # 网格中专门留一格
ax_leg.set_axis_off()
ax_leg.legend(*ax_data.get_legend_handles_labels(), loc='center left')
```

**为什么**：数据面板保持干净，图例完整可见——优于 `bbox_to_anchor` 挪到画布外（后者浪费画布宽度且导出裁剪易翻车）。

## 模式三：分类柱隐藏 x 刻度

**何时用**：x 轴是"方法/条件"类别且图例已标识它们时（多方法 × 多指标矩阵）。

```python
ax.set_xticks([])   # 类别名交给图例/面板标题，不重复标
```

**为什么**：十几个方法名横排必然互相重叠或斜排难读；图例单独承担命名后 x 轴零噪音。注意：x 轴是连续数值时**禁止**用此模式。

## 模式四：动态 y 轴缩放

**何时用**：所有数值挤在窄区间（如 85~95）时，固定 0 起点会把差异压扁成"看起来都一样"。

```python
margin = data.std()          # 或 range 的小比例
ax.set_ylim(data.min() - margin, data.max() + margin)
```

**为什么**：比较差异是柱状图的本职；诚实前提是轴范围在图注中写明。竞赛论文答辩时"这图放大了差异"是加分操作而非造假（与截断 y 轴误导的区别：是否披露）。

## 模式五：边线 + hatch 打印安全分离

**何时用**：灰度打印/黑白复印后同色系柱子会糊成一片时——审稿人打印论文是常态。hatch 技法在 `matplotlib` 技能亦有覆盖（SKILL.md 图表增强清单、`references/plot_types.md` 代码示例；2026-09-10 复核更正，前次"全库零覆盖"查重结论有漏）；本模式的价值是**决策打包**——何时用、边线+hatch 二维分离的组合方式、与打印质检门禁的衔接。

```python
ax.bar(x, y, color=PALETTE["blue_main"], edgecolor='black', linewidth=2)
ax.bar(x, y2, color=PALETTE["blue_main"], hatch='/',  edgecolor='black')  # 同色不同纹
ax.bar(x, y3, color=PALETTE["blue_main"], hatch='.',  edgecolor='black')
```

**为什么**：色相在灰度转换后只剩明度差；黑边线提供硬轮廓，hatch 提供"纹理 × 明度"二维分离，双保险。hatch 纹理字典：`'/'` `'\'` `'.'` `'|'` `'-'` `'+'` `'x'` `'o'`。

## 使用顺序建议

构图决策放在出图前（规划阶段读本文件选模式），而非出图后补救：
1. 多指标对比 → 模式一（超宽）+ 模式三（隐藏刻度）；
2. 方法多图例大 → 模式二（独立图例）；
3. 数值区间窄 → 模式四（动态 y 轴）；
4. 要过打印关 → 模式五（边线+hatch）+ [semantic-palette.md](semantic-palette.md) 的 alpha 梯度。

## 六、多面板反冗余三原则（收编自 fig-academic @`1df9940`，Apache-2.0；2026-09-11 适应性改写）

多方法多指标组合图（`[2-panel]`/`[4-panel]`）规划时，在选完构图模式后过这三关：

**1. 反冗余三层递进**——每个 panel 必须回答**唯一**问题；遮住任一 panel 读者若无损失，该 panel 就是冗余：

| 层 | 问题 | 编码方式 |
|---|---|---|
| Overview 总览 | "整体模式是什么" | 堆叠柱/构成/总体分布 |
| Deviation 偏差 | "各组独有什么" | Z-score 热力图/发散色图/相对基线 |
| Relationship 关系 | "变量如何共变" | 散点/气泡/相关 |

典型冗余陷阱：绝对值+绝对值（同数据两种画法）→ 把其一改成偏差层；子集重复排名→合并或换成关系图；"不同视觉同一数据"（饼图+堆叠柱）→ 二选一。**终检四问**：同数据？同问题？可互相推导？去掉不动摇结论？——任一"是"即冗余。3 个信息致密的非冗余 panel 胜过 6 个有重复的。

**2. Hero Panel 原则**——每张多面板图要有且只有一个**主面板**：面积 1.2-1.5× 于辅助面板、居左上/居中最显眼位、用强调色（全图唯一允许高饱和处）、直接承载核心结论（审稿人看它 3 秒拿到主信息）。辅助面板更小、次级色、低饱和。

**3. 叙事排序**——panel 阅读顺序=左→右、上→下，**顺序就是故事**：数据证据在前、模型/示意图在后（示意图放 (a) 会暗示"这是推测"）；灵敏度/稳健性检验收尾。

## Related

- [semantic-palette.md](semantic-palette.md) — 语义调色板（本源另一半）
- `../SKILL.md` — 本技能入口（Output Contract / Workflow）
- `../../shared-scripts/figure_style_guide.md` / `../../_utils/figure_style_guide.md` — 防丑检查清单
