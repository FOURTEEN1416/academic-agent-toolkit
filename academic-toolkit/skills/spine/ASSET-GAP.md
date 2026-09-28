# ASSET-GAP 资产缺口声明 — spine

> 2026-09-28 深读批补登（裁决卡 B 口径：上游资产未随本仓集成，收编待用户裁决）：

## 缺失依赖（2026-09-28 审计，P0 级）

- `_paper_spine_utils.py`（共享 helpers 模块）

以下 tracked 脚本 `from _paper_spine_utils import ...`，干净克隆 import 即 ModuleNotFoundError（上游 PaperSpine pin 1fe46f0 的 helpers 未随本仓集成，vendor 本地副本亦已不在盘）——收编方式见 spine 裁决卡：

- scripts/integrity_audit.py
- scripts/translate_guard.py

## 补登（2026-09-28 逐行轮：references/orchestrator-branch-map.md 引用的上游 playbook）

- `references/intake.md`、`references/research.md`、`references/citation.md`、`references/rewrite.md`、
  `references/build.md`、`references/audit.md`、`references/latex.md`、`references/translate.md`、
  `references/submission.md`（branch-map 引用的 9 份 playbook，本仓已拆分为 spine-* 独立技能——
  路由请改走各 spine-* 技能）
- `scripts/progress_check.py`（branch-map :70 引用）

## 清账（2026-09-28：用户裁决允许拉取，上列 9 份 playbook 与 progress_check.py 已自 pin 1fe46f0 回填）

- 9 份 playbook 收编为 `references/<名>.md`（与 orchestrator-branch-map 引用一致）；`scripts/progress_check.py` 回填 scripts/。
