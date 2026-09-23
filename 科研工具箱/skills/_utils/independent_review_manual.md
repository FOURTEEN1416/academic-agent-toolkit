# 独立评审操作手册（统一 · 驱动协议层 · 宿主无关）

> 读者：当前驱动本项目的 Agent。
> 适用：任何技能或步骤要求「外部审稿 / 外部 LLM 评审 / `reviewer_client` / 审稿循环 / 视觉审」时，
> 一律按本手册执行。外部 LLM API 审稿通道已于 2026-09-23 全线退役：
> **零 APIKey、零网络调用、不读取任何密钥。**
> 方法论：换驱动，不拆机制——技能的流程骨架与质量门保持不变，只置换评审的执行者。

## 四条铁律

1. **独立性**：评审者与实现者必须上下文隔离。评审上下文不得携带实现过程的沉没成本
   （自己写的稿、自己调的参、自己做的取舍）。判独立的标准只有一条：
   **评审者能否毫无包袱地毙掉这份产物。**
2. **只评不改**：评审者只产出 score / verdict / 弱点清单 / 最小修复项，不直接修改产物；
   一切改动由执行 Agent 落实。
3. **证据全留**：任务卡、verdict、评审 raw 全文逐字落盘，不摘要、不截断——这是 L3 审计证据链本体。
4. **如实记录驱动方**：每轮评审把驱动方式写进状态/证据文件；缺席降级必须附原因。
   禁止把自审伪装成独立评审。

## 标准流程（四步）

### ① 写评审任务卡

落盘 `review_tasks/<任务名>.task.md`：

```markdown
# Review Task — <任务名/轮次>

## Role
You are a senior reviewer in this domain. 评审上下文独立于实现窗口：只评不改。

## Input
[完整待评内容或其落盘路径；多轮任务附上一轮 verdict 摘要与本轮修改清单]

## Output contract — 回写 review_tasks/<任务名>.verdict.md
1. Score this work 1-10
2. List remaining critical weaknesses (ranked by severity)
3. For each weakness, specify the MINIMUM fix
4. State clearly: is this READY? Yes/No/Almost

Be brutally honest. If the work is ready, say so clearly.
```

### ② 派发独立评审

用你可用的任何方式获得一个**独立上下文**来执行任务卡：独立子代理、独立会话、独立窗口、
另一模型均可——宿主形态不限，满足铁律 1 即算合格。
派发物 = 任务卡路径；回执 = verdict 文件路径。**评审完成以 verdict 文件落盘为准。**

### ③ 收 verdict 并落证据

`review_tasks/<任务名>.verdict.md` 固定五段：
Score (1-10) / Verdict (ready|almost|not ready) / Weaknesses（按严重度排序）/
Minimum fixes / READY 判定。
视觉类任务把 Input 换成图件路径与对应检查单，verdict 五段格式不变。

### ④ 缺席降级（最后手段）

确实无法获得任何独立上下文时，才允许当前执行 Agent 自审。自审必须：

- 先做**负面对照**：以对手审稿人身份写下"第一枪打哪里"，再正式评分；
- 在 verdict 头部标注 `driver: self-fallback` + 一句降级原因；
- 连续 self-fallback 达 2 轮及以上时，在最终交付报告中显著声明"本产物未经独立评审"。

## 与技能的关系

- `auto-review-loop`（多轮审稿循环）已内置本手册：每轮任务卡/verdict 进 `review_tasks/`，
  驱动方记入 `REVIEW_STATE.json` 的 `review_driver`（`independent` / `self-fallback`）。
- 视觉审核三工具由 `tools/host_visual_review.py` 承载同一任务卡制（`visual_review_tasks/`）。
- 其余技能文中出现 `reviewer_client.py` / 外部审稿 API / APIKey 配置等字样时，
  **一律以本手册为准**：不配置密钥、不发起网络调用、按上述四步执行。
