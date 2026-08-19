---

name: comp-prob-analysis

description: "数学建模竞赛赛题分析。拆解子问题、定义变量、拟定建模思路。Use when user says \"赛题分析\", \"problem analysis\", \"分析题目\"."

argument-hint: [competition-problem-text]

allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, WebSearch, WebFetch, Agent

---

# 竞赛赛题分析

对以下赛题进行深度分析：**$ARGUMENTS**

## ⚡ 快速模式检测（开头先跑）

```bash

FAST_MODE=0

grep -q 'MH_FAST_MODE=1' CLAUDE.md 2>/dev/null && FAST_MODE=1

echo "FAST_MODE=$FAST_MODE"

```

**若 `FAST_MODE=1`（速度优先）：** 仍必须产出完整的 PROBLEM_ANALYSIS.md（子问题拆解完整、变量定义、建模思路、图表清单 FIGURE_MANIFEST；题面参数密集时 PROBLEM_FACTS.json 仍要建），但**跳过**：反复推敲措辞的打磨、过度深挖的扩展分析。一次成型、结构齐全即可。**若 `FAST_MODE=0`（默认）：** 后文照常。

## 常量

- **COMPETITION** / **PROBLEM_ID** / **LANGUAGE** — 从 Additional Parameters 读取

- **TOOLS** — 默认 `python`

- **CUSTOM_REQUIREMENTS** — 用户自定义要求

## 输入

1. 赛题文本（$ARGUMENTS 或 `user_data/` 中的 PDF/Word 文件）

2. 附件数据（`user_data/*.csv` 等）

## ⛔⛔⛔ 完成铁律（最高优先级，违反则本步骤失败）

**本步骤必须产出 `PROBLEM_ANALYSIS.md`（≥ 1.5KB，完整的赛题分析）+ FIGURE_MANIFEST 区块 + `CAPABILITY_CHECKLIST.json`（能力清单）**。

⛔ **能力清单结构校验（结束前必跑，零额度两模式都跑）**：

```bash

python _utils/capability_check.py --checklist CAPABILITY_CHECKLIST.json --analysis PROBLEM_ANALYSIS.md

CAP=$?   # 0=结构合格 1=结构非法/漏拆子问题(必修) 2=无清单

```

> `CAP=1`（漏拆子问题、machine 项没挂闸、字段非法）必须先修再结束本步骤——能力清单是下游"题型无关验收"的契约，结构不合格 comp-code 的语义校验器就没法逐项验收，题目要的能力会被悄悄降维。`CAP=2`（无清单）：除非纯建模题确实无可拆能力项，否则必须补出清单。

⛔ **结束前必跑产出验证**：

```bash

PASS=true

# 1. 文件大小

[ -f PROBLEM_ANALYSIS.md ] && SZ=$(wc -c < PROBLEM_ANALYSIS.md) || SZ=0

if [ "$SZ" -ge 1500 ]; then

    echo "✅ PROBLEM_ANALYSIS.md ($SZ bytes)"

else

    echo "❌ PROBLEM_ANALYSIS.md 缺失或过小 ($SZ bytes) — 必须补全后重新跑验证, 不要结束本步骤"

    PASS=false

fi

# 2. ⛔ FIGURE_MANIFEST 区块必须存在 (下游 paper-figure / paper-figure-drawio 按它对账)

# 不写就会让用户踩"画了 1 张就跳过"的死循环 bug

if grep -q '<!-- BEGIN FIGURE_MANIFEST -->' PROBLEM_ANALYSIS.md 2>/dev/null \

    && grep -q '<!-- END FIGURE_MANIFEST -->' PROBLEM_ANALYSIS.md 2>/dev/null; then

    # 数下规划了几张图

    START=$(grep -n '<!-- BEGIN FIGURE_MANIFEST -->' PROBLEM_ANALYSIS.md | head -1 | cut -d: -f1)

    END=$(grep -n '<!-- END FIGURE_MANIFEST -->' PROBLEM_ANALYSIS.md | head -1 | cut -d: -f1)

    MANIFEST_CONTENT=$(sed -n "${START},${END}p" PROBLEM_ANALYSIS.md)

    # 总图数（数据图 + DrawIO 流程图 + TikZ + GPT Image 合计）— 仅供参考

    TOTAL_COUNT=$(echo "$MANIFEST_CONTENT" | grep -cE '^[[:space:]]*-[[:space:]]+(fig_[a-zA-Z0-9_]+|tikz_[a-zA-Z0-9_]+)')

    # ⛔ 前缀合规硬校验：没前缀的图名（image2/图2/chart1）会被下游对账静默漏掉、图不生成 → 硬阻塞

    BAD_NAMES=$(echo "$MANIFEST_CONTENT" | grep -E '^[[:space:]]*-[[:space:]]+' | grep -vE '^[[:space:]]*-[[:space:]]+(fig_|tikz_)' | sed -E 's/^[[:space:]]*-[[:space:]]*//')

    if [ -n "$BAD_NAMES" ]; then

        echo "❌ FIGURE_MANIFEST 有图名缺少 fig_/tikz_ 前缀，会被下游对账漏掉、导致图静默不生成，必须改名（如 image2 → fig_q1_xxx）："

        echo "$BAD_NAMES" | sed 's/^/    · /'

        PASS=false

    fi

    # ⛔ 数据图（DATA 类，matplotlib 产出的 .png/.pdf）单独计数

    #    12-20 张阈值【只针对数据图】，流程图（DrawIO）/ 推导示意（TikZ）不计入此阈值

    #    优先从 FIGURE_MANIFEST 末尾的 "**总数：DATA=N, ...**" 标记提取

    DATA_COUNT=$(echo "$MANIFEST_CONTENT" | grep -oE 'DATA=[0-9]+' | head -1 | grep -oE '[0-9]+')

    # Fallback：DATA= 标记缺失时，用 awk 在 "**数据图**" 章节内数 - fig_ 行

    if [ -z "$DATA_COUNT" ]; then

        DATA_COUNT=$(echo "$MANIFEST_CONTENT" | awk '

            /^\*\*数据图/ { f=1; next }

            /^\*\*/       { f=0 }

            f && /^[[:space:]]*-[[:space:]]+fig_/ { c++ }

            END           { print c+0 }

        ')

    fi

    DATA_COUNT=${DATA_COUNT:-0}

    # ⛔ 检查策略（区分硬阻塞和软引导）：

    #   1. 真"非空"硬底线 ≥3 张（少于这个 = 工作严重不完整，硬阻塞）

    #   2. 用户在「高级选项」显式指定 MIN_FIGURES > 0 → 硬阻塞达不到（用户硬要求）

    #   3. 其他情况 → 仅软引导（参考值 12-20 张，AI 按赛题复杂度自由规划）

    source .env_skill 2>/dev/null || true

    HARD_FLOOR=3

    SOFT_REF_LOW=12

    SOFT_REF_HIGH=20

    USER_REQ=""

    if [ -n "$MIN_FIGURES" ] && [ "$MIN_FIGURES" -gt 0 ] 2>/dev/null; then

        USER_REQ="$MIN_FIGURES"

    fi

    if [ "$DATA_COUNT" -lt "$HARD_FLOOR" ]; then

        # 真"非空"硬底线 — 数据图少于 3 张工作严重不完整

        echo "❌ FIGURE_MANIFEST 数据图(DATA 类) 只 $DATA_COUNT 张, 低于最低底线 $HARD_FLOOR 张"

        echo "   (总图含流程图/示意 = $TOTAL_COUNT 张) — 工作严重不完整，必须扩展数据图后重新验证"

        PASS=false

    elif [ -n "$USER_REQ" ] && [ "$DATA_COUNT" -lt "$USER_REQ" ]; then

        # 用户显式指定硬目标

        echo "❌ FIGURE_MANIFEST 数据图(DATA 类) $DATA_COUNT 张 < 用户在前端「高级选项」指定的 MIN_FIGURES=$USER_REQ"

        echo "   (总图含流程图/示意 = $TOTAL_COUNT 张) — 必须扩展数据图到 >= $USER_REQ 张后重新验证"

        PASS=false

    else

        # 通过：根据是否达到参考区间给不同语气提示（不阻塞）

        if [ "$DATA_COUNT" -lt "$SOFT_REF_LOW" ]; then

            echo "✅ FIGURE_MANIFEST 数据图 $DATA_COUNT 张(总图 $TOTAL_COUNT) — 通过底线"

            echo "   ⚠ 参考值: 竞赛论文标准 $SOFT_REF_LOW-$SOFT_REF_HIGH 张数据图, 当前略少"

            echo "   ℹ 是否扩展由你根据赛题复杂度决定 — 不强制，但 $DATA_COUNT 张数据图对 30 页论文偏稀"

            echo "   📊 如需扩展可考虑(每个子问题 2-3 张): 趋势/对比/分布/热力/灵敏度/Pareto/SHAP 等"

            echo "   🔄 流程图/推导示意(DRAWIO/TIKZ)按需另算, 不计入数据图参考值"

        elif [ "$DATA_COUNT" -le "$SOFT_REF_HIGH" ]; then

            echo "✅ FIGURE_MANIFEST 数据图 $DATA_COUNT 张(总图 $TOTAL_COUNT) — 落在推荐区间 $SOFT_REF_LOW-$SOFT_REF_HIGH 张"

        else

            echo "✅ FIGURE_MANIFEST 数据图 $DATA_COUNT 张(总图 $TOTAL_COUNT) — 超过推荐上限 $SOFT_REF_HIGH, 富余度高"

        fi

    fi

else

    echo "❌ PROBLEM_ANALYSIS.md 缺少 FIGURE_MANIFEST 区块 — 必须按本 SKILL 「图表预规划」一节追加完整的 <!-- BEGIN/END FIGURE_MANIFEST --> 区块"

    PASS=false

fi

[ "$PASS" != true ] && echo "⛔ 验证未通过 — 必须修复后重新跑验证, 不要结束本步骤"

```

### ⛔ 参数密集型题目额外门槛（题面参数 ≥ 20 时必跑）

若题面参数 ≥ 20（武器性能 / 距离 / 时间 / 概率 / 规则等可量化条目），本步骤必须产出 `PROBLEM_FACTS.json` + `PARAMS_RAW.md`，并**在结束本步骤前**跑 OCR 客观比对：

```bash

# 第一步审计：纯 OCR 客观比对（防 AI 抄题面时虚构 / 漏抄 / 串台）

python3 _utils/facts_audit.py --stage prob 2>&1 | tee AUDIT_REPORT.md

RC=$?

if [ $RC -eq 1 ]; then

    echo "⛔ 第一步审计失败：facts 与 OCR 原文不一致。必须修复 PROBLEM_FACTS.json 后重新跑，不要结束本步骤。"

    echo "   常见原因：facts 里写的数字在 user_data/*_extracted.txt 里 grep 不到（虚构）；source_files 的 sha256 不一致（OCR 被改）"

elif [ $RC -eq 2 ]; then

    echo "⚠ 第一步审计有警告（如 OCR 数字过多未登记），可继续但建议人工抽检"

else

    echo "✅ 第一步审计通过：facts 与 OCR 原文一致"

fi

```

**为什么必须在第一步就跑**：题面参数虚构是"根因型 bug"，错一个数会污染下游所有 step（建模、编码、写稿全部基于错误前提）。在第一步抓出 = 修一次；在第三步 comp-code 才抓出 = 已经污染了 comp-modeling，修起来要返工三步。

## 工作流程

### Step 0: 读取赛题原文 + 上游规划

**⛔ 赛题读取优先级（严格按此顺序，不要跳过）：**

```bash

# 第一步：检查是否有 Vision OCR 提取的文本（公式最准确）

echo "=== 检查赛题文本 ==="

for f in user_data/*_extracted.txt; do

    [ -f "$f" ] || continue

    echo "找到提取文本: $f"

    head -3 "$f"  # 查看是否有 "Vision OCR" 标记

done

```

1. **`user_data/*_extracted.txt`（最高优先级）** — 系统已用 Vision AI 识别 PDF 生成，公式为 LaTeX 格式（如 `$k = 2 \times 10^7$`），直接 Read 读取

2. `user_data/*.pdf` — **⛔ 禁止直接用 Read 工具读 PDF！** PDF 的数学公式会变成乱码（如 `7210` 实际是 `$7 \times 10^2$`）。如果没有 `_extracted.txt`，用下面的脚本提取

3. `$ARGUMENTS` 文本 — 用户在创建工作流时输入的文字

**⛔ 绝对不要直接 Read PDF 文件。** PDF 中的上标、下标、数学符号无法正确提取，会导致参数值错误（如 $10^7$ 变成 "107"）。必须读 `_extracted.txt`。

**如果 TOPIC_PLAN.md 存在（统计建模选题规划），先读取它**，确保分析方向与选题规划一致：

```bash

[ -f TOPIC_PLAN.md ] && echo "=== TOPIC_PLAN.md exists ===" && cat TOPIC_PLAN.md || echo "No TOPIC_PLAN.md (normal for math modeling competitions)"

```

只有在没有 `_extracted.txt` 时才尝试提取：PDF 用 pdftotext 或 PyPDF2，Word 用 python-docx。

### Step 1: 赛题全文解读

提取：背景信息、核心问题、已知条件、评价标准。

**⛔ 子问题数量识别规则（必须严格遵守）：**

- 只有赛题中明确编号的顶层问题才算子问题。常见格式：

  - "问题一"、"问题二"、"问题三"（中文编号）

  - "问题1"、"问题2"、"问题3"（阿拉伯数字）

  - "Problem 1"、"Problem 2"（英文）

  - "(一)"、"(二)"、"(三)"（带括号中文编号）

- **不要把子问题内部的小问 (1)(2)(3) 或 a/b/c 当成独立子问题**——它们是同一个子问题的不同部分

- **不要把背景描述、数据说明、提交要求当成子问题**

- 如果赛题只有 2 个问题，就是 2 个，不要凑成 3-4 个

- 识别完后在报告开头明确写出："本赛题共 X 个子问题"

### Step 1.2: 关键概念对齐表 + 任务回译（⛔ 必做，治"赛题读歪"——理解层最上游的锚点）

⛔ **这是防"整道题方向错"的地基**：下游所有合同/台账/能力清单都建立在"你对题目的理解"上，若这里理解歪了，全链会一致地歪、且全部绿灯（因为下游只核"是否忠于你的声明"，不核"你的声明是否忠于原文"）。本步用**题目原文当独立锚点**，把理解显性化、摆到原句旁边，让人和复核 AI 一眼可查。

**1. 关键概念对齐表**：对每个**核心目标 / 关键约束 / 关键物理量**，三列并排写进 `PROBLEM_ANALYSIS.md`：

| 题目原文怎么说（原句片段） | 我理解成什么（一句话精确定义） | 对应数学符号/公式 |

|---|---|---|

| "求覆盖宽度"（原文S3） | 测线垂直方向被覆盖的水平距离 W | W = ... |

| "使总成本最小"（原文S5） | 目标函数=建设+运营，min | min C = ... |

> - ⛔ **"原文片段"必须是题目里真实出现的字句**（可引 Step5.6 逐句表的句号 S1/S2），不许编一个不存在的"原文"。

> - ⛔ **误解会直接暴露在"原句 vs 我理解"的并排对比里**——如把"覆盖宽度"理解成"覆盖面积"、把"最小"看成"最大"、把"垂直于测线"理解成"垂直于海底"，摆在原句旁边一眼看穿。

> - 每个关键量还要标**单位/量纲**（防单位误解：m vs km、角度 vs 弧度）。

**2. 任务回译自检**：用**一句话**复述"这题到底要我求什么"，与题目原文并列，自问三条——

1. 我复述的任务，和题目原句要的，是**同一件事**吗？（求 W 不是求面积、求最优不是求可行）

2. 目标的**方向**对吗？（最小化/最大化、上界/下界）

3. 有没有把**某个要求理解反或漏掉**？

> ⛔ 这是软自检（同源有盲区），但配合上面的原文锚点，能逼你把理解摊开；也给 comp-review 提供"核对任务理解 vs 题目原文"的靶子。**存疑处宁可标"此处理解存疑，需复核"，也不要假装读懂。**

### Step 1.5: 假设敏感性预检（⛔ 必做，防止全盘方向错误）

**核心原则：拿到题后先花时间做"假设预检"，不要急着建模。一个关键假设选错，后续所有结果都会偏离题目设计意图。**

**1. 识别模糊表述，列出多种解释：**

逐句读题目，找出所有可能有歧义的表述。对每个模糊点，列出至少两种合理解释：

```

模糊表述清单：

1. "[原文引用]" 

   - 解释A: ...

   - 解释B: ...

   - 初步倾向: A/B，理由: ...

2. "[原文引用]"

   - 解释A: ...

   - 解释B: ...

```

常见歧义类型：

- 数量歧义："各类设备完成工程量"→ 每类 1 台 vs 每类多台并行？

- 范围歧义："优化方案"→ 只优化顺序 vs 同时优化数量和顺序？

- 约束歧义："不超过预算"→ 总预算 vs 每期预算？

- 时间歧义："完成时间最短"→ 最后一个完成的时间 vs 所有任务总时间？

**2. 对关键歧义做快速验算（两种解释都算一遍问题一）：**

对影响最大的 1-2 个歧义点，用最简单的方法（手算/Excel/10 行 Python）把两种解释都在问题一上算一遍：

```

假设预检结果：

- 解释A: 问题一结果 = XXX

- 解释B: 问题一结果 = YYY

- 选择: B，理由: [结果更合理 / 更符合后续问题递进设计 / ...]

```

**3. 检查问题递进性（最关键的验证手段）：**

竞赛题的问题一般层层递进。在你选定的假设下，预判每个问题的结果应该如何变化：

```

问题递进性预判：

- 问题一（基础场景）→ 结果: 基准值

- 问题二（增加约束/扩大规模）→ 结果应该: 比问题一差/好，因为...

- 问题三（进一步变化）→ 结果应该: 比问题二有明显变化，因为...

- 问题四（花钱/加资源）→ 结果应该: 比问题三明显改善，因为...

```

**⛔ 递进性退化检测：** 如果在你的假设下，某个后续问题的结果和前一个问题几乎相同（新增的变量/资源对目标函数没有边际效益），说明你的假设大概率有问题。**立刻回头检查基础假设，不要继续往下做。**

**4. 在 PROBLEM_ANALYSIS.md 中显式记录假设预检结果：**

```markdown

## 假设敏感性预检

### 模糊表述及解释

[列出每个歧义点和选择的解释]

### 快速验算对比

[两种解释在问题一上的结果对比]

### 问题递进性预判

[每个问题的预期结果变化方向]

### 最终假设选择及理由

[选择了哪种解释，为什么]

```

### Step 2: 子问题拆解

每个子问题明确：

- 输入/输出

- 难度（简单/中等/困难）

- 建议方法

- 与其他子问题的关系（依赖/独立/递进）

**⛔⛔ 同时产出 `CAPABILITY_CHECKLIST.json`（题型无关的能力清单，验收契约本体）。** 这是解决"验收只认数模错法、对 NLP/金融科技等题语义失明"的地基——把每个子问题拆成**可判定的交付能力项**，每项标注"怎么判"。数模题会列"物理约束/双算法交叉/资源单调"，NLP 题会列"五元组抽取/NER/指代消解/测试集预测/无泄漏AUC"——**清单由题目动态生成，不再靠硬编码数模规则**。格式：

```json

{"problem_id": "<赛题号>", "n_subproblems": 4, "capabilities": [

  {"id":"P1-C1","subproblem":1,"name":"事件五元组抽取","judge":"machine",

   "criterion":"产物每条含(主体,事件类型,客体,时间,地点)五字段且非空",

   "required_output":"output/events.json","machine_check":"delivery","source_sentence":"S2"},

  {"id":"P1-C2","subproblem":1,"name":"指代消解","judge":"semantic",

   "criterion":"代词/简称正确回指到实体，非字符串匹配","source_sentence":"S5",

   "falsifiable_check":"抽取结果带 span 起止位置且抽取器非纯 str.find 词典；否则判不成立"}

]}

```

> - **`judge` 两类**：`machine`=可被确定性闸自动核（必写 `machine_check`：delivery/leakage/ingest/constraint/facts，其中 delivery 还要写 `required_output` 产物路径）；`semantic`=要懂语义才能判（留严格模式考官 AI）。

> - **`falsifiable_check`（可证伪断言，防降维冒充，方向无关）**：一句话写清"代码里**怎样算真做到**这条能力、**什么情况判不成立**"——comp-code 会据此在子问题代码末尾生成 `validate_capability()` 运行时硬断言，不过即 `raise` 中断，而不是记个注释继续出图。**semantic 项 + 非 delivery 的 machine 项必填**（这些靠判断/算法验、是降维高发区），delivery 项可不填。写法方向无关、按本题实质写：

>   - NLP 真伪判别：`去泄漏后独立测试 AUC 显著>0.5，且标签不来自 file_id/文件名前缀；否则判不成立`

>   - 优化题：`该硬约束进了求解器模型(非事后配平)，最优解满足全部约束；越界即判不成立`

>   - CV 分割：`输出为逐像素 mask 且留出集 IoU>阈值；只输出分类标签则判不成立`

>   - 关键是给出**可被代码检验的证伪条件**，不是泛泛"效果好"。

> - **`source_sentence`（承上，防漏）**：引用 Step 5.6「题目逐句拆解表」里对应的句号（S1/S2…）。Step 5.6 里凡标"决策/目标/机制"类的句子（=题目明确要出活），**必须**被至少一条能力项的 `source_sentence` 认领——`capability_check.py` 会核对，漏认领即 FAIL。这把"题面要求→能力清单"焊死，从源头堵"题目明确要求的能力没进清单"。

> - **每个子问题至少拆 1 条能力项**，漏拆的子问题下游无法验收、极易被做成"最小演示"蒙混。

> - ⛔ **能力项写"题目真正要求的能力"，不是"你打算做的事"**：题目要五元组抽取就写抽取（判定标准=五字段非空），别写成"分类"降维；要测试集预测就把预测产物列进去。清单写全了，后面才拦得住降维。

### Step 3: 数据探索

检查 `user_data/` 中是否有附件数据。

**⛔⛔ 第一件事：机器建档（防"数据没读全/凭记忆编行数"，红线四的权威基准）。** 看到数据先跑 `data_profile.py`，它会逐文件逐 sheet 探测行数/列名/缺失率/sha256，落盘成 `DATA_PROFILE.json`（机器写的权威台账，不靠你记）。**后续任何一步要核对"该有多少行、几张 sheet"，一律读这份档，禁止凭上下文印象报数字**：

```bash

python _utils/data_profile.py --datadir user_data --out DATA_PROFILE.json

cat DATA_PROFILE.json    # 看清每个文件的 total_rows / n_sheets / 各 sheet 行数

```

> ⚠ 谨防"一个 xlsx 里藏了带标签的多张表、却只读到首表"——`data_profile.py` 内部用 `sheet_name=None` 读全部，若这里显示某文件有多张 sheet，说明后续 comp-code **必须把这些 sheet 全用上或显式说明只用哪张**。把这份"文件→sheet→行数"清单原样抄进本报告的数据探索小节，作为下游 comp-code「数据摄入完整性闸」的行数断言基准。

**有数据**：分析数据规模、字段含义、数据质量、数据特征。

**无数据（纯建模题）**：标注"本题无附件数据"，在建模思路中说明需要自行构造参数/初始条件（如优化问题的约束参数、微分方程的初始值、蒙特卡洛的分布假设等）。`data_profile.py` 也会写一份 `{"n_files":0}` 的空档，让"无数据"这件事同样有据可查。

**⛔⛔ 同时产出「数据事实台账」`DATA_FACTS.json`（通用，与题型无关，下游逻辑体检的依据）：** 把附件数据的**硬事实**结构化摊出来，专治"把设定值当实测、把封顶值当真值、把没数据的量当识别结果"这一类**认知错误**（不是数值错，是理解错）。对每个关键变量填：

```json

{"variables":[

  {"name":"<列名/物理量>","role":"observed|setpoint|assumed","unit":"...",

   "range":[<min>,<max>],                         // 该变量在附件里的实测取值范围

   "granularity":"second|minute|hour|mean_only",  // 数据粒度(仅均值就写 mean_only)

   "censored":{"kind":"none|right|left|interval","at":<界值或null>},  // 有无传感器封顶/删失及界在哪

   "has_data":true|false}                          // false=题目要它但附件没给,只能靠假设

]}

```

> - **`role` 三分**：`observed`=真实测量值(下游必须当自变量用,漏了报警)；`setpoint`=设定值/控制参数(**不是实测结果**,禁止拿它当"识别出的真实值")；`assumed`=无数据、靠假设。

> - **`censored`**：若某列被传感器封顶(如上限截断)，必须标 `kind` 和界值——下游反解/取界时才知道"观测值是真值的上界还是下界"，防方向反。

> - **`has_data:false`** 的量：下游只能"情景模拟"，正文禁用确定性口吻当数据结论。

> - ⛔ 这份台账机器可核(下游 `logic_audit.py` 读它做外推报警/特征完整性)，**只填附件里查得到的客观事实，不填推测**。填不出的字段留 `null`，不要编。

**⛔ 数据探索的边界：** 本步骤只做描述性统计和初步特征识别（数据规模、缺失率、分布形态、相关性矩阵、异常值检测），不要做建模求解。以下行为属于越界：

- 拟合模型（线性回归、周期函数拟合、移动平均预测等）→ 留给 comp-modeling

- 写独立的 .py 文件保存到 code/ 目录 → 留给 comp-code

- 优化求解（遗传算法、线性规划等）→ 留给 comp-code

- 如果需要用 Python 做简单的描述性统计（如 `df.describe()`、`df.isnull().sum()`），可以用 Bash 内联一次性脚本，但不要创建独立文件

### Step 4: 变量定义与符号表

| 符号 | 含义 | 单位 | 类型 |

|------|------|------|------|

### Step 5: 建模思路规划

每个子问题 1-2 种候选方法，标注推荐方案。

常用模型类型：优化类、预测类、评价类、分类/聚类、图论/网络、随机/统计、微分方程。

### Step 5.5: 范例感知 + 图表预规划

在输出分析报告前，**先读取参考资料了解可用的图表类型**：

```bash

# 1. 读范例和套餐：了解各方法类型推荐的图表组合

cat _utils/figure_exemplars.md 2>/dev/null || cat skills/shared-scripts/figure_exemplars.md

# 2. 读选择指南：了解每种图表的适用场景、数据特征匹配、配色规则

cat _utils/figure_style_guide.md 2>/dev/null || cat skills/shared-scripts/figure_style_guide.md

# 3. 配方库（可选参考，60+ 张 SCI 级图表代码模板，paper-figure 会按本规划提取）

ls _utils/figure_recipes_*.md 2>/dev/null || ls skills/shared-scripts/figure_recipes_*.md

```

**5 个配方库供参考**（不强制按编号生成，根据数据形态自主选择）：

- `basic`：12 张基础图（柱状/散点/折线 + 渐变填充 / KDE 背景 / Rain Cloud / Lollipop）

- `advanced`：17 张高 SCI 影响因子图（SHAP / Kaplan-Meier / Forest plot / Sankey）

- `empirical`：16 张计量/统计图（DID / 工具变量 / 分位数回归）

- `competition`：23 张竞赛常用图（收敛曲线 / Pareto / 重心迁移 / Bubble+KDE）

- `academic`：12 张 AI/CS 图（ablation / t-SNE / training curves）

> **配方编号是建议起点**：在 FIGURE_MANIFEST 列每张图时，可以在图名后注明配方编号（如 `fig_q2_pareto  // competition#8`），paper-figure 步骤用 `python3 _utils/get_recipe.py competition 8` 提取代码模板作为起点，再适配实际数据。不写编号也行，paper-figure 会自己根据数据形态选。

**图表规划方法（按分析步骤推导，不要套模板）：**

先读 `figure_exemplars.md` 中的"按研究方法的图表套餐"：

- 匹配套餐（A-F）→ 以必选项为基础，根据具体选题增减

- 不匹配 → 用下面的"数据形态推导法"

再读 `figure_style_guide.md` 的 "By data shape" 决策表，对每个分析步骤做推导：

| 分析步骤输出 | 数据形态 | 推荐图表 |

|------------|---------|---------|

| 多变量时间趋势 | 时间×值 | 折线图 basic #3 |

| 变量相关系数矩阵 | N×N 矩阵 | 聚类热力图 advanced #14 |

| 多模型多指标数值 | 方法×指标矩阵 | 分组柱状图 basic #1 或 方法对比热力图 advanced #16 |

| 系数±标准误 | 系数+CI | 森林图 empirical #1 |

| 正负方向效应值 | 正负差值 | 发散柱状图 advanced #20 |

| 多组分布形态 | 多组连续值 | Ridgeline advanced #23 或 Grouped Violin advanced #24 |

| 地理空间数据 | 地理×值 | 地图热力图 competition #7 |

| 排名数据 | 名称×单一数值 | 棒棒糖图 advanced #1 |

| 模块增量贡献 | 步骤×增量 | Waterfall advanced #6 |

**⛔ 每张图必须写明配方编号和选择理由**，格式：

`fig_xxx — 发散柱状图 (advanced #20) — 效应分解有正有负，发散柱状图能直观展示方向 — 章节: 实证结果`

**⛔ 配方编号是必填项！** 格式为 `(类别 #编号)`，如 `(advanced #1)`、`(basic #3)`、`(empirical #1)`、`(competition #7)`。系统会根据配方编号自动注入对应的代码模板到 Claude 的 prompt 中。如果不写配方编号，Claude 将无法获得配方代码，只能从零写图表脚本，质量无法保证。如果图表类型不在配方库中，写 `(custom)` 标注。

配方库是"菜单"不是"菜谱"——知道有哪些图表可用，但根据你的数据和选题自主决定。如果你认为某种不在配方库里的图表更适合，也可以用。

**硬规则（只有这几条必须遵守）：**

- 同一种图表类型不超过 3 次（如已有 3 个柱状图，下一个对比换别的类型）

- 每张图必须指定具体类型（不能写"对比图"，要写"分组柱状图"或"发散柱状图"或"雷达图"）

- 至少 1 张 DrawIO 技术路线图（放问题重述章节末尾 `1_restatement.tex`）

- 如果涉及空间数据，必须有空间分布可视化（地图热力图/LISA图）

- 如果涉及模型对比（≥3个模型），至少用 2 种不同的对比图表类型

- 如果涉及前后/分组对比，考虑发散柱状图、Back-to-Back Bar、配对点图等方向性图表

- ⛔ **逐个子问题评估 TikZ 高级图**：对每一问，检查其核心方法是否命中 `figure_exemplars.md`「TikZ 不止架构图」触发表（线性规划→可行域图、微分方程→相平面图、物理力学→受力分析、几何→几何示意、光学→光路图、神经网络→架构图、PINN→PINNs 图等）。命中就为该问规划一张 `tikz_xxx`（如问题二用线性规划 → `tikz_feasible_q2`），写进 FIGURE_MANIFEST 的 TIKZ 类。这类图精确渲染公式+几何，是体现专业度的加分项；只在内容真正匹配时加，不要硬塞。

  - ⛔⛔ **TIKZ 类的严格边界（规划=产物的硬约束，务必遵守）**：**只有上面触发表里的「真几何结构图」才能进 TIKZ 类**——即需要按真实坐标画点/线/角度/向量场/区域的图（可行域、相平面、受力分解、几何示意、光路、网络拓扑架构、PINN 结构等）。**下列一律归 DATA 类（`fig_` 前缀），严禁列进 TIKZ 类**：函数曲线（含分段函数、风险函数 $w(t)$、损失曲线）、统计分布、时序趋势、对比柱状/折线、热力图、散点、ROC/KM 曲线等——这些是数据可视化，用 matplotlib 画更清晰。**判据**：这张图画的是「按坐标定义的几何结构」还是「一条/几条数据曲线」？后者一律 `fig_`。

  - ⛔ **一旦写进 TIKZ 类，就是对下游的硬合同**：`paper-figure` / `paper-figure-html` 步骤会按 manifest 的 TIKZ 清单逐个产出真 TikZ PDF（`tikz_<name>.pdf`），**不允许下游用数据图替代或跳过**。所以规划时不要把"其实是函数曲线"的图误标成 `tikz_`（否则要么逼下游用 TikZ 画本该 matplotlib 的曲线、要么造成"规划了 tikz 却没同名产物"的对账缺口）。**不确定时一律归 DATA 类**。

- ⛔ **感知/重构类任务必须规划定性"门面图"**：若赛题产出本身可视（图像增强/去雾/去噪/超分/分割/检测/重构/生成、信号/音频处理、三维重建等），对照 `figure_exemplars.md`「领域特定门面图」触发表，**每个相关子问题必须规划一张 `fig_<问>_visual_cmp` 真实样本前后/方法并排对比图（含关键区域局部放大），归入 FIGURE_MANIFEST 的 DATA 类，且优先级排在所有指标图之前**。所有客观指标（PSNR/NIQE/CII/边缘强度/mIoU 等）都是为佐证肉眼效果而生——只规划了指标图却漏掉真实图像对比图，是本末倒置的致命缺陷。用真实数据集样本，不要用 AI 生成的想象图。

- ⛔ **先按赛题领域想"标志图"，再去配方库找；允许自由设计 custom 图**：规划每张图前先问两件事——①这道题属于什么领域、评委最期待看到什么图（对照 `figure_exemplars.md`「按赛题领域的标志图」触发表：地理/选址→流向图+覆盖图、图论网络→拓扑图、动力学→仓室流图+相轨迹、物理场→云图/矢量场、博弈→收益矩阵/博弈树、信号→时频图、元胞/仿真→时空快照序列…）；②这一步算出了什么、什么视觉形式最能让人一眼信服。**配方库是灵感菜单不是限制清单**——库里没有但更贴合本题的图，大胆标 `(custom)` 自己用 matplotlib/TikZ 设计（地图叠加、嵌套放大 inset、时空序列、3D 渲染等都欢迎）。但守住底线：数据必须真实(严禁画图脚本硬编码编造数字)、图表类型匹配数据语义(排序用排序条形非发散柱、越小越好的指标进雷达前先反向归一化)、要素完整(轴标题/单位/图例/必要的误差棒)、最终清单零 TODO。

- ⛔ **组合图（Subfigure）按必要性自决**：每张图先自问"是单值/单维"还是"多值对比/多维并陈"：

  🟢 **适合组合**（panel ≤ 4，每 panel 宽度 ≥ `0.48\textwidth`）：

  - 残差诊断 4 联图（Q-Q / 残差-拟合 / 直方图 / 残差-时间）—— 单张孤立看意义不全

  - 方法/算法对比（A vs B 同坐标系）—— 优劣一目了然

  - 灵敏度 2-4 参数小图 —— 看哪个最敏感

  - 感知/重构类门面图（处理前 ‖ 处理后 + 局部放大）

  - 同一物理量多视角/多时间快照

  🔴 **不要组合**（拼图凑数）：

  - 两张内容无关的图硬塞一行

  - panel > 4 → 拆成两个 figure 反而清楚

  - 单 panel < `0.45\textwidth` → 太挤

  - 单图本身就复杂（满版热力图、地理图、3D、网络图）→ 独占一行才能看清细节

  **FIGURE_MANIFEST 显式标注**：`[2-panel]` / `[4-panel]` / `[single]`，默认 `[single]` 可省略。

  示例：`fig_q2_residual_diag [4-panel] — 残差诊断 — basic #5 — 章节: 问题二模型验证`

  详细判据 + 排版规范见 `_utils/writing_rules.md` 第 4 条。**AI 自己判断是否组合，不强求数量，但鼓励"信息密度高于占页数"的设计**。

**在 PROBLEM_ANALYSIS.md 中输出图表预规划清单：**

```markdown

## 图表预规划

### 数据图表清单

对每张图写明：文件名 — 具体图表类型 (配方编号) — 展示什么数据/传达什么信息 — 放在哪个章节

示例（根据实际选题自由发挥，每张图必须带配方编号）：

- fig_xxx — 棒棒糖图 (advanced #1) — 方法排名对比 — 章节: 模型对比

- fig_yyy — 森林图 (empirical #1) — 回归系数及置信区间 — 章节: 实证结果

- fig_zzz — 可行域图 (competition #28) — 约束条件与最优解 — 章节: 模型求解

- TABLE_xxx — [表格描述] — [章节位置]

### DrawIO 架构图清单

对每张 DrawIO 图写明：编号 — 图类型 — 展示什么内容 — 放在哪个章节。

**⛔ 语言规则：DrawIO 图中的所有文字（节点标签、箭头标注、分组框标题）必须与论文语言一致。**

- 中文赛题（国赛/数维杯中文/MathorCup/长三角/五一/华为杯等）→ 图中文字用中文

- 英文赛题（MCM/ICM/APMCM/数维杯英文/认证杯英文等）→ 图中文字用英文

必须规划（所有赛题）：

- DrawIO-1: 技术路线图 — 整体求解思路 → 问题重述章节末尾 (1_restatement.tex)

竞赛多问题赛题额外规划（每个子问题都需要求解流程图）：

- DrawIO-2: 问题一求解流程图 → fig_flow_q1.drawio → 问题一章节开头

- DrawIO-3: 问题二求解流程图 → fig_flow_q2.drawio → 问题二章节开头

- DrawIO-4: 问题三求解流程图 → fig_flow_q3.drawio → 问题三章节开头

- ...（有几个子问题就规划几张，一一对应）

按需规划（根据赛题特征判断，写明理由）：

- DrawIO-N: [模型架构图/变量关系图/算法流程图/Pipeline图/概念框架图] — [展示什么] → [章节位置] — 理由: [为什么需要这张图]

### 图表多样性检查

[列出每种图表类型的使用次数，确认无重复超过 3 次]

总计: ~X 数据图 + ~Y 表 + Z DrawIO + P TikZ + W GPT Image

```

#### GPT Image / DrawIO 图预规划

**GPT Image 只用于场景示意图**（物理/工程类赛题的问题背景图）。技术路线图、求解流程图、架构图等结构化图表使用 DrawIO。

**GPT Image 场景示意图（按需，仅物理/工程类赛题）：**

- 仅当赛题有具体的物理/工程空间场景时才规划（光学、无人机、传感器网络、交通流、热传导、管道网络等）

- 纯数据/统计类赛题（蔬菜定价、人口预测等）不需要

- 最多 1-2 张，放在问题重述章节（`1_restatement.tex`）的问题背景描述之后

**DrawIO / TikZ / GPT Image 图类型与适用场景（按赛题特征选择）：**

| 图类型 | 推荐工具 | 适用场景 | 放置位置 | 是否必须 |

|--------|---------|---------|---------|---------|

| 技术路线图 | DrawIO | 所有赛题 | 问题重述章节末尾（`1_restatement.tex`），国赛/竞赛没有单独问题分析章节时放问题重述 | ✅ 必须（1张） |

| 子问题求解流程图 | DrawIO | 竞赛多问题赛题，每个子问题一张 | 各子问题章节开头 | ✅ 每个子问题必须 |

| 数据处理 Pipeline | DrawIO | 涉及多阶段数据清洗/特征工程 | 数据预处理章节 | 按需 |

| 概念框架图（简单分层） | DrawIO | 涉及理论模型/研究框架构建（无复杂连线） | 引言或理论分析章节 | 按需 |

| 指标体系层次图 | DrawIO | 涉及 AHP/熵权法/TOPSIS/模糊综合评价等评价类问题 | 模型构建章节 | 评价类必须 |

| 模型选择决策树 | DrawIO | 涉及多种候选模型需要对比选择 | 模型构建章节 | 按需（≥3候选模型时推荐） |

| 甘特图/调度方案图 | DrawIO | 涉及排程/调度/资源分配/时间规划 | 求解结果章节 | 调度类必须 |

| 网络拓扑图（≤15节点） | DrawIO | 涉及图论/物流网络/社交网络 | 问题描述或求解结果章节 | 图论类必须 |

| 方法对比矩阵图 | DrawIO | 涉及多方法优缺点对比 | 模型构建章节 | 按需 |

| 模型架构图 | TikZ | 涉及神经网络/深度学习/集成模型 | 模型构建章节 | 按需 |

| 变量关系/因果路径图 | TikZ | 涉及因果推断/中介效应/SEM | 理论框架或模型设定章节 | 按需 |

| 算法流程图（带公式） | TikZ | 涉及自定义算法/迭代优化/启发式搜索 | 算法描述章节 | 按需 |

| 几何示意图（2D 平面） | TikZ | 涉及平面几何关系（三角形、圆、角度标注、坐标系） | 问题描述章节 | 按需 |

| 几何示意图（3D 空间） | GPT Image | 涉及 3D 空间几何（圆柱体、球面、反射/折射、空间坐标系） | 问题描述章节 | 按需 |

| 概念框架图（复杂连线） | TikZ | 有跨层箭头+标注系数的理论框架 | 理论框架章节 | 按需 |

| 网络拓扑/路径图（>15节点或需标注路径） | TikZ/matplotlib | 节点多或需要精确标注最优路径+权重 | 求解结果章节 | 按需 |

| 场景示意图 | GPT Image | 涉及物理/工程空间场景（无人机/传感器/交通等） | 问题重述章节 | 按需（仅物理/工程类） |

**速查：需要公式→TikZ，需要精确连线→TikZ，需要写实渲染→GPT Image，其余→DrawIO**

**⛔ TikZ vs GPT Image 判断（几何示意图必须过这条规则）：**

- 图中有圆柱体、球体、锥体、曲面等 3D 立体 → **GPT Image**（TikZ 画 3D 透视会变形、标注重叠）

- 图中有反射/折射光线在 3D 空间中传播 → **GPT Image**

- 图中只有 2D 平面元素（圆、三角形、直线、角度标注、坐标轴）→ **TikZ**

- 不确定时 → **GPT Image**（比 TikZ 画 3D 安全得多）

**⛔ 按赛题特征自动判断（规划时必须逐条过一遍，符合条件的必须规划）：**

一、所有赛题必须：

- 技术路线图（1张）— 展示整体求解思路

二、按赛题类型触发（逐条检查，符合就加）：

- 赛题有多个子问题 → 每个子问题都必须有一张求解流程图，放在对应章节开头。简单问题的流程图可以简化（3-4 个节点），但不能省略

- 赛题涉及评价/排名/打分（AHP/熵权法/TOPSIS/模糊综合评价/灰色关联） → 加指标体系层次图（目标层→准则层→指标层）

- 赛题涉及深度学习/集成学习/多模型融合 → 加模型架构图（TikZ）

- 赛题涉及因果推断/路径分析/中介效应/SEM → 加变量关系图（TikZ）

- 赛题涉及自定义迭代算法（遗传算法/模拟退火/强化学习/粒子群/蚁群） → 加算法流程图（TikZ，带公式）

- 赛题涉及复杂多阶段数据预处理（爬虫→清洗→特征工程→建模） → 加 Pipeline 图

- 赛题需要构建理论框架（经管/社科类，有假设推导） → 加概念框架图

- 赛题涉及图论/网络优化/物流配送/社交网络 → 加网络拓扑图或路径图

- 赛题涉及排程/调度/资源分配/生产计划 → 加甘特图

- 赛题涉及物理/工程空间场景（光学/无人机/传感器/交通/热传导） → 加场景示意图（GPT Image）或几何示意图（TikZ）

- 赛题有 ≥3 种候选模型需要对比选择 → 加模型选择决策树（展示选模型的逻辑）

- 赛题涉及空间数据/地理分布 → 加空间分布示意图（可用 matplotlib 地图热力图代替）

**⛔ 每张 DrawIO 图必须在清单中写明文件名**，格式为 `fig_xxx.drawio`，`流程与架构图绘制` 步骤会按此清单逐条生成并校验。

**在 PROBLEM_ANALYSIS.md 中输出：**

```

### GPT Image / DrawIO / TikZ 图清单

**语言: [中文/English]**（与论文语言一致，图中所有文字使用此语言）

DrawIO 图（技术路线图/流程图/Pipeline/指标体系/决策树/甘特图/网络图）：

- DrawIO-1: 技术路线图 → fig_roadmap.drawio → 问题重述章节末尾 (1_restatement.tex) [必须]

- DrawIO-2: 问题一求解流程图 → fig_flow_q1.drawio → 问题一章节开头 [按需]

- DrawIO-3: 指标体系层次图 → fig_index_hierarchy.drawio → 模型构建章节 [评价类必须]

- DrawIO-4: 数据处理Pipeline → fig_pipeline.drawio → 数据预处理章节 [按需]

- DrawIO-5: 模型选择决策树 → fig_model_decision.drawio → 模型构建章节 [按需]

- DrawIO-6: 甘特图/调度方案 → fig_gantt.drawio → 求解结果章节 [调度类必须]

- DrawIO-7: 网络拓扑/路径图 → fig_network.drawio → 问题描述或结果章节 [图论类必须]

- DrawIO-8: 概念框架图 → fig_framework.drawio → 理论分析章节 [按需]

TikZ 图（模型架构图/变量关系图/算法流程图/几何示意图，需要精确连线或公式）：

- TikZ-1: [图类型] → tikz_diagrams.tex → [章节位置] [按需]

GPT Image 场景示意图（仅物理/工程类赛题）：

- GPTIMG-1: {场景名}示意图 → fig_scene.png → 问题重述章节 (1_restatement.tex) [按需]

总计: N 张 DrawIO + P 张 TikZ + M 张 GPT Image

```

### ⛔⛔⛔ FIGURE_MANIFEST（机器可读对账清单，必须输出）

**写完上面三类图清单（数据图 + DrawIO + TikZ + GPT Image）后，在 PROBLEM_ANALYSIS.md **最后**追加一个机器可读的清单区块，下游 paper-figure / paper-figure-drawio 会按此清单逐条对账。少一张就报错。**

**格式严格按此输出（不要漏 `<!-- BEGIN/END FIGURE_MANIFEST -->` 锚点）：**

```markdown

<!-- BEGIN FIGURE_MANIFEST -->

## 图表清单（FIGURE_MANIFEST）

**数据图（matplotlib gen_fig_*.py，paper-figure 产出 .png/.pdf）：**

- fig_xxx

- fig_yyy

- fig_zzz

**DrawIO 流程/架构图（paper-figure-drawio 产出 .drawio + .png/.pdf）：**

- fig_roadmap

- fig_flow_q1

- fig_flow_q2

**TikZ 图（paper-figure 产出 tikz_*.pdf）：**

- tikz_model_arch

**GPT Image 场景图（paper-illustration 产出 .png）：**

- fig_scene

**总数：DATA=3, DRAWIO=3, TIKZ=1, GPTIMG=1, ALL=8**

<!-- END FIGURE_MANIFEST -->

```

⛔ **铁律：**

- **每条只写文件名主干**（不带 `.py` / `.drawio` / `.png` / `.pdf` 后缀），让下游能用同一个名字校验多种产物

- **⛔⛔ 图名必须以 `fig_` 或 `tikz_` 前缀开头**（问题「规划了图却没生成」的根因）：数据图/流程图/架构图/场景图一律 `fig_xxx`，TikZ 几何图一律 `tikz_xxx`。**严禁用 `image2`、`图2`、`chart1`、`示意图` 这类没有前缀的名字**——下游对账脚本（paper-figure / paper-figure-drawio / workflow_engine.py）按 `fig_`/`tikz_` 前缀在 manifest 章节里抓图名，不带前缀的会被**直接漏掉、既不计数也不报警**，导致该图静默不生成（用户就会看到"赛题分析规划了 image2 但没画出来"）。图名用小写英文+下划线，见名知意（如 `fig_q1_turbidity_trend`、`fig_flow_q2`）。

- **数量必须跟上面三类图清单完全一致**（一一对应）

- 写完后跑这个自检确认格式 OK：

```bash

START=$(grep -n '<!-- BEGIN FIGURE_MANIFEST -->' PROBLEM_ANALYSIS.md | head -1 | cut -d: -f1)

END=$(grep -n '<!-- END FIGURE_MANIFEST -->' PROBLEM_ANALYSIS.md | head -1 | cut -d: -f1)

if [ -z "$START" ] || [ -z "$END" ]; then

  echo "❌ FIGURE_MANIFEST 区块缺失, 必须补"

else

  MANIFEST=$(sed -n "${START},${END}p" PROBLEM_ANALYSIS.md)

  # (原 ALL_FIGS 变量已移除：改用与完成铁律块一致的 DATA= 标记法后不再需要 fig_ 总数做减法)

  N_DRAWIO=$(echo "$MANIFEST" | grep -cE '^[[:space:]]*-[[:space:]]+fig_(roadmap|flow_|pipeline|index_|gantt|network|framework|model_decision)')

  N_GPTIMG=$(echo "$MANIFEST" | grep -cE '^[[:space:]]*-[[:space:]]+fig_scene')

  N_TIKZ=$(echo "$MANIFEST" | grep -cE '^[[:space:]]*-[[:space:]]+tikz_')

  # ⛔ 数据图计数口径必须与「完成铁律」块(本文件开头 PASS 块)完全一致：优先取 DATA=N 标记，

  #    取不到再数 "**数据图**" 章节内的 - fig_ 行。之前这里用 ALL_FIGS-N_DRAWIO-N_GPTIMG 的减法

  #    白名单口径，DrawIO 图若命名不在白名单(如 fig_solve_q1)会被误算进数据图 → 与完成铁律块

  #    给出不同张数 → AI 反复回查。统一到标记法后两处口径一致，消除矛盾。

  N_DATA=$(echo "$MANIFEST" | grep -oE 'DATA=[0-9]+' | head -1 | grep -oE '[0-9]+')

  if [ -z "$N_DATA" ]; then

    N_DATA=$(echo "$MANIFEST" | awk '/^\*\*数据图/{f=1;next} /^\*\*/{f=0} f&&/^[[:space:]]*-[[:space:]]+fig_/{c++} END{print c+0}')

  fi

  N_DATA=${N_DATA:-0}

  TOTAL_LINE=$(echo "$MANIFEST" | grep -E '总数:|ALL=')

  echo "✅ FIGURE_MANIFEST: data=$N_DATA, drawio=$N_DRAWIO, tikz=$N_TIKZ, gptimg=$N_GPTIMG（data 口径同完成铁律块）"

  echo "  $TOTAL_LINE"

  # ⛔ 前缀合规校验：抓 BEGIN..END 之间的列表项，凡不以 fig_/tikz_ 开头的报警

  #   （image2、图2、chart1 这类没前缀的会被下游对账静默漏掉、导致图不生成）

  BAD=$(echo "$MANIFEST" | grep -E '^[[:space:]]*-[[:space:]]+' | grep -vE '^[[:space:]]*-[[:space:]]+(fig_|tikz_)' | sed -E 's/^[[:space:]]*-[[:space:]]*//')

  if [ -n "$BAD" ]; then

    echo "❌ 以下图名缺少 fig_/tikz_ 前缀，会被下游对账漏掉、导致图静默不生成，必须改名（如 image2 → fig_q1_xxx）："

    echo "$BAD" | sed 's/^/    · /'

  else

    echo "✅ 所有图名前缀合规（fig_/tikz_）"

  fi

fi

```

### Step 5.6: ⛔ 赛题分析自检协议（逐句扫描，通用防遗漏）

**核心问题：赛题分析遗漏一个关键句子，后续建模/编码/论文全部基于错误前提，不可逆地传播到最终结果。**

**以下是完全通用的自检流程，不依赖任何具体赛题。必须逐句执行。**

#### 第一步：逐句拆解题目

把赛题原文按句号/分号/冒号切成独立的句子单元，每一句都打上标签：

```markdown

## 题目逐句拆解表

| 句号 | 原文句子 | 句子类型 | 提取的要素 |

|------|---------|----------|-----------|

| S1 | "..." | 背景/约束/决策/数据/目标 | 名词+动词+数值 |

| S2 | "..." | 背景/约束/决策/数据/目标 | 名词+动词+数值 |

```

**句子类型分类（6种，必须每句标一类）：**

- **背景**：介绍问题场景，无需建模

- **约束**：限定条件（不超过/至少/必须），必须在模型中有对应不等式/等式

- **决策**：题目问"怎么选/如何规划/求最优"，必须识别为决策变量

- **数据**：提供具体数值/公式/分布，必须代入模型

- **目标**：题目最终要求的量（最大化/最小化/求解），必须是目标函数或输出

- **机制**：描述系统的动态行为/可选操作（"可以充电"、"可以重新分配"、"故障时"），**最容易被遗漏，必须特别标注**

#### 第二步：对每个句子做五问

对每个句子，必须回答以下五个问题（不能跳过）：

```markdown

## 句子级五问审查

### S1: "[原文]"

1. **这句话提到了什么实体？** （列出所有名词）

2. **这些实体是否都出现在我的变量定义表中？** （必须对照 Step 4 的符号表逐一核对）

3. **这句话描述的机制/行为是否在我的模型中有对应表达？** （动词→数学表达）

4. **如果这句话有数值，是否代入了模型？** 如果没数值，是否需要假设？假设值是多少？

5. **这句话如果被完全忽略，会导致什么后果？** （严重性评估：致命/严重/轻微）

```

**⛔ 特别提示：**

- **出现一次的关键词**最容易被遗漏（如"补给点"、"中转"、"休息"、"故障"只出现一句但改变建模本质）

- **模糊量词**必须量化（如"较长时间"、"足够远"、"适当"必须给出具体阈值假设）

- **隐含的"可选"操作**必须建模为决策变量（如"可以充电"不是"必须充电"）

#### 第三步：反向推理检查（从模型找回题目）

列出我当前的模型包含了什么，然后反向对照题目：

```markdown

## 反向对照表

| 我的模型中的组件 | 对应题目哪一句/哪几句 | 如果题目没说我为什么要加？ |

|-----------------|---------------------|---------------------------|

## 题目中未覆盖的组件

| 题目句子 | 我的模型是否覆盖？ | 不覆盖的后果 |

|---------|-------------------|-------------|

```

**⛔ 规则：**

- 题目的每个句子（除纯背景外）必须至少映射到模型的一个组件

- 模型的每个组件必须能追溯到题目的某一句话

- 如果模型有题目没说的组件 → 说明有凭空引入的假设，必须显式声明

- 如果题目有模型没覆盖的句子 → 说明有遗漏，必须补充

**⛔⛔ 逐句拆解表与能力清单焊死（承上启下的地基）：** 本表里凡标 **决策 / 目标 / 机制** 类的句子（= 题目明确要出活），**必须**被 `CAPABILITY_CHECKLIST.json` 里至少一条能力项的 `source_sentence` 认领。`capability_check.py` 会自动核对：有"决策/目标/机制"句没被任何能力项认领 → HARD FAIL。这样"题面逐句要求 → 能力清单 → 下游建模/编码/论文"形成一条不断链的合同——**从源头堵住"题目白纸黑字要求的能力，被赛题分析漏读、后面全歪"**（那个任务降维案例的真正病根）。填逐句表时给每句稳定编号（S1/S2…），能力清单再按号认领。

#### 第四步：经典问题升级检查

判断我的"经典问题映射"是否因为某些关键句子需要升级：

```markdown

## 经典问题升级判定表

| 初步映射 | 题目关键句子触发的升级 | 最终模型 | 严重性 | 必须性 | 缺失影响 |

|---------|---------------------|---------|--------|--------|---------|

| 示例：TSP | "可在中转点补给" → Multi-Trip | Multi-Trip VRP | 🔴 致命 | 必须 | 覆盖数严重低估 |

| 示例：线性规划 | "不同时段不同需求" → 多阶段 | 多阶段 LP | 🟡 重要 | 必须 | 无法反映时变需求 |

| 示例：最短路 | "有概率失败" → 随机 | 随机最短路 | 🟡 重要 | 建议 | 鲁棒性评估缺失 |

```

**⛔ 严重性标记规则：**

- 🔴 **致命**：如果不升级，结果会偏离题目本意 50% 以上（如单次 vs Multi-Trip 可能差一个数量级）

- 🟡 **重要**：如果不升级，会丢失关键评价指标（如灵敏度/鲁棒性分析无法做）

- 🟢 **优化**：建议升级但不升级也能回答题目

**⛔ 必须性标记规则：**

- **必须**：题目原文明确要求的机制（白纸黑字），不升级=未读懂题目

- **建议**：题目隐含或延伸的建模空间，升级能提升但不升级也可

- **可选**：锦上添花的扩展，与题目核心无关

**⛔ 针对每条升级建议，在建模阶段的预期处理方式：**

- 🔴 致命 + 必须 → 建模阶段**无条件采用**

- 🟡 重要 + 必须 → 建模阶段**应当采用**（除非技术不可行）

- 🟢 优化 + 建议 → 建模阶段可根据资源决定

**⛔ 对每个升级建议必须附加"缺参数处理预案"：**

如果某个升级涉及的参数在题目中没给出（如"可充电"但没给充电时间），必须在此处写明建议的假设值：

```markdown

升级：Multi-Trip OP

缺失参数：充电时间、补给点坐标

建议假设：充电时间=10min（参考工业无人机常识），补给点=区域4角

建模阶段操作：用假设值完整建模升级版，灵敏度分析扰动假设参数

⛔ 禁止：以"题目未给参数"为由跳过升级

```

**⛔ 触发升级的通用信号（在题目中出现则必须升级）：**

| 题目里出现这种说法 | 必须升级为 |

|------------------|-----------|

| 可充电/补给/中转/休息 | 多架次/Multi-Trip 变体 |

| 时间窗/营业时间/可用时段 | 带时间窗的变体（TW） |

| 优先级/价值不同/收益不同 | Orienteering/Prize-Collecting 变体 |

| 不确定/随机/概率 | 随机规划/鲁棒优化 |

| 动态变化/时变/实时 | 动态规划/MDP/在线算法 |

| 多方博弈/对抗 | 博弈论/Stackelberg |

| 信息不完全/未知 | 部分观测 MDP/贝叶斯 |

| 多目标/权衡 | 多目标优化/帕累托 |

| 阶段/分步 | 分层/序贯决策 |

| 故障/失效/损坏 | 可靠性/冗余设计 |

**⛔ 三步检查必须全部通过才能进入 Step 6。任何一步有遗漏，必须回到 Step 1 重读题目并更新分析。**

### Step 6: 输出

**输出前自检**：

- [ ] 每个子问题是否都有明确的建模方法建议（不是"待定"）？

- [ ] 变量定义表是否覆盖了赛题中出现的所有关键量（≥15 个变量）？

- [ ] 数据探索是否发现了有价值的模式（不是只列基本统计量）？

- [ ] 子问题间的依赖关系是否标注清楚（哪个先做、哪个依赖哪个的结果）？

- [ ] 每个子问题是否预标注了需要的图表类型和数量？

- [ ] 工作计划是否包含时间分配？

- [ ] ⛔ 非数据图规划是否完整？逐条过了 13 条触发规则？至少有技术路线图 1 张？

- [ ] ⛔ 图表总数是否合理？参考值：竞赛论文 **12-20 张数据图（DATA 类）** + 2-5 张非数据图（DRAWIO/TIKZ 流程示意）+ 3-8 张表。丰满模式 / 华为杯 DATA 类 30+ 张。**12-20 是参考不是硬规定**，按赛题复杂度自由调整；但 < 3 张数据图会硬阻塞（工作不完整）

保存到 `PROBLEM_ANALYSIS.md`：赛题概述、子问题拆解、数据探索摘要、变量定义、建模思路（含图表预规划）、工作计划。

**⛔ 分段写入规则（防止输出截断导致空工具调用）：**

PROBLEM_ANALYSIS.md 通常很长（3000-8000 字），必须分段写入，每段 < 150 行：

```bash

# 第 1 段：赛题概述 + 子问题拆解

cat << 'EOF' > PROBLEM_ANALYSIS.md

# 赛题分析报告

## 一、赛题概述

...

## 二、子问题拆解

...

EOF

# 第 2 段：数据探索 + 变量定义

cat << 'EOF' >> PROBLEM_ANALYSIS.md

## 三、数据探索

...

## 四、变量定义与符号表

...

EOF

# 第 3 段：建模思路 + 图表预规划

cat << 'EOF' >> PROBLEM_ANALYSIS.md

## 五、建模思路

...

## 五点五、硬约束清单（必须可机器审计 — comp-code 阶段会按此清单复核）

⛔ **本节解决一类典型 bug：**「优化器写了约束但最终输出 JSON 时没复验」导致越界方案被当成最优解通过。

详见 `_utils/error_prevention.md` 第九章「约束闭环校验」。

在 PROBLEM_ANALYSIS.md 中必须把题设的每一条硬约束写成**可机器审计**格式：

```markdown

## 硬约束清单（HARD_CONSTRAINTS）

| 约束编号 | 自然语言描述 | 数学表达（一行可执行） | 涉及变量 | 类型 |

|---------|------------|---------------------|---------|------|

| C1 | 决策变量边界 | `lo ≤ x ≤ hi` | x | 静态边界 |

| C2 | 实体间距上下界 | `lo ≤ ‖a-b‖ ≤ hi` | a, b | 静态 / 动态（看是否随时间变） |

| C3 | 列表内两两最小间距 | `min‖i-j‖ ≥ d  (i≠j)` | items[] | 静态对所有时刻 |

| C4 | 派生属性归属正确 | `attr.platform ∈ 合法载体集合` | attrs[] | **机动**（随载体变化） |

| C5 | 守恒律 / 容量上界 | `Σ flow_in - Σ flow_out = 0` 或 `Σ ≤ cap` | flows[] | 静态 / 时变 |

| C6 | 时间窗 / 单调性 | `start ≤ end`, `f(t) monotone` | events[] | 时变 |

```

⛔ **三个铁律**：

1. **每条约束都要写数学表达式**（一行 Python lambda 或显式公式），不能只写自然语言

2. **类型列必须明确**：静态 / 动态 / 机动派生 / 时变；凡是**依赖载体或上游变量动态变化的派生属性**（作用范围 / 时变参数 / 状态依赖容量 / 时变转化率等），**禁止**简化成"以静态点为圆心的固定区域 / 固定常量"——必须按"载体当前状态 + 平台/系统参数"动态计算

3. **comp-code 阶段会按此清单写 `constraint_audit.py`**，从最终 results.json 重新计算每条约束。不要在 comp-modeling/comp-code 阶段才补这个清单 —— 题面理解阶段就要列全。

> **海战部署题填法示例**（仅作通用模板的填表参考，不代表本题）：

>

> | C1 | 战场边界 X/Y ∈ [0, 50km] | `0 ≤ x ≤ 50000` | 所有 unit | 静态 |

> | C2 | 红艇距运输船 1-5km | `1000 ≤ ‖boat-transport‖ ≤ 5000` | red_boats[], transport | 动态 |

> | C3 | 艇间距 ≥ 1km | `min ‖i-j‖ ≥ 1000` | red_boats[] | 静态 |

> | C4 | 小功率激光归属红艇 | `weapon.platform=='red_boat' AND range=f(boat_pos, ±2km)` | weapons[] | **机动** |

>

> **其他领域举例**：交通调度填 C5（车容量/总里程上界）+ C6（时间窗）；SEIR 流行病填 C4（时变接触率归属于干预策略）；机器人路径填 C1（地图边界）+ C2（避障距离）；电网填 C5（潮流守恒）+ C6（爬坡速率单调）。

> **罕见情形**：若题目确实不含任何硬约束（如纯回归 / 纯统计推断 / 纯描述性建模），在表格下方注明 `（无硬约束 — 题面未给定边界/范围/不等式条件）`，comp-code 阶段会跳过 `constraint_audit.py` 而只跑结果合理性自检。

---

## 五点六、PROBLEM_FACTS.json（题面参数权威源 — 参数密集型题目必做）

⛔ **本节解决一类典型 bug：**题面给了 50-100 个参数（武器性能 / 距离 / 时间 / 概率 / 编队规则），AI 在长上下文工作流里抄进模型时**虚构 / 抄错 / 张冠李戴**，下游再严密的求解 / 审计 / 写稿都建立在错误前提上。

详见 `_utils/error_prevention.md` 第十四章「题面参数保真度」。

**触发条件**：当题面参数 ≥ 20 个（含距离 / 时间 / 概率 / 容量 / 规则等所有可量化条目），**必须**在 PROBLEM_ANALYSIS.md 同目录下产出 `PROBLEM_FACTS.json`，作为下游 comp-code / paper-analysis / 写稿阶段的唯一数字权威源。

**强制要求**：

1. **逐项手抄题面参数到结构化 JSON**（不能"简化记忆"，必须按原文一字一字抄；派生值另起 derived 字段并写换算因子）

2. **每条事实必须带 `source` 字段**：标"来自题面哪一页 / 哪一表 / 哪一行"，例如 `"source": "P4, 表1, 行1-2"`

3. **隐式约束必须列入 `rules` 段**：题面自然语言一句话级别的规则（如"作战全程阵型不变"、"激光只能与激光协同"、"飞行高度上限 100m"）必须显式登记，并给出 `machine_check`（伪代码或 Python 表达式）

4. **武器属性按表分组登记 + targets 数组**：同一武器对不同目标有不同概率时，必须分别登记，避免串台

5. **文件头 `_meta.source_files`**：comp-prob-analysis 阶段必须扫描 `user_data/*_extracted.txt`（workflow_engine 入口 Vision OCR 自动产出），把这些路径与 sha256 写入 `_meta.source_files`。comp-code 阶段 `facts_audit_v2.py` 会重新计算 sha256 验证文件未被篡改，并自动从 OCR 抽数字集合与 facts 数字集合比对。**全程机器化，不依赖人工**。

⛔ **禁止编辑 `user_data/*_extracted.txt`**：这些文件是 workflow_engine 入口在 AI 介入前自动产出的 OCR 原文，是 facts_audit_v2 客观比对的"权威证据"。任何对这些文件的修改都会让 sha256 校验失败，下游所有审计阶段会拒绝。如果发现 OCR 内容有问题（公式乱码、表格识别不全等），可以在 PROBLEM_FACTS.json 的 `_meta.verification_notes` 记录"OCR 在第 X 页有遗漏，对照原 PDF 补充了 Y"，但**不要直接改 _extracted.txt 文件本身**。

**JSON 标准结构（详见第十四章 14.3）**：

```json

{

  "_meta": {"problem_id": "Ddd", "source_pages": [1,2,3,4,5,6,7], "source_files": [{"path": "user_data/Ddd_extracted.txt", "sha256": "<workflow_engine OCR 产出文件 SHA256>"}]},

  "domain": {"spatial": {...}, "temporal": {...}},

  "entities": [{...}],

  "weapons": [{"id": "big_laser", "side": "red", "targets": [{"target_type": "blue_missile", "p_detect": 0.95, ...}]}],

  "rules": [{"id": "R1", "natural_language": "...", "source": "P?", "machine_check": "..."}],

  "derived_formulas": [{"name": "激光恢复可照射时长", "formula": "..."}],

  "unit_conversions": [{"raw": "18kn", "si_value": 9.26, "si_unit": "m/s"}]

}

```

**罕见情形兜底**：参数 < 10 个的简单题（如纯回归 / 纯描述统计），可以跳过 PROBLEM_FACTS.json，但仍建议在 PROBLEM_ANALYSIS.md 里有"参数登记表"小节。

### 防自抄自审循环：双源对比要求

⛔ **PROBLEM_FACTS.json 是 AI 抄出来的，再用它审计 AI 写的代码，存在"自抄自审"循环风险**——如果题面就抄错了，audit 反而"确认"错误。强制防护：

1. **每条事实附 `raw_quote`**：标"原文一字不差的引用"，例如

   ```json

   {"id": "big_laser", "p_damage_vs_missile": 0.95,

    "raw_quote": "毁伤概率 0.95 / 大功率激光武器 / 巡飞弹"}

   ```

2. **额外产出 `PARAMS_RAW.md`**：用自然语言描述题面所有数值参数（≥ 20 个），与 PROBLEM_FACTS.json 同步登记。例如：

   ```markdown

   ## 红方武器参数原文摘录

   - 大功率激光武器：打击距离 ≤ 5km，总照射时长 100s，对巡飞弹发现/命中/毁伤概率 0.95/0.95/0.95

   - 小功率激光武器：搭载红方无人艇，打击距离 ≤ 2km，总照射时长 120s

   - 反舰巡飞弹（红方）：≤10min 巡航，≤40m/s 航速，对蓝方无人艇 0.60/0.80/0.45

   ```

3. **comp-code 阶段跑 `audit_dual_source`**：从 PARAMS_RAW.md 抽数字集合 vs 从 PROBLEM_FACTS.json 抽数字集合，两边差集即"疑似添油加醋"或"疑似漏抄"。详见第十四章 14.6。

---

## 六、图表预规划

...

EOF

# 第 4 段：工作计划 + 合理性审查

cat << 'EOF' >> PROBLEM_ANALYSIS.md

## 七、工作计划

...

EOF

```

**⛔ 禁止一次性用 Write 工具写完整个文件。** 如果内容超过 150 行，必须用多次 `cat << 'EOF' >> file` 追加。一次性写太长会导致输出 token 截断，触发空工具调用循环。


## STEP_MANIFEST 产出声明

本步骤完成后，必须调用 `engine.step_manifest.write_manifest`（或经 bridge/common 等价入口）在工作区根目录写入 `STEP_MANIFEST.json`，至少包含：stepName / backend（含版本）/ config / inputFiles / outputFiles（含 SHA-256）/ commands / dependencies。质量门禁 `step_manifest` 将校验其存在性与完整性；缺失或无效将导致本步骤无法通过（fail）。

建议额外记录：题面文件 SHA-256、分析工具版本。

## 关键规则

- 不要跳过数据探索

- 子问题间的逻辑关系很重要

- 建模思路要具体（不要只写"用机器学习"）

- 时间紧迫，分析要高效

- ⛔⛔ **Markdown LaTeX 公式必须包在 `$` / `$$` 内，否则会原样显示 LaTeX 代码**：

  - 行内 `$...$`，块级 `$$...$$` 单独成行且前后空行

  - 多行环境（`\begin{aligned}` / `\begin{cases}` / `\begin{bmatrix}`）必须用块级 `$$...$$`

  - 避免 `\text{}` 包裹中文（KaTeX 对中文支持有限）

  - ❌ 反例（缺 `$$` 包围 → 渲染器当纯文本）：`v_k = b\sqrt{1+\theta_k^2}|\dot\theta_k|. \tag{12}`

  - ✅ 正例：用 `$$` 块单独成行包住整行公式（含 `\tag{N}` 编号）

  - 凡是写出 `\tag{` / `\sqrt` / `\hat` / `\frac` / `\dot` 等反斜杠命令的行，**必须**先确认已经在 `$...$` 或 `$$...$$` 包围之内

- ⛔ 主输出文件：`PROBLEM_ANALYSIS.md`。不要在根目录写额外报告

- ⛔ **不要创建独立的 .py 文件。** 本步骤只输出 PROBLEM_ANALYSIS.md。数据探索用 Bash 内联 Python 一次性脚本即可，不要保存为 code/*.py。建模求解和编程实现是后续步骤的职责

- ⛔ **分段写入：每次 Bash heredoc < 150 行。** 不要一次性写完整个报告，分 3-4 段追加写入（`>>` 而非 `>`）

