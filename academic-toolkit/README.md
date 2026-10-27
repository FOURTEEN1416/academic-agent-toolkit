# academic-toolkit

本套件为**任意驱动 Agent**提供 6 大能力域的科研技能、工具、工作流状态、质量门禁和本地证据链。它不提供新的 UI，也不启动或替代 Agent runtime。

## 当前入口（宿主无关）

从共享根（**git clone 后的仓库根**）由任意 Agent 读取根 `AGENTS.md` 驱动。

```powershell
cd academic-toolkit
python -m engine.workflow_cli boot
python -m engine.workflow_cli probe
python -m engine.workflow_cli start --template comp_cumcm --workspace workspaces\demo --params '{"language":"zh","agent":"acat-agent"}'
python -m engine.workflow_cli next --wf <workflow-id> --db workspaces\demo\.engine\workflow.sqlite
```

`next` 返回执行会话；用 `session run`/`session write` 记录真实命令与产物，再由 `session finish` 一次验收推进；旧 `complete --evidence` 仅兼容外部集成。

缺工具时：`python -m engine.workflow_cli forge --tool <name> --purpose "..."`。
自举技能：`skills/agent-bootstrap/`；铸造技能：`skills/tool-forge/`。

工作流默认数据库在 `<workspace>/.engine/workflow.sqlite`。每一步的执行证据在 `<workspace>/.engine/evidence/`，运行日志在 `<workspace>/.engine/logs/`。操作审计可生成到 `<workspace>/OPERATION_AUDIT_REPORT.json`；竞赛最终交付审计的预审报告写入 `<workspace>/reports/<workflow_id>/AUDIT_REPORT.json`（根 `<workspace>/AUDIT_REPORT.json` 保留同内容预审快照）；`ready` 结论写入 `<workspace>/DELIVERY_REPORT.json` 并按 `release_id` 归档到 `<workspace>/releases/<release_id>/`，两者不会互相覆盖：

```powershell
python -m engine.workflow_cli audit --workspace workspaces\demo
```

## 本地 Smoke Check

在本套件目录运行：

```powershell
python -m engine.workflow_cli boot
python -m engine.workflow_cli probe
python -m engine.workflow_cli caps
pytest -q
```

`boot/probe/caps` 只检测协议与本机依赖；`pytest` 验证离线的工作流、门禁、证据、文档读取与工具行为。它们不证明外部 API、外部集成或子 Agent 在当前账户已真实可用。

## 审稿证据

审稿人和视觉审查角色只读。结论由主 Agent 受控写入：

- `COMP_REVIEW.md` 与 `COMP_REVIEW_VERDICT.json`
- `VISUAL_REVIEW.md` 与 `VISUAL_REVIEW_VERDICT.json`
- `EDITOR_CHANGELOG.md`
- `FINAL_REVIEW.md`、`FINAL_REVIEW_VERDICT.json`
- `REVIEW_EXECUTION_EVIDENCE.json`

最终证据账本必须列出 `reviewer`、`visual_reviewer`、`editor` 和 `final_reviewer` 的独立会话、模型、输出文件、SHA-256 与完成时间。

## 文档读取

读取 DOCX/PDF 题面或规范时使用：

```powershell
python tools/doc_reader.py <file.docx-or-pdf> --out report.md
```

视觉识别失败时命令返回 `3` 并在报告中标记失败，防止后续自动判断误认为已经完整读取。只有人工复核场景才能显式添加 `--allow-vision-failure`；`--no-vision` 仅列出图片，不表示图片内容已读取。

## 边界

- 2026 官方竞赛规则仍需逐条核验后才能作为最终合规依据。
- 本仓自有内容按根目录 `LICENSE` 分发（CC-BY-NC-4.0，禁止商用与训练 AI）；第三方技能与规则材料的再分发授权尚未逐项确认，不能据此公开发布发行包。
- 驱动协议以「读文件 + Python CLI」为最小面；技能扫描、工具事件审计等增强能力属可选集成，未实测的环境不宣称支持。
- L1 工具事件审计由 `hooks/agent_audit_l1.py` 提供：PreToolUse/PostToolUse/PostToolUseFailure 事件落 `<项目根>/.engine/audit/operations.jsonl`；fail-open（钩子故障不阻断），仅 `git add .`/`-A`/`--all` 走 deny。运行环境未注册钩子时如实记为 `unavailable`，L2（引擎门禁）/L3（证据链）始终可用；注册引导可用 `--print-bootstrap`。
- 不要将 `.env` 打入压缩包、复制到公开仓库或写入审计报告。
