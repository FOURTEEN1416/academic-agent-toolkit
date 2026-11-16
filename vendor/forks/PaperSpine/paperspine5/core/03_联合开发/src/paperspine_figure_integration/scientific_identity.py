"""Hash-bound scientific-identity repair and post-assembly completion receipts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .contracts import ContractError, load_json, write_json_atomic


IDENTITY_REPAIR_REASON = "scientific_identity_error"
CANDIDATE_AUDIT_VERSION = "1.0"
REQUIRED_CANDIDATE_SURFACES = (
    "final_pixels",
    "editable_source",
    "caption",
    "lineage_receipt",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def requires_identity_repair(request: dict[str, Any]) -> bool:
    return IDENTITY_REPAIR_REASON in request.get("repair_reasons", [])


def _candidate_local(candidate_dir: Path, value: Any, field: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{field}.path must be non-empty text")
    path = Path(value)
    if not path.is_absolute():
        path = candidate_dir / path
    path = path.resolve()
    try:
        path.relative_to(candidate_dir.resolve())
    except ValueError as exc:
        raise ContractError(f"{field}.path escapes the candidate directory: {path}") from exc
    if not path.is_file():
        raise ContractError(f"{field}.path does not exist: {path}")
    return path


def _validate_surface_flags(surface: Any, field: str) -> dict[str, Any]:
    if not isinstance(surface, dict):
        raise ContractError(f"{field} must be an object")
    if surface.get("canonical_name_consistent") is not True:
        raise ContractError(f"{field}.canonical_name_consistent must be true")
    if surface.get("forbidden_names_absent") is not True:
        raise ContractError(f"{field}.forbidden_names_absent must be true")
    return dict(surface)


def validate_candidate_identity_audit(
    request: dict[str, Any],
    *,
    candidate_dir: Path,
    publication_source: Path,
    editable_source: Path | None,
    authoring_report_path: Path,
    authoring_report: dict[str, Any],
) -> dict[str, Any] | None:
    """Verify a repaired candidate's independent, hash-bound identity receipt."""
    if not requires_identity_repair(request):
        return None
    identity = request.get("scientific_identity")
    if not isinstance(identity, dict) or identity.get("authority_status") != "verified":
        raise ContractError(
            f"{request.get('figure_id')} identity repair is BLOCKED without verified authority"
        )
    if authoring_report.get("scientific_identity") != identity:
        raise ContractError(
            f"{request['figure_id']} authoring report changed the scientific_identity lock"
        )
    producer_identity = str(authoring_report.get("producer_identity") or "").strip()
    if not producer_identity or producer_identity == "UNASSIGNED":
        raise ContractError(f"{request['figure_id']} candidate producer identity is unverified")

    audit_path = candidate_dir / "identity_audit.json"
    if not audit_path.is_file():
        raise ContractError(f"{request['figure_id']} identity_audit.json is required")
    audit = load_json(audit_path)
    if (
        audit.get("schema_version") != CANDIDATE_AUDIT_VERSION
        or audit.get("status") != "PASS"
        or audit.get("figure_id") != request["figure_id"]
        or audit.get("scientific_identity") != identity
    ):
        raise ContractError(f"{request['figure_id']} identity audit header or authority lock is invalid")
    reviewer = audit.get("reviewer")
    reviewer_identity = str((reviewer or {}).get("identity") or "").strip()
    if (reviewer or {}).get("role") != "scientific_identity_reviewer" or not reviewer_identity:
        raise ContractError(f"{request['figure_id']} scientific identity reviewer is missing")
    if reviewer_identity.casefold() == producer_identity.casefold():
        raise ContractError(f"{request['figure_id']} identity reviewer cannot be the candidate producer")

    surfaces = audit.get("surfaces")
    if not isinstance(surfaces, dict) or set(surfaces) != set(REQUIRED_CANDIDATE_SURFACES):
        raise ContractError(
            f"{request['figure_id']} identity audit must cover {list(REQUIRED_CANDIDATE_SURFACES)}"
        )
    publication_source = publication_source.resolve()
    expected_editable = (
        editable_source.resolve()
        if editable_source is not None
        else publication_source
        if publication_source.suffix.lower() == ".svg"
        else None
    )
    if expected_editable is None:
        raise ContractError(
            f"{request['figure_id']} identity repair requires an editable source for cross-surface audit"
        )

    normalized_surfaces: dict[str, Any] = {}
    for surface_name, expected_path in (
        ("final_pixels", publication_source),
        ("editable_source", expected_editable),
        ("lineage_receipt", authoring_report_path.resolve()),
    ):
        field = f"{request['figure_id']}.identity_audit.surfaces.{surface_name}"
        surface = _validate_surface_flags(surfaces[surface_name], field)
        declared_path = _candidate_local(candidate_dir, surface.get("path"), field)
        if declared_path != expected_path:
            raise ContractError(f"{field}.path does not match the selected artifact")
        actual_sha = _sha256(declared_path)
        if str(surface.get("sha256") or "").lower() != actual_sha:
            raise ContractError(f"{field}.sha256 does not match the selected artifact")
        normalized_surfaces[surface_name] = {
            **surface,
            "path": str(declared_path),
            "sha256": actual_sha,
        }

    caption_field = f"{request['figure_id']}.identity_audit.surfaces.caption"
    caption = _validate_surface_flags(surfaces["caption"], caption_field)
    caption_sha = _text_sha256(request["caption"])
    if str(caption.get("sha256") or "").lower() != caption_sha:
        raise ContractError(f"{caption_field}.sha256 does not bind the request caption")
    normalized_surfaces["caption"] = {**caption, "sha256": caption_sha}
    return {
        "schema_version": CANDIDATE_AUDIT_VERSION,
        "status": "PASS",
        "audit_path": str(audit_path.resolve()),
        "audit_sha256": _sha256(audit_path),
        "reviewer": {"role": "scientific_identity_reviewer", "identity": reviewer_identity},
        "producer_identity": producer_identity,
        "scientific_identity": identity,
        "surfaces": normalized_surfaces,
    }


def write_identity_completion_receipt(
    *,
    output_dir: Path,
    body_contract_path: Path,
    requests: dict[str, Any],
    records: list[dict[str, Any]],
) -> Path | None:
    """Bind the assembled body contract as the fifth identity surface."""
    request_by_id = {item["figure_id"]: item for item in requests["figures"]}
    record_by_id = {item["figure_id"]: item for item in records}
    figures: list[dict[str, Any]] = []
    for figure_id, request in request_by_id.items():
        if (
            not requires_identity_repair(request)
            or request.get("publication_role", "main") == "omit"
        ):
            continue
        evidence = record_by_id[figure_id].get("identity_audit")
        if not isinstance(evidence, dict) or evidence.get("status") != "PASS":
            raise ContractError(f"{figure_id} identity completion is missing candidate audit evidence")
        figures.append(
            {
                "figure_id": figure_id,
                "status": "PASS",
                "scientific_identity": request["scientific_identity"],
                "surfaces": {
                    **evidence["surfaces"],
                    "body_contract": {
                        "path": body_contract_path.resolve().relative_to(output_dir.resolve()).as_posix(),
                        "sha256": _sha256(body_contract_path),
                        "canonical_name_consistent": True,
                        "forbidden_names_absent": True,
                    },
                },
                "candidate_identity_audit": {
                    "path": evidence["audit_path"],
                    "sha256": evidence["audit_sha256"],
                },
            }
        )
    if not figures:
        return None
    receipt = {
        "schema_version": "1.0",
        "contract_type": "paperspine.figure.identity-completion",
        "status": "PASS",
        "body_contract_sha256": _sha256(body_contract_path),
        "figures": figures,
    }
    payload = json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    receipt["receipt_sha256"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return write_json_atomic(output_dir / "figure_identity_completion_receipt.json", receipt)
