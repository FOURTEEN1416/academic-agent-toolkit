#!/usr/bin/env python3
"""Validate the scientific story carried by every PaperSpine figure.

This is deliberately one compact contract, not a second rationale matrix. It
connects the paper claim, panel jobs, evidence anchors, Results units, the
generation handoff, and the final visual receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

SAFE_ID = re.compile(r"^[A-Za-z0-9._-]+$")
REQUIRED_STORY_FIELDS = (
    "figure_role",
    "scientific_question",
    "intended_conclusion",
    "claim_boundary",
    "results_units",
    "hero_panel",
    "panels",
)
PANEL_FIELDS = ("panel_id", "question", "role", "evidence_anchor", "intended_reading")


@dataclass
class FigureStoryResult:
    request_path: str
    phase: str
    ok: bool
    figure_count: int
    findings: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate PaperSpine figure-story contracts.")
    parser.add_argument("output_dir", nargs="?", default="paper_rewriting_output")
    parser.add_argument("--phase", choices=("planning", "final"), default="planning")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write", action="store_true")
    return parser.parse_args()


def _text(value: object) -> str:
    return " ".join(str(value or "").split())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_figure_story(output_dir: Path, phase: str = "planning") -> FigureStoryResult:
    path = output_dir / "figure_requests.json"
    findings: list[str] = []
    if not path.is_file():
        return FigureStoryResult(str(path), phase, False, 0, ["figure_requests.json is missing"])
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return FigureStoryResult(str(path), phase, False, 0, [f"invalid JSON: {exc}"])
    figures = raw.get("figures") if isinstance(raw, dict) else None
    if not isinstance(figures, list) or not figures:
        return FigureStoryResult(str(path), phase, False, 0, ["figures must be a non-empty list"])

    seen: set[str] = set()
    labels: set[str] = set()
    requests_by_id: dict[str, dict] = {}
    for index, figure in enumerate(figures):
        name = f"figures[{index}]"
        if not isinstance(figure, dict):
            findings.append(f"{name} must be an object")
            continue
        figure_id = _text(figure.get("figure_id"))
        if not figure_id or not SAFE_ID.fullmatch(figure_id) or figure_id in seen:
            findings.append(f"{name}.figure_id must be a unique safe identifier")
        seen.add(figure_id)
        if figure_id:
            requests_by_id[figure_id] = figure
        label = _text(figure.get("label") or f"fig:{figure_id}")
        labels.add(label)
        for field in ("claim", "caption", *REQUIRED_STORY_FIELDS):
            if field not in figure or figure.get(field) in (None, "", []):
                findings.append(f"{name}.{field} is required")
        if figure.get("decision", "create") not in {"keep", "redesign", "create"}:
            findings.append(f"{name}.decision must be keep, redesign, or create")
        results_units = figure.get("results_units")
        if not isinstance(results_units, list) or not results_units or any(not _text(item) for item in results_units):
            findings.append(f"{name}.results_units must contain named Results unit(s)")
        panels = figure.get("panels")
        panel_ids: set[str] = set()
        if not isinstance(panels, list) or not panels:
            findings.append(f"{name}.panels must be a non-empty list")
        else:
            for panel_index, panel in enumerate(panels):
                panel_name = f"{name}.panels[{panel_index}]"
                if not isinstance(panel, dict):
                    findings.append(f"{panel_name} must be an object")
                    continue
                for field in PANEL_FIELDS:
                    if not _text(panel.get(field)):
                        findings.append(f"{panel_name}.{field} is required")
                panel_id = _text(panel.get("panel_id"))
                if not SAFE_ID.fullmatch(panel_id) or panel_id in panel_ids:
                    findings.append(f"{panel_name}.panel_id must be unique and safe")
                panel_ids.add(panel_id)
        if _text(figure.get("hero_panel")) not in panel_ids:
            findings.append(f"{name}.hero_panel must name one declared panel")
        if figure.get("figure_kind") == "data" and not figure.get("source_data"):
            findings.append(f"{name}.source_data is required for data figures")

    if phase == "final":
        manifest_path = output_dir / "visual_audit_manifest.json"
        if not manifest_path.is_file():
            findings.append("visual_audit_manifest.json is missing for final figure-story verification")
        else:
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError) as exc:
                findings.append(f"invalid visual_audit_manifest.json: {exc}")
            else:
                audited = {
                    _text(item.get("figure_id"))
                    for item in manifest.get("figures", [])
                    if isinstance(item, dict)
                }
                missing = sorted(label for label in labels if label not in audited)
                if missing:
                    findings.append(f"final visual audit does not cover requested labels: {missing}")

        body_path = output_dir / "figure_body_contract.json"
        body_figures: dict[str, dict] = {}
        if not body_path.is_file():
            findings.append("figure_body_contract.json is missing for final body integration")
        else:
            try:
                body = json.loads(body_path.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError) as exc:
                findings.append(f"invalid figure_body_contract.json: {exc}")
            else:
                if body.get("schema_version") != "1.0" or body.get("contract_type") != "paperspine.figure.body":
                    findings.append("figure_body_contract.json has an unsupported contract identity")
                if body.get("status") != "PASS":
                    findings.append("figure_body_contract.json status is not PASS")
                raw_body_figures = body.get("figures")
                if not isinstance(raw_body_figures, list):
                    findings.append("figure_body_contract.json figures must be a list")
                else:
                    for item in raw_body_figures:
                        if not isinstance(item, dict) or not _text(item.get("figure_id")):
                            findings.append("figure_body_contract.json contains an invalid figure record")
                            continue
                        figure_id = _text(item.get("figure_id"))
                        if figure_id in body_figures:
                            findings.append(f"figure_body_contract.json duplicates {figure_id}")
                        body_figures[figure_id] = item

        for figure_id, request in requests_by_id.items():
            body_figure = body_figures.get(figure_id)
            if body_figure is None:
                findings.append(f"figure body contract does not cover requested figure: {figure_id}")
                continue
            for field in (
                "figure_kind",
                "figure_role",
                "label",
                "caption",
                "scientific_question",
                "claim",
                "intended_conclusion",
                "claim_boundary",
                "results_units",
                "hero_panel",
                "panels",
            ):
                expected = request.get(field) if field != "label" else request.get("label") or f"fig:{figure_id}"
                if body_figure.get(field) != expected:
                    findings.append(f"figure body contract changed {figure_id}.{field}")
            asset = body_figure.get("publication_asset")
            if not isinstance(asset, dict) or not _text(asset.get("path")):
                findings.append(f"figure body contract {figure_id}.publication_asset is invalid")
            else:
                asset_path = (output_dir / str(asset["path"])).resolve()
                try:
                    asset_path.relative_to(output_dir.resolve())
                except ValueError:
                    findings.append(f"figure body contract asset escapes output directory: {asset_path}")
                else:
                    if not asset_path.is_file():
                        findings.append(f"figure body contract asset is missing: {asset_path}")
                    elif _sha256(asset_path) != asset.get("sha256"):
                        findings.append(f"figure body contract asset hash changed: {asset_path}")
            editable = body_figure.get("editable_source")
            if editable is not None:
                if not isinstance(editable, dict) or not _text(editable.get("path")):
                    findings.append(f"figure body contract {figure_id}.editable_source is invalid")
                else:
                    editable_path = (output_dir / str(editable["path"])).resolve()
                    try:
                        editable_path.relative_to(output_dir.resolve())
                    except ValueError:
                        findings.append(f"figure editable source escapes output directory: {editable_path}")
                    else:
                        if not editable_path.is_file():
                            findings.append(f"figure editable source is missing: {editable_path}")
                        elif _sha256(editable_path) != editable.get("sha256"):
                            findings.append(f"figure editable source hash changed: {editable_path}")

        main_tex = output_dir / "final_paper" / "main.tex"
        includes_tex = output_dir / "final_paper" / "figure_includes.tex"
        if not main_tex.is_file():
            findings.append("final_paper/main.tex is missing for figure body-reference verification")
        else:
            main_text = main_tex.read_text(encoding="utf-8-sig")
            main_body = re.sub(r"(?m)(?<!\\)%.*$", "", main_text)
            includes_text = includes_tex.read_text(encoding="utf-8-sig") if includes_tex.is_file() else ""
            combined = main_text + "\n" + includes_text
            for label in labels:
                if rf"\label{{{label}}}" not in combined:
                    findings.append(f"final LaTeX does not declare requested figure label: {label}")
                reference = re.compile(rf"\\(?:ref|autoref|cref|Cref)\{{{re.escape(label)}\}}")
                if not reference.search(main_body):
                    findings.append(f"final manuscript body does not reference requested figure label: {label}")

    return FigureStoryResult(str(path), phase, not findings, len(figures), findings)


def to_markdown(result: FigureStoryResult) -> str:
    lines = [
        "# Figure Story Check",
        "",
        f"- Phase: `{result.phase}`",
        f"- Request: `{result.request_path}`",
        f"- Status: {'PASS' if result.ok else 'FAIL'}",
        f"- Figures: {result.figure_count}",
        "",
        "## Findings",
        "",
    ]
    lines.extend(f"- {item}" for item in result.findings) if result.findings else lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    result = validate_figure_story(output_dir, args.phase)
    markdown = to_markdown(result)
    if args.write:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "figure_story_check.md").write_text(markdown, encoding="utf-8")
    if args.json:
        print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
    if args.markdown or not args.json:
        print(markdown)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
