---

name: comp-paper-zh

description: "数学建模竞赛/统计建模中文论文撰写。按竞赛规范结构生成完整 LaTeX 论文。Use when user says \"写竞赛论文\", \"competition paper\", \"建模论文\"."

argument-hint: [competition-type]

allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Agent, WebSearch, WebFetch

---

# Competition Paper Writing (Chinese)

使用当前执行会话完成本步；路径按步骤合同，运行清单和证据由程序生成，模型负责实质成果。

Write a competition paper based on modeling results: **$ARGUMENTS**

## ⚡ 快速模式检测（开头先跑）

```bash

FAST_MODE=0

grep -q 'MH_FAST_MODE=1' AGENTS.md 2>/dev/null && FAST_MODE=1

echo "FAST_MODE=$FAST_MODE"

```

**若 `FAST_MODE=1`（速度优先）：** 仍必须产出完整论文（各章齐全、子问题全覆盖、图表按 manifest 嵌入、正文页数不超过下发上限、引用真实数据不编造、通过产出验证），但**跳过**：图文数值一致性逐句核对、AUDIT_OK 溯源反查、发现小瑕疵后的反复润色重写。一次写成、结构与内容齐全即可。**若 `FAST_MODE=0`（默认）：** 后文所有一致性检查照常执行。

## Constants（全部逐字转录自下发的 `contest_profile`，禁止转换与猜测）

执行会话上下文带有 `contest_profile` JSON（引擎按 `comp_rules.json` 下发；`contest_profile: null` = 本工作流无赛事身份）。把下列字段**逐字**转录进 shell 变量后只消费，不自己加前缀、转换名字、或从 AGENTS.md / 文件名 / 自由文本 / shell 默认值猜：

> 注入通道已落地（B-CLOSE-01）：引擎 `workflow_runner` 在步骤启动时把 bound 快照的赛事 ID/页限/范围/性质/届次写入 `workspace/.engine/contest_env` 并注入实际命令环境。下述模型侧逐字转录保留作一致性冗余；两边不一致时以引擎注入值为准并上报待核实。

- **CONTEST_ID** ← `contest_profile.contest_id` — 档案规范 `comp_*` 键（如 `comp_cumcm`、`comp_huawei`）。仅在 `contest_profile.status == "bound"` 时转录；`pending_binding` 或缺失 ⇒ 无有效赛事身份——停下报待核实，不是猜测，无默认，不回退国赛。

- **PAGE_CAP** ← `contest_profile.gate_page_cap` — 本任务 operative 页数门禁口径。只准不超，**没有页数下限、没有默认值**；具体数值以档案下发为准，本技能不写死。缺席 ⇒ 该赛事无 operative 页数合同（或历史裁决不继承）：页数上限未知 → 报待核实。

- **PAGE_SCOPE** ← `contest_profile.gate_page_scope` — `body`（只计正文，附录/参考文献另计）或 `total`（整本 PDF 计）。两个计数分开统计，不混用。

- **PAGE_CAP_STATUS** ← `contest_profile.page_cap_status` — `official_verified` / `task_override` / `unverified`。`unverified`（来源未核验）**不产生默认硬页限**，也不得当作已证官方规则——未知只阻塞对应合规结论（既不放行也不编出限制）。仅 `official_verified` 或单独标识的显式任务授权（`task_override`/显式任务口径）才按硬上限执行；禁止把未知官方规则包装成任务覆盖。

- **EDITION** ← `contest_profile.edition` — 可缺席；缺席经 `missing_fields` 上报，不反向推断。

- **CUSTOM_REQUIREMENTS**

## Inputs

1. PROBLEM_ANALYSIS.md, MODELING_REPORT.md, RESULTS.md

2. figures/, code/

## Load shared rules

```bash

cat skills/_utils/writing_rules.md 2>/dev/null || cat academic-toolkit/skills/_utils/writing_rules.md 2>/dev/null || cat ../../skills/_utils/writing_rules.md

```

<paper_structure>

## Paper Structure by Competition Type

### 数模竞赛 (cumcm/huawei/mathorcup/huazhong/etc.)

Template: `_templates/cumcm/`（国赛：`cumcmthesis.cls` + `cumcm2026.sty` + 骨架 `main.tex`）
华为杯：`_templates/huawei/`（`gmcmthesis.cls` + 骨架 `main.tex` + 封面 `logo.pdf`/`title.pdf`；字体 SimSun/SimHei/KaiTi/LiSu 不随库分发，取法见其 README.md）

⛔ **sty 定制纪律（防双源分叉）**：需要改样式时**禁止整份复制 `cumcm2026.sty` 后私改**（双源分叉：diff 说不清改了什么，合规无法对账）。正确做法：复制同目录 `cumcm2026_local.example.sty` 为 `cumcm2026_local.sty`——`\input` 真源 + 只在 PATCH 区追加差异 + BASELINE 行登记基线版本；`cumcm2026.sty` 头部有 `TEMPLATE_VERSION` 基线标记。

⛔ **其余赛事模板现状**：模板目录已收编进 `_templates/<模板目录>/`，Step 1 的 case 表把规范 `comp_*` ID 一一映射到目录（comp_huazhong 复用 `cumcm/`；comp_teddy / comp_certcup / comp_zhongqing / comp_tianfu / comp_shenzhen / comp_huadong 暂无专用目录，按档案 `template_cls: ctexart` 走通用骨架 `default/`——这是档案指定文档类的通用骨架，不是跨赛事套用）。目录不在位时断言**显式报错 exit 1 并给出补救路径**，不改用其他赛事模板。

**⛔ MathorCup 与 亚太赛中文(APMCM) 都使用 `MathorCupmodeling.cls` 文档类**（该 cls 随 `_templates/mathorcup/` 与 `_templates/apmcm_zh/` 入库，直接走下方分支复制）。使用 `\bianhao{}`、`\tihao{}`、`\timu{}` 设置队伍信息，`\keyword{}` 设置关键词。摘要用 `\begin{abstract}...\end{abstract}` 环境。参考文献用 `\begin{thebibliography}` 环境。

**⛔ 华中杯必须使用 `cumcmthesis` 文档类**（与国赛同源：本仓库 `_templates/cumcm/` 已入库 cls+sty+骨架，可直接 `cp _templates/cumcm/* paper/` 复用；中文渲染由 ctex 走系统字体，无需随模板捆绑字体）。华中杯模板使用 `\begin{abstract}...\keywords{}\end{abstract}` 环境写摘要（不是手动排版），参考文献用 `\begin{thebibliography}` 环境（不是 `\bibliography{}`）。

```

摘要（~1页，含关键词）

1 问题重述

2 模型假设

3 符号说明

4 问题一的建模与求解（each sub-problem gets its own chapter）

5 问题二的建模与求解

6 问题三的建模与求解

7 灵敏度分析与模型检验

8 模型评价与推广

参考文献

附录 A：代码

```

**⛔ 国赛提交文件命名规则（仅 `comp_cumcm` 适用；以下两条规则均为国赛专属，其他赛事按各自官方要求执行，不套用）**：

1. **所有提交文件必须以中文命名**，例如：`论文.pdf`、`代码说明.txt`、`支撑材料.pdf`、`AI工具使用详情.pdf`
2. **禁止使用英文文件名**提交，如 `paper.pdf`、`code_description.txt` 等
3. **程序说明仅使用 TXT 文件**（`代码说明.txt`），不使用 Markdown 或其他格式
4. **压缩包命名**：`参赛编号+队号.zip`（如 `20260001_A01.zip`），内部文件中文命名

**⛔ AI工具使用声明规则（按赛事档案裁决，不静默跳过）**：

- **`comp_cumcm`（2026 国赛强制，档案已入库规定）**：
1. **声明位置**：AI工具使用声明必须放在**参考文献之前**，不能放在附录中
2. **声明内容**：用途逐项**如实**来自用户确认的使用记录（`.mh/ai_disclosure.json`，存在时）——实际使用了哪些环节（资料查询/语言润色/代码调试/图表制作/建模求解等）就声明哪些；**不得隐瞒实际发生的 AI 用途**（隐瞒或虚假声明按当届规程可取消评奖资格），也不得虚构未发生的用途
3. **唯一生成通道**：`comp-cumcm-disclosure` 技能 / `skills/_utils/build_ai_disclosure.py` 程序化生成——禁止手写声明正文、禁止事后手工改写产物；声明正文与详情 PDF 口径必须一致（`--check-only` 会反查一致性）
4. 格式骨架（由程序生成，此处仅为结构示意，勿照抄为终稿）：

```latex
\section*{AI工具使用声明}
（由 build_ai_disclosure.py 依 .mh/ai_disclosure.json 如实生成）
```

- **其他赛事**：档案（`contest_profile.compliance`）无当届 AI 声明规定 ⇒ **不得静默不生成、也不得套用国赛格式冒充合规**——在交付/交接说明中显式上报待核实项：`AI_USE_REPORT: 待核实（comp_<x> 当届 AI 声明规定未入库，提交前对照当届官方规程核实）`。内容一律只依据用户确认的记录（`.mh/ai_disclosure.json`，存在时），不虚构工具、日期、用途。用户关闭 AI_DISCLOSURE 开关只影响是否生成声明内容，不免除上述待核实上报。

### 统计建模 (stats)

Template: `templates/stats/main.tex`

**Chapter structure is driven by research content, not fixed templates.**

Award-winning stats modeling papers vary wildly in structure — some organize by model, some by analysis step, some by research question. There is no "standard structure". 执行 Agent must design chapters autonomously based on the actual content in TOPIC_PLAN.md / MODELING_REPORT.md.

#### Fixed skeleton (must keep)

```

表格清单

插图清单

摘要（中英文，分页）

一、绪论/前言（研究背景 + 文献综述/研究现状 + 研究目标/内容）

  ↓

  [Middle chapters: content-driven, 执行 Agent designs autonomously, typically 3-5 chapters]

  ↓

N、结论与建议（结论 + 建议/展望 + 创新与不足）

参考文献

致谢

附录（代码）

```

#### Middle chapter design guide

After reading TOPIC_PLAN.md, design middle chapters following these principles:

**Principle 1: Chapter titles must be specific, not generic**

- ✗ "四、模型构建" → ✓ "四、基于 CNN 的水质预测模型构建与评价"

- ✗ "五、实证分析" → ✓ "五、生育意愿的影响因素——集成学习模型"

**Principle 2: Organize by research logic chain, not by textbook methodology**

- If the research has multiple sub-problems/models, each model can be its own chapter

- If the research uses a single method with deep analysis, organize by analysis steps

**Principle 3: Data and method chapters can be merged or separated**

- Simple data (one dataset) → merge into "数据与方法"

- Complex data (multi-source, heavy preprocessing) → separate chapter "数据描述与预处理"

#### Award-winning paper structure examples (reference only, do not copy)

**Example A — Classification + Path Analysis (fertility intention)**:

前言 → 模型构建 (introduce ensemble + Bayesian network) → 数据说明和预处理 → 探索性特征分析 → 生育意愿的影响因素 (ensemble results) → 生育意愿影响路径 (Bayesian network results) → 结论与建议

**Example B — Mixed Modeling (data factors & economic growth)**:

研究背景+文献 → 研究思路和模型介绍 → 理论分析 → 模型构建 (production function + regression + ARIMA, each a section) → 模型应用 (GDP prediction) → 总结与建议 → 创新与不足

**Example C — DEA Evaluation (economic sustainability)**:

绪论 → 文献综述 → 研究区域概况 → 评价指标体系构建 → 数据优化处理 (normalization + PCA) → DEA 模型建立及求解 → 结论及建议

**Example D — Deep Learning Prediction (water quality CNN)**:

绪论 → 模型构建思路与创新 → 数据描述及预处理 → 主成分分析 → CNN 模型构建与评价 (with model comparison) → 结论与展望

**Key observations**:

- No award-winning paper uses the "baseline regression → robustness → heterogeneity" causal inference structure (unless the topic IS causal inference)

- Chapter count varies from 5-7, determined by content

- "Model introduction / theoretical basis" can come before or after the data chapter

- "Innovation & limitations" can be inside the conclusion or a standalone chapter

#### Chapter design checklist (self-check before writing)

- [ ] Does every chapter title contain specific research content (not generic "模型构建")?

- [ ] Does the chapter order follow the research logic chain (reader can follow naturally)?

- [ ] Do core analysis chapters (model results) occupy 40-50% of the paper?

- [ ] Is there a dedicated data description / exploratory analysis chapter (reviewers value data understanding)?

- [ ] Does the conclusion include "innovation" and "limitations" (reviewer bonus points)?

Use Chinese numbering (一、二、三...) with sub-sections (一)(二)(三). Do not use 1、2、3 or 1.1、1.2 format.

Fixed sections that must be kept: 表格清单, 插图清单, 中英文摘要, 绪论, 结论, 参考文献, 致谢.

</paper_structure>

## ⛔⛔⛔ 完成铁律（最高优先级）

**根据 `params.output_format` 决定主产物**：

- **PDF 模式（默认）**：`paper/main.tex`（≥ 5KB）+ `paper/sections/*.tex` + `paper/references.bib`

- **docx 模式**：`paper/main.md`（单文件，≥ 5KB）。**禁止产 paper/main.tex**


产出结构、存在性和最低完整性由 `finish` 按模板中的 `output_contract` 自动核验；修复返回的具体问题，不复制执行验证脚本。

## Workflow

### Step 0: Backup + resume check + upstream validation

**⛔ 上游输出完整性（写论文前必做）：** `PROBLEM_ANALYSIS.md`、`MODELING_REPORT.md`、`RESULTS.md` 必须存在且非空壳——缺失或过小说明上游未交付，停下补上游，不带病开写。子问题覆盖度交叉核对（引擎没有的检查，唯一保留项）：

```bash

PROB_COUNT=$(bash skills/_utils/count_subproblems.sh PROBLEM_ANALYSIS.md 2>/dev/null || bash academic-toolkit/skills/_utils/count_subproblems.sh PROBLEM_ANALYSIS.md 2>/dev/null || bash ../../skills/_utils/count_subproblems.sh PROBLEM_ANALYSIS.md)

MODEL_COUNT=$(bash skills/_utils/count_subproblems.sh MODELING_REPORT.md 2>/dev/null || bash academic-toolkit/skills/_utils/count_subproblems.sh MODELING_REPORT.md 2>/dev/null || bash ../../skills/_utils/count_subproblems.sh MODELING_REPORT.md)

echo "子问题数: 分析=$PROB_COUNT, 建模=$MODEL_COUNT"

[ "$MODEL_COUNT" -lt "$PROB_COUNT" ] && echo "⚠ 建模报告覆盖子问题数少于赛题分析——回上游补齐再写"

```

> 结果数据缺席由引擎在本步 finish 强制拦截（`paper_consistency`：论文无结果数字来源即拒绝完成）；图表缺席由编译阶段引用检查兜底。这是安全网，不是豁免——动笔前确认上游齐套，`figures/all_results.json` 与 `figures/latex_includes.tex` 缺席就先回上游。

**⛔⛔ 能力验收闸门（写论文前必做，承接全链合同的最后一环，零额度两模式都跑）：** 论文是最终交付物，绝不能把没做到/做砸的能力写成成果。写正文前先核编码阶段的能力验收总账：

```bash

FAST_MODE=0; grep -q 'MH_FAST_MODE=1' AGENTS.md 2>/dev/null && FAST_MODE=1

python skills/_utils/paper_claim_check.py --audit CAPABILITY_AUDIT.md --checklist CAPABILITY_CHECKLIST.json --sections paper/sections --fast $FAST_MODE 2>/dev/null || python academic-toolkit/skills/_utils/paper_claim_check.py --audit CAPABILITY_AUDIT.md --checklist CAPABILITY_CHECKLIST.json --sections paper/sections --fast $FAST_MODE 2>/dev/null || python ../../skills/_utils/paper_claim_check.py --audit CAPABILITY_AUDIT.md --checklist CAPABILITY_CHECKLIST.json --sections paper/sections --fast $FAST_MODE

PCC=$?   # 0=全通过可写 1=有能力项未通过(FAIL/严格模式PENDING,不该写) 2=无总账跳过

```

> `PCC=1` 说明有能力项在编码阶段验收就没通过（FAIL/PENDING）——**回到 comp-code 把它真做到 PASS，再来写论文**，别把没做成的能力写进最终稿。写完正文后本闸会再跑一次（见 Step 6），那次还会扫正文有没有"吹了没通过的能力"。⛔ 承上启下收口：赛题分析定合同 → 建模认领 → 编码实现验收 → **论文只如实书写验收通过的成果**。

Back up existing `paper/`. 断点续写口径：`paper/sections/*.tex` 里 <500 字符或含"待补充/placeholder"的是占位章——续写它；>2000 字符的已完成章跳过不重写。每写完一章立即落盘，不在内存里攒。

### Step 1: Select template（规范 CONTEST_ID → 模板目录；拒绝猜测，无默认）

```bash

mkdir -p paper/sections

# Select template based on competition type — copy entire folder (tex + cls + fonts)

TMPL_BASE="_templates"

[ -d "$TMPL_BASE" ] || TMPL_BASE="templates"

# ⛔ 模板选择只认执行会话 contest_profile.contest_id 下发的规范 comp_* ID（逐字转录）。
# 禁止从 $ARGUMENTS / AGENTS.md / 文件名 / 子串猜赛事（自由文本与子串曾多次误命中，
# 如 "apmcm" 含 "mcm" 子串）；未指明赛事时报错停下，绝不默认国赛、绝不默认任何赛事。
if [ -z "$CONTEST_ID" ]; then
    echo "⛔ CONTEST_ID 缺失：contest_profile 未下发（contest_profile=null）。本技能只在 comp_* 赛事工作流内运行，拒绝猜测。" >&2
    exit 1
fi
case "$CONTEST_ID" in
    comp_cumcm)      TMPL="cumcm" ;;        # 档案 template_cls: cumcmthesis
    comp_huazhong)   TMPL="cumcm" ;;        # 档案 template_cls: cumcmthesis（withoutpreface，复用 _templates/cumcm/）
    comp_wuyi)       TMPL="wuyi" ;;         # cumcmthesis 同源 cls + 封面
    comp_huawei)     TMPL="huawei" ;;       # gmcmthesis
    comp_mathorcup)  TMPL="mathorcup" ;;    # mathorcup_main.tex（ctexart 基）
    comp_apmcm_zh)   TMPL="apmcm_zh" ;;     # MathorCupmodeling.cls
    comp_stats)      TMPL="stats" ;;
    comp_yangtze)    TMPL="changsanjiao" ;; # 长三角
    comp_huashu)     TMPL="huashubei" ;;
    comp_diangong)   TMPL="diangongbei" ;;
    comp_liaoning)   TMPL="dongsansheng" ;; # 辽宁/东三省联赛
    comp_shuwei)     TMPL="shuweibei" ;;
    comp_teddy|comp_certcup|comp_zhongqing|comp_tianfu|comp_shenzhen|comp_huadong)
        # 档案 template_cls: ctexart，暂无专用目录 → 通用 ctexart 骨架（_templates/default/）。
        # 这是档案指定文档类对应的通用骨架，不是跨赛事套用；专用模板入库后改回专属目录。
        TMPL="default" ;;
    *)
        echo "⛔ 未知赛事 ID: '$CONTEST_ID'（须为 comp_rules.json 顶层键的 comp_* 规范 ID）。拒绝猜测、不回退国赛。" >&2
        exit 1 ;;
esac

[ -d "$TMPL_BASE/$TMPL" ] || { echo "❌ 模板目录缺失：$TMPL_BASE/$TMPL/（入库位置 skills/comp-paper-zh/_templates/$TMPL/）。报能力缺口并停止，不得改用其他赛事模板。"; exit 1; }
# 按 .tex/.cls/.sty 逐文件复制：模板库中的子目录（如华为杯 official_docx/ 参考资料指针）
# 不是骨架组成，整体 glob 复制会因目录报错中断——这里只取骨架文件，逐文件显式失败
for _f in "$TMPL_BASE/$TMPL/"*.tex "$TMPL_BASE/$TMPL/"*.cls "$TMPL_BASE/$TMPL/"*.sty; do
    [ -e "$_f" ] || continue
    cp "$_f" paper/ || { echo "❌ 模板复制失败：$_f -> paper/"; exit 1; }
done
# 图/书目族（wuyi image2.png、dongsansheng refs.bib、huawei gmcm.bst 等骨架组成）
for _f in "$TMPL_BASE/$TMPL/"*.png "$TMPL_BASE/$TMPL/"*.bib "$TMPL_BASE/$TMPL/"*.bst; do
    [ -e "$_f" ] || continue
    cp "$_f" paper/ || { echo "❌ 模板复制失败：$_f -> paper/"; exit 1; }
done
# 字体子目录（huazhong/shuweibei 等模板以 Path=fonts/ 相对引用，整目录随迁）
if [ -d "$TMPL_BASE/$TMPL/fonts" ]; then cp -r "$TMPL_BASE/$TMPL/fonts" paper/; fi
echo "Template source: $CONTEST_ID -> $TMPL_BASE/$TMPL"

# ⛔ 同文档类复用核对（复制后立即执行）：复用骨架不携带另一赛事的封面、队号或声明。
# 逐项核对 paper/main.tex：源骨架注释口径、封面/标题占位、队号/编号设置、赛事声明——
# 一律替换/移除为本赛事当届口径；把源赛事专属元素留在交付物里属合规失败。

# ⛔ 模板落地断言：防止模板缺失时 cp 静默跳过、拖到编译阶段才炸——
#   此处硬性断言 cls/sty 已就位，否则立即失败并给出补救路径。
if ls paper/*.cls paper/*.sty > /dev/null 2>&1; then
    echo "✅ 模板文件已就位: $(ls paper/*.cls paper/*.sty 2>/dev/null | tr '
' ' ')"
else
    echo "❌ 模板缺失：$TMPL_BASE/ 下没有本题竞赛模板（paper/ 无 .cls/.sty）"
    echo "   补救路径："
    echo "   ① 国赛 cumcm：内置模板在 skills/comp-paper-zh/_templates/cumcm/，执行"
    echo "      cp skills/comp-paper-zh/_templates/cumcm/*.cls skills/comp-paper-zh/_templates/cumcm/*.sty paper/"
    echo "   ② 其他赛事：从赛事官方渠道获取模板文件夹放入 $TMPL_BASE/<赛事名>/ 后重跑"
    exit 1
fi

# Rename to main.tex if needed

[ -f paper/main.tex ] && echo "Template copied: $(wc -l < paper/main.tex) lines" || echo "ERROR: template not found!"

```

**⛔ 模板复制后立即验证（必须通过才能继续）：**

```bash

python skills/_utils/template_integrity_check.py --fingerprint --template-base skills/comp-paper-zh/_templates 2>/dev/null || python academic-toolkit/skills/_utils/template_integrity_check.py --fingerprint --template-base academic-toolkit/skills/comp-paper-zh/_templates 2>/dev/null || python ../../skills/_utils/template_integrity_check.py --fingerprint --template-base ../../skills/comp-paper-zh/_templates

```

`--fingerprint` 按 documentclass 行定位模板原文，对比 paper/main.tex 前 20 行 preamble：差异过大（>10 行）说明骨架被重写——必须从模板重新复制、只替换占位符（字体/边距/编号/引用格式都在 preamble 里调好，重写必炸）。

Read the copied template to understand its structure before writing:

```bash

cat paper/main.tex

```

**⛔ 你必须完整读取 main.tex 模板内容。后续写章节时，只修改 sections/*.tex 文件，不要重写 main.tex。**

Use the template as-is. Only modify:

- Replace bracket placeholders (`[论文标题]`, `[中文摘要内容]`, etc.) with actual content

- Replace `\input{sections/...}` filenames if your section files have different names

- Fill in the abstract and keywords

**⛔ CRITICAL TEMPLATE RULES (violation = broken PDF):**

1. **NEVER rewrite main.tex from scratch** — the template has 100+ lines of carefully tuned preamble (fonts, margins, section numbering, citation format). Writing from scratch will break fonts, margins, and formatting.

2. **NEVER replace `\listoftables`/`\listoffigures` with hand-written text lists** — the template uses LaTeX auto-generated lists. If you write "表1.xxx\n表2.yyy" manually, the list won't update when tables change.

3. **NEVER add a separate cover page for MathorCup** — MathorCup 官方格式没有独立封面。队伍编号表格+标题+摘要都在第一页。不要自己加 `\maketitle` 或写一个大标题封面。直接用模板里的格式：表格 → 分隔线 → 标题 → 摘要。

4. **NEVER change the cover page year/届数 format** — replace `[竞赛年份]` with the actual year (e.g., `2026`), `[届数]` with the actual number (e.g., `十二`).

5. **Verify after writing**: `diff paper/main.tex` against the template — only bracket placeholders and `\input` lines should differ.

6. **MathorCup 模板验证**：检查 main.tex 使用 `\documentclass{MathorCupmodeling}`，`\bianhao{}`/`\tihao{}`/`\timu{}` 已填写。

7. **华中杯模板验证**：检查 `\documentclass[withoutpreface,bwprint]{cumcmthesis}` 未被修改，摘要使用 `\begin{abstract}...\keywords{}\end{abstract}` 环境，参考文献使用 `\begin{thebibliography}{99}...\end{thebibliography}`，附录使用 `\begin{appendices}...\end{appendices}`，不要自己加 `\usepackage{geometry}`。

**⛔ 华为杯官方格式硬约束（版式 / 摘要 / 引用 / 提交）** —— 完整证据见
[`references/huawei-official-format.md`](references/huawei-official-format.md)，
机检字段同步在 `engine/modex-core/comp_rules.json` → `contests.comp_huawei` profiles 约束带（`hw-*` 条，vintage 2026-23rd）。
写作完成后**逐项自检**：

| 项 | 硬约束 | 自检命令/位置 |
|---|---|---|
| 页边距 | 上下左右各 **≥ 2.5 cm**（22届口径/工程保守值，23届官方无页边距条款 → comp_rules `hw-margins: unknown`；gmcmthesis.cls 默认已修 25mm，勿回退） | `grep -n "geometry" paper/main.tex` / `gmcmthesis.cls` |
| 页眉 | **禁止有页眉** | PDF 顶部 50pt 区无文字 |
| 页码 | 自**摘要页**起、页脚中部、阿拉伯数字从 1 连续 | PDF 逐页页脚 |
| 首页 | 封皮不可删，4 logo 不可替换；**除首页外不得出现单位/姓名/队号**（否则论文无效） | 全文检索校名/姓名/队号 |
| 摘要 | **≤ 2 页**、**无需英文**、必须含 **建模思路/主要方法/模型/结果与结论/创新点/关键词** 六要素 | 摘要页 PDF 提取 |
| 字体 | 题目三号黑体、一级标题四号黑体（均居中）、其余小四宋体、单倍行距 | cls 设置 |
| 参考文献 | 方括号编号、**按正文引用次序**；书籍/期刊/网络三种表述；**引用程序须注明来源**（未标注且雷同按抄袭认定） | 文末 + 正文引用处 |
| 承诺书 | 官方模板无承诺书页（21届模板实测；23届 `hw-pledge: unknown`，实践口径不变：校级材料不入论文） | 前 3 页不得命中「承诺书」（命中转人工确认） |
| 页数 | 当届 **unknown**（50 为历届内部口径不作官方主张；本轮任务口径经任务级覆盖通道下发） | `quick_gates --compliance-profile comp_huawei` |

8. **⛔ 华为杯专属：模板与标题约束（gmcmthesis，只对华为杯生效）**：

   标题机检（仅 `CONTEST_ID=comp_huawei` 时跑，其他竞赛跳过保持原本行为）：

   ```bash

   python skills/_utils/template_integrity_check.py --full 2>/dev/null || python academic-toolkit/skills/_utils/template_integrity_check.py --full 2>/dev/null || python ../../skills/_utils/template_integrity_check.py --full

   ```

   脚本拦两类标题问题并打印赛题原文前几行供对照：① `\title{}` 含 `\\` 强制换行（gmcmthesis v1.5.0+ 已支持按宽度自动换行，多行字号会不一致）；② AI 风格自创标题（"基于 X 的 Y / Y 的研究 / Y 的探索与应用 / Y：一种基于 X 的方法"）。

   **⛔ 华为杯标题硬约束（其他竞赛保持原本，不受影响）**：

   - `\title{...}` 必须使用赛题官方原标题（从 `user_data/*_extracted.txt` 抄），严禁自创 "基于 X 的 Y"

   - 不要在 `\title{}` 里写 `\\` 换行（cls v1.5.0+ 已支持自动按宽度换行，多行字号保持一致）

   - 题目长就一行写完，模板自动换行渲染

9. **五一杯模板验证**：检查承诺书页完整保留，摘要使用手动排版（`\noindent \textbf{关键词：}` 在上，`\noindent \textbf{摘\quad 要：}` 在下，不用 `\begin{abstract}` 环境），参考文献使用 `\begin{thebibliography}`，附录第一节是文件列表表格。**⛔ 五一杯额外检查**：(a) 不要加 `\usepackage{cite}`（和 natbib 冲突会导致编译错误），(b) 不要重复加载 `\usepackage{subcaption}` 和 `\usepackage{float}`（cls 已包含），(c) 不要加 `\maketitle`（五一杯用手写承诺书页，不用 cls 的 maketitle），(d) 不要删除 `withoutpreface` 选项。

The cover page uses `\fzxbsong` (方正小标宋) and `\fsgb` (仿宋GB2312) fonts with `\cline{2-2}` underlines in a tabular. These fonts have fallback definitions — if the .ttf files are not installed, they fall back to `\heiti` and `\fangsong`.

When replacing cover page placeholders, ONLY change the text inside `[...]` brackets. Do NOT touch `\cline{2-2}`, `\\`, `&`, or any LaTeX commands:

```latex

% Template has (和 cover station.tex 格式一致):

参赛学校：&[学校名称]\\\cline{2-2}

% Replace ONLY the bracket text:

参赛学校：&某某大学\\\cline{2-2}

% NEVER remove \cline{2-2} (creates underline) or & (column separator)

```

Do NOT modify:

- `\documentclass` line (font size, paper size)

- `\usepackage[...]{geometry}` (page margins)

- `\ctexset{section=...}` (chapter numbering format)

- `\pagestyle` / `\fancyhf` (header/footer)

- `\usepackage[...]{natbib}` or `\usepackage[...]{gbt7714}` (citation format)

- Cover page structure (封面布局)

- `\listoftables` / `\listoffigures` (表格与插图清单 — 自动生成，不要手写)

- Anything before `\begin{document}` (preamble)

- The cover page, abstract, TOC, and bibliography sections in main.tex — only replace placeholder text within them

Write all chapter content in separate `paper/sections/*.tex` files. The main.tex `\input{sections/...}` lines load them automatically. Do not paste chapter content directly into main.tex.

If you need to add packages, add them after the existing `\usepackage` block, before `\begin{document}`.

Do not write main.tex from scratch — the template handles fonts, spacing, margins, citation format, headers/footers.

Note: citation command depends on the template. **stats / huawei / dongsansheng / apmcm_zh / mathorcup / huashubei** load `natbib` with the `super`(or `\setcitestyle{super}`) option → use `\cite{key}` directly (auto-superscript). **cumcm / wuyi**（含按派发表落到 `_templates/cumcm/` 的 huazhong）carry **no natbib load** — they define a manual `\@cite` superscript hack → use `\cite{key}` directly (superscript automatic). **apmcm / changsanjiao / diangongbei / shuweibei / mcm** use manual thebibliography → use `\cite{key}` directly. ⛔ `\upcite` is ONLY defined in cumcm / huazhong / wuyi / dongsansheng — do NOT use `\upcite` in any other template (undefined → compile error); use `\cite` there.

Do not redefine LaTeX built-in commands (`\sin`, `\cos`, `\tanh`, `\log`, `\exp`, `\max`, `\min`, etc.) in math_commands.tex.

### Step 2: Abstracts

**⛔ CRITICAL: Do NOT write the abstract now.** Skip this step entirely. Write a placeholder `[摘要待正文完成后填写]` in the abstract section. The abstract MUST be written LAST (after Step 5) because it needs specific numerical results from all chapters. Writing it first = making up numbers.

Come back to fill the abstract in Step 5 (final check), after all body chapters are complete. At that point, read RESULTS.md and all section .tex files to extract the actual numbers.

<abstract_format>

**⛔ 摘要动笔前先读语料**：读 `data/award_paper_exemplars.json` 同赛事 2-3 篇结构化条目 + `skills/award-paper-mining/data/abstract_golden_structure.md`（摘要黄金结构）与 `sentence_pattern_library.md`（句式库），模仿其信息密度与节奏，禁止照抄措辞。下述规则是与语料对标后的底线要求，不是替代。

The template uses manual typesetting for abstracts. Do not use two `\begin{abstract}` environments — ctexart shows "摘要" as title for both.

**⛔ 华中杯例外**：华中杯模板基于 `cumcmthesis` 文档类，使用 `\begin{abstract}...\keywords{}\end{abstract}` 环境。不要改成手动排版格式。正确写法：

```latex

\begin{abstract}

[中文摘要内容，600-800字，写满一整页]

\keywords{[关键词1]\quad [关键词2]\quad [关键词3]}

\end{abstract}

```

**⛔ 五一杯说明**：五一杯模板有承诺书页（第一页）和封面页（第二页）。**五一杯摘要使用手动排版（不用 `\begin{abstract}` 环境）**：关键词在上（`\noindent \textbf{关键词：}...`），摘要在下（`\noindent \textbf{摘\quad 要：}`）。这是五一杯官方格式，跟国赛/华中杯不同。承诺书页不要删除。

Correct format for cumcm/stats templates (already in template):

```latex

% === 中文摘要 ===

\begin{center}

{\zihao{3}\heiti 摘\hspace{2em}要}

\end{center}

\zihao{-4}\songti

[中文摘要内容，600-800字，写满一整页]

\noindent\textbf{关键词：}...

% === 英文摘要（新页）===

\newpage

\begin{center}

{\zihao{3}\bfseries Abstract}

\end{center}

[English abstract, 300-400 words, faithful translation]

\noindent\textbf{Keywords:} ...

```

**数模竞赛摘要（国赛/MathorCup/APMCM/五一杯等通用）**: 600-800 字（硬范围，目标 680-760；单一事实源见 `_utils/abstract_writing_contract.md`；统计建模特例 500-700 字）, every sub-problem must have specific numerical results（整篇合计 ≥3 个带单位/精度的真实数值结果）。

⛔⛔ **必须按问题分段，绝不允许所有问题挤成一大段。** 段骨架：

- 第 1 段：背景概述 + 整体建模思路

- 第 2 段起：**每个"针对问题 X"独占一段**（方法 + 具体数值结果）

- 末段：模型评价与推广

- **段间强制用 LaTeX 空行分隔**（源码里空一行 = 一个新段落）。五一杯手动排版摘要，分段规则同样适用。

⛔⛔ **摘要关键内容加粗（只在摘要正文，用 LaTeX `\textbf{}`）**：评审快速扫读摘要抓重点，把最关键的方法与结果加粗是加分项。**只加粗以下三类"结论锚点"**：

1. **关键结果数值**（最终答案数字）：如 `\textbf{2376.8}`、`\textbf{98.7\%}`、`\textbf{12.4 km}`（注意 `%` 在 LaTeX 里要写 `\%`）

2. **核心方法/模型名**：如 `\textbf{NSGA-II}`、`\textbf{灰色预测 GM(1,1)}`——**每个方法名只在首次出现或结论处加粗一次**，不是每次提到都加

3. **关键结论的核心名词**

⛔ **加粗铁律（防加粗过多反而杂乱，宁少勿多）**：

- 每段 **1~3 处**，全篇 **≤ 12 处**。超了就是错。

- **禁止**：整句 `\textbf{}`、背景铺垫加粗、连接词加粗、同一方法名反复加粗。

- ⛔ 只用 `\textbf{}`（LaTeX），**不要用 markdown `**xxx**`**（LaTeX 下 `**` 不渲染成粗体、会原样显示）。

- ⛔ **不影响关键词行**：`\textbf{关键词：}` 那个加粗是标签本身，照旧。

- ⛔ `\textbf{}` 只包文字，**数字本身必须仍从正文如实摘出**，不能因加粗改动或编造。

- ⛔ 五一杯等手动排版摘要同样适用（`\textbf{}` 在正文任意位置都合法）。

正例：`本文构建 \textbf{NSGA-II} 多目标模型，求得最优成本 \textbf{2376.8 万元}，较基线降低 \textbf{12.3\%}。`

⛔ **硬约束：一个自然段里绝不允许出现两个及以上"针对问题"。** 正反例：

```latex

（正确 ✅ — 每个"针对问题 X"之间空一行，各自独立成段）

本文针对……建立了……模型。

针对问题一，构建……模型，采用……算法求解，最优解为……，适应度达 0.917。

针对问题二，构建……模型，……MAPE 由 29.48\% 降至 14.93\%。

针对问题三，……预测结果为 952.8、1570.5、11030.9。

灵敏度分析表明……，模型评价显示……。

```

```latex

（错误 ❌ — 问题二/三挤在同一段，评委无法按问题快速定位）

针对问题二，构建……模型，MAPE 14.93\%。针对问题三，预测结果为 952.8、1570.5。

```

⛔ **写完摘要后跑自检（检测→修复→再检测闭环）**：

```bash

python skills/_utils/abstract_paragraph_check.py 2>/dev/null || python academic-toolkit/skills/_utils/abstract_paragraph_check.py 2>/dev/null || python ../../skills/_utils/abstract_paragraph_check.py

```

检测"针对问题 X"是否每问独立成段（含定位逻辑：abstract 环境 → 手动排版摘要段 → sections/ 兜底）。exit 1 时在每个"针对问题 X"前补一个 LaTeX 空行拆成独立段落，重跑直到输出"✓ 摘要按问题分段正确"，方可进入下一步。

> 其余摘要质量线由机器分工：「随着…的发展」式 AI 套话开头由引擎 `ai_flavor` 强制闸硬拦——现在就别写；摘要加粗克制度由 `abstract_emphasis_check`（writing_check.sh 全家桶）把关；字数/六要素/分段骨架的唯一事实源见 `_utils/abstract_writing_contract.md`。

**⛔⛔ 丰满模式摘要标准（华为杯默认 / 任意竞赛开启丰满模式时生效，1500-2200 字，跨两页）**：

⛔ **触发条件**（赛事判据=下发的 `CONTEST_ID`；用户开关才读 AGENTS.md，不用文本猜赛事）：

- `CONTEST_ID = comp_huawei` — 华为杯默认走丰满模式

- `丰满模式` / `rich_mode` — 任意竞赛通过前端"丰满模式"开关启用（用户开关，读 AGENTS.md 合法）

**触发自检**：`CONTEST_ID = comp_huawei`，或 AGENTS.md 含 `丰满模式`/`rich_mode` 用户开关 ⇒ 摘要按 1500-2200 字 + 6 项要素 + 5 段骨架写。

丰满模式下官方允许/鼓励摘要跨两页，**字数压在通用 600-800 字会让评委觉得工作量不够**。

**篇幅与结构（强制）**：

- **总字数 1500-2200 字**（不算空格、空行），允许跨 2 页，**不要刻意压缩到一页**

- **每子问题段 280-400 字**（5 个问题 → 1400-2000 字主体 + 100-200 字开头背景 + 关键词）

- 段间用 LaTeX 空行分隔，**每段独立成块**，便于评委按问题快速定位

**6 项展示要素清单（每段必须命中）**：

| 要素 | 反例（AI 常犯） | 正例（华为杯优秀作品） |

|---|---|---|

| **1. 问题背景开头（写具体矛盾）** | "随着...的发展" 式空背景（AI 套话，ai_tell_check 硬拦） | 首句直接给现实矛盾或数据事实："...在...场景下存在...瓶颈，...作为核心组件，其[关键指标]直接制约[宏观目标]。" |

| **2. 方法链叙述（因果衔接）** | 只甩结论"构建了 XGBoost 三分类模型"（无过程无取舍） | 方法按因果连缀成句："噪声叠加导致直接拟合失真，故先以傅里叶变换分离趋势项并提取 X/Y/Z 特征；为避免单模型偏差，建立 A/B/C 三模型对比，以混淆矩阵和交叉验证择优"（不用"首先/接着/最后"机械过渡词） |

| **3. 候选方法对比** | 只讲最优方案（XGBoost） | 列 2-3 个候选方法 + 选定 + 选择理由（MLP / 随机森林 / MLP-RF 加权集成；Solow / 二次多项式 / 温度饱和） |

| **4. 中间过程数值** | 只给最终 MAPE/R² | 加候选模型对比数（"MAPE 由 29.48% 降至 14.93%"、"参数估计值分别接近 1.5、1.4、1.5"） |

| **5. 附件预测结果数值** | 只说"已对附件三 400 样本完成预测" | **列若干代表性预测值**："部分模型预测结果为 952.8 W/m³、1570547.8 W/m³、11030.9 W/m³、..."（4-10 个数值） |

| **6. 可视化手段提及** | 不提图表 | "借助混淆矩阵和残差图"、"对磁通密度可视化"、"部分结果以表格呈现" |

**关键词数量**：8-12 个，**算法名 + 数学工具 + 模型族**全列，每个 `\quad` 分隔

- ❌ 反例（5-6 个）：磁芯损耗 XGBoost Steinmetz方程 方差分解 NSGA-II

- ✅ 正例（8+ 个）：多层感知机 随机森林 最小二乘法 温度饱和模型 方差分析（ANOVA） 多目标优化 双目标-单目标转化 粒子群算法

**⛔ 关键词行约束（国赛强制）**：`\keywords{...}` 或 `\noindent\textbf{关键词：}...` 中所有关键词加上 `\quad` 分隔后，**必须在一行内排完，不得换行**。若关键词过多导致换行，应精简至 6-8 个核心关键词，确保单行容纳。自检方法：编译 PDF 后检查关键词行是否有换行，若有则减少关键词数量。

**5 段华为杯摘要骨架模板**（按这个填）：

```latex

% 第 1 段：问题导入（150-200 字）

[现实场景中的具体矛盾或数据事实：...在...场景下存在...瓶颈]，

[问题对象]作为[系统]中的核心组件，其[关键指标]直接影响[宏观目标]。

本文针对[赛题 5 个子问题]，基于[数据集规模]，建立了[方法链概述]。

% 第 2 段：问题一（280-400 字，过程式 + 候选对比 + 数值）

针对问题一[一句话交代：要解决什么、难点在哪]。考虑[约束/难点]，建立 [方法 A、B、C] 等模型进行对比，

最终选用 [选定方法] 并通过 [评估方式] 验证。结果表明 [关键数值1, 2]，

[附件二/三/四 的具体结果如：分类为正弦波 20 个、三角波 44 个、梯形波 16 个]。

% 第 3-5 段：问题二、三、四、五，结构同问题一

% 第 6 段（可选）：模型评价与意义（80-150 字）

% 关键词（8-12 个，\quad 分隔）

\noindent\textbf{关键词：} 算法名1 \quad 算法名2 \quad ... \quad 数学工具N

```

⛔ **华为杯摘要写作禁区**：

- ❌ 把摘要压到 1 页：评委一眼判工作量不够

- ❌ 只讲最终方案不讲候选对比：评委看不到方法选择的合理性

- ❌ 关键词只 5-6 个：丧失关键词检索曝光

- ❌ 用「随着…的发展」式空背景开头：AI 套话（ai_tell_check 硬拦）；背景必须写具体矛盾或数据事实

- ❌ 不列附件预测代表数值：评委无法快速核验工作量

**统计建模摘要**: 500-700 字, aim to fill most of one page but leave 3-4 lines margin at bottom — overflowing onto a second page looks worse than being slightly short. Content chain: 研究背景与意义 → 现有方法不足 → 本文方法 → 数据来源与处理 → 关键数值结果 → 应用价值与政策建议. English abstract: 350-500 words, same structure and all numerical results, also fit on one page.

</abstract_format>

### Step 3: Figure inventory + mandatory embedding plan

Before writing any chapter, build a complete inventory of available figures:

```bash

ls figures/*.pdf figures/TABLE_*.tex figures/TABLE_*.md figures/tikz_*.pdf 2>/dev/null

cat figures/latex_includes.tex 2>/dev/null   # figure→PDF 映射真源：每个 \begin{figure} 块从这里复制

```

**⛔ MANDATORY: Build a FIGURE EMBEDDING PLAN before writing any chapter:**

```

FIGURE EMBEDDING PLAN:

1. fig_desc_stats.pdf → 第三章 描述性统计 → caption: "图X 核心变量描述性统计分布"

2. fig_model_comparison.pdf → 第四章 模型对比 → caption: "图X 模型性能对比雷达图"

3. TABLE_regression.tex(PDF模式) / TABLE_regression.md(Word模式) → 第四章 回归分析 → caption: "表X 回归分析结果"

4. tikz_diagrams.pdf (几何/算法/架构 TikZ, from latex_includes.tex) → 对应章节 → caption: "图X 弦长递推几何关系示意"

```

> 表格按输出模式选格式：PDF 模式 `\input{figures/TABLE_*.tex}`；Word/docx 模式 `cat figures/TABLE_*.md`。figures/ 里有几个 TABLE 文件就嵌入几个，一张不漏。

**Rules:**

- **⛔ 图表嵌入受引擎 `figure_narrative` 强制闸**：finish 时全量重扫正文，凡「全文零 `\ref` 引用」的**零引用孤儿**（旁有叙述不豁免——"如下图所示"不算引用）与「被引用但零解读」的图直接拒绝完成（真实终版曾 20+ 图中 11+ 张孤儿——图海堆砌是图表 AI 味首因）。嵌入每张图时**同步写两句**：引用句（"图~\ref{fig:xxx} 显示……"）+ 解读句（该图揭示的结论）。没有解读可写的图不要嵌入。

- **⛔ 图表 caption 必须是中文**（中文论文）。如果 `latex_includes.tex` 里的 caption 是英文，嵌入时必须翻译成中文

- **⛔ caption 要短**：流程图/路线图/架构图的 caption 只写图的类别/主题，**≤ 20 个汉字**（如「问题一求解流程图」「整体技术路线图」）。若上游 caption 是一长串方法描述，嵌入时必须精简成短标题，详细说明放进正文，**禁止让 caption 超过一行**

- **⛔ 必须使用 `latex_includes.tex` 里的 figure 代码块**，不要自己写 `\includegraphics`。直接复制整个 `\begin{figure}...\end{figure}` 块，只改 caption 为中文

- **⛔ TikZ 图必须嵌入**：`latex_includes.tex` 里每个引用 `tikz_diagrams.pdf` / `tikz_*.pdf` 的 `\begin{figure}...\end{figure}` 块都要复制到对应章节，一张都不能漏

- **⛔ 图片路径必须是 `../figures/xxx.pdf`**（因为 sections/ 在 paper/ 下面）

- Only embed figures whose PDF files actually exist — do not create figure environments for PDFs that don't exist

- **⛔⛔ 图要由论证自然引出，而不是套模板句（铁律）**：每张图都要嵌在行文里，让正文的论证需要"顺理成章地"引出它，读者读到这里正好需要看这张图。判断标准只有一个——**读起来是流畅的承上启下，不是逐张贴标签**。

  - **✅ 要达到的三个目的（是目的，不是句式模板，更不是每张图都要照抄的固定结构）**：让读者明白 ①这张图在讲什么、②它承接上文的什么、③它支撑什么结论。怎么把这三点织进段落、按什么顺序、用什么句式，由你按当时的行文自由安排——可以先给结论再放图印证，可以先描述现象再引出图解释。**要变的是"怎么写"（句式、切入角度、顺序），不变的是"写多深"。**

  - **⛔⛔ 图后解读的深度底线（铁律，本次要根治的第二个核心问题）**：每张图后面的解读**绝不能一句话带过**（像"见图 24：盘入螺线、两段圆弧与盘出螺线在切点处光滑连接"这样单句收尾就是失败）。每张图的配文（图前引导+图后解读合计）**必须落地这三样，缺一不可**：①**具体数值**——从图里读出的关键数字（极径 4.229m、缩短 7.59%、峰值 1.72 m/s 等），不是泛泛说"趋势明显"；②**对比或趋势**——和基准/其他方案/前一问的对照，或量沿某轴怎么变；③**推论或衔接**——这张图证明了什么、暴露了什么瓶颈、引出下文哪一步。做不到这三样，说明这张图对论证没用，那就不该放。

    - **❌ 敷衍反例（现在的通病，禁止）**：「弧长优化过程与对比见图 25：多起点收敛到同一最优邻域，最优值稳定低于基准。」——只有一句、没有数值、没有量化对比、戛然而止。

    - **✅ 标杆正例（要模仿的充实度）**：「由图 15 可见，碰撞半径随螺距增大严格单调下降：螺距由 0.4m 增至 0.55m 时，碰撞半径由 7.04m 单调降至 2.289m；数据点与 R_t=4.5m 阈值线的交点恰对应临界螺距 p_min=0.448m，交点左侧盘不进边界、右侧可盘入。曲线在交点附近斜率适中，说明临界螺距的反演稳定、二分求根条件良好。」——数值、单调趋势、阈值交点、稳定性推论俱全，且句式自然不套路。

  - **⛔⛔ 严禁句式套路化（本次要根治的核心问题）**：绝对不许把每张图都写成同一个骨架的句子，尤其是「【图类型】（如图 N）+ 动词 + 一句结论」这种统一开头（例："瀑布图（如图 33）把……"、"雷达图（如图 34）对比……"、"热力图（如图 35）表明……"——连续几张图都这么起头就是失败）。**相邻的图、同一节里的图，引导句的切入角度和句式必须换着来**：有的从上文结论切入、有的从要回答的问题切入、有的从图里的反常现象切入、有的干脆把图揉进正在展开的论述里不单独起句。像好论文那样叙述，而不是给每张图发一张格式一样的说明卡。

  - **✅ 图号必须显式引用（学术规范，与"去套路化"并行不悖）**：每张图在正文里都必须被明确点名（"图 N"），让读者能把这段文字准确对应到是哪张图——这是数模/论文的硬规范，不能为了避免套路就把图号删掉。**要变的是引用的句式和位置，不是要不要引用**。至少在下面几种切入方式之间轮换，相邻两张图不要用同一种：

    - 句首带出：「图 3 所示流程中，第三阶段的双阈值门控……」

    - 句中括注：「……该前提基本成立（见图 2）：传播度与文本强度……」

    - 动词引导：「观察图 4 中的三条收敛曲线，其差异集中体现于……」

    - 图作主语：「图 5 对比了本文方法与基线在四项指标上的表现……」（**限量：整节最多一次，绝不能当默认开头；相邻两张图都以「图 N…」起句直接判违规**）

    - 后置印证：「……这一结论在图 6 中得到印证。」

    要点：图号一定要出现，但别让每张图都用「图 N + 动词 + 一句结论」这一种开头。

  - **⛔ 严禁套话占位**：像"如图 X 所示"、"下图展示了实验结果"、"图 X 是本文的流程图"这种不含任何实质信息、换成任何一张图都成立的句子，等于没写。说不出这张图独有的内容和作用，就说明这张图对论证没用，那就不该放（"放进去要有用，不然不如不放"）。

  - **⛔ 术语与代号必须通俗化**：正文首次出现的专业术语、内部代号、变量简写（如 C4、C14、blend、脊线分布、弱监督自洽上界、C~密度），必须先用一句大白话说清"它是什么/衡量什么"再用；严禁把建模流水线里的内部代号、临时命名不加解释直接搬进正文——论文是给评委看的，不是给流水线看的。

  - **⛔ 图注（caption）只写简短标签（中文主体 ≤20 字，不含"图 N"编号）**：`\caption{}` 只写这张图是什么的名词短语；判据、参数、坐标含义、结论移到正文那段图解读里，别塞进题注（否则图下方折成多行很难看）。反例 `\caption{覆盖半径几何示意：站点为圆心、R=3km 覆盖圆、区域出车距离与响应时间判据}` → 正例 `\caption{站点覆盖半径几何示意}`。详见 `_utils/writing_rules.md` 的图注长度总则；编译阶段会扫 caption 长度，超限判违规。

  - **⛔ 严禁两个 `\begin{figure}...\end{figure}` 环境直接相邻**（`\end{figure}` 后紧跟 `\begin{figure}`、中间没有正文段落）。若确需连续展示两图，必须在它们之间写一段过渡正文，说清楚两图之间的逻辑关系（为什么先看这张再看那张）。

**⛔⛔⛔ DrawIO 图嵌入规则（最容易被遗漏，必须逐条检查）：**

DrawIO 图（技术路线图、求解流程图、Pipeline 图等）的 `\begin{figure}...\end{figure}` 代码块在 `latex_includes.tex` 的**末尾部分**（由 paper-figure-drawio 步骤追加）。你必须把它们嵌入到正确的章节：

| DrawIO 图类型 | 嵌入位置 | 章节文件 |

|--------------|---------|---------|

| 技术路线图 (fig_roadmap) | 问题重述章节末尾 | `1_restatement.tex` 或 `1_introduction.tex` |

| 子问题求解流程图 (fig_flow_q1/q2/q3) | 对应子问题的"模型建立"小节开头，先写 2-3 句引导文字（概述本问题的求解思路和主要步骤），再放流程图 | `5_problem1.tex`、`6_problem2.tex` 等 |

| 数据处理 Pipeline (fig_pipeline) | 数据预处理章节 | 数据处理相关章节 |

| TikZ 几何/算法图 (tikz_diagrams.pdf) | 几何示意图→对应子问题章节开头；算法流程图→模型建立小节 | 对应子问题/模型章节 |

**⛔⛔ 铁律：子问题流程图必须分散到各自的问题章节，严禁全部堆在"问题分析"(2_analysis) 一章。**

把 fig_flow_q1~q5 五张图全塞进问题分析章节，是最常见也最难看的错误：一个章节连插 5 张大图，LaTeX 浮动机制会把它们全推到章节开头层层堆叠，正文被挤到后面，排版严重失衡。正确做法：`fig_flow_q1` → `5_problem1.tex`、`fig_flow_q2` → `6_problem2.tex`、…、`fig_flow_q5` → `9_problem5.tex`，每章一张、紧跟该问题的引导文字之后。问题分析章节(2_analysis)**最多只放整体技术路线图 fig_roadmap 一张**，其余流程图一律不许出现在该章节。

**写完所有章节后（以及每写完一章），运行布局检查：**

```bash

python skills/_utils/figure_layout_check.py paper/ 2>/dev/null || python academic-toolkit/skills/_utils/figure_layout_check.py paper/ 2>/dev/null || python ../../skills/_utils/figure_layout_check.py paper/

```

覆盖三件引擎不查的事：① `figures/*.pdf` 全部被正文引用（`figure_narrative` 引擎闸只查"已嵌入正文"的图——零引用孤儿与零叙述都拦，查不到从未嵌入的文件）；② FIGURE_MANIFEST 对账——规划了几张就必须产出几张并嵌入几张，一张不漏；③ 流程图堆叠——问题分析章节里 `fig_flow_qN` ≥2 张即违约（见上方铁律）。任何 ❌ 立即修复后再继续写下一章，不要等到最后。

TikZ 图通过 `latex_includes.tex` 里的 `\includegraphics{tikz_diagrams.pdf}` 图块嵌入（不要用 `\input`），位置同上表。

> 图连排（两个 figure/table 环境相邻、中间无正文）若还零 `\ref` 引用，由 `figure_narrative` 引擎闸在 finish 全量重扫直接拒绝完成；被引用的连排引擎不拦——写的时候就守上方连排禁令，别等闸拦。

### Step 3.5: 文献预检索（写正文之前必须完成）

**⛔ 在写任何 \cite{} 之前，必须先建立已验证的文献池。** 往届优秀论文（`data/historical_papers.md` 与本地优秀论文页面图）仅作写法/模式借鉴——其无著录信息，禁止据此编造 bib 条目。

```bash

PYTHON=""; for _c in "$MH_PYTHON" python python3; do [ -z "$_c" ] && continue; if $_c -c "import sys" >/dev/null 2>&1; then PYTHON="$_c"; break; fi; done; [ -z "$PYTHON" ] && PYTHON=python

mkdir -p _tmp

# 根据论文主题搜索真实论文，建立引用池

# 示例（根据实际选题调整）：

#   $PYTHON "$SCHOLAR_SCRIPT" bibtex "你的核心方法关键词" --max 5

#   $PYTHON "$SCHOLAR_SCRIPT" bibtex "你的研究领域关键词" --max 5

```

搜索后创建 `_tmp/_verified_refs.txt`，写正文时只引用池子里的论文。需要新引用时先搜索验证再加入池子。

**兜底**：如果 `scholar_fetch.py` 搜不到或 `match_label="low"`，用 WebSearch 在 Google Scholar / Semantic Scholar 网站上搜索，手动核实标题+作者+年份后再加入池子。

### Step 4: Write each chapter

#### 先把这一章写好（写完再检查，检查不能代替写好）

本章的产出是给评委读的论文，不是给闸门读的报文。下面六条是获奖论文的共同写法（提炼自 `_utils/human_competition_paper_style.md`，动笔前通读该文件；同赛事范文对照 `data/award_paper_exemplars.json` 取 2-3 篇）：

1. **每段先给结论再给推导。** 段首句是本段要证明的判断（"问题三的瓶颈在充电窗口而非机队规模"），后续句子是支撑它的推导与数值。评委扫段首即可跟上全文逻辑。
2. **数值嵌进叙述，不罗列。** 把数字写进因果句（"能量约束把可行载荷压到 2.31 t，比质量上限低 18%"），而不是"结果如下表"后甩一串数。表格承载全量数据，正文承载带方向和量级的判断。
3. **章首段交代本章任务与路线。** 用 2-3 句说清本章解决哪个问、用什么模型族、按什么顺序展开——这是导航，不是背景重述。
4. **写"为什么"不写"是什么"。** 假设要给理由（"忽略风载，因为巡航段风速上限 6 m/s 对能耗影响 <3%"），模型选择要给对比（为什么选 MILP 而不是启发式），符号表之外的记号首次出现即定义。
5. **图题写发现。** 图题陈述该图揭示的结论（"误差随噪声水平升高呈指数增长"），"XX 对比图 / XX 结果图"式空标题禁用；图在正文中必须有指代句和解读段，不能"见图自明"。
6. **段间衔接靠因果不靠连接词。** "首先/其次/最后"机械过渡链是 AI 痕迹；自然段之间用内容上的承接（上一段的结论是下一段的出发点）。

数字纪律与结果读取方式见下方 CRITICAL 块——先读数据，再按上面六条写。

**⛔ CRITICAL: ALL numerical results in the paper MUST come from `figures/*.json` or `RESULTS.md`.**

**⛔ NEVER `cat figures/*_results.json`.** These result files often contain full-precision time-series arrays (tens of MB / hundreds of thousands of lines); reading them whole blows up the context — local models fail outright, and GPT-via-transit chokes on protocol translation of the oversized payload and stalls on repeated `api_retry`. **The paper text only uses scalar values (fitness / optimal solution / solve time / metrics); the giant arrays are for figures, not prose.** Before writing any result chapter, run the `summarize` script below to get a KB-level overview (scalars shown verbatim — zero precision loss — only big arrays compressed to "length + range + first 3 samples"):

```bash

cat RESULTS.md

python skills/_utils/summarize_results.py 2>/dev/null || python academic-toolkit/skills/_utils/summarize_results.py 2>/dev/null || python ../../skills/_utils/summarize_results.py

```

Every scalar you need is in `RESULTS.md` or the range/sample of the summary above. If one scalar isn't fully shown, fetch just that value with `python3 -c "import json;d=json.load(open('figures/all_results.json'));print(d['key'])"` — still never read the whole file. Copy the exact numbers into the LaTeX text. Do NOT round differently, do NOT estimate, do NOT make up numbers that "look reasonable". If a number is not in the data, it cannot appear in the paper.

**⛔ 动笔前先读获奖语料（六大板块通用：摘要/问题分析/建模推导/求解/检验/结论，一个都不能跳）：**

写每个板块前，读 `data/award_paper_exemplars.json`（国赛优秀论文范文精选包索引，2021-2025 共 62 篇，`priority_25` 为优先样本）中**同赛事/同题型 2-3 篇**的结构化条目，并对照 `skills/award-paper-mining/data/` 对应库取该板块的写法基准：

| 板块 | 对应语料 |
|---|---|
| 摘要 | `abstract_golden_structure.md`（摘要黄金结构） |
| 全文句式与段落节奏 | `sentence_pattern_library.md`（句式库） |
| 图表使用与版面 | `figure_table_conventions.md` + `typography_spec.md` |
| 原文对照 | `assets-local/award-papers/` 按 `all_by_year` 索引取本现代码页 |

模仿其信息密度与节奏（一段承载几个论点、数值怎么嵌进叙述、推导怎么铺开）；**禁止照抄措辞**——照抄同时踩查重与 AI 痕迹两道闸。语料索引缺席或字段不全时如实说明并跳过对标，不虚构读过。

**⛔ 数模竞赛（cumcm/huawei/mathorcup）必须严格按模板的章节顺序写：**

```

1_restatement.tex  — 问题重述（用自己的话重述，不是抄题目）

2_assumptions.tex  — 模型假设（5-7 条，每条有内容+合理性说明）

3_symbols.tex      — 符号说明（⛔ 见下方格式规则）

4_problem1.tex     — 问题一的建模与求解

5_problem2.tex     — 问题二的建模与求解

6_problem3.tex     — 问题三的建模与求解

7_sensitivity.tex  — 灵敏度分析与模型检验

8_evaluation.tex   — 模型评价与推广

A_code.tex         — 附录：代码

```

**⛔ 模型假设必须在符号说明之前。** 不要合并成一个章节，不要调换顺序。文件名必须和模板 `\input{sections/...}` 一致。

**⛔ 模型假设数量控制**：4-5 条，不要超过 6 条。每条假设 1-2 句话（假设内容 + 合理性说明），不要写成长段落。假设太多说明问题没简化好。

**⛔ 符号说明表格控制**：15-20 个变量以内。只列正文中实际使用的核心变量，不要把所有中间变量都列进去。

**⛔ 分页规则（所有章节通用）：**

- **不要在 section 文件内部加 `\newpage`、`\clearpage` 或 `\nopagebreak`** — 让 LaTeX 自动分页，手动干预容易产生空白页

- main.tex 里只在摘要后和目录后用分页，正文章节之间不要加

- compile_utils.sh 会自动移除 section 文件里的 `\newpage`/`\clearpage`/`\nopagebreak`

- **例外**：符号说明文件（compile_utils.sh 会自动转成 longtable 支持跨页）

**⛔⛔ 符号说明表格格式（必须用 longtable + 禁止漂浮，否则会出现"半页空白 + 表格塞下一页"）：**

⛔ **根因警告**：**所有数学建模竞赛模板**（国赛 / 华为杯 / MathorCup / 华中杯 / 五一杯 / 美赛 / 华数杯 / 统计建模 / 长三角 / 电工杯 / 东三省 / 数维杯 / APMCM 等 13 个模板）的 `main.tex` 都启用了 `\usepackage[section]{placeins}`，作用是"每个 section 末尾自动插 `\FloatBarrier` 阻止浮动跨节"——这本来是好规范（防止图表漂到下一节），**但会让浮动表无法跨节漂移**。如果 AI 用 `\begin{table}[!ht]` / `[!h]` / `[htbp]` 写符号说明等小节的表格，且表格高度 + 引导文字超出剩余页面空间，LaTeX 会：

1. 把 `[!ht]` 表格扔到本节内能放下的位置 → 通常是节末

2. 节标题 + 引导文字停留在节开头 → **当前页大段空白**

3. 评委看到的就是"4. 符号说明" + 一句话 + 大半页空白 + 翻页才看到表

⛔ **不是华为杯独有问题**：所有竞赛都有这个陷阱。只是华为杯 gmcmthesis 字号大（4 号字 ≈ 14pt + 1.5 行距）、页边距宽，更容易触发"放不下当前页"的浮动条件，所以更显眼。

✅ **正确做法（务必遵守）**：

- **必须用 `\begin{longtable}` 而不是 `\begin{table}` + `\begin{tabular}`**

- longtable 不是 float，**不参与浮动**，就地排版 → 没有"漂走"问题

- longtable 天然支持跨页，标题永远在表格开头，不会出现标题和表格分离

- 不需要 `\centering`（longtable 自带居中）

- 不需要引导文字（"本文所用主要符号..."），节标题直接紧跟表格

- compile_utils.sh 会自动把 table+tabular 转成 longtable（兜底），但**源头写对最稳**

❌ **绝对反例**（任一出现都会引发空白页问题）：

```latex

\begin{table}[!ht]      % ❌ 漂浮，可能被推到节末

\begin{table}[ht]       % ❌ 同样漂浮

\begin{table}[htbp]     % ❌ 漂浮，加 b/p 让 LaTeX 决定页位

```

✅ **正确写法**：

```latex

\section{符号说明}

\begin{longtable}{clc}

\caption{主要符号说明}\label{tab:symbols} \\

\toprule

符号 & 含义 & 单位 \\

\midrule

\endfirsthead

\toprule

符号 & 含义 & 单位 \\

\midrule

\endhead

$N$ & 总数量 & 个 \\

$x_i$ & 第$i$个变量 & --- \\

... \\

\bottomrule

\end{longtable}

```

自检已由 `symbol_layout_check`（writing_check.sh 全家桶）接管符号节形状；另守一条：任何 section 文件里出现 `egin{table}[!ht]` / `[ht]` / `[htbp]` 漂浮选项都要改——短表（<半页）用 `egin{table}[H]` 强制就地，长表/符号说明用 `egin{longtable}`。

- 符号控制在 15-20 个以内- 符号控制在 15-20 个以内，表格控制在半页以内

**⛔ 写每个章节前，先读 MODELING_REPORT.md 和 RESULTS.md 对应部分的内容。** 不要凭记忆写——数值结果、公式推导、算法步骤都必须从这些文档中提取。

**⛔ 跨章上下文 + 图数据绑定（防"两张皮"）：**

- **每写完一章**，立刻往工作区根目录 `_writing_context.md` 追加 3-5 行要点卡（核心论点／关键数字／新定义的符号术语／已讨论的图表）；**写下一章前先 `cat _writing_context.md`**，承接前文结论、复用已定义术语（不重复定义）、保持同一指标数字全文一致——详见 `_utils/writing_rules.md` 的 `<chapter_context_card>`。

- **写每张图/表的分析前**，先按 `<figure_data_binding>`：从 FIGURE_MANIFEST/latex_includes 认清"这张图画的是什么量" → 去 `RESULTS.md`／`figures/all_results.json` 定位它对应的真实数值 → 分析里只用这些真值，**禁止凭图形状/位置猜数、禁止编造坐标**。

Read RESULTS.md for exact numbers — ensure paper numbers match computation results.

**⛔ 图文数值一致性规则：** 描述图表内容时（如"从图X可以看出，模型A的RMSE为0.023"），数值必须从 `figures/*.json` 或 `RESULTS.md` 中读取，不要凭记忆编写。写完后用 `bash ../../skills/_utils/writing_check.sh paper/`（cwd=工作区根）检查一致性。

**⛔ 长表格处理规则（>12 行的数据表格）：**

正文中**禁止**直接放超过 12 行的表格（调度方案、完整数据列表、逐步迭代结果等）。处理方式：

1. **正文：只放缩略版**（前 3 行 + 后 3 行 + 中间 `$\vdots$` 省略），底部注明"完整结果见附录 X"

2. **附录：放完整表格**（用 longtable 环境，允许跨页）

示例（正文缩略版）：

```latex

\begin{table}[H]

\centering

\caption{问题一调度方案（部分）}

\begin{tabular}{cccc}

\toprule

任务 & 设备 & 开始时间 & 结束时间 \\

\midrule

1 & A & 0 & 5 \\

2 & B & 2 & 8 \\

3 & A & 5 & 12 \\

\multicolumn{4}{c}{$\vdots$} \\

28 & C & 45 & 52 \\

29 & A & 48 & 55 \\

30 & B & 50 & 58 \\

\bottomrule

\end{tabular}

\label{tab:q1_schedule_short}

\footnotesize 注：完整调度方案（30 条记录）见附录 B。

\end{table}

```

**判断标准：** 写表格前先数数据行数。如果 `figures/TABLE_*.tex` 或结果表格超过 **12 行**数据行，必须自动生成缩略版（前 3-5 行 + `$\vdots$` + 后 3 行，可再加一行**汇总统计**如均值/最优/总计 Makespan）+ 附录完整版（`longtable`，放 `paper/appendix/` 如 `A_code.tex` / 新建 `A_tables.tex`）。不要把 100+ 行的 longtable 直接嵌入正文章节。`compile_utils.sh` 也会自动检测并截断超长表格兜底，但最好写的时候就按本规则处理好。

Follow the interleaving, embedding, and LaTeX rules from `_utils/writing_rules.md`.

**⛔ 图文并茂硬规则（每个章节都必须遵守）：**

- **浮动符（受控浮动）**：图用 `\begin{figure}[H]`（就地钉死），表用 `\begin{table}[H]`（就地）。图用 `[H]` 是为了钉在引出文字正下方、从机制上杜绝多图连排（`[htbp]` 会让 LaTeX 把多张图攒到一页、最伤可读性）；代价是极少数"图接近整页高+恰好落页底"时上方留一段空白，但图已限高在 `0.9\textheight` 内、且每张图前后都有引导/承接文字，此情形罕见且优于连排。模板已加载 `\usepackage[section]{placeins}`，每节末自动 `\FloatBarrier`（防残余浮动体跨节）。⛔ 表格不要用 `[htbp]`：会被 `\FloatBarrier` 逼到节末，在表上方留半页空白（符号表最常中招）；短表用 `[H]` 就地，超长表用 `\begin{longtable}`。伪代码 `\begin{algorithm}[H]` 保持就地。

- 每张图/表后面必须有 ≥5 行分析文字（数值解读+对比+结论），然后才能放下一张图

- 绝对禁止两张图连续出现中间没有分析段落

- 图片用 `\includegraphics[width=0.85\textwidth,keepaspectratio]`（以宽度为主，高度自适应）。⛔ 不要再加 `height=0.38\textheight` 这种小高度限制——在 `keepaspectratio` 下 height 只会把图**压得更小**：方形或竖高的图（热力图、雷达图、森林图、混淆矩阵、竖排子图、流程图）会被 0.38 页高卡到只有半页宽，导致"图很小看不清"。只有当某张图确实接近整页高、可能溢出时，才加 `height=0.9\textheight` 作为防溢出兜底

- **⛔ 禁止使用 LaTeX `subfigure`/`subcaption` 并排「多张独立 PDF」。** 每张图必须独占一个 `\begin{figure}[H]...\end{figure}` 环境，宽度 ≥ `0.85\textwidth`。不要用 `\begin{subfigure}{0.48\textwidth}` 把两张独立 PDF 缩成半页宽——这会导致图片太小看不清。如果确实需要对比两张图，分成两个独立的 figure 环境，中间加 2-3 句过渡分析文字。

  **✅ 例外（推荐做法）：多面板组合图（FIGURE_MANIFEST 标了 `[2-panel]` / `[4-panel]`）应当在 matplotlib 内一次性画出 —— 用 `plt.subplots(1, 2)` 或 `plt.subplots(2, 2)` + 每子图 `(a)(b)(c)(d)` 标签 —— 输出为「单个 PDF」，LaTeX 引用时仍是 `\includegraphics[width=0.85\textwidth]{fig_xxx.pdf}` 一行搞定。这种方式既能并排对比又能保持高分辨率，不属于禁令范围。详见 `_utils/writing_rules.md` 第 4 条。

  **🟡 数据图不是都要并排——默认单列，留白才触发**：数据结果图**默认一张一行**；只有当两张图**同类/可比**（如两变量分布、两场景同类曲线）、且**各自单列都只占半页、配文字后留半页以上白**时，才做成 2-panel 并排把版面填满。两张图不相关的，哪怕都很空也各自单列，不为凑页硬拼（详见 `_utils/writing_rules.md` 第 4 条决策流程 3.5 步）。

  **⛔ 但逻辑框图例外中的例外——流程图/架构图/技术路线图/TikZ 几何·算法·架构示意图（drawio 或 tikz 生成的逻辑框图）绝对单列独占，不论主题多相关都不并排**：它们靠节点文字和连线表意，缩成半栏字就糊了，并排没有信息收益。上面的✅ matplotlib 合成单 PDF 只针对**数据结果图**（柱状/折线/热力/混淆矩阵等）的并排对比，逻辑框图（含 tikz_*.pdf）不走这条、永远一张一行。

- **⛔ 图片宽度下限：** `width` 参数不得小于 `0.8\textwidth`。任何 `width=0.5\textwidth`、`width=0.48\textwidth`、`width=0.45\textwidth` 都是错误的，必须改为 `0.85\textwidth` 或 `0.9\textwidth`

> ⛔ 长表格处理规则以上方「长表格处理规则（>12 行的数据表格）」一处为唯一口径（含缩略版示例 + 汇总统计行 + 附录 longtable + compile_utils.sh 兜底）；此处不重复，禁止另立 >15 行之类矛盾阈值。

每写完一章自查体量：`wc -c paper/sections/当前章节.tex`（中文 LaTeX ≈900 字符/页）。预期 5 页的章只有 ~2000 字符就当场扩写，不留到最后。

<exemplar_depth>

#### Writing depth reference

**国赛一等奖 (25-30 pages, 3 sub-problems)**:

- 问题重述+分析 (2-3p): restate in own words, extract core problems — not copying the problem statement

- 模型假设+符号说明 (2p): 5-7 assumptions (each with content + justification, not too many not too few), one complete symbol table with 15-25 variables (符号/含义/单位 three columns, do not split into multiple tables)

- Each sub-problem (5-7p): model formulation (2p, with derivation and physical meaning) + solution method (1.5p, with algorithm steps) + results with table+figure (1p) + analysis (0.5-1.5p, numerical meaning + comparison with expectations + reasoning)

- 灵敏度分析 (2-3p): ≥2 key parameters, each with variation curve plot + analysis paragraph

- 模型评价 (2p): 3-4 strengths + 2-3 weaknesses + generalization directions. Pure text discussion, no figures or tables needed

**华为杯一等奖 (55-65 pages typical, comp_rules guidance 历届经验口径，非官方规定)**: deeper derivations, more thorough analysis per sub-problem (8-10p each), 灵敏度分析 (4-5p), 模型评价 (3p, pure text, no figures) with comparison to other methods

**统计建模获奖 (35-40 pages)** — chapter structure is content-driven, page allocation reference:

- 绪论/前言 (4-8p): research background + literature review (grouped by 3-4 themes, 3-5 papers per theme with detailed discussion) + research objectives

- 数据描述与预处理 (6-8p): data source + variable description table + descriptive statistics table + exploratory analysis (distribution / trend / cross-tabulation plots)

- 模型/方法 chapters (6-10p): theoretical basis + formula derivation + parameter settings + implementation details (adjust by actual number of models)

- Core results analysis (10-16p): the most important part of the paper — every result needs 2-3 paragraphs of interpretation, not just "as shown in Table X"

- 结论与建议 (3-5p): conclusions + recommendations + innovation points + limitations and future work

Common traits of award-winning papers:

- Solid exploratory analysis (cross-tabulation, group comparisons, rich visualization)

- Core analysis chapters occupy 40-50% of total pages, every numerical result has deep interpretation

- Specific chapter titles ("基于集成学习的生育意愿影响因素分析" not "模型构建")

- Include "innovation & limitations" discussion (reviewer bonus points)

| Type | Pages | Characters | References |

|------|-------|-----------|------------|

| 数模国赛 (30p limit) | 25-30 | 18000-25000 | ≥10 |

| 华为杯（历届经验口径，非官方规定；对齐 comp_rules guidance） | 40-60（一等奖通常 55-65） | 30000-40000 | ≥15 |

| MathorCup | 35-40 | 25000-35000 | ≥10 |

| 华中杯 | 25-30 | 18000-25000 | ≥10 |

| 五一杯 | 25-30 | 18000-25000 | ≥10 |

| 统计建模 | 35-40 | 25000-35000 | ≥20 |

</exemplar_depth>

<figure_usage_principles>

#### Figure/table usage by competition type

**统计建模**: Figures first, tables second. Figure/table selection is driven by the actual analysis methods used — regression uses forest plots + regression tables, prediction uses prediction comparison plots + accuracy tables, classification uses confusion matrices + ROC, evaluation uses radar charts + ranking tables. Every analysis step should have a corresponding figure or table.

**数模竞赛**: "字不如表，表不如图". Every sub-problem must have independent result display (table + figure). Comprehensive comparison figures are additional supplements. Reviewers value information density and aesthetics.

Do not force figures where they are not needed (pure literature review, theoretical derivation). 执行 Agent decides figure count and placement based on content needs.

</figure_usage_principles>

<stats_figure_placement>

#### Stats modeling paper figure placement rules

Figure/table selection is driven by research content, not fixed type templates. Below are figures mapped to analysis methods:

**Data description stage** (almost all papers need these):

- Descriptive statistics table (required), data distribution plots / boxplots, correlation heatmap, time series trend plots

**Model results stage** (select based on actual methods used):

- Regression: regression result table + coefficient forest plot

- Prediction: prediction comparison plot (actual vs predicted) + model accuracy table (MAE/RMSE/R²) + error distribution plot

- Classification: confusion matrix + ROC curve + model comparison table (Accuracy/F1/AUC)

- Clustering: cluster scatter plot / t-SNE + silhouette score table

- Evaluation: comprehensive score ranking table + radar chart

- Causal inference: baseline regression table + robustness check table + heterogeneity comparison plot

**Model interpretation / diagnostics stage** (select as needed):

- Feature importance / SHAP plot, residual diagnostics, sensitivity analysis plot, ablation table

**Principle**: Core result figures/tables go in the body text. Appendix only for code and very long auxiliary tables.

</stats_figure_placement>

<chapter_writing_points>

#### Chapter writing points (universal, adapt to research logic)

**⛔ 写作风格铁律（所有章节都必须遵守）：**

- **禁止在正文中使用 `\begin{itemize}` 或 `\begin{enumerate}` 列表。** 黑点/编号列表是最明显的 AI 写作痕迹。必须用连贯的段落叙述。

  - 需要列举时用行内编号："（1）...（2）...（3）..."，或改写为自然衔接的连贯段落（不用"首先/其次/最后"机械过渡链——那是过程式骨架，与"首先...再...接着...最后"同属 AI 痕迹）

  - 例外：模型假设列表（可用编号）、附录

- **每段至少 3-5 句话。** 不要写只有 1-2 句的短段落。

- **连续段落不能以相同句式开头。** 如连续三段都以"本文..."开头，必须改。

- **段落长短错落。** 相邻段落字数几乎相等（差 <20%）说明节奏单一，是 AI 结构痕迹；长段展开论证、短段给结论，写作时自查。

- **图题写发现，不写「XX 对比图」。** 图题应陈述该图揭示的结论（如"误差随噪声水平升高呈指数增长"），"XX 对比图 / XX 结果图"式空标题是 AI 痕迹。

- **关键数据给误差范围或置信区间，禁止全文统一四位小数。** 所有数值一刀切同一精度是机器输出痕迹；按量纲与误差水平取有效位，关键估计量附 ± 区间或置信区间。

- **图号必须显式引用、句式换着来（标准优秀论文口径）。** 每张图都要点名"图 N"让读者对上号（硬规范，别为避免套路删图号）；要禁的是"图X展示了……从图中可以看出……"这种图作主语+空话的单调重复，不是禁止一切图作主语。相邻两图引用句式必须不同，在括号旁注（首选）／句首带出／动词引导／图作主语（带实质结论时可用）／后置印证间轮换。详见 `_utils/writing_rules.md` 的"图表是论据"规则。

- **禁止元叙述和内部指令泄露。** 正文中不能出现"参赛者"、"参赛队伍"、"RESULTS.md"、"figures/*.json"、"AGENTS.md"等内部文件名或工作流术语。用"本文"代替"我们团队"，论文是独立学术文档。

**⛔⛔ 优化/规划与求解章节写法（modex-3 同源吸收 2026-09-22，置于本清单最前执行）：**

##### ⛔⛔ 优化/规划类模型：决策变量、目标函数、约束条件必须分段交代

**适用范围**：模型里出现 `\min` / `\max`、或有"最优/最省/最大化/选址/指派/排班/路径/调度/配比"这类
决策问题时**必须**照此写。**统计建模（评价指标体系 / DEA / PCA / 回归 / 预测）不适用**，按上面的
"theoretical basis → formulas → parameters"写即可。

> 依据：最优化问题的三要素就是**决策变量、目标函数、约束条件**。优秀论文通常按这条辨识顺序
> 组织；硬要求是三者各自清楚可辨。把三者混成一坨公式是评委最容易看出"没想清楚"的地方 ——
> 他扫一眼找不到"你到底在决定什么"。

**要求是"三者各自清楚可辨"，不是"必须切成三个小节"。** 惯用顺序是
决策变量 → 目标函数 → 约束条件 → 变量取值范围，照它写读者最省力；真正的硬线只有一条：
**评委扫一眼就能分清哪个是决策变量、哪个是目标、约束有几条**。

- 变量多、约束多的复杂模型（如四类变量九条约束）→ 分小节或用表格+公式承载，否则没法逐条核对
- 只有一两个变量、两三条约束的简单模型 → 一段文字 + 一个 `aligned` 公式就够，
  **不要为了凑结构硬切三个小节** —— 数模论文讲少而精，形式服务于内容

**⛔⛔ 怎么在"禁止 itemize/enumerate"的前提下把三要素分开写（必读，否则会写成一坨散文）**

上面的写作铁律禁止正文用黑点/编号列表，于是最容易出现的失败形态是**把四类决策变量和九条约束
全揉进一个自然段**（"决策变量有四类：$y_k$ 表示…；$x_{ijk}$ 表示…；模型须满足如下约束。
动用车辆数不超过 5 辆，即…。沿路线的累积载量…"）—— 信息都在，但评委无法逐条核对，
等于没写清楚。**这不是列表禁令的错，是选错了载体。** 正确做法：

| 要素 | 用什么载体 | 为什么不违反列表禁令 |
|---|---|---|
| 决策变量 | **三线表**（符号／含义／类型／下标范围）+ 表后一段讲类型理由 | 表格不是列表，全篇本来就要用表 |
| 0-1 变量的语义 | `cases` **公式** | 公式不是列表 |
| 目标函数 | `equation` 独立成式 + 一句话讲来源 | — |
| 约束条件 | 按现实机理分组；一个 `equation` 里用 `aligned` 逐条排开，组后成段解释各行含义 | 公式不是列表 |
| 变量取值范围 | 与约束同一个 `aligned` 的最后一行，或单独一式 | — |

这套载体正是运筹学论文的标准形态：**公式承担"逐条罗列"，散文承担"解释为什么"**。
⛔ 别为了守列表禁令而牺牲可核对性，也别用 `itemize` 去偷懒。

**⛔ 展示公式必须编号（PDF/LaTeX 硬线）。** 正文中的目标函数、状态方程、推导式和成组约束统一使用
非星号的 `equation` / `align` / `gather` / `multline`；禁止 `equation*`、`align*`、`\\[...\\]`
和 `$$...$$`。若多条约束只需要一个组号，用 `equation` 外层加 `aligned`；若每条都需要单独讨论，
用 `align` 逐行编号。后文会引用的公式必须加 `\\label{eq:语义名}` 并通过 `\\eqref{...}` 引用，
禁止手写固定数字。只有行内短符号和短定义不要求编号。

**⛔ 子问题章内部的小节标题要带上模型是什么，别写空标题。** 优化题最容易起成"模型建立"
"模型求解"这类谁都能套的题目，评委从目录上看不出你做了什么：

| ❌ 空标题 | ✅ 带信息的标题 |
|---|---|
| 模型建立 | 基于 0-1 整数规划的服务站选址模型 |
| 模型求解 | 分支切割法求解与最优选址方案 |
| 结果分析 | 选址方案的成本构成与覆盖率分析 |
| 灵敏度分析（作为子问题内的小节时） | 预算上限变动对选址数量的影响 |

⛔ **只管子问题章（第 4/5/6 章）内部的小节，不要拿去改章级标题。** 上面骨架里的
"1 问题重述""7 灵敏度分析与模型检验""8 模型评价与推广"是竞赛通行的章名，评委按它定位，
**照原样保留**。要带信息的是它们下面的小节，例如第 7 章内部可分
"需求波动 ±20% 下的方案稳定性""depot 位置切换的影响"。

**① 决策变量（先声明，这是全部推导的地基）**

必须交代五件事：**符号、含义、类型、下标范围、类型理由**。句式用"设 $x$ 表示…"或"记 $x$ 为…"。

- **类型理由不能省**：为什么必须取整（人数/车辆数不可分）、为什么是 0-1（选或不选，没有中间态）、
  为什么连续（可任意分割的流量/配比）。⛔ 只写"$x_j$ 为整数"不给理由 = 没想清楚。
- **0-1 变量一律用分段函数写清两种取值各自的现实含义**，不许只写"$y_j \in \{0,1\}$"：

```latex
设 $x_{ij}$ 表示是否把第 $i$ 个需求点指派给第 $j$ 个服务站，因"指派"只有成立与不成立
两种状态、不存在部分指派，故取 0-1 变量：
\begin{equation}
x_{ij}=\begin{cases}
1, & \text{第 } i \text{ 个需求点由第 } j \text{ 个服务站服务},\\
0, & \text{否则},
\end{cases}\qquad i=1,\dots,m;\ j=1,\dots,n
\end{equation}
```

**② 目标函数（独立成式，并说明"为什么是这个目标"）**

- 独立一个公式环境，带 `\min` / `\max`，不要和约束挤在一行。
- **紧跟一句话交代目标的来源**，引赛题原话（口径与 `MODELING_REPORT.md` 的目标溯源表一致）。
- 多目标要说清怎么处理（加权 / 分层 / Pareto），权重怎么定、量纲怎么统一。

```latex
题目要求"在满足全部需求点覆盖的前提下使总建设与运营成本最低"，故以总成本最小为目标：
\begin{equation}
\min\ Z=\sum_{j=1}^{n} f_j y_j+\sum_{i=1}^{m}\sum_{j=1}^{n} c_{ij} d_i x_{ij}
\end{equation}
其中第一项为服务站固定建设成本，第二项为需求点到服务站的运输成本。
```

**③ 约束条件（独立于目标、按现实机理分组，每组必须有业务含义）**

- 目标函数必须与约束分开。多条同类约束用一个 `equation + aligned`（或 `cases`）纵向罗列，默认整组
  共用一个可见编号；功率守恒、状态递推、终端条件等会被单独讨论的机理可各自独立编号。
- 默认不在论文里写 `C1/C2`、`H1/H2`、“审计项”“约束验证编号”等内部工程标签。只有正文后续确实要
  逐条引用时才设置语义化子编号，否则由公式承担罗列、由自然语言按顺序解释现实含义。
- **每组约束下面必须有业务解释**，说明各行对应题目里的哪个现实限制。
  ⛔ 只有公式没有解释 = 评委无法判断你有没有漏约束，这是最常见的扣分点。
- 每个优化子问题必须出现“独立展示的目标函数 + 至少一个约束公式组”，或明确通过 `\eqref{...}`
  说明沿用了哪些前序约束并只写新增约束；不能只用一句“满足前述全部条件”带过。
- 建议用"约束类型清单"自查有没有漏（**不是要求全都有，是用来查漏**）：

| 类型 | 典型表达 | 对应的现实限制 |
|---|---|---|
| 需求覆盖 | $\sum_j x_{ij}\ge 1$ | 每个需求点至少被服务一次 |
| 资源/预算上限 | $\sum_i b_i x_i\le B$ | 总投入不超过预算 |
| 容量约束 | $\sum_i d_i x_{ij}\le Q_j y_j$ | 单站服务量不超过其容量 |
| 总量固定 | $\sum_i x_i=k$ | 恰好选 $k$ 个 / 总量守恒 |
| 至多/至少选 | $\sum_{i\in S} x_i\le 2$ | 同一区域最多建 2 个 |
| 互斥 | $x_a+x_b\le 1$ | 两方案不能同时采用 |
| 逻辑联动（big-M） | $x_j\le M y_j$ | 未开设的站点不能有流量 |
| 时间窗 | $a_i\le t_i\le b_i$ | 必须在时间窗内到达 |
| 流量平衡 | $\sum_{\text{in}}=\sum_{\text{out}}$ | 节点不积压不凭空产生 |
| 度约束 / 子回路消除 | $\sum_{e\in\delta(S)}x_e\ge 2$ | 路径不能断成多个圈 |

- **线性化技巧必须解释,不能只丢公式**。`big-M`、分段线性、绝对值转换、
  `max` 转约束这些,都要说清"原来的非线性长什么样、为什么这样一改就等价"。
  例：$x_j\le My_j$ 的作用是"$x_j>0$ 时逼 $y_j=1$",从而把目标里只在开设时才计入的
  固定成本 $f_jy_j$ 变成线性项。⛔ $M$ 取多大也要给依据（取数据上界,不是随手写 99999）。

**④ 变量取值范围 + 模型定性（收口）**

- 非负/整数/上下界单独一行列出。
- 紧接一段说明：这是什么类型的问题（LP / ILP / MILP / NLP / 多目标 / 动态规划）、
  **规模多大**（变量数、约束数，按下标范围算出来）、**为什么选这个求解方法**
  （精确求解器还是启发式；若用启发式要说清为什么精确解不可行 —— NP-hard / 规模爆炸）。

**⛔ 反面写法（评委看不出你在决定什么）**：

```latex
（错误 ❌ — 三要素糊成一坨，决策变量从没定义过就直接用，约束没有业务含义）
本文建立如下优化模型：$\min\sum c_{ij}x_{ij}+\sum f_jy_j$，其中满足
$\sum_j x_{ij}=1$，$\sum_i d_ix_{ij}\le Q_j$，$x_{ij},y_j\in\{0,1\}$，
使用 Gurobi 求解得到最优解。
```
问题：$x_{ij}$ / $y_j$ / $c_{ij}$ / $f_j$ / $Q_j$ 全部没交代含义；没说为什么是 0-1；
两条约束不知道对应题目哪句话；没说模型类型与规模；"使用 Gurobi 求解"没说为什么能精确求解。

**⛔ 与上游一致性**：三要素的内容必须与 `MODELING_REPORT.md` 对得上 —— 目标函数要能在
它的**目标/约束原文溯源表**里找到对应行，约束条数不能少于建模阶段登记的关键约束数
（那些下游 `constraint_audit.py` 会复核）。⛔ 不许在论文里新编一个建模阶段没有的约束，
也不许把建模阶段有的关键约束在论文里悄悄漏掉。

##### ⛔ 每个模型的建模小节必答「人类痕迹四问」

评审实测反馈：「模型建立过程一点没有」「找不到公式」——AI 式建模只把公式摆出来，看不见人的决策痕迹。
每个建模小节动笔前自问四问，答不上来就是没写完（第四问可与检验章节呼应，但必须点名）：

1. **为什么选这个方法**：对比过哪些替代方案、各自为何不合适（一两句写进正文，与摘要"候选方法对比"要素同源）；
2. **参数从哪来**：数据估计、文献取值还是标定实验，给出处与取值依据，不凭空落数；
3. **完整推导链**：从假设到结论逐步呈现，关键一步一行，读者能跟着验算；禁止只给终式；
4. **这个模型哪里脆弱**：哪里可能失真、对哪个假设或参数最敏感——检验章节（灵敏度/误差界）必须回应这一问。

**正反对照（建模小节开头怎么写）**：

- ❌ AI 式：直接抛公式。"建立 XGBoost 模型：[公式]。参数取 n_estimators=500。"——看不见选择理由、参数依据与推导过程，评委有理由怀疑模型是抄的。

- ✅ 人类式：先说约束冲突，再引出建模选择。"样本特征含连续与类别两类量纲，直接最小二乘会被类别维度主导，故先将类别量做目标编码，再以梯度提升树拟合非线性项：[公式]。树深与学习率按 5 折交叉验证在训练段标定；弱学习器个数受样本量约束取 500（附录参数表）。该模型对编码泄露最敏感，第 X 章灵敏度分析单独检验。"

##### ⛔⛔ 求解小节：写"解为什么可信"，不要复述算法原理

数模论文的核心是**建模**与**求解**，不是算法教学。评委关心的是"模型对不对、这个解可不可信"，
不是"你能不能把遗传算法讲清楚"。**算法叙述要短。**

| 该写（占求解小节大头） | 不该写（教科书内容，最多一句带过） |
|---|---|
| 为什么选这个解法（问题规模／NP-hard／精确解可行性） | 遗传算法的选择、交叉、变异怎么操作 |
| 能解释结果的比较：与基准/边界对照、误差、容量余量、参数变化 | 模拟退火的 Metropolis 准则推导 |
| 关键实现选择及其理由（怎么分解、怎么线性化、种子怎么构造） | 逐行伪代码、时间复杂度 $O(n^2)$ 的推导 |
| 结果的现实边界（容量余量、误差范围、适用条件） | 算法的历史沿革与文献综述 |

**⛔ 算法名 + 一句作用 + 引文，就够了。** 例："用 OR-Tools 约束路由求解器\cite{xx}、
以几何种子初始化的模拟退火\cite{xx}、以及 CBC 整数规划\cite{xx} 三种原理不同的方法
交叉求解，三者收敛到同一目标值则可相互印证。"—— 不要再展开这三种方法各自怎么工作。

> ⛔ 上例的 `\cite{}` 只是占位写法。**实际用哪个引用命令看模板** —— 见后面"引用格式规则"：
> 模板已是上标样式（`gbt7714-numerical` / natbib 带 `super`）就用 `\cite{}`；模板是
> `plain/plainnat/unsrt` 才改用 `\upcite{}`。⛔ **`\upcite` 并非所有模板都定义**
> （实测 15 个中文模板里只有 cumcm / dongsansheng / huazhong / wuyi 在 cls 里定义了它），
> 在没定义的模板里直接写会报 undefined control sequence、整篇编译失败。

**⛔ 不要为了篇幅去写伪代码和复杂度分析。** 那是计算机类论文的体例。
数模论文里它们属于**附录内容**：伪代码放 `paper/appendix/`，算法参数（初温、降温率、迭代数、
求解器时限、随机种子）也一并列进附录的参数表。正文只需一句"全流程以固定随机种子运行，
结果可复现，参数见附录 X"。

**要交代清楚的是下面这些事，怎么组织、放在哪个小节、要不要单独设节，由题目自己定：**

- 求解难度与方法选择的理由（规模、是否 NP-hard、精确解可行不可行）
- 关键实现选择及其依据（怎么分解、怎么线性化、多起点怎么构造）
- **结果的解释边界**：与基准或理论界的差异、误差范围、哪项容量最接近上限、结论在哪些参数范围内稳定。
  后台逐项检查仍必须运行，但正文只保留其中有数学或现实解释价值的数值，不写函数名和通过状态。

⛔ **不要套固定的小节名或固定条数。** 有的题一段话就说完（模型简单、调用现成求解器直接出解），
有的题需要单独讨论误差、敏感性或基准比较；单纯确认约束未被违反不值得另设一节。
判断标准只有一个：**读者能否确信这个解是对的**。数模论文讲少而精，
没内容的小节标题比没有小节更糟。

⛔ 唯一的比例硬线：**"解为什么可信"的篇幅不能少于"算法怎么工作"的篇幅。** 前者是评委看的，
后者是教科书内容。

**⛔ 诚实边界**：解析下界／松弛界**不是可行方案**，它与最优解的差值只能用来确认"最优解没有
异常偏低"，**不能解读成"还有这么多优化空间"**。这条写错是硬伤。

**Expansion strategies** when content is thin (not padding — substantive content):
- Formula listed without derivation → add step-by-step derivation with physical meaning explanation
- Result with only "如表所示" → add 2-3 paragraphs of interpretation (numerical meaning, comparison with expectations, reasoning, comparison with other methods)
- Assumptions as bare list → add justification for each assumption
- Literature review only lists papers → add method summary for each and connection to this work

**⛔⛔ 扩写只能往「建模深度」和「结果可信度」上扩，不许往「算法叙述」上扩。**
数模论文的核心是建模与求解，算法原理是教科书内容。篇幅不够时该补的是：
模型假设的合理性论证、口径定义的推敲、结果与预期/基准的对比、灵敏度与鲁棒性、
约束松紧分析、结论的业务含义 —— 而**不是**把遗传算法的交叉变异步骤展开写、
不是加逐行伪代码、不是补时间复杂度推导（那些属附录）。
⛔ 判据：正文里"算法怎么工作"的字数若超过"解为什么可信"的字数，就是写反了。

**绪论/前言** (all papers):

- Research background (why this problem matters) → Literature review / research status (what others did, what gaps remain) → Research objectives / content / contributions → Paper structure overview

- Literature review organized by theme (≥15 citations), not chronologically listed

**数据与预处理** (almost all papers need this):

- Data source → Sample description (time range / sample size / variable count) → Variable definition / coding table → Missing value / outlier handling → Exploratory analysis (distribution plots / trend plots / cross-tabulation)

- Exploratory analysis is a key capability demonstration for reviewers — do not skip

**模型/方法 chapters** (organize by actual research content):

- Each model/method: theoretical basis (1-2 paragraphs) → mathematical formulas → parameter setting rationale → implementation details

- Multiple models: can introduce all models first then show results (Example B style), or give each model its own chapter with results (Example A style)

**结果分析 chapters** (core, should occupy 40-50% of paper):

- Every result must have: numerical presentation (table/figure) → interpretation (2-3 paragraphs, not just "as shown in Table X") → comparison with expectations / other methods → reasoning

- Multi-model comparison: horizontal comparison table + rationale for selecting the best model

**结论与建议**:

- Main conclusions (echo research objectives) → Policy / application recommendations (specific and actionable) → Innovation points → Limitations and future work

- "Innovation & limitations" can be inside the conclusion or a standalone chapter (Example B style)

- ⛔ 结论章禁止复述摘要：不复述各问数值结果，必须给出局限性与适用边界（模型在哪类场景失效、对哪个假设/参数最敏感、结论在什么范围内成立）

</chapter_writing_points>

### Step 5: References

Follow the `<references_workflow>` in `_utils/writing_rules.md`.

Stats papers: ≥20 references. The stats template uses `natbib` with `[numbers, square, super]` — use `\cite{key}` in body text (auto-superscript) + `\bibliography{references}` + `\bibliographystyle{plainnat}`. **cumcm / wuyi** load `natbib[numbers]` (no super) + `\bibliographystyle{gbt7714-numerical}` + `\bibliography{references}` — body text MUST use `\upcite{key}` (not `\cite`, which gives inline `[1]`). The huazhong template uses `\begin{thebibliography}{99}...\end{thebibliography}` — manually add `\bibitem` entries (do not use `\bibliography{}`); body uses `\cite`. ⛔ `\upcite` exists ONLY in cumcm / huazhong / wuyi / dongsansheng; every other template uses `\cite`.

**⛔ 使用 scholar_fetch.py 工具获取所有参考文献的 BibTeX。禁止凭记忆编造 BibTeX。**

**⛔⛔ 引用编号必须全局递增（严格，不可违反）：** 全文首次引用必须按 [1], [2], [3]... 顺序出现；先 [3] 后 [8] 再回 [1]、或已现 [5] 后又出新引用 [3]，都是编号跳跃/回退，均不可违反。保证方法：key 在 .bib / thebibliography 里的排列顺序 = 正文首次出现顺序（`\begin{thebibliography}` 模板手工排，`\bibliography{references}` 模板 BibTeX 自动排）；写作中新加的引用编号自然排到当前最大值+1；写完全文逐段扫一遍编号确认严格递增（只许重复已出现的编号）。

**⛔ 引用格式规则（中文竞赛论文必须上标）：**

- 必须用上标引用样式：`\bibliographystyle{gbt7714-numerical}` 或 natbib 的 `super` 选项

- 如果模板用的是 `plain/plainnat/unsrt`（非上标），正文中必须用 `\upcite{}` 或 `\textsuperscript{\cite{}}` 而不是 `\cite{}`

- 禁止：非上标样式 + 直接 `\cite{}` → 引用会显示为 `[1]` 而非上标 `¹`

**⛔ 多引用合并规则（合并必须按编号升序）：** `方法A\cite{a,b,c}` 一个命令逗号分隔，且 key 顺序必须对应编号升序（[1,2,5]）；编号不相邻（如 [3] 与 [7]）可分开写 `\cite{a}\cite{b}`；连续相邻的多个 `\cite` 必须合并；**宁愿分开写也不要错序合并**（`\cite{c,a,b}` 对应 [5,1,2] 是错误）。写作时难以预知最终编号，先按 key 出现逻辑合并，编译后用 compile_check.sh 检查调整。

**⛔ 引用写法规则：写正文时，citation key 必须包含描述性关键词，格式为 `作者姓_年份_主题关键词`。**

例如：`\cite{wang_2023_supply_chain_resilience}` 而不是 `\cite{wang2023supply}`。

不确定作者/年份时用 `TODO__` 前缀：`\cite{TODO__digital_economy_spatial_spillover}`。

```bash

# Step 5a: 收集所有引用 key

grep -roh '\\cite[tp]*{[^}]*}' paper/sections/*.tex paper/main.tex 2>/dev/null \

  | grep -oP '\{[^}]+\}' | tr -d '{}' | tr ',' '\n' | sed 's/^ *//;s/ *$//' | sort -u > _tmp/_cited_keys.txt

echo "引用 key 数量: $(wc -l < _tmp/_cited_keys.txt)"

# Step 5b: 逐个搜索并获取 BibTeX（用描述性关键词搜索）

PYTHON=""; for _c in "$MH_PYTHON" python python3; do [ -z "$_c" ] && continue; if $_c -c "import sys" >/dev/null 2>&1; then PYTHON="$_c"; break; fi; done; [ -z "$PYTHON" ] && PYTHON=python

SCHOLAR_SCRIPT="tools/scholar_fetch.py"

while IFS= read -r key; do

    query=$(echo "$key" | sed 's/^TODO__//; s/_/ /g')

    echo "--- 获取: $key (搜索: $query) ---"

    $PYTHON "$SCHOLAR_SCRIPT" bibtex "$query" --max 3

    sleep 0.5

done < _tmp/_cited_keys.txt

```

处理每个搜索结果：

1. 检查 `match_label`：`"good"` → 直接使用。`"partial"` → 核实标题。`"low"` → 很可能搜错了，换关键词或用 WebSearch。

2. `match_score` < 0.3 说明大概率不是目标论文，不要盲目使用。

3. 将 .tex 中的 citation key 替换为 BibTeX 条目中的实际 key。

4. `bibtex_source=auto` 的条目加 `% [VERIFY]`。`match_label="low"` 的加 `% [LOW_MATCH]`。

### Step 5.5: De-AI polish

全文写完后、编译前，按以下顺序做一轮改写（目标是把"程序验收话"改成"读者视角的事实"，不是同义词替换）：

1. **跑机检定位**：`python ../../skills/_utils/ai_tell_check.py --strict paper/`（cwd=工作区根；目录参数已支持递归找正文）。exit 1 时逐条输出都有行号+改法建议。**本步受引擎 `ai_flavor` 强制闸**：finish 时自动全量重扫，硬伤+空话 >3 处（获奖论文水平上界）直接拒绝完成——所以别等闸拦，现在就改到位。
2. **按优先级改写**（替代表与实测规模见 `_utils/writing_rules.md` `<de_ai_polish>` 段）：
   - 工程/质检语汇泄漏（实测第一大破绽，10 工作区 442 次）：口径→定义/取法/计算方式；自检→校验/一致性检验；兜底→缺省处理；链路(隐喻义)→写明具体传递关系。**改写方向是删掉"检查视角"，直接陈述被验证的事实**：不写"容量校验零越界"，写"最高利用率 0.992，仍有 0.8% 余量"；不写"单调性断言通过"，写"时延权重由 0 增至 20 后，迁移比例由 0.549 降至 0"。
   - 空话套话（值得注意的是/综上所述/不难发现/显而易见/在此基础上/随着…的发展）：整句删掉或改成带具体内容的陈述——套话删除后段落通常更紧凑，不需要补话。
   - 内部标记（⛔✅❌⚠ / RESULTS.md 等文件名 / HC-01 类质检编号）：直接删除或改写成自然语言；论文自己定义过的编号（符号说明里的"假设 A1"）不受影响。
3. **重跑到绿**：`ai_tell_check --strict paper/` exit 0 才算本步完成；人工风格对照 `_utils/human_competition_paper_style.md` 复核背景/重述/分析三章节的职责划分是否混写。

领域术语不算泄漏（735 篇获奖论文反证）：通信链路、河流上下游、闭环控制、频谱复用、误差修正项等字面义该写就写；只在讲自己的建模流程时避开工程隐喻。改写完的段落自己读一遍——像给同行讲思路，不像交验收报告。

### Step 5.6: Write abstract NOW (after all chapters are complete)

**⛔ MANDATORY: NOW write the abstract.** Read RESULTS.md and all section .tex files. Extract the actual numerical results from each sub-problem. The abstract must contain ONLY numbers that appear in the body text — do NOT invent or round differently.

**⛔ 统计建模必须写中英文两个摘要**：先写中文摘要（500-700字），然后将中文摘要忠实翻译为英文摘要（350-500 words），所有数值结果、方法名称、结论必须一一对应。数模竞赛（国赛/五一杯/MathorCup/华中杯等）只写中文摘要。

For math modeling competitions: each sub-problem must have its specific result in the abstract (e.g., "问题一采用XX算法，最优解为YY，空间利用率达ZZ%")。

Read `_utils/writing_rules.md` for abstract format rules (分段、首行缩进、长度).

### Step 6: Final verification

```bash

bash skills/_utils/writing_check.sh paper/ 2>/dev/null || bash academic-toolkit/skills/_utils/writing_check.sh paper/ 2>/dev/null || bash ../../skills/_utils/writing_check.sh paper/

```

**⛔ 能力声称终检（正文写完后跑，扫"有没有把没通过的能力写成成果"）：**

```bash

FAST_MODE=0; grep -q 'MH_FAST_MODE=1' AGENTS.md 2>/dev/null && FAST_MODE=1

python skills/_utils/paper_claim_check.py --audit CAPABILITY_AUDIT.md --checklist CAPABILITY_CHECKLIST.json --sections paper/sections --fast $FAST_MODE 2>/dev/null || python academic-toolkit/skills/_utils/paper_claim_check.py --audit CAPABILITY_AUDIT.md --checklist CAPABILITY_CHECKLIST.json --sections paper/sections --fast $FAST_MODE 2>/dev/null || python ../../skills/_utils/paper_claim_check.py --audit CAPABILITY_AUDIT.md --checklist CAPABILITY_CHECKLIST.json --sections paper/sections --fast $FAST_MODE

PCC=$?   # 此时正文已成型：会扫未通过能力名是否出现在正文(WARN),并复核验收状态(FAIL阻断)

```

> WARN（未通过能力名出现在正文）：确认不是把没做成的写成做到了；若确在"局限/未来工作"里如实提及可放行。`PCC=1`：仍有能力未通过验收，不能定稿。

Also check:

- `wc -c paper/sections/*.tex` 看各章明细（≈900 字符/页），找出最薄的 1-2 章优先扩充；页数是否达标以下方「正文页数预检」为唯一权威

- Any sub-problem chapter <3500 chars (~4 pages) needs expansion

- All figures/*.pdf and TABLE files (PDF模式 .tex / Word模式 .md) referenced in sections/正文

- No template bracket placeholders remaining (`[论文标题]`, `[中文摘要内容]`, etc.)

**⛔ Constraint consistency check (MUST do before finishing):**

Read PROBLEM_ANALYSIS.md (or the original problem statement in user_data/) and check every numerical result in the paper against the problem's constraints:

```

=== 论文-题目约束一致性检查 ===

1. 读取题目中的所有约束条件（容量、预算、时间窗、数量限制等）

2. 逐个检查论文正文中的结果是否满足这些约束

3. 例如：题目说"车辆载重上限 6000kg"，论文写"装载 7344kg" → 矛盾，必须修正

4. 例如：题目说"30 个省份"，论文分析了 28 个 → 不完整，必须补充

5. 摘要中的数字是否与正文一致？

6. 不同章节引用同一个结果时数字是否一致？（如问题一的最优解在摘要、正文、结论中出现 3 次，必须完全相同）

```

如果发现矛盾，修改论文正文（不是修改约束）。如果是代码结果本身违反约束，说明代码有 bug，需要回到 comp-code 修复。

**⛔ Page count pre-check (MUST pass before finishing — do NOT leave this to compile step):**

> ⛔ 上限取 **PAGE_CAP**（`contest_profile.gate_page_cap`，本任务 operative 门禁口径）；计哪些页由 **PAGE_SCOPE**（`gate_page_scope`：`body`/`total`）决定——正文/总页数分开统计，不混成一个数。

> `PAGE_SCOPE=body`（如 `comp_cumcm`/`comp_huawei`）：上限只计正文（章节 1 - 结论，含图表），**不含**摘要 / 目录 / 参考文献 / **附录代码**；检查只统计 `paper/sections/*.tex`，附录代码归 `paper/appendix/*.tex`，单独不限页数。

> `PAGE_SCOPE=total`（如 `comp_mcm`，25 页按整本计）：对照**全文估算**检查，不拿正文估算充数（正文口径会静默少算）。

> **PAGE_CAP_STATUS**（`page_cap_status`）必须随数值一起上报：`unverified` = 来源未核验——**不产生默认硬页限**、不得当作已证官方规则，未知只使对应合规结论保持阻塞；仅 `official_verified` 或单独标识的显式任务授权（`task_override`）才按硬上限执行，禁止包装混充。

```bash

python skills/_utils/page_precheck.py --workspace . 2>/dev/null || python academic-toolkit/skills/_utils/page_precheck.py --workspace . 2>/dev/null || python ../../skills/_utils/page_precheck.py --workspace .

```

脚本做三件事：①代码块（lstlisting/verbatim 等）混进 sections/ 即违约——代码属 appendix/，混入会让估页虚高而实际正文薄；②字符估页（sections/ 900 字符/页）对照 PAGE_CAP，超限即违约；③附录单独统计不计入。cap 缺失=上限未知（待核实），禁止编默认值。finish 时 quick_gates 会以真实 PDF 按同一合同终检。cwd 语义：`--workspace .` 要求在工作区根执行；从工具箱根跑时改传 `--workspace workspaces/<工作区名>`。

不为凑任何页数目标扩写充数；章节完整性由写作合同保证（每个子问题覆盖、论断有证据支撑），篇幅随建模与论证需要自然形成。

⛔ **正文 vs 附录归档约束**：

- `paper/sections/` — 仅放正文章节（绪论 / 方法 / 结果 / 讨论 / 结论）

- `paper/appendix/` — 放代码 / 长数据表 / 求解日志 / 公式补充推导 / 算法伪代码

- 严禁把代码塞 sections/（会让页数预检虚高但实际正文薄）

⛔ **页数扩展约束（防幻觉）— 写公式 / 加过程图 / 加灵敏度时必须遵守**：

| 扩展方向 | ✅ 允许 | ⛔ 禁止 |

|---|---|---|

| **补公式推导** | 从 MODELING_REPORT.md 抄推导链；中间步骤展开（如 (a)→(b) 的代数变换写明）；编号 (1)(2)(3) 连续 | 凭印象写新公式；编"假设 X 服从 Y 分布"等没有依据的统计假设；公式里编数字（如 ρ=0.873） |

| **增过程图** | 用 plot_utils 真画图（gen_fig_xxx.py 跑出 PDF/PNG）；流程图节点对应 comp-code 实际算法步骤；TikZ 流程图节点文本与代码注释一致 | 用占位符；编一个不存在的算法步骤；流程图数字不与 RESULTS 一致 |

| **加灵敏度** | 必须**真跑** sensitivity 代码，把结果存 `figures/sensitivity_*.json`；表格数字从 json 读 | 直接在正文写"参数 α 增加 10% 时目标值下降 5.2%" 而**没有真跑实验** |

| **充实结果讨论** | 解读已有结果（results.json / RESULTS.md）；对比基准方法；分析误差来源 | 重复说同一件事；加"如表所示"水文；编未做的对比实验 |

⛔ **进阶扩展方向（按题型分类，所有数字必须真跑代码产出）**：

**🔹 通用扩展（任何题型都适用，每个能扩 3-8 页）**：

| 扩展模块 | 内容 | 必须真做的事 | 推荐图表 |

|---|---|---|---|

| **数据预处理章节** | 异常值检测（boxplot/Mahalanobis）/ 缺失值处理（均值/KNN/多重插补）/ 归一化（min-max/z-score/robust）/ 特征工程（PCA/多项式/交互项）/ 数据划分（8:1:1 或 K-Fold） | comp-code 跑预处理脚本，保存 `figures/preprocess_*.json` | EDA 概览 4-panel（basic #1+#5）/ 预处理前后 2-panel / 缺失值热图 / 相关性矩阵 |

| **多算法对比** | 同一问题用 ≥3 个算法解（GA/SA/PSO/Greedy / RF/XGBoost/LightGBM/DNN / SVM/Logistic/kNN） | 真跑所有算法，记录准确率/F1/RMSE/运行时间/收敛迭代数 | 收敛曲线对比（comp #1）/ Performance Profile（adv #25）/ 雷达图 / 方法对比柱状图 |

| **超参敏感性** | 学习率 / batch size / 正则化系数 / 树深度 / λ 罚项；用 grid search / 贝叶斯优化 / Optuna | 用 sklearn.model_selection 跑 GridSearchCV，保存 `figures/hpopt_*.json` | 超参敏感性热图 / 等高线图 / 学习曲线 2-panel |

| **消融实验**（ML 类必备） | 移除某组件看性能变化（完整方法 vs -A vs -B vs -C 各组件） | 真跑每个消融变体，保存 `figures/ablation_*.json` | Diverging Bar（adv #20）/ 消融对比表 |

| **复杂度分析** | 时间复杂度 O(N²)/O(N log N) / 空间复杂度 / 实测 wall clock time（不同 N 下） | 用 time.perf_counter() 真测，画 log-log 复杂度图 | 复杂度 log-log 图 / 内存占用曲线 |

| **理论支撑** | 收敛性证明（数值方法）/ 唯一性证明 / 可行性证明 / 稳定性分析 | 从 MODELING_REPORT.md 抄推导，不能新编；引文献 | TikZ 证明流程图（推导逻辑可视化） |

| **可解释性** | SHAP / LIME / PDP / 决策树可视化 / 注意力图（NN 类） | 用 shap.Explainer / lime 真跑，保存 `figures/explain_*.json` | SHAP 摘要图（adv #7）/ ICE+PDP（adv #26）/ 注意力热图 |

**🔹 工程优化类（A/B 题）专属扩展**：

| 扩展模块 | 内容 | 真做要求 |

|---|---|---|

| **多目标 Pareto** | 双目标 / 三目标 Pareto 前沿 + 决策偏好分析 | 用 NSGA-II / MOEAD 真跑（pymoo 库） |

| **鲁棒性分析** | 数据扰动 / 参数扰动下的解稳定性 | 蒙特卡洛 N=1000 次扰动 |

| **求解器对比** | Gurobi / CPLEX / SCIP / 自实现启发式 | 真跑各求解器对比 |

| **大规模数据扩展** | 100/1000/10000 实例规模下的算法表现 | 跑不同规模 benchmark |

**🔹 数据分析/ML 类（C/D 题）专属扩展**：

| 扩展模块 | 内容 | 真做要求 |

|---|---|---|

| **误差来源分解** | 偏差-方差权衡（bias-variance tradeoff）；噪声拆解 | 5×CV + 多模型测 bias 和 variance |

| **类别不平衡处理** | SMOTE / 欠采样 / 类别权重 | 真跑各方法对比 |

| **特征重要性** | 排列重要性 / SHAP / 信息增益 | 至少 2 种方法交叉验证 |

| **学习曲线诊断** | train / val 损失曲线，判断欠拟合 / 过拟合 | 真跑不同训练集大小 |

**🔹 综合建模类（E/F 题）专属扩展**：

| 扩展模块 | 内容 | 真做要求 |

|---|---|---|

| **多种建模思路对比** | 机理模型 vs 数据驱动 vs 混合模型；同一现象 3 种描述 | 真跑各建模思路 |

| **物理一致性检查** | 量纲检验 / 守恒律 / 边界条件 | 公式真验 |

| **仿真验证** | 数值仿真 vs 解析解 / 历史数据回测 | 真跑仿真代码 |

| **不确定性量化** | 蒙特卡洛 / Bootstrap / 贝叶斯后验 | N≥500 次重复 |

⛔ **仅当本轮确实扩展了章节，才立即重跑 facts_audit**（扩完当场抓虚构数字）：

> ⛔ **去重说明**：这与数据可追溯性一节的 `facts_audit.py --stage paper` 是**同一份检查**（[13][14][15][16]），后者是**权威终检、一定会跑**。本轮没扩展任何章节就跳过这里，不重复跑。

```bash

python skills/_utils/facts_audit.py --stage paper 2>/dev/null || python academic-toolkit/skills/_utils/facts_audit.py --stage paper 2>/dev/null || python ../../skills/_utils/facts_audit.py --stage paper

```

[15] 会抽 60 个 2 位以上小数浮点数核对溯源。**审计 FAIL 不允许结束**，必须把不能溯源的数字改回真实值或删掉。

⛔ **乱码防护（LaTeX 模式）**：

- 公式定界符：`\begin{equation} ... \end{equation}` 或 `$ ... $`（不要 markdown `$$...$$`）

- 特殊字符必须转义：`& → \&`、`% → \%`、`_ → \_`、`# → \#`、`~ → \~{}`、`^ → \^{}`

- 中英文混排：变量符号英文（如 R²、RMSE、α），描述中文；不要中英文之间多空格

- 中文标点和英文符号之间不加空格（如 `f(x)。` 而非 `f(x) 。`）

- 公式中含中文用 `\text{...}`（如 `\sum_{i \in \text{测试集}}`）

**Figure embedding verification（必须全绿才能进入 Step 7）**：

```bash

python skills/_utils/figure_layout_check.py paper/ 2>/dev/null || python academic-toolkit/skills/_utils/figure_layout_check.py paper/ 2>/dev/null || python ../../skills/_utils/figure_layout_check.py paper/

```

终检版覆盖：figures/*.pdf 全部被正文引用、FIGURE_MANIFEST 对账（规划→产出→嵌入逐环核对）、流程图堆叠。任何 ❌ 回对应章节补嵌/补画后再跑，直到全绿。

**⛔ 模板完整性自检（写完所有章节后必须跑，确认 main.tex 没有被破坏）：**

```bash

python skills/_utils/template_integrity_check.py --full 2>/dev/null || python academic-toolkit/skills/_utils/template_integrity_check.py --full 2>/dev/null || python ../../skills/_utils/template_integrity_check.py --full

```

通用五项（documentclass / sections input / 参考文献结构 / 附录结构 / 上标引用定义）+ 按 `CONTEST_ID` 自动带赛事专属检查（五一杯承诺书页与封面 logo、MathorCup·APMCM 的 cls 与队伍信息、华中杯 cls、华为杯标题约束）。任一失败 = main.tex 可能被意外重写，从模板重新复制、只替换占位符。

### Step 7: Output

数模竞赛: sections/ numbered by sub-problem (4_problem1.tex, 5_problem2.tex...)

统计建模: sections/ by academic structure (1_introduction.tex, 2_data_method.tex...)





## Key Rules

- ⛔ **AI 申报双件套自动生成（合规硬要求）**：竞赛要求正文参考文献前放“AI 工具使用声明”+ 独立支撑材料《AI工具使用详情.pdf》。生成/核验必须用确定性脚本 `_utils/build_ai_disclosure.py`（双副本同 shared-scripts/，规范见 `_utils/ai_disclosure_rules.md`）：工具/型号/日期/用途只来自用户确认的清单（`.mh/ai_disclosure.json`），禁止语言模型自由编写详情；正文声明位置在参考文献之前；交付前必跑 `--check-only` 反查闸。未使用 AI 时用脚本生成“未使用”声明并清理旧详情文件。
- ⛔ **AI 痕迹自检（交稿前必跑）**：`python ../../skills/_utils/ai_tell_check.py --strict paper/`（cwd=工作区根；双副本同 shared-scripts/）——工程/质检语汇（口径/闭环等）从提示词流进正文是实测最高频 AI 痕迹（10 工作区 442 次命中）；中文套话（值得注意的是/综上所述/不难发现/显而易见/在此基础上/随着…的发展）与工程词同级硬拦，`--strict` 下剩余空话（由此可见/换言之等）也计失败；exit 1 时必修。人工风格对照 `_utils/human_competition_paper_style.md`，风格检查 `python ../../skills/_utils/human_paper_style_check.py paper/`。
- **防过度/辩护性写作（修订轮主动推荐）**：修订或压缩页数时调 `anti-defensive-writing` 技能，删不必要的 hedge/免责声明/道歉式框架/过度解释——保留必要的范围、误差与方法学限定，删的是"可能在一定程度上"式空转措辞；深度检测可加跑 `anti-ai-detection` 技能（8 维度 AI 特征分析+改写建议）。与 ai_tell_check 互补：一个删 AI 痕迹语汇、一个删防御性冗余。

- Use templates from `templates/`, do not write main.tex from scratch

- Chinese/English abstracts: manual typesetting, not two `\begin{abstract}` environments

- Citation format: use whichever the template provides (stats: natbib `[1]`, cumcm: gbt7714 superscript, huazhong: thebibliography manual entries, wuyi: gbt7714-numerical)

- No `\hypersetup{colorlinks=true}` — conflicts with hidelinks

- 正文页数不超过引擎下发的赛事档案页数上限（无下限，不为凑页扩写）

- No team info — use placeholders

- Tables: three-line style (booktabs)

- Primary output: `paper/` directory, temp files: `_tmp/`

- ⛔ **本步骤只写论文 .tex 文件，不要重新生成图表 PDF、不要修改 code/*.py、不要重新运行分析代码。** 图表和数据已由前序步骤（paper-figure / comp-code）生成完毕，直接引用即可

- Large files: Bash heredoc

- ⛔ **Bash heredoc 必须用带引号的 `'EOF'`（防止 `\\` 被转义）：**

  - ✅ 正确：`cat << 'EOF' > paper/sections/4_problem1.tex`（引号内 `\\` 原样保留）

  - ❌ 错误：`cat << EOF > paper/sections/4_problem1.tex`（无引号，`\\` 变成 `\`，导致表格 `Misplaced \noalign` 错误）

  - 这是表格编译失败的最常见原因——40+ 处 `\\` 全部变成 `\`，编译器只报第一个错就停了

## ⛔ 数据可追溯性（写稿强制规则）

> 防止「图文表面自洽但数据是历史版本」的 bug。详见 `_utils/error_prevention.md` 第九章。

正文/图表/附录引用的**每一个具体数字**必须满足：

1. 能在当前 `results.json` 或 `figures/all_results.json` 里 `grep` 到

2. RESULTS.md 末尾有 `<!-- AUDIT_OK source=results.json rechecked_at=<timestamp> -->` 凭证

3. 工作区没有 `results_v*.json` / `results_old.json` 等历史文件残留

4. 描述任何"依赖载体 / 上游变量动态变化的派生属性"（作用范围 / 时变参数 / 状态依赖容量 / 时变转化率等）时，**禁止**简化成"以静态点为中心的固定区域"或"取均值后当常数"，除非确为静态实体且已显式声明简化条件

写完正文前自检（数据追溯）：

```bash

grep -q '<!-- AUDIT_OK source=' RESULTS.md || echo "❌ 缺 AUDIT_OK 凭证 — 先回 comp-code 跑约束审计"

ls results_v*.json results_old.json *_backup.json 2>/dev/null && echo "⚠ 历史版本 JSON 残留（版本漂移源），确认后删除"

(python skills/_utils/facts_audit.py --stage paper 2>/dev/null || python academic-toolkit/skills/_utils/facts_audit.py --stage paper 2>/dev/null || python ../../skills/_utils/facts_audit.py --stage paper) 2>&1 | tee -a AUDIT_REPORT.md

```

`facts_audit --stage paper` 是权威终检：[13] 正文结论一致性、[14] 事件源归属（谁做了什么 N 次的指向性陈述必须能从 results.json 的 verb_to_sources/events 反推）、[15] 数字溯源（60 采样+容差匹配）。**exit 1 = 正文有与 results.json 不一致或无法溯源的数字——改回真实值或删除，禁止带病编译。**

## 退出判据（Verification）

本步完成前逐项自检（不达标即视为未完成）：

- [ ] 章节结构与模板要求一致（不照抄模板文字）
- [ ] 摘要含结论性数值而非空话
- [ ] 每个数值与图表可在账本中溯源
- [ ] 正文页数在规则上限内（附录另计）

## 常见合理化（Common Rationalizations）

| 合理化 | 现实 |
|---|---|
| "字数够了就行" | 体量不等于质量：本项目真实教训是产物只有目录级厚度的形式合规。 |
| "摘要最后再补" | 摘要是评审第一眼；后补的摘要往往与正文结论脱节。 |
| "页数超一点没关系" | 页数是官方硬性上限，属交付阻断项，不存在超一点的说法。 |

> 本段与 `skills/_utils/anti_rationalization.md`（全局版）配套：本表是本步专属，
> 全局版覆盖跨步骤通用借口。新增借口时优先落到本表（更贴岗位），能泛化再上升。

## 版式参考（paper-layout）

- `references/mml-skills/paper-layout/`：论文版式六件（core/body-density/page-composition/latex-figures/latex-math/docx-figures）——排版与图表密度决策时按需读。（来源 Math-model-skills，MIT，溯源见同目录 UPSTREAM.md）
