# Publication Cycle 主流程整合接口

## 目的

该接口把 PaperSpine + PaperFigure 的规范主稿继续交给 PaperSpine Publication Cycle，同时明确区分三件事：规范主稿完成、目标投稿包完成、外部投稿获授权。前两项由本地证据决定；第三项不在本接口授权范围内。

## 版本与权威

- 整合状态：`integration-state` 1.2。
- 生命周期快照：`figure-workflow` 1.1，共八段证据链。
- 下游接口：`paperspine.publication-cycle.interface` 1.0。
- 请求/结果合同：`paperspine.publication-cycle.invoke-request` / `paperspine.publication-cycle.result` 1.0。
- `integration_state.json` 保存最近操作与历史回执；每次请求和结果另存为不可混淆的独立 JSON 文件。

`canonical_paper_ready` 只证明规范主稿和 PaperSpine 五维 readiness 完成。只有 `assemble` 成功且回执含 `signals.submission_bundle_ready=true`，整合状态才进入 `awaiting_external_authorization`，`deliverables.bundle_ready/ready` 才为真。

## 五个操作

| 操作 | 必需输入 | 输出 | 成功后的整合状态 |
|---|---|---|---|
| `profile_check` | `profile` | 无 | `target_profile_ready` |
| `assemble` | `profile`, `plan` | `directory` | `awaiting_external_authorization` |
| `rebuttal_check` | `review_round` | 无 | `rebuttal_validated` |
| `rebuttal_render` | `review_round` | `directory` | `rebuttal_materials_ready` |
| `transfer_plan` | `origin_profile`, `destination_profile`, `transfer_request` | `directory` | `destination_rebuild_ready` |

`transfer_plan` 只说明差异与重建计划就绪；实际转投必须回到目标研究、计划、写作、格式和审计主流程。返修材料就绪也不授权重投。

## 调用面

CLI：

```powershell
python 03_联合开发/scripts/paperspine_figure.py publication-cycle-describe <integration_job.json>
python 03_联合开发/scripts/paperspine_figure.py publication-cycle-invoke <integration_job.json> <operation-request.json>
```

Loopback HTTP：

```text
GET  /api/publication-cycle
POST /api/publication-cycle
```

POST body 是简化的 UI/宿主请求：

```json
{
  "operation": "assemble",
  "inputs": {"profile": "profiles/carbon.json", "plan": "plans/carbon.json"},
  "outputs": {"directory": "paper/publication/carbon-v1"},
  "options": {"write_report": true}
}
```

协调器验证所有路径仍在 `project_root` 内，再转换为下游 invocation JSON 所需的相对路径。省略必需输出目录时，系统在论文输出目录下分配新的时间戳目录；不预先伪造成功产物。

## 前端

第五个工作页“投稿循环”提供五个一一对应的真实按钮。按钮调用 `POST /api/publication-cycle`，完成后重新读取权威快照，并显示完整结构化回执。规范主稿完成前按钮禁用。页面明确没有自动投稿按钮。

## 权限边界

整合 bridge 同时检查 `signals.external_action_authorized` 和 `authority_boundary.external_action_authorized` 必须为 `false`。任何不安全或版本不兼容的回执都会使边界调用失败。外部提交、重投、费用、许可和作者专属事实始终需要用户另行确认或授权。
