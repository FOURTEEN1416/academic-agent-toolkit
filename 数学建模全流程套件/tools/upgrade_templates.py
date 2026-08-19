#!/usr/bin/env python3
"""一次性、可复现的模板升级迁移脚本（升级计划 Phase 2/3/4/6）。

行为：
1. 按技能名 → required_checks 映射，为模板步骤追加门禁（保留已有检查，去重）。
2. 审核类步骤（comp-review/comp-visual-review/comp-final-review）补 requires_subagent: true。
3. 每个步骤补全嵌套 metadata（Phase 6 标准）：
   {requires_subagent, required_checks, display_name}。
4. 校验所有 required_checks 名称都存在于 engine.quality_gates.run_all 的
   named_checks 注册表（动态读取，防止引用不存在的门禁）。
5. 输出变更摘要并写回 templates.json（UTF-8、ensure_ascii=False、indent=2）。

可重跑：输入已满足规则的步骤保持不变（幂等）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TEMPLATES = ROOT / "engine" / "modex-core" / "templates.json"

# 升级计划 Phase 2/3/4：技能 → 应启用的 named checks（与既有 checks 合并）
SKILL_CHECKS: dict[str, list[str]] = {
    # Phase 2 数模竞赛域
    "comp-prob-analysis": ["step_manifest"],
    "comp-modeling": ["step_manifest", "modeling_contract"],
    "comp-code": ["step_manifest"],
    "comp-paper-zh": ["step_manifest", "paper_consistency"],
    "comp-paper-en": ["step_manifest", "paper_consistency"],
    "comp-compile-zh": ["step_manifest", "compilation_log"],
    "comp-compile-en": ["step_manifest", "compilation_log"],
    # 图表（数模与其他域共用）
    "paper-figure": ["figure_provenance"],
    "paper-figure-drawio": ["figure_provenance"],
    "paper-figure-html": ["figure_provenance"],
    "nature-figure": ["figure_provenance"],
    # Phase 3 学术论文域
    "paper-write": ["step_manifest", "citation_integrity"],
    "paper-write-zh": ["step_manifest", "citation_integrity"],
    "paper-write-nature": ["step_manifest", "citation_integrity"],
    "paper-compile": ["step_manifest", "compilation_log"],
    "paper-compile-zh": ["step_manifest", "compilation_log"],
    "paper-plan": ["step_manifest"],
    "paper-plan-zh": ["step_manifest"],
    "paper-analysis": ["step_manifest"],
    "auto-paper-improvement-loop": ["step_manifest"],
    # Phase 4.1 文献研究域
    "comp-literature": ["step_manifest", "citation_integrity"],
    "literature-review": ["step_manifest", "citation_integrity"],
    "research-lit": ["step_manifest"],
    "novelty-check": ["step_manifest"],
    "idea-creator": ["step_manifest"],
    # Phase 4.2 知识产权域
    "patent-draft": ["step_manifest"],
    "patent-build": ["step_manifest"],
    "copyright-draft": ["step_manifest"],
    "copyright-build": ["step_manifest"],
    # Phase 4.3 实验研究域
    "experiment-bridge": ["step_manifest", "experiment_reproduc"],
    # Phase 4.4 课程/报告域
    "course-paper": ["step_manifest"],
    "course-report": ["step_manifest"],
    "course-plan": ["step_manifest"],
    "course-report-plan": ["step_manifest"],
    "thesis-proposal": ["step_manifest"],
    "humanities-plan": ["step_manifest"],
    "humanities-write": ["step_manifest"],
    # 毕业设计域
    "dev-requirement": ["step_manifest"],
    "dev-design": ["step_manifest"],
    "dev-code": ["step_manifest"],
    "dev-selfcheck": ["step_manifest"],
}

# 审核类步骤 → 必须 require_subagent（M5 机制扩展）
REVIEW_SUBAGENT_SKILLS = {"comp-review", "comp-visual-review", "comp-final-review"}


def _registered_gates() -> set[str]:
    from engine.quality_gates import NAMED_CHECKS_REGISTRY
    return set(NAMED_CHECKS_REGISTRY)


def upgrade(templates_path: Path) -> dict:
    catalog = json.loads(templates_path.read_text(encoding="utf-8"))
    registered = _registered_gates()
    unknown: list[str] = []
    changed_steps = 0

    for template_name, tpl in catalog.items():
        for step in tpl.get("sub_steps", []):
            skill = step.get("skill_name", "")
            existing = list(step.get("required_checks") or [])
            desired = SKILL_CHECKS.get(skill, [])
            if skill in REVIEW_SUBAGENT_SKILLS:
                step["requires_subagent"] = True
                if "review" not in desired:
                    desired = desired + ["review"]
            # 合并去重（保留顺序：先已有、后新增）
            merged = list(existing)
            for check in desired:
                if check not in merged:
                    merged.append(check)
            if merged != existing:
                step["required_checks"] = merged
                changed_steps += 1
            # 补全嵌套 metadata（Phase 6），以顶层当前值为准
            meta = step.get("metadata")
            if not isinstance(meta, dict):
                meta = {}
            meta["requires_subagent"] = bool(step.get("requires_subagent", False))
            meta["required_checks"] = step.get("required_checks", [])
            if not meta.get("display_name"):
                meta["display_name"] = step.get("display_name", skill)
            step["metadata"] = meta
            # 校验未知门禁
            for check in step.get("required_checks", []):
                if check not in registered:
                    unknown.append(f"{template_name}/{step.get('display_name', skill)}: {check}")

    templates_path.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "templates": len(catalog),
        "changed_steps": changed_steps,
        "registered_gates": sorted(registered),
        "unknown_checks": unknown,
        "ok": not unknown,
    }


def main() -> int:
    payload = upgrade(TEMPLATES)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())