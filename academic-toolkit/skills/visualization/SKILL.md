---
name: visualization
description: "Visualization Skill——把数据和模型结果画成”评委一眼能看懂”的图。**图好 = 论文档次 +1 档**。"
---

# Visualization Skill

## 用途
把数据和模型结果画成"评委一眼能看懂"的图。**图好 = 论文档次 +1 档**。

## 触发时机
- 数据清洗后画 overview
- 模型结果出来后画对比 / 预测 / 灵敏度
- 论文写作时统一配色 / 字体

## 输入
1. 清洗后数据 + 模型结果
2. 论文整体配色（建议 ≤ 4 色）

## 输出
1. **所有图**（`work/figures/*.png`，300 DPI，白底）
2. **图表说明**（`work/figures/README.md`，每张图：标题 + 含义 + 数据来源）

## 强制作图清单
每篇国一论文必备 6 类图：
| # | 图类型 | 数量 | 用途 |
|---|--------|------|------|
| 1 | 数据概览 | 3-4 | 缺失/分布/相关/异常 |
| 2 | 模型结构 | 1-2 | 流程图 / 算法框图 |
| 3 | 结果对比 | 2-3 | 基线 vs 改进（柱状/折线） |
| 4 | 预测拟合 | 2-3 | 实际 vs 预测（散点 + 折线） |
| 5 | 灵敏度分析 | 1-2 | 参数扰动 → 指标变化 |
| 6 | 综合评价 | 1-2 | 雷达图 / 热力图 / 排名 |

**总数 12-15 张图，AAAI/中文学报标准**。

## 配色方案（真源引用，不自创）
```python
# 基线真源 skills/_utils/academic.mplstyle（elegant 定版色板 + CJK 字体链 + 印刷字号）；
# 竞赛场景按 paper-figure-palette 统一注册表（skills/paper-figure-palette/assets/palette_registry.json）选板——色值不得自创。
# 默认色环（tab10/#1f77b4 系）是"AI 默认味"来源，禁用。
COLORS = {
    'primary': '#7AAEC8',     # 蓝
    'secondary': '#E8945A',   # 橙
    'success': '#7BC8A4',     # 绿
    'warning': '#E0A0A0',     # 红
    'neutral': '#8FAEC0',     # 灰蓝
    'palette': ['#7AAEC8', '#E8945A', '#7BC8A4', '#E0A0A0', '#9B8EC4']
}
```

## 字体设置（中文不乱码）
```python
# 基线：skills/_utils/academic.mplstyle（setup_style() 一键加载——CJK 字体链、
# 色板、印刷字号、savefig 不裁剪护栏均内置）；手动 rcParams 仅作差异项覆盖
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['SimHei']      # 中文（基线已含 Noto Sans SC 链）
plt.rcParams['axes.unicode_minus'] = False        # 负号
plt.rcParams['figure.dpi'] = 300                  # 高清
# savefig 不裁剪为交付护栏；bbox_inches='tight' 仅屏幕预览用
```

## 常用代码片段
```python
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

# 1. 数据分布（4 子图）
fig, axes = plt.subplots(2, 2, figsize=(12, 10))
axes[0,0].hist(df['x']); axes[0,0].set_title('x 分布')
axes[0,1].boxplot(df['x']); axes[0,1].set_title('x 箱线图')
# ... 缺失/相关/异常

# 2. 模型对比（柱状）
methods = ['基线', '改进1', '改进2']
rmse = [0.85, 0.72, 0.65]
plt.bar(methods, rmse, color=COLORS['palette'])

# 3. 预测拟合（散点 + 折线）
plt.plot(y_test, label='实际')
plt.plot(pred, label='预测', linestyle='--')
plt.legend()

# 4. 灵敏度分析（折线 + 误差棒）
plt.errorbar(params, means, yerr=stds, marker='o')

# 5. 雷达图（综合评价）
from math import pi
categories = ['A', 'B', 'C', 'D', 'E']
values = [4, 3, 5, 4, 3]
angles = [n / len(categories) * 2 * pi for n in range(len(categories))]
plt.polar(angles + [angles[0]], values + [values[0]])

# 6. 热力图（相关性）
sns.heatmap(df.corr(), annot=True, cmap='coolwarm')

# 保存
plt.tight_layout()
plt.savefig('work/figures/xxx.png', dpi=300)
```

## 画图铁律
1. **白底**：不要用默认灰底
2. **300 DPI**：PDF 矢量图优先
3. **图例齐全**：标题 + 轴标签 + 单位
4. **配色统一**：全篇用一套色板
5. **无 gridnoise**：少用 grid
6. **数字标注**：关键数据点上标数字
7. **图大小**：单图 ≤ 5MB，单张图 ≤ 半页 A4

## 必填交付物
- `work/figures/*.png`（12-15 张）
- `work/figures/README.md`（每张图：标题 + 用途 + 数据源）

## 后续 Skill
- `paper-writing`：图表放进论文
