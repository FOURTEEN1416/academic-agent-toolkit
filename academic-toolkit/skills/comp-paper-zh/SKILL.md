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

## Load shared rules（按需读，禁止整篇下发）

`writing_rules.md` 是共享写作规则的唯一真源（`skills/_utils/writing_rules.md`，与 `skills/shared-scripts/writing_rules.md` 同源），**不在这里复制正文**。整篇 65KB 一次 cat 会把注意力预算从论证上挤走：先取 tag 目录，再只读本章实际需要的 1-2 节。

```bash
RULES=skills/_utils/writing_rules.md
[ -f "$RULES" ] || RULES=academic-toolkit/skills/_utils/writing_rules.md
[ -f "$RULES" ] || RULES=../../skills/_utils/writing_rules.md
awk '/^<[a-z_]+>$/ {print NR": "$0}' "$RULES"   # tag 目录；行号随改版漂移，以实跑输出为准
```

| tag | 何时读 |
|---|---|
| `<figure_text_interleaving>` | 写含图表的章节（图前后文字、图注长度、"图表是论据"） |
| `<figure_embedding>` | 嵌图 / TikZ / 多面板 / 防遮挡 |
| `<latex_constraints>` | 本步第一次写公式、表格、浮动体 |
| `<page_filling>` | 页数明显偏少、需要补版面时 |
| `<abstract_requirements>` | Step 5.6 写摘要（Step 2 只落占位，不读正文规格） |
| `<resume_strategy>` | 断点续写 |
| `<chapter_context_card>` | 每章收尾的要点卡、写下一章前 |
| `<de_ai_polish>` | Step 5.5 去 AI 味 |
| `<references_workflow>` | Step 5 参考文献 |
| `<output_conventions>` | 产出命名与落盘 |

**只取需要的 tag**（例：本章要嵌图）：

```bash
for t in figure_text_interleaving figure_embedding; do
  awk -v s="<$t>" -v e="</$t>" '$0==s{f=1} $0==e{f=0} f' "$RULES"
done
```

例外：Step 5.5 的 `<de_ai_polish>` 一节全读（那节本身就是终稿改写清单）；其余未命中本章任务的 tag 不读。

## 赛事结构 → `skills/comp-paper-zh/references/format-playbook.md` §1

只有两族结构，按 `CONTEST_ID` 读对应那一段（不要两段都读）：

| 赛事族 | 结构类型 | 读法（playbook §1） |
|---|---|---|
| 数模族：`comp_cumcm` / `comp_huawei` / `comp_mathorcup` / `comp_huazhong` / `comp_wuyi` / `comp_apmcm_zh` / `comp_csf` / 其余 `comp_*` | 固定骨架：摘要 → 问题重述 → 模型假设 → 符号说明 → 各子问题章 → 灵敏度与检验 → 模型评价与推广 → 参考文献 → 附录 | `awk '/^### 数模竞赛/{f=1} /^### 统计建模/{f=0} f' skills/comp-paper-zh/references/format-playbook.md` |
| `comp_stats` | 内容驱动骨架：表格清单 → 插图清单 → 中英文摘要 → 绪论 → 2-4 个内容章 → 结论与建议 → 参考文献 → 致谢 → 附录 | `awk '/^### 统计建模/{f=1} f' skills/comp-paper-zh/references/format-playbook.md` |

**硬门禁（不读 playbook 也必须守）：** ① 章序与文件名必须和模板 `\input{sections/...}` 一致；② 模型假设在符号说明之前；③ 每个子问题独立成章、独立给结果；④ `comp_stats` 固定保留表格清单/插图清单/中英文摘要/绪论/结论/参考文献/致谢。

## 赛事合规硬门禁（写稿前必读；不随结构细则进 playbook）

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

## ⛔⛔⛔ 完成铁律（最高优先级）

**根据 `params.output_format` 决定主产物**：

- **PDF 模式（默认）**：`paper/main.tex`（≥ 5KB）+ `paper/sections/*.tex` + `paper/references.bib`

- **docx 模式**：`paper/main.md`（单文件，≥ 5KB）。**禁止产 paper/main.tex**


产出结构、存在性和最低完整性由 `finish` 按模板中的 `output_contract` 自动核验；修复返回的具体问题，不复制执行验证脚本。


## 引用命令（全技能单一真源）

正文引用命令按模板定，步骤文件不再另行判断：

| 模板族（`CONTEST_ID` → `_templates/<dir>`） | 正文命令 | 依据 |
|---|---|---|
| `comp_huawei`(huawei) / `comp_stats`(stats) / `comp_mathorcup`(mathorcup) / `comp_apmcm_zh`(apmcm_zh) / `comp_huashu`(huashubei) / `comp_liaoning`(dongsansheng)：natbib + `super` | `\cite{key}`（自动上标） | `huawei/main.tex`、`mathorcup/MathorCupmodeling.cls`、`apmcm_zh/MathorCupmodeling.cls`、`huashubei/JXUSTmodeling.cls`、`stats/main.tex`、`dongsansheng/main.tex` |
| `comp_cumcm` / `comp_huazhong`（cumcmthesis，无 natbib；cls 定义 `\upcite`） | `\upcite{key}`（上标）；`\cite` 是行内 `[1]` | `cumcm/cumcmthesis.cls` |
| `comp_wuyi`（cumcmthesis + natbib `[numbers]`；cls 定义 `\upcite`） | `\upcite{key}` | `wuyi/main.tex`、`wuyi/cumcmthesis.cls` |
| `comp_shuwei`(shuweibei)：`main.tex` 内置上标 hack，无 `\upcite` | `\cite{key}`（上标） | `shuweibei/main.tex` |
| 其余（`comp_yangtze` / `comp_diangong` / `comp_csf`、`default` 族）：手写 `thebibliography` 或 `plainnat`，未配上标 | `\cite{key}`；赛事要求上标时用 `\textsuperscript{\cite{key}}` | 模板实况 |

⛔ `\upcite` 只在 cumcm / 华中杯 / wuyi / dongsansheng 的 cls 里有定义；对其他模板写 `\upcite` 会 undefined control sequence、整篇编译失败。

## Workflow（分步路由；每步只读自己的细则）

固定顺序 Step 0 → Step 7。**每步动手前整篇读该步的细则文件（`skills/comp-paper-zh/references/step_*.md`，见各步「细则」行）；只读当前步那一份，不要一次读完所有 step 文件。** 判据不全绿不得进入下一步。

### Step 0: 上游校验 + 断点续写判定

**触发**：进入本技能第一步；续写任务先判占位。**细则**：`skills/comp-paper-zh/references/step_0_preflight.md`

- 上游 `PROBLEM_ANALYSIS.md`、`MODELING_REPORT.md`、`RESULTS.md` 存在且非空壳；子问题覆盖 `MODEL_COUNT ≥ PROB_COUNT`，不足回上游补齐再写。
- `paper_claim_check.py` 的 `PCC`：0 或 2 可写；**1 = 有能力项在编码阶段就没通过 → 回 comp-code 做到 PASS 再写论文**。
- 续写口径：`paper/sections/*.tex` <500 字符或含「待补充/placeholder」= 占位章，续写；>2000 字符 = 已完成，跳过；每写完一章立即落盘。

### Step 1: Select template（只认规范 CONTEST_ID；拒绝猜测，无默认）

**触发**：Step 0 通过后，建 `paper/sections` 并落模板。**细则**：`skills/comp-paper-zh/references/step_1_template.md`（复制循环、字体/书目族随迁、落地断言、main.tex 必读、华为杯专项）

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
    comp_csf)        TMPL="csf" ;;          # 仿真建模应用挑战赛（ctexart + csf.sty；官方《论文规范》未取证，版式保持保守默认）
    comp_teddy|comp_certcup|comp_zhongqing|comp_tianfu|comp_shenzhen|comp_huadong)
        # 档案 template_cls: ctexart，暂无专用目录 → 通用 ctexart 骨架（_templates/default/）。
        # 这是档案指定文档类对应的通用骨架，不是跨赛事套用；专用模板入库后改回专属目录。
        TMPL="default" ;;
    *)
        echo "⛔ 未知赛事 ID: '$CONTEST_ID'（须为 comp_rules.json 顶层键的 comp_* 规范 ID）。拒绝猜测、不回退国赛。" >&2
        exit 1 ;;
esac
```

**放行判据**：

- 未知赛事 ID 或 `CONTEST_ID` 缺失 → 立刻停下（不回落国赛、不猜）；模板目录缺失 → 报能力缺口停止，不改用其他赛事模板。
- 复制后 `template_integrity_check.py --fingerprint` 必须通过：`paper/main.tex` 前 20 行 preamble 与模板差异 >10 行 = 骨架被重写，从模板重新复制。
- 只改 `sections/*.tex`，不重写 `main.tex`（骨架纪律见 `skills/comp-paper-zh/references/format-playbook.md` §2）。
- **同文档类复用核对**：复用骨架不携带另一赛事的封面、队号或声明。

### Step 2: Abstract 占位

**触发**：模板就位后。**细则**：`skills/comp-paper-zh/references/step_2_abstract.md`（本步只执行「占位」段；摘要规格到 Step 5.6 才整篇执行）

- **现在不写摘要正文**，只落占位 `[摘要待正文完成后填写]`——摘要必须最后写（数值来自全部章节），先写等于编数。
- 丰满模式判据：`CONTEST_ID = comp_huawei`，或 AGENTS.md 含 `丰满模式`/`rich_mode` 用户开关。
- 字数 / 六要素 / 分段骨架的唯一事实源：`skills/_utils/abstract_writing_contract.md`。

### Step 3: 图表清单与嵌入计划

**触发**：写任何章节之前。**细则**：`skills/comp-paper-zh/references/step_3_figure_plan.md`

- 先产 `FIGURE EMBEDDING PLAN`（每张图 → 章 / caption）；只嵌实际存在的 PDF。
- 每张嵌入图同步写**引用句 + 解读句**；零 `\ref` 引用或零解读的图由 `figure_narrative` 闸拒绝完成——没有解读可写的图不要嵌。
- caption 必须中文、单行、≤20 个汉字（不含「图 N」）；判据 / 参数 / 结论写正文。
- 图用 `[H]` 就地、宽度 ≥0.85\textwidth（不得 <0.8）；两个 `figure` 环境不得直接相邻。
- 子问题流程图分到各自问题章（`2_analysis` 最多放一张整体技术路线图）。
- 每写完一章跑 `figure_layout_check.py paper/`，任何 ❌ 当场修。

### Step 3.5: 文献预检索

**触发**：写任何 `\cite{}` 之前。**细则**：`skills/comp-paper-zh/references/step_3_5_literature.md`

- 先建 `_tmp/_verified_refs.txt`，正文只引用池内已验证文献；需新引用先搜再加池。
- 往届论文页面图 / `academic-toolkit/data/historical_papers.md` 只作写法借鉴，无著录信息，**禁止据此编造 bib 条目**。
- `scholar_fetch.py` 搜不到或 `match_label=low` → WebSearch 核实标题 + 作者 + 年份后再入池。

### Step 4: 写各章

**触发**：图表计划与文献池就绪后。**细则**：`skills/comp-paper-zh/references/step_4_chapters.md`（整篇读；写作方法展开见 `skills/comp-paper-zh/references/writing-playbook.md`，按节读）

- 数字只来自 `RESULTS.md` / `figures/*.json`；**禁止 `cat figures/*_results.json`**，先跑 `summarize_results.py` 取 KB 级摘要。
- 章序与文件名必须和模板 `\input{sections/...}` 一致；模型假设在符号说明之前；假设 4-5 条（上限 6 条）；符号 15-20 个。
- 正文禁 `itemize` / `enumerate`（假设与附录除外）；符号表用 `longtable`；>12 行数据表正文放缩略、附录放完整。
- 每个 headline number 带「差在哪 / 为什么 / 改变什么决策」，禁止裸数字复述；创新点按 `skills/_utils/innovation_contract.md`。
- 每章收尾把 3-5 行要点卡追加到 `_writing_context.md`，写下一章前先读。
- 本章写完自查体量：`wc -c paper/sections/当前章节.tex`（≈900 字符/页）。

### Step 5: 参考文献

**触发**：正文各章完成、引用 key 稳定后。**细则**：`skills/comp-paper-zh/references/step_5_references.md`

- BibTeX 一律经 `scholar_fetch.py` 获取，**禁止凭记忆编造**；`match_label=low` 换关键词或 WebSearch 核实。
- 引用编号全局严格递增；多引用合并按编号升序。
- citation key 用 `作者姓_年份_主题关键词`；未定项用 `TODO__` 前缀。
- 正文引用命令见上「引用命令」表（唯一真源）。

### Step 5.5: De-AI polish

**触发**：全文写完、编译前。**细则**：`skills/comp-paper-zh/references/step_5_5_deai.md`

- `python ../../skills/_utils/ai_tell_check.py --strict paper/` 必须 exit 0（本步受引擎 `ai_flavor` 闸：硬伤 + 空话 >3 处直接拒绝完成）。
- 工程 / 质检语汇、中文套话、内部标记（⛔✅❌ / RESULTS.md 等文件名 / HC-01 类编号）清零。

### Step 5.6: 写摘要（现在）

**触发**：全部正文章节完成后（Step 5 之后）。**细则**：`skills/comp-paper-zh/references/step_5_6_abstract_final.md`；摘要格式整篇读 `skills/comp-paper-zh/references/step_2_abstract.md`

- 只写正文已出现的数字，不改精度、不编造。
- 每问独立成段；统计建模写中英文双语摘要。
- 写完跑 `abstract_paragraph_check.py`，直到输出「✓ 摘要按问题分段正确」。

### Step 6: Final verification

**触发**：正文与参考文献定稿后、产出前。**细则**：`skills/comp-paper-zh/references/step_6_final_verification.md`

- `writing_check.sh paper/` 全绿；`paper_claim_check.py` 的 WARN 逐条确认（`PCC≠1`）。
- 论文-题目约束一致性逐条核对：摘要 / 正文 / 结论里同一结果的数字必须相同。
- `page_precheck.py --workspace .` 不超 `PAGE_CAP`，口径按 `PAGE_SCOPE`；cap 缺失 = 待核实，禁止编默认值。
- 代码只进 `paper/appendix/`；`figure_layout_check.py` 与 `template_integrity_check.py --full` 全绿。
- 扩写只往建模深度 / 结果可信度扩，不往算法叙述扩；本轮扩过章节就重跑 `facts_audit.py --stage paper`。

### Step 7: Output

**触发**：Step 6 全绿后。**细则**：`skills/comp-paper-zh/references/step_7_output.md`

- 章节文件按赛事族命名（数模按子问题编号；统计按学术结构）。
- 主产物按 `params.output_format`：PDF 模式 `paper/main.tex`（≥5KB）+ `paper/sections/*.tex` + `paper/references.bib`；docx 模式 `paper/main.md`（单文件 ≥5KB，禁止产 main.tex）。
- 产出结构 / 最低完整性由 `finish` 按 `output_contract` 核验，不另写验证脚本。

## Key Rules

- ⛔ **AI 申报双件套自动生成（合规硬要求）**：竞赛要求正文参考文献前放“AI 工具使用声明”+ 独立支撑材料《AI工具使用详情.pdf》。生成/核验必须用确定性脚本 `_utils/build_ai_disclosure.py`（双副本同 shared-scripts/，规范见 `_utils/ai_disclosure_rules.md`）：工具/型号/日期/用途只来自用户确认的清单（`.mh/ai_disclosure.json`），禁止语言模型自由编写详情；正文声明位置在参考文献之前；交付前必跑 `--check-only` 反查闸。未使用 AI 时用脚本生成“未使用”声明并清理旧详情文件。
- ⛔ **AI 痕迹自检（交稿前必跑）**：`python ../../skills/_utils/ai_tell_check.py --strict paper/`（cwd=工作区根；双副本同 shared-scripts/）——工程/质检语汇（口径/闭环等）从提示词流进正文是实测最高频 AI 痕迹（10 工作区 442 次命中）；中文套话（值得注意的是/综上所述/不难发现/显而易见/在此基础上/随着…的发展）与工程词同级硬拦，`--strict` 下剩余空话（由此可见/换言之等）也计失败；exit 1 时必修。人工风格对照 `_utils/human_competition_paper_style.md`，风格检查 `python ../../skills/_utils/human_paper_style_check.py paper/`。
- **防过度/辩护性写作（修订轮主动推荐）**：修订或压缩页数时调 `anti-defensive-writing` 技能，删不必要的 hedge/免责声明/道歉式框架/过度解释——保留必要的范围、误差与方法学限定，删的是"可能在一定程度上"式空转措辞；深度检测可加跑 `anti-ai-detection` 技能（8 维度 AI 特征分析+改写建议）。与 ai_tell_check 互补：一个删 AI 痕迹语汇、一个删防御性冗余。

- Use templates from `templates/`, do not write main.tex from scratch

- Chinese/English abstracts: manual typesetting, not two `\begin{abstract}` environments

- Citation command: 按模板取，唯一真源见上「引用命令」表。

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
