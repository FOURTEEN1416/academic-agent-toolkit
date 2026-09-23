# 搭配与移植配方（recipes.md）

> 每一节都是"抄了就能用"的完整配方。色值来自 `assets/palette_v6.json`；
> 原理见 `color-system.md`。

## 1. matplotlib 全套（论文级 rcParams）

```python
from palette_kit import (T4, T3, T2, TMAIN, TACC, M4, M2, M1,   # 8 色
                         NEU, INK, CRIT, GRID,                  # 中性
                         INK_MAP, deepen, ramp_lab, lighten,
                         CMAP_TEMP, CMAP_MOIST, LINESTYLES)

plt.rcParams.update({
    "font.sans-serif": ["Microsoft YaHei", "SimHei", "Arial", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "font.size": 9.4, "axes.labelsize": 9.6, "axes.titlesize": 9.8,
    "xtick.labelsize": 9.1, "ytick.labelsize": 9.1, "legend.fontsize": 8.9,
    # 图例压在渐变填充上必须有极淡白底，否则"陷进"填充里
    "legend.frameon": True, "legend.framealpha": 0.92,
    "legend.facecolor": "white", "legend.edgecolor": "#E4E0D8",
    "legend.fancybox": False, "legend.borderpad": 0.35,
    "axes.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False,   # 顶/右脊去掉
    "axes.facecolor": "white", "figure.facecolor": "white",
    "lines.linewidth": 1.8, "lines.markersize": 5,
    "xtick.direction": "in", "ytick.direction": "in",        # 刻度朝内
    "mathtext.fontset": "stix",
    "figure.dpi": 120, "savefig.dpi": 400,                   # 印刷 400dpi
    "savefig.bbox": "tight", "savefig.pad_inches": 0.03,
})
```

**字号带**（以 455pt 版心、图宽 0.92×版心为基准；其他版心按比例换算）：
正文 7.7 / 轴标签 7.8 / 标题 8.0 / 刻度 7.4 / 图例 7.3 pt。
只缩字号、不整幅缩放——整幅等比缩小不改变"文字相对图幅"的观感。

**典型双曲线对比图**：

```python
ax.plot(t, T, color=INK_MAP[TMAIN], lw=1.8, ls="-", label="温度")   # 墨色线
ax.fill_between(t, T, alpha=0.18, color=TMAIN)                      # 基色大面积
ax.plot(t, C, color=INK_MAP[MMAIN], lw=1.8, ls="--", label="水分")  # 线型冗余
ax.axhline(0.15, color=CRIT, lw=1.2, ls=(0, (4, 3)))                # 判据线
ax.grid(True, color=GRID, lw=0.6, ls=(0, (4, 3)), zorder=0)         # 网格垫底
```

**热图 + 等值线 + 白描边标注**：

```python
im = ax.imshow(T2d, cmap=CMAP_TEMP, aspect="auto", origin="lower")
cs = ax.contour(X, Y, T2d, colors="white", linewidths=0.7)
lbls = ax.clabel(cs, fontsize=7.5, colors="#2B2B2E")
for lb in lbls:                                   # 白色光晕：浅底深底都可读
    lb.set_path_effects([pe.withStroke(linewidth=1.8, foreground="white")])
```

**矢量渐变（面积填充不用 imshow！）**：用 44 层细竖带逐层加深（grad_under），
或 `fill_between(..., alpha=0.15~0.25)` 单层浅填充。imshow 渐变在对数轴上会生成
畸形巨型位图（实测曾放大 66 倍文件体积），**面积渐变一律矢量**；
仅热图与 3D 曲面允许位图。

**荧光描边 glow（主曲线顶刊质感）**：底层三层加宽低透明度描边 + 顶层实线，
参数 (6.5pt, α=.10) / (3.6pt, α=.16) / (1.9pt, α=.26)，顶层墨色 lw=1.8。

**交替行底色（表格型图/雷达图背景）**：`ax.axhspan(k-0.5, k+0.5, color="#FBF7F1")`
——与暖族同调的极浅米白，比纯灰柔和。

## 2. TikZ / LaTeX（框架图、流程图）

```latex
\definecolor{fwTemp}{HTML}{FDA574}   % 温度深端 = 唯一高亮
\definecolor{fwTempB}{HTML}{FEBDAA}  % 蜜桃次色
\definecolor{fwTempC}{HTML}{FED3A1}  % 浅橙
\definecolor{fwWarm}{HTML}{FEE6A9}   % 浅黄
\definecolor{fwMoist}{HTML}{6FCDFD}  % 冷锚亮蓝
\definecolor{fwMoistB}{HTML}{2BC3F1} % 天蓝
\definecolor{fwMoistC}{HTML}{9FE698} % 浅绿
\definecolor{fwNeu}{HTML}{B6B6B2}    % 中性灰
\definecolor{fwInk}{HTML}{2B2B2E}    % 文字

% 毛玻璃主卡片：shade 渐变 + 两层 preaction 荧光 + 圆角
\tikzset{
  fwmain/.style={rounded corners=1.8mm, align=center, text=fwInk,
    draw=fwTemp!88!black, line width=1.05pt,
    top color=fwTempC!18!white, bottom color=fwTempC!52!white,
    preaction={draw=fwTemp, line width=3.0pt, opacity=0.20, line cap=round},
    preaction={draw=fwTemp, line width=1.6pt, opacity=0.34, line cap=round}},
  fwsub/.style={rounded corners=1.5mm, text=fwInk, draw=fwNeu!78!black,
    line width=0.5pt, fill=white},
  fwarrow/.style={-{Stealth[length=2.1mm,width=1.9mm]}, line width=1.05pt,
    draw=fwTempB!78!black, rounded corners=1.2mm},
}
```

**TikZ 混色规律**（本体系在 TikZ 里的"deepen"等价物）：
描边 = `主色!62!black ~ !92!black`（越主要越深：主卡片 88%、子卡片 85%、
容器 62–72%）；填充 = `top color=浅色!3~18!white, bottom color=浅色!13~52!white`
（上浅下深制造受光感）；文字一律 fwInk（可 `fwInk!82` 弱化）。
箭头/总线用次色 `!78!black`，纯装饰小箭头用 `fwNeu!58!black`。

**连线纪律**：全部正交圆角路径（avoid 对角斜线）；层级越低线宽越细
（1.05 / 0.8 / 0.55pt）；投影只给顶层卡片（general shadow 柔和投影）。

## 3. Word / PPT / Excel 移植表

| 用途 | 取色 |
|---|---|
| 表头底纹 | T4 `#FEE6A9`（文字用 INK）或 M4 `#9FE698` |
| 隔行底纹 | `#FBF7F1`（暖调米白） |
| 强调单元格 | TACC `#FDA574` @ 30% 着色 |
| 图表系列 1/2 | TMAIN / MMAIN；线条用墨色 `#C74C53` / `#307697` |
| 阈值参考线 | CRIT `#57575A` 虚线 |
| PPT 标题条 | 白底 + TACC 细色条（4px），勿整条大色块 |
| 页面文字 | INK `#2B2B2E`（替代纯黑，更柔和） |

Excel 折线图默认把基色用作线条色——**手动改**：系列格式 → 线条用墨色，
标记用基色，形成"深线浅点"层次。

## 4. 图型 → 配色映射（论文 21 图的实践总结）

| 图型 | 色彩方案 |
|---|---|
| 场演化热图（T） | CMAP_TEMP + 白等值线 + 深字白晕标注 |
| 场演化热图（C） | CMAP_MOIST + 同上 |
| 多时刻剖面族 | 暖族按时间序 T4→T3→T2→TMAIN（墨色线）+ 线型冗余 |
| 双量时程对比 | TMAIN 族（温度）vs MMAIN 族（水分），墨色线 + 0.15~0.2 α 填充 |
| 干燥速率特性 | M1 墨色主曲线 + CRIT 判据虚线 + INK 箭头文字标注 |
| 3D 物性曲面 | CMAP_TEMP + 底面等值线投影（同带淡色） |
| 收缩镶嵌图 | 每时刻圆柱截面用 CMAP_MOIST 着色 + 白色分隔线 |
| 灵敏度雷达 | ±20% 两向：TACC（正向）vs M1（负向），背景 GRID 同心环 |
| 龙卷风图 | 正向条 TACC 渐变、负向条 M1 渐变，零线 INK 实线 |
| 收敛双对数 | 数据点墨色 + N⁻² 参考斜线 NEU 虚线 + 判据横线 CRIT |
| 验证汇总图 | 各验证行 axhspan 交替 #FBF7F1，条形按所属问题取族色 |
| 求解框架图 | TikZ 毛玻璃卡片：暖族（求解器）+ 冷族（输出/水分语义） |

## 5. 检查清单（出图后 60 秒自检）

- [ ] 文字全部 INK / 墨色，无基色细字
- [ ] 曲线/描边全部墨色，无 darken 痕迹（浑浊深灰彩）
- [ ] 全图最多一个 TACC 级高亮
- [ ] 多曲线有线型冗余（≥2 种线型）
- [ ] 网格 GRID 在 zorder=0 垫底，不压数据
- [ ] 热图色带与本图语义族一致，无 rainbow
- [ ] 图例白底半透明（framealpha≈0.92）
- [ ] `python scripts/palette_kit.py check` 全 PASS
- [ ] 灰度打印预览无"假亮带"、无并列同灰
