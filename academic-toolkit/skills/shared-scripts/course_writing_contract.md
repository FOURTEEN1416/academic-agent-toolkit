# Course/Humanities 写作系共享契约（唯一真源）

课程论文（course-paper）、课程报告（course-report）、课程规划（course-plan / course-report-plan）、人文社科（humanities-plan / humanities-write）六技能共享的契约块单源文件。

- 双副本：`skills/_utils/course_writing_contract.md` 与 `skills/shared-scripts/course_writing_contract.md` 逐字节一致（`test_dual_copy_consistency` 守护），改任一侧必须同步另一侧。
- 按需加载：先取本目录，再用 sed 取本步骤实际需要的 tag 节，禁止整篇 cat 挤占注意力预算。

```bash
RULES="skills/_utils/course_writing_contract.md"
[ -f "$RULES" ] || RULES="academic-toolkit/skills/_utils/course_writing_contract.md"
[ -f "$RULES" ] || RULES="../../skills/_utils/course_writing_contract.md"
# 示例：取反 AI 痕迹铁律一节
sed -n '/<anti_ai_trace_rules>/,/<\/anti_ai_trace_rules>/p' "$RULES"
```

<anti_ai_trace_rules>
## ⛔⛔⛔ 反 AI 痕迹写作铁律（Word 模式必须遵守，违反等同失败）

Word 输出最常被识别为「AI 写的」就是因为下面这 6+1 条没遵守。优先级凌驾于章节模板和字数要求。

1. **禁止 markdown bullet/编号列表（`-`、`*`、`1.`、`2.`）作为正文叙述。** 含「问题一/二/三」「需求一/二/三」「研究目标」「创新点」「贡献点」「拟解决问题」「关键问题」「核心模块」「子任务」「待解决问题」等场景必须用连贯段落，不许分点罗列。

   - ❌ 错（课程论文示例，最典型 AI 痕迹）：

     ```
     本文需依次解决三个递进的子问题：
     - 问题一：针对 AI 生成图像，建立...
     - 问题二：利用问题一的模型...
     - 问题三：将模型拓展到视频...
     ```

   - ❌ 错（课程报告示例）：

     ```
     本系统需依次实现三个核心功能：
     - 功能一：用户登录与鉴权…
     - 功能二：数据采集与持久化…
     - 功能三：可视化报表生成…
     ```

   - ✅ 对（连贯段落 + 过渡词，课程论文）：`本文需依次解决三个递进的子问题。**首先**，针对 AI 生成图像，建立无参考综合质量评估指标体系……；**其次**，利用第一问的模型对 8 张真实图像进行完整评估与分级……；**最后**，将模型拓展到视频时序维度，量化帧间运动连续性、内容一致性与闪烁稳定性。`

   - ✅ 对（连贯段落 + 过渡词，课程报告）：`本系统需依次实现三个核心功能。**首先**，用户登录与鉴权模块基于 JWT 实现…；**其次**，数据采集层通过…；**最后**，可视化报表模块基于 ECharts…。`

   - ✅ 替代（行内括号编号）：`本文需依次解决三个递进的子问题：（1）针对…；（2）利用…；（3）将模型拓展到…。`

   - bullet **唯一允许场景**：输入清单 / 软件依赖 / 接口定义 / 测试用例表 / 评价指标定义 / 模型假设条目 / 参考文献列表 / 作者贡献声明，正文叙述一律禁止。

2. **加粗写作 `**标签**：内容`，不要 `**标签：**内容`。** 把冒号包进 `**` 里 docx 引擎正则匹配不到，会留下孤立 `**` 残留。

   - ❌ `**关键词：** AI 生成图像质量评价；...`
   - ✅ `**关键词**：AI 生成图像质量评价；...`

3. **每段至少 3-5 句话。** 1-2 句的短段落是 AI 痕迹；要么扩写到 3 句以上，要么并入相邻段落。

4. **连续段落不能以相同句式开头。** 三段都「本文…」「本系统…」开头必须改，交替用「首先」「为此」「在此基础上」「针对…」「不同于…」「另一方面」等多样化连接词。

5. **图号必须显式引用，但句式换着来（标准优秀论文口径）。** 每张图/表都要点名「图 N」让读者对上号（硬规范，别为避免套路删图号）。要禁的是**"图 X 展示了……从图中可以看出……"这种图作主语+空话的单调流水账**，不是禁止一切图作主语。相邻两图引用句式必须不同，在括号旁注（首选）／句首带出／动词引导／图作主语（带实质结论时允许）／后置印证间轮换。

   - ❌ `图 3 展示了三种算法的收敛曲线。从图中可以看出，遗传算法收敛最快。`（图作主语 + 空话）
   - ✅ 括号旁注：`遗传算法在前 50 代即接近全局最优（图 3），收敛速度显著优于粒子群与模拟退火。`
   - ✅ 图作主语（带实质结论）：`图 3 对比了三种算法的收敛轨迹，遗传算法在第 50 代即逼近全局最优，较粒子群提前约 30 代。`

6. **去掉 AI 写作口头禅。** 少用「值得注意的是」「综上所述」「这一发现表明」「随着…的发展」「在…的背景下」「具有重要意义」。「研究表明」「多项研究证实」必须紧跟具体引用号 [N]，不能空喊。

7. **（人文社科附加）理论/引文是论据不是主语。** 段落不要以「福柯认为」「如某某所说」开头堆砌；先提出你的论点 → 引文/理论作支撑 → 推论。

⛔ **无图表分支**特别规则：

- 如果 PAPER_PLAN.md 是「无图表分支」，**禁止写任何 `![](figures/...)` 标记**
- **禁止写「如图 X 所示」**
- 所有论点用文献引用支撑
</anti_ai_trace_rules>

<figure_manifest_output>
## ⛔⛔⛔ FIGURE_MANIFEST（机器可读对账清单，必须输出）

**写完上面的图表清单后，在产出文档（PAPER_PLAN.md 等规划文档）的**最后**追加一个机器可读的清单区块。下游 paper-figure / paper-figure-drawio / 写作 SKILL / workflow_engine.py 都按此清单对账。少一张就触发 AUTO-RECOVER。**

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
- **⛔⛔ 图名必须以 `fig_` 或 `tikz_` 前缀开头**（问题「规划了图却没生成」的根因）：数据图/流程图/架构图一律 `fig_xxx`，TikZ 几何图一律 `tikz_xxx`。**严禁用 `image2`、`图2`、`chart1`、`示意图` 这类没有前缀的名字**——下游对账脚本按 `fig_`/`tikz_` 前缀在 manifest 章节里抓图名，不带前缀的会被直接漏掉，导致该图静默不生成。图名用小写英文+下划线，见名知意（如 `fig_turbidity_trend`、`fig_flow_q1`）。
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
    # ⛔ 校验 manifest 里的图名前缀：抓 BEGIN..END 之间的列表项，凡不以 fig_/tikz_ 开头的报警
    START=$(grep -n '<!-- BEGIN FIGURE_MANIFEST -->' "$PLAN_FILE" | head -1 | cut -d: -f1)
    END=$(grep -n '<!-- END FIGURE_MANIFEST -->' "$PLAN_FILE" | head -1 | cut -d: -f1)
    BAD=$(sed -n "${START},${END}p" "$PLAN_FILE" | grep -E '^[[:space:]]*-[[:space:]]+' | grep -vE '^[[:space:]]*-[[:space:]]+(fig_|tikz_)' | sed -E 's/^[[:space:]]*-[[:space:]]*//')
    if [ -n "$BAD" ]; then
      echo "❌ 以下图名缺少 fig_/tikz_ 前缀，会被下游对账漏掉、导致图不生成，必须改名："
      echo "$BAD" | sed 's/^/    · /'
    else
      echo "✅ 所有图名前缀合规（fig_/tikz_）"
    fi
  else
    echo "❌ FIGURE_MANIFEST 区块缺失，必须按上面格式追加（即使无图也要写 ALL=0）"
  fi
fi
```
</figure_manifest_output>

<figure_manifest_reconcile>
## ⛔ FIGURE_MANIFEST 对账（写完正文必跑，规划了几张就必须嵌入几张）

`PROD_DOC` 填本技能最终产物文档名（course-paper→`COURSE_PAPER.md`，course-report→`COURSE_REPORT.md`）。

```bash
echo "=== FIGURE_MANIFEST 对账 ==="
PROD_DOC="COURSE_PAPER.md"   # 按本技能产物改名
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
        elif ! grep -qE "${name}\.(png|pdf)" "$PROD_DOC" 2>/dev/null; then
            echo "❌ MANIFEST: $name 文件存在但 $PROD_DOC 未引用"
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
</figure_manifest_reconcile>

<paper_stage_audit>
## ⛔ 通用 paper-stage 审计（所有写稿步骤共用，跨工作流）

写完正文 / 编译前必须跑一次通用审计，独立于 PROBLEM_FACTS.json 是否存在：

```bash
# 通用 paper 审计：
#   [13] 正文结论与 results.json 一致（防"最优解 X 但正文写 Y"）
#   [14] 事件源归属（防"凭变量名脑补撞击 / 命中 / 拦截"）
# 即使没 PROBLEM_FACTS.json（普通学术 / 课程论文 / 人文社科），也会以"简化模式"跑独立审计。
if [ -f _utils/facts_audit.py ]; then
    PYTHON=""; for _c in "$MH_PYTHON" python python3; do [ -z "$_c" ] && continue; if $_c -c "import sys" >/dev/null 2>&1; then PYTHON="$_c"; break; fi; done; [ -z "$PYTHON" ] && PYTHON=python
    $PYTHON _utils/facts_audit.py --stage paper 2>&1 | tee -a AUDIT_REPORT.md
    PRC=${PIPESTATUS[0]}
    if [ "$PRC" = "1" ]; then
        echo "❌ 通用 paper-stage 审计未通过 — 必须按上面提示修正正文 / results.json 后重新跑"
    fi
fi
```
</paper_stage_audit>
