"""Resolve Modex-compatible workflow templates into executable step specs."""
from __future__ import annotations

from copy import deepcopy
from typing import Any


def resolve_template(name: str, params: dict[str, Any], catalog: dict[str, Any]) -> list[dict[str, Any]]:
    if name not in catalog:
        raise KeyError(f"unknown workflow template: {name}")
    steps = deepcopy(catalog[name].get("sub_steps", []))
    language = params.get("language")
    resolved: list[dict[str, Any]] = []
    for step in steps:
        item = dict(step)
        # Phase 6 标准：嵌套 metadata 子对象展开到顶层（子对象优先），
        # 同时保留 metadata 键本身（审计/溯源用）。顶层字段仍可独立存在（向后兼容）。
        nested_meta = item.get("metadata")
        if isinstance(nested_meta, dict):
            merged = dict(item)
            merged.update({k: v for k, v in nested_meta.items() if v is not None})
            merged["metadata"] = nested_meta
            item = merged
        if language == "zh" and item.get("skill_name") == "paper-write":
            item["skill_name"] = "paper-write-zh"
        if language == "en" and item.get("skill_name") == "paper-write-zh":
            item["skill_name"] = "paper-write"
        skill_name = item.get("skill_name")
        if item.get("required_checks"):
            skipped_checks = set()
            if params.get("skip_literature", False):
                skipped_checks.add("literature")
            if params.get("skip_review", False):
                skipped_checks.add("review")
            item["required_checks"] = [
                check for check in item["required_checks"] if check not in skipped_checks
            ]
        is_literature = skill_name == "comp-literature"
        is_review = skill_name in {"comp-review", "comp-visual-review", "comp-editor", "comp-final-review"}
        if not params.get(f"skip_{skill_name}", False) and not (params.get("skip_literature", False) and is_literature) and not (params.get("skip_review", False) and is_review):
            resolved.append(item)
    if params.get("output_format") == "docx" and not any(s.get("skill_name") == "docx-export" for s in resolved):
        resolved.append({
            "skill_name": "docx-export",
            "display_name": "DOCX 导出",
            "output_files": ["paper.docx"],
            "primary_output": "paper.docx",
            "has_checkpoint": False,
            "checkpoint_type": None,
        })
    return resolved
