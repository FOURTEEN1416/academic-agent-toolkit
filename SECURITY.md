# 安全策略（Security Policy）

本仓是公开academic-toolkit仓（技能库 + 工作流引擎 + 质量门禁）。本策略声明密钥/路径卫生边界与漏洞报告渠道。

## 支持版本

| 版本 | 状态 |
|------|------|
| main 分支最新 | 支持 |

本仓当前不含 `releases/` 快照目录；发布以 `main` 分支为准，历史发布记录见 `CHANGELOG.md`。

## 密钥与隐私边界（本仓的底线）

- **本地密钥不入库**：`academic-toolkit/.env`、任何 API key、token、证书私钥**永不提交**。`.gitignore` 已排除 `.env` 族；工具链不读取任何外部平台/运行环境的凭据文件。
- **tracked 配置必须可移植**：`pytest.ini`、`requirements-dev.txt` 等不得写入本机绝对路径（`C:\Users\...`）与过期项目根；环境相关配置放在本地未提交的覆盖中，不入库。
- **机检门禁**：`python academic-toolkit/tools/secret_scan.py --strict` 扫描全部 tracked 文本文件的高置信凭证模式与配置绝对路径（豁免须登记 `data/secret_scan_allowlist.json` 并给出理由）；CI 每次推送执行。
- **单一真源**：`tools/` 只有 `.py` 单一真源，零 `.pyc`（`test_tool_reliability` 棘轮钉住）。
- **上游 fork**：`vendor/forks/` 为上游 fork 收编区，**已 tracked 并随公开仓分发**（2026-09-28 用户裁决；`node_modules` 按全局排除不入库）。各 fork 保留其上游许可证，授权以各目录随附的 `LICENSE` / `UPSTREAM.md` 为准（当前仅部分目录齐备，缺失者待补台账）；`python academic-toolkit/tools/check_provenance.py` 目前只审计 `third_party/` 与技能 `UPSTREAM.md` 台账，尚未覆盖 `vendor/forks/`。
- **审计日志不入库**：L1 审计钩子（`academic-toolkit/hooks/agent_audit_l1.py`，须与本条一并入库）把工具事件写入项目根 `.engine/audit/operations.jsonl`，只记命令/查询模式、路径与内容长度，不记文件正文；`.engine/` 已由 `.gitignore` 排除，不随仓分发；无 L1 钩子时审计状态如实记为 `unavailable`，不阻断执行。

## 报告漏洞

**请勿对已泄露密钥提交公开 issue。** 若发现本仓历史中存在真实凭证：

1. 该密钥视同已泄露——**立即在对应服务商侧吊销/轮换**（改写 git 历史不能撤销已发生的泄露）；
2. 通过 GitHub 私有渠道（Security Advisories / 私信仓库所有者）报告；
3. 修复后 `secret_scan` 豁免台账不得用于掩盖真实密钥（豁免条目必须有可复核的理由，测试会拒绝无理由/TODO 条目）。

## 工具边界（TOOL_GAP 如实声明）

`secret_scan` 只覆盖 tracked 文本文件的模式级检测：不扫二进制内嵌字符串、不扫 git 历史、无熵分析。纵深防御应同时启用 GitHub 原生 secret scanning + push protection（仓库设置 → Code security）。
