"""Publish the confirmed PaperFigure result as a PaperSpine body contract."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .contracts import ContractError, write_json_atomic


BODY_CONTRACT_VERSION = "1.0"
BODY_CONTRACT_NAME = "paperspine.figure.body"
BODY_MAP_START = "<!-- PAPERFIGURE-BODY-MAP:START -->"
BODY_MAP_END = "<!-- PAPERFIGURE-BODY-MAP:END -->"
STORY_FIELDS = (
    "figure_role",
    "scientific_question",
    "intended_conclusion",
    "claim_boundary",
    "results_units",
    "hero_panel",
    "panels",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _portable_path(path: Path, output_dir: Path, field: str) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(output_dir.resolve()).as_posix()
    except ValueError as exc:
        raise ContractError(f"{field} escapes the PaperSpine output directory: {resolved}") from exc


def _markdown_text(value: Any) -> str:
    return " ".join(str(value or "").replace("|", "\\|").split())


def _body_markdown(contract: dict[str, Any]) -> str:
    lines = [
        "# PaperFigure → PaperSpine 正文结合合同",
        "",
        "- Status: `PASS`",
        f"- Paper: `{contract['paper_id']}`",
        f"- Job: `{contract['job_id']}`",
        "- Authority: PaperFigure owns rendered assets and visual evidence; PaperSpine owns manuscript prose and interpretation.",
        "",
    ]
    for figure in contract["figures"]:
        lines.extend(
            [
                f"## {figure['figure_id']}",
                "",
                f"- LaTeX label: `{figure['label']}`",
                f"- Body reference: `{figure['latex']['display_reference']}`",
                f"- Results units: `{'; '.join(figure['results_units'])}`",
                f"- Publication asset: `{figure['publication_asset']['path']}`",
                f"- Editable source: `{(figure.get('editable_source') or {}).get('path', 'not separately available')}`",
                f"- Allowed claim: {_markdown_text(figure['claim'])}",
                f"- Intended conclusion: {_markdown_text(figure['intended_conclusion'])}",
                f"- Claim boundary: {_markdown_text(figure['claim_boundary'])}",
                f"- Caption: {_markdown_text(figure['caption'])}",
                "",
                "| Panel | Role | Evidence anchor | Intended reading |",
                "| --- | --- | --- | --- |",
            ]
        )
        lines.extend(
            "| {panel_id} | {role} | {evidence_anchor} | {intended_reading} |".format(
                panel_id=_markdown_text(panel["panel_id"]),
                role=_markdown_text(panel["role"]),
                evidence_anchor=_markdown_text(panel["evidence_anchor"]),
                intended_reading=_markdown_text(panel["intended_reading"]),
            )
            for panel in figure["panels"]
        )
        lines.append("")
    return "\n".join(lines)


def _asset_map_block(contract: dict[str, Any]) -> str:
    lines = [
        BODY_MAP_START,
        "## PaperFigure confirmed body assets",
        "",
        "This generated block is authoritative for selected figure files, labels, Results mappings, and claim boundaries.",
        "",
        "| Figure | Asset | Editable source | LaTeX label | Results unit(s) | Allowed claim | Boundary |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for figure in contract["figures"]:
        lines.append(
            "| {figure_id} | `{asset}` | `{editable}` | `{label}` | {results} | {claim} | {boundary} |".format(
                figure_id=_markdown_text(figure["figure_id"]),
                asset=figure["publication_asset"]["path"],
                editable=(figure.get("editable_source") or {}).get("path", "—"),
                label=figure["label"],
                results=_markdown_text("; ".join(figure["results_units"])),
                claim=_markdown_text(figure["claim"]),
                boundary=_markdown_text(figure["claim_boundary"]),
            )
        )
    lines.extend(["", BODY_MAP_END])
    return "\n".join(lines)


def _update_asset_map(path: Path, block: str) -> None:
    if path.is_file():
        original = path.read_text(encoding="utf-8-sig")
        start = original.find(BODY_MAP_START)
        end = original.find(BODY_MAP_END)
        if start >= 0 and end >= start:
            end += len(BODY_MAP_END)
            updated = original[:start].rstrip() + "\n\n" + block + "\n" + original[end:].lstrip()
        else:
            updated = original.rstrip() + "\n\n" + block + "\n"
    else:
        updated = "# Figure Asset Map\n\n" + block + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(updated, encoding="utf-8")


def validate_figure_body_contract(
    raw: dict[str, Any],
    *,
    requests: dict[str, Any] | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    if raw.get("schema_version") != BODY_CONTRACT_VERSION:
        raise ContractError(f"figure body contract schema_version must be {BODY_CONTRACT_VERSION}")
    if raw.get("contract_type") != BODY_CONTRACT_NAME or raw.get("status") != "PASS":
        raise ContractError("figure body contract must be a PASS paperspine.figure.body contract")
    figures = raw.get("figures")
    if not isinstance(figures, list) or not figures:
        raise ContractError("figure body contract figures must be a non-empty list")
    by_id: dict[str, dict[str, Any]] = {}
    for index, figure in enumerate(figures):
        if not isinstance(figure, dict) or not isinstance(figure.get("figure_id"), str):
            raise ContractError(f"figure body contract figures[{index}] is invalid")
        figure_id = figure["figure_id"]
        if figure_id in by_id:
            raise ContractError(f"duplicate figure body contract figure_id: {figure_id}")
        for field in ("label", "caption", "claim", "intended_conclusion", "claim_boundary", *STORY_FIELDS):
            if field not in figure or figure[field] in (None, "", []):
                raise ContractError(f"figure body contract {figure_id}.{field} is required")
        asset = figure.get("publication_asset")
        if not isinstance(asset, dict) or not isinstance(asset.get("path"), str):
            raise ContractError(f"figure body contract {figure_id}.publication_asset is invalid")
        if not isinstance(asset.get("sha256"), str) or len(asset["sha256"]) != 64:
            raise ContractError(f"figure body contract {figure_id}.publication_asset.sha256 is invalid")
        by_id[figure_id] = figure

        if output_dir is not None:
            asset_path = (output_dir / asset["path"]).resolve()
            try:
                asset_path.relative_to(output_dir.resolve())
            except ValueError as exc:
                raise ContractError(f"figure body contract asset escapes output_dir: {asset_path}") from exc
            if not asset_path.is_file() or _sha256(asset_path) != asset["sha256"]:
                raise ContractError(f"figure body contract asset is missing or changed: {asset_path}")
            editable = figure.get("editable_source")
            if editable is not None:
                if not isinstance(editable, dict) or not isinstance(editable.get("path"), str):
                    raise ContractError(f"figure body contract {figure_id}.editable_source is invalid")
                editable_path = (output_dir / editable["path"]).resolve()
                try:
                    editable_path.relative_to(output_dir.resolve())
                except ValueError as exc:
                    raise ContractError(f"figure editable source escapes output_dir: {editable_path}") from exc
                if not editable_path.is_file() or _sha256(editable_path) != editable.get("sha256"):
                    raise ContractError(f"figure editable source is missing or changed: {editable_path}")

    if requests is not None:
        expected = {item["figure_id"]: item for item in requests["figures"]}
        if set(expected) != set(by_id):
            raise ContractError("figure body contract does not cover every requested figure")
        for figure_id, request in expected.items():
            figure = by_id[figure_id]
            for field in ("label", "caption", "claim", *STORY_FIELDS):
                if figure.get(field) != request.get(field):
                    raise ContractError(f"figure body contract changed {figure_id}.{field}")
    return raw


def build_figure_body_contract(
    job: dict[str, Any],
    requests: dict[str, Any],
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Create the file/Markdown interface consumed by PaperSpine body writing."""
    output_dir = Path(job["paper"]["output_dir"])
    final_dir = Path(job["assembly"]["final_paper_dir"])
    record_by_id = {item["figure_id"]: item for item in records}
    body_figures: list[dict[str, Any]] = []
    for request in requests["figures"]:
        figure_id = request["figure_id"]
        missing_story = [field for field in STORY_FIELDS if request.get(field) in (None, "", [])]
        if missing_story:
            raise ContractError(
                f"{figure_id} cannot enter PaperSpine body without the complete scientific-story fields: {missing_story}"
            )
        record = record_by_id.get(figure_id)
        if record is None:
            raise ContractError(f"assembled figure record is missing: {figure_id}")
        destination = Path(record["destination"])
        publication_asset = {
            "path": _portable_path(destination, output_dir, f"{figure_id}.publication_asset"),
            "format": record["format"],
            "sha256": record["sha256"],
            "candidate_id": record["candidate_id"],
        }
        editable_source = record.get("editable_source")
        if editable_source:
            editable_source = {
                **editable_source,
                "path": _portable_path(
                    Path(editable_source["destination"]), output_dir, f"{figure_id}.editable_source"
                ),
            }
            editable_source.pop("destination", None)
            editable_source.pop("source", None)
        evidence_anchors = list(
            dict.fromkeys(panel["evidence_anchor"] for panel in request["panels"])
        )
        body_figures.append(
            {
                "figure_id": figure_id,
                "figure_kind": request["figure_kind"],
                "figure_role": request["figure_role"],
                "label": request["label"],
                "caption": request["caption"],
                "scientific_question": request["scientific_question"],
                "claim": request["claim"],
                "intended_conclusion": request["intended_conclusion"],
                "claim_boundary": request["claim_boundary"],
                "results_units": request["results_units"],
                "hero_panel": request["hero_panel"],
                "panels": request["panels"],
                "publication_asset": publication_asset,
                "editable_source": editable_source,
                "latex": {
                    "insertion_marker": f"% PAPERSFIGURE:{figure_id}",
                    "reference": rf"\ref{{{request['label']}}}",
                    "display_reference": rf"Fig.~\ref{{{request['label']}}}",
                    "includes_file": _portable_path(
                        final_dir / "figure_includes.tex", output_dir, "figure_includes"
                    ),
                },
                "prose_contract": {
                    "results_units": request["results_units"],
                    "allowed_claim": request["claim"],
                    "intended_conclusion": request["intended_conclusion"],
                    "claim_boundary": request["claim_boundary"],
                    "hero_panel": request["hero_panel"],
                    "evidence_anchors": evidence_anchors,
                },
            }
        )

    contract_path = output_dir / "figure_body_contract.json"
    markdown_path = output_dir / "figure_body_contract.md"
    asset_map_path = output_dir / "figure_asset_map.md"
    contract = {
        "schema_version": BODY_CONTRACT_VERSION,
        "contract_type": BODY_CONTRACT_NAME,
        "status": "PASS",
        "job_id": job["job_id"],
        "paper_id": requests["paper_id"],
        "authority": {
            "scientific_story": job["paper"]["figure_requests"],
            "rendered_assets": "PaperFigure/FigMirror selected candidate and authoring report",
            "manuscript_prose": "PaperSpine",
            "final_pixels": "visual_audit_manifest.json",
        },
        "figures": body_figures,
        "artifacts": {
            "contract_markdown": markdown_path.name,
            "figure_asset_map": asset_map_path.name,
            "assembly_manifest": _portable_path(
                final_dir / "figure_integration_manifest.json", output_dir, "assembly_manifest"
            ),
            "figure_includes": _portable_path(
                final_dir / "figure_includes.tex", output_dir, "figure_includes"
            ),
        },
    }
    validate_figure_body_contract(contract, requests=requests, output_dir=output_dir)
    write_json_atomic(contract_path, contract)
    markdown_path.write_text(_body_markdown(contract), encoding="utf-8")
    _update_asset_map(asset_map_path, _asset_map_block(contract))
    return {
        "contract": contract,
        "contract_path": str(contract_path),
        "markdown_path": str(markdown_path),
        "asset_map_path": str(asset_map_path),
    }
