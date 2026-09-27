# ASSET-GAP 资产缺口声明 — paper-writing-clinical

> 2026-09-28 深读批补登：模块 SKILL.md 自带的验证入口引用上游 tests/ 目录，未随本仓集成。

## 缺失资产清单（2 项）

- `tests/clinical-decision-support/`（modules/clinical-decision-support/SKILL.md:218 的
  unittest discover 入口引用）
- `tests/treatment-plans/`（modules/treatment-plans/SKILL.md:156 同上）

## 补登（2026-09-28 逐行轮：上游同级 pptx 技能未随本仓集成）

- `skills/pptx/scripts/thumbnail.py`（modules/scientific-slides 的 presentation_workflow.md:129、
  slide_capabilities.md:257、visual_review_workflow.md:122,125 四处引用；上游
  claude-scientific-writer 套件假定同级 pptx 技能存在。本仓替代：modules/scientific-slides
  自带的 pdf_to_images.py）
