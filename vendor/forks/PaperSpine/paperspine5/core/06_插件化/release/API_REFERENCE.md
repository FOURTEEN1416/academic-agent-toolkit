# 本地 Agent / REST 参考

普通用户从 [快速开始](USER_GUIDE.md) 操作 Web。本参考供集成者，不要求用户手写协议。Web 与 MCP 必须使用同一个 `--profile-root`。当前服务只绑定 loopback，以启动进程给出的本地 principal/session/reviewer 上下文处理身份；它不是互联网多用户认证服务，不要端口转发或公网暴露。

`GET /api/v1/capabilities` 返回当前公开命令。`GET /api/v1/tasks/{task_id}` 读取最新任务；每次新写入使用返回的 `task_version` 作为 `expected_version`。每个逻辑操作保留唯一 `command_id`；丢失响应时原请求原样重放，同 ID 改内容会拒绝。请求 body 不接受 actor/principal/session 身份。

| 目的 | MCP 工具 | REST |
| --- | --- | --- |
| 创建或恢复 | paperspine_open_task | POST /api/v1/tasks |
| 查看任务 | paperspine_get_task | GET /api/v1/tasks/{task_id} |
| 等待同任务更新 | paperspine_wait_for_task_change | 宿主只读 MCP 等待；Web 保存仍走原接口 |
| 材料只读授权 | paperspine_authorize_materials | POST /api/v1/tasks/{task_id}/materials |
| 登记已完成的研究等阶段 | paperspine_commit_milestone | POST /api/v1/tasks/{task_id}/milestones |
| 证据绑定 | paperspine_bind_evidence | POST /api/v1/tasks/{task_id}/evidence-links |
| 请求用户选择 | paperspine_request_decision | POST /api/v1/tasks/{task_id}/decisions |
| 用户确认 | 无，Agent 不可代确认 | POST /api/v1/tasks/{task_id}/decisions/{decision_id}/resolution |
| 发布已登记成果 | paperspine_publish_artifact | POST /api/v1/tasks/{task_id}/artifacts |
| 独立审核 | paperspine_submit_review | POST /api/v1/tasks/{task_id}/reviews |
| 解决审核问题 | paperspine_resolve_finding | POST /api/v1/tasks/{task_id}/findings/{finding_id}/resolution |
| 准备已有交付包 | paperspine_prepare_delivery | POST /api/v1/tasks/{task_id}/delivery |
| 恢复原操作 | paperspine_recover_operation | POST /api/v1/tasks/{task_id}/recovery |
| 本地下载 | 使用 Web 链接 | GET /api/v1/tasks/{task_id}/artifacts/{artifact_id}/download |

创建 body 示例（REST）：

```json
{"command_id":"example-open-1","expected_version":0,"payload":{"mode":"open","title":"本地教学示例"}}
```

MCP 命令工具接受 `request` 对象，包含当前 `schema_version`、`task_id`、`command_id`、`expected_version` 和 `payload`；读取/恢复工具按 tools/list 参数调用。具体请求及版本以安装内 MCP tools/list 为准。合同随包位于 `03_联合开发/contracts/`，供集成者查阅，不是普通用户操作清单。

恢复 body 是 `operation_id`、`expected_version` 和可选 `confirm_no_effect`。先读任务 `recovery.next_action`：`retry` 才可安全重试；`confirm_no_effect` 必须由真实用户核对后通过 Business 确认。`reconnect` 表示重连读取，`retry_download` 表示重试已有下载，`check_request` 表示检查输入。不要按错误种类单独推断安全性，网络超时也可能结果未知。

事件读取：`GET /api/v1/tasks/{task_id}/events` 返回 JSON；Accept 为 `text/event-stream` 时返回有序事件快照和 `snapshot-end`，不是持续订阅。支持 `Last-Event-ID` 游标。页面定时读任务以更新进度。

`CommitMilestone` 记录已有工作，不运行研究。`PublishArtifact` 可导入同任务已授权文件夹内的文件，见下文。`PrepareDelivery` 检查已有交付包，不自动生成论文或 ZIP。生成论文、图件和 ZIP 仍由 Agent 完成，核心只导入并核验实际字节。


## 导入 Agent 实际生成的本地成果

宿主读取公开任务的 `workspace_root`，将本任务产物写入其 `paper/`。发布时使用 `source.relative_path`，如 `paper/manuscript.tex`，不需要 grant_id。外部输入目录仍须通过 materials 接口取得本任务的有效只读授权；相对路径不能包含绝对路径、父目录跳转、盘符、符号链接、junction 或硬链接。导入在本机进行，不上传，源文件保留。Windows 相对路径分隔使用 `/`。

发布 TeX 的 payload 示例（省略公共 command_id/expected_version）：

```json
{"artifact_id":"teaching-note-v1","artifact_type":"tex","stage":"draft","source":{"relative_path":"paper/note.tex"}}
```

核心自己计算 sha256、size、media_type，并将完整文件复制到本任务输出区、交给既有成果权威登记后发布。无需手填 hash。已有旧登记仍支持原 sha256/media_type 形式。相同 command_id 原请求重放不重复发表事件；相同 artifact_id 换字节会冲突，新版本请用新 artifact_id。

原创样例演练：复制 examples/local-demo 到安装外的练习文件夹，实际核对 CSV，登记 research 里程碑 summary（平均数 6、范围 8，人工构造，不是研究发现）。通过 decisions 请求 motivation 和 figure，用户在 Web 确认；发布 note.tex 为 tex、values.svg 为 figure。使用 Agent 的本地压缩工具，把 README.md、measurements.csv、note.tex、values.svg 打包成 teaching-package.zip，发布为 delivery_package。用独立审核者身份实际核对这些文件后提交 review，再以 `{"scope":"local_delivery","required_formats":["tex","figures"]}` 准备交付。用户点 Web 的下载链接并解压核对。这是可编辑教学材料的交付演练，不是完整 PDF/Word 论文或期刊投稿示例。

请求选择的 payload 示例：

```json
{"decision_id":"demo-motivation","task_version":3,"decision_type":"motivation","prompt":"用哪个教学目的解释这些人工构造值？","allowed_decisions":[{"option_id":"mean","label":"解释平均数"},{"option_id":"spread","label":"解释范围如何补充平均数"}],"scope_refs":["demo-research"],"requested_by_command_id":"ask-motivation","expires_at":null}
```

把 task_version 改为刚读取的版本。Agent 只请求选择，不提交 resolution。研究阶段 body 的 payload 是 `{"stage":"research","summary":"实际核算与局限说明","artifact_ids":[]}`，不是启动模型指令。

审核 payload 形状：`{"review_id":"demo-review","reviewed_artifact_ids":["teaching-note-v1","values-v1"],"reviewer_id":"independent-reviewer","findings":[]}`。只有实际独立读过这些文件才能提交空 findings；存在问题时填写 finding_id/severity/message，并修订、解决问题。服务的 reviewer_id 必须与启动配置一致，身份不等于审核证据。
