#!/usr/bin/env python3
"""Validate FigMirror provenance, outputs, QA evidence, and DOCX preservation."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path


PASS_VALUES = {"pass", "passed", "verified", "yes", "true"}
ARTIFACT_TYPES = {"schematic", "data", "hybrid", "photographic"}


@dataclass
class CheckResult:
    status: str = "PASS"
    mode: str = "none"
    figure_count: int = 0
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a PaperSpine V5 FigMirror package.")
    parser.add_argument("output_dir", nargs="?", default="paper_rewriting_output")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--write", action="store_true", help="Write figmirror/figmirror_report.md")
    parser.add_argument("--require", action="store_true", help="Require FigMirror even when config says none.")
    return parser.parse_args()


def read_json(path: Path) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return data


def figmirror_mode(config: dict[str, object]) -> str:
    value = str(config.get("figmirror_mode") or "none").strip().lower()
    return value if value in {"none", "audit", "rebuild"} else "none"


def is_pass(value: object) -> bool:
    return str(value or "").strip().lower() in PASS_VALUES


def resolve_artifact(output_dir: Path, figmirror_dir: Path, value: object) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    output_candidate = output_dir / candidate
    if output_candidate.exists():
        return output_candidate
    return figmirror_dir / candidate


def nonempty_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def validate_inventory(inventory: dict[str, object], result: CheckResult) -> None:
    assets = nonempty_list(inventory.get("media_assets"))
    placements = nonempty_list(inventory.get("placements"))
    if not assets:
        result.failures.append("figure_inventory.json has no media_assets.")
    if not placements:
        result.warnings.append("figure_inventory.json has no document placements; confirm the source is not VML/header-only.")
    for index, asset in enumerate(assets, start=1):
        if not isinstance(asset, dict):
            result.failures.append(f"Inventory asset {index} is not an object.")
            continue
        if not asset.get("media_target") or not asset.get("sha256"):
            result.failures.append(f"Inventory asset {index} lacks media_target or sha256.")


def figure_outputs(figure: dict[str, object]) -> dict[str, object]:
    outputs = figure.get("outputs")
    if isinstance(outputs, dict):
        return outputs
    return {key: figure.get(key) for key in ("pdf", "svg", "png", "word_png") if figure.get(key)}


def figure_sources(figure: dict[str, object]) -> list[object]:
    sources: list[object] = []
    for key in ("source_assets", "existing_figures", "data_inputs", "panels"):
        sources.extend(nonempty_list(figure.get(key)))
    if figure.get("source_document"):
        sources.append(figure["source_document"])
    return sources


def validate_qa_report(path: Path, figure_id: str, result: CheckResult) -> None:
    if not path.is_file():
        result.failures.append(f"{figure_id}: QA report does not exist: {path}")
        return
    try:
        qa = read_json(path)
    except (OSError, ValueError) as exc:
        result.failures.append(f"{figure_id}: {exc}")
        return
    if not is_pass(qa.get("status")):
        result.failures.append(f"{figure_id}: QA report status is not PASS: {path}")
    failures = qa.get("failures")
    if isinstance(failures, list) and failures:
        result.failures.append(f"{figure_id}: QA report still contains failures: {failures}")


def validate_docx_report(path: Path, result: CheckResult) -> None:
    if not path.is_file():
        result.failures.append(f"DOCX preservation report does not exist: {path}")
        return
    try:
        report = read_json(path)
    except (OSError, ValueError) as exc:
        result.failures.append(str(exc))
        return
    if not is_pass(report.get("status")):
        result.failures.append("DOCX preservation report status is not PASS.")
    for key in ("document_xml_preserved", "styles_xml_preserved", "relationships_preserved"):
        if report.get(key) is not True:
            result.failures.append(f"DOCX preservation report does not prove {key}.")
    changed_entries = report.get("changed_entries")
    if not isinstance(changed_entries, list) or not changed_entries:
        result.failures.append("DOCX preservation report has no changed media entries.")
    elif any(not str(entry).startswith("word/media/") for entry in changed_entries):
        result.failures.append("DOCX preservation report shows non-media package changes.")


def check(output_dir: Path, require: bool = False) -> CheckResult:
    result = CheckResult()
    config_path = output_dir / "paper_spine_config.json"
    config: dict[str, object] = {}
    if config_path.is_file():
        try:
            config = read_json(config_path)
        except (OSError, ValueError) as exc:
            result.failures.append(str(exc))
    result.mode = figmirror_mode(config)
    if result.mode == "none" and not require:
        return result
    if result.mode == "none" and require:
        result.mode = "audit"

    figmirror_dir = output_dir / "figmirror"
    inventory_path = figmirror_dir / "figure_inventory.json"
    source_map_path = figmirror_dir / "figure_source_map.md"
    design_brief_path = figmirror_dir / "figure_design_brief.md"
    manifest_path = figmirror_dir / "figure_manifest.json"
    for path in (inventory_path, source_map_path, design_brief_path, manifest_path):
        if not path.is_file():
            result.failures.append(f"Missing required FigMirror artifact: {path.relative_to(output_dir)}")
    if result.failures:
        result.status = "FAIL"
        return result

    try:
        inventory = read_json(inventory_path)
        manifest = read_json(manifest_path)
    except (OSError, ValueError) as exc:
        result.failures.append(str(exc))
        result.status = "FAIL"
        return result
    validate_inventory(inventory, result)

    manifest_mode = str(manifest.get("mode") or result.mode).strip().lower()
    if manifest_mode != result.mode:
        result.failures.append(f"Manifest mode {manifest_mode!r} does not match config mode {result.mode!r}.")
    figures = nonempty_list(manifest.get("figures"))
    result.figure_count = len(figures)
    if not figures:
        result.failures.append("figure_manifest.json has no figures.")

    seen_ids: set[str] = set()
    for index, raw_figure in enumerate(figures, start=1):
        if not isinstance(raw_figure, dict):
            result.failures.append(f"Figure {index} is not an object.")
            continue
        figure: dict[str, object] = raw_figure
        figure_id = str(figure.get("figure_id") or figure.get("id") or f"figure-{index}")
        if figure_id in seen_ids:
            result.failures.append(f"Duplicate figure ID: {figure_id}")
        seen_ids.add(figure_id)
        if len(str(figure.get("claim") or "").strip()) < 12:
            result.failures.append(f"{figure_id}: claim is missing or too short.")
        artifact_type = str(figure.get("artifact_type") or "").strip().lower()
        if artifact_type not in ARTIFACT_TYPES:
            result.failures.append(f"{figure_id}: invalid artifact_type {artifact_type!r}.")
        if not figure_sources(figure):
            result.failures.append(f"{figure_id}: no source asset, document, panel, or data input is recorded.")

        verification = figure.get("verification")
        if not isinstance(verification, dict):
            result.failures.append(f"{figure_id}: verification object is missing.")
            verification = {}
        for key in ("programmatic_status", "visual_status", "scientific_status"):
            if not is_pass(verification.get(key)):
                result.failures.append(f"{figure_id}: {key} is not PASS.")
        qa_path = resolve_artifact(output_dir, figmirror_dir, verification.get("qa_report"))
        if qa_path is None:
            result.failures.append(f"{figure_id}: qa_report path is missing.")
        else:
            validate_qa_report(qa_path, figure_id, result)

        if result.mode == "rebuild":
            source_code = figure.get("source_code") or figure.get("plotting_sources")
            if not source_code:
                result.failures.append(f"{figure_id}: rebuild mode requires source_code/plotting_sources.")
            outputs = figure_outputs(figure)
            vector_values = [outputs.get("pdf"), outputs.get("svg")]
            raster_values = [outputs.get("png"), outputs.get("word_png")]
            if not any(vector_values):
                result.failures.append(f"{figure_id}: rebuild mode requires PDF or SVG output.")
            if not any(raster_values):
                result.failures.append(f"{figure_id}: rebuild mode requires PNG or word_png output.")
            for label, value in outputs.items():
                path = resolve_artifact(output_dir, figmirror_dir, value)
                if path is None or not path.is_file():
                    result.failures.append(f"{figure_id}: output {label} does not exist: {value}")

    docx_report_value = manifest.get("docx_preservation_report")
    if docx_report_value:
        docx_report_path = resolve_artifact(output_dir, figmirror_dir, docx_report_value)
        if docx_report_path is None:
            result.failures.append("docx_preservation_report path is invalid.")
        else:
            validate_docx_report(docx_report_path, result)
    elif manifest.get("docx_replacement_requested") is True:
        result.failures.append("DOCX replacement was requested but no docx_preservation_report is recorded.")

    if result.failures:
        result.status = "FAIL"
    return result


def to_markdown(result: CheckResult) -> str:
    lines = [
        "# FigMirror Check",
        "",
        f"Status: {result.status}",
        f"Mode: {result.mode}",
        f"Figures checked: {result.figure_count}",
        "",
        "## Failures",
        "",
    ]
    lines.extend(f"- {item}" for item in result.failures)
    if not result.failures:
        lines.append("- None")
    lines.extend(["", "## Warnings", ""])
    lines.extend(f"- {item}" for item in result.warnings)
    if not result.warnings:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    result = check(output_dir, require=args.require)
    markdown = to_markdown(result)
    if args.write:
        report_path = output_dir / "figmirror" / "figmirror_report.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(markdown, encoding="utf-8")
    if args.markdown or not args.write:
        print(markdown)
    elif args.write:
        print(f"FigMirror check: {result.status}")
    return 0 if result.status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
