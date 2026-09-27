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
        project_type = params.get("project_type", "fullstack")
        if skill_name == "dev-design" and project_type != "fullstack":
            item["output_files"] = [p for p in item.get("output_files", []) if p != "schema.sql"]
        if skill_name == "dev-code" and project_type != "fullstack":
            item["output_files"] = ["code", "RUN.md"]
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
    # Editing changes accepted paper versions. Re-declare the affected producers'
    # outputs and re-run their checks instead of accepting only a prose changelog.
    for index, item in enumerate(resolved):
        producers = set(item.get("revalidates_outputs_from") or [])
        if item.get("skill_name") == "auto-paper-improvement-loop":
            producers.update({"paper-write", "paper-write-zh", "paper-write-nature",
                              "paper-compile", "paper-compile-zh"})
        if not producers:
            continue
        previous = [s for s in resolved[:index] if s.get("skill_name") in producers]
        item["output_files"] = list(dict.fromkeys(list(item.get("output_files") or []) +
            [p for s in previous for p in s.get("output_files", [])]))
        item["required_checks"] = list(dict.fromkeys(list(item.get("required_checks") or []) +
            [check for s in previous for check in s.get("required_checks", [])]))
        if any(s.get("skill_name") in {"comp-compile-zh", "comp-compile-en"} for s in previous):
            item["revalidate_paper_pages"] = True
    if params.get("output_format") == "docx" and not any(s.get("skill_name") == "docx-export" for s in resolved):
        # 导出必须先于终审，否则 final-audit 不再是最后一步而无法获得 eligible。
        insertion = next((i for i, s in enumerate(resolved)
                          if s.get("skill_name") in {"comp-final-review", "comp-final-audit"}), len(resolved))
        resolved.insert(insertion, {
            "skill_name": "docx-export",
            "display_name": "DOCX 导出",
            "output_files": ["paper.docx"],
            "primary_output": "paper.docx",
            "has_checkpoint": False,
            "checkpoint_type": None,
        })
    return resolved
