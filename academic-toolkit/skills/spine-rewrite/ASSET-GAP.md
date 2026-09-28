# ASSET-GAP 资产缺口声明 — spine-rewrite

> 2026-09-28 深读批补登（裁决卡 B 口径：上游资产未随本仓集成，收编待用户裁决）：

## 缺失依赖（2026-09-28 审计，P0 级）

- `_paper_spine_utils.py`（共享 helpers 模块）

以下 tracked 脚本 `from _paper_spine_utils import ...`，干净克隆 import 即 ModuleNotFoundError（上游 PaperSpine pin 1fe46f0 的 helpers 未随本仓集成，vendor 本地副本亦已不在盘）——收编方式见 spine 裁决卡：

- scripts/integrity_audit.py
- scripts/structured_review.py

## 补登（2026-09-28 逐行轮：references/ 引用的上游资产）

- `references/paragraph_function_templates.md`（rewrite-matrix.md:17-18）
- `references/result_narrative_templates.md`（rewrite-matrix.md:140,156）
- `references/logic-transfer-audit.md`（rewrite-matrix.md）
- `scripts/revision_audit.py`（rewrite-matrix.md:140 以 CWD 相对调用；本件在 spine-audit/scripts/，
  spine-rewrite/scripts/ 缺副本）
- `scripts/section_economy_check.py`（deep-imitation-protocol.md:113 声称 hard-fail 门禁，未随本仓集成）

## 清账（2026-09-28：已自 pin 1fe46f0 回填）

- ~~`scripts/revision_audit.py`~~（已回填 spine-rewrite/scripts/）
- ~~`scripts/section_economy_check.py`~~（已回填）
- ~~`references/logic-transfer-audit.md`~~（已回填）
- `references/paragraph_function_templates.md`、`references/result_narrative_templates.md`：**上游 pin 亦无此二件**（rewrite-matrix.md 的引用在上游即为悬空），维持缺位登记。
