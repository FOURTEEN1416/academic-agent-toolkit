---

name: comp-code

description: "数学建模竞赛编程实现。根据建模报告编写代码、执行计算、收集结果。Use when user says \"编程\", \"写代码\", \"code implementation\"."

argument-hint: [modeling-report-or-topic]

allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Agent

---

# 竞赛编程实现

根据建模报告编写代码并执行计算：**$ARGUMENTS**

## ⛔⛔⛔ 任务规模警示（先读这段, 再读后面所有内容）

**这不是简单任务。** 数学建模竞赛的 comp-code 步骤要把建模报告里**每个**子问题落地成可跑的代码 + 真实结果。

子问题数量由 MODELING_REPORT.md 决定（一问也可能, 多问也可能）, 不是固定的。

⛔ **判断你是否真的做完了**, 在 `end_turn` 之前自问：

1. MODELING_REPORT.md 里有几问？你是不是真的为每问都写了独立的 .py？

2. `figures/` 下是不是每问都有对应的 `problem_*_results.json` 且文件非空？

3. RESULTS.md 是不是已经存在, 包含每问的方法和数值结果？

4. 跑过完成铁律最后那段 bash 验证脚本了吗？

**任何一项答 "否" → 不要 `end_turn`, 继续干活。** 引擎会反复检测这些产物, 没产出会自动重新拉你回来重做, 与其被动重做不如一次做完。

⛔ **不要用 "我已经做了主要工作, 剩下的晚点再说" 的心态退出**。

"晚点" 在 LLM 单轮预算里不存在 — 一旦 `end_turn`, 你就被切断了, 下一次进来要重新读上下文 + 重新理解任务, 比当前继续干活贵得多。

### ⛔⛔⛔ 长求解必须【前台同步等】—— 禁止"后台跑 + 等唤醒"的反模式（会烧光额度）

**你现在是非交互模式（`claude -p`），没有"下一轮"。一旦你 `end_turn`，整个进程立即被切断——你用 `run_in_background` 起的后台任务、你挂的 Monitor 监视，全部随之作废，那条"稍后会有通知把我唤醒"的假设【永远不成立】。** 之前真实翻车过：把求解丢后台 → 挂 Monitor → 说"我等通知"就 `end_turn` → 后台求解跟着被杀、RESULTS.md 从没产出 → 引擎判产出不完整 → 自动重试 → 下一次又重复同样的错 → 白白烧掉多轮额度。

- **❌ 禁止**：`求解脚本 &`（后台）/ `run_in_background` 跑长求解 + Monitor 监视 + `end_turn` 等唤醒。**只要你打算 `end_turn`，后台任务就等于没跑。**

- **✅ 必须**：长求解【前台同步等它真正返回】——`timeout 3600 "$PYTHON" problemN.py ...`（超时值按下文"求解器超时设置"，最长 1 小时），**站在原地等到它打印出结果、写出 json 文件为止**，再继续下一步。求解慢没关系，前台等就是了；额度花在"真的在算"上不亏，花在"反复重试白跑"上才亏。

- **✅ 崩溃/跑不出来 → 在【本轮内】当场诊断解决**，不要 `end_turn` 甩给自动重试：

  - 前台同步跑，崩溃会**立即在输出里暴露**（报错/段错误/超时），你能马上定位；后台跑只会把崩溃藏在 Monitor 后面、耗光整轮却什么也没产出。

  - 处理手段：降规模（如聚合对称的相同地块/大棚、减情景数）、换求解策略（限节点数、放宽 gap、加 `maxSolutions` 早停并**接受竞赛级 gap** 的可行解）、或分块求解。**先拿到一个能写进 json 的可行解，再谈优化**——有结果的粗解，远胜于"追求最优却反复崩、最终零产出"。

  - ⛔ 同一求解**最多在本轮内试 3 种策略**；3 种都拿不到可行解，就在 RESULTS.md 如实记"该子问题求解受限，已用 X 策略取得 gap≈Y% 的可行解 / 或降规模近似解"，**带着已有的最好结果继续下一问**，绝不 `end_turn` 空手退出。

## ⚡ 快速模式检测（第一步先跑，决定后面审查强度）

```bash

FAST_MODE=0

grep -q 'MH_FAST_MODE=1' CLAUDE.md 2>/dev/null && FAST_MODE=1

echo "FAST_MODE=$FAST_MODE"

```

**若 `FAST_MODE=1`（用户选了快速模式，速度优先）：**

- ✅ **仍必须做到**：每个子问题都写独立 .py、跑出真实结果、产出 `problem_*_results.json` + `RESULTS.md` + `code/main.py`、子问题全覆盖、结果不编造、通过下方"完成铁律"的产出验证。**这些是出稿底线，一个都不能省。**

- ❌ **跳过以下"追求完美"的耗时环节**（本 SKILL 后文出现时一律略过，不进入反复修正循环）：

  - `constraint_audit.py` 约束闭环审计、`validate_constraints()` 自动验证

  - `facts_audit.py` / `audit_facts_against_ocr` / `event_breakdown_audit.py` 三方比对与事件源审计

  - 结果合理性逐条审查（Q1-Q9）、建模-代码一致性深度对照（Q9）

  - 多算法交叉验证、双求解器对比、发现小偏差后的反复重跑打磨

  - 参数保真度审计（PROBLEM_FACTS.json 三方核对）——快速模式下正常取参、跑通即可

- ⚠ **例外（快速模式也必须跑，零额度、地基级）**：`claim_code_check.py`（声称↔代码，拦名不副实）、`data_ingest_check.py`（数据摄入完整性，拦"只读首表/静默丢数据"）、`delivery_audit.py`（交付真实性，拦"声称产物缺失/暗中抽样冒充全量"）、`leakage_audit.py`（标签泄漏，拦"≥0.99高分却零去泄漏举证的循环论证"）——这几个都是纯静态零成本，拦的是"论文一眼假/数据没读全后面全白算/交付偷工/指标虚高作弊"的地基级 bug，不是打磨项，`=1` 一律先修再往下。

- 原则：**一次跑通、产出齐全即结束**，把深度质检留给用户。RESULTS.md 末尾的 `<!-- AUDIT_OK ... -->` 凭证仍可写（标注 `fast_mode=1`），但不因审计不过而反复重跑。

**若 `FAST_MODE=0`（默认，严格模式）：** 后文所有审计/审查环节照常执行，不得跳过。

## 输入

1. **MODELING_REPORT.md** — 建模报告（必须存在）

2. **PROBLEM_ANALYSIS.md** — 赛题分析报告

3. **TOPIC_PLAN.md** — 选题规划（统计建模，含图表预规划）

4. **user_data/** — 赛题附件数据

## ⛔⛔⛔ 完成铁律（最高优先级，违反则本步骤失败）

**本步骤必须产出 `RESULTS.md`（≥ 1KB）+ `code/main.py`（≥ 500 字节）+ 至少 1 个 `figures/*.json`**。

⛔ **结束前必跑产出验证**：

```bash

PASS=true

[ -f RESULTS.md ] && SZ=$(wc -c < RESULTS.md) || SZ=0

[ "$SZ" -ge 1024 ] && echo "✅ RESULTS.md ($SZ)" || { echo "❌ RESULTS.md 缺失或过小"; PASS=false; }

[ -f code/main.py ] && CSZ=$(wc -c < code/main.py) || CSZ=0

[ "$CSZ" -ge 500 ] && echo "✅ code/main.py ($CSZ)" || { echo "❌ code/main.py 缺失"; PASS=false; }

JSON_COUNT=$(ls figures/*.json 2>/dev/null | wc -l)

[ "$JSON_COUNT" -ge 1 ] && echo "✅ figures/*.json ($JSON_COUNT)" || { echo "❌ figures/*.json 缺失"; PASS=false; }

# 子问题数对照: 建模报告里有几问, code/ 和 figures/ 就要有几份对应产出

# 统一口径（调 _utils/count_subproblems.sh，与 comp-modeling / comp-paper-zh 完全一致）

EXPECTED_PROBS=$(bash _utils/count_subproblems.sh MODELING_REPORT.md)

ACTUAL_CODE=$(ls code/problem*.py 2>/dev/null | wc -l)

ACTUAL_JSON=$(ls figures/problem_*_results.json 2>/dev/null | wc -l)

[ "$EXPECTED_PROBS" -gt 0 ] && {

  [ "$ACTUAL_CODE" -ge "$EXPECTED_PROBS" ] || { echo "❌ 建模报告 $EXPECTED_PROBS 问, 但只有 $ACTUAL_CODE 个 problem*.py"; PASS=false; }

  [ "$ACTUAL_JSON" -ge "$EXPECTED_PROBS" ] || { echo "❌ 建模报告 $EXPECTED_PROBS 问, 但只有 $ACTUAL_JSON 个 problem_*_results.json"; PASS=false; }

}

[ "$PASS" != true ] && echo "⛔ 产出验证失败 — 必须补全所有缺失项后重新跑验证, 禁止 end_turn 结束本步骤"

```

## 工作流程

### Step 0: 恢复检查

检查 `RESULTS.md`、`code/*.py`、`figures/*_results.json` 是否已存在：

- RESULTS.md 完整（>1KB）-> 跳到结果验证

- code/*.py 存在但无 RESULTS.md -> 直接执行已有代码

- 什么都没有 -> 从头开始

### Step 1: 读取建模报告 + 建立实现清单 + 防错审查

从 MODELING_REPORT.md 提取每个子问题的求解算法、数学公式、输入输出要求、所需 Python 库。

**⛔⛔⛔ 忠实实现铁律（本步最高原则，先记死）：本步的唯一任务是"把建模报告指定的能力真正实现出来"，不是"实现一个能跑通、能过 validate_constraints、能出图的方案"。** 开头必须：

1. **Read `CAPABILITY_CHECKLIST.json` + `MODELING_REPORT.md` 的 `METHOD_CLAIMS_MACHINE` 合同块**，把每条能力的 `name`/`criterion`/`falsifiable_check` 和每条方法的 `must`/`forbid` 签名逐条抄成本步的实现清单。

2. **只实现清单/合同指定的方法**。⛔ **绝对禁止用"未在建模报告里出现的替代范式"**——建模写了 A，代码就必须是 A；不许因为 A 难写就偷偷换成更简单的 B（这正是"选对方法却在实现时降维"的真实翻车根因）。

3. ⛔⛔ **反降维/反代理红线（方向无关，违反即返工，不许用解释代替修复）：**

   - **禁止**把 `MODELING_REPORT` 的 `METHOD_CLAIMS_MACHINE` 里任何 `forbid` 签名写进代码（`claim_code_check.py` 会硬拦）。

   - **禁止用"代理指标"冒充"真实能力"**：拿 ID/文件名/时间/序号等**非语义元数据**当预测标签或分类真值；用**同一批数据派生出的特征去预测由该数据派生的标签**（循环论证/自证）；用字符串/词频匹配冒充"语义"能力；只提取特征却不执行声称的下游动作（如声称"过滤低质"却只打分不过滤）。

   - ⛔ **发现自己正在用代理冒充真能力时，必须换成真方法，不许在注释/RESULTS 里写一句"由于时间/算力限制用了简化"就继续**——那是把降维合法化。真做不到就回 comp-modeling 改声称，而不是让代码与声称脱钩。

**⛔ 防错审查（必做）：** 读取 `references/error_prevention_code.md`，根据 MODELING_REPORT.md 末尾标注的题型，对照对应章节的"必须验证"和"常见 Bug"条目。编码过程中逐项检查。

**⛔⛔ 约束闭环审计（写 RESULTS.md 前必做，最后一道防线）：** 读取 `_utils/error_prevention.md` 的"九、约束闭环校验"章节。按本题题设硬约束写一个 `constraint_audit.py`，**从最终写入的 results.json 重新计算所有约束**（不能信任优化器的 constraints_ok 字段）。**⚠ 该脚本必须遵守 Step 4.5「数据自检铁律·规则 B」：Python 读全精度重算，但只 `print` 结论（PASS/FAIL、n_violations、max_error、最多 5 条越界定位），禁止 print 整个数组。** 任何 audit_fail：必须先修复模型/求解，再回头写稿。在 RESULTS.md 末尾必须有 `<!-- AUDIT_OK source=results.json rechecked_at=<timestamp> -->` 凭证；缺这一行直接判该子问题不通过。

> **⛔⛔ 约束审计必须覆盖"对比基线 / 对照情景"，不能只审最优解（真实翻车根因）：** 凡是要写进正文用于对比的方案——`naive`/`baseline`/`greedy`/就近派车/等权/"不调整"情景等——**必须过与最优解完全同一套 `constraint_audit`**。两种合法结局，二选一，禁止第三种：

> 1. 该基线**满足**全部硬约束 → 正常作对比；

> 2. 该基线**违反**某条硬约束（如就近派车使某站负荷 37 > 单站上限 36，违反 c6）→ 允许保留作对比，但正文**必须显式写明**"此基线违反约束 cX、仅作理论下界/对照、实际不可行"。

> ⛔ **绝对禁止**：把违反约束的基线默认当可行方案参与择优；更禁止**反过来描述**成"该基线已包含/满足该约束"（例：把纯就近派车的 0.658 km 说成"已含容量约束、并非纯就近"——这是硬伤级自相矛盾）。审计报告里对每个基线也要有 `[baseline_name] PASS=.. n_violations=..` 一行。

>

> ⛔⛔ **基线自动登记（把"靠 AI 记得审基线"变成"脚本自动发现基线"，不留人为遗漏口）：** `constraint_audit.py` 开头**必须自动扫 results.json 的键**，把键名或方案名里含 `baseline / naive / greedy / 就近 / 等权 / 均分 / 不调整 / lower_bound / 下界` 的都收集成"待审基线清单"，然后**断言每一个都进了本次审计**，漏审直接 FAIL。这样即使写稿时忘了某个对照方案，脚本也会自己发现并要求补审。范式：

> ```python

> # constraint_audit.py 开头 —— 自动发现所有需审计的方案（最优解 + 全部基线）

> import re, json

> sol = json.load(open('results.json', encoding='utf-8'))

> _BASE_KW = re.compile(r'baseline|naive|greedy|就近|等权|均分|不调整|lower.?bound|下界', re.I)

> discovered = [k for k in sol if _BASE_KW.search(k)]      # 自动发现的基线键

> audited = set()                                          # 每审一个方案就 audited.add(名字)

> # ... 逐个 audit（最优解 + discovered 里每个基线）...

> missing = [b for b in discovered if b not in audited]

> assert not missing, f"[基线漏审] 这些对照方案未过约束审计: {missing} —— 必须补审再写稿"

> ```

> **罕见情形兜底**：若 PROBLEM_ANALYSIS.md 的硬约束清单注明「无硬约束」（纯回归/统计推断/描述性建模），跳过 `constraint_audit.py`，但仍需在 RESULTS.md 末尾留 `<!-- AUDIT_OK source=results.json rechecked_at=<timestamp> n_constraints=0 -->` 凭证以及一句话说明"本题无硬约束，已跑结果合理性自检（量纲/符号/数值范围）"。

**⛔⛔ 方法实现对账（红线一/三根治 · 两道：确定性静态扫描 + 严格模式锚定式对账）：**

**第 3 层 · 声称↔代码 确定性静态扫描（⛔ 两个模式都跑，零额度，拦"灾难级名不副实"）：** 代码写完后必跑 `claim_code_check.py`——它读 MODELING_REPORT.md 的 METHOD_CLAIMS + RESULTS.md + paper/sections，扫 `code/*.py` 里方法必备的 API 标记：

```bash

python _utils/claim_code_check.py --modeling MODELING_REPORT.md --codedir code

CC=$?   # 0=通过 1=HARD FAIL(名不副实,必修) 2=缺文件跳过

```

> - **它只判铁证**：声称"整数规划"却全代码零整数变量标记（只有 `linprog` 连续变量）→ HARD FAIL（红线一）；声称"泊松/排队/蒙特卡洛仿真"却找不到泊松到达采样/队列/事件结构（只是给固定值加 `exponential(0.3)` 噪声）→ HARD FAIL（红线三）。

> - ⛔ **`CC=1` 必须先修再往下**：要么把代码补成真实现该方法，要么把正文/建模报告的声称改成代码真做的事。**这条快速模式也不跳过**——它零成本、且拦的是"论文一眼假掉"的硬伤，不是打磨项。

> - 扫描器**宁漏勿误**：只有"声称了但铁证为 0"才 HARD FAIL；冷门写法只警告，交下面严格模式的锚定式对账。

**第 4 层 · 锚定式 AI 对账（仅严格模式 `FAST_MODE=0` · 同模型自核不额外烧额度 · 兜确定性查不了的残余）：** 快速模式跳过。严格模式下，静态扫描过了之后，**你再逐条核 METHOD_CLAIMS 里扫描器管不到的部分**（如"某条单站容量约束到底进没进模型/进没进目标函数"——约束名任意、无法通用静态扫）。⛔ **关键：不许问自己"我实现了吗"（会诱导自证），要拿上一步扫描器的客观结果当锚**：

> - 把扫描输出摆出来对照——"扫描显示：整数变量命中 N 处、poisson 到达命中 M 处、队列结构命中 K 处"，再逐条问"对照这些硬证据，我这句声称成立吗？哪几行代码支撑？"

> - **典型残余脱钩**：声称"含单站容量约束"，`solve_pmedian` 只跑 p-median + 事后就近配车、容量约束没进模型（红线一的隐蔽版，静态扫描抓不到"某约束缺失"，靠这步）。发现即返工。

> - 在 RESULTS.md 末尾写凭证：`<!-- METHOD_CHECK static_cc=<0/1> n_claims=K n_implemented=K fast_mode=0 -->`（快速模式：`static_cc=<0/1> fast_mode=1 skipped_anchor=1`，static_cc 仍记录，因为第 3 层两模式都跑）。

> ⛔ **数值一致 ≠ 结论成立**：数字全和 results.json 对上，也穿透不了"代码没实现声称方法"——第 3、4 层就是补这个盲区，是数值审计之上的必要闸。

**⛔⛔ 数据摄入完整性闸（红线四根治 · 防"程序照常跑完却悄悄只喂了一部分数据" · 零额度，两模式都跑）：**

真实翻车根因：`pd.read_excel` 不写 `sheet_name` 时**默认只读第 1 个 sheet、不报错不告警**——一个 xlsx 里藏了带标签的多张表，只读到首表，58% 训练数据在数据加载第一步就被静默丢掉，程序照样跑完、照样吐出一堆"看着合理"的数字。这类**静默 bug** 骗过了前面所有"数字对不对/方法做没做"的闸，必须单独一道闸把"静默容错"改成"响声崩溃"。

**治本层（写数据加载代码时的硬性铁律）：**

1. **Excel 一律 `sheet_name=None` 读全部表**，再按题意决定合并/择取；确要只用某张，**必须显式** `sheet_name='表名'`/索引并在注释写明理由。**绝对禁止**裸 `pd.read_excel(f)`（= 默认首表 = 静默丢数据）。

2. **禁止 `nrows=` / `df[:N]` / `.head(N)` 截断建模用数据**（探查打印可用）。真要抽样：`df.sample(n=, random_state=SEED)`，并在 RESULTS.md 声明"抽样 N / 总量 M"。

3. **读完对 `DATA_PROFILE.json` 核行数（基准来自机器建档，不手填、不靠记忆）**：comp-prob-analysis 阶段 `data_profile.py` 已把每个文件的 `total_rows`/`n_sheets`/各 sheet 行数探测好落盘。数据加载末尾**从这份档读基准值**做断言，实读行数对不上（被截断/漏表）立即 `raise`、中止编码，禁止带残缺往下跑。关键标签列再 `assert df[label_col].notna().any()`（整列全空 = 那张标签表根本没读进来）。

   ```python

   # 数据加载末尾 —— 摄入完整性断言（基准从 DATA_PROFILE.json 取，只 print 结论，遵守 Step 4.5 规则 B）

   import json

   _prof = json.load(open('DATA_PROFILE.json', encoding='utf-8'))['files'].get(fname, {})

   # 先确认该文件建档成功（建档失败的只有 error 键、无 total_rows）——报错说人话，别抛裸 KeyError

   assert 'total_rows' in _prof, (

       f"[未建档] {fname} 不在 DATA_PROFILE.json 或建档失败（{_prof.get('error','缺记录')}）——"

       f"先修 data_profile.py 把该文件读通再核对；连档都建不出来的文件不应直接喂给模型。")

   assert total_rows == _prof['total_rows'], (

       f"[摄入不全] {fname} 实读 {total_rows} 行 ≠ 建档时的 {_prof['total_rows']} 行"

       f"（该文件共 {_prof['n_sheets']} 张 sheet）——多半只读了首表/被 nrows 截断，"

       f"改 sheet_name=None 读全并重跑。")

   print(f"[data_ingest] {fname} 全量 {total_rows} 行 / {_prof['n_sheets']} sheet 已核对通过")

   ```

   > ⛔ **基准值一律取自 `DATA_PROFILE.json`，禁止在代码里手写魔数行数**——手写的数会随上下文漂移/被 AI 凭印象编错，而建档是探查阶段机器数出来的、落在磁盘上，不受对话长短影响。这跟 `params.py` 强制从 `PROBLEM_FACTS.json` 取参是同一个道理。

**兜底层 · 确定性静态扫描（⛔ 两个模式都跑，零额度，拦"默认首表"这个铁证）：** 代码写完后必跑 `data_ingest_check.py`——扫 `code/*.py`，`read_excel(...)` 没写 `sheet_name=` 直接 HARD FAIL（强制作者表明读哪张，根治首表陷阱）；`nrows=`/大数值 `.head()`/`[:N]` 截断判 WARN：

```bash

python _utils/data_ingest_check.py --codedir code

DC=$?   # 0=通过 1=HARD FAIL(有裸 read_excel,必修) 2=无 code 跳过

```

> - ⛔ **`DC=1` 必须先修再往下**：把裸 `read_excel(f)` 改成 `sheet_name=None`（读全部）或显式写死某张。这条**快速模式也不跳过**——它零成本、拦的是"数据都没读全、后面全白算"的地基级 bug。

> - 扫描器**宁漏勿误**：只有"read_excel/ExcelFile.parse 没显式表明读哪张 sheet"这种零歧义铁证才 HARD FAIL；它不替你判该读几张（那是语义），只逼你别用"默认只读首表"这个危险默认值。截断写法只 WARN，交你/严格模式判用途。

**⛔⛔⛔ 题面参数保真度审计（参数密集型题目必做，最前置防线）：** 若工作区存在 `PROBLEM_FACTS.json`（comp-prob-analysis 阶段产出，题面参数 ≥ 20 时必产），编码前**必须**先按以下顺序做：

1. **以 PROBLEM_FACTS.json 为唯一权威源载入参数**：`facts = json.load(open('PROBLEM_FACTS.json'))`；所有数值常数必须从 facts 取，禁止裸数字字面量

2. **建命名常数**：例如 `P_DETECT_BIG_LASER_VS_MISSILE = facts['weapons'][0]['targets'][0]['p_detect']`，让代码读起来与题面表 1 行 1 直接对得上

3. **跑 `facts_audit.py`**（见 `_utils/error_prevention.md` 第十四章 14.4）：三方比对 PROBLEM_FACTS.json ↔ code/*.py ↔ paper/正文；找出疑似虚构 / 抄错的数字

4. **跑 `audit_facts_against_ocr` 做 OCR 客观比对**（见第十四章 14.7）：从 `user_data/*_extracted.txt`（workflow_engine 入口 Vision OCR 自动产出，AI 改不了）自动抽数字集合，与 PROBLEM_FACTS.json 数字集合比对；并验证 `_meta.source_files[].sha256` 与文件实际 sha256 一致（防 OCR 被篡改）。**facts 含 OCR 原文没有的数字 → 拒绝**（视为虚构）。

5. **每条 `rules` 段的 `machine_check` 必须有对应的 unit test**：例如"激光只能与激光协同"对应 `assert not any(plan.has_laser and plan.has_non_laser for plan in synergy_plans)`

**⛔⛔⛔ 事件源分类计数与反推（含多种来源累积同一聚合量时必做，最易出"约束都过但结论错位"bug）：**

详见 `_utils/error_prevention.md` 第十五章。

**触发条件**：题目里**多个来源**累积成**同一聚合量**时必须按本规则编码。常见形态：

- 多种伤害源（远程 / 近战 / 自爆）累加同一目标的总伤害

- 多种成本源（运输 / 等待 / 延误 / 罚款）累加同一总成本

- 多种来源人流（社区 / 输入 / 院内）累加同一新增量

- 多种胜负原因（主动击败 / 对手退出 / 裁定）累加同一胜率

- 多种漏检 / 拦截 / 通过原因累加同一统计指标

**编码硬性要求**：

1. **每个计数器只记录一种来源的事件**：模式 `count_by_<source>` / `total_<metric>_from_<source>`；禁止 `n_hit` / `events` / `struck` 这类二义命名（这是导致 bug 的根因——一个计数器同时被多个分支 append 不同来源的事件）

2. **每次离散事件落详细元组**：`events.append({'t': t, 'source': '<具体来源标识>', 'target': ..., 'value_per_event': <理论单次量值，从 facts 取>, 'cause_id': ...})`，禁止只 `flag=True` 或 `counter += 1`

3. **results.json 必须含**：

   - `events` 字段（所有离散事件列表）

   - `source_unit_value` 字典（每种 source 的理论单次量值，来自 PROBLEM_FACTS.json）

   - `totals` 字典（按 metric 分组的累计量）

   - `verb_to_sources` 字典（陈述动词到合法 source 集合的映射，供写稿步骤反查）

4. **代码末尾跑 `event_breakdown_audit.py`**（见 15.3，同样遵守 Step 4.5「数据自检铁律·规则 B」：只 print 结论，禁止 print 整个 events 数组）：

   - 总量 = Σ(per-event value)，差超 1e-3 拒绝

   - 按 source 分组每组 `count × theoretical_per_event ≈ actual_sum`，差超 1e-3 拒绝

5. **RESULTS.md 描述事件时必须标注**：计数器名 + 单次量值 + 事件次数 + 各 source 贡献

   - 例：`总量 X = N × <per_event_value>（来自 count_by_<source>，每次贡献 v）`

   - 让下游写稿步骤可以直接 grep 独立字段，无需脑补**⛔⛔⛔⛔ 防长上下文记忆漂移：强制生成 `code/params.py`（编码第一步）：**

   ```python

   # code/params.py — 自动生成，禁止手改

   import json

   from pathlib import Path

   _FACTS = json.loads(Path('PROBLEM_FACTS.json').read_text(encoding='utf-8'))

   # 命名常数（按 facts 结构展开所有数值）

   BIG_LASER_RANGE_KM = _FACTS['weapons'][0]['range_km']

   BIG_LASER_VS_MISSILE_P_DETECT = _FACTS['weapons'][0]['targets'][0]['p_detect']

   # ... 等等

   ```

   后续所有 code/*.py 必须 `from params import *`，**禁止裸数字字面量**（除白名单 0/1/2/-1/π/e 等纯数学常数）。这样即使上下文窗口压缩、AI"忘了"具体参数值，命名常数也只能从 params.py 取，不会凭印象重写。

   ⛔⛔ **参数口径一致性自检（防"同一物理量在不同子问题口径打架"，红线二根治，零额度本地跑，任何模式都跑）：** 若 MODELING_REPORT.md 有「参数口径表」，`params.py` 必须按表定义命名常数，并在末尾写一段断言：**凡带同一语义标签、或存在换算关系的量，换算后有效值必须一致**。典型如"服务率 μ 次/分 × 营业分钟数" 应 ≈ "日服务上限 次/日"——不一致直接 `assert` 报错、中止编码，回去统一口径。

   ```python

   # params.py 末尾 —— 口径一致性断言（只 print 结论/冲突，不 print 大数组）

   OP_MINUTES = OP_HOURS * 60

   _daily_from_mu = SERVICE_RATE_MU * OP_MINUTES      # 由排队参数换算的日服务力

   assert abs(_daily_from_mu - DAILY_CAPACITY) <= max(1.0, 0.05 * DAILY_CAPACITY), (

       f"[口径冲突] 日服务力：排队模型 μ×营业时长={_daily_from_mu:.3g} 次/日 "

       f"≠ 运输模型 DAILY_CAPACITY={DAILY_CAPACITY} 次/日。同一辆车两个模型能力不一致，"

       f"必须统一口径（改 μ 或改上限）再继续。")

   print("[params] 口径一致性 OK")

   ```

   ⛔ 每个语义标签的物理含义全篇唯一（如 `total_response` 只能指"总响应时间"，不能一处当总响应、一处当纯排队等待）——写稿引用时按标签取，别自造同名不同义的量。

**⛔ 加固版审计（参数密集型必跑，覆盖 6 个边缘漏洞）：**

   ```bash

   # comp-prob-analysis 阶段已跑过 --stage prob（OCR 比对）；本阶段跑完整审计含代码端

   python3 _utils/facts_audit.py --stage code 2>&1 | tee AUDIT_REPORT.md

   RC=$?

   n_suspicious=$(grep -cE '^- (⛔|⚠)' AUDIT_REPORT.md || echo 0)

   # 凭证里加 n_suspicious_numbers 字段（写稿阶段拦截非零）

   echo "<!-- AUDIT_OK source=results.json rechecked_at=$(date -Iseconds) n_constraints=$N n_suspicious_numbers=$n_suspicious -->" >> RESULTS.md

   ```

   含：OCR 比对（复查，防中途篡改）/ schema 校验 / 派生值验算 / 代码端裸数字审计 / 图脚本数据溯源 / 子问题字段隔离。详见 `_utils/error_prevention.md` 第十四章 14.6-14.7。

**📚 按题型按需调用其他审计章节（`_utils/error_prevention.md`）**：

- **第十章 单位审计**（`unit_audit.py`）：含物理量 / 工程量 / 经济量的题 — 扫描代码裸常数，比对 PROBLEM_ANALYSIS.md 的变量-单位登记表

- **第十一章 可复现性**（`repro_audit.py` + `set_all_seeds`）：含随机数 / 启发式 / 蒙特卡洛 / 神经网络 / MCMC 的题 — **代码入口必须先调 `set_all_seeds(seed)`**；results.json 头部必须含 `seed / run_id / python / numpy / torch` 等版本信息；每张图 figures/*.json 必含 seed 字段

- **第十二章 数据泄露**（切分泄漏模板）：含训练 / 测试 / 时序预测 / 因果识别的题 — 切分必须早于任何 `fit()`，时序题禁用 KFold shuffle，检测未来信息特征。**注**：训练/测试切分泄漏用本章模板；"高分虚高/循环论证"另有部署好的第 8 闸 `leakage_audit.py`（见 Step 7，两模式都跑）自动扫，不用手抄。

- **第十三章 求解器收敛**（`solver_audit.py`）：含数值优化 / 启发式 / MCMC 的题 — 不要盲信 `success=True`，必须检查梯度范数 / 多重起点方差 / 收敛曲线尾段 / 多链 R̂ 等"二阶证据"

**⛔ MANDATORY: 输出实现清单，后续逐项打勾：**

```

IMPLEMENTATION CHECKLIST (from MODELING_REPORT.md):

[ ] 问题1: [算法名] — 输入: [xxx], 输出: [yyy], 库: [zzz]

[ ] 问题2: [算法名] — 输入: [xxx], 输出: [yyy], 库: [zzz]

[ ] 问题3: [算法名] — 输入: [xxx], 输出: [yyy], 库: [zzz]

[ ] 灵敏度分析: [参数列表]

```

每完成一个子问题，更新清单状态。

### Step 1.5: 提取图表预规划

**⛔ MANDATORY: 读取规划文档的图表预规划，了解下一步 paper-figure 需要生成哪些图表。**

comp-code 不生成 PDF 图表，但需要确保输出的 JSON 数据能支撑这些图表。

```bash

echo "=== 图表预规划 ==="

for plan in TOPIC_PLAN.md PROBLEM_ANALYSIS.md MODELING_REPORT.md; do

    [ -f "$plan" ] || continue

    echo "--- $plan ---"

    grep -i 'fig_\|图表\|TABLE_\|TikZ\|预规划\|figure' "$plan" | head -30

done

```

记录规划中的图表清单，确保每个图表对应的数据都会在分析过程中输出到 JSON。

**⛔ 图表语言规则：** 中文论文（统计建模/数模竞赛）的图表 axis label、legend、annotation 必须用中文。例如 `ax.set_xlabel('迭代次数')` 而不是 `ax.set_xlabel('Iterations')`。但这是 paper-figure 的事——comp-code 只需确保 JSON 数据的 key 名有意义即可。

### Step 2: 环境准备

检查 Python，安装必要库（numpy, pandas, scipy, matplotlib, scikit-learn, statsmodels, networkx）。

### Step 2.5: 数据读取验证（有附件数据时必做）

**⛔ 写任何求解代码之前，先写一个独立的数据验证脚本，确认数据读取正确：**

```python

# code/data_check.py — 数据读取验证（先跑这个，再写求解代码）

import pandas as pd

import os, glob

data_files = glob.glob('user_data/*.csv') + glob.glob('user_data/*.xlsx') + glob.glob('user_data/*.xls')

print(f"找到 {len(data_files)} 个数据文件")

for f in data_files:

    print(f"\n=== {os.path.basename(f)} ===")

    try:

        if f.endswith('.csv'):

            # 尝试多种编码

            for enc in ['utf-8', 'gbk', 'gb2312', 'latin-1']:

                try:

                    df = pd.read_csv(f, encoding=enc)

                    print(f"  编码: {enc}")

                    break

                except UnicodeDecodeError:

                    continue

        else:

            # ⛔ 必须看全部 sheet：不写 sheet_name 时 pandas 默认只读第 1 张、不报错不告警，

            #    多 sheet 数据会被静默丢掉（真实翻车根因）。这里读全部并逐张打印行数暴露全貌。

            _all = pd.read_excel(f, sheet_name=None)

            print(f"  共 {len(_all)} 个 sheet: " + ", ".join(f"{n}({len(d)}行)" for n, d in _all.items()))

            df = pd.concat(_all.values(), ignore_index=True) if len(_all) > 1 else next(iter(_all.values()))

        print(f"  形状: {df.shape}")

        print(f"  列名: {list(df.columns)}")

        print(f"  数据类型:\n{df.dtypes}")

        print(f"  缺失值:\n{df.isnull().sum()[df.isnull().sum() > 0]}")

        print(f"  前3行:\n{df.head(3)}")

        # 数值列的基本统计

        num_cols = df.select_dtypes(include='number').columns

        if len(num_cols) > 0:

            print(f"  数值统计:\n{df[num_cols].describe()}")

            # 检查异常值

            for col in num_cols:

                if df[col].min() < 0 and '价格' in col or '数量' in col or '距离' in col:

                    print(f"  ⚠ {col} 有负值（{df[col].min()}），检查是否合理")

                if df[col].isnull().sum() > len(df) * 0.5:

                    print(f"  ⚠ {col} 缺失率 > 50%")

    except Exception as e:

        print(f"  ❌ 读取失败: {e}")

```

**执行 data_check.py 后，确认以下几点再继续：**

1. 所有数据文件都能正确读取（编码、分隔符无误）

2. 列名和题目描述一致（不是乱码或错位）

3. 数据规模和题目描述一致（行数、列数）

4. ⛔ **每个 Excel 的 sheet 总数与每张行数都看清楚了**（上面打印的"共 N 个 sheet"）——把这份"文件→sheet→行数"清单记进 `PROBLEM_ANALYSIS.md`/`MODELING_REPORT.md`，作为后续「数据摄入完整性闸」断言的预期基准值。谨防"一个 xlsx 里藏了带标签的多张表、却只读到首表"。

4. 缺失值和异常值已识别，后续代码中有处理方案

### Step 3: 代码目录结构

```

code/

  main.py          # 主程序（串联所有子问题）

  problem1.py      # 子问题 1

  problem2.py      # 子问题 2

  utils.py         # 公共工具

  requirements.txt

```

### Step 3.0: ⛔⛔⛔ 模块导入铁律（违反必失败）

**问题本质：** code/ 下的脚本互相 `import` 时，从不同目录调用会导致 sys.path 不包含 `code/`，

报 `ModuleNotFoundError: No module named 'utils'` / `'problem1'` 等。这是历史上最高频的失败原因。

**⛔ 规则 1：每个 .py 文件顶部必须有自举 import 头（在所有 import 之前）：**

```python

# ⛔ 自举模块路径（让 sibling import 不依赖调用方式）

import os, sys

_HERE = os.path.dirname(os.path.abspath(__file__))

if _HERE not in sys.path:

    sys.path.insert(0, _HERE)

# 之后才能写其它 import

import numpy as np

import utils as u   # 现在 utils.py 跟当前文件同目录就一定能 import 到

```

**⛔ 规则 2：执行任何 code/ 下的脚本必须 `cd code && python xxx.py`，禁止 `python code/xxx.py`**

```bash

# ✅ 正确（无论 utils 在不在都能跑）

cd code && python data_check.py && cd ..

cd code && python problem1.py && cd ..

cd code && python main.py && cd ..

# ❌ 错误：sys.path 不含 code/，sibling import 会爆 ModuleNotFoundError

python code/problem1.py

python -m code.problem1

```

**⛔ 规则 3：写入子问题脚本前先写 `code/utils.py` 雏形（哪怕暂时为空），避免"先写 problem1 → import utils → utils 还没创建"的瞬时错。**

**⛔ 规则 4：跑代码必须用 `set -e` + 显式检查 exit code，不能在脚本失败后假装结果有效：**

```bash

cd code

set -e

python data_check.py 2>&1 | tee ../_tmp/data_check.log

python problem1.py 2>&1 | tee ../_tmp/problem1.log

[ -f ../figures/problem_1_results.json ] || { echo "❌ problem1 未产出结果 JSON"; exit 1; }

cd ..

```

### Step 4: 逐子问题编写和执行

**必须按顺序逐问求解：编写 -> 执行 -> 验证 -> 下一问。**

**⛔ Step 4.0: 上游一致性检查（开始编码前必做）：**

```bash

echo "=== 上游一致性检查 ==="

# 检查 MODELING_REPORT.md 是否存在

[ -f MODELING_REPORT.md ] && echo "✅ MODELING_REPORT.md 存在" || { echo "❌ MODELING_REPORT.md 不存在！"; exit 1; }

# 提取子问题数量（统一口径：只数标题行，避免正文出现次数导致虚高）

PROB_COUNT=$(bash _utils/count_subproblems.sh PROBLEM_ANALYSIS.md)

MODEL_COUNT=$(bash _utils/count_subproblems.sh MODELING_REPORT.md)

echo "赛题分析子问题数: $PROB_COUNT, 建模报告子问题数: $MODEL_COUNT"

[ "$MODEL_COUNT" -lt "$PROB_COUNT" ] && echo "⚠ 建模报告覆盖的子问题数少于赛题分析，请检查是否遗漏"

# 提取建模报告推荐的方法

echo "--- 建模报告推荐方法 ---"

grep -i '算法\|方法\|模型.*选择\|求解.*策略' MODELING_REPORT.md 2>/dev/null | head -10

echo "--- 编程实现时必须使用上述方法，或明确说明替代理由 ---"

```

代码性能要求：

- 优先使用 numpy 向量化运算，避免 Python 原生 for 循环遍历大数据

- 数据量大（>1000 行）必须用向量化或矩阵运算

- 每个脚本执行前后打印进度信息

- 如果代码跑超过 3 分钟，立即重写优化版本

自主判断数据来源：

- 有附件数据（`user_data/*.csv` 存在）：从文件读取

- 无附件数据（纯建模题）：根据 MODELING_REPORT.md 自行构造参数

每个子问题：

1. 编写独立 Python 文件

2. 执行并检查输出

3. 验证结果合理性

4. 保存结果到 `figures/problem_N_results.json`

5. 结果异常则修改代码重跑

---

### Step 4.5: ⛔⛔⛔ 每问跑完后的自检流程（核心，每个子问题都必须做）

**这是本步骤防失败的关键。每完成一问的代码 + JSON 后，必须按下面流程做自检，

满足要求才能进入下一问。** 不要写完所有问题再统一自检 — 那样发现问题要回头改, 浪费 turn 预算。

#### ⛔⛔⛔ 数据自检铁律（读到这里先记死，贯穿全部自检环节）

**核心原则：全精度数据一个字节不删，但你（AI）永远不许把整个 `results.json` 读进上下文。** 所有对结果数据的核对，一律由 Python 脚本读文件重算，只把「结论」打印给你看。原因：`problem_*_results.json` 常含 301 步 × 数百部件的全精度时序数组（可达 10+ MB / 数十万行），一旦你 `Read` / `cat` / `Grep` 全文，会瞬间撑爆上下文——本地大模型直接失败，经中转的 GPT 会因协议翻译超长而反复 `api_retry` 卡死。**这与精度无关：数据照样全精度写盘，只是不进你的 token 窗口。**

**⛔ 规则 A — 禁止整读结果 JSON。** 对 `figures/*_results.json`、`figures/all_results.json` 这类结果文件，**禁止** `Read` 整个文件、禁止 `cat`、禁止 `Grep` 全文捞数值。要看内容，只能跑下面的 `summarize` 脚本拿 KB 级摘要（字段 → 长度 / 数值范围 / 前 3 个样本）：

```bash

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

    sz=os.path.getsize(f)

    d=json.load(open(f,encoding='utf-8'))

    print(f'\n=== {os.path.basename(f)} ({sz//1024}KB) ===')

    if isinstance(d, dict):

        for k,v in d.items(): print(f'  {k}: {summarize(v)}')

    else: print(f'  {summarize(d)}')

PY

```

**⛔ 规则 B — 自检 / 审计脚本只准输出结论，禁止 print 整个数组。** `constraint_audit.py`、`event_breakdown_audit.py`、`validate_constraints()` 等所有自检脚本：用 Python **读全精度文件、重算每一条约束**（算得比你肉眼准，精度全在），但**只准 `print` 结论**——`PASS` / `FAIL`、`n_violations=N`、每条约束的 `max_error`，以及**最多 5 条**越界样本的定位（如 `t=137 gap=-0.0047 超限`）。**禁止 `print` 整段数组 / 整个 dict / 整个 DataFrame。** 你只读这份 KB 级审计报告来决定「过 / 回去改」，自检链条完整、且比 grep 猜数更可靠。

```python

# constraint_audit.py 输出范式（✅ 对 / ❌ 错）

# ✅ 只吐结论：

print(f"[Q1] PASS={ok}  n_violations={nv}  max_gap_error={maxe:.3e}")

for s in violations[:5]:               # 最多 5 条定位

    print(f"    VIOLATION t={s['t']} gap={s['gap']:.4g}")

# ❌ 绝对禁止（会把全精度大数组灌进 AI 上下文）：

# print(results)          /  print(json.dumps(data))  /  print(df.to_string())

```

> 说明：约束闭环审计（第 97 行）、事件源审计（第 128 行）都遵循本规则——脚本重算用全精度、给 AI 的只有结论。全量数据仍完整写盘供下游 paper-figure 使用，精度零损失。

每个子问题跑完, 立即按以下顺序 Read 自检文件并按其要求验证：

**第 1 步：必读（所有题型）**

```

Read references/checks/_index.md         # 自检总索引（仅第 1 问读, 后续可跳过）

Read references/checks/consistency.md    # 建模-代码契约 + 物理参数引用 + 自动化约束验证代码

Read references/checks/sanity_check.md   # 自动数值审查 + 9 问背景审查 + 编程 Bug 排查

```

**第 2 步：根据本问的题型选读 1 个分类自检文件**

| 本问类型 | Read 哪个 |

|---|---|

| 优化类（调度/选址/路径/分配/规划/求最优值）| `references/checks/optimization.md`（含 5 层求解 + 结构性验证）|

| 预测类（时间序列/回归/分类）| `references/checks/prediction.md` |

| 评价类（TOPSIS/AHP/熵权法/排名打分）| `references/checks/evaluation.md` |

| 物理/几何（碰撞检测/动力学/ODE/SAT 检测）| `references/checks/physical.md` |

| 统计/实证/图论 | `references/checks/sanity_check.md` 末尾的 S/G 区段已涵盖 |

**第 3 步：把自检结论写到 `_tmp/problem_N_check.md`，每条 ✅/⚠️/❌**

**⛔⛔ 第 3.5 步：任务对齐硬断言 `validate_capability()`（核心升级——自检从"数值合法"到"能力真做到"，方向无关）**

`validate_constraints()` / `constraint_audit.py` 只查"数值合法"（∈[0,1]、sum=1、约束不越界）——但**数值全合法 ≠ 这段代码真解决了那个能力**（逻辑回归的输出也 ∈[0,1]、sum=1）。所以本问代码末尾**必须再写一个 `validate_capability()`**，把该子问题在 `CAPABILITY_CHECKLIST.json` 里每条能力的 **`falsifiable_check`** 逐条翻译成**可证伪的运行时断言**：**断言不过就 `raise`、中断本问，而不是记个注释继续出图。**

```python

# code/problem_N.py 末尾 —— 任务对齐硬断言（断言内容来自能力清单的 falsifiable_check，方向无关）

def validate_capability():

    # 逐条把本问能力的 falsifiable_check 变成断言。下面按不同方向举例，你按本题实际写：

    # 【真伪/需外部真值类】禁代理标签 + 去泄漏后指标显著优于随机 + 金标准来源已声明

    assert LABEL_SOURCE not in ("file_id", "filename_prefix", "row_index"), \

        "[能力不成立] 标签来自非语义元数据(ID/文件名)，是代理冒充真伪判别"

    assert auc_deleaked > 0.5 + MARGIN, \

        f"[能力不成立] 去泄漏后 AUC={auc_deleaked:.3f} 未显著>0.5，模型在拟合自己(循环论证)"

    assert GOLD_STANDARD_SOURCE, "[能力不成立] 真伪判别未声明金标准来源(人工标注/外部核查)"

    # 【抽取类】结果带 span 位置 + 抽取器非纯词典

    # assert all("span" in r and r["span"] for r in extracted), "[能力不成立] 抽取无位置=词典匹配冒充"

    # 【优化类】声称的硬约束真进了求解器(非事后配平)

    # assert constraint_in_solver_model, "[能力不成立] 约束未进模型，是事后配平"

    # 【CV分割类】输出逐像素 mask 而非仅分类标签

    # assert output_mask.ndim == 2 and iou_holdout > IOU_TH, "[能力不成立] 未输出mask/IoU不达标"

    print(f"[Q{N}] validate_capability PASS")

validate_capability()   # ⛔ 不过即 raise 中断，禁止 try/except 吞掉后继续

```

> - **断言内容不由本 SKILL 预置**（那会锁死方向）——一律**从该问能力清单的 `falsifiable_check` 字段来**，写清"什么情况判不成立"。NLP/优化/CV/时序/RL 各写各的，机制通用。

> - ⛔ **禁止把 `validate_capability` 写成永远为真的空壳**（如 `assert True`）或 `try/except` 吞掉——那等于没有。断言必须真能在"代码降维/用代理"时炸出来。

> - 在 `_tmp/problem_N_check.md` 记录：`validate_capability: PASS/FAIL + 各条断言`。FAIL 按第 4 步处理（修代码到真做到，不是删断言）。

**第 4 步：处理 ❌**

- 任何 ❌（含 `validate_capability` raise） → 修代码 → 重跑 → 重新自检

- ⛔ **`validate_capability` 不过，只能"把能力真做出来"，绝不许删断言/改成空壳/降低阈值蒙混**

- 同一问最多修 3 轮，3 轮还不通过 → 在 RESULTS.md 中标注"建模需修正"，继续下一问

**第 5 步：全部 ✅ 或最多 ⚠️ → 把本问的方法 + 关键结果写到 RESULTS.md 对应章节，立即下一问**

⛔ **关键纪律**：

- 自检时**不能依赖记忆里的规则**，必须显式 Read 上面列出的 .md 文件 — 这是本拆分设计的目的

- 每问都要走完 Step 4.5 才能开始下一问，不要跳过、不要合并、不要等到所有问都跑完再统一自检

### Step 5: 编写主程序

`code/main.py` 串联所有子问题，汇总结果到 `figures/all_results.json`。

### Step 5.5: 模型检验（根据题型自主判断）

根据题目类型，选择合适的模型检验方式。不是所有题都需要灵敏度分析 — 自己判断：

- **优化类**（调度/选址/路径）→ 灵敏度分析：关键参数 ±20% 对目标函数的影响

- **预测类**（时间序列/回归）→ 交叉验证 + 残差分析 + 多模型对比

- **评价类**（TOPSIS/AHP/熵权法）→ 权重稳定性分析：微调权重看排名是否变化

- **图论/网络类** → 参数灵敏度（边权/容量变化对最优解的影响）

- **统计/实证类** → 稳健性检验（替换变量、子样本、工具变量）

如果判断需要灵敏度分析，执行以下步骤：

Read MODELING_REPORT.md for the sensitivity analysis plan. For each key parameter identified:

1. Write `code/sensitivity_analysis.py` that varies the parameter across a range (e.g., ±20% in 10 steps)

2. For each parameter value, re-run the model and record the objective function value

3. Save results to `figures/sensitivity_results.json`:

```json

{

  "parameter_name": {"values": [...], "objective": [...]},

  "parameter_name2": {"values": [...], "objective": [...]}

}

```

4. Execute the script and verify results are reasonable

This data is required by paper-figure to generate tornado charts and sensitivity curves, and by comp-paper-zh for the 灵敏度分析 chapter.

### Step 6: 结果验证 + 实现清单对照

- 数值范围：概率在[0,1]、非负数、非 NaN/Inf

- 一致性：子问题间不矛盾

- 收敛性：优化器是否收敛

- 统计检验：R2在[0,1]、p值在[0,1]

**⛔ MANDATORY: 对照 Step 1 的实现清单，逐项验证：**

```bash

echo "=== 实现清单对照 ==="

echo "检查每个子问题的结果文件是否存在且非空："

for f in figures/problem_*_results.json figures/all_results.json; do

    if [ -f "$f" ] && [ -s "$f" ]; then

        echo "  ✅ $f ($(wc -c < "$f") bytes)"

    else

        echo "  ❌ $f — MISSING or EMPTY"

    fi

done

# 灵敏度分析数据是软性要求(优化类必做, 其他题型可选)

if [ -f figures/sensitivity_results.json ]; then

    echo "  ✅ figures/sensitivity_results.json (灵敏度分析数据)"

elif [ -f MODELING_REPORT.md ] && grep -qE '灵敏度|sensitivity' MODELING_REPORT.md; then

    echo "  ⚠ figures/sensitivity_results.json — 建模报告提到灵敏度但未产出, 优化类必须补"

fi

echo ""

echo "检查代码文件是否存在："

for f in code/*.py; do

    [ -f "$f" ] && echo "  ✅ $(basename $f)" || echo "  ❌ $(basename $f)"

done

```

**如果有 ❌，必须回去补完再继续。** 特别注意：

- `figures/all_results.json` 必须存在（paper-figure 依赖它画图）

- 每个子问题的 `figures/problem_N_results.json` 必须存在

- `figures/sensitivity_results.json` 仅当题目/建模报告涉及灵敏度分析时必须（优化类必做）

### Step 7: 结果汇总

保存到 `RESULTS.md`：每个子问题的方法、关键结果、数据文件路径、代码文件清单。

**⛔⛔ 同时产出 `DELIVERABLES.json`（机器可读的交付清单，第 7 道闸的对账基准）：** 把"本次真正产出了哪些交付物"逐条列清，供 `delivery_audit.py` 核对"声称的都真产出了"。这是防"声称与产物不符"（声称有测试集预测/五元组结果，产物里却没有）的地基。格式：

```json

{"deliverables": [

  {"path": "figures/problem_1_results.json", "desc": "任务一：事件五元组抽取结果"},

  {"path": "output/predictions_test.csv",    "desc": "测试集预测产物"}

]}

```

> ⛔ 只列**真已产出**的文件；不要把"计划要做但没做"的写进去（那会被对账闸抓成"声称与产物不符"）。反过来，题目/建模报告要求的产物若没产出，别靠删清单蒙混——回去补做。

**⛔⛔ 交付真实性闸（红线四延伸 · 防"交付偷工/声称不符/暗中抽样冒充全量" · 零额度，两模式都跑）：** 结果汇总后必跑 `delivery_audit.py`：

```bash

python _utils/delivery_audit.py --codedir code --deliverables DELIVERABLES.json --results RESULTS.md

DA=$?   # 0=通过 1=HARD FAIL(声称产物缺失/为空,或代码抽样却没在RESULTS声明) 2=缺清单跳过

```

> - **交付对账**：`DELIVERABLES.json` 里每个声称产物必须真实存在且非空——声称有、实际无/空 → HARD FAIL。要么真产出，要么别声称。

> - **抽样透明**：代码里出现 `sample()/nrows=/[:N]/train_test_split` 等抽样截断，RESULTS.md 却找不到任何抽样声明 → HARD FAIL（暗中抽样冒充全量是重大失真）。抽样必须显式写"仅用 N 行 / 总量 M 行（对齐 DATA_PROFILE.json）、为什么抽、对结论的影响"。

> - ⛔ **`DA=1` 必须先修再往下**，快速模式也不跳过——它零成本，拦的是"论文声称的东西根本没做/数据缩水没交代"这类交付级硬伤。

**⛔⛔ 标签泄漏/循环论证闸（红线四延伸 · 防"虚高指标冒充真本事" · 零额度，两模式都跑）：** 含机器学习/分类/判别/评分（有 AUC/准确率/F1 等**分类性能**指标）的题，结果汇总后必跑 `leakage_audit.py`。**⚠ 注意：本闸只认分类/判别性能指标，故意不认 R²/拟合优度**——数模曲线拟合/插值题 R²=0.999 是正常拟合优度、无泄漏概念，不会被本闸触发或误伤：

```bash

python _utils/leakage_audit.py --codedir code --results RESULTS.md

LK=$?   # 0=通过 1=HARD FAIL(≥0.99高分却零去泄漏举证) 2=无指标可查跳过

```

> - **高分举证闸**：结果 JSON 里出现 ≥0.99 的性能指标（auc/accuracy/f1/r2…），却在 RESULTS/代码/建模报告全局找不到去泄漏举证（去泄漏/holdout/嵌套CV/独立测试集/真实标签…）→ HARD FAIL。这精准命中"用生成弱标签的公式又去算 AUC 得 0.994"的循环论证。修复=①用去泄漏后独立评估重算并写进结果 ②在 RESULTS.md 说明评估为何无泄漏，缺一不可。

> - **弱标签回流**：出现弱标签/伪标签生成却无"标签源特征未进评估"声明 → WARN（静态难判准，严格模式重点核）。

> - ⛔ **`LK=1` 必须先修再往下**；≥0.99 本身不算作弊、但必须举证（几乎零误报），快速模式也不跳过。

### Step 7.5: 数据输出完整性检查（⛔ 必须通过）

确保所有分析结果都保存为 JSON/CSV，供下一步 paper-figure 读取画图：

```bash

echo "=== 数据输出完整性检查 ==="

echo ""

echo "JSON 数据文件（paper-figure 的输入）："

ls -la figures/*.json 2>/dev/null || echo "  (无)"

echo ""

echo "TABLE 文件："

ls -la figures/TABLE_*.tex 2>/dev/null || echo "  (无)"

```

**⛔ MANDATORY：**

```bash

MISSING=0

# all_results.json 必须存在

if [ -f figures/all_results.json ] && [ -s figures/all_results.json ]; then

    echo "  ✅ figures/all_results.json"

else

    echo "  ❌ figures/all_results.json — MISSING or EMPTY"

    MISSING=$((MISSING+1))

fi

# 灵敏度分析数据（数模竞赛必须）

if [ -f figures/sensitivity_results.json ]; then

    echo "  ✅ figures/sensitivity_results.json"

else

    echo "  ⚠ figures/sensitivity_results.json — not found (required for sensitivity chapter)"

fi

echo "Missing: $MISSING"

```

**如果 ❌，必须回去补完再继续。**

**⛔ 不要在这一步生成 PDF 图表或 latex_includes.tex——那是 paper-figure 的职责。**

### Step 7.6: ⛔⛔ 能力清单最终验收（题型无关的"语义达标"闸，所有闸之后的总关）

前面的闸（数据摄入/交付/泄漏/约束）各管一段，这一步拿 comp-prob-analysis 产出的 `CAPABILITY_CHECKLIST.json` 做**逐项总验收**——确认"题目要求的每项能力都真做到了"，而不是只看图够页够文件在。这是防"任务降维"（要 NER/五元组却做成分类、要按事件簇却按行预警）的总关。

```bash

FAST_MODE=0; grep -q 'MH_FAST_MODE=1' CLAUDE.md 2>/dev/null && FAST_MODE=1

python _utils/capability_audit.py --checklist CAPABILITY_CHECKLIST.json --verdict CAPABILITY_VERDICT.json --fast $FAST_MODE

CAPA=$?   # 0=全达标 1=有未达标/缺结论(阻断) 2=无清单跳过

```

> - **machine 项**（judge=machine）：脚本按凭证自动核（如 delivery 项核 required_output 存在非空）。

> - **semantic 项 + 缺凭证的 machine 项**：脚本列进 `SEMANTIC_REVIEW_TODO.md`。**严格模式下你（考官角色）必须逐条判**——拿客观证据当锚（指出哪几行代码/哪个产物支撑该能力），对照 `criterion` 给 `verdict(PASS/FAIL)+evidence+note`，写进 `CAPABILITY_VERDICT.json`，再重跑本闸。⛔ 不许问自己"我做了吗"（会自证），要拿代码/产物硬证据核。

> - **`CAPA=1` 必须先修再往下**：能力项判 FAIL（如"按新闻行预警、未按事件簇"）说明题目要求的能力没做到或做降维了——回去补做，不是改结论。

> - **快速模式**：semantic 项缺结论降级为提示（不阻断），但 machine 项自动核与已判 FAIL 仍阻断。

> - ⛔ **天花板（诚实认知）**：本闸核不出"清单里根本没列的能力"——清单完备性取决于 comp-prob-analysis 阶段拆得全不全；semantic 判定靠考官 AI，与答题同源、有共同盲区。它**显著降低降维/漏做的漏网率，但不是万无一失**。清单尽量拆全、严格模式认真判，是它有效的前提。


## STEP_MANIFEST 产出声明

本步骤完成后，必须调用 `engine.step_manifest.write_manifest`（或经 bridge/common 等价入口）在工作区根目录写入 `STEP_MANIFEST.json`，至少包含：stepName / backend（含版本）/ config / inputFiles / outputFiles（含 SHA-256）/ commands / dependencies。质量门禁 `step_manifest` 将校验其存在性与完整性；缺失或无效将导致本步骤无法通过（fail）。

建议额外记录：依赖清单、求解器、运行时长、退出码。

## 关键规则

- **comp-code 只负责数据采集、统计分析、输出结果数据（JSON/CSV）。不画图。**

- **⛔ 禁止在分析代码中生成 PDF 图表。** 所有 `plt.savefig()`、`save_fig()` 调用都不应该出现在 comp-code 的代码里。如果分析过程中需要可视化验证结果，用 `plt.show()` 看一眼就行，不要保存 PDF。

- **图表 PDF 全部由下一步 paper-figure 生成。** paper-figure 会读取 comp-code 输出的 JSON 数据，按 recipe 系统生成高质量 PDF。

- **⛔ 求解器/优化器超时设置：** 不要设太短的超时（如 120 秒）。竞赛数据量可能很大，求解器需要足够时间。推荐设置：

  - 小规模问题（变量 <100）：`timeout=300`（5 分钟）

  - 中规模问题（变量 100-1000）：`timeout=600`（10 分钟）

  - 大规模问题（变量 >1000）：`timeout=1800`（30 分钟）

  - 超大/难解问题（变量 >5000 或强对称 MILP）：`timeout=3600`（1 小时，硬上限）

  - ⛔ **求解器 timeout 最多设到 3600（1 小时），不要更长**：引擎对整个步骤有 5400 秒（1.5 小时）"无输出超时"保护，求解器上限压在 1 小时以内可留足缓冲——即使求解器全程不打印，也是它自己先优雅超时退出（能拿到已有可行解），而不会被引擎当"卡死"粗暴杀掉丢结果。

  - 所有求解器都必须打印进度（每 30 秒输出一次当前最优解），防止无输出超时被系统杀掉

- 主输出文件：`RESULTS.md` + `figures/*.json`

- **⛔ 禁止整读结果 JSON（见 Step 4.5「数据自检铁律」）：** `figures/*_results.json` 常含全精度时序大数组，**绝不 `Read`/`cat`/`Grep` 全文**——只用 summarize 脚本拿摘要、用审计脚本拿结论。全精度数据照常写盘供 paper-figure 用，但不进 AI 上下文。

- 临时文件放 `_tmp/` 目录

- 代码必须能运行：写完必须执行验证

- 结果必须保存为 JSON/CSV 文件（供 paper-figure 读取画图）

<data_quality>

### Data generation quality (when generating/simulating data without user uploads)

When no user data is available and you need to generate or simulate data:

1. **Realistic ranges**: values must match the problem domain — e.g., temperature in °C not arbitrary 0-1, population in millions not random integers

2. **Meaningful patterns**: data should show the trends/relationships the model is designed to capture — e.g., if modeling seasonal demand, the data should have seasonal patterns

3. **Visualization-friendly**: design data so the resulting figures look informative and professional:

   - Avoid extreme outliers that compress the main data into a tiny range

   - Ensure different methods/groups have visible but not identical differences (5-20% gaps, not 0.1% or 500%)

   - Include enough data points for smooth curves (≥50 for line plots, ≥200 for distributions)

   - For method comparison: the proposed method should be best but not unrealistically dominant — other methods should have their own strengths on some metrics

4. **Consistent with problem statement**: all generated numbers must be traceable to the problem description — if the problem says "30 provinces", generate 30 data points, not 10

5. **Reproducible**: set random seeds (`np.random.seed(42)`) so results are deterministic

</data_quality>

- 代码要有注释（附录评审加分项）

- 数据路径用相对路径

- 基本异常处理，一个子问题失败不能全崩

- requirements.txt 必须生成

- 大文件用 Bash heredoc 分块写入

## 详细参考（按需 Read，不要一次全读）

主流程已在 Step 0–7.5。以下是按主题搬到 `references/checks/` 的深度参考，按 Step 4.5 的指引在每问跑完时打开：

| 触发场景 | Read 哪个文件 |

|---|---|

| 第 1 问开始前（仅 1 次）| `references/checks/_index.md` |

| 任何子问题跑完 | `references/checks/consistency.md` |

| 任何子问题跑完 | `references/checks/sanity_check.md` |

| 优化类子问题 | `references/checks/optimization.md`（含 5 层求解 + 结构性验证）|

| 预测类子问题 | `references/checks/prediction.md` |

| 评价类子问题 | `references/checks/evaluation.md` |

| 物理/几何题 | `references/checks/physical.md` |

| 写代码遇到具体 bug | `references/error_prevention_code.md`（按题型查防错条目）|

⛔ **每问的自检流程见 Step 4.5，不能跳过、不能合并、不能等到所有问跑完才统一自检。**

