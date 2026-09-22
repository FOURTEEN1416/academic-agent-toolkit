# 安全策略（Security Policy）

本仓是公开科研工具箱仓（技能库 + 工作流引擎 + 质量门禁）。本策略声明密钥/路径卫生边界与漏洞报告渠道。

## 支持版本

| 版本 | 状态 |
|------|------|
| main 分支最新 | 支持 |
| releases/ 下 dated 快照（本地留存，不入库） | 仅供追溯，不接收修复 |

## 密钥与隐私边界（本仓的底线）

- **本地密钥不入库**：`科研工具箱/.env`、任何 API key、token、证书私钥**永不提交**。`.gitignore` 已排除 `.env` 族；`tools/pyc_loader.py` 旧版曾从宿主配置注入 vision provider key——2026-09-23 视觉审核换驱动（宿主独立窗口）后该注入逻辑已整段拆除，现不再读取任何宿主凭据文件。
- **tracked 配置必须可移植**：`opencode.json` / `.zcode/config.json` / `pytest.ini` 等使用占位符（`${DOCSEARCH_MCP_SERVER}` 等）；本机绝对路径（`C:\Users\...`）与过期项目根不得写入。
- **机检门禁**：`python 科研工具箱/tools/secret_scan.py --strict` 扫描全部 tracked 文本文件的高置信凭证模式与配置绝对路径（豁免须登记 `data/secret_scan_allowlist.json` 并给出理由）；CI 每次推送执行。
- **受控 pyc 分发件**：`科研工具箱/tools/*.pyc` 为 tracked 分发件（与同名 `.py` 配对）。**公开仓中字节码不可源码审查**——审计者应优先阅读同名 `.py`；发布/重构以 `.py` 为真源。
- **上游 fork**：`vendor/forks/` 为上游暂存区，不入 git。

## 报告漏洞

**请勿对已泄露密钥提交公开 issue。** 若发现本仓历史中存在真实凭证：

1. 该密钥视同已泄露——**立即在对应服务商侧吊销/轮换**（改写 git 历史不能撤销已发生的泄露）；
2. 通过 GitHub 私有渠道（Security Advisories / 私信仓库所有者）报告；
3. 修复后 `secret_scan` 豁免台账不得用于掩盖真实密钥（豁免条目必须有可复核的理由，测试会拒绝无理由/TODO 条目）。

## 工具边界（TOOL_GAP 如实声明）

`secret_scan` 只覆盖 tracked 文本文件的模式级检测：不扫二进制内嵌字符串、不扫 git 历史、无熵分析。纵深防御应同时启用 GitHub 原生 secret scanning + push protection（仓库设置 → Code security）。
