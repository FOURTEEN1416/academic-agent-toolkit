---
name: paper-write-zh-docx
description: "Draft a Chinese academic paper as Markdown for Word (docx) export. Use when params.output_format == 'docx'. Mirrors paper-write-zh writing rules but produces paper/main.md only."
argument-hint: [topic]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Agent, WebSearch, WebFetch
---

# 中文论文写作（docx 模式）

为 Word 输出撰写中文学术论文：**$ARGUMENTS**

> 本 SKILL 是 `paper-write-zh` 的 docx 专用版本：保留全部写作哲学（Claims-Evidence、章节深度、引用纪律、上游验证），但产物只有 **`paper/main.md`** 一个文件。后续 `docx-export` 步骤会用 docx-cn-engine 把它转成 .docx。
>
> ⛔ **绝不产 `paper/main.tex` / `paper/sections/*.tex` / `.cls` / `.sty`。绝不执行 XeLaTeX 编译。**

## Constants

- **PAPER_TYPE** — `bachelor`/`master`/`journal`，默认 `journal`
- **MAX_PAGES** — bachelor=25, master=55, journal=15。正文页数 ≥ MAX_PAGES（按 800 字/页估算）
- **CUSTOM_REQUIREMENTS** — 最高优先级
- **REVIEWER_SCRIPT** — 外部评审脚本 `reviewer_client.py`

## Inputs

1. **PAPER_PLAN.md** — 大纲与数据分析摘要
2. **NARRATIVE_REPORT.md** — 研究叙述
3. **figures/** — `.png`/`.pdf` + `latex_includes.tex`（仅作 caption 与图编号参考，不直接嵌入）
4. **user_data/** — 用户上传材料（数据文件、参考文献等）
5. **RESULTS.md / experiment_results.md / figures/all_results.json** — 数值证据来源

如果 `user_data/` 含 CSV/JSON，写实验章节前必须用 pandas 读取精确数值。

## Load shared rules

```bash
cat _utils/writing_rules.md 2>/dev/null || cat skills/shared-scripts/writing_rules.md
```

> shared rules 中关于 LaTeX 的部分（`\begin{figure}`、`\input`、`gbt7714`）在 docx 模式下不适用，但 **写作哲学（claims-evidence、interleaving、章节深度、扩写策略、de-AI polish）全部适用**。

## ⛔⛔⛔ 完成铁律（最高优先级）

**主产物**：`paper/main.md`（**单文件**，UTF-8，含完整论文，≥ 5KB）

**禁止产**：
- `paper/main.tex`、`paper/sections/*.tex`
- `paper/references.bib`（参考文献以 markdown 文本形式直接写入 main.md 的「## 参考文献」章节）
- 任何 `.cls` / `.sty` / `.bbl` / `.aux`
- 任何 LaTeX 命令（`\begin`、`\input`、`\cite`、`\label`、`\ref`、`\section`、`\includegraphics`...）

**结束前必跑产出验证**：
```bash
echo "=== 产出验证（必须全部 ✅）==="
PASS=true

[ -f paper/main.md ] && SZ=$(wc -c < paper/main.md) || SZ=0
if [ "$SZ" -ge 5120 ]; then
    echo "✅ paper/main.md ($SZ bytes)"
else
    echo "❌ paper/main.md 缺失或过小 ($SZ bytes，需 ≥ 5120)"; PASS=false
fi

# 字数估算
chars=$(wc -m < paper/main.md 2>/dev/null || echo 0)
est_pages=$((chars / 800))
target_pages="${MAX_PAGES:-15}"
echo "正文字符数: $chars，估算页数: ~$est_pages，目标: ≥ $target_pages"
if [ "$est_pages" -lt "$((target_pages * 80 / 100))" ]; then
    echo "⚠ 页数低于目标 80%，建议扩充最薄章节"
fi

# 禁止残留 LaTeX 命令
if grep -qE '\\(begin|end|input|cite|ref|label|includegraphics|section|chapter|subsection)\{' paper/main.md 2>/dev/null; then
    echo "❌ paper/main.md 残留 LaTeX 命令，必须改成 markdown"
    grep -nE '\\(begin|end|input|cite|ref|label|includegraphics|section|chapter|subsection)\{' paper/main.md | head -5
    PASS=false
fi

# 禁止生成 .tex
if ls paper/*.tex paper/sections/*.tex 2>/dev/null | head -1 | grep -q .; then
    echo "❌ 检测到 .tex 文件，docx 模式禁止产 LaTeX："
    ls paper/*.tex paper/sections/*.tex 2>/dev/null
    PASS=false
fi

[ "$PASS" != true ] && echo "⛔ 产出验证失败 — 必须补全后重新跑验证，不要结束本步骤"
```

**如果验证失败，继续修正而不是退出。**

## docx-cn-engine 的 markdown 约定（必须遵守）

后续 `docx-export` 步骤用 `tools/docx-cn-engine/md_to_docx.js` 把 main.md 转 .docx。引擎对以下 markdown 语法有特殊处理，**必须按规范写**：

### 1. 标题层级
- `# 论文标题` — 论文封面标题（**全文唯一**，居中、加粗、最大字号）
- `## 章节名` — 一级章节（如「1 引言」、「2 方法」）
- `### 子章节名` — 二级章节
- `#### 三级` — 三级章节

### 2. 摘要 / Abstract（引擎自动识别居中样式）
```markdown
## 摘要

[500-700 字摘要正文，研究背景 → 现有方法不足 → 本文方法 → 数据来源 → 关键数值结果 → 应用价值]

**关键词**：关键词1；关键词2；关键词3；关键词4；关键词5

## Abstract

[350-500 字英文翻译，覆盖相同结构与全部数值结果]

**Keywords**: keyword1; keyword2; keyword3; keyword4; keyword5
```

⛔ 摘要要尽量填满一页但留 3-4 行底部空白，宁可短一点也不要溢出到第二页。

### 3. 公式
- 行内公式：`$x^2 + y^2 = r^2$`
- 独立公式：`$$E = mc^2$$`
- 编号公式：在公式后另起一行写 `(1)`、`(2)`，引擎会自动右对齐编号

```markdown
模型可表示为：

$$y_i = \beta_0 + \beta_1 x_i + \varepsilon_i \quad (1)$$

其中 $\beta_0$、$\beta_1$ 为待估参数。
```

⛔ **禁止 `\begin{equation}`、`\[...\]`、`\begin{align}`** —— 引擎不处理这些 LaTeX 环境。

### 4. 图片嵌入
```markdown
![图 1：模型架构示意图](figures/fig_arch.png)
```
- alt 文字会变成图注（居中、加粗、宋体）
- 图片路径相对工作区根目录
- 引擎会自动按比例缩放图片
- 优先用 `.png`，PDF 也支持但 Word 显示效果不如 PNG
- **⛔ 图注（alt 文字）只写简短标签（主体 ≤20 字，不含"图 N："前缀）**：只写这张图是什么的名词短语；判据、参数、坐标含义、结论移到正文图解读里，别塞进图注（Word 图注居中加粗，太长挤成多行很难看）。反例 `![图 3：覆盖半径几何示意：站点为圆心、R=3km 覆盖圆、区域出车距离与响应时间判据](...)` → 正例 `![图 3：站点覆盖半径几何示意](...)`。详见 `_utils/writing_rules.md` 图注长度总则；最终验证会扫图注长度，超限判违规。

⛔ **必须用真实存在的图片文件**：
```bash
for pdf in figures/*.png figures/*.pdf; do
    [ -f "$pdf" ] || continue
    bn=$(basename "$pdf")
    grep -q "$bn" paper/main.md && echo "✅ $bn 已嵌入" || echo "⚠ $bn 未嵌入"
done
```

如果 `figures/` 仅含 `latex_includes.tex` 占位（纯文字论文场景），跳过图嵌入步骤。

### 5. 表格（三线表）
```markdown
| 方法 | 准确率 | F1 | 训练时间(s) |
|------|--------|----|------------|
| Baseline | 0.823 | 0.811 | 124 |
| Ours | **0.917** | **0.905** | 132 |
```

引擎会自动渲染成三线表（顶/底粗线，header 下细线）。表格上方一行可以加表注：
```markdown
**表 1：主要方法对比结果**

| ... |
```

⛔ **禁止 `\begin{table}` / `\input{figures/TABLE_x.tex}`**。如果 `figures/TABLE_*.md` 已存在，可以直接 `cat figures/TABLE_x.md` 把内容贴进 main.md 对应位置。

### 6. 参考文献
```markdown
## 参考文献

[1] LeSage J P, Pace R K. Introduction to Spatial Econometrics[M]. CRC Press, 2009.
[2] 张三, 李四. 数字经济发展水平测度研究[J]. 经济研究, 2023, 58(5): 12-25.
[3] ...
```

引擎检测到 `## 参考文献` 或 `## References` 标题后，下面以 `[N]` 开头的行会自动套 hanging indent + 较小字号样式。

⛔ **正文引用用 `[1]`、`[1, 2]`、`[1-3]` 而不是 `\cite{key}`。** 写作时维护一个 citation key → 编号的映射，最后统一编号。

## Workflow

### Step 0: 上游验证 + 续写检查

```bash
echo "=== 上游输出完整性检查 ==="
UPSTREAM_OK=true

# 1. 核心文件
for f in PAPER_PLAN.md RESULTS.md; do
    if [ -f "$f" ]; then
        sz=$(wc -c < "$f")
        echo "✅ $f ($sz 字符)"
        [ "$sz" -lt 500 ] && { echo "  ⚠ 文件过小，内容可能不完整"; UPSTREAM_OK=false; }
    else
        echo "⚠ $f 不存在（将使用最小大纲兜底）"
    fi
done

# 2. 数值数据
[ -f figures/all_results.json ] && echo "✅ figures/all_results.json" || echo "⚠ 无 all_results.json，数值可能不准确"
[ -f experiment_results.md ] && echo "✅ experiment_results.md" || echo "  （无 experiment_results.md，将依赖 RESULTS.md）"

# 3. 图表
PNG_COUNT=$(ls figures/*.png 2>/dev/null | wc -l)
PDF_COUNT=$(ls figures/*.pdf 2>/dev/null | wc -l)
echo "可嵌入图: PNG $PNG_COUNT 张, PDF $PDF_COUNT 张"

# 4. 续写检查
if [ -f paper/main.md ]; then
    sz=$(wc -c < paper/main.md)
    echo "已存在 paper/main.md ($sz 字符) — 进入续写模式"
    cp paper/main.md "paper/main-backup-$(date +%s).md.bak"
fi

echo "=== 上游检查完成 ==="
$UPSTREAM_OK || echo "⚠ 部分上游文件不完整，继续执行但结果可能欠佳"
```

**⛔ 数值来源规则（全文遵守）：**
所有论文中的数值（精度、RMSE、R²、p-value、系数、训练时间等）必须来自 `figures/all_results.json` 或 `RESULTS.md`。

**⛔ 禁止 `cat figures/*_results.json`。** 这些结果文件可能含全精度时序数组（可达数十 MB / 数十万行），整读会撑爆上下文——本地大模型直接失败、经中转的 GPT 因协议翻译超长反复 `api_retry` 卡死。**论文正文只用标量数值（精度/RMSE/R²/p 值/系数/训练时间等），巨型数组是给图表用的、不进正文。** 写任何含数值的章节之前，用下面的 `summarize` 脚本拿 KB 级摘要（标量原样显示、精度零损失，只把大数组压成「长度+范围+前3样本」）：
```bash
[ -f RESULTS.md ] && cat RESULTS.md
python3 - <<'PY'
import json, os, glob
def summarize(v, depth=0):
    if isinstance(v, list):
        n=len(v); nums=[x for x in v if isinstance(x,(int,float))]
        if nums: return f'list[{n}] range=[{min(nums):.4g},{max(nums):.4g}] sample={v[:3]}'
        if v and isinstance(v[0], (list,dict)): return f'list[{n}] of {type(v[0]).__name__}, first_shape={len(v[0]) if hasattr(v[0],"__len__") else "?"}'
        return f'list[{n}] sample={str(v[:3])[:80]}'
    if isinstance(v, dict) and depth<2:
        return 'dict{'+', '.join(f'{k}: {summarize(x,depth+1)}' for k,x in list(v.items())[:6])+'}'
    return f'{type(v).__name__}={str(v)[:60]}'
for f in sorted(glob.glob('figures/*_results.json')):
    sz=os.path.getsize(f); d=json.load(open(f,encoding='utf-8'))
    print(f'\n=== {os.path.basename(f)} ({sz//1024}KB) ===')
    if isinstance(d, dict):
        for k,v in d.items(): print(f'  {k}: {summarize(v)}')
    else: print(f'  {summarize(d)}')
PY
```
论文要引的标量都在 `RESULTS.md` 和上面摘要的 range/sample 里；若某个标量摘要没显示全，用 `python3 -c "import json;d=json.load(open('figures/all_results.json'));print(d['键名'])"` 定点取那一个值，仍然不要整读。原样复制数字填入论文。**不要凭记忆估算、四舍五入或编造数值。**

**⛔ Claims-Evidence 对照（必须严格遵循规划）：**

写每个章节前重读 PAPER_PLAN.md 中的 claims-evidence 矩阵：
```bash
grep -A 100 'Claims-Evidence\|claim.*evidence\|claim-evidence\|观点.*证据' PAPER_PLAN.md 2>/dev/null | head -30
```

写作纪律：
- 论文中的每个论断必须对应到规划中的某一行
- 不要添加规划外的新论断（如有新发现，先更新 PAPER_PLAN.md）
- 不要跳过规划中的论断（即使是负面结果也要如实报告）
- 每个论断的数值证据必须与 `figures/all_results.json` 一致

如果某个规划中的论断在数据中找不到证据，诚实写"初步结果提示 X，更严谨的验证留待未来工作"，不要编造证据。

### Step 1: 图表清单

```bash
echo "=== 可用图片 ==="
ls -la figures/*.png figures/*.pdf 2>/dev/null

echo ""
echo "=== 可用表格（.md 优先，docx 模式不读 .tex） ==="
ls -la figures/TABLE_*.md 2>/dev/null

echo ""
echo "=== latex_includes.tex 中的图编号与 caption（仅作参考）==="
cat figures/latex_includes.tex 2>/dev/null
```

从输出中建立映射：图编号 → 文件名 → 目标章节。**只嵌入实际存在的图片** —— 不要为不存在的文件写图块。

### Step 1.5: 文献预检索（写正文之前必须完成）

⛔ 在写任何引用之前，必须先建立已验证的文献池。

```bash
PYTHON=""; for _c in "$MH_PYTHON" python python3; do [ -z "$_c" ] && continue; if $_c -c "import sys" >/dev/null 2>&1; then PYTHON="$_c"; break; fi; done; [ -z "$PYTHON" ] && PYTHON=python
mkdir -p _tmp

# 根据论文主题搜索真实论文
# 示例：
#   $PYTHON "$SCHOLAR_SCRIPT" bibtex "空间杜宾模型 数字经济" --max 5
#   $PYTHON "$SCHOLAR_SCRIPT" bibtex "算力基础设施 区域发展" --max 5
```

把搜索结果写到 `_tmp/_verified_refs.txt`：
```
[1] LeSage J P, Pace R K. Introduction to Spatial Econometrics[M]. CRC Press, 2009. | match: good
[2] 张三. 数字经济发展水平测度[J]. 经济研究, 2023, 58(5): 12-25. | match: good
```

**写正文时只能引用这个池子里的论文。** 找不到的论文用 WebSearch 在 Google Scholar / Semantic Scholar 上验证。

### Step 2: 撰写论文

写作顺序：方法/核心 → 实验 → 引言 → 相关工作 → 结论 → 摘要（最后写）。

**⛔ 跨章上下文 + 图数据绑定（防"两张皮"）：**
- 全文写在一个 `main.md` 里，也要保持前后连贯：**每写完一节，就往工作区根目录 `_writing_context.md` 追加 3-5 行要点卡**（核心论点／关键数字／新定义的符号术语／已讨论的图表），后续章节先回读它，承接前文结论、复用已定义术语（不重复定义）、保持同一指标数字全文一致。详见 `_utils/writing_rules.md` 的 `<chapter_context_card>`。
- **写每张图/表的分析前**，先按 `<figure_data_binding>`：从 FIGURE_MANIFEST/latex_includes 认清"这张图画的是什么量" → 去 `RESULTS.md`／`figures/all_results.json` 定位它对应的真实数值 → 分析里只用这些真值，**禁止凭图形状/位置猜数、禁止编造坐标**。

把所有内容直接写到 **`paper/main.md`** 一个文件。建议结构：

```markdown
# [论文标题]

## 摘要

[500-700 字]

**关键词**：...

## Abstract

[350-500 字]

**Keywords**: ...

## 1 引言

### 1.1 研究背景

[2-3 段，每段 3-5 句]

### 1.2 国内外研究现状

[按 2-3 个方向分类综述，每个方向 1-2 段]

### 1.3 研究内容与方法

[1 段]

### 1.4 论文结构

[1 段]

## 2 [理论基础 / 相关工作]

...

## 3 [方法 / 模型设计]

公式与模型公式化用 markdown 数学：

$$y = f(x; \theta) + \varepsilon \quad (1)$$

![图 1：方法整体框架](figures/fig_arch.png)

[≥ 5 行分析。图号必须点名"图 1"，但换着句式引出——句首带出「图 1 的框架中，X 模块承接上文提出的 Y……」／动词引导「观察图 1 可见……」／图作主语「图 1 给出了本文方法的整体框架，其中……」／先讲发现图号后置「X 模块承接上文提出的 Y（见图 1）……」。别每张图都用"如图 N 所示"或"图 N…"这一种开头。⛔ 相邻两张图的图后解读段不许都以「图 N…」起句，整节图号作主语打头的段落占比不超过一半]

## 4 实验

### 4.1 实验设置

### 4.2 主要结果

**表 1：主要方法对比**

| 方法 | 准确率 | F1 |
|------|--------|----|
| ... | ... | ... |

由表 1 可见，... [数值解读 + 对比 + 原因分析，≥ 2 段]

![图 2：消融实验](figures/fig_ablation.png)

[≥ 5 行分析。图 2 与上面图 1 的引用句式要换一种——例如括号旁注「去掉 X 模块后指标下降 4.2%（图 2），说明……」。相邻两图别用同一种开头]

### 4.3 消融实验

### 4.4 讨论

## 5 结论

[工作总结 + 不足 + 未来方向]

## 参考文献

[1] LeSage J P, Pace R K. Introduction to Spatial Econometrics[M]. CRC Press, 2009.
[2] ...
```

**⛔ 写作风格铁律：**
- **禁止用 markdown bullet/列表（`-`、`1.`）作为正文叙述。** 列举用「（1）...（2）...」行内编号或「首先...其次...」过渡词。bullet 仅用于「输入清单 / 评价指标定义 / 软件依赖」等枚举性内容。
- **每段至少 3-5 句话。**
- **连续段落不能以相同句式开头。**
- **✅ 图号必须显式引用，但句式要换着来。** 每张图都要点名"图 N"让读者对上号（硬规范，别为了避免套路就删图号）；但相邻两张图的引用句式必须不同，在括号旁注（首选）／句首带出／动词引导／图作主语／后置印证之间轮换。**要禁的是"图 N + 动词 + 一句空话"的单调重复开头，不是禁止引用图号。** ⛔ 图作主语开头（「图 N 的…」「图 N 展示了…」）可以用，但**相邻两段不许都这么起句、整节占比不超过一半**（docx 图片就地嵌入天然诱导每段「图 N…」打头，须刻意对抗）；其余图用"先讲发现、图号后置括注（见图 N）"或"由图 N 可见"的口吻。
- **每张图/表后面必须有 ≥ 5 行分析文字（数值解读 + 对比 + 结论），然后才能放下一张图。** 绝对禁止两张图连续出现中间没有分析段落。

每写完一个章节后检查字数：
```bash
chars=$(wc -m < paper/main.md)
echo "main.md 当前: $chars 字符（中文 ≈ 800/页）"
```

<exemplar_depth>
#### 章节深度参考

**本科毕业论文 (~25 页, 5 章)**:
- 1 引言 (5-6p): 研究背景 1-2 段 + 国内外研究现状按 2-3 方向分类 + 研究内容 + 论文结构
- 2 理论基础 (5-6p): 核心概念定义 + 相关理论 + 技术路线
- 3 方法/系统设计 (8-10p): 整体架构 + 各模块详细设计 + 关键算法/公式 + 实现细节
- 4 实验/测试 (6-8p): 实验环境 + 数据集 + 评价指标 + 主要结果 + 对比 + 分析
- 5 总结与展望 (2-3p): 工作总结 + 不足 + 未来方向

**硕士论文 — CS/AI (~80 页, 6 章)**:
- 1 绪论 (8-10p)
- 2 相关工作 (12-14p): 按子领域 3-4 类，每类 3-5 篇详细讨论
- 3 方法 (18-20p): 每个核心概念完整段落（定义→公式→直觉→与本工作的联系）
- 4 实现 (10-12p)
- 5 实验 (20-24p): 每个结果 2-3 段解读
- 6 总结 (4-6p)

**硕士论文 — 经管/统计 (~80 页)**:
- 1 绪论 (6-8p)
- 2 文献综述 (12-14p): 按 3-4 主题分组，每主题 5-8 篇
- 3 理论与方法 (10-16p)
- 4 数据与描述性分析 (10-16p)
- 5 核心分析 (20-24p): 每个结果 2-3 段解读
- 6 结论 (6p)

**期刊论文 (~15 页, 5-6 节)**:
- 引言 (1.5p): hook → gap → contribution → results preview
- 相关工作 (1-1.5p): 按类别合成，不是罗列
- 方法 (2-2.5p): 符号 → 公式化 → 算法
- 实验 (3-4p): 设置 → 主结果 → 消融 → 分析
- 结论 (0.5p)

| 类型 | 页数 | 字符数 | 文献数 |
|------|------|--------|--------|
| 本科 | 25-30 | 18000-25000 | ≥ 20 |
| 硕士 | 50-80 | 40000-65000 | ≥ 50 |
| 期刊 | 12-15 | 9000-13000 | ≥ 30 |
</exemplar_depth>

#### 每章最低图表/引用要求
- 引言：≥ 1 图（可选）+ ≥ 3 引用
- 相关工作：≥ 1 图/表（可选）+ ≥ 3 引用
- 方法：≥ 2 图 + ≥ 2 引用
- 实验：≥ 3 图/表 + ≥ 3 引用
- 结论：≥ 1 引用

**扩写策略**（实质内容，不是注水）：
- 公式无推导 → 加分步推导与物理意义
- 结果只写「如表所示」 → 加 2-3 段（数值含义 + 与预期对比 + 原因分析 + 与其他方法对比）
- 文献综述只罗列 → 加每篇方法摘要 + 与本工作的联系
- 算法只伪代码 → 加解释、复杂度分析、收敛性讨论

### Step 3: 引用整理与编号

写完正文后，统一整理引用：

```bash
# 1. 提取正文里所有 [N] 编号
grep -oE '\[[0-9]+(-[0-9]+)?(, *[0-9]+)*\]' paper/main.md | sort -u > _tmp/_cited_nums.txt
echo "正文出现的引用编号:"
cat _tmp/_cited_nums.txt

# 2. 检查参考文献条目数
ref_count=$(awk '/^## 参考文献|^## References/,0' paper/main.md | grep -cE '^\[[0-9]+\]')
echo "参考文献条目: $ref_count"
```

确保正文每个 `[N]` 都在「## 参考文献」里有对应条目，且编号连续无跳号。每个文献条目按 GB/T 7714 格式：

```
[1] 作者. 标题[J]. 期刊, 年份, 卷(期): 页码.   # 期刊
[2] 作者. 书名[M]. 出版地: 出版社, 年份: 页码. # 专著
[3] Author A, Author B. Title[C]//Conf. Year: pages. # 会议
[4] Author. Title[D]. 学校, 年份. # 学位论文
```

### Step 3.5: 用 scholar_fetch 验证文献（必跑）

⛔ **所有参考文献必须用 scholar_fetch.py 工具获取真实 BibTeX。禁止凭记忆编造。**

写正文时，用**描述性 citation key**便于后续搜索：`作者姓_年份_主题关键词`。
- ✅ `wang_2023_供应链韧性` / `wang_2023_supply_chain_resilience`
- ❌ `wang2023supply`（搜不到）
- 不确定作者/年份 → 用 `TODO__` 前缀：`TODO__数字经济空间溢出`

写完正文后逐个验证：

```bash
PYTHON=""; for _c in "$MH_PYTHON" python python3; do [ -z "$_c" ] && continue; if $_c -c "import sys" >/dev/null 2>&1; then PYTHON="$_c"; break; fi; done; [ -z "$PYTHON" ] && PYTHON=python
mkdir -p _tmp

# 把每个引用的描述性 key 列到 _tmp/_topics.txt（一行一个）
# 然后逐个搜索：
while IFS= read -r key; do
    query=$(echo "$key" | sed 's/^TODO__//; s/_/ /g')
    echo "--- 搜索: $key (query: $query) ---"
    $PYTHON "$SCHOLAR_SCRIPT" bibtex "$query" --max 3
    sleep 0.5
done < _tmp/_topics.txt
```

处理每个搜索结果：
1. 检查 `match_label`：`"good"` → 直接用。`"partial"` → 核对标题。`"low"` → 重新搜索或用 WebSearch。
2. 检查 `match_score`：< 0.3 说明可能搜错，不要盲目使用。
3. 把搜到的真实文献按 GB/T 7714 格式写入正文末尾的「## 参考文献」章节。
4. 文献条目顺序必须与正文 `[N]` **首次出现**顺序一致。

**兜底**：搜不到或 `match_label="low"`，用 WebSearch 在 Google Scholar / Semantic Scholar 网站手动核实标题+作者+年份后再加入。

⛔ 引用编号必须按正文出现顺序排列（[1] 先于 [2] 先于 [3]），不能跳号、不能回退。
⛔ 多引用合并：编号相邻 → `[1, 2, 3]`；编号不相邻或跨度大 → 分别写 `[1] [5]`。
⛔ 文献数量：本科 ≥ 20，硕士 ≥ 50，期刊 ≥ 30。**⛔ 真实性优先于数量**：以上是"真实检索到的目标量"，绝不允许为凑够数量编造条目。真实检索不足下限时，保留真实的、如实说明缺口（可在正文注明"受篇幅/领域所限"），禁止用编造条目填数——收尾核验会交叉核对检索留档，编造条目一律判失败。

### Step 4: 去 AI 化润色

参见 `_utils/writing_rules.md` 中的 `<de_ai_polish>`。重点：
- 删除 "this paper proposes / 本文提出" 类套话开头
- 用具体动词替换 "explore / investigate"
- 控制 "we / 我们" 出现频次（每段 ≤ 2 次）
- 中英文混排时英文术语前后留半角空格

### Step 5: 交叉评审

```bash
mkdir -p _tmp
cat << 'REVIEW_EOF' > _tmp/_review_prompt.txt
请评审这篇中文学术论文草稿。重点关注：
1. 逻辑流畅性和论证结构
2. 论点-证据对齐（每个论点是否有数据支撑？）
3. 写作清晰度和简洁性
4. 缺失内容或薄弱章节
5. 评分（1-10）和最需要改进的 3 个方面

## 论文正文：
REVIEW_EOF
cat paper/main.md >> _tmp/_review_prompt.txt
PYTHON=""; for _c in "$MH_PYTHON" python python3; do [ -z "$_c" ] && continue; if $_c -c "import sys" >/dev/null 2>&1; then PYTHON="$_c"; break; fi; done; [ -z "$PYTHON" ] && PYTHON=python
$PYTHON "$REVIEWER_SCRIPT" --prompt-file _tmp/_review_prompt.txt --thread-file _tmp/_reviewer_thread.json 2>&1 | tee _tmp/_cross_review.txt
```

如评审脚本不可用则跳过。

### Step 6: 最终验证

```bash
echo "=== 最终验证 ==="

# 1. 主产物
[ -f paper/main.md ] && SZ=$(wc -c < paper/main.md) || SZ=0
echo "paper/main.md: $SZ bytes"

# 2. 字符 / 估算页数
chars=$(wc -m < paper/main.md)
est_pages=$((chars / 800))
target=${MAX_PAGES:-15}
echo "字符: $chars, 估算页数: ~$est_pages, 目标: ≥ $target"

# 3. 章节数
sec_count=$(grep -cE '^## [^A-Za-z]*[0-9]+ |^## 摘要|^## Abstract|^## 参考文献|^## References' paper/main.md)
echo "顶级章节数: $sec_count"

# 4. 图嵌入检查（FATAL：figures/ 下每张图都必须在 paper/main.md 出现，无 MANIFEST 时也兜底）
echo "--- 图嵌入检查 ---"
missing_img=0
for img in figures/*.png figures/*.pdf; do
    [ -f "$img" ] || continue
    bn=$(basename "$img")
    if ! grep -q "$bn" paper/main.md; then
        # latex_includes.tex 占位文件不算缺失
        [ "$bn" = "latex_includes.tex" ] && continue
        echo "❌ 未嵌入: $bn — figures/ 已生成但 paper/main.md 未引用，必须补嵌入"
        missing_img=$((missing_img + 1))
    fi
done
echo "未嵌入图数量: $missing_img"
[ "$missing_img" -gt 0 ] && echo "⛔ 不允许结束：上述图必须在对应章节用 ![图N：caption](figures/xxx.png) 嵌入。"

# 5. 引用编号连续性
echo "--- 引用编号检查 ---"
max_cited=$(grep -oE '\[[0-9]+\]' paper/main.md | grep -v '^## ' | tr -d '[]' | sort -n | tail -1)
ref_lines=$(awk '/^## 参考文献|^## References/,0' paper/main.md | grep -cE '^\[[0-9]+\]')
echo "正文引用最大编号: ${max_cited:-0}, 参考文献条目: $ref_lines"
[ -n "$max_cited" ] && [ "$ref_lines" -lt "$max_cited" ] && echo "⛔ 参考文献条目数少于正文引用编号"

# 6. LaTeX 残留检查
if grep -qE '\\(begin|end|input|cite|ref|label|includegraphics|section|chapter)\{' paper/main.md; then
    echo "⛔ 检测到 LaTeX 残留命令："
    grep -nE '\\(begin|end|input|cite|ref|label|includegraphics|section|chapter)\{' paper/main.md | head -5
fi

# 7. .tex 残留检查
ls paper/*.tex paper/sections/*.tex 2>/dev/null | head -5 | grep -q . && echo "⛔ 检测到 .tex 文件，docx 模式禁止" || echo "✅ 无 .tex 残留"

# 8. ⛔ 图注超长检测（图注 alt 文字只写简短标签，判据/参数/结论移入正文；与竞赛 docx 流口径一致）
echo "--- 图注超长检测 ---"
python - paper/main.md << 'PYEOF'
import re, sys
LIMIT = 20  # 剥掉"图 N："前缀后的中文字上限（超 20 字判违规）
try:
    text = open(sys.argv[1], encoding='utf-8', errors='ignore').read()
except FileNotFoundError:
    sys.exit(0)
# 只查正文（截到附录/参考文献为止），与 writing_check.sh 7b3 口径一致
m = re.search(r'(?m)^##\s*(附录|参考文献|Appendix|References)', text)
body_text = text[:m.start()] if m else text
bad = []
for alt in re.findall(r'!\[([^\]]*)\]\([^)]*\)', body_text):
    body = re.sub(r'^\s*[图表]\s*\d+\s*[:：.、]?\s*', '', alt)   # 剥"图/表 N："编号前缀
    cn = re.findall(r'[一-鿿]', body)                 # 只数中文字
    if len(cn) > LIMIT:
        bad.append((len(cn), ''.join(cn)[:30]))
if bad:
    for n, preview in bad:
        print(f"  ❌ 图注主体 {n} 字（>{LIMIT}）: {preview}...")
    print(f"  共 {len(bad)} 处图注过长 — alt 文字只写简短标签(≤20字)，判据/参数/结论移入正文")
    sys.exit(3)
print("  ✅ 图注长度合规")
PYEOF
cap_rc=$?
[ "$cap_rc" -eq 3 ] && echo "⛔ 图注过长：把 alt 文字压成简短标签、细节移入正文后，重跑本检测直到输出 ✅ 才能结束"

# 9. ⛔ 图号起句去套路化检测（Word 版专属：LaTeX 流程由 writing_check.sh 7b2 兜底，docx 流程此前没有，导致
#     正文里每张图都写成"图 N 显示…/图 N 中…"这种单调开头。这里补上，与竞赛 docx 第10项、LaTeX 版口径一致。）
echo "--- 图号起句去套路化检测 ---"
PYTHONIOENCODING=utf-8 python - paper/main.md << 'PYEOF'
import re, sys
try:
    text = open(sys.argv[1], encoding='utf-8', errors='ignore').read().replace('\r\n', '\n')
except FileNotFoundError:
    sys.exit(0)
# 只查正文：截到"## 附录"/"## 参考文献"为止（附录代码/参考文献里的图号不算）
m = re.search(r'\n##\s*(附录|参考文献|Appendix|References)', text)
body = text[:m.start()] if m else text
# 以"图 N…/表 N…"起句 = 最单调的 AI 痕迹（"如图/从图/由图/见图/观察图"这类带出式不算，它们把图号沉在句中）
open_re = re.compile(r'^(图|表)\s*\d')
def is_prose(p):
    s = p.strip()
    if len(s) < 15:                      # 太短：多半是题注残行/单行标签
        return False
    if s[0] in '#>|`!*-\\%{}$&':         # 标题/引用/表格/代码/图片(![)/列表/加粗/LaTeX 命令，非分析散文
        return False
    if re.match(r'^\d+\.', s):           # 有序列表 "1."
        return False
    return True
# 按顶级章节 (## ) 分组，段内按空行拆
sections = re.split(r'(?m)^##\s', body)
adj_pairs = 0        # 相邻两分析段都图号起句（硬违规，继承 LaTeX 版口径）
heavy_secs = []      # 单节图号起句 >=3（交替盲区：每图配一个"图N开头"段，中间隔带出段也算）
for sec in sections:
    flags = [bool(open_re.match(p.strip())) for p in re.split(r'\n\s*\n', sec) if is_prose(p)]
    adj_pairs += sum(1 for i in range(len(flags) - 1) if flags[i] and flags[i + 1])
    n_open = sum(flags)
    if n_open >= 3:
        heavy_secs.append(n_open)
bad = adj_pairs > 0 or bool(heavy_secs)
if bad:
    if adj_pairs:
        print(f"  X {adj_pairs} 处相邻段落都以「图 N…/表 N…」起句 — 最刺眼的套路，必须把图号沉到句中或句末括号")
    if heavy_secs:
        print(f"  X {len(heavy_secs)} 个章节里图号起句段 >=3（{heavy_secs}）— 每张图都'图N开头'太单调，须换切入方式")
    print("  修复：改成 括号旁注(首选，如『……（图 3）』)／动词引导(『观察图 4 中……』)／后置印证(『……在图 5 得到印证』)；「图作主语」整节最多一次")
    sys.exit(3)
print("  OK: 图号引用句式无套路化")
PYEOF
fig_rc=$?
[ "$fig_rc" -eq 3 ] && echo "⛔ 图号起句套路化：按上面提示改写后，重跑本检测直到输出 ✅ 才能结束"
```

如果任何 ⛔ 出现，回到对应步骤修复后重跑验证。**图注超长检测是"检测→修复→再检测"闭环：只要报 ❌（`exit 3`），就回到 `paper/main.md` 把点名的图注压成 ≤20 字的简短标签、细节移入正文，重跑第 8 项直到输出"✅ 图注长度合规"为止。**

⛔ **图号起句检测同样是"检测→修复→再检测"闭环**：只要第 9 项报 ❌（`exit 3`），就回到 `paper/main.md`，把被点名的"图 N…/表 N…"开头段改成括号旁注／动词引导／后置印证等切入方式（「图作主语」整节最多一次），然后**重跑第 9 项直到输出「✅ 图号引用句式无套路化」为止**，确保 Word 导出与 PDF 导出质量对齐。

## Key Rules（docx 模式专属）

- **唯一主产物**：`paper/main.md`
- **绝不产**：`.tex` / `.bib` / `.cls` / `.sty` / `.aux`
- **正文中绝不出现** `\begin{...}` / `\input` / `\cite` / `\section` / `\includegraphics`
- **公式用** `$...$` / `$$...$$`，不用 `\[...\]` / `\begin{equation}`
- **图嵌入用** `![alt](path)`，不用 `\includegraphics`
- **表格用** markdown pipe table，不用 `\begin{table}`
- **引用用** `[N]`，不用 `\cite{key}`
- **参考文献** 直接以文本形式写在「## 参考文献」章节，不用 `.bib`
- 中文摘要 500-700 字、英文摘要 350-500 词
- 正文字符数 ≥ MAX_PAGES × 800
- 数值必须来自 `figures/all_results.json` / `RESULTS.md`，禁止编造
- 备份现有 `paper/main.md` 后再覆盖


---

## ⛔ FIGURE_MANIFEST 对账（写完正文必跑，规划了几张就必须嵌入几张）

```bash
echo "=== FIGURE_MANIFEST 对账 ==="
PLAN_FILE=""
for f in PROBLEM_ANALYSIS.md PAPER_PLAN.md MODELING_REPORT.md TOPIC_PLAN.md; do
  [ -f "$f" ] && grep -q "<!-- BEGIN FIGURE_MANIFEST -->" "$f" && { PLAN_FILE="$f"; break; }
done
if [ -n "$PLAN_FILE" ]; then
    START=$(grep -n "<!-- BEGIN FIGURE_MANIFEST -->" "$PLAN_FILE" | head -1 | cut -d: -f1)
    END=$(grep -n "<!-- END FIGURE_MANIFEST -->" "$PLAN_FILE" | head -1 | cut -d: -f1)
    EXPECTED_FIGS=$(sed -n "${START},${END}p" "$PLAN_FILE" | grep -oE "^[[:space:]]*-[[:space:]]+(fig_[a-zA-Z0-9_]+|tikz_[a-zA-Z0-9_]+)" | sed "s/^[[:space:]]*-[[:space:]]*//")
    manifest_missing=0
    for name in $EXPECTED_FIGS; do
        if ! ls figures/${name}.png figures/${name}.pdf figures/${name}.drawio 2>/dev/null | head -1 | grep -q .; then
            echo "❌ MANIFEST: $name 文件不存在"
            manifest_missing=$((manifest_missing + 1))
        elif ! grep -qE "${name}\.(png|pdf)" paper/main.md 2>/dev/null; then
            echo "❌ MANIFEST: $name 文件存在但 paper/main.md 未引用"
            manifest_missing=$((manifest_missing + 1))
        fi
    done
    if [ "$manifest_missing" -gt 0 ]; then
        echo "⛔ FIGURE_MANIFEST 对账失败 ($manifest_missing 张): 必须把这些图都画出来 + 嵌入正文后再结束"
    else
        echo "✅ FIGURE_MANIFEST 全部嵌入"
    fi
else
    echo "(规划文档无 FIGURE_MANIFEST, 跳过对账)"
fi
```

## ⛔ 通用 paper-stage 审计（所有写稿步骤共用，跨工作流）

写完正文 / 编译前必须跑一次通用审计，独立于 PROBLEM_FACTS.json 是否存在：

```bash
# 通用 paper 审计：
#   [13] 正文结论与 results.json 一致（防"最优解 X 但正文写 Y"）
#   [14] 事件源归属（防"凭变量名脑补撞击 / 命中 / 拦截"）
# 即使没 PROBLEM_FACTS.json（普通学术 / 课程论文 / 人文社科），也会以"简化模式"跑独立审计。
if [ -f _utils/facts_audit.py ]; then
    python3 _utils/facts_audit.py --stage paper 2>&1 | tee -a AUDIT_REPORT.md
    PRC=$?
    if [ "$PRC" = "1" ]; then
        echo "❌ 通用 paper-stage 审计未通过 — 必须按上面提示修正正文 / results.json 后重新跑"
    fi
fi
```

