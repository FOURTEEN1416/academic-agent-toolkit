---
name: nature-figure
description: "Generate publication-ready matplotlib figures matching Nature journal standards. Use when user says 'Nature figure', 'Nature style plot', or needs high-impact journal figures with Nature typography, color systems, and SVG/PDF export."
argument-hint: [figure-plan-or-data-path]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Agent, mcp__codex__codex, mcp__codex__codex-reply
---

# Nature Figure: Publication-Quality Figures for Nature/High-Impact Journals

Generate Nature-style figures from: **$ARGUMENTS**

## Constants

- **FIG_DIR = `figures/`**
- **PRIMARY_FORMAT = `pdf`** (LaTeX embedding, vector)
- **DPI = 300**
- **CUSTOM_REQUIREMENTS** — User-specified requirements, highest priority.

## 📊 Recipe Library Reference (for layout inspiration only — colors stay Nature)

If `PAPER_PLAN.md`'s FIGURE_MANIFEST contains recipe annotations like `fig_q1 // empirical#8`,
you **may** read the corresponding recipe's *layout / annotation style* as a starting point.
However, **colors, fonts, font sizes, line widths, and figure dimensions must strictly follow
Nature's `PALETTE_NATURE` and rcParams** defined below — do **not** copy recipe colors/styles.

```bash
# Read a recipe for layout reference (NOT for colors)
python3 _utils/get_recipe.py empirical 8 2>/dev/null \
  || cat skills/shared-scripts/figure_recipes_empirical.md
```

**Recipe libraries available** (browse for layout inspiration only):
- `basic` / `advanced` / `empirical` / `academic` — generally suitable for Nature-style charts
- `competition` — ⛔ avoid: contest-style charts (Pareto fronts, convergence curves) do not match Nature aesthetics

**Override checklist when using a recipe as starting point:**
- Replace all colors with `PALETTE_NATURE`
- Set `plt.rcParams` per Nature spec (font: Arial/Helvetica 7pt, line width 0.5pt, single-column 89mm)
- Strip recipe-specific decorations (no gradient fills unless single-column heatmap; no Rain Cloud violins)
- Remove `plt.title()` (Nature figures use external captions)

---

## ⛔⛔⛔ Figure Completeness (HIGHEST PRIORITY — prevents "broken / partial" figures)

Nature style is minimal, but **minimal ≠ broken**. Users reported figures that came out as **floating colored blocks with no axes, no ticks, no curves** (e.g. a lone green shaded area, or scattered rectangles). Every figure MUST stay fully readable. Hard rules:

1. **Y-axis MUST keep numeric ticks.** Never call `ax.set_yticks([])` on a data plot — an axis with no scale is unreadable. Sparse (3–5 ticks) is fine, empty is forbidden.
2. **Both `ax.set_xlabel(...)` and `ax.set_ylabel(...)` are mandatory**, with units (e.g. `Time (h)`, `RMSE`). No bare/unlabeled axes.
3. **If you hide x-ticks (`ax.set_xticks([])`), you MUST directly label the data** (`ax.bar_label`, `ax.text`, or `annotate`). Hiding ticks WITHOUT direct labels = broken figure.
4. **Every `fill_between` / confidence band MUST be drawn together with its main line** (`ax.plot(...)`). A standalone shaded area with no curve and no axis is meaningless — this is exactly the "green blob" users complained about.
5. **`ax.set_frame_on(False)` is allowed ONLY for heatmaps / image plates**, never for line / bar / scatter plots — those keep left + bottom spines.
6. **Multi-panel: every subplot must have its own visible axes + labels.** Never leave bare colored rectangles floating with no axis.

⛔ **竞赛 / 中文论文场景**：评委需要完整可读的图（坐标轴 + 刻度 + 单位 + 图例或直接标注齐全）。Nature 的"省略图例 / 隐藏刻度 / 直接标注"只在仍能保证可读时才用，**绝不能产出只剩色块的残图**。每画完一张图，肉眼自检：去掉 caption 后，单看这张图能不能读懂坐标含义？不能就是残图，必须补全。

⛔⛔ **防标注遮挡（硬性，多点/轨迹/3D 图必守——"一堆文字糊成一团"是最常见的丑）：** 只要一张图上有 ≥2 个文字标注（点名/事件名/坐标注记等），就必须保证**标注之间、标注与数据点之间不重叠**：
- **2D 图**：用 `adjustText`（`from adjustText import adjust_text`，环境已装）自动排开，或手动给每个 `annotate` 设**不同方向的 `xytext` 偏移 + 带 `arrowprops` 引线**指回目标点。禁止把多个 `ax.text` 堆在同一坐标附近不管重叠。
- **3D 图（`adjustText` 对 3D 无效，必须手动）**：多个点挤在视觉中心时（正是本反馈的翻车——"M1初始/FY1初始/遮蔽/爆炸"糊成一团），**不要在每个点旁硬塞长文字**。改用以下任一：① 点旁只放**短代号**（`M1`/`F1`/`E`），代号与全称的对照放进**图例**；② 给标注加**明显 `xytext` 偏移 + 引线**，各标注朝不同方向拉开；③ 点极密时干脆**只标图例、点上不标字**。关键是"**看得清每个字属于哪个点、字不互相压**"。
- **出图后自检**：放大看标注区——有没有两段文字叠在一起、字压在数据点上看不清？有就按上面改，别交付"糊成一团"的图。这条对 nature 风格和竞赛风格**一律适用**。

## Mandatory rcParams (apply at top of EVERY script)

```python
import matplotlib.pyplot as plt

plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['Arial', 'DejaVu Sans', 'Liberation Sans']
plt.rcParams['svg.fonttype'] = 'none'          # editable text in SVG/PDF
plt.rcParams['font.size'] = 16                 # 24 for large bar panels
plt.rcParams['axes.spines.right'] = False
plt.rcParams['axes.spines.top'] = False
plt.rcParams['axes.linewidth'] = 2.5           # 3 for big bars, 2 for compact
plt.rcParams['legend.frameon'] = False
```

### Integration with plot_utils.py

Try `setup_style(palette='nature')` first. If unavailable, use inline rcParams above as fallback:

```python
import os, sys, shutil
os.makedirs('_utils', exist_ok=True)
for src in ['plot_utils.py']:
    for search in ['skills/shared-scripts', '../skills/shared-scripts']:
        p = os.path.join(search, src)
        if os.path.isfile(p):
            shutil.copy2(p, f'_utils/{src}')
            break
sys.path.insert(0, '.')
try:
    from _utils.plot_utils import setup_style, save_fig, PALETTE
    setup_style(palette='nature')
except (ImportError, TypeError):
    # Fallback: apply Nature rcParams directly
    plt.rcParams['font.family'] = 'sans-serif'
    plt.rcParams['font.sans-serif'] = ['Arial', 'DejaVu Sans', 'Liberation Sans']
    plt.rcParams['svg.fonttype'] = 'none'
    plt.rcParams['font.size'] = 16
    plt.rcParams['axes.spines.right'] = False
    plt.rcParams['axes.spines.top'] = False
    plt.rcParams['axes.linewidth'] = 2.5
    plt.rcParams['legend.frameon'] = False
```

## Nature Color Palette

```python
PALETTE_NATURE = {
    "blue_main":      "#0F4D92",   # deep blue — hero method
    "blue_secondary": "#3775BA",   # medium blue
    "green_1": "#DDF3DE",          # light positive
    "green_2": "#AADCA9",          # mid positive
    "green_3": "#8BCF8B",          # strong positive
    "red_1":   "#F6CFCB",          # light baseline
    "red_2":   "#E9A6A1",          # mid baseline
    "red_strong": "#B64342",       # strong baseline/negative
    "neutral_light": "#CFCECE",
    "neutral_mid":   "#767676",
    "neutral_dark":  "#4D4D4D",
    "neutral_black": "#272727",
    "gold":   "#FFD700",
    "teal":   "#42949E",
    "violet": "#9A4D8E",
}

# For unified-family figures (NMI-style dense pages)
PALETTE_NMI_PASTEL = {
    "baseline_dark": "#484878",
    "baseline_mid":  "#7884B4",
    "baseline_soft": "#B4C0E4",
    "ours_tiny":  "#E4E4F0",
    "ours_base":  "#E4CCD8",
    "ours_large": "#F0C0CC",
    "delta_up":   "#2E9E44",
    "delta_down": "#E53935",
}
```

Semantic rules:
- Blue = proposed/hero method
- Green = positive variants/improvements
- Red/pink = baselines/contrast
- Neutral grays = reference/background
- Use NMI pastel when comparing method families on dense pages

## Default Operating Stance

1. **Classify** the figure into one of 5 Nature page archetypes (see below)
2. **Hero panel** concept: one dominant panel + subordinate evidence panels
3. **Direct labels** over legends when categories are spatially fixed
4. **White background** for plots; black only for microscopy/imaging plates
5. **One restrained palette** per figure: neutral + signal + accent families
6. **Panel labels**: small bold lowercase (a, b, c) near top-left edge

## 5 Nature Page Archetypes

| Archetype | Layout | When to use |
|-----------|--------|-------------|
| Schematic-led composite | Wide story panel + smaller quant panels below | Method explanation + validation |
| Dark image plate | Black tiles with fluorescent channels | Microscopy, imaging, volume rendering |
| Clinical triptych | Top longitudinal, middle forest, bottom summary | Clinical/longitudinal studies |
| Dense categorical | Grid of equal panels, unified palette | Multi-metric comparisons |
| Asymmetric hero | One dominant panel spanning grid cells + small supports | Single key result + context |

## Layout Rules

- Hero panel gets visual hierarchy; support panels validate, not compete
- Panel labels: `ax.set_title('a', loc='left', pad=3, fontsize=14, fontweight='bold')`
- Tight gutters; increase spacing when dark/light modalities touch
- Prefer shared legend strip above a row over per-panel legends
- Dynamic y-axis: tighten to data range, never fixed 0–100 for narrow bands
- figsize guidance: journal-width composite (7.0–7.4, 5.5–7.8); bar panels (28–45, 6–12)

## Export Policy

**根据工作流模式选择输出格式（查看 CLAUDE.md 末尾的格式指令）：**

```python
import os
os.makedirs('./figures/', exist_ok=True)
fig.tight_layout(pad=0.5)

# 默认（LaTeX 模式）— 只输出 PDF（矢量、给 \includegraphics 用）
save_fig(fig, './figures/name.pdf')

# Word 模式（CLAUDE.md 含「⛔ 输出格式：仅 PNG」时）— 只输出 PNG（350 DPI）
# save_fig(fig, './figures/name.png')
```

- **LaTeX 模式：只输出 PDF**（不要同时存 PNG，避免冗余）
- **Word 模式：只输出 PNG**（DPI 350 防中文糊；不要存 PDF，Word 不能嵌 PDF）
- `save_fig()` 自动加 `bbox_inches='tight'` 并 `plt.close(fig)`，无需手写
- 检查 CLAUDE.md 末尾决定用哪种格式

## Workflow

### Step 1: Read data + classify figure type

Read PAPER_PLAN.md and data files. For each figure, classify into archetype and choose palette.

### Step 2: Read references + Generate scripts

**⛔ 必须在写任何绑图脚本之前，先读取以下参考文件：**

```bash
# 必读：配色方案和 helper 函数
cat _references/api.md

# 必读：根据图表类型选择对应教程
cat _references/tutorials.md

# 按需读取（多面板/复杂布局时）
cat _references/common-patterns.md

# 按需读取（需要了解 Nature 真实页面风格时）
cat _references/nature-2026-observations.md

# 按需读取（雷达图/3D/特殊图表时）
cat _references/chart-types.md
```

One script per figure. Each starts with Nature rcParams setup (`setup_style(palette='nature')` or inline rcParams). Follow the patterns from `_references/tutorials.md` as starting point.

### Step 3: Execute and validate

Run each script. Verify PDF output exists in `figures/`. Check:
- No `plt.title()` (captions in LaTeX only)
- Font ≥ 9pt final size
- Grayscale-distinguishable
- Panel labels present for multi-panel figures
- Colors from Nature palette, not matplotlib defaults
- ⛔ **Completeness (anti-broken图)**: y-axis has numeric ticks (NOT empty); both `set_xlabel` & `set_ylabel` present with units; if x-ticks are hidden then data is directly labeled; every `fill_between` has an accompanying `plot` line; `set_frame_on(False)` only on heatmaps; no subplot is a bare colored rectangle. **Open each PNG/PDF and confirm it is not just floating color blocks — if it is, fix and re-run before continuing.**

### Step 3.5: 数据图视觉质检（可选，默认关 · 仅当用户在高级选项开启时才跑）

⛔ **这一步默认不执行**。只有工作区 CLAUDE.md 含 `MH_DATA_FIG_VISION=1` 标记（用户在前端「高级选项」开启了「数据图视觉质检」）时才跑。它会对每张数据图调 vision 模型看图，检查坐标轴标签截断 / 图例压数据 / 刻度重叠等**肉眼硬伤**（Step 3 的静态检查抓不到这些渲染层问题）。**会消耗额度**（每张图每轮都调一次 vision），所以默认关。

先跑下面这段**检测脚本**，它会对每张数据图调 vision 并把结果记进独立账本 `_tmp/datafig_vision_*.txt`：

```bash
# ⛔ 门 1：默认关。CLAUDE.md 无 MH_DATA_FIG_VISION=1 标记就整段跳过（一个字不打，静默）
if ! grep -q 'MH_DATA_FIG_VISION=1' CLAUDE.md 2>/dev/null; then
  :  # 用户没开数据图视觉质检 → 跳过（默认行为，省额度）
# ⛔ 门 2：快速模式让位。省额度优先，即使开了数据图 vision 也跳过
elif grep -q 'MH_FAST_MODE=1' CLAUDE.md 2>/dev/null; then
  echo "⚡ 快速模式：跳过数据图视觉质检（省额度）"
else
  mkdir -p _tmp
  PYTHON=""; for _c in "$MH_PYTHON" python python3; do [ -z "$_c" ] && continue; if $_c -c "import sys" >/dev/null 2>&1; then PYTHON="$_c"; break; fi; done; [ -z "$PYTHON" ] && PYTHON=python
  # 定位数据图 vision 脚本：_utils/ 优先，兜底 $MH_TOOLS_DIR，再兜底 tools/
  DFV=""
  for _p in "_utils/data_fig_vision_check.py" "$MH_TOOLS_DIR/data_fig_vision_check.py" "tools/data_fig_vision_check.py"; do
    [ -n "$_p" ] && [ -f "$_p" ] && { DFV="$_p"; break; }
  done
  # ⛔ 收集数据图：靠【产物来源】判定，不靠前缀猜（前缀既会误伤真数据图 fig_error_dist，
  #    又会误收流程图 → 用数据图 PROMPT 检流程图/插画会得到牛头不对马嘴的反馈、误导修图）。
  #    数据图 = matplotlib gen_fig 脚本产的；流程/架构图有同名 .drawio（归 paper-figure-drawio 的
  #    vision，已单独质检，本步不重复检）；TikZ 有同名 .tex 含 tikzpicture；GPT Image 插画是
  #    fig_scene*/fig_gptimg*（AI 生成的场景图，非数据图）。判据：
  #      正向铁证：存在同名 gen_fig 脚本（规范 one gen_fig script per figure）→ 一定是数据图
  #      负向兜底：无 .drawio、无 tikz .tex、非 GPT 前缀 → 可能是「一脚本产多图」的数据图，也检
  DF_LIST=""
  for pdf in figures/fig_*.pdf; do
    [ -f "$pdf" ] || continue
    bn=$(basename "$pdf" .pdf)
    # 已判过 PASS 的不再调（复核循环省额度）
    grep -q "^${bn} PASS" _tmp/datafig_vision_passed.txt 2>/dev/null && continue
    is_data=0
    if [ -f "figures/gen_${bn}.py" ]; then
      is_data=1                                   # 正向：有同名 gen_fig 脚本 = 铁定数据图
    else
      # 兜底：排除 drawio 流程图 / TikZ / GPT Image 插画，其余当数据图（覆盖一脚本多图）
      _skip=0
      [ -f "figures/${bn}.drawio" ] && _skip=1
      [ -f "figures/${bn}.tex" ] && grep -q '\\begin{tikzpicture}' "figures/${bn}.tex" 2>/dev/null && _skip=1
      case "$bn" in fig_scene*|fig_gptimg*) _skip=1 ;; esac
      [ "$_skip" = "0" ] && is_data=1
    fi
    [ "$is_data" = "1" ] && DF_LIST="$DF_LIST $pdf"
  done
  if [ -z "$DF_LIST" ]; then
    echo "ℹ 数据图视觉质检：无待检数据图（或都已 PASS）"
  elif [ -z "$DFV" ]; then
    echo "🟥 开了数据图视觉质检但找不到 data_fig_vision_check.py（_utils/ 与 tools/ 均无）——本轮跳过，不阻断"
    for pdf in $DF_LIST; do echo "$(basename "$pdf" .pdf) (找不到 data_fig_vision_check.py)" >> _tmp/datafig_vision_skipped.txt; done
  else
    for pdf in $DF_LIST; do
      bn=$(basename "$pdf" .pdf)
      echo "=== 数据图视觉质检: $bn ==="
      PNG_OK=0
      # PyMuPDF(fitz) 优先：纯 wheel、不依赖 poppler，打包 runtime 必有
      $PYTHON -c "
import fitz
d=fitz.open('$pdf'); d[0].get_pixmap(matrix=fitz.Matrix(200/72,200/72)).save('_tmp/${bn}_dfv.png')
" 2>/dev/null && [ -f "_tmp/${bn}_dfv.png" ] && PNG_OK=1
      if [ "$PNG_OK" = "0" ] && command -v pdftoppm >/dev/null 2>&1; then
        pdftoppm -png -r 200 -singlefile "$pdf" "_tmp/${bn}_dfv" && PNG_OK=1
      fi
      if [ "$PNG_OK" = "0" ] && $PYTHON -c "from pdf2image import convert_from_path" 2>/dev/null; then
        $PYTHON -c "
from pdf2image import convert_from_path
convert_from_path('$pdf', dpi=200, first_page=1, last_page=1)[0].save('_tmp/${bn}_dfv.png','PNG')
" 2>/dev/null && [ -f "_tmp/${bn}_dfv.png" ] && PNG_OK=1
      fi
      [ "$PNG_OK" = "0" ] && { echo "🟥 $bn: PDF→PNG 均失败，本图未审（不阻断）"; echo "$bn (PDF→PNG 转换失败)" >> _tmp/datafig_vision_skipped.txt; continue; }
      DVOUT=$($PYTHON "$DFV" "_tmp/${bn}_dfv.png" 2>&1); DVEXIT=$?
      echo "$DVOUT"
      if [ "$DVEXIT" -eq 0 ]; then
        echo "✅ $bn 视觉通过"; echo "$bn PASS" >> _tmp/datafig_vision_passed.txt
      elif [ "$DVEXIT" -eq 2 ]; then
        echo "⚠ vision 不可用，跳过 $bn（不阻断）"; echo "$bn (Vision API 不可用/调用失败)" >> _tmp/datafig_vision_skipped.txt
      else
        # DVEXIT=1：有硬伤 → 记 pending，交给上面散文里的修复循环（AI 改脚本重跑后重跑本检测块复核）
        echo "⛔ $bn 有视觉硬伤（见上），按修复循环改 gen_fig 脚本重跑"
        echo "$bn" >> _tmp/datafig_vision_pending.txt
      fi
      rm -f "_tmp/${bn}_dfv.png"   # 临时 PNG 只喂 vision 用完即弃，检完即删避免 _tmp/ 堆积
    done
    # 汇总（供 AI 判断还剩几张要修）：pending.txt 跨轮累积，需剔除已 PASS 的图才是真待修数
    _pend=0
    if [ -f _tmp/datafig_vision_pending.txt ]; then
      for _b in $(sort -u _tmp/datafig_vision_pending.txt); do
        grep -q "^${_b} PASS" _tmp/datafig_vision_passed.txt 2>/dev/null || _pend=$((_pend+1))
      done
    fi
    echo "=== 数据图视觉质检小结：真待修 $_pend 张（已 PASS 的不计；passed/skipped 见 _tmp/datafig_vision_*.txt）==="
    echo "   （待修的图改完 gen_fig 脚本、重跑出图后，重新执行本检测块复核；最多 3 轮，之后警告不阻断）"
  fi
fi
```

**⛔ 修复循环（AI 执行，最多 3 轮，不阻断出稿）**：
上面脚本若打印出某张图的 `ISSUE ...`，你必须逐张修复——数据图的修复是**改 `gen_fig_xxx.py` 的绘图代码**（不是改 LaTeX）：
1. 用 Read 读 vision 反馈里点名的那张图对应的 `figures/gen_fig_xxx.py`
2. 按反馈用 Edit 改：标签被截断 → 调 `figsize`/`fontsize`（`save_fig` 已带 `bbox_inches='tight'`）；图例压数据 → 改 `legend(loc=...)` 或 `bbox_to_anchor` 移到画布外；刻度重叠 → `plt.xticks(rotation=30, ha='right')` 或减少刻度数；子图挤压 → `fig.tight_layout()` 或调 `figsize`
3. 重跑该脚本：`$PYTHON figures/gen_fig_xxx.py`，确认新 PDF 生成
4. **重新执行上面的检测脚本复核**（它只对还没 PASS 的图再调 vision）
5. 每张图最多修 3 轮。3 轮后小结里「真待修」仍 > 0 → 这些图就是没修好的，**警告即可、不阻断**，直接继续 Step 4（用户会自己复核）

⛔ **绝不能因为数据图 vision 没修好就卡在这里不往下走**——这是可选增值检查，警告即可。API 不可用 / 转图失败等环境问题一律记 skipped 跳过，同样不阻断。

### Step 4: Generate latex_includes.tex

Include all figures with `[H]` float specifier and English captions.

### Step 5: ⛔ FIGURE_MANIFEST 对账（按规划数量逐张核对，必跑）

**PAPER_PLAN.md 里规划了几张数据图，本步骤就必须产出几张。** 防止 context 中途爆掉只画了 1-2 张就退出的死循环 bug。

```bash
echo "=== FIGURE_MANIFEST 对账 ==="
PLAN_FILE=""
for f in PAPER_PLAN.md PROBLEM_ANALYSIS.md TOPIC_PLAN.md; do
  [ -f "$f" ] && grep -q "<!-- BEGIN FIGURE_MANIFEST -->" "$f" && { PLAN_FILE="$f"; break; }
done
PASS=true
if [ -n "$PLAN_FILE" ]; then
    START=$(grep -n "<!-- BEGIN FIGURE_MANIFEST -->" "$PLAN_FILE" | head -1 | cut -d: -f1)
    END=$(grep -n "<!-- END FIGURE_MANIFEST -->" "$PLAN_FILE" | head -1 | cut -d: -f1)
    # ⛔ 只对账「数据图」章节: 按 manifest 的粗体章节标题归类(权威), 不靠文件名前缀。
    #    这样 fig_data_pipeline/fig_model_arch 这类「关键词在中间」的架构图不会被误纳入
    #    数据图对账(它们归 DrawIO 章节, 由 paper-figure-drawio 负责); TikZ 章节也跳过。
    EXPECTED=$(sed -n "${START},${END}p" "$PLAN_FILE" \
        | awk '
            /^[[:space:]]*\*\*/ {
                if ($0 ~ /数据图/ || tolower($0) ~ /matplotlib|gen_fig/) cap=1; else cap=0;
                next
            }
            cap && match($0, /^[[:space:]]*-[[:space:]]+fig_[a-zA-Z0-9_]+/) {
                s=substr($0, RSTART, RLENGTH); sub(/^[[:space:]]*-[[:space:]]*/, "", s); print s
            }')
    miss=0
    for name in $EXPECTED; do
        if ! ls figures/${name}.pdf figures/${name}.png 2>/dev/null | head -1 | grep -q .; then
            echo "❌ 缺失数据图: $name"
            miss=$((miss + 1))
        fi
    done
    if [ "$miss" -gt 0 ]; then
        echo "⛔ FIGURE_MANIFEST 对账失败: 缺 $miss 张数据图，必须全部画出来再结束本步骤"
        PASS=false
    else
        echo "✅ 数据图全部产出"
    fi
else
    echo "(规划文档无 FIGURE_MANIFEST, 跳过对账)"
fi
[ "$PASS" != true ] && echo "⛔ 验证未通过 — 必须补齐缺失图表后再结束"
```

## STEP_MANIFEST 产出声明

本步骤完成后，必须调用 `engine.step_manifest.write_manifest`（或经 bridge/common 等价入口）在工作区根目录写入 `STEP_MANIFEST.json`，至少包含：stepName / backend（含版本）/ config / inputFiles / outputFiles（含 SHA-256）/ commands / dependencies。质量门禁 `step_manifest` 将校验其存在性与完整性；缺失或无效将导致本步骤无法通过（fail）。

建议额外记录：每张图的数据源、生成脚本、colormap、参数。图表溯源门禁 figure_provenance 要求图有来源证据。

## Key Rules

- ⛔ Never use `svg.fonttype = 'path'` — breaks text editability
- ⛔ No `plt.title()` — captions belong in LaTeX
- ⛔ No matplotlib default colors — always use Nature palette
- ⛔ No grid lines by default — sparse y-ticks guide the eye
- Active voice in axis labels; concise legend entries
- For ablation: single color with varying alpha (0.2–1.0)
- Error bars: `elinewidth=2, capthick=2, capsize=10`
- Heatmap text contrast: white on dark cells, black on light cells

## Related Files

| File | Open when |
|------|-----------|
| [references/api.md](references/api.md) | Palette constants, helper function signatures, validation rules |
| [references/design-theory.md](references/design-theory.md) | Typography, color theory, layout rationale |
| [references/chart-types.md](references/chart-types.md) | Radar, 3D sphere, fill_between, scatter patterns |
| [references/common-patterns.md](references/common-patterns.md) | Ultra-wide panels, legend-only axes, print-safe bars |
| [references/nature-2026-observations.md](references/nature-2026-observations.md) | Real Nature page archetypes from 2026 issues |
| [references/tutorials.md](references/tutorials.md) | End-to-end walkthroughs: bars, trends, heatmaps |
| `_utils/plot_utils.py` | Shared plotting infrastructure |
