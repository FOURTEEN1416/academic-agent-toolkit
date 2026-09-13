---
name: palette-health-check
description: >-
  论文/报告配色「去灰提彩」与可验证配色体检。当用户说配色"发灰、发闷、太重、不够鲜艳、
  有点克制"，或需要为新论文工程建立可复核的用色体系（顺序色带、多序列分类色、线条/描边墨色）
  时使用。提供 C*/Cmax 去灰指标、deepen（固定色相压明度、彩度取色域上限）替代 darken、
  色盲/灰度/入带序单调性复核，以及三道既有图件闸之外的"色彩健康闸"接法。
  触发词：配色发灰、颜色太深、不够鲜艳、色板优化、顺序色带单调、色盲自检、deepen、darken、
  C*/Cmax、palette health check。
agent_created: true
---

# 配色健康体检（palette-health-check）

把"配色好不好看"翻译成**客观可测、可机检**的量，避免改完仍靠眼缘。
完整方法论与真源见同目录 `README.md` 与 `data/_palette_v6.json`。

## 何时用

- 用户对配色给出**主观负评**："发灰 / 发闷 / 太深 / 不够鲜艳 / 太克制 / 看着脏"。
- 新建论文工程需要一套**顺序色带 + 分类色 + 线条墨色**且要通过灰度/色盲/单调性复核。
- 要把配色检查接入既有的图件三道闸（tikz_palette / figure_text_budget / figure_pdf_quality）。

## 三条核心判据（先量测，再动手改）

1. **去灰指标** `ratio = C* / C*max(L*, H°)`
   —— 该色在其明度/色相下占 sRGB 色域上限的彩度比例。低 = 本可更艳却没用满 = 发灰。
   暖族目标 ≥0.94。
2. **深色必须用 `deepen()`，禁用 `darken()`**
   —— `darken`（RGB 向黑等比缩放）会把彩度一起砍掉 → 深而浊；
   `deepen` 固定 H°、压 L*、彩度取色域上限的 `INK_RATIO` 倍 → 饱满深色。
3. **色带单调性**用累积口径 `max(L* − running_min(L*)) ≤ 0.5 L*`，
   且**按语义入带序**校验（不是按 L* 排序后的清单——见 README 坑 1）。

## 标准流程

```
1. 量测现状   → 对每个色算 L*/C*/H*/ratio；对每条色带算累积回升
2. 定位病灶   → ratio 低的色（发灰）/ 用 darken 生成的墨色（发浊）/ 回升>0.5 的带（假亮带）
3. 重解色板   → bin/design_palette_v6.py 反解：给定目标 L* 与允许的 C*/Cmax
4. 独立复核   → bin/palette_cvd_check_v6.py（**刻意重写色彩数学，不 import 生成脚本**）
5. 目检图板   → bin/make_cvd_sheet_v6.py
6. 落地       → 更新图脚本（基色常量 + 色带深端 + 全部 darken→deepen）
7. 回归       → 重跑既有三道闸，确认未引入新问题（尤其图内文字预算）
```

## 硬约束

- **复核脚本必须独立实现色彩数学**。共用实现只能验自洽、验不了正确——v6 的真实回归
  正是独立复核抓到的。
- 改完配色**必须重跑** `figure_text_budget.py`（改标题/标签极易超 36 显示宽）与
  `figure_pdf_quality_check.py`（字号带）。
- 深色一律 `deepen`；凡出现"向黑缩放"的旧代码，全量替换并**保留注释说明为何改**。

## 产物

- `data/_palette_v6.json`：色板真源（含墨色与对比度）。
- `data/_cvd_v6.txt` / `_cvd_ramp_v6.txt`：色盲/灰度/单调性复核结论。
- `references/cvd_check_v6.png`：目检图板（迁移时由 `review/` 移至 `references/`）。
- 移植建议：转成第四道闸「色彩健康闸」，接口对齐 `_utils/` 既有闸（argparse + 退出码）。

## 脚本调用

```bash
# 1) 生成/重解色板（给定目标 L* 与允许的 C*/Cmax）
python bin/design_palette_v6.py          # -> data/_palette_v6.json + 预览图

# 2) 独立复核（色盲/灰度/入带序单调，刻意不 import 生成脚本）
python bin/palette_cvd_check_v6.py       # -> data/_cvd_v6.txt + _cvd_v6.json

# 3) 目检图板
python bin/make_cvd_sheet_v6.py          # -> references/cvd_check_v6.png
```

> 依赖：仅 `numpy` + `matplotlib`（画图板需要）；`design_palette_v6` / `palette_cvd_check_v6` 核心仅标准库。

## STEP_MANIFEST 产出声明

| 产出 | 类型 | 说明 |
|---|---|---|
| `data/_palette_v6.json` | 色板真源 | 8 基色 + 8 墨色 + 2 色带深端，含 L/C/Cmax/ratio/H/dE/ink/对比度 |
| `data/_cvd_v6.txt` / `_cvd_v6.json` | 复核结论 | 色盲合并风险 / 灰度区分度 / 入带序累积回升（≤0.5 L*） |
| `references/cvd_check_v6.png` | 目检图板 | 色板 + 墨色 + 色带 + 三色盲模拟并排 |

