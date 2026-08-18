---
name: comp-review
description: "数学建模竞赛·逻辑对抗复核。在编程实现后、论文撰写前，用独立视角挑'方向反/重复计量/外推过硬/漏变量/跨问矛盾'这类自查看不见的硬错。Use between comp-code and comp-paper."
argument-hint: [problem-context]
allowed-tools: Bash(*), Read, Grep, Glob, Agent
---

# 竞赛·逻辑对抗复核（独立视角，专挑自查盲区）

**为什么需要这一步**：建模/编程用的是同一个"心智模型"，如果它在建模阶段就把某个方向想反了（如把上界当下界）、或把某项算了两次，**自查时用的还是那个反的脑子，永远看不见**。这一步换一个独立视角，只干一件事——挑那五类"数值合法但逻辑错"的硬伤。

## ⚡ 开关说明 + FAST_MODE 二级保险（开头先跑）

⛔ **本步默认「关」**：后端 `_resolve_template` 默认把 comp-review 从步骤链里移除，**只有用户显式 `enable_comp_review=true` 时本步才会出现并执行**（这才是真省额度——不出现在链里就不启动进程）。所以你现在能读到这段，说明用户已选择开启。

```bash
# 二级保险：即便被开启，FAST_MODE 下仍跳过（速度优先场景），产占位不阻塞。
if grep -q 'MH_FAST_MODE=1' CLAUDE.md 2>/dev/null; then
  echo "⏭ FAST_MODE：逻辑对抗复核跳过。确定性闸(logic_audit/cross_problem_check)已在 comp-code 兜底。"
  printf '# 逻辑对抗复核\n\nFAST_MODE 跳过（省额度）。确定性逻辑闸仍在 comp-code 阶段跑过。\n' > COMP_REVIEW.md
  exit 0
fi
```
> ⛔ 本步是**唯一多花一次 AI 调用**的环节。默认关(后端移除)、开启后 FAST_MODE 仍可跳。跳过时确定性闸(logic_audit/cross_problem_check)已在上一步兜底，不影响主流程。

## 输入（只读摘要，禁整读大 JSON）

- `PROBLEM_ANALYSIS.md`（题面/逐句表/硬约束）、`DATA_FACTS.json`（数据事实台账）
- `MODELING_REPORT.md`（假设/`LOGIC_CONTRACT_MACHINE`/`CROSS_PROBLEM_LEDGER`）
- `RESULTS.md` + `AUDIT_REPORT.md`（前面各闸的结论）
- `figures/*_results.json` 用 `_utils` 下的 summarize 或 `Grep`/`Read` 局部看，**⛔ 禁 `cat` 整包大 JSON**（吃光 context）

## Step 1: 先看确定性闸的既有结论（不重复劳动）

```bash
# logic_audit / cross_problem_check 已在 comp-code 阶段跑过，先复用它们的裁定作锚点
[ -f AUDIT_REPORT.md ] && grep -nE "外推|特征完整性|重复计量|跨问|矛盾|❌|⚠" AUDIT_REPORT.md | head -30
```

## Step 2: 逐条对撞五类缺口（核心，用证据说话）

对每一类，找**具体代码行/具体数值**当证据，不泛泛而谈：

1. **方向/界反没反**：核对 `LOGIC_CONTRACT_MACHINE.bounds` 声明的上/下界与代码实现是否一致。凡有删失/封顶/反解，代入观测值验证不等号方向。（这是确定性闸抓不到、最需要独立视角的一类）
2. **重复计量**：任何"总量=A+B"，查 A 的拟合/标定是否已吸收 B（如截距用含某分项的总量拟合、又显式加该分项）。
3. **外推口吻过硬**：预测点落在 `DATA_FACTS` 观测区间外的，正文是否用了确定性口吻当"数据结论"（应标"情景模拟、需现场标定"）。
4. **漏真实变量**：`DATA_FACTS` 里 `role=observed` 的关键变量，是否都进了模型；被当"不重要"丢掉的要质疑。
5. **跨问矛盾**：某问算出的关键结论（如峰值/边界）是否与另一问的优化约束/结论冲突。
6. **任务理解 vs 题目原文（⛔ 最该由你独立视角兜的一类）**：拿 `PROBLEM_ANALYSIS.md` 的**关键概念对齐表**和 `MODELING_REPORT.md` 的**目标/约束原文溯源**，逐条核对——建的目标函数/约束/关键量，和题目**原句**要的是不是同一件事？重点抓：求 A 做成了求 B（如覆盖宽度→面积）、最优化方向反（min↔max）、约束理解反、关键量物理含义错、漏做某个明确要求。⛔ **这是"赛题读歪"唯一的独立防线**——下游所有确定性闸都只核"是否忠于建模者的理解"，核不了"理解本身对不对"，只有你带着题目原文重看才可能发现。发现"任务读歪/目标搞错"属 **fatal**（方向全错，回炉重来）。

⛔ **诚实认知（天花板）**：本复核 AI 与答题同源，有共同盲区，**显著降漏网率但非万无一失**（尤其"任务理解"这类：你也可能和答题时一样误读同一句话）。机器可判的部分已由 logic_audit/cross_problem_check 确定性拦截，本步只兜"确定性查不了的语义残余"。发现存疑处要给出"哪行代码/哪个数/哪句原文"支撑，不做无证据的断言。机器可判的部分已由 logic_audit/cross_problem_check 确定性拦截，本步只兜"确定性查不了的语义残余"。发现存疑处要给出"哪行代码/哪个数"支撑，不做无证据的断言。

## Step 3: 产出裁定（人读 + 机器读）

当通过只读审稿子 Agent 执行时，子 Agent 仅在会话回复中提供报告与 JSON；主 Agent 负责原样、受控地写入以下工作区文件，并在最终复审时登记该会话证据。不要要求只读子 Agent 直接编辑文件。

```bash
# 人读报告
cat > COMP_REVIEW.md <<'EOF'
# 逻辑对抗复核报告
（逐条：问题描述 / 严重性(fatal|major|minor) / 定位(文件:行或数值) / 证据 / 建议）
EOF
```

机器可读裁定 `COMP_REVIEW_VERDICT.json`：
```json
{"findings":[
  {"category":"bound_direction|double_count|extrapolation|missing_feature|cross_problem",
   "severity":"fatal|major|minor","where":"calibrate.py:L692 或 Q1峰值","evidence":"...","fix":"..."}
],"fatal_count":0}
```

## Step 4: 硬门禁（⛔ 有 fatal 不许放行）

```bash
FATAL=$(python3 -c "import json;d=json.load(open('COMP_REVIEW_VERDICT.json'));print(d.get('fatal_count',0))" 2>/dev/null || echo 0)
if [ "$FATAL" -gt 0 ]; then
  echo "❌ 逻辑对抗复核发现 $FATAL 处致命逻辑错 — 必须回 comp-modeling/comp-code 修正后重跑，不许进论文撰写。"
  echo "   (fatal 类：方向反、同一项算两次、跨问硬矛盾——这些会系统性歪曲结论)"
else
  echo "✅ 逻辑对抗复核通过（无 fatal；major/minor 见 COMP_REVIEW.md，写论文时注意）。"
fi
```
> - `fatal`（方向反/重复计量/跨问硬矛盾）= 退出前必修，回炉重跑。
> - `major/minor`（外推口吻、可疑假设）= 不硬拦，但必须在论文里如实标注为"情景模拟/假设"，禁确定性口吻。
