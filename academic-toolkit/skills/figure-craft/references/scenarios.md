# 统一配色方案 · 场景映射与使用规范

> **真源分工**：本文件是人读规范（**怎么选、怎么用、什么不许用**）；
> 机器可读真源是同目录 `../assets/palette_registry.json`（色值、类型、CVD 契约、禁用清单），
> 机检：`python palette_kit.py registry-verify`（子命令在 `../scripts/palette_kit.py`）。
> 两者必须同改；色值以 JSON 为准，本文件不重复抄色值（防双源漂移）。

---

## 一、三步选色法（先定类型，再定色板）

```
第 1 步：看数据类型
   类别（A/B/C，无大小关系）        → categorical
   单向连续（低→高，无零点语义）     → sequential
   有意义的零点（残差/相关系数/偏差） → diverging

第 2 步：看使用场景（见 §二表格）
   场景决定"用哪一套"，并决定是否要求灰度可分

第 3 步：看容量与冗余
   类别数 ≤ 色板容量（分类色上限 7-8）；超了就分面（facet）或加第二编码
   任何分类图都叠加线型/标记/直接标签 —— 这不是可选项
```

**类型选错，任何美化都救不回来**：把分类数据画成连续色带，读者会读出并不存在的"高低"。

---

## 二、场景 → 色板映射（5 个场景）

| 场景 id | 适用 | 分类色 | 顺序色带 | 发散色带 | 灰度 | CVD 政策 |
|---------|------|--------|----------|----------|------|----------|
| `cn-competition` | 中文竞赛论文（国赛/省赛/校赛） | `summer-beach-v6` | `summer-beach-ramp` / `summer-beach-moist-ramp` | `rdbu` | **要求** | 允许第二编码 |
| `journal-submission` | 英文期刊投稿（Elsevier/IEEE/Springer/Nature 系） | `okabe-ito`（备 `tol-bright`） | `viridis`（备 `cividis`） | `rdbu` | **要求** | **要求直用可分** |
| `thesis-report` | 学位论文 / 课程报告 / 教学材料 | `tol-bright` | `cividis` | `pu-or` | **要求** | **要求直用可分** |
| `slide-poster` | 答辩幻灯 / 会议海报 | `tol-bright` | `viridis` | `rdbu` | 不要求 | **要求直用可分** |
| `office-embed` | Word / PPT / Excel 内嵌图表 | `summer-beach-v6` | `summer-beach-ramp` | `rdbu` | 不要求 | 允许第二编码 |

### 各场景使用要点

- **`cn-competition`**：本地 v6「夏日海滩」是**填充型**色板（实测 CVD 最近色对 ΔE=1.7，
  白底对比 1.2–2.1:1）。它靠**墨色描边 + 线型 + 直接标签**区分类别，**不得**仅凭颜色区分。
  色带（温度/水分）已通过灰度单调复核，黑白打印仍可读。
- **`journal-submission`**：多数期刊明示要求色盲友好（Nature / Cell / PLOS / eLife 为硬性）。
  Okabe-Ito 是分类首选；连续量用 viridis，无障碍优先时换 cividis。**期刊品牌色板
  （ggsci 系：npg/jama/lancet/nejm）只解决"风格合规"，不保证无障碍**——用了必须自行复核灰度与色盲。
- **`thesis-report`**：常以黑白稿提交，优先灰度可分；JAMA/NEJM 系的品牌色不可用于此。
- **`slide-poster`**：投影会压暗中间调，别用浅色作唯一区分；类别数压到 5 以内。
- **`office-embed`**：Office 会二次压缩重采样，导出用 400 dpi PNG 或矢量 PDF，**不要用截图**；
  色值不得改动。

---

## 三、使用规范（10 条铁律）

| # | 规范 | 违反后果 |
|---|------|----------|
| R1 | 先定数据类型再选色板（分类/顺序/发散） | 读者读出不存在的高低关系 |
| R2 | 三层分工：色板只承担填充/色带，线条/描边/图例文字用同色相**墨色** | 浅色当线条 → 白底上不可见 |
| R3 | 类别数不超过色板容量（分类 7-8 上限） | 图例失效，相邻色无法区分 |
| R4 | **第二编码冗余**：分类图必须叠线型/标记/直接标签 | 灰度或色盲下信息全丢 |
| R5 | 顺序色带必须明度单调（任一方向）；发散色带中点最亮/最暗且两臂单调 | 灰度打印出现假环带 |
| R6 | 禁用色板零容忍（见 §四），草稿也不行——草稿会进正文 | 直接构成图表硬伤 |
| R7 | 全文色板语义一致：同一颜色只表达同一含义 | 跨图误读 |
| R8 | 深色一律 `deepen`（固定色相压明度、彩度取色域上限），禁 `darken` | 深而浊，色板整体发灰 |
| R9 | 导出即定稿：在导出分辨率下复核色带与图例字号 | 屏幕好看、打印糊成一团 |
| R10 | 移植 Office 按 `office-embed` 执行，色值不得改 | 双源漂移，前后不一致 |

---

## 四、禁用清单（任何场景不得使用）

| 禁用 | 别名 | 原因 | 替代 |
|------|------|------|------|
| `jet` | `rainbow`、`turbo` | 非感知均匀且亮度非单调，灰度后出现假环带 | `viridis` / `cividis` |
| `RdGn` | `rd-yl-gn` | 红-绿发散：红绿色盲（约占男性 8%）分不清两端 | `rdbu` / `pu-or` |
| `RdYlGn` | `red-yellow-green` | 同 RdGn，且中段黄与两端灰度接近 | `rdbu` / `BrBG` |
| `hsv` | `spectral-cycle` | 色相环形循环无单调明度 | `tol-bright` / `okabe-ito` |
| 期刊品牌色板 | `ggsci-npg` / `jama` / `lancet` / `nejm` | **风格合规工具，非无障碍工具** | 仅期刊强制要求品牌风格时用，且须自行复核灰度+色盲 |

---

## 五、机检与留痕

```bash
cd academic-toolkit/skills/paper-figure-palette/scripts
python palette_kit.py check             # 本地 8 色板体检：对比度/去灰比/灰度单调/色盲最近对
python palette_kit.py registry-verify   # 全注册表体检：色值/单调性/CVD 契约/场景交叉一致
```

`registry-verify` 的四类硬 FAIL 与两类 WARN：

- **FAIL**：非法 hex、色板内色值重复、顺序色带非单调、发散色带中点非极值或两臂不单调、
  声明 `cvd_mode=direct` 但最近色对 ΔE < 12、`secondary_encoding` 未声明第二编码要求、
  场景引用不存在的色板或禁用色板、`cvd_policy=direct_required` 却映射填充型色板；
- **WARN**：最近色对 ΔE 介于 12–25（建议加第二编码）、要求灰度可分的场景用了填充型色板。

> **WARN 不是免责**：命中 WARN 时必须在交付说明或图注中留痕（说明叠加了哪些第二编码），
> 否则视为"知道有风险而不处理"。

---

## 六、与相关技能的边界

| 技能 | 负责什么 | 不负责什么 |
|------|----------|-----------|
| `paper-figure-palette`（本技能） | 色值真源、类型与场景映射、使用规范、禁用清单、机检 | 图形构图、字号、排版 |
| `palette-health-check` | 单套论文色板的**去灰提彩**诊断与重解（C*/Cmax、deepen、入带序单调） | 多场景选型 |
| `figure-aesthetics-craft` | 图形质感技法（渐变语义、边色继承、绘图纪律） | 色值选择 |
| `_utils/figure_pdf_quality_check` | 出图后的 PDF 级门禁（图内文字预算、字号下限） | 配色合规 |

冲突时以本技能的类型/场景映射与禁用清单为准（配色合规责任在本技能）。
