# 绘图方式手册（plotting-playbook）— 质感三件套与 figstyle API

> 真源脚本：`_utils/figstyle.py`。本文件是"怎么画出质感"的操作手册 + 全函数签名速查。
> 换版本以脚本为准。

## 一、质感三件套铁律

每个图形元素 = **浅渐变填充 + 同族加深描边 + 外扩荧光层**，缺一即"纯色平涂"被打回。

- **浅渐变填充**：`imshow` 竖向/横向渐变（`color → lighten(color, fade)`），`clip` 到边框 patch。
- **同族加深描边**：`edgecolor=color`（或 `deepen`/`ink_of`），`linewidth` 常规。
- **外扩荧光层**：另叠一条 `linewidth+2.6~3.2`、`alpha≈0.22~0.30` 的 halo（垫在主体 zorder 之下）。

## 二、辅助函数全签名（含默认值）

```python
setup_style(palette="elegant", **kw)
    # 一次性设定字体/字号/色板；同包有 plot_utils 时委托其 setup_style。

apply(ax, *, grid=True, boxed=False, bg=None)
    # 左+下 spine #8A8A8A lw0.8；top/right 默认不可见（boxed 才开 #C9C9C9 lw0.6）；
    # 网格 GRID #EBE8E3 lw0.6 zorder0；set_axisbelow(True)；bg=面板浅底色。

gradient_box(ax, x, y, w, h, pastel, *, vertical=True, rounding=0.12,
             glow=0.30, lw=1.3, zorder=2, alpha_top=0.62)
    # 流程图/卡片三件套：halo=FancyBboxPatch(lw+3.2,alpha=glow)；
    # 填充 lighten(fill,alpha_top)→fill；返回 FancyBboxPatch（可 set_clip 放文字）。

gradient_bar(ax, x0, y0, w, h, color, *, horizontal=False, fade=0.78,
             lw=1.0, glow=0.30, zorder=3)
    # 渐变柱/条（替代平涂 bar）；halo lw+2.6；horizontal=True 沿 x 渐变。

gradient_area(ax, x, y, color, *, baseline=0.0, max_alpha=0.5, zorder=1)
    # 曲线下/差值渐变带：PathPatch 闭合多边形 + imshow alpha 渐隐（淡端 0.02）；
    # baseline 标量或同长数组；方向按两端均值自动翻转。

fade_area_x(ax, x_curve, y, color, *, max_alpha=0.38, zorder=1)
    # 垂直剖面：沿 x 向 x=0 水平淡出。

glow_scatter(ax, x, y, color, *, s=42, alpha=0.26, scale=2.8, zorder=3, **kw)
    # 大半径半透明垫一层再画真实点。

glow_line(ax, x, y, color, *, lw=1.8, alpha=0.22, zorder=3, **kw)
    # lw+2.8 底衬线 + 主线。

label(ax, *, xlabel=None, ylabel=None)          # FS_LABEL 墨色轴标
legend(ax, *, loc="upper right", **kw)          # framealpha0.92 / edgecolor NEU / 直角框
panel_title(ax, text)                           # 仅多面板 (a)(b) 小标（FS_TITLE11, pad6）
save_fig(fig, path_png, path_pdf=None)          # PNG300dpi + 矢量 PDF 双出（别名 save）
lighten(hexv, t) / deepen(hexv, t=0.45) / ink_of(hexv)   # 浅化 / 加深 / 取同族墨色
```

## 三、色板与序列（真源 `assets/palette_v6.json`）

- 字号阶梯（按"插入文档后 ≥8pt"反推，画布约 6.1 in）：
  `FS_TITLE 11.0 / FS_LABEL 10.5 / FS_TICK 9.5 / FS_LEGEND 9.5 / FS_ANNO 9.0 / FS_NOTE 8.5`。
- 字体回退链：`Times New Roman → Noto Serif SC → Source Han Serif SC → SimSun → DejaVu Serif`。
- `WARM`：T4 #FEE6A9 / T3 #FED3A1 / T2 #FEBDAA / TMAIN #FEB8B5 / TACC #FDA574。
- `COOL`：DEEP 重锚 **#00B4AD**（亮青绿，禁藏蓝），M1 #2BC3F1 / MMAIN #6FCDFD / M3 / M4。
- 序列：`WARM_SEQ`（深→浅，时间/位置越远越浅）；`COOL_SEQ`（青绿深端→浅端，全程无藏蓝）。
- 数据线主色 `PC=[#00B4AD,#2BC3F1,#C74C53,#FDA574]`（族深端，浅色禁作细线）。
- 线型循环 `LS_SEQ=["-", (0,(4,1.5)), (0,(1,1)), (0,(3,1,1,1))]`——多系列"颜色+线型"双编码。
- 文字/小元素墨色单设 `AQUA_INK=#0F7E78`（#00B4AD 太亮不作小字）。
- PASTEL 框色对（fill 浅端 + 同族饱和描边）：yellow/orange/blue(青绿族)/green/rose/gray。

## 四、最小骨架模板

```python
import sys; sys.path.insert(0, "<figure-craft>/_utils")
import numpy as np, matplotlib.pyplot as plt, figstyle as fs
fs.setup_style()
rng = np.random.default_rng(42)                 # 确定性：验收可复跑
fig, ax = plt.subplots(figsize=(6.6, 3.0))      # 近横幅，原生宽≈上页显示宽
fs.gradient_bar(ax, x0, y0, w, h, fs.PC[0])     # 或 glow_scatter / gradient_area ...
fs.apply(ax); fs.label(ax, xlabel="…", ylabel="…"); fs.legend(ax)
fs.save_fig(fig, "out/fig1.png", "out/fig1.pdf")
```
