# UPSTREAM 溯源台账 — palette-health-check

- Upstream: 本仓库下游工程 cumcm2026A（非外部 URL 源，本队原创实战沉淀）
- Pinned commit: 不可固定（下游工程未纳入版本控制，成包于 2026-09-12 配色 v5→v6 定稿轮）
- License: CC-BY-NC-4.0（与仓库一致）
- Local use: `skills/palette-health-check/`（SKILL.md + bin/ 3 脚本 + data/ 4 真源 + references/cvd_check_v6.png）

| 项 | 值 |
|----|----|
| 来源 | 本仓库下游工程 `D:\Desktop\workbuddy_space\cumcm2026A`（CUMCM 2026A 论文工程）第六轮配色优化实战沉淀 |
| 成包时间 | 2026-09-12（配色 v5→v6「去灰提彩」定稿轮） |
| 原始资产包 | `cumcm2026A/palette_kit_v6/`（自包含：bin 3 脚本 + data 4 真源 + review 目检图 + README + SKILL.md） |
| 迁移文件 | SKILL.md / README.md / bin/{design_palette_v6, palette_cvd_check_v6, make_cvd_sheet_v6}.py / data/{_palette_v6.json, _cvd_v6.json, _cvd_v6.txt, _cvd_ramp_v6.txt} / references/cvd_check_v6.png |
| 许可证 | 与仓库一致（本队原创，随仓库 CC-BY-NC-4.0 发布） |
| 依赖 | 仅 `numpy` + `matplotlib`（画图板需要）；`design_palette_v6` / `palette_cvd_check_v6` 核心仅标准库 |
| 本地适配 | ① 目检图 `cvd_check_v6.png` 由 `review/` 移至 `references/`（对齐 skill 惯例：非 SKILL.md 直接依赖的辅助材料归 references）；② 脚本路径用 `os.path.dirname(__file__)` 相对定位，迁移后自动指向本 skill 目录，无硬编码论文工程路径 |

## 设计要点（为何可复用到其它工程）

1. **量化"发灰"**：`ratio = C*/C*max(L*, H°)` —— 该色在其明度/色相下占 sRGB 色域上限的彩度比例。低 = 发灰。
2. **`deepen` 替代 `darken`**：`darken`（RGB 向黑等比缩放）会同步砍彩度 → 深而浊；`deepen` 固定 H°、压 L*、彩度取色域上限的 `INK_RATIO` 倍 → 饱满深色。
3. **复核脚本独立重写色彩数学**（`palette_cvd_check_v6.py` 不 import `design_palette_v6.py`）：共用实现只能验"自洽"，验不出真实回归——v6 初版温度带"假亮带"正是独立复核抓到的。

## 与既有技能的边界

- 与 `figure-aesthetics-craft`（参考配色**提取**、渐变/边色/绘图纪律）互补：本技能管**配色体检与去灰提彩**（"已有一组色板，怎么修得更好 + 怎么机检"）。
- 与 `_utils/` 三闸（tikz_palette_check / figure_text_budget / figure_pdf_quality_check）互补：本技能提供**第四道"色彩健康闸"**的判据与脚本，接口可按 argparse + 退出码对齐。
