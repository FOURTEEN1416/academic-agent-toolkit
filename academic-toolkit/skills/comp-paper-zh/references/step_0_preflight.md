## Step 0: Backup + resume check + upstream validation

本文件是 `skills/comp-paper-zh/SKILL.md` Step 0 的执行细则；触发条件与放行判据见 SKILL.md「Workflow」。

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
