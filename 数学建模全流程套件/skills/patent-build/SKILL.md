---
name: patent-build
description: >
  读取 patent-draft 产出的 专利交底书/交底书草稿.md 与自主设计的 fig_*.html，调用
  html_figure_render.py 用 Electron 把系统框图/流程图截成 PNG（含几何自检自修复），
  再导出 专利交底书/交底书.docx。是"一句话生成专利交底书"工作流的第二步（成品阶段）。
user-invocable: false
allowed-tools: >
  Bash, Read, Write, Edit, Glob, Grep
metadata:
  short-description: 截图出图并导出专利交底书 Word
  stage: build
---

# 专利技术交底书 · 成品阶段（patent-build）

上一步 `patent-draft` 已在 `专利交底书/交底书草稿.md` 写好交底书，并**自主设计好两张自包含 HTML 图**（`专利交底书/fig_arch.html` 系统框图 + `专利交底书/fig_flow.html` 流程图），草稿正文用 `<!-- ![...](figures/fig_arch.png) -->` / `<!-- ![...](figures/fig_flow.png) -->` 注释占位引用（PNG 此刻尚未生成）；平台检查点也已让用户确认。**本步骤把这两张 HTML 用 Electron 截成 PNG 并导出 Word**。

成品脚本目录通过环境变量 `$PATENT_SCRIPT_DIR` 注入（平台已把 `html_figure_render.py`、`md_to_docx.py`、`mermaid_render.py`、`math_render.py` 复制到工作区并解密，同目录）；Electron 截图后端 `screenshot_capture.py` 已复制到脚本目录的上级 `_utils/`，其运行时路径经 `MH_ELECTRON_*` 环境变量注入，`html_figure_render.py` 会自动定位，无需手动指定。

⛔ **本机用 `python` 不用 `python3`**（`python3` 触发 Microsoft Store 存根、exit 49）。

## 截图出图 + 几何自检自修复循环

⛔ **先做几何自检、按报告改 HTML 修好，再正式出图导出**。这样 Word 里的图不会文字被裁/越界/重叠。

### 第 1 步：逐张几何自检（不出图，只测量）

对 `专利交底书/` 下每张 `fig_*.html` 跑几何自检（含公式的图加 `--render-math`）。截图后端在脚本目录上级 `_utils/`：

```bash
CAPTURE=""
for f in "$PATENT_SCRIPT_DIR/../screenshot_capture.py" _utils/screenshot_capture.py tools/screenshot_capture.py; do
  [ -f "$f" ] && { CAPTURE="$f"; break; }
done
echo "截图后端 CAPTURE=${CAPTURE:-（未找到，将跳过自检，出图时降级）}"

for hf in 专利交底书/fig_*.html; do
  [ -f "$hf" ] || continue
  echo "=== 几何自检: $hf ==="
  [ -n "$CAPTURE" ] && python "$CAPTURE" --geom-check "$hf"   # 含公式的图末尾加 --render-math
done
# 退出码：0=干净 1=有几何问题（必修） 2=无法检查（Electron 不可用，跳过不阻塞）
```

**⛔ 若某张退出码 1（有溢出/越界/重叠），进入自修复循环（最多 3 轮，每轮"检→读→改→重检"）：**
1. **读报告**逐条定位问题元素（报告印了每块前 20 字，对得上 HTML 节点）。
2. **用 Read 读这张 `专利交底书/fig_xxx.html`**，按类型针对性改 CSS：
   - **文字溢出被裁** → 加大节点 `min-width`/`width`、缩短文字或移到副标题 `.sub`、调小 `font-size`、去掉多余 `overflow:hidden`+`white-space:nowrap`。
   - **越出画布边界 / 文字块重叠** → 十有八九误用了 `position:absolute` 定坐标。改回 **flex/grid 自动布局**，留白靠 `padding`/`gap`。
3. **改完重跑本步几何自检**，直到退出码 0，或 3 轮用完（用完仍有问题不阻塞，但汇报时提一句这张需人工看一眼）。

### 第 2 步：正式出图 + 导出 Word（一条命令）

自检干净后运行（批量截 PNG + 调 `md_to_docx.py` 导出）：

```bash
python "$PATENT_SCRIPT_DIR/html_figure_render.py" \
  -i 专利交底书/交底书草稿.md \
  -o 专利交底书/交底书.md \
  --docx 专利交底书/交底书.docx
# 图内含公式时末尾加 --render-math
```

行为说明：

- 脚本 glob `专利交底书/fig_*.html`，逐张用 Electron 先量内容真实宽高、再按贴合视口截成紧凑 PNG（无右侧白边），存到 `专利交底书/figures/`（`fig_arch.html → figures/fig_arch.png`，确定性 1:1）。随后把草稿 md 原样写成定稿 `交底书.md`（图引用注释已在草稿里），调用 `md_to_docx.py` 见 `figures/` 下 PNG 存在即按注释占位嵌成全幅居中插图 + "图 N" 题注。
- **公式走 Word 原生 OMML 矢量**（不转 PNG），由 `md_to_docx.py` 处理，本步不动公式链路。
- **降级不中断**：Electron 不可用或某张截图失败 → 该图缺失（Word 里显示"[图片缺失]"），其余照常；仍写 `.md` 并照常尝试导出，Word 导出失败退出码仍 0，stderr 给可手动执行的命令。
- 若 Electron 完全不可用（`screenshot_capture.py --check` 退出非 0），PNG 无法生成——不阻塞流程，但应在汇报里如实说明"系统框图/流程图未渲染成图片"。

## 输出

成功后在 `专利交底书/` 下生成：

- `交底书.md`（定稿，含图引用注释）
- `交底书.docx`（正式 Word，两张 HTML 图已嵌为 PNG，公式为 OMML 矢量）
- `figures/`（截出的 PNG：`fig_arch.png`、`fig_flow.png`）

## 完成校验

运行后检查 `专利交底书/交底书.docx` 存在且非空。读脚本 stderr：出现"✅ fig_*.html → ..."即该图截图成功、"已写入 Word: ..."即导出成功；若出现几何问题累计提示、"截图失败"或"md_to_docx 失败"，按提示修复重试或如实转达用户。完成后向用户汇报 Word 路径，并说明两张图（系统框图 / 流程图）是否成功截成图片嵌入。
