# PaperSpine5 四核心包构建与验证报告

- 版本：`0.3.0-rc.1`
- 构建身份：`paperspine5-0.3.0-rc.1-build.20260823.1`
- 结果：**PASS**
- 同版核心摘要：`9eed412bf2a40b1e00787cd04de2adf696a662055ea31152ebc8f2899e2ba95f`（每包 176 个核心文件，逐字节一致）
- 发布状态：已作为 `v0.3.0-rc.1` GitHub prerelease 发布；公开 Release 页面与下载 URL 是最终发布权威。

## 产物

| 类型 | ZIP | 字节 | SHA-256 |
| --- | --- | ---: | --- |
| universal-skill | `paperspine5-skill-0.3.0-rc.1.zip` | 577038 | `04cf4eefcf467054ab0c6da38bb5fc4cc264c8132efc8d4ccc23c03d0c44766d` |
| codex-plugin | `paperspine5-codex-plugin-0.3.0-rc.1.zip` | 589272 | `a5c0553ace8c96e547e2d2e4ec1063c74bab06d78528b8b2db26eeb064875f87` |
| claude-code-plugin | `paperspine5-claude-code-plugin-0.3.0-rc.1.zip` | 591636 | `ae181ce48e0168b9d3492dd0af3695ab00dad5a002cc8a7dcbe246c857424e29` |
| dsh-plugin | `dsh-paperspine5-0.3.0-rc.1.zip` | 577009 | `57495524d0f81f1b0ea24828e53546ce306a8733e96450528d064921c18c7655` |

## 自动验证

| 检查 | 结果 | 证据 |
| --- | --- | --- |
| release-identity | PASS | 0.3.0-rc.1; paperspine5-0.3.0-rc.1-build.20260823.1 |
| artifact:universal-skill | PASS | bytes=577038; sha256=04cf4eefcf467054ab0c6da38bb5fc4cc264c8132efc8d4ccc23c03d0c44766d |
| zip-layout:universal-skill | PASS | root=['paperspine5-skill-0.3.0-rc.1']; forbidden=[] |
| zip-portability:universal-skill | PASS | machine_path_leaks=[] |
| zip-accepted-scope:universal-skill | PASS | deferred_beta_leaks=[] |
| artifact:codex-plugin | PASS | bytes=589272; sha256=a5c0553ace8c96e547e2d2e4ec1063c74bab06d78528b8b2db26eeb064875f87 |
| zip-layout:codex-plugin | PASS | root=['paperspine5-codex-plugin-0.3.0-rc.1']; forbidden=[] |
| zip-portability:codex-plugin | PASS | machine_path_leaks=[] |
| zip-accepted-scope:codex-plugin | PASS | deferred_beta_leaks=[] |
| artifact:claude-code-plugin | PASS | bytes=591636; sha256=ae181ce48e0168b9d3492dd0af3695ab00dad5a002cc8a7dcbe246c857424e29 |
| zip-layout:claude-code-plugin | PASS | root=['paperspine5-claude-code-plugin-0.3.0-rc.1']; forbidden=[] |
| zip-portability:claude-code-plugin | PASS | machine_path_leaks=[] |
| zip-accepted-scope:claude-code-plugin | PASS | deferred_beta_leaks=[] |
| artifact:dsh-plugin | PASS | bytes=577009; sha256=57495524d0f81f1b0ea24828e53546ce306a8733e96450528d064921c18c7655 |
| zip-layout:dsh-plugin | PASS | root=['dsh-paperspine5-0.3.0-rc.1']; forbidden=[] |
| zip-portability:dsh-plugin | PASS | machine_path_leaks=[] |
| zip-accepted-scope:dsh-plugin | PASS | deferred_beta_leaks=[] |
| checksums-file | PASS | checksums.sha256 matches all four artifacts |
| core:universal-skill | PASS | files=176; sha256=9eed412bf2a40b1e00787cd04de2adf696a662055ea31152ebc8f2899e2ba95f; truth=True |
| runtime-health:universal-skill | PASS | {   "status": "PASS",   "runtime": "paperspine5-local",   "version": "0.3.0-rc.1",   "build_id": "paperspine5-0.3.0-rc.1-build.20260823.1",   "project_root": "<release-staging>\\packages\\paperspine5-skill-0.3.0-rc.1\\core",   "core": "paperspine_figure_integration.coordinator.IntegrationCoordinator",   "transport": [     "mcp-stdio",     "json-bridge"   ] |
| runtime-identity:universal-skill | PASS | version=0.3.0-rc.1; build_id=paperspine5-0.3.0-rc.1-build.20260823.1 |
| core:codex-plugin | PASS | files=176; sha256=9eed412bf2a40b1e00787cd04de2adf696a662055ea31152ebc8f2899e2ba95f; truth=True |
| runtime-health:codex-plugin | PASS | {   "status": "PASS",   "runtime": "paperspine5-local",   "version": "0.3.0-rc.1",   "build_id": "paperspine5-0.3.0-rc.1-build.20260823.1",   "project_root": "<release-staging>\\packages\\paperspine5-codex-plugin-0.3.0-rc.1\\plugins\\paperspine5\\core",   "core": "paperspine_figure_integration.coordinator.IntegrationCoordinator",   "transport": [     "mcp- |
| runtime-identity:codex-plugin | PASS | version=0.3.0-rc.1; build_id=paperspine5-0.3.0-rc.1-build.20260823.1 |
| core:claude-code-plugin | PASS | files=176; sha256=9eed412bf2a40b1e00787cd04de2adf696a662055ea31152ebc8f2899e2ba95f; truth=True |
| runtime-health:claude-code-plugin | PASS | {   "status": "PASS",   "runtime": "paperspine5-local",   "version": "0.3.0-rc.1",   "build_id": "paperspine5-0.3.0-rc.1-build.20260823.1",   "project_root": "<release-staging>\\packages\\paperspine5-claude-code-plugin-0.3.0-rc.1\\plugins\\paperspine5\\core",   "core": "paperspine_figure_integration.coordinator.IntegrationCoordinator",   "transport": [     |
| runtime-identity:claude-code-plugin | PASS | version=0.3.0-rc.1; build_id=paperspine5-0.3.0-rc.1-build.20260823.1 |
| core:dsh-plugin | PASS | files=176; sha256=9eed412bf2a40b1e00787cd04de2adf696a662055ea31152ebc8f2899e2ba95f; truth=True |
| runtime-health:dsh-plugin | PASS | {   "status": "PASS",   "runtime": "paperspine5-local",   "version": "0.3.0-rc.1",   "build_id": "paperspine5-0.3.0-rc.1-build.20260823.1",   "project_root": "<release-staging>\\packages\\dsh-paperspine5-0.3.0-rc.1\\core",   "core": "paperspine_figure_integration.coordinator.IntegrationCoordinator",   "transport": [     "mcp-stdio",     "json-bridge"   ],  |
| runtime-identity:dsh-plugin | PASS | version=0.3.0-rc.1; build_id=paperspine5-0.3.0-rc.1-build.20260823.1 |
| core-consistency | PASS | unique_digests=['9eed412bf2a40b1e00787cd04de2adf696a662055ea31152ebc8f2899e2ba95f'] |
| json-contracts | PASS | parsed=15; invalid=[] |
| state-workflow-schema | PASS | integration-state=1.2; figure-workflow=1.1 |
| five-stage-ui | PASS | 工作配置 → 论文定锚 → 科研图件 → 规范主稿 → 投稿循环 |
| update-policy | PASS | manual update + explicit opt-in launch preflight; default disabled |
| skill-quick-validate | PASS | Skill is valid! |
| paperspine-inner-skill-quick-validate | PASS | Skill is valid! |
| codex-validate-plugin | PASS | Plugin validation passed: <release-staging>\packages\paperspine5-codex-plugin-0.3.0-rc.1\plugins\paperspine5 |
| claude-plugin-validate | PASS | Validating plugin manifest: <release-staging>\packages\paperspine5-claude-code-plugin-0.3.0-rc.1\plugins\paperspine5\.claude-plugin\plugin.json  √ Validation passed |
| claude-command-skill-discovery | PASS | manifest + /paperspine5 command + paperspine5 Skill present |
| codex-marketplace-cachebuster | PASS | manifest_version=0.3.0-rc.1+codex.release-20260823-rc1 |
| dsh-bundle-structure | PASS | package.json dsh.bundle.patch + Cordis dsh-mcp-client + relocatable placeholder |
| dsh-pnpm-pack-dry-run | PASS | paperspine_figure_integration/bridges.py"     },     {       "path": "core/03_联合开发/src/paperspine_figure_integration/cli.py"     },     {       "path": "core/03_联合开发/src/paperspine_figure_integration/contracts.py"     },     {       "path": "core/03_联合开发/src/paperspine_figure_integration/coordinator.py"     },     {       "path": "core/03_联合开发/src/paperspine_figure_integration/ui_server.py"     },     {       "path": |

## 回归证据

- PaperSpine：按委托发布权威冻结为 267 项已验收检查点；当前工作树另有未被本次发布权威接受的 Open Release Beta/276 项声明，因此本构建器显式剥离该 Beta，未用 276 冒充 267 重跑。
- PaperFigure：`python -m unittest discover -s tests -p "test_*.py"`，2026-08-23 实跑 `Ran 60 tests ... OK`。
- V5 integration：`python -m unittest discover -s integration_tests -p "test_*.py"`，2026-08-23 实跑 `Ran 19 tests ... OK`。

## 真实宿主安装烟测（本报告生成前独立执行）

- Codex：`codex plugin marketplace add <包根>` 后 `codex plugin add paperspine5@paperspine5-release` 成功；缓存安装版本为 `0.3.0-rc.1+codex.release-20260823-rc1`。
- Claude Code：marketplace add、plugin install、plugin list 均成功，发现 `paperspine5@paperspine5-release 0.3.0-rc.1`；`claude plugin validate` 无警告通过。
- DSH：本机 DSH/Pnpm 11.7.0 在隔离 profile `paperspine5-release-validation` 中成功 link Bundle；`--dump-config` 显示 `mcp-paperspine5` / `@deepseek-ai/dsh-mcp-client` 及已展开的运行时路径。
- 通用 Skill：官方 `quick_validate.py` 通过；四份共享运行时 `health` 均返回同一版本与构建身份。

## 已知宿主限制

- Codex 与 Claude Code 安装或更新后需要新任务/重启才能重新发现 Skill、命令与 MCP。
- DSH 包必须先运行随包配置器（安装脚本已执行）以展开绝对路径；移动已安装目录后需重新配置并重新 add。
- 当前本地运行时只接受位于其 `PAPERSPINE5_PROJECT_ROOT` 内的 `integration_job.json`，这是 0.3.0 RC 的路径边界；外部工作目录需要显式部署/映射到该根，不能把任意绝对路径直接交给 MCP。
- 外部投稿、上传或公开发布没有被任何包授权；更新默认关闭自动模式，仅手动或明确 opt-in 启动前检查。
- 这是一组本地 RC，不包含公开 URL、签名安装器或联网更新源变更。
