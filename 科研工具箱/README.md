# 科研工具箱

本套件为 OpenCode Desktop 提供数学建模竞赛的技能、工具、工作流状态、质量门禁和本地证据链。它不提供新的 UI，也不启动或替代 Agent runtime。

## 当前入口

从共享根 `D:\Desktop\数模竞赛` 启动 OpenCode Desktop。根 `opencode.json` 配置默认角色、技能路径和本套件的 `AGENTS.md` 指令。

在 Agent 会话中，先按 `AGENTS.md` 的路由加载对应技能。工作流引擎只记录状态与验证证据：

```powershell
python -m engine.workflow_cli caps
python -m engine.workflow_cli start --template comp_cumcm --workspace workspaces\demo --params '{"language":"zh"}'
python -m engine.workflow_cli next --wf <workflow-id> --db workspaces\demo\.engine\workflow.sqlite
```

工作流默认数据库在 `<workspace>/.engine/workflow.sqlite`。每一步的执行证据在 `<workspace>/.engine/evidence/`，运行日志在 `<workspace>/.engine/logs/`。操作审计可生成到 `<workspace>/OPERATION_AUDIT_REPORT.json`；竞赛最终交付审计独立使用 `<workspace>/AUDIT_REPORT.json`，两者不会互相覆盖：

```powershell
python -m engine.workflow_cli audit --workspace workspaces\demo
```

## 本地 Smoke Check

在本套件目录运行：

```powershell
python -m engine.workflow_cli caps
pytest -q
```

`caps` 只检测本机依赖；`pytest` 验证离线的工作流、门禁、证据、文档读取与工具行为。它们不证明外部 API、OpenCode Desktop 插件或子 Agent 在当前账户已真实可用。

## 审稿证据

数模审稿人和视觉审查子 Agent 均为只读角色。它们在会话中输出结论，主 Agent 受控写入：

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
- `LICENSE`、第三方技能与规则材料的再分发授权尚未确认，不能据此公开发布发行包。
- 当前实际支持边界是 OpenCode Desktop；Codex 兼容性尚未完成真实验证。
- 不要将 `.env` 打入压缩包、复制到公开仓库或写入审计报告。
