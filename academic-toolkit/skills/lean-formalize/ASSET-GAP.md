# ASSET-GAP 资产缺口声明 — lean-formalize

> 外部运行时依赖声明（2026-11-17 收编批）：本技能的机器验证环节依赖 **Lean 工具链（elan / lake / lean；Mathlib 可选）**。该工具链**不随本仓分发、本仓不代装**，须由执行环境预先提供。

## 外部依赖清单（1 项）

- `Lean toolchain（elan/lake/lean，Mathlib 可选）` — 用于 `lake build`、`lean --version`、`#print axioms` 等一切机器验证命令。

## 处置口径

- 本技能 SKILL.md 开头设有「环境前置检查」：执行前先探测 `lean --version && lake --version`；探测失败即按 TOOL_GAP 如实报告并停在该缺口，**不得以文字证明冒充机器验证**，不得声称开箱即用。
- 本声明使该外部依赖显性化；删除本文件前必须先让技能不再依赖外部工具链（不可能）或经用户裁决。
- 工具链的安装/授权属执行环境责任；本仓 tracked 文件不写入任何本机安装路径。
