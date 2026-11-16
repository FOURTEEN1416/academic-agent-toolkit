# ASSET-GAP 资产缺口声明 — meta-skill-creator

> 2026-11-16 cluster:meta 修复批补登。此前 asset_gap_register.json 曾以「claude-code-templates 聚合 fork 在库」为由销账 2 条；经核查，`vendor/forks/claude-code-templates/.../skill-creator/` 的相对布局与 `academic-toolkit/skills/meta-skill-creator/` 不互通，模型在技能目录内执行仍会失败，故重新登记。SKILL.md「Running and evaluating test cases」评测流水线整节依赖下列资产，缺席时按 SKILL.md 节内降级路径执行（写 evals.json → 人工评审 → 改稿）。

## 缺失资产清单（8 项，2026-11-16 审计）

- `eval-viewer/generate_review.py`（SKILL.md :17、:238、:478 引用）
- `scripts/aggregate_benchmark.py`（:229）
- `scripts/run_loop.py`（:382）
- `scripts/package_skill.py`（:413）
- `agents/grader.md`（:225、:463）
- `agents/analyzer.md`（:234、:465）
- `agents/comparator.md`（:327、:464）
- `evals/`（:145 —— 运行时工作目录约定：由执行者按模板创建 `evals/evals.json`，非盘上既有资产引用）

## 处置口径

- 本声明使上述断链显性化（audit 豁免）；SKILL.md 评测流水线节已加降级路径标注，正文不再诱导直接执行不存在的脚本。
- 若后续补齐：从上游 fork 复制对应文件并保持技能内相对布局 → 逐项从本清单移除 → 删除本声明；或按 DEF-17（四件套合并）裁决一并处置。
