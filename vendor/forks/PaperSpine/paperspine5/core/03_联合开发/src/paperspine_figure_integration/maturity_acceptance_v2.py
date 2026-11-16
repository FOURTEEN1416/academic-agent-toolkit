"""Protocol-v2 target adaptation evaluator.

This module intentionally does not modify or reinterpret the frozen v1
evaluator.  V2 loads a protocol-pinned target profile catalog, requires one
finding for every registered operator, binds every finding to the evaluated
task/material/build subject and authoritative artifact bytes, and recomputes
the operator result from those bytes.  Producer/reviewer summaries are never
accepted as target-compliance evidence.
"""

from __future__ import annotations

import copy
import hashlib
import json
import posixpath
import re
import zipfile
from datetime import datetime
from xml.etree import ElementTree
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator

from . import maturity_acceptance as v1
from .canonical_artifacts import validate_surface_receipt


ROOT = Path(__file__).resolve().parents[3]
TARGET_REVIEW_SCHEMA_PATH = (
    ROOT / "03_联合开发" / "contracts" / "maturity-target-review-evidence-v2.schema.json"
)
PROTOCOL_SCHEMA_PATH = (
    ROOT / "03_联合开发" / "contracts" / "maturity-acceptance-protocol-v2.schema.json"
)
EVALUATOR_SCHEMA_PATH = (
    ROOT / "03_联合开发" / "contracts" / "maturity-evaluator-receipt-v2.schema.json"
)
SURFACE_RECEIPT_SCHEMA_PATH = (
    ROOT / "03_联合开发" / "contracts" / "surface-receipt.schema.json"
)
CANONICAL_SURFACE_ADAPTER_PATH = Path(__file__).with_name("canonical_artifacts.py")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
EVALUATOR_PIN_PATHS = {
    "evaluator_code_sha256": Path(__file__).resolve(),
    "evaluator_schema_sha256": EVALUATOR_SCHEMA_PATH,
    "protocol_schema_sha256": PROTOCOL_SCHEMA_PATH,
    "target_review_schema_sha256": TARGET_REVIEW_SCHEMA_PATH,
    "canonical_surface_adapter_sha256": CANONICAL_SURFACE_ADAPTER_PATH,
    "surface_receipt_schema_sha256": SURFACE_RECEIPT_SCHEMA_PATH,
}
V2_ALWAYS_REQUIRED_EVIDENCE = v1.ALWAYS_REQUIRED_EVIDENCE + (
    "pdf_figure_receipt",
    "fixture_freeze_receipt",
    "bibliography_source_receipt",
)
V2_CONDITIONAL_REQUIRED_EVIDENCE = dict(v1.CONDITIONAL_REQUIRED_EVIDENCE)


class MaturityAcceptanceV2Error(ValueError):
    """Raised when target evidence is incomplete, forged, or stale."""


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _without_hash(payload: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(payload)
    result.pop("receipt_sha256", None)
    return result


def _resolve_protocol_path(protocol: dict[str, Any], value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path.resolve()
    return (ROOT / path).resolve()


def protocol_sha256_v2(protocol: dict[str, Any]) -> str:
    """Return the semantic hash of a v2 protocol without its self-hash field."""

    subject = copy.deepcopy(protocol)
    subject.pop("protocol_sha256", None)
    return canonical_sha256(subject)


def current_evaluator_hashes_v2(protocol: dict[str, Any]) -> dict[str, str]:
    """Resolve every source/schema dependency that can change v2 semantics."""

    hashes = {
        field: file_sha256(path) for field, path in EVALUATOR_PIN_PATHS.items()
    }
    catalog_ref = protocol.get("target_profile_catalog")
    if not isinstance(catalog_ref, dict):
        raise MaturityAcceptanceV2Error("protocol target profile catalog is absent")
    catalog_path = _resolve_protocol_path(protocol, str(catalog_ref.get("path", "")))
    if not catalog_path.is_file():
        raise MaturityAcceptanceV2Error("protocol target profile catalog is missing")
    hashes["target_profile_catalog_sha256"] = file_sha256(catalog_path)
    return hashes


def _schema_errors_v2(
    value: dict[str, Any], schema_path: Path, label: str
) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(
            schema, format_checker=Draft202012Validator.FORMAT_CHECKER
        ).iter_errors(value),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        error = errors[0]
        location = ".".join(str(item) for item in error.absolute_path) or "root"
        raise MaturityAcceptanceV2Error(
            f"{label} schema violation at {location}: {error.message}"
        )


def _validate_protocol_structure_v2(protocol: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(protocol, dict):
        raise MaturityAcceptanceV2Error("protocol v2 must be an object")
    _schema_errors_v2(protocol, PROTOCOL_SCHEMA_PATH, "protocol v2")
    evaluator = protocol["evaluator_requirements"]
    if tuple(evaluator["required_evidence_types"]) != V2_ALWAYS_REQUIRED_EVIDENCE:
        raise MaturityAcceptanceV2Error(
            "protocol v2 always-required evidence differs from evaluator contract"
        )
    conditional = {
        mode: tuple(evidence_types)
        for mode, evidence_types in evaluator[
            "conditional_required_evidence_types"
        ].items()
    }
    if conditional != V2_CONDITIONAL_REQUIRED_EVIDENCE:
        raise MaturityAcceptanceV2Error(
            "protocol v2 conditional evidence differs from evaluator contract"
        )
    sample_ids = [sample["sample_id"] for sample in protocol["samples"]]
    if len(sample_ids) != len(set(sample_ids)):
        raise MaturityAcceptanceV2Error("protocol v2 sample_id values must be unique")
    for target in protocol["coverage_requirements"]["target_templates"]:
        load_protocol_target_profile(protocol, target)
    return copy.deepcopy(protocol)


def load_protocol_target_profile(
    protocol: dict[str, Any], target_template: str
) -> tuple[dict[str, Any], str]:
    catalog_ref = protocol.get("target_profile_catalog")
    if not isinstance(catalog_ref, dict):
        raise MaturityAcceptanceV2Error("protocol target profile catalog is absent")
    path = _resolve_protocol_path(protocol, str(catalog_ref.get("path", "")))
    if not path.is_file():
        raise MaturityAcceptanceV2Error("protocol target profile catalog is missing")
    actual_sha256 = file_sha256(path)
    if catalog_ref.get("sha256") != actual_sha256:
        raise MaturityAcceptanceV2Error("protocol target profile catalog hash drift")
    catalog = json.loads(path.read_text(encoding="utf-8"))
    if catalog.get("contract") != "paperspine5.fixture-target-rule-profiles":
        raise MaturityAcceptanceV2Error("target profile catalog contract is invalid")
    try:
        profile = catalog["profiles"][target_template]
    except (KeyError, TypeError) as exc:
        raise MaturityAcceptanceV2Error("target template is absent from the catalog") from exc
    return copy.deepcopy(profile), actual_sha256


def validate_protocol_design_v2(protocol: dict[str, Any]) -> dict[str, Any]:
    normalized = _validate_protocol_structure_v2(protocol)
    if normalized["status"] != "draft_unfrozen":
        raise MaturityAcceptanceV2Error("v2 design is not an unfrozen draft")
    if (
        normalized["protocol_sha256"] is not None
        or normalized["frozen_at"] is not None
    ):
        raise MaturityAcceptanceV2Error("v2 draft cannot claim a freeze hash/time")
    return normalized


def validate_preregistered_protocol_v2(
    protocol: dict[str, Any], *, now: datetime | None = None
) -> dict[str, Any]:
    """Reject drafts, future freeze times, and any semantic dependency drift."""

    normalized = _validate_protocol_structure_v2(protocol)
    if normalized["status"] != "design_frozen":
        raise MaturityAcceptanceV2Error(
            "protocol v2 is draft_unfrozen and cannot accept fixtures or results"
        )
    try:
        frozen_at = datetime.fromisoformat(
            normalized["frozen_at"].replace("Z", "+00:00")
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise MaturityAcceptanceV2Error(
            "protocol v2 frozen_at must be an ISO-8601 timestamp"
        ) from exc
    if frozen_at.tzinfo is None:
        raise MaturityAcceptanceV2Error(
            "protocol v2 frozen_at must include a timezone"
        )
    if frozen_at > (now or datetime.now().astimezone()):
        raise MaturityAcceptanceV2Error(
            "protocol v2 frozen_at cannot be in the future"
        )
    if normalized["protocol_sha256"] != protocol_sha256_v2(normalized):
        raise MaturityAcceptanceV2Error(
            "protocol v2 protocol_sha256 does not bind the frozen design"
        )
    current = current_evaluator_hashes_v2(normalized)
    evaluator = normalized["evaluator_requirements"]
    for field in EVALUATOR_PIN_PATHS:
        if evaluator[field] != current[field]:
            raise MaturityAcceptanceV2Error(
                f"protocol v2 {field} differs from current source"
            )
    if normalized["target_profile_catalog"]["sha256"] != current[
        "target_profile_catalog_sha256"
    ]:
        raise MaturityAcceptanceV2Error(
            "protocol v2 target profile catalog hash differs from current source"
        )
    return normalized


def validate_independent_evaluator_receipt_v2(
    protocol: dict[str, Any], receipt: dict[str, Any]
) -> dict[str, Any]:
    """Validate receipt identity pins before any result can be consumed."""

    normalized_protocol = validate_preregistered_protocol_v2(protocol)
    if not isinstance(receipt, dict):
        raise MaturityAcceptanceV2Error("evaluator receipt v2 must be an object")
    _schema_errors_v2(receipt, EVALUATOR_SCHEMA_PATH, "evaluator receipt v2")
    if receipt["receipt_sha256"] != canonical_sha256(_without_hash(receipt)):
        raise MaturityAcceptanceV2Error("evaluator receipt v2 self-hash drift")
    if receipt["protocol_sha256"] != normalized_protocol["protocol_sha256"]:
        raise MaturityAcceptanceV2Error("evaluator receipt v2 protocol binding drift")
    expected = current_evaluator_hashes_v2(normalized_protocol)
    evaluator = normalized_protocol["evaluator_requirements"]
    for field in EVALUATOR_PIN_PATHS:
        if receipt[field] != evaluator[field] or receipt[field] != expected[field]:
            raise MaturityAcceptanceV2Error(
                f"evaluator receipt v2 {field} binding drift"
            )
    if receipt["target_profile_catalog_sha256"] != expected[
        "target_profile_catalog_sha256"
    ]:
        raise MaturityAcceptanceV2Error(
            "evaluator receipt v2 target profile catalog binding drift"
        )
    sample = _sample_v2(normalized_protocol, receipt["sample_id"])
    if receipt["entry_mode"] != sample["entry_mode"]:
        raise MaturityAcceptanceV2Error(
            "evaluator receipt v2 entry mode differs from registered case"
        )
    required_evidence = set(V2_ALWAYS_REQUIRED_EVIDENCE)
    required_evidence.update(
        V2_CONDITIONAL_REQUIRED_EVIDENCE.get(sample["figure_mode"], ())
    )
    if set(receipt["evidence"]) != required_evidence:
        raise MaturityAcceptanceV2Error(
            "evaluator receipt v2 evidence set is incomplete or unknown"
        )
    for evidence_name, ref in receipt["evidence"].items():
        if ref["subject"] != receipt["subject"]:
            raise MaturityAcceptanceV2Error(
                f"evaluator receipt v2 evidence subject drift: {evidence_name}"
            )
        path = Path(ref["path"]).resolve()
        if not path.is_file() or file_sha256(path) != ref["sha256"]:
            raise MaturityAcceptanceV2Error(
                f"evaluator receipt v2 evidence hash drift: {evidence_name}"
            )
    fixture_payload = _typed_json(
        Path(receipt["evidence"]["fixture_freeze_receipt"]["path"]).resolve()
    )
    if fixture_payload.get("receipt_sha256") != receipt["fixture_receipt_sha256"]:
        raise MaturityAcceptanceV2Error(
            "evaluator receipt v2 fixture evidence/top-level binding drift"
        )
    if receipt["producer_identity"] == receipt["evaluator_identity"]:
        raise MaturityAcceptanceV2Error(
            "evaluator receipt v2 producer cannot evaluate its own result"
        )
    return copy.deepcopy(receipt)


def _sample_v2(protocol: dict[str, Any], sample_id: str) -> dict[str, Any]:
    matches = [
        sample for sample in protocol["samples"] if sample["sample_id"] == sample_id
    ]
    if len(matches) != 1:
        raise MaturityAcceptanceV2Error(
            f"sample is not uniquely registered in protocol v2: {sample_id}"
        )
    return matches[0]


def _parse_time_v2(value: Any, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise MaturityAcceptanceV2Error(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise MaturityAcceptanceV2Error(f"{field} must include a timezone")
    return parsed


def build_fixture_freeze_receipt_v2(
    protocol: dict[str, Any],
    *,
    sample_id: str,
    fixture_root: str | Path,
    fixture_provenance: str,
    freezer_identity: str,
    materializer_path: str | Path,
    bound_at: str,
    first_run_not_before: str,
    inventory_root: str | Path | None = None,
) -> dict[str, Any]:
    """Freeze every v2 fixture byte without creating a product/evaluator result."""

    normalized = validate_preregistered_protocol_v2(protocol)
    sample = _sample_v2(normalized, sample_id)
    if fixture_provenance != sample["fixture_provenance"]:
        raise MaturityAcceptanceV2Error(
            "fixture v2 provenance differs from preregistration"
        )
    if not freezer_identity or freezer_identity == "producer":
        raise MaturityAcceptanceV2Error(
            "fixture v2 freezer must be a named host authority"
        )
    root = Path(fixture_root).resolve()
    physical_root = Path(inventory_root).resolve() if inventory_root else root
    entries = v1._tree_entries(  # noqa: SLF001 - v1 inventory is immutable compatibility
        physical_root
    )
    materializer = Path(materializer_path).resolve()
    if not materializer.is_file():
        raise MaturityAcceptanceV2Error("fixture v2 materializer source is missing")
    frozen = _parse_time_v2(normalized["frozen_at"], "frozen_at")
    bound = _parse_time_v2(bound_at, "bound_at")
    first_run = _parse_time_v2(first_run_not_before, "first_run_not_before")
    if not (frozen <= bound <= first_run):
        raise MaturityAcceptanceV2Error(
            "protocol v2 freeze must precede fixture freeze and runs"
        )
    receipt = {
        "contract": "paperspine5.maturity-fixture-freeze-v2",
        "contract_version": "2.0",
        "authority": "paperspine5-authenticated-host-fixture-freezer-v2",
        "sample_id": sample_id,
        "fixture_family_id": sample["fixture_family_id"],
        "fixture_provenance": fixture_provenance,
        "benchmark_lineage": sample["benchmark_lineage"],
        "author_facts_are_fixture_only": True,
        "protocol_sha256": normalized["protocol_sha256"],
        "materializer_path": str(materializer),
        "materializer_sha256": file_sha256(materializer),
        "fixture_root": str(root),
        "entries": entries,
        "file_count": len(entries),
        "total_bytes": sum(item["size_bytes"] for item in entries),
        "fixture_tree_sha256": canonical_sha256(entries),
        "material_snapshot_sha256": canonical_sha256(
            {"sample_id": sample_id, "entries": entries}
        ),
        "freezer_identity": freezer_identity,
        "bound_at": bound_at,
        "first_run_not_before": first_run_not_before,
        "external_action_authorized": False,
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    return receipt


def verify_fixture_freeze_receipt_v2(
    protocol: dict[str, Any],
    receipt: dict[str, Any],
    *,
    inventory_root: str | Path | None = None,
) -> dict[str, Any]:
    normalized = validate_preregistered_protocol_v2(protocol)
    required = {
        "contract",
        "contract_version",
        "authority",
        "sample_id",
        "fixture_family_id",
        "fixture_provenance",
        "benchmark_lineage",
        "author_facts_are_fixture_only",
        "protocol_sha256",
        "materializer_path",
        "materializer_sha256",
        "fixture_root",
        "entries",
        "file_count",
        "total_bytes",
        "fixture_tree_sha256",
        "material_snapshot_sha256",
        "freezer_identity",
        "bound_at",
        "first_run_not_before",
        "external_action_authorized",
        "receipt_sha256",
    }
    if not isinstance(receipt, dict) or set(receipt) != required:
        raise MaturityAcceptanceV2Error(
            "fixture freeze v2 fields are missing or unknown"
        )
    sample = _sample_v2(normalized, receipt["sample_id"])
    if (
        receipt["contract"] != "paperspine5.maturity-fixture-freeze-v2"
        or receipt["contract_version"] != "2.0"
        or receipt["authority"]
        != "paperspine5-authenticated-host-fixture-freezer-v2"
        or receipt["fixture_family_id"] != sample["fixture_family_id"]
        or receipt["fixture_provenance"] != sample["fixture_provenance"]
        or receipt["benchmark_lineage"] != sample["benchmark_lineage"]
        or receipt["author_facts_are_fixture_only"] is not True
        or receipt["protocol_sha256"] != normalized["protocol_sha256"]
        or not SHA256_RE.fullmatch(str(receipt["materializer_sha256"]))
        or receipt["external_action_authorized"] is not False
        or receipt["receipt_sha256"] != canonical_sha256(_without_hash(receipt))
    ):
        raise MaturityAcceptanceV2Error(
            "fixture freeze v2 subject/hash/provenance is invalid"
        )
    materializer = Path(receipt["materializer_path"]).resolve()
    if (
        not materializer.is_file()
        or file_sha256(materializer) != receipt["materializer_sha256"]
    ):
        raise MaturityAcceptanceV2Error("fixture v2 materializer hash drift")
    physical_root = (
        Path(inventory_root).resolve()
        if inventory_root
        else Path(receipt["fixture_root"]).resolve()
    )
    entries = v1._tree_entries(physical_root)  # noqa: SLF001
    if entries != receipt["entries"]:
        raise MaturityAcceptanceV2Error("fixture v2 bytes drifted after freeze")
    if (
        receipt["file_count"] != len(entries)
        or receipt["total_bytes"]
        != sum(item["size_bytes"] for item in entries)
        or receipt["fixture_tree_sha256"] != canonical_sha256(entries)
        or receipt["material_snapshot_sha256"]
        != canonical_sha256({"sample_id": receipt["sample_id"], "entries": entries})
    ):
        raise MaturityAcceptanceV2Error(
            "fixture v2 inventory totals or hashes are invalid"
        )
    frozen = _parse_time_v2(normalized["frozen_at"], "frozen_at")
    bound = _parse_time_v2(receipt["bound_at"], "bound_at")
    first_run = _parse_time_v2(
        receipt["first_run_not_before"], "first_run_not_before"
    )
    if not (frozen <= bound <= first_run):
        raise MaturityAcceptanceV2Error(
            "fixture v2 freeze timestamps are out of order"
        )
    return copy.deepcopy(receipt)


def _active_tex(path: Path) -> str:
    lines = []
    for line in path.read_text(encoding="utf-8", errors="strict").splitlines():
        active = re.split(r"(?<!\\)%", line, maxsplit=1)[0]
        lines.append(active)
    return "\n".join(lines)


def _bib_keys(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8", errors="strict")
    return set(re.findall(r"(?im)^@\w+\s*\{\s*([^,\s]+)", text))


def _typed_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise MaturityAcceptanceV2Error(f"typed evidence is not an object: {path}")
    if "receipt_sha256" in payload and payload["receipt_sha256"] != canonical_sha256(
        _without_hash(payload)
    ):
        raise MaturityAcceptanceV2Error(f"typed evidence self-hash drift: {path}")
    return payload


def _pdf_page_count(path: Path) -> int:
    import fitz

    document = fitz.open(path)
    try:
        for index in range(document.page_count):
            document.load_page(index).get_pixmap(matrix=fitz.Matrix(0.1, 0.1))
        return document.page_count
    finally:
        document.close()


def _source_visual_image(path: Path):
    from PIL import Image

    if path.suffix.lower() == ".pdf":
        import fitz

        document = fitz.open(path)
        try:
            page = document.load_page(0)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            return Image.frombytes(
                "RGB", (pixmap.width, pixmap.height), pixmap.samples
            )
        finally:
            document.close()
    with Image.open(path) as image:
        return image.convert("RGB").copy()


def _visual_identity_matches(actual, expected) -> bool:
    from PIL import Image, ImageChops, ImageStat

    target_size = (192, 192)
    actual_normalized = actual.convert("RGB").resize(
        target_size, Image.Resampling.LANCZOS
    )
    expected_normalized = expected.convert("RGB").resize(
        target_size, Image.Resampling.LANCZOS
    )
    difference = ImageChops.difference(actual_normalized, expected_normalized)
    mean_absolute_error = sum(ImageStat.Stat(difference).mean) / 3
    changed_fraction = sum(
        1 for pixel in difference.getdata() if max(pixel) > 24
    ) / (target_size[0] * target_size[1])
    return mean_absolute_error <= 10.0 and changed_fraction <= 0.08


def _pdf_has_two_text_columns(path: Path) -> bool:
    import fitz

    document = fitz.open(path)
    try:
        if document.page_count == 0:
            return False
        page = document.load_page(0)
        midpoint = page.rect.width / 2
        words = page.get_text("words")
        left = any((word[0] + word[2]) / 2 < midpoint * 0.75 for word in words)
        right = any((word[0] + word[2]) / 2 > midpoint * 1.25 for word in words)
        return left and right
    finally:
        document.close()


def _docx_parts(path: Path) -> tuple[str, dict[str, bytes], dict[str, str], list[str]]:
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise MaturityAcceptanceV2Error("DOCX ZIP integrity failed")
        names = archive.namelist()
        document = archive.read("word/document.xml").decode("utf-8", errors="strict")
        media = {
            name: archive.read(name)
            for name in names
            if name.startswith("word/media/") and not name.endswith("/")
        }
        relationships_xml = archive.read("word/_rels/document.xml.rels")
    relationships_root = ElementTree.fromstring(relationships_xml)
    relationships = {
        item.attrib["Id"]: posixpath.normpath(
            posixpath.join("word", item.attrib["Target"])
        )
        for item in relationships_root
        if item.attrib.get("Type", "").endswith("/image")
    }
    document_root = ElementTree.fromstring(document.encode("utf-8"))
    relationship_namespace = (
        "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
    )
    drawing_namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}drawing"
    blip_namespace = "{http://schemas.openxmlformats.org/drawingml/2006/main}blip"
    embedded_ids = []
    for drawing in document_root.iter(drawing_namespace):
        embedded_ids.extend(
            blip.attrib[relationship_namespace]
            for blip in drawing.iter(blip_namespace)
            if relationship_namespace in blip.attrib
        )
    return document, media, relationships, embedded_ids


def _artifact_ledger_preserved(path: Path) -> bool:
    ledger = _typed_json(path)
    section_roles = set(ledger.get("section_roles_present", []))
    expected = ledger.get("expected_figure_count")
    delivered = ledger.get("delivered_figure_count")
    source_ids = ledger.get("figure_source_ids", [])
    hashes = ledger.get("figure_source_hashes", {})
    return bool(
        ledger.get("material_coverage") == 1.0
        and {"methods", "results"}.issubset(section_roles)
        and isinstance(expected, int)
        and delivered == expected
        and len(source_ids) == len(set(source_ids)) == expected
        and set(hashes) == set(source_ids)
        and all(isinstance(value, str) and SHA256_RE.fullmatch(value) for value in hashes.values())
        and ledger.get("reference_count", 0) > 0
    )


def _local_surfaces(context: dict[str, Path], *, visible_word_media: bool) -> bool:
    if _pdf_page_count(context["pdf"]) <= 0:
        return False
    document, _media, _relationships, _embedded_ids = _docx_parts(context["docx"])
    if not document:
        return False
    word_surface = _canonical_word_surface(context)
    if word_surface is None:
        return False
    if visible_word_media:
        return _word_media_bound_and_visible(context, word_surface)
    return True


def _canonical_word_surface(context: dict[str, Path]) -> dict[str, Any] | None:
    manifest = _typed_json(context["package_manifest"])
    ledger = _typed_json(context["artifact_ledger"])
    subject = ledger.get("subject")
    if (
        manifest.get("contract") != "paperspine5.maturity-package-evidence-v2"
        or not isinstance(subject, dict)
        or manifest.get("subject") != subject
    ):
        return None
    run_root = Path(str(manifest.get("run_root") or "")).resolve()
    if not run_root.is_dir():
        return None
    for path in context.values():
        try:
            path.resolve().relative_to(run_root)
        except ValueError:
            return None
    files = manifest.get("files")
    if not isinstance(files, list):
        return None
    by_role = {
        item.get("role"): item for item in files if isinstance(item, dict)
    }
    for role in ("pdf", "docx"):
        item = by_role.get(role)
        if (
            not isinstance(item, dict)
            or Path(str(item.get("path") or "")).resolve() != context[role]
            or item.get("sha256") != file_sha256(context[role])
        ):
            return None
    receipt = _typed_json(context["render_receipt"])
    validation = validate_surface_receipt(
        run_root,
        receipt,
        task_id=str(subject.get("task_id") or ""),
        revision_id=str(subject.get("revision_id") or ""),
    )
    if (
        validation.get("status") != "PASS"
        or validation.get("surface_kind") != "word"
        or validation.get("source_path") != context["docx"]
        or not validation.get("page_paths")
    ):
        return None
    return {"receipt": receipt, **validation}


def _docx_drawings_are_structurally_visible(document: str) -> bool:
    root = ElementTree.fromstring(document.encode("utf-8"))
    w = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    wp = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"
    drawings = []
    for run in root.iter(f"{w}r"):
        hidden = any(True for _item in run.iter(f"{w}vanish"))
        for drawing in run.iter(f"{w}drawing"):
            extent = next(iter(drawing.iter(f"{wp}extent")), None)
            doc_properties = next(iter(drawing.iter(f"{wp}docPr")), None)
            try:
                width = int(extent.attrib.get("cx", "0")) if extent is not None else 0
                height = int(extent.attrib.get("cy", "0")) if extent is not None else 0
            except ValueError:
                return False
            if (
                hidden
                or width <= 0
                or height <= 0
                or (
                    doc_properties is not None
                    and str(doc_properties.attrib.get("hidden", "0")).casefold()
                    in {"1", "true"}
                )
            ):
                return False
            drawings.append(drawing)
    return bool(drawings)


def _word_media_bound_and_visible(
    context: dict[str, Path], word_surface: dict[str, Any] | None = None
) -> bool:
    document, media, relationships, embedded_ids = _docx_parts(context["docx"])
    if not _docx_drawings_are_structurally_visible(document):
        return False
    if len(embedded_ids) != len(set(embedded_ids)):
        return False
    referenced_parts = []
    for relationship_id in embedded_ids:
        part = relationships.get(relationship_id)
        if part is None or part not in media:
            return False
        referenced_parts.append(part)
    if set(referenced_parts) != set(media):
        return False
    if not referenced_parts or any(Path(part).suffix.lower() != ".png" for part in referenced_parts):
        return False
    ledger = _typed_json(context["artifact_ledger"])
    source_ids = ledger.get("figure_source_ids", [])
    source_hashes = ledger.get("figure_source_hashes", {})
    deliveries = ledger.get("figure_word_media", [])
    if len(deliveries) != len(source_ids) or len(referenced_parts) != len(source_ids):
        return False
    delivery_by_source = {item.get("source_id"): item for item in deliveries}
    if set(delivery_by_source) != set(source_ids):
        return False
    if word_surface is None:
        word_surface = _canonical_word_surface(context)
    if word_surface is None:
        return False
    receipt = word_surface["receipt"]
    page_records = {
        item.get("sha256"): item
        for item in receipt.get("pages", [])
        if isinstance(item, dict)
    }
    page_paths = {
        file_sha256(path): path for path in word_surface.get("page_paths", [])
    }
    from io import BytesIO

    from PIL import Image

    for source_id in source_ids:
        delivery = delivery_by_source[source_id]
        part = delivery.get("media_part")
        if (
            delivery.get("source_sha256") != source_hashes.get(source_id)
            or part not in referenced_parts
            or delivery.get("media_sha256")
            != hashlib.sha256(media[part]).hexdigest()
            or not delivery.get("render_region_id")
        ):
            return False
        page_sha256 = delivery.get("page_image_sha256")
        page_record = page_records.get(page_sha256)
        page_path = page_paths.get(page_sha256)
        bbox = delivery.get("bbox_pixels")
        if (
            not isinstance(page_record, dict)
            or page_path is None
            or not isinstance(bbox, list)
            or len(bbox) != 4
            or any(isinstance(value, bool) or not isinstance(value, int) for value in bbox)
        ):
            return False
        try:
            with Image.open(page_path) as page_image:
                page_rgb = page_image.convert("RGB")
                left, top, right, bottom = bbox
                if (
                    left < 0
                    or top < 0
                    or right <= left
                    or bottom <= top
                    or right > page_rgb.width
                    or bottom > page_rgb.height
                ):
                    return False
                crop = page_rgb.crop((left, top, right, bottom))
            with Image.open(BytesIO(media[part])) as media_image:
                if not _visual_identity_matches(crop, media_image.convert("RGB")):
                    return False
        except (OSError, ValueError):
            return False
    return True


def _active_dependencies_resolve(context: dict[str, Path]) -> bool:
    tex_path = context["tex_source"]
    active = _active_tex(tex_path)
    root = tex_path.parent
    dependencies: list[Path] = []
    for command, value in re.findall(
        r"\\(input|include|includegraphics|bibliography|addbibresource)(?:\[[^]]*\])?\{([^}]+)\}",
        active,
    ):
        for item in value.split(","):
            candidate = item.strip()
            if command in {"input", "include"} and not Path(candidate).suffix:
                candidate += ".tex"
            elif command == "bibliography" and not Path(candidate).suffix:
                candidate += ".bib"
            dependencies.append((root / candidate).resolve())
    return bool(dependencies) and all(path.is_file() for path in dependencies)


def _fixture_bibliography_bound(context: dict[str, Path]) -> bool:
    fixture = _typed_json(context["fixture_freeze_receipt"])
    bibliography_source = _typed_json(context["bibliography_source_receipt"])
    bibliography_sha256 = file_sha256(context["bibliography"])
    entries = fixture.get("entries", [])
    entry_by_relative = {item.get("relative_path"): item for item in entries}
    fixture_root = Path(fixture.get("fixture_root", "")).resolve()
    bibliography_entry = entry_by_relative.get("references.bib")
    source_entry = entry_by_relative.get("bibliography-source.json")
    return bool(
        fixture.get("contract") == "paperspine5.maturity-fixture-freeze-v2"
        and fixture.get("authority") == "paperspine5-authenticated-host-fixture-freezer-v2"
        and bibliography_entry
        and source_entry
        and (fixture_root / "references.bib").resolve() == context["bibliography"]
        and bibliography_entry.get("sha256") == bibliography_sha256
        and bibliography_entry.get("size_bytes") == context["bibliography"].stat().st_size
        and (fixture_root / "bibliography-source.json").resolve()
        == context["bibliography_source_receipt"]
        and source_entry.get("sha256")
        == file_sha256(context["bibliography_source_receipt"])
        and bibliography_source.get("contract")
        == "paperspine5.fixture-bibliography-source"
        and bibliography_source.get("bibliography_sha256") == bibliography_sha256
        and bibliography_source.get("source_sha256")
        and all(
            record.get("key")
            and record.get("title")
            and re.fullmatch(r"\d{4}", str(record.get("year", "")))
            and re.fullmatch(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", record.get("doi", ""), re.IGNORECASE)
            for record in bibliography_source.get("records", [])
        )
    )


def _citations_bind_bibliography(context: dict[str, Path], *, ieee: bool) -> bool:
    if not _fixture_bibliography_bound(context):
        return False
    active = _active_tex(context["tex_source"])
    cited = {
        key.strip()
        for block in re.findall(r"\\cite\w*\{([^}]+)\}", active)
        for key in block.split(",")
        if key.strip()
    }
    if not cited or not cited.issubset(_bib_keys(context["bibliography"])):
        return False
    if not ieee:
        return True
    return bool(
        re.search(r"\\bibliographystyle\{IEEEtran\}", active)
        or re.search(r"\\usepackage(?:\[[^]]*\])?\{cite\}", active)
    )


def pdf_render_region_sha256(
    pdf_path: Path, page_index: int, bbox_points: list[float]
) -> tuple[str, int, float]:
    image, page_width = _pdf_region_image(pdf_path, page_index, bbox_points)
    payload = (
        f"{image.width}:{image.height}:".encode("ascii") + image.tobytes()
    )
    nonwhite = sum(1 for pixel in image.getdata() if min(pixel) < 245)
    return hashlib.sha256(payload).hexdigest(), nonwhite, page_width


def _pdf_region_image(pdf_path: Path, page_index: int, bbox_points: list[float]):
    import fitz
    from PIL import Image

    document = fitz.open(pdf_path)
    try:
        page = document.load_page(page_index)
        rectangle = fitz.Rect(*bbox_points)
        if rectangle.is_empty or not page.rect.contains(rectangle):
            raise MaturityAcceptanceV2Error("PDF figure bbox is outside its page")
        pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=rectangle, alpha=False)
        return (
            Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples),
            page.rect.width,
        )
    finally:
        document.close()


def _figure_placement_declared(context: dict[str, Path]) -> bool:
    active = _active_tex(context["tex_source"])
    ledger = _typed_json(context["artifact_ledger"])
    source_ids = ledger.get("figure_source_ids", [])
    source_hashes = ledger.get("figure_source_hashes", {})
    layouts = ledger.get("figure_pdf_layout", [])
    fixture = _typed_json(context["fixture_freeze_receipt"])
    fixture_root = Path(fixture.get("fixture_root", "")).resolve()
    fixture_entries = {
        item.get("relative_path"): item for item in fixture.get("entries", [])
    }
    declared = re.findall(
        r"\\begin\{(figure\*?)\}.*?\\includegraphics(?:\[[^]]*\])?\{[^}]+\}.*?\\end\{\1\}",
        active,
        flags=re.DOTALL,
    )
    declared_spans = ["double" if environment == "figure*" else "single" for environment in declared]
    layout_by_source = {item.get("source_id"): item for item in layouts}
    if (
        len(source_ids) != len(declared_spans)
        or len(layouts) != len(source_ids)
        or set(layout_by_source) != set(source_ids)
    ):
        return False
    receipt = _typed_json(context["pdf_figure_receipt"])
    if (
        receipt.get("contract") != "paperspine5.pdf-figure-render-evidence-v2"
        or receipt.get("authority") != "independent-pdf-layout-reviewer"
        or receipt.get("producer_identity") == receipt.get("reviewer_identity")
        or receipt.get("source_pdf_sha256") != file_sha256(context["pdf"])
    ):
        return False
    rendered = receipt.get("figures", [])
    rendered_by_source = {item.get("source_id"): item for item in rendered}
    if len(rendered) != len(source_ids) or set(rendered_by_source) != set(source_ids):
        return False
    for index, source_id in enumerate(source_ids):
        layout = layout_by_source[source_id]
        figure = rendered_by_source[source_id]
        if (
            layout.get("source_sha256") != source_hashes.get(source_id)
            or figure.get("source_sha256") != source_hashes.get(source_id)
            or layout.get("span") != declared_spans[index]
            or figure.get("span") != declared_spans[index]
        ):
            return False
        source_path = Path(layout.get("source_path", "")).resolve()
        try:
            source_relative = source_path.relative_to(fixture_root).as_posix()
        except ValueError:
            return False
        fixture_entry = fixture_entries.get(source_relative)
        if (
            not source_path.is_file()
            or file_sha256(source_path) != source_hashes.get(source_id)
            or not fixture_entry
            or fixture_entry.get("sha256") != source_hashes.get(source_id)
            or fixture_entry.get("size_bytes") != source_path.stat().st_size
        ):
            return False
        try:
            region_sha256, nonwhite, page_width = pdf_render_region_sha256(
                context["pdf"], figure["page_index"], figure["bbox_points"]
            )
            rendered_image, _page_width = _pdf_region_image(
                context["pdf"], figure["page_index"], figure["bbox_points"]
            )
            source_image = _source_visual_image(source_path)
        except (KeyError, IndexError, OSError, ValueError, MaturityAcceptanceV2Error):
            return False
        width = figure["bbox_points"][2] - figure["bbox_points"][0]
        span_valid = (
            width <= page_width * 0.52
            if figure["span"] == "single"
            else width >= page_width * 0.75
        )
        if (
            not span_valid
            or region_sha256 != figure.get("rendered_region_sha256")
            or nonwhite < figure.get("minimum_nonwhite_pixels", 1)
            or not _visual_identity_matches(rendered_image, source_image)
        ):
            return False
    return True


def _word_render_nonblank(context: dict[str, Path]) -> bool:
    word_surface = _canonical_word_surface(context)
    return bool(
        word_surface is not None
        and _word_media_bound_and_visible(context, word_surface)
    )


def _word_structure(context: dict[str, Path]) -> bool:
    document, _media, _relationships, _embedded_ids = _docx_parts(context["docx"])
    lowered = document.lower()
    return all(role in lowered for role in ("methods", "results", "references"))


def _operator_evaluators(profile: dict[str, Any]) -> dict[str, Callable[[dict[str, Path]], bool]]:
    maximum_pages = next(
        (
            check["maximum"]
            for check in profile["machine_checks"]
            if check["operator"] == "rendered_template_page_count_lte"
        ),
        0,
    )
    return {
        "active_document_class_equals_oup_authoring_template": lambda context: bool(
            re.search(
                r"\\documentclass(?:\[[^]]*\])?\{oup-authoring-template\}",
                _active_tex(context["tex_source"]),
            )
        ),
        "rendered_template_page_count_lte": lambda context: 0
        < _pdf_page_count(context["pdf"])
        <= maximum_pages,
        "methods_results_figures_references_hashes_preserved": lambda context: _artifact_ledger_preserved(
            context["artifact_ledger"]
        ),
        "pdf_and_docx_openable_with_visible_word_media": lambda context: _local_surfaces(
            context, visible_word_media=True
        ),
        "rendered_layout_matches_two_column_article_profile": lambda context: _pdf_has_two_text_columns(
            context["pdf"]
        ),
        "numeric_citations_bind_frozen_bibliography": lambda context: _citations_bind_bibliography(
            context, ieee=True
        ),
        "figure_single_or_double_column_placement_is_declared_and_rendered": _figure_placement_declared,
        "active_tex_dependencies_resolve": _active_dependencies_resolve,
        "active_citations_bind_frozen_bibliography": lambda context: _citations_bind_bibliography(
            context, ieee=False
        ),
        "material_figure_reference_hashes_preserved": lambda context: _artifact_ledger_preserved(
            context["artifact_ledger"]
        ),
        "pdf_and_docx_openable_and_rendered": lambda context: _local_surfaces(
            context, visible_word_media=False
        ),
        "docx_is_primary_local_delivery_surface": lambda context: _typed_json(
            context["package_manifest"]
        ).get("primary_surface")
        == "docx",
        "all_registered_figures_are_visible_supported_word_media": lambda context: _local_surfaces(
            context, visible_word_media=True
        ),
        "portable_word_render_contains_no_blank_figure_frames": _word_render_nonblank,
        "methods_results_figures_references_present_in_docx_and_pdf": lambda context: _word_structure(
            context
        )
        and _artifact_ledger_preserved(context["artifact_ledger"])
        and _pdf_page_count(context["pdf"]) > 0,
    }


def _validated_context(
    bindings: list[dict[str, Any]], authoritative_context: dict[str, dict[str, str]]
) -> dict[str, Path]:
    by_role: dict[str, Path] = {}
    for binding in bindings:
        role = binding["role"]
        if role in by_role:
            raise MaturityAcceptanceV2Error(f"duplicate artifact binding role: {role}")
        expected = authoritative_context.get(role)
        if expected is None:
            raise MaturityAcceptanceV2Error(f"unknown artifact binding role: {role}")
        path = Path(binding["path"]).resolve()
        if (
            str(path) != str(Path(expected["path"]).resolve())
            or binding["sha256"] != expected["sha256"]
            or not path.is_file()
            or file_sha256(path) != binding["sha256"]
        ):
            raise MaturityAcceptanceV2Error(f"artifact binding drift: {role}")
        by_role[role] = path
    return by_role


def authoritative_context_from_evidence(
    evidence: dict[str, dict[str, str]], subject: dict[str, Any]
) -> dict[str, dict[str, str]]:
    """Build the only allowed role map from hash-checked evidence/package files."""

    required = {
        "pdf": "pdf",
        "docx": "docx",
        "artifact_ledger": "artifact_ledger",
        "package_manifest": "package_manifest",
        "render_receipt": "render_receipt",
        "pdf_figure_receipt": "pdf_figure_receipt",
        "fixture_freeze_receipt": "fixture_freeze_receipt",
        "bibliography_source_receipt": "bibliography_source_receipt",
    }
    context: dict[str, dict[str, str]] = {}
    for evidence_name, role in required.items():
        ref = evidence[evidence_name]
        if ref.get("subject") != subject:
            raise MaturityAcceptanceV2Error(f"evidence subject drift: {evidence_name}")
        path = Path(ref["path"]).resolve()
        if not path.is_file() or file_sha256(path) != ref.get("sha256"):
            raise MaturityAcceptanceV2Error(f"evidence hash drift: {evidence_name}")
        context[role] = {"path": str(path), "sha256": ref["sha256"]}
    package = _typed_json(Path(context["package_manifest"]["path"]))
    if package.get("subject") != subject:
        raise MaturityAcceptanceV2Error("package manifest subject drift")
    package_roles: dict[str, dict[str, Any]] = {}
    for item in package.get("files", []):
        role = item.get("role")
        if role not in {"tex_source", "bibliography", "pdf", "docx"}:
            continue
        path = Path(item.get("path", "")).resolve()
        if role in package_roles or not path.is_file() or file_sha256(path) != item.get("sha256"):
            raise MaturityAcceptanceV2Error(f"package target file binding drift: {role}")
        package_roles[role] = {"path": str(path), "sha256": item["sha256"]}
    if set(package_roles) != {"tex_source", "bibliography", "pdf", "docx"}:
        raise MaturityAcceptanceV2Error(
            "package manifest lacks exact target TeX/bibliography/PDF/DOCX files"
        )
    for role in ("pdf", "docx"):
        if package_roles[role] != context[role]:
            raise MaturityAcceptanceV2Error(f"package/evidence surface drift: {role}")
    context.update(
        {role: package_roles[role] for role in ("tex_source", "bibliography")}
    )
    return context


def evaluate_target_adaptation_v2(
    protocol: dict[str, Any],
    sample: dict[str, Any],
    target_review: dict[str, Any],
    *,
    subject: dict[str, Any],
    authoritative_context: dict[str, dict[str, str]],
) -> dict[str, Any]:
    """Return recomputed per-operator checks or raise on invalid evidence."""

    schema = json.loads(TARGET_REVIEW_SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(target_review), key=str)
    if errors:
        raise MaturityAcceptanceV2Error(
            "target review schema invalid: " + errors[0].message
        )
    if target_review["receipt_sha256"] != canonical_sha256(_without_hash(target_review)):
        raise MaturityAcceptanceV2Error("target review self-hash drift")
    if target_review["subject"] != subject:
        raise MaturityAcceptanceV2Error("target review subject drift")
    if (
        target_review["authority"] != "paperspine5-host-independent-target-evaluator"
        or target_review["reviewer_identity"]
        != "paperspine5-independent-target-reviewer-v2"
        or target_review["producer_identity"] == target_review["reviewer_identity"]
        or target_review["producer_process_id"]
        == target_review["reviewer_process_id"]
    ):
        raise MaturityAcceptanceV2Error("target review authority is not independent")
    profile, catalog_sha256 = load_protocol_target_profile(
        protocol, sample["target_template"]
    )
    if (
        target_review["target_template"] != sample["target_template"]
        or target_review["profile_catalog_sha256"] != catalog_sha256
        or target_review["hard_obligation_ids"] != sample["target_obligation_ids"]
        or sample["target_obligation_ids"] != [profile["obligation_id"]]
    ):
        raise MaturityAcceptanceV2Error("target review profile/obligation binding drift")
    required = {
        check["check_id"]: check["operator"] for check in profile["machine_checks"]
    }
    findings = target_review["findings"]
    finding_ids = [finding["check_id"] for finding in findings]
    if len(finding_ids) != len(set(finding_ids)):
        raise MaturityAcceptanceV2Error("duplicate target operator finding")
    if set(finding_ids) != set(required):
        raise MaturityAcceptanceV2Error("missing or unknown target operator finding")
    evaluators = _operator_evaluators(profile)
    results: dict[str, str] = {}
    for finding in findings:
        check_id = finding["check_id"]
        operator = finding["operator"]
        if operator != required[check_id] or operator not in evaluators:
            raise MaturityAcceptanceV2Error("target finding operator drift")
        context = _validated_context(
            finding["artifact_bindings"], authoritative_context
        )
        try:
            passed = bool(evaluators[operator](context))
        except (KeyError, OSError, ValueError, zipfile.BadZipFile):
            passed = False
        results[check_id] = "PASS" if passed else "FAIL"
    return {
        "target_template": sample["target_template"],
        "profile_catalog_sha256": catalog_sha256,
        "operator_checks": results,
        "target_adaptation": "PASS"
        if results and all(value == "PASS" for value in results.values())
        else "FAIL",
    }


def derive_hard_checks_v2(
    protocol: dict[str, Any],
    sample: dict[str, Any],
    fixture: dict[str, Any],
    entry_mode: str,
    evidence: dict[str, dict[str, Any]],
    subject: dict[str, Any],
) -> dict[str, str]:
    """Run the existing hard checks but replace v1 target self-report with v2 bytes."""

    if protocol.get("status") == "design_frozen":
        validate_preregistered_protocol_v2(protocol)
    else:
        validate_protocol_design_v2(protocol)
    v1_evidence_names = set(v1.ALWAYS_REQUIRED_EVIDENCE)
    v1_evidence_names.update(
        v1.CONDITIONAL_REQUIRED_EVIDENCE.get(sample["figure_mode"], ())
    )
    v1_evidence = {
        name: evidence[name] for name in v1_evidence_names if name in evidence
    }
    if set(v1_evidence) != v1_evidence_names:
        raise MaturityAcceptanceV2Error(
            "v2 receipt lacks the v1-compatible base evidence required for hard checks"
        )
    checks = v1._derive_hard_checks(  # noqa: SLF001 - intentional v1 compatibility read
        protocol, sample, fixture, entry_mode, v1_evidence, subject
    )
    _path, target_review = v1._load_evidence(  # noqa: SLF001
        evidence["target_review_receipt"], subject
    )
    if target_review is None:
        raise MaturityAcceptanceV2Error("target review must be typed JSON")
    context = authoritative_context_from_evidence(evidence, subject)
    target = evaluate_target_adaptation_v2(
        protocol,
        sample,
        target_review,
        subject=subject,
        authoritative_context=context,
    )
    checks["target_adaptation"] = target["target_adaptation"]
    return checks


def build_independent_evaluation_receipt_v2(
    protocol: dict[str, Any],
    fixture_receipt: dict[str, Any],
    *,
    run_id: str,
    entry_mode: str,
    attempt: int,
    producer_identity: str,
    evaluator_identity: str,
    evaluated_at: str,
    subject: dict[str, Any],
    evidence: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Build the persisted v2 receipt from the exact evidence later recomputed."""

    normalized = validate_preregistered_protocol_v2(protocol)
    fixture = verify_fixture_freeze_receipt_v2(normalized, fixture_receipt)
    sample = _sample_v2(normalized, fixture["sample_id"])
    if entry_mode != sample["entry_mode"]:
        raise MaturityAcceptanceV2Error(
            "entry mode differs from the registered v2 case"
        )
    if attempt not in range(1, normalized["consecutive_runs_per_entry"] + 1):
        raise MaturityAcceptanceV2Error(
            "attempt is outside registered v2 consecutive runs"
        )
    if subject.get("material_snapshot_sha256") != fixture[
        "material_snapshot_sha256"
    ]:
        raise MaturityAcceptanceV2Error(
            "evaluation subject material differs from the frozen v2 fixture"
        )
    if (
        producer_identity == evaluator_identity
        or evaluator_identity != normalized["evaluator_requirements"]["evaluator_identity"]
    ):
        raise MaturityAcceptanceV2Error(
            "producer cannot act as the independent v2 evaluator"
        )
    if _parse_time_v2(evaluated_at, "evaluated_at") < _parse_time_v2(
        fixture["first_run_not_before"], "first_run_not_before"
    ):
        raise MaturityAcceptanceV2Error(
            "v2 evaluation predates the frozen fixture/run boundary"
        )
    required_evidence = set(V2_ALWAYS_REQUIRED_EVIDENCE)
    required_evidence.update(
        V2_CONDITIONAL_REQUIRED_EVIDENCE.get(sample["figure_mode"], ())
    )
    if set(evidence) != required_evidence:
        raise MaturityAcceptanceV2Error(
            "independent evaluator v2 evidence set is incomplete or unknown"
        )
    fixture_ref = evidence["fixture_freeze_receipt"]
    fixture_evidence = _typed_json(Path(fixture_ref["path"]).resolve())
    if fixture_evidence.get("receipt_sha256") != fixture["receipt_sha256"]:
        raise MaturityAcceptanceV2Error(
            "fixture evidence does not bind the verified v2 freeze receipt"
        )
    hard_checks = derive_hard_checks_v2(
        normalized, sample, fixture, entry_mode, evidence, subject
    )
    current = current_evaluator_hashes_v2(normalized)
    receipt = {
        "contract": "paperspine5.maturity-independent-evaluation-v2",
        "contract_version": "2.0",
        "run_id": run_id,
        "sample_id": sample["sample_id"],
        "entry_mode": entry_mode,
        "attempt": attempt,
        "protocol_sha256": normalized["protocol_sha256"],
        "fixture_receipt_sha256": fixture["receipt_sha256"],
        "producer_identity": producer_identity,
        "evaluator_identity": evaluator_identity,
        **{field: current[field] for field in EVALUATOR_PIN_PATHS},
        "target_profile_catalog_sha256": current[
            "target_profile_catalog_sha256"
        ],
        "evaluated_at": evaluated_at,
        "subject": copy.deepcopy(subject),
        "evidence": copy.deepcopy(evidence),
        "hard_checks": hard_checks,
        "status": "PASS" if set(hard_checks.values()) == {"PASS"} else "FAIL",
        "external_action_authorized": False,
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    validate_independent_evaluator_receipt_v2(normalized, receipt)
    return receipt


def verify_independent_evaluation_receipt_v2(
    protocol: dict[str, Any],
    fixture_receipt: dict[str, Any],
    receipt: dict[str, Any],
) -> dict[str, Any]:
    """Reopen the persisted evidence map and recompute every hard check."""

    normalized = validate_preregistered_protocol_v2(protocol)
    fixture = verify_fixture_freeze_receipt_v2(normalized, fixture_receipt)
    validated = validate_independent_evaluator_receipt_v2(normalized, receipt)
    if (
        validated["fixture_receipt_sha256"] != fixture["receipt_sha256"]
        or validated["sample_id"] != fixture["sample_id"]
        or validated["subject"]["material_snapshot_sha256"]
        != fixture["material_snapshot_sha256"]
    ):
        raise MaturityAcceptanceV2Error(
            "v2 evaluator receipt differs from the frozen fixture subject"
        )
    sample = _sample_v2(normalized, validated["sample_id"])
    recomputed = derive_hard_checks_v2(
        normalized,
        sample,
        fixture,
        validated["entry_mode"],
        validated["evidence"],
        validated["subject"],
    )
    if validated["hard_checks"] != recomputed:
        raise MaturityAcceptanceV2Error(
            "v2 evaluator hard checks differ from authoritative evidence"
        )
    expected_status = "PASS" if set(recomputed.values()) == {"PASS"} else "FAIL"
    if validated["status"] != expected_status:
        raise MaturityAcceptanceV2Error(
            "v2 evaluator status differs from recomputed hard checks"
        )
    if _parse_time_v2(validated["evaluated_at"], "evaluated_at") < _parse_time_v2(
        fixture["first_run_not_before"], "first_run_not_before"
    ):
        raise MaturityAcceptanceV2Error(
            "v2 evaluation predates the fixture freeze boundary"
        )
    return copy.deepcopy(validated)
