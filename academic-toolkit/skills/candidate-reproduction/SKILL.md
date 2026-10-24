---
name: candidate-reproduction
description: "候选交付复现：按引擎生成的复现计划在独立目录重跑候选冻结 recipe，逐目标核对结果并产出复现报告。触发词：候选复现、复现计划、candidate reproduction、冻结 recipe 重跑。"
argument-hint: [reproduction-plan]
allowed-tools: Bash(*), Read, Grep, Glob
---

# 候选交付·复现（冻结 recipe 的真实重跑）

**为什么需要这一步**：promotion 只冻结候选的输入、产物、谱系与命令 recipe，不重跑生产步骤。交付工作流必须证明「同一份冻结 recipe 在干净目录里仍能产出同一字节」，否则候选只是历史文件快照。本步由引擎分派，输出 `REPRODUCTION_REPORT.json`；没有真实重跑（no-op、复用旧字节、手写报告）一律不算复现。

## 输入（引擎已生成，不要手改）

- `REPRODUCTION_PLAN.json`：工作区根目录，引擎在 `start --candidate` 时写入。
  - `candidate_id`：本次交付候选。
  - `targets[]`：每项含 `target`（工作区相对路径）、`recipe_id`、`spec`（候选冻结 recipe 的原样副本）。
  - 同一 `recipe_id` 可能覆盖多个 target；**一条命令只跑一次**。
- 会话 `context` 返回的 `delivery_candidate_id` 与 plan 内 `candidate_id` 必须一致；不一致时停止并报告，不要自行猜测。

## 执行（唯一合法入口）

```bash
python -m engine.workflow_cli session reproduce \
  --session .engine/sessions/<attempt_id>.json \
  --plan REPRODUCTION_PLAN.json \
  --candidate <candidate_id>
```

引擎内部完成（不要手工重做其中任何一步）：

1. 从候选冻结数据读取 recipe 与 target 冻结 sha；plan 的 recipe 与候选冻结值不一致时直接拒绝。
2. 每个 recipe 新建 `_reproduction/<candidate_id>/<recipe_hash>/<attempt_id>/<submission_id>/`；`submission_id` 每次调用新生成，**重试也不会复用旧目录**。
3. 复制该 recipe 的冻结输入（含 `inputs_snapshot` 中的脚本/配置）到复现目录并逐项校验 sha。
4. 非 `mutates` 输出断言运行前不存在；`mutates` 输出允许存在，但 before 必须等于候选冻结的输入版本。
5. 绝对路径 argv token 映射到复现目录；相对 token 原样保留；工作区外绝对路径拒绝。
6. 以 `no_cache=True` 真实执行；运行后逐 target 用 `outputs_snapshot[mapped_path]` 对候选冻结 sha，写入 `payload["reproduction"]`（原始 recipe、`recipe_sha256`、`targets[].mapped_path`、`hash_match`、`fresh_outputs`）。
7. 生成 `REPRODUCTION_REPORT.json`。**报告由命令生成，禁止手写或改写。**

## 失败语义（如实报告，不绕过）

| 情况 | 处理 |
|---|---|
| 命令非零退出 / 超时 | 保留 stderr 摘要，报告 failed；修的是 `recipe` 或环境，不是报告 |
| target 哈希不匹配 | 报告 failed，不得把 `hash_match` 改成 true |
| 输出在运行前已存在 | 拒绝执行；不能把旧字节冒充复现产物 |
| `mutates` 且运行前后相同 | `fresh_outputs=false`，按未复现处理（no-op 不算复现） |
| 输入与冻结 sha 不一致 | 拒绝执行；先查候选冻结后是否被改写 |

重试只通过再次 `session reproduce`（自动新目录）；不得删除/复用 `_reproduction/` 旧目录，也不得改动候选根文件。候选根被改写会让 `candidate_frozen` 门失败，正确路径是新建候选。

## 退出判据（Verification）

- [ ] `REPRODUCTION_REPORT.json` 存在且 `status="succeeded"`
- [ ] plan 中每个 target 均出现在 `targets[]`，`hash_match=true`，且 `fresh_outputs=true`
- [ ] 复现操作是 `candidate-reproduction` 步骤内、带 `payload["reproduction"]` 的 command 操作；普通 `commands.execute` 不计入
- [ ] 没有手写/篡改报告，没有复用 `_reproduction/` 旧目录

`candidate_reproduction` 就绪门只认上述真实操作；本步失败时如实 `finish` 让门禁报错，不得用补录或空命令蒙混。

## 常见合理化（Common Rationalizations）

| 合理化 | 现实 |
|---|---|
| "候选文件还在，复制一份报告就行" | 报告是执行事实的摘要，不是承诺书；门禁核对 `payload["reproduction"]` 与真实 `outputs_snapshot`。 |
| "命令没写出新文件，但旧文件哈希对得上" | 非 mutates 输出运行前必须不存在；旧字节按 retained 处理，`fresh_outputs=false`。 |
| "这次目录里有旧产物，直接用" | 每次 `submission_id` 新生成；旧目录存在即拒绝，重试不得复用。 |
| "哈希差一点，手改报告里的 sha" | 报告由引擎生成；手改即伪造证据，门禁与审计会按未复现处理。 |
