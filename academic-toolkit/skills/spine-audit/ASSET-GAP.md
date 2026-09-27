# ASSET-GAP 资产缺口声明 — spine-audit

> 2026-09-28 深读批补登（裁决卡 B 口径：上游资产未随本仓集成，收编待用户裁决）：

## 缺失依赖（2026-09-28 审计，P0 级）

- `_paper_spine_utils.py`（共享 helpers 模块）

以下 tracked 脚本 `from _paper_spine_utils import ...`，干净克隆 import 即 ModuleNotFoundError（上游 PaperSpine pin 1fe46f0 的 helpers 未随本仓集成，vendor 本地副本亦已不在盘）——收编方式见 spine 裁决卡：

- scripts/artifact_check.py
- scripts/integrity_audit.py
- scripts/revision_audit.py
- scripts/citation_quality_audit.py
- scripts/structured_review.py
