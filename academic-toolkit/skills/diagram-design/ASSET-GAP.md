# ASSET-GAP 资产缺口声明 — diagram-design

> 2026-09-28 深读批补登，上游资产未随本仓集成：以下条目为正文实际引用、盘上缺失、
> 且未经内联标记/登记册棘轮/本清单三渠道豁免的资产。

## 缺失资产清单（11 项，2026-09-28 审计）

references/doctor.md、animation.md、type-bar.md、type-line.md 与 assets/example-*-dark.html
指示运行的验证器脚本（上游 scripts/ 未随本仓集成；本仓仅有 drawio_extract.py、
mermaid_extract.py、self_check.py）：

- `scripts/verify-motion.py`
- `scripts/verify-dumbbell.py`
- `scripts/verify-ridgeline.py`
- `scripts/verify-treemap.py`
- `scripts/verify-slopegraph.py`
- `scripts/verify-bubble.py`
- `scripts/verify-docs-sync.py`
- `scripts/verify-drawio-import.py`
- `scripts/verify-mermaid-import.py`
- `scripts/verify-plugin-package.py`
- `scripts/lint-skin.py`

## 补登（2026-09-28 逐行轮：第三批漏项）

- `scripts/verify-geometry.py`（SKILL.md:295,488）
- `scripts/test-verify-motion.py`（references/animation.md:119）
- `scripts/test-verify-dumbbell.py`（references/type-bar.md:100）
- `scripts/test-verify-ridgeline.py`（references/type-line.md:189）
- `scripts/fixtures/sample-architecture.drawio`（references/import-drawio.md:121）
- `scripts/fixtures/sample-flowchart.mmd`（references/import-mermaid.md:81）
- `assets/example-data-flow-extended*.html` ×3（references/type-data-flow.md:369-374）
- `assets/example-process-extended*.html` ×3（references/type-process.md:493-495）
- 图标目录缺 `prometheus` / `grafana` 条目（references/type-high-level.md §1 YAML 引用）
