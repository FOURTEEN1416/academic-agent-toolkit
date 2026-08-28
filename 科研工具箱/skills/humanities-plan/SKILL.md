---
name: humanities-plan
description: "人文社科论文规划。适用于文学、历史、哲学、社会学、传播学、新闻学、文化研究等领域的中文学术论文。通过结构化提问理清问题意识，选定理论框架，设计递进论证结构，规划文献综述，产出 OUTLINE.md + PAPER_PLAN.md。Use when starting a humanities/social-science paper workflow."
argument-hint: [paper-topic]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, WebSearch, WebFetch, Agent
---

# 人文社科论文规划

为以下主题规划人文社科论文：**$ARGUMENTS**

> **适用范围**：文学、历史、哲学、社会学、传播学、新闻学、文化研究等人文社科中文学术论文。
> **本步骤只规划，不写正文。** 正文由 `humanities-write` 完成。
> **输出形态**：Word（docx）。论文以**文字论证 + 文本细读 + 文献对话**为主，通常**没有数据图/代码**。

## 常量
- **WORD_COUNT_TARGET** — 目标字数（默认 8000）
- **CUSTOM_REQUIREMENTS** — 用户自定义要求（从 CLAUDE.md 读取）

## 输入
1. 论文主题（$ARGUMENTS）
2. 用户上传资料（`user_data/`，可选：研究对象文本、已读文献、老师要求）
3. 已有大纲草稿（如存在 `OUTLINE.md`）

## ⛔ 方法论三原则（贯穿规划全程，最高优先级）
1. **理论是工具，文本/史料是目的地。** 引入理论是因为它能命名材料里**已经存在**的现象，不是为材料提供需要被验证的答案。用一个概念把一个问题想透，胜过堆砌多个概念。
2. **历史背景是语境，不是解释。** 背景回答"为什么这个作者/文本会提出这个问题"，不回答"这个文本说了什么"。把背景当答案，论文就沦为历史注脚。
3. **论点从材料内部生长出来。** 好论点是被材料逼出来的，不是从外部框架演绎的。先有细读中的困惑/发现，再找匹配的理论语言。

## ⛔ 学术诚信红线（规划阶段也适用）
- 不编造文献（作者/标题/期刊/年份/页码任一项都不能编）。文献关键词清单只列**检索方向**，不预先编造具体条目。
- 不根据论文标题推测其内容；不把摘要当作论文全部。
- 不确定的史实/人名/年份标注"待查证"。

## 阶段零：提问引导（动笔规划前必做，不要跳过）

通过结构化提问把模糊想法变成清晰方案。**逐个问，一次只问一个**，等用户回答再问下一个。

**第一轮 · 定位（必问）：**
1. 你在写什么？课程论文 / 本科毕业论文 / 硕士论文 / 博士论文 / 期刊投稿？
2. 研究对象是什么？具体到作品名 / 历史事件 / 哲学文本 / 社会现象。（用户说"研究鲁迅"→ 追问哪部作品/哪个时期）
3. 你现在最困惑的一件事是什么？（比"你的论点是什么"更易回答，往往直指真正的问题意识）
4. 有没有已读过的文献或理论？有的话：这个理论能解释材料里的什么现象？

**第二轮 · 聚焦（据第一轮回答选追问）：**
| 用户状态 | 追问 |
|---|---|
| 有对象没问题 | "读这个文本时，哪个细节让你最困惑？" |
| 有问题不会论证 | "如果有人反对你，他们最可能怎么说？" |
| 有理论不会结合材料 | "这个理论描述的现象，在你的材料里对应哪个具体段落？" |
| 有大量笔记不会组织 | 读 `_utils/humanities-material-integration.md` |

**第三轮 · 确认方案：** 把研究对象、核心问题、初步论点方向、拟用理论框架、论文类型与预期篇幅复述给用户确认，再进入后续。

> ⛔ 如果用户在创建工作流时已通过 CUSTOM_REQUIREMENTS 把这些信息说清楚了，可合并提问、快速确认，不必机械问满三轮。但**问题意识和论点方向必须明确**才能往下走。

## 阶段一：选题与问题意识

把模糊兴趣转化为**可争辩、可论证、有原创性**的问题。

| 层次 | 示例 | 评价 |
|---|---|---|
| 弱论点 | "《X》批判了 Y" | 描述性、是常识 |
| 中等论点 | "《X》通过 Y 机制揭示了 Z" | 有分析、可能缺深度 |
| 强论点 | "《X》在 A 与 B 的双重失败之后，在 C 处涌现出 D，揭示了关于 E 的根本悖论" | 有张力、有原创、可争辩 |

目标是写出一个**强论点句**作为全文骨架。

## 阶段二：理论框架选择

把理论框架和材料的核心观察放在一起问：**这个理论家是否已经在理论层面想透了材料里存在的问题？** 如果需要削足适履改造材料来适应理论，就换框架。

每引入一个理论概念，规划时确认三层：① 定义（用自己的语言）② 适用性论证（为什么它能描述材料里的现象）③ 落地（对应哪个具体细节）。

⛔ 常见错误：理论堆砌（三个框架各用一点）、理论先于材料、引用而不分析。

**选理论框架时读取理论家速查**（含 20 位理论家 + 兜底搜索策略）：
```bash
cat _utils/humanities-theory-frameworks.md 2>/dev/null || cat skills/shared-scripts/humanities-theory-frameworks.md
```
表里没有的理论家：联网搜其核心概念，确认后再用；查不到就用拼音+解释兜底，并标注待核实。

## 阶段三：论文结构设计（产出 OUTLINE.md）

好结构是**递进的论证**，不是平行的观察。每章应：接收上一章留下的张力 → 推进论证 → 开启下一章的问题。把各章标题连成一句话，若能读出完整论证逻辑，结构就对了。

**人文社科论文通用结构：**
```
摘要 + 关键词
引言（有张力的细节切入 → 核心问题 → 学术史定位 → 分析框架 → 论点句）
（文献综述：硕博论文独立成章；课程/期刊论文可并入引言）
（研究方法：实证型需要；思辨型可省略）
正文主体章节（2-4 章，递进论证；文本细读 + 理论分析 + 历史语境交织）
结语（收拢论证 → 回应引言 → 向更大问题敞开）
参考文献
```

**OUTLINE.md 写作要点：**
- 标题用 `## 第N章` / `### N.1`
- 每章一个子表标注：预期字数 / 核心论点 1-2 条 / 关键概念 / 涉及的核心材料段落
- 章节标题用"核心概念：论点方向"格式（冒号前点明对象，冒号后揭示论证动作）
- 末尾必须有 **Claims-Evidence Matrix**（每个核心论点 → 支撑它的文本细读/史料/文献）
- 末尾必须有 **文献调研关键词清单**

**Claims-Evidence Matrix 模板（人文社科版，Evidence 主要是文本/史料/文献，不是数据图）：**
```markdown
## Claims-Evidence Matrix
| Claim（核心论点） | Evidence（文本细读 / 史料 / 文献） | Section | Status |
|---|---|---|---|
| 《X》的碎片化句法是对叙事能力丧失的形式回应 | 《秋夜》《影的告别》语言层细读 + 文献[本雅明寓言论] | 第1章 | 待定 |
| 核心意象是寓言碎片而非象征 | 《死火》《墓碣文》意象系统细读 | 第2章 | 待定 |
```

## 📊 图表规划方法（如开启图表 / 不开启可跳过本节）

**规划任何图表前必读 SCI 图表配方库**（避免从零写代码、风格统一）：

```bash
# 1. 查看图表分布参考（哪些图适合人文社科/定量内容分析/历史数据）
cat _utils/figure_exemplars.md 2>/dev/null | head -200   || cat skills/shared-scripts/figure_exemplars.md | head -200

# 2. 查看调色板和样式规范
cat _utils/figure_style_guide.md 2>/dev/null | head -150   || cat skills/shared-scripts/figure_style_guide.md | head -150

# 3. 列出可用配方主题（5 个配方库共 60+ 张 SCI 级图表代码）
ls _utils/figure_recipes_*.md 2>/dev/null   || ls skills/shared-scripts/figure_recipes_*.md
```

**为每张要规划的图选择配方编号**（用 `python3 _utils/get_recipe.py <library> <id>` 提取代码模板）：
- `basic`：12 张基础图（gradient fill / KDE / Rain Cloud / Lollipop）
- `advanced`：17 张高 SCI 影响因子图（SHAP / Kaplan-Meier / Forest plot）
- `empirical`：16 张计量/统计图（DID / 分位数回归 / 工具变量）⛐ **人文社科定量内容分析、问卷统计、历史数据趋势优先在这里挑**
- `academic`：12 张 AI/CS 图（ablation / t-SNE）
- `competition`：23 张竞赛常用图（一般用不上）

⛐ **人文社科图表 ≠ STEM 论文堆数据图**：
- 一篇人文社科论文图表数量通常 **0-3 张**，DRAWIO（概念关系图/理论框架图）比数据图更常见
- 数据图必须有真实可量化材料（问卷/词频/历史档案数据），不可为凑图编数据
- 选配方时优先考虑「叙事清晰」而非「视觉炫技」(forest plot / lollipop / 简洁折线 > 复杂热图)

**⛔ 组合图（Subfigure）按必要性自决**（开启图表才适用）：每张图先自问"单值/单维"还是"多值对比/多维并陈"：

🟢 **适合组合**（panel ≤ 4，每 panel ≥ `0.48\textwidth`）：问卷分组对比（性别×态度 / 年龄×态度）/ 历史趋势分时期对比 / 概念关系图前后版本对比 / 多文本词频对比
🔴 **不要组合**：内容无关硬拼 / 单图本身复杂（地图、概念网络）

FIGURE_MANIFEST 标注 `[2-panel]` / `[4-panel]` / `[single]`（默认 single 可省）。详细判据见 `_utils/writing_rules.md` 第 4 条。**人文社科论文图本就少，组合图不是凑数手段，只在"对比维度天然同构"时才用。**

## 阶段四：文献综述与关键词规划（写进 PAPER_PLAN.md）

文献综述按**论证功能**组织（奠基型 / 对话型 / 空白型），不是按时间罗列。详细方法：
```bash
cat _utils/humanities-literature-review.md 2>/dev/null || cat skills/shared-scripts/humanities-literature-review.md
```

**中国学者发表路径**（CSSCI / 北核 / 普通核心 / 集刊 / 学位论文的写作差异 + 期刊选择策略）：
```bash
cat _utils/humanities-platform-guide.md 2>/dev/null || cat skills/shared-scripts/humanities-platform-guide.md
```

在 OUTLINE.md 末尾追加文献调研关键词：
```markdown
## 文献调研关键词
- 核心：[关键词1]、[关键词2]
- 理论：[理论家+概念]
- 时间范围：经典理论文献不限年份；研究综述近 5-10 年优先
```

⛔ 文献检索在 `humanities-write` 阶段用 `$SCHOLAR_SCRIPT` 真实检索（英文走 OpenAlex/S2，中文优先用户自己在知网/国家哲社文献中心搜后提供；AI 负责分析整合，不自动编造）。规划阶段只定关键词方向。

## 工作流程小结

1. 读输入（user_data 提取文本、老师要求）：
```bash
ls user_data/ 2>/dev/null
for f in user_data/*_extracted.md user_data/*_extracted.txt; do [ -f "$f" ] && { echo "--- $f ---"; head -c 800 "$f"; echo; }; done
TPL=$(find user_data -maxdepth 1 -name "*.docx" 2>/dev/null | head -1); [ -n "$TPL" ] && echo "检测到 docx 模板: $TPL（docx-export 会套用其样式）"
```
⛔ 读大文件用 `Read` 带 offset/limit 或 `Grep`，不要全量 `cat`，否则吃光 context。

2. 走阶段零→三，用 `Write` 产出 `OUTLINE.md`。
3. 走阶段四，用 `Write` 产出 `PAPER_PLAN.md`（含文献规划 + FIGURE_MANIFEST 区块）。

## ⛔⛔⛔ 完成铁律（最高优先级）

**必须产出 `OUTLINE.md`（≥ 800 字节）和 `PAPER_PLAN.md`（≥ 800 字节，含 FIGURE_MANIFEST）。**
⛔ 用 `Write` 工具真实落盘，不要只 Read/Bash 就 end_turn（这是本步骤失败 #1 原因）。

结束前必跑 PASS 阻断验证：
```bash
PASS=true
[ -f OUTLINE.md ] && SZ_O=$(wc -c < OUTLINE.md) || SZ_O=0
[ -f PAPER_PLAN.md ] && SZ_P=$(wc -c < PAPER_PLAN.md) || SZ_P=0
[ "$SZ_O" -ge 800 ] && echo "✅ OUTLINE.md ($SZ_O)" || { echo "❌ OUTLINE.md 缺失/过小 ($SZ_O) — 立即 Write"; PASS=false; }
[ "$SZ_P" -ge 800 ] && echo "✅ PAPER_PLAN.md ($SZ_P)" || { echo "❌ PAPER_PLAN.md 缺失/过小 ($SZ_P) — 立即 Write"; PASS=false; }
[ "$PASS" != true ] && echo "⛔ 验证未通过 — 修复后再结束"
```

## ⛔⛔⛔ FIGURE_MANIFEST（机器可读对账清单，必须输出）

人文社科论文**默认纯文字论证、无图**。是否规划图表**以引擎在 CLAUDE.md 中的提示为准**
（用户在前端勾选「数据图表」或「理论框架图/示意图」时，引擎会注明要规划对应图表）：
- **未开启任何图表（默认）**：写 `ALL=0`，全部留空。
- **开启「数据图表」**：规划 1-3 张数据图（`fig_xxx`，如内容分析词频、问卷/统计分布、历史数据趋势、
  田野计数等），列入 DATA 类。⛔ 仅当论文确有可量化材料时才规划，不可为凑图编数据。
- **开启「理论框架图/示意图」**：规划 1-2 张示意图（概念关系图 `fig_framework`、分析框架图、
  研究路线图 `fig_roadmap` 等），列入 DRAWIO 类。

**为每张规划的图列以下 5 项**（写进 OUTLINE.md 对应章节，方便 humanities-write 阶段对照）：
- **图号**：fig_xxx（数据图）/ fig_framework_xxx / fig_roadmap_xxx（DRAWIO 类）
- **标题**：用于正文引用（如 "图 1：晚清报刊关键词词频分布"）
- **目的**：本图回答论证中的哪个具体问题
- **数据源**：来自 user_data/xxx 文件 / 用户在知网检索后提供 / 历史档案
- **图表类型 + 配方**：如 "Lollipop 图 (advanced#7)" 或 "概念关系图 (drawio 手绘)"

在 `PAPER_PLAN.md` **最后**追加（BEGIN/END 锚点不可缺）：
```markdown
<!-- BEGIN FIGURE_MANIFEST -->
## 图表清单（FIGURE_MANIFEST）

**数据图（matplotlib gen_fig_*.py）：**
（默认无；开启数据图表且有可量化材料时列 - fig_xxx）

**DrawIO 流程/架构图：**
（默认无；开启理论框架图时列 - fig_framework / fig_roadmap）

**TikZ 图：**
（一般无）

**总数：DATA=0, DRAWIO=0, TIKZ=0, ALL=0**
<!-- END FIGURE_MANIFEST -->
```
⛔ 把计数改成实际规划数量（开启图表时 DATA/DRAWIO 不能仍写 0）。

⛔ 结束前验证 FIGURE_MANIFEST 区块存在：
```bash
if grep -q '<!-- BEGIN FIGURE_MANIFEST -->' PAPER_PLAN.md && grep -q '<!-- END FIGURE_MANIFEST -->' PAPER_PLAN.md; then
  echo "✅ FIGURE_MANIFEST 区块存在"
else
  echo "❌ FIGURE_MANIFEST 区块缺失，必须补（无图也写 ALL=0）"
fi
```

## 输出文件
- `OUTLINE.md` — 大纲（递进结构 + 各章论点 + Claims-Evidence Matrix + 文献关键词）
- `PAPER_PLAN.md` — 文献综述规划 + FIGURE_MANIFEST

## 关键规则
1. 只规划不写正文（正文交 `humanities-write`）。
2. 方法论三原则 + 学术诚信红线全程遵守。
3. 论点必须是**强论点**（可争辩、可论证、有原创、有方向）。
4. 结构必须**递进**（接收张力→推进→开启），不能平行罗列。
5. Claims-Evidence Matrix 必须存在，是后续撰写质量基准。
6. FIGURE_MANIFEST 区块必须存在（无图写 ALL=0）。

## STEP_MANIFEST 产出声明

本步骤完成后，必须调用 `engine.step_manifest.write_manifest`（或经 bridge/common 等价入口）在工作区根目录写入 `STEP_MANIFEST.json`，至少包含：stepName / backend（含版本）/ config / inputFiles / outputFiles（含 SHA-256）/ commands / dependencies。质量门禁 `step_manifest` 将校验其存在性与完整性；缺失或无效将导致本步骤无法通过（fail）。

建议额外记录：输入材料来源哈希、模板版本。
