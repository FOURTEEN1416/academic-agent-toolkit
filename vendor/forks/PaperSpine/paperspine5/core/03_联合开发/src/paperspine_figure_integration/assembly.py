"""Assemble confirmed FigMirror candidates into a PaperSpine final-paper directory."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any

from .body_integration import STORY_FIELDS, build_figure_body_contract
from .contracts import ContractError, load_json, write_json_atomic


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _candidate_export(candidate_dir: Path, exports: dict[str, Any], format_name: str) -> Path | None:
    value = exports.get(format_name)
    if not isinstance(value, str) or not value.strip():
        return None
    source = Path(value).resolve()
    try:
        source.relative_to(candidate_dir.resolve())
    except ValueError as exc:
        raise ContractError(f"selected {format_name} export escapes its candidate directory: {source}") from exc
    if not source.is_file():
        raise ContractError(f"selected {format_name} export does not exist: {source}")
    return source


def _latex_figure(figure_id: str, relative_asset: str, caption: str, label: str) -> str:
    return "\n".join(
        [
            f"% PAPERSFIGURE-INJECTED:{figure_id}",
            r"\begin{figure}[htbp]",
            r"  \centering",
            rf"  \includegraphics[width=\linewidth]{{{relative_asset}}}",
            rf"  \caption{{{caption}}}",
            rf"  \label{{{label}}}",
            r"\end{figure}",
        ]
    )


def assemble_figures(
    job: dict[str, Any],
    requests: dict[str, Any],
    decision: dict[str, Any],
) -> dict[str, Any]:
    final_dir = Path(job["assembly"]["final_paper_dir"])
    figure_output = final_dir / "figures"
    editable_output = final_dir / "figure_sources"
    figure_job = Path(job["figure"]["job_dir"])
    preferred = [job["figure"]["preferred_format"], *job["figure"]["fallback_formats"]]
    preferred = list(dict.fromkeys(preferred))
    request_by_id = {item["figure_id"]: item for item in requests["figures"]}
    selected_by_id = {item["figure_id"]: item for item in decision["figures"]}

    for request in requests["figures"]:
        missing_story = [field for field in STORY_FIELDS if request.get(field) in (None, "", [])]
        if missing_story:
            raise ContractError(
                f"{request['figure_id']} cannot be assembled for PaperSpine body use without: {missing_story}"
            )

    revision_required = [
        f"{item['figure_id']}:{panel.get('panel_id')}"
        for item in decision["figures"]
        for panel in item.get("panel_decisions", [])
        if panel.get("action") == "revise"
    ]
    if revision_required:
        raise ContractError(f"figure assembly is blocked by revision requests: {revision_required}")

    main_tex = Path(job["assembly"]["main_tex"])
    tex_text = main_tex.read_text(encoding="utf-8") if main_tex.is_file() else None
    snippets: list[str] = []
    pending: list[dict[str, Any]] = []
    missing_markers: list[str] = []

    for figure_id, request in request_by_id.items():
        selected = selected_by_id[figure_id]
        candidate_id = selected["selected_candidate"]
        if request.get("decision") == "keep":
            source = Path(request["current_figure"]).resolve()
            chosen_format = source.suffix.lower().removeprefix(".")
            if candidate_id != "existing" or chosen_format not in {"pdf", "svg", "png"}:
                raise ContractError(
                    f"{figure_id} keep decisions require selected_candidate=existing and a PDF/SVG/PNG current_figure"
                )
            pptx_source = None
        else:
            candidate_dir = figure_job / "candidates" / figure_id / candidate_id
            report = load_json(candidate_dir / "authoring_report.json")
            exports = report.get("exports", {})
            chosen_format = next((item for item in preferred if isinstance(exports.get(item), str)), None)
            if chosen_format is None:
                raise ContractError(f"{figure_id}/{candidate_id} has none of the requested export formats: {preferred}")
            source = _candidate_export(candidate_dir, exports, chosen_format)
            if source is None:  # guarded by chosen_format, retained for type narrowing
                raise ContractError(f"selected figure export does not exist: {figure_id}/{candidate_id}")
            pptx_source = _candidate_export(candidate_dir, exports, "pptx")
        destination = figure_output / f"{figure_id}.{chosen_format}"
        editable_destination = editable_output / f"{figure_id}.pptx" if pptx_source else None
        relative_asset = f"figures/{destination.name}"
        snippet = _latex_figure(figure_id, relative_asset, request["caption"], request["label"])
        marker = f"% PAPERSFIGURE:{figure_id}"
        injected_marker = f"% PAPERSFIGURE-INJECTED:{figure_id}"
        if job["assembly"]["inject_tex_markers"] and tex_text is not None:
            if marker in tex_text:
                tex_text = tex_text.replace(marker, snippet, 1)
            elif injected_marker not in tex_text:
                missing_markers.append(figure_id)
        snippets.append(snippet)
        pending.append(
            {
                "figure_id": figure_id,
                "candidate_id": candidate_id,
                "format": chosen_format,
                "source": source,
                "destination": destination,
                "pptx_source": pptx_source,
                "editable_destination": editable_destination,
                "relative_asset": relative_asset,
                "caption": request["caption"],
                "label": request["label"],
            }
        )

    if missing_markers and job["assembly"]["require_tex_markers"]:
        raise ContractError(f"main.tex is missing required PaperFigure markers: {missing_markers}")

    figure_output.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for item in pending:
        if item["source"].resolve() != item["destination"].resolve():
            shutil.copy2(item["source"], item["destination"])
        editable_source: dict[str, Any] | None = None
        if item["pptx_source"] is not None and item["editable_destination"] is not None:
            editable_output.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item["pptx_source"], item["editable_destination"])
            editable_source = {
                "format": "pptx",
                "source": str(item["pptx_source"]),
                "destination": str(item["editable_destination"]),
                "sha256": _sha256(item["editable_destination"]),
            }
        elif item["format"] == "svg":
            editable_source = {
                "format": "svg",
                "source": str(item["source"]),
                "destination": str(item["destination"]),
                "sha256": _sha256(item["destination"]),
            }
        records.append(
            {
                "figure_id": item["figure_id"],
                "candidate_id": item["candidate_id"],
                "format": item["format"],
                "source": str(item["source"]),
                "destination": str(item["destination"]),
                "relative_asset": item["relative_asset"],
                "sha256": _sha256(item["destination"]),
                "caption": item["caption"],
                "label": item["label"],
                "editable_source": editable_source,
            }
        )
    final_dir.mkdir(parents=True, exist_ok=True)
    includes_path = final_dir / "figure_includes.tex"
    includes_path.write_text("\n\n".join(snippets) + "\n", encoding="utf-8")
    tex_updated = False
    if tex_text is not None and job["assembly"]["inject_tex_markers"]:
        main_tex.write_text(tex_text, encoding="utf-8")
        tex_updated = True
    body = build_figure_body_contract(job, requests, records)
    manifest = {
        "schema_version": "1.0",
        "status": "PASS",
        "job_id": job["job_id"],
        "paper_id": requests["paper_id"],
        "figures": records,
        "figure_includes": str(includes_path),
        "main_tex": str(main_tex) if main_tex.is_file() else None,
        "main_tex_updated": tex_updated,
        "missing_optional_markers": missing_markers,
        "body_contract": body["contract_path"],
        "body_contract_markdown": body["markdown_path"],
        "figure_asset_map": body["asset_map_path"],
    }
    manifest_path = write_json_atomic(final_dir / "figure_integration_manifest.json", manifest)
    report_path = final_dir / "figure_integration_report.md"
    lines = [
        "# PaperSpine × PaperFigure Integration Report",
        "",
        "- Status: PASS",
        f"- Job: `{job['job_id']}`",
        f"- Manifest: `{manifest_path}`",
        f"- LaTeX marker injection: `{'updated' if tex_updated else 'not requested or main.tex absent'}`",
        f"- Body contract: `{body['contract_path']}`",
        f"- Figure asset map: `{body['asset_map_path']}`",
        "",
        "| Figure | Candidate | Format | Destination | Editable source |",
        "| --- | --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| {item['figure_id']} | {item['candidate_id']} | {item['format']} | `{item['relative_asset']}` | `{(item.get('editable_source') or {}).get('format', '—')}` |"
        for item in records
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {**manifest, "manifest": str(manifest_path), "report": str(report_path)}
