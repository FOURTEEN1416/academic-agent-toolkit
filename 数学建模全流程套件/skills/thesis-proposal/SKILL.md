---
name: thesis-proposal
description: "开题报告撰写。生成完整的学位论文开题报告，包含选题背景、研究现状、研究内容、技术路线、进度安排和参考文献。Use when user says \"开题报告\", \"thesis proposal\", \"开题\"."
argument-hint: [research-topic]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, WebSearch, WebFetch, Agent
---

# 开题报告撰写

为以下研究课题生成开题报告：**$ARGUMENTS**

## 常量

- **DEGREE_LEVEL** — 从 Additional Parameters 读取（master / doctoral / undergraduate）
- **CUSTOM_REQUIREMENTS** — 用户自定义要求

## 输入

1. 研究课题（$ARGUMENTS）
2. 用户上传的学校模板（`user_data/*.docx`，可选）
3. 用户上传的参考资料（`user_data/*.pdf`，可选）

## 硬约束（借鉴 lunwen-skill intake 模式）

1. 如果 `user_data/` 中有学校开题报告模板（.docx），必须先分析模板结构再写内容
2. 参考文献必须真实可核验（有 DOI 或可查证的出版信息），不确定就不用
3. 参考文献时间范围：2020 年及以后为主（≥80%）
4. 参考文献数量：10-15 篇（中文 7-10 篇 + 英文 3-5 篇）
5. 技术路线**根据 `skip_drawio` 参数自动决定形式**：
   - `skip_drawio=False`（默认，画图）：4.2 章节用 `![技术路线图](figures/fig_roadmap.png)` 引用图片，不写 mermaid/drawio 源码
   - `skip_drawio=True`（不画图）：4.2 章节用**文字 + Markdown 表格**描述各阶段，不引用任何图片
6. 进度安排必须以表格形式呈现
7. 最终输出文件名：`PROPOSAL.md`

## ⛔⛔⛔ 完成铁律（最高优先级，违反则本步骤失败）

**本步骤必须产出 `PROPOSAL.md`（≥ 5KB，完整的开题报告内容）**。

⛔ **MANDATORY: 用 `Write` 工具直接写出 `PROPOSAL.md`。不要只调 Read/Bash 工具就 end_turn — 这是本步骤失败的 #1 原因。产出必须是真实落盘的文件。**

⛔ **读用户上传的文献/数据时**：
- 不要 `cat` 整个 `_extracted.md/.txt` 文件 — 一个大文件就能把 context budget 吃光，没空间产出主文件。
- 用 `Read` 工具带 offset/limit 范围读，或用 `Grep` 工具按关键词提取。
- CLAUDE.md 已列出所有上传文件清单 + 字数，**优先用清单 + Read 局部，不要全量 cat**。

⛔ **结束前必跑 PASS 阻断验证**（只 echo "❌" 不算，必须显式判定）：
```bash
PASS=true
[ -f PROPOSAL.md ] && SZ=$(wc -c < PROPOSAL.md) || SZ=0
if [ "$SZ" -ge 5120 ]; then
    echo "✅ PROPOSAL.md ($SZ bytes)"
else
    echo "❌ PROPOSAL.md 缺失或过小 ($SZ bytes) — 立即用 Write 工具产出, 不要 end_turn"
    PASS=false
fi
[ "$PASS" != true ] && echo "⛔ 验证未通过 — 必须修复后再结束本步骤"
```


## 工作流程

### Step 1: 读取输入 + 分析模板

```bash
echo "=== 检查用户上传资料 ==="
ls user_data/ 2>/dev/null || echo "无用户上传文件"
```

如果存在学校模板（.docx 或 .pdf）：
- 读取 `user_data/*_extracted.txt`（系统已自动提取文本）
- 分析模板要求的章节结构
- 按模板结构调整后续输出

如果无模板，使用以下默认结构。

### Step 2: 文献调研

⛔ **必须使用 `$SCHOLAR_SCRIPT` 搜索真实文献，禁止凭记忆编造。** WebSearch 不可信用作主搜索，**只能在 scholar_fetch 失败时兜底**。

```bash
PYTHON=""; for _c in "$MH_PYTHON" python python3; do [ -z "$_c" ] && continue; if $_c -c "import sys" >/dev/null 2>&1; then PYTHON="$_c"; break; fi; done; [ -z "$PYTHON" ] && PYTHON=python
mkdir -p _tmp

# 中文主题搜索（AMiner 自动返回中文标题 + 作者 + 年份 + DOI）
$PYTHON "$SCHOLAR_SCRIPT" bibtex "你的研究主题中文关键词" --max 10 > _tmp/refs_zh.json
# 英文补充搜索
$PYTHON "$SCHOLAR_SCRIPT" bibtex "English keywords" --max 5 > _tmp/refs_en.json

# 按方法 / 应用场景 / 综述类多维补搜（每个搜 3 篇够用）
$PYTHON "$SCHOLAR_SCRIPT" bibtex "你的核心方法名" --max 3
$PYTHON "$SCHOLAR_SCRIPT" bibtex "你的应用场景中文" --max 3
```

**搜索策略（借鉴 PaperSpine 三维度调研）：**

1. **研究背景维度**：搜索课题所在领域的综述论文和行业报告
2. **技术方法维度**：搜索与课题方法相关的核心论文（近 3 年优先）
3. **应用场景维度**：搜索课题应用领域的最新进展

**结果处理（必读）：**
1. **检查 `match_label`**：`"good"` → 直接采用；`"partial"` → 核对标题是否真符合主题；`"low"` → 大概率搜错了，换关键词重搜或用 WebSearch 兜底。
2. `match_score < 0.3` 不要盲信。
3. `bibtex_source="auto"` 的需手动核实 DOI 真实性（CrossRef / 出版社官网）。

**文献筛选规则（借鉴 lunwen-skill reference_selector）：**
- 优先 2022 年及以后的文献
- 中文优先 CNKI/万方可核验来源
- 英文优先有 DOI 的 IEEE/Springer/Elsevier/ACM 来源
- 不确定真实性的条目直接丢弃
- 总数控制在 10-15 篇（中文 7-10 + 英文 3-5）

**兜底**：如果某主题 scholar_fetch 全 `match_label="low"`，再用 WebSearch 在 Google Scholar / Semantic Scholar 网站搜索，**手动核实** title + authors + year 后才能加入。

将搜索到的文献信息记录到 `literature_notes.md`。

### Step 3: 撰写开题报告

基于文献调研结果，撰写完整开题报告。输出到 `PROPOSAL.md`。

**默认结构（中国高校通用）：**

```markdown
# [论文题目]

## 一、选题背景与意义

### 1.1 研究背景
（行业现状 + 技术发展趋势，800-1000 字）

### 1.2 选题意义
（理论意义 + 实践意义，500-800 字）

## 二、国内外研究现状

### 2.1 国外研究现状
（按时间线或技术路线梳理，600-800 字）

### 2.2 国内研究现状
（按时间线或技术路线梳理，600-800 字）

### 2.3 现有研究不足
（指出 gap，为本研究提供切入点，300-500 字）

## 三、研究内容与目标

### 3.1 研究目标
（总目标 + 具体目标，300-500 字）

### 3.2 研究内容
（用**连贯段落**叙述 3-5 个核心研究内容，**禁止用 `-`/`*` bullet 分点罗列**；用「首先…其次…再次…最后…」过渡词或「（1）（2）（3）」行内编号衔接，500-800 字。详细规则见下方「⛔ 反 AI 痕迹写作铁律」第 1 条）

### 3.3 拟解决的关键问题
（2-3 个关键技术难点，300-500 字）

## 四、研究方法与技术路线

### 4.1 研究方法
（具体方法论描述，500-800 字）

### 4.2 技术路线

⛔ **先检查 `skip_drawio` 参数**（CLAUDE.md 顶部「## 参数」段会列出）：

```bash
SKIP_DRAWIO=$(grep -E '^- skip_drawio:\s*[Tt]rue' CLAUDE.md 2>/dev/null | head -1)
echo "skip_drawio: ${SKIP_DRAWIO:-False}"
```

**分支 A：`skip_drawio=False`（默认，画图）**
- 在本节文字描述各研究阶段后，**末尾加一行**：
  ```markdown
  ![图 1：本研究技术路线图](figures/fig_roadmap.png)
  ```
- **禁止**在正文中输出 mermaid/drawio/PlantUML 源码块
- 后续 paper-figure-drawio 步骤会自动绘制 fig_roadmap.drawio 并导出 PNG

**分支 B：`skip_drawio=True`（不画图）**
- **禁止**写 `![](figures/fig_roadmap.png)` 引用（不存在的图会变成"image missing"占位符）
- 用**文字 + Markdown 表格**描述各阶段：
  ```markdown
  | 阶段 | 输入 | 核心方法 | 输出/产物 |
  |------|------|---------|----------|
  | 阶段一：文献调研 | 研究方向 | 系统综述+主题聚类 | literature_notes.md |
  | 阶段二：模型设计 | 文献空白点 | 理论建模 | 数学模型 |
  | ... | ... | ... | ... |
  ```
- 用 3-5 个阶段，每段配一两句文字说明衔接关系

## 五、创新点与预期成果

### 5.1 创新点
（2-3 个创新点，每个 100-200 字）

### 5.2 预期成果
（论文 + 系统/模型/数据集等，200-300 字）

## 六、进度安排

| 阶段 | 时间 | 主要工作内容 | 预期成果 |
|------|------|-------------|----------|
| 第一阶段 | 第1-2月 | 文献调研与方案设计 | 文献综述初稿 |
| 第二阶段 | 第3-5月 | 核心方法研究与实现 | 算法/系统实现 |
| 第三阶段 | 第6-8月 | 实验验证与结果分析 | 实验数据与分析 |
| 第四阶段 | 第9-10月 | 论文撰写与修改 | 论文终稿 |
| 第五阶段 | 第11-12月 | 论文答辩准备 | 答辩材料 |

## 七、参考文献

[1] 作者. 题名[J]. 刊名, 年, 卷(期): 页码.
...
```

### Step 4: 质量自检

撰写完成后执行以下检查：

1. **结构完整性**：所有 7 个一级章节是否齐全
2. **字数检查**：总字数是否在 4000-6000 字范围
3. **文献检查**：
   - 参考文献数量是否在 10-15 篇
   - 是否有 2020 年之前的文献超过 20%
   - 格式是否符合 GB/T 7714
4. **技术路线图**：
   - 如果 `skip_drawio=False`：必须包含 `![技术路线图](figures/fig_roadmap.png)` 引用，且不应有 mermaid/drawio 源码块
   - 如果 `skip_drawio=True`：必须有 Markdown 表格描述阶段，**不应**有 `figures/fig_roadmap.png` 引用
5. **进度表**：是否以表格形式呈现
6. **Markdown 清洁度**：正文中不应残留 `**`、反引号等标记（标题除外）

如果检查不通过，修正后重新输出。

## 写作风格约束（借鉴 lunwen-skill style guardrails）

1. 语言正式、学术化，但不堆砌空话
2. 避免"具有重要意义""实现了良好效果"等模板化表述
3. 研究现状部分必须有具体文献支撑，不能泛泛而谈
4. 技术路线描述要具体到方法名称，不能只写"采用先进技术"
5. 创新点要具体、可验证，不能过度夸大

---

## ⛔⛔⛔ 反 AI 痕迹写作铁律（Word 模式必须遵守，违反等同失败）

Word 输出最常被识别为「AI 写的」就是因为下面这 6 条没遵守。优先级凌驾于章节模板和字数要求。

1. **禁止 markdown bullet/编号列表（`-`、`*`、`1.`、`2.`）作为正文叙述。** 含「研究目标」「研究内容」「创新点」「拟解决的关键问题」「预期成果」等场景必须用连贯段落，不许分点罗列。
   - ❌ 错（最典型 AI 痕迹）：
     ```
     本研究的主要内容包括：
     - 内容一：构建多模态特征提取框架…
     - 内容二：设计动态权重融合机制…
     - 内容三：在公开数据集上进行实验验证…
     ```
   - ✅ 对（连贯段落 + 过渡词）：`本研究的主要内容包含三个递进部分。**首先**，构建多模态特征提取框架，从语义、纹理、结构三个维度…；**其次**，针对模态间的不平衡问题，设计动态权重融合机制…；**最后**，在 ImageNet 与 COCO 等公开数据集上进行实验验证…。`
   - ✅ 替代（行内括号编号）：`本研究主要内容包括：（1）构建多模态特征提取框架；（2）设计动态权重融合机制；（3）在公开数据集上验证。`
   - bullet **唯一允许场景**：进度安排表 / 参考文献列表 / 软件依赖 / 评价指标定义，正文叙述一律禁止。

2. **加粗写作 `**标签**：内容`，不要 `**标签：**内容`。** 把冒号包进 `**` 里 docx 引擎正则匹配不到，会留下孤立 `**` 残留。
   - ❌ `**研究目标：** 构建无参考的图像质量评估模型…`
   - ✅ `**研究目标**：构建无参考的图像质量评估模型…`

3. **每段至少 3-5 句话。** 1-2 句的短段落是 AI 痕迹；要么扩写到 3 句以上，要么并入相邻段落。

4. **连续段落不能以相同句式开头。** 三段都「本研究…」开头必须改，交替用「首先」「为此」「在此基础上」「针对…」「不同于…」「另一方面」等多样化连接词。

5. **图号必须显式引用，但句式换着来（标准优秀论文口径）。** 每张图/表都要点名「图 N」让读者对上号（硬规范，别为避免套路删图号）。要禁的是**"图 X 展示了……从图中可以看出……"这种图作主语+空话的单调流水账**，不是禁止一切图作主语。相邻两图引用句式必须不同，在括号旁注（首选）／句首带出／动词引导／图作主语（带实质结论时允许）／后置印证间轮换。
   - ❌ `图 1 展示了本研究的技术路线。从图中可以看出，研究分为四个阶段。`（图作主语+空话）
   - ✅ 括号旁注：`本研究遵循「文献调研 → 模型设计 → 实验验证 → 论文撰写」的四阶段递进路线（图 1），各阶段产出形成完整证据链。`
   - ✅ 图作主语（带实质结论）：`图 1 勾勒出本研究的四阶段技术路线，其中"模型设计"阶段的输出直接作为"实验验证"的输入，形成闭环。`

6. **去掉 AI 写作口头禅。** 少用「值得注意的是」「综上所述」「这一发现表明」「随着…的发展」「在…的背景下」「具有重要意义」。「研究表明」「多项研究证实」必须紧跟具体引用号 [N]，不能空喊。

---

## 输出文件

- `literature_notes.md` — 文献调研笔记
- `PROPOSAL.md` — 最终开题报告（主产出）
## ⛔⛔⛔ FIGURE_MANIFEST（机器可读对账清单，必须输出）

**写完上面的图表清单后，在产出文档（PAPER_PLAN.md / PROBLEM_ANALYSIS.md / 等）的**最后**追加一个机器可读的清单区块。下游 paper-figure / paper-figure-drawio / 写作 SKILL / workflow_engine.py 都按此清单对账。少一张就触发 AUTO-RECOVER。**

格式严格按此输出：

```markdown
<!-- BEGIN FIGURE_MANIFEST -->
## 图表清单（FIGURE_MANIFEST）

**数据图（matplotlib gen_fig_*.py，paper-figure 产出 .png/.pdf）：**
- fig_xxx
- fig_yyy

**DrawIO 流程/架构图（paper-figure-drawio 产出 .drawio + .png/.pdf）：**
- fig_arch
- fig_flow_xxx

**TikZ 图（paper-figure 产出 tikz_*.pdf）：**
- tikz_xxx

**总数：DATA=N, DRAWIO=M, TIKZ=K, ALL=N+M+K**
<!-- END FIGURE_MANIFEST -->
```

⛔ **铁律：**
- **每条只写文件名主干**（不带 .py / .drawio / .png / .pdf 后缀）
- **数量必须跟上面三类图清单完全一致**（一一对应）
- **如果用户禁用了 skip_figures / skip_drawio**，对应类别留空但 BEGIN/END 标记必须存在
- **纯文字论文（无图）**：写 `**总数：ALL=0**` 但 BEGIN/END 标记仍必须存在

⛔ **结束前必跑产出验证**（如果产出文档是 PAPER_PLAN.md / PROBLEM_ANALYSIS.md / TOPIC_PLAN.md）：

```bash
# 自动找产出文档
PLAN_FILE=""
for f in PAPER_PLAN.md PROBLEM_ANALYSIS.md TOPIC_PLAN.md MODELING_REPORT.md; do
  [ -f "$f" ] && PLAN_FILE="$f" && break
done
if [ -n "$PLAN_FILE" ]; then
  if grep -q '<!-- BEGIN FIGURE_MANIFEST -->' "$PLAN_FILE" && grep -q '<!-- END FIGURE_MANIFEST -->' "$PLAN_FILE"; then
    echo "✅ FIGURE_MANIFEST 区块存在"
  else
    echo "❌ FIGURE_MANIFEST 区块缺失，必须按上面格式追加（即使无图也要写 ALL=0）"
  fi
fi
```


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
