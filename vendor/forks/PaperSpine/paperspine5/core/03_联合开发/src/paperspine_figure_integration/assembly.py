"""Assemble confirmed FigMirror candidates into a PaperSpine final-paper directory."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any

from .body_integration import STORY_FIELDS, build_figure_body_contract
from .contracts import ContractError, load_json, write_json_atomic
from .redesign_selection import resolve_redesign_decisions
from .scientific_identity import (
    requires_identity_repair,
    validate_candidate_identity_audit,
    write_identity_completion_receipt,
)


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


def _latex_placement(request: dict[str, Any]) -> tuple[str, str]:
    context = request.get("final_size_context")
    if not isinstance(context, dict):
        return "figure", r"\linewidth"
    mode = context.get("document_layout_mode")
    span = context.get("column_span")
    if mode == "single_column" and span == "one_column":
        return "figure", r"\textwidth"
    if mode == "two_column" and span == "one_column":
        return "figure", r"\columnwidth"
    if mode == "two_column" and span == "two_column_span":
        return "figure*", r"\textwidth"
    raise ContractError(
        f"{request.get('figure_id')} has an incompatible document layout and column span"
    )


def _latex_figure(
    figure_id: str,
    relative_asset: str,
    caption: str,
    label: str,
    *,
    environment: str,
    width: str,
) -> str:
    return "\n".join(
        [
            f"% PAPERSFIGURE-INJECTED:{figure_id}",
            rf"\begin{{{environment}}}[htbp]",
            r"  \centering",
            rf"  \includegraphics[width={width}]{{{relative_asset}}}",
            rf"  \caption{{{caption}}}",
            rf"  \label{{{label}}}",
            rf"\end{{{environment}}}",
        ]
    )


def assemble_figures(
    job: dict[str, Any],
    requests: dict[str, Any],
    decision: dict[str, Any],
) -> dict[str, Any]:
    decision = resolve_redesign_decisions(job, requests, decision)
    final_dir = Path(job["assembly"]["final_paper_dir"])
    figure_output = final_dir / "figures"
    editable_output = final_dir / "figure_sources"
    supplementary_dir = final_dir / "supplementary"
    supplementary_figure_output = supplementary_dir / "figures"
    supplementary_editable_output = supplementary_dir / "figure_sources"
    figure_job = Path(job["figure"]["job_dir"])
    preferred = [job["figure"]["preferred_format"], *job["figure"]["fallback_formats"]]
    preferred = list(dict.fromkeys(preferred))
    request_by_id = {item["figure_id"]: item for item in requests["figures"]}
    selected_by_id = {item["figure_id"]: item for item in decision["figures"]}

    for request in requests["figures"]:
        if request.get("publication_role", "main") == "omit":
            continue
        missing_story = [field for field in STORY_FIELDS if request.get(field) in (None, "", [])]
        if missing_story:
            raise ContractError(
                f"{request['figure_id']} cannot be assembled for PaperSpine body use without: {missing_story}"
            )

    revision_required = [
        f"{item['figure_id']}:{panel.get('panel_id')}"
        for item in decision["figures"]
        if request_by_id[item["figure_id"]].get("publication_role", "main") != "omit"
        for panel in item.get("panel_decisions", [])
        if panel.get("action") == "revise"
    ]
    if revision_required:
        raise ContractError(f"figure assembly is blocked by revision requests: {revision_required}")

    main_tex = Path(job["assembly"]["main_tex"])
    tex_text = main_tex.read_text(encoding="utf-8") if main_tex.is_file() else None
    main_snippets: list[str] = []
    supplementary_snippets: list[str] = []
    pending: list[dict[str, Any]] = []
    omitted_dispositions: list[dict[str, Any]] = []
    missing_markers: list[str] = []
    supplementary_number = 0

    for figure_id, request in request_by_id.items():
        selected = selected_by_id[figure_id]
        candidate_id = selected["selected_candidate"]
        publication_role = request.get("publication_role", "main")
        marker = f"% PAPERSFIGURE:{figure_id}"
        if publication_role == "omit":
            if candidate_id != "omitted":
                raise ContractError(f"{figure_id} omit disposition requires selected_candidate=omitted")
            if job["assembly"]["inject_tex_markers"] and tex_text is not None and marker in tex_text:
                tex_text = tex_text.replace(
                    marker, f"% PAPERSFIGURE-OMITTED:{figure_id}", 1
                )
            omitted_dispositions.append(
                {
                    "figure_id": figure_id,
                    "publication_role": "omit",
                    "editorial_rationale": request["editorial_rationale"],
                    "claim_coverage": request["claim_coverage"],
                    "assembly_status": "omitted",
                    "display_number": None,
                    "selected_candidate": "omitted",
                    "publication_asset": None,
                    "editable_source": None,
                }
            )
            continue
        if requires_identity_repair(request) and candidate_id == "existing":
            raise ContractError(
                f"{figure_id} scientific identity repair cannot fall back to the known-invalid original"
            )
        if candidate_id == "existing" and request.get("decision") in {"keep", "redesign", "improve"}:
            source = Path(request["current_figure"]).resolve()
            chosen_format = source.suffix.lower().removeprefix(".")
            if chosen_format not in {"pdf", "svg", "png"}:
                raise ContractError(
                    f"{figure_id} original selections require selected_candidate=existing and a PDF/SVG/PNG current_figure"
                )
            pptx_source = None
            identity_audit = None
        else:
            candidate_dir = figure_job / "candidates" / figure_id / candidate_id
            authoring_report_path = candidate_dir / "authoring_report.json"
            report = load_json(authoring_report_path)
            exports = report.get("exports", {})
            comparison = selected.get("comparison_validation") or {}
            if (
                request.get("decision") in {"redesign", "improve"}
                and selected.get("selection_authority") == "independent_strict_superiority"
                and comparison.get("valid") is True
            ):
                source = Path(str(comparison.get("winner_source"))).resolve()
                chosen_format = source.suffix.lower().removeprefix(".")
                if (
                    chosen_format not in {"pdf", "svg", "png"}
                    or not source.is_file()
                    or _sha256(source).upper() != comparison.get("winner_sha256")
                ):
                    raise ContractError(
                        f"{figure_id}/{candidate_id} independently reviewed winner changed before assembly"
                    )
            else:
                chosen_format = next(
                    (item for item in preferred if isinstance(exports.get(item), str)), None
                )
                if chosen_format is None:
                    raise ContractError(
                        f"{figure_id}/{candidate_id} has none of the requested export formats: {preferred}"
                    )
                source = _candidate_export(candidate_dir, exports, chosen_format)
                if source is None:  # guarded by chosen_format, retained for type narrowing
                    raise ContractError(
                        f"selected figure export does not exist: {figure_id}/{candidate_id}"
                    )
            pptx_source = _candidate_export(candidate_dir, exports, "pptx")
            identity_audit = validate_candidate_identity_audit(
                request,
                candidate_dir=candidate_dir,
                publication_source=source,
                editable_source=pptx_source,
                authoring_report_path=authoring_report_path,
                authoring_report=report,
            )
        if publication_role == "supplementary":
            supplementary_number += 1
            destination = supplementary_figure_output / f"{figure_id}.{chosen_format}"
            editable_destination = (
                supplementary_editable_output / f"{figure_id}.pptx" if pptx_source else None
            )
            relative_asset = f"supplementary/figures/{destination.name}"
            display_number = f"Fig. S{supplementary_number}"
        else:
            destination = figure_output / f"{figure_id}.{chosen_format}"
            editable_destination = editable_output / f"{figure_id}.pptx" if pptx_source else None
            relative_asset = f"figures/{destination.name}"
            display_number = None
        latex_environment, latex_width = _latex_placement(request)
        snippet = _latex_figure(
            figure_id,
            relative_asset,
            request["caption"],
            request["label"],
            environment=latex_environment,
            width=latex_width,
        )
        injected_marker = f"% PAPERSFIGURE-INJECTED:{figure_id}"
        if publication_role == "main" and job["assembly"]["inject_tex_markers"] and tex_text is not None:
            if marker in tex_text:
                tex_text = tex_text.replace(marker, snippet, 1)
            elif injected_marker not in tex_text:
                missing_markers.append(figure_id)
        elif publication_role == "supplementary" and job["assembly"]["inject_tex_markers"] and tex_text is not None:
            if marker in tex_text:
                tex_text = tex_text.replace(
                    marker, f"% PAPERSFIGURE-MOVED-TO-SUPPLEMENT:{figure_id}", 1
                )
        if publication_role == "supplementary":
            supplementary_snippets.append(snippet)
        else:
            main_snippets.append(snippet)
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
                "publication_role": publication_role,
                "editorial_rationale": request["editorial_rationale"],
                "claim_coverage": request["claim_coverage"],
                "display_number": display_number,
                "placement": request.get("placement"),
                "final_size_context": request.get("final_size_context"),
                "latex_environment": latex_environment,
                "latex_width": latex_width,
                "selection_authority": selected.get("selection_authority")
                or (
                    "confirmed_existing_original"
                    if candidate_id == "existing"
                    else "confirmed_review_decision"
                ),
                "comparison_receipt": selected.get("comparison_receipt"),
                "comparison_validation": selected.get("comparison_validation"),
                "fallback_reason": selected.get("fallback_reason"),
                "current_figure_sha256": request.get("current_figure_sha256"),
                "source_sha256": _sha256(source),
                "scientific_identity": request.get("scientific_identity"),
                "identity_audit": identity_audit,
            }
        )

    if missing_markers and job["assembly"]["require_tex_markers"]:
        raise ContractError(f"main.tex is missing required PaperFigure markers: {missing_markers}")

    figure_output.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for item in pending:
        item["destination"].parent.mkdir(parents=True, exist_ok=True)
        if item["source"].resolve() != item["destination"].resolve():
            shutil.copy2(item["source"], item["destination"])
        editable_source: dict[str, Any] | None = None
        if item["pptx_source"] is not None and item["editable_destination"] is not None:
            item["editable_destination"].parent.mkdir(parents=True, exist_ok=True)
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
                "publication_role": item["publication_role"],
                "editorial_rationale": item["editorial_rationale"],
                "claim_coverage": item["claim_coverage"],
                "display_number": item["display_number"],
                "editable_source": editable_source,
                "selection_evidence": {
                    "authority": item.get("selection_authority"),
                    "comparison_receipt": item.get("comparison_receipt"),
                    "comparison_validation": item.get("comparison_validation"),
                    "fallback_reason": item.get("fallback_reason"),
                    "current_figure_sha256": item.get("current_figure_sha256"),
                    "source_sha256": item["source_sha256"],
                    "selected_candidate": item["candidate_id"],
                },
                "scientific_identity": item.get("scientific_identity"),
                "identity_audit": item.get("identity_audit"),
                "placement": item.get("placement"),
                "final_size_context": item.get("final_size_context"),
                "latex_environment": item["latex_environment"],
                "latex_width": item["latex_width"],
            }
        )
    final_dir.mkdir(parents=True, exist_ok=True)
    includes_path = final_dir / "figure_includes.tex"
    includes_path.write_text("\n\n".join(main_snippets) + "\n", encoding="utf-8")
    supplementary_includes_path = supplementary_dir / "supplementary_figures.tex"
    if supplementary_snippets:
        supplementary_dir.mkdir(parents=True, exist_ok=True)
        supplementary_preamble = "\n".join(
            [
                r"% PaperSpine supplementary-figure numbering",
                r"\setcounter{figure}{0}",
                r"\renewcommand{\thefigure}{S\arabic{figure}}",
            ]
        )
        supplementary_includes_path.write_text(
            supplementary_preamble + "\n\n" + "\n\n".join(supplementary_snippets) + "\n",
            encoding="utf-8",
        )
    tex_updated = False
    if tex_text is not None and job["assembly"]["inject_tex_markers"]:
        main_tex.write_text(tex_text, encoding="utf-8")
        tex_updated = True
    record_by_id = {item["figure_id"]: item for item in records}
    dispositions_by_id = {item["figure_id"]: item for item in omitted_dispositions}
    for request in requests["figures"]:
        figure_id = request["figure_id"]
        if figure_id in dispositions_by_id:
            continue
        record = record_by_id[figure_id]
        editable = record.get("editable_source")
        dispositions_by_id[figure_id] = {
            "figure_id": figure_id,
            "publication_role": record["publication_role"],
            "editorial_rationale": record["editorial_rationale"],
            "claim_coverage": record["claim_coverage"],
            "assembly_status": (
                "included_supplementary"
                if record["publication_role"] == "supplementary"
                else "included_main"
            ),
            "display_number": record["display_number"],
            "selected_candidate": record["candidate_id"],
            "publication_asset": {
                "path": record["relative_asset"],
                "source_sha256": record["selection_evidence"]["source_sha256"],
                "assembled_sha256": record["sha256"],
            },
            "editable_source": (
                {
                    "path": Path(editable["destination"])
                    .resolve()
                    .relative_to(final_dir.resolve())
                    .as_posix(),
                    "sha256": editable["sha256"],
                }
                if editable
                else None
            ),
        }
    disposition_manifest = {
        "schema_version": "1.0",
        "contract_type": "paperspine.figure.disposition",
        "status": "PASS",
        "job_id": job["job_id"],
        "paper_id": requests["paper_id"],
        "figures": [dispositions_by_id[item["figure_id"]] for item in requests["figures"]],
        "supplementary_figure_includes": (
            str(supplementary_includes_path) if supplementary_snippets else None
        ),
    }
    disposition_manifest_path = write_json_atomic(
        final_dir / "figure_disposition_manifest.json", disposition_manifest
    )
    body = build_figure_body_contract(job, requests, records)
    identity_completion = write_identity_completion_receipt(
        output_dir=Path(job["paper"]["output_dir"]),
        body_contract_path=Path(body["contract_path"]),
        requests=requests,
        records=records,
    )
    manifest = {
        "schema_version": "1.0",
        "status": "PASS",
        "job_id": job["job_id"],
        "paper_id": requests["paper_id"],
        "figures": records,
        "dispositions": disposition_manifest["figures"],
        "figure_includes": str(includes_path),
        "supplementary_figure_includes": (
            str(supplementary_includes_path) if supplementary_snippets else None
        ),
        "figure_disposition_manifest": str(disposition_manifest_path),
        "main_tex": str(main_tex) if main_tex.is_file() else None,
        "main_tex_updated": tex_updated,
        "missing_optional_markers": missing_markers,
        "body_contract": body["contract_path"],
        "body_contract_markdown": body["markdown_path"],
        "figure_asset_map": body["asset_map_path"],
        "identity_completion_receipt": str(identity_completion) if identity_completion else None,
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
        f"- Figure disposition manifest: `{disposition_manifest_path}`",
        "",
        "| Figure | Publication role | Candidate | Format | Destination | Editable source |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| {item['figure_id']} | {item['publication_role']} | {item['candidate_id']} | {item['format']} | `{item['relative_asset']}` | `{(item.get('editable_source') or {}).get('format', '—')}` |"
        for item in records
    )
    lines.extend(
        f"| {item['figure_id']} | omit | omitted | — | `—` | `—` |"
        for item in omitted_dispositions
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {**manifest, "manifest": str(manifest_path), "report": str(report_path)}
