# 验收门禁管线（acceptance-gates）— 收口必跑，全绿才算过

> 本包 `_utils/` 内含 4 道独立可跑的机检闸，零依赖外部仓库。数值只搬运不重算（版面级）。

## 管线顺序

### 1. 确定性重生成
图脚本顶部 `rng = np.random.default_rng(42)`；重跑核对**数值零改动**（对比 all_results.json 或原图数字化值）。

### 2. 代码级闸 · figure_check.sh
```bash
bash _utils/figure_check.sh          # cwd=工作区根，扫 figures/gen_fig*.py
```
CRITICAL（进退出码、硬阻断）：硬编码色 >2 处、默认蓝 `#1f77b4`、RdYlGn/RdBu 红绿灯 cmap、
暗色主题、缺 `setup_style`/`PALETTE`、`plt.title/suptitle`、`.pdf` 泄漏、混合 constrained_layout。
WARNING（不阻断）：图型反模式（bar>3×、boxplot→raincloud、pie→donut）、原生画布相对档位过大
（缩放后字糊）、配方使用建议、全篇能力普查、规划↔脚本对账（`recipe_audit.py`）。
退出码 3 = 检查器不可用（降级，不误判返修）。

### 3. 图内文字预算 · figure_text_budget.py
```bash
python _utils/figure_text_budget.py figures          # 静态 AST 扫出图脚本
python _utils/figure_text_budget.py --selftest        # 改判据后先跑，全过才算对
```
判据：`ax.text/annotate/fig.text/bar_label` 只准数值+单位/短锚点（≤45 显示宽/≤3 行/≤12 汉字），
拦结论词句（因此/表明/始终…）与箭头；轴标/标题/图例 label ≤36 显示宽、禁句读。解释性文字移 caption。

### 4. 渲染级 PDF 闸 · figure_pdf_quality_check.py
```bash
python _utils/figure_pdf_quality_check.py figures --paper paper
```
逐图 PDF：字体嵌入（pdffonts）、**最终打印字号**（按真实 `\includegraphics` 宽 + `\textwidth` 反推，
下限 **8pt**）、文字块重叠（≥35% 小框）、文字/背景**对比度 ≥4.5:1**（像素合成）、文字越界、
大面积空白带（>25% 页高）、PDF-vs-PNG 偏色告警、多页处理、`gates_override.json` 逐图阈值豁免。
exit 1 on fail。

### 5. 宿主视觉全页复审（机检抓不到的只能看图）
montage 拼图 + 关键页单独渲染，逐页看：标题互碰、图例丢手柄、面板挤压、灰度打印下浅色头偏弱。
**图型改动后同步正文措辞**（"柱状图的形态"→"得分点阵的对比"）。

## 编译侧配套（LaTeX 工程）
- `xelatex ×2` → `grep -c "^!" main.log` = 0；fitz 扫 `\uffff` notdef = 0。
- fitz 的 warning 会污染 stdout，机检解析前先隔离 stderr。

## gates_override 豁免
复制 `_utils/gates_override.example.json` 为 `gates_override.json`，按图名放宽个别阈值
（如某示意图确需小字）。豁免是**例外**，须留理由，不得用于绕过质感三件套或字号下限。

## 完成声明四要素
验证证据（四道闸退出码 + 视觉复审截图）/ 边界检查（版面级、未重算）/ 已知限制（灰度浅色头）/
置信度。无证据＝未执行；TOOL_GAP 不伪造通过。
