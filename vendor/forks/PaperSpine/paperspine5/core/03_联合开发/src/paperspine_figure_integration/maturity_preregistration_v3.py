"""Fail-closed PS-GAP-014 successor preregistration and fixture verification.

V3 is an immutable overlay on the frozen V2 design and fixture payloads.  It
does not reinterpret the V2 evaluator.  Instead it reopens every predecessor
byte, preserves its registered sample/threshold/public-entry commitments, and
binds the currently verified canonical Word surface adapter for future runs.
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[3]
ACCEPTANCE_ROOT = ROOT / "03_联合开发" / "acceptance" / "ps-gap-014"
CONTRACT_ROOT = ROOT / "03_联合开发" / "contracts"
V2_PROTOCOL_PATH = ACCEPTANCE_ROOT / "preregistered-acceptance-v2.json"
V2_FIXTURE_ROOT = ACCEPTANCE_ROOT / "frozen-fixtures-v2"
V2_INDEX_PATH = V2_FIXTURE_ROOT / "index.json"
V3_PROTOCOL_PATH = ACCEPTANCE_ROOT / "preregistered-acceptance-v3.json"
V3_DIFF_PATH = ACCEPTANCE_ROOT / "preregistered-acceptance-v3.semantic-diff.json"
V3_FREEZER_PATH = ACCEPTANCE_ROOT / "freeze_protocol_design_v3.py"
V3_MATERIALIZER_PATH = ACCEPTANCE_ROOT / "materialize_fixture_freeze_v3.py"
PUBLIC_ENTRY_PLAN_PATH = (
    ROOT
    / "90_临时工作"
    / "TimeB闭环修复"
    / "PS-GAP-014_OFFICIAL_RUN_PLAN_V2.md"
)
TARGET_CATALOG_PATH = ACCEPTANCE_ROOT / "target-rule-profiles-v2.json"
CANONICAL_ADAPTER_PATH = Path(__file__).with_name("canonical_artifacts.py")
SURFACE_RECEIPT_SCHEMA_PATH = CONTRACT_ROOT / "surface-receipt.schema.json"
TARGET_REVIEW_SCHEMA_PATH = CONTRACT_ROOT / "maturity-target-review-evidence-v2.schema.json"

PROTOCOL_SCHEMA_PATH = CONTRACT_ROOT / "maturity-preregistration-v3.schema.json"
DIFF_SCHEMA_PATH = CONTRACT_ROOT / "maturity-semantic-diff-v3.schema.json"
JOURNAL_SCHEMA_PATH = CONTRACT_ROOT / "maturity-protocol-freeze-journal-v3.schema.json"
FREEZE_RECEIPT_SCHEMA_PATH = CONTRACT_ROOT / "maturity-protocol-freeze-receipt-v3.schema.json"
FIXTURE_RECEIPT_SCHEMA_PATH = CONTRACT_ROOT / "maturity-fixture-freeze-receipt-v3.schema.json"
FIXTURE_INDEX_SCHEMA_PATH = CONTRACT_ROOT / "maturity-fixture-index-v3.schema.json"

EXPECTED_V2_PROTOCOL_FILE_SHA256 = (
    "501d3a750dc76bd92a5ee0633ac604d82f653dcaddb9c0a5412d49cae6de81fc"
)
EXPECTED_V2_PROTOCOL_SHA256 = (
    "c75aa0af8ff66761d153310d2c14926f3b4cfa9757265a88d68d37e623b1c262"
)
EXPECTED_V2_INDEX_FILE_SHA256 = (
    "a74294cee29e9674080c31fe629706568f18314d773d57f559f64802dc32e3f9"
)
EXPECTED_V2_INDEX_SHA256 = (
    "2aebcb1cb4c0f102100821f8ea9979bc76ea3c371b9724b76d42ac15aef8fea0"
)
EXPECTED_OLD_ADAPTER_SHA256 = (
    "288ee1283b9a594cde505aa1a6a5f2fbb9cf76e1734d161188bd2dfeeac7f6d3"
)
EXPECTED_SAMPLE_COUNT = 21
EXPECTED_PAYLOAD_FILE_COUNT = 280
EXPECTED_PAYLOAD_BYTES = 14_476_365

PIN_PATHS_V3 = {
    "validator_code_sha256": Path(__file__).resolve(),
    "protocol_schema_sha256": PROTOCOL_SCHEMA_PATH,
    "semantic_diff_schema_sha256": DIFF_SCHEMA_PATH,
    "freeze_journal_schema_sha256": JOURNAL_SCHEMA_PATH,
    "freeze_receipt_schema_sha256": FREEZE_RECEIPT_SCHEMA_PATH,
    "fixture_receipt_schema_sha256": FIXTURE_RECEIPT_SCHEMA_PATH,
    "fixture_index_schema_sha256": FIXTURE_INDEX_SCHEMA_PATH,
    "freeze_transaction_sha256": V3_FREEZER_PATH,
    "fixture_materializer_sha256": V3_MATERIALIZER_PATH,
    "canonical_surface_adapter_sha256": CANONICAL_ADAPTER_PATH,
    "surface_receipt_schema_sha256": SURFACE_RECEIPT_SCHEMA_PATH,
    "target_review_schema_sha256": TARGET_REVIEW_SCHEMA_PATH,
}


class MaturityPreregistrationV3Error(ValueError):
    """The V3 preregistration or its predecessor evidence failed closed."""


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


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MaturityPreregistrationV3Error(f"{label} is unreadable: {path}") from exc
    if not isinstance(value, dict):
        raise MaturityPreregistrationV3Error(f"{label} must be a JSON object")
    return value


def _validate_schema(value: dict[str, Any], path: Path, label: str) -> None:
    schema = load_json(path, f"{label} schema")
    errors = sorted(
        Draft202012Validator(
            schema, format_checker=Draft202012Validator.FORMAT_CHECKER
        ).iter_errors(value),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        details = "; ".join(error.message for error in errors[:6])
        raise MaturityPreregistrationV3Error(
            f"{label} schema validation failed: {details}"
        )


def _self_hash(value: dict[str, Any], field: str) -> str:
    subject = copy.deepcopy(value)
    subject.pop(field, None)
    return canonical_sha256(subject)


def _parse_time(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise MaturityPreregistrationV3Error(f"{field} must be a timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise MaturityPreregistrationV3Error(f"{field} is invalid") from exc
    if parsed.tzinfo is None:
        raise MaturityPreregistrationV3Error(f"{field} must include timezone")
    return parsed


def protocol_sha256_v3(protocol: dict[str, Any]) -> str:
    return _self_hash(protocol, "protocol_sha256")


def design_subject_sha256_v3(protocol: dict[str, Any]) -> str:
    subject = copy.deepcopy(protocol)
    subject["status"] = "draft_unfrozen"
    subject["frozen_at"] = None
    subject["protocol_sha256"] = None
    subject["semantic_diff_receipt"]["file_sha256"] = None
    subject["semantic_diff_receipt"]["receipt_sha256"] = None
    return canonical_sha256(subject)


def current_pins_v3() -> dict[str, str]:
    missing = [field for field, path in PIN_PATHS_V3.items() if not path.is_file()]
    if missing:
        raise MaturityPreregistrationV3Error(
            "V3 semantic pin source is missing: " + ", ".join(missing)
        )
    return {field: file_sha256(path) for field, path in PIN_PATHS_V3.items()}


def _verify_v2_self_hash(value: dict[str, Any], field: str, label: str) -> None:
    if value.get(field) != _self_hash(value, field):
        raise MaturityPreregistrationV3Error(f"{label} self-hash does not recompute")


def _v2_sample_order(protocol: dict[str, Any]) -> list[str]:
    samples = protocol.get("samples")
    if not isinstance(samples, list) or len(samples) != EXPECTED_SAMPLE_COUNT:
        raise MaturityPreregistrationV3Error("V2 sample set is not the frozen 21-case set")
    order = [sample.get("sample_id") for sample in samples]
    if any(not isinstance(sample_id, str) for sample_id in order) or len(set(order)) != len(order):
        raise MaturityPreregistrationV3Error("V2 sample order is invalid")
    return order


def reopen_predecessor_v3(*, verify_payloads: bool = True) -> dict[str, Any]:
    if file_sha256(V2_PROTOCOL_PATH) != EXPECTED_V2_PROTOCOL_FILE_SHA256:
        raise MaturityPreregistrationV3Error("frozen V2 protocol file drifted")
    protocol = load_json(V2_PROTOCOL_PATH, "frozen V2 protocol")
    if (
        protocol.get("contract") != "paperspine5.maturity-acceptance-protocol"
        or protocol.get("contract_version") != "2.0"
        or protocol.get("status") != "design_frozen"
        or protocol.get("protocol_sha256") != EXPECTED_V2_PROTOCOL_SHA256
    ):
        raise MaturityPreregistrationV3Error("frozen V2 protocol identity drifted")
    _verify_v2_self_hash(protocol, "protocol_sha256", "frozen V2 protocol")

    if file_sha256(V2_INDEX_PATH) != EXPECTED_V2_INDEX_FILE_SHA256:
        raise MaturityPreregistrationV3Error("frozen V2 fixture index file drifted")
    index = load_json(V2_INDEX_PATH, "frozen V2 fixture index")
    if (
        index.get("contract") != "paperspine5.maturity-fixture-index-v2"
        or index.get("contract_version") != "2.0"
        or index.get("index_sha256") != EXPECTED_V2_INDEX_SHA256
        or index.get("protocol_file_sha256") != EXPECTED_V2_PROTOCOL_FILE_SHA256
        or index.get("protocol_sha256") != EXPECTED_V2_PROTOCOL_SHA256
        or index.get("sample_count") != EXPECTED_SAMPLE_COUNT
        or index.get("fixture_file_count") != EXPECTED_PAYLOAD_FILE_COUNT
        or index.get("fixture_total_bytes") != EXPECTED_PAYLOAD_BYTES
        or index.get("product_runs_executed") != 0
        or index.get("evaluator_results_created") != 0
        or index.get("external_action_authorized") is not False
    ):
        raise MaturityPreregistrationV3Error("frozen V2 fixture index identity drifted")
    _verify_v2_self_hash(index, "index_sha256", "frozen V2 fixture index")

    order = _v2_sample_order(protocol)
    items = index.get("fixtures")
    if not isinstance(items, list) or [item.get("sample_id") for item in items] != order:
        raise MaturityPreregistrationV3Error("V2 fixture order does not bind sample order")

    receipts: dict[str, dict[str, Any]] = {}
    payload_sets: list[dict[str, Any]] = []
    if verify_payloads:
        for item in items:
            sample_id = item["sample_id"]
            receipt_path = V2_FIXTURE_ROOT / item["receipt_relative_path"]
            fixture_root = V2_FIXTURE_ROOT / item["fixture_relative_path"]
            if file_sha256(receipt_path) != item["receipt_file_sha256"]:
                raise MaturityPreregistrationV3Error(
                    f"V2 fixture receipt file drifted: {sample_id}"
                )
            receipt = load_json(receipt_path, f"V2 fixture receipt {sample_id}")
            if (
                receipt.get("contract") != "paperspine5.maturity-fixture-freeze-v2"
                or receipt.get("sample_id") != sample_id
                or receipt.get("receipt_sha256") != item["receipt_sha256"]
            ):
                raise MaturityPreregistrationV3Error(
                    f"V2 fixture receipt identity drifted: {sample_id}"
                )
            _verify_v2_self_hash(receipt, "receipt_sha256", f"V2 receipt {sample_id}")
            entries = receipt.get("entries")
            if not isinstance(entries, list) or entries != sorted(
                entries, key=lambda entry: entry["relative_path"]
            ):
                raise MaturityPreregistrationV3Error(
                    f"V2 fixture entries are invalid: {sample_id}"
                )
            for entry in entries:
                path = fixture_root / entry["relative_path"]
                if (
                    not path.is_file()
                    or path.stat().st_size != entry["size_bytes"]
                    or file_sha256(path) != entry["sha256"]
                ):
                    raise MaturityPreregistrationV3Error(
                        f"V2 fixture payload drifted: {sample_id}/{entry['relative_path']}"
                    )
            if (
                canonical_sha256(entries) != item["fixture_tree_sha256"]
                or receipt.get("fixture_tree_sha256") != item["fixture_tree_sha256"]
                or receipt.get("material_snapshot_sha256")
                != item["material_snapshot_sha256"]
                or receipt.get("file_count") != item["file_count"]
                or receipt.get("total_bytes") != item["total_bytes"]
            ):
                raise MaturityPreregistrationV3Error(
                    f"V2 fixture payload ledger drifted: {sample_id}"
                )
            receipts[sample_id] = receipt
            payload_sets.append({"sample_id": sample_id, "entries": entries})

    return {
        "protocol": protocol,
        "index": index,
        "sample_order": order,
        "receipts": receipts,
        "fixture_payload_set_sha256": canonical_sha256(payload_sets)
        if verify_payloads
        else None,
    }


def semantic_commitments_from_predecessor(
    predecessor: dict[str, Any],
) -> dict[str, str]:
    protocol = predecessor["protocol"]
    if predecessor.get("fixture_payload_set_sha256") is None:
        predecessor = reopen_predecessor_v3(verify_payloads=True)
        protocol = predecessor["protocol"]
    samples = protocol["samples"]
    registered_entries = [
        {
            "sample_id": sample["sample_id"],
            "entry_mode": sample["entry_mode"],
            "simple_entry_request_class": sample["simple_entry_request_class"],
        }
        for sample in samples
    ]
    return {
        "sample_order_sha256": canonical_sha256(predecessor["sample_order"]),
        "samples_sha256": canonical_sha256(samples),
        "coverage_requirements_sha256": canonical_sha256(
            protocol["coverage_requirements"]
        ),
        "thresholds_sha256": canonical_sha256(
            {"thresholds": protocol["thresholds"], "aggregation": protocol["aggregation"]}
        ),
        "registered_entry_semantics_sha256": canonical_sha256(registered_entries),
        "required_evidence_sha256": canonical_sha256(
            {
                "required": protocol["evaluator_requirements"]["required_evidence_types"],
                "conditional": protocol["evaluator_requirements"][
                    "conditional_required_evidence_types"
                ],
            }
        ),
        "target_profile_catalog_sha256": file_sha256(TARGET_CATALOG_PATH),
        "fixture_payload_set_sha256": predecessor["fixture_payload_set_sha256"],
    }


def validate_semantic_diff_v3(
    receipt: dict[str, Any], protocol: dict[str, Any], predecessor: dict[str, Any]
) -> dict[str, Any]:
    normalized = copy.deepcopy(receipt)
    _validate_schema(normalized, DIFF_SCHEMA_PATH, "V3 semantic diff receipt")
    if normalized["receipt_sha256"] != _self_hash(normalized, "receipt_sha256"):
        raise MaturityPreregistrationV3Error("V3 semantic diff self-hash does not recompute")
    expected_commitments = semantic_commitments_from_predecessor(predecessor)
    expected = {
        "predecessor_protocol_file_sha256": EXPECTED_V2_PROTOCOL_FILE_SHA256,
        "predecessor_protocol_sha256": EXPECTED_V2_PROTOCOL_SHA256,
        "predecessor_fixture_index_file_sha256": EXPECTED_V2_INDEX_FILE_SHA256,
        "predecessor_fixture_index_sha256": EXPECTED_V2_INDEX_SHA256,
        "successor_design_subject_sha256": design_subject_sha256_v3(protocol),
        "preserved_semantic_commitments": expected_commitments,
        "old_canonical_surface_adapter_sha256": EXPECTED_OLD_ADAPTER_SHA256,
        "new_canonical_surface_adapter_sha256": file_sha256(CANONICAL_ADAPTER_PATH),
    }
    for field, value in expected.items():
        if normalized.get(field) != value:
            raise MaturityPreregistrationV3Error(
                f"V3 semantic diff does not bind {field}"
            )
    expected_classes = {
        "v3_contract_namespace",
        "successor_evidence_paths",
        "current_canonical_adapter_pin",
        "v3_transaction_and_receipt_paths",
        "future_freeze_time_and_self_hashes",
    }
    if set(normalized["allowed_change_classes"]) != expected_classes:
        raise MaturityPreregistrationV3Error("V3 semantic diff change classes drifted")
    return normalized


def _validate_protocol_structure_v3(protocol: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(protocol)
    _validate_schema(normalized, PROTOCOL_SCHEMA_PATH, "V3 protocol")
    predecessor = reopen_predecessor_v3(verify_payloads=True)
    expected_predecessor = {
        "protocol_path": str(V2_PROTOCOL_PATH.relative_to(ROOT)).replace("\\", "/"),
        "protocol_file_sha256": EXPECTED_V2_PROTOCOL_FILE_SHA256,
        "protocol_sha256": EXPECTED_V2_PROTOCOL_SHA256,
        "fixture_index_path": str(V2_INDEX_PATH.relative_to(ROOT)).replace("\\", "/"),
        "fixture_index_file_sha256": EXPECTED_V2_INDEX_FILE_SHA256,
        "fixture_index_sha256": EXPECTED_V2_INDEX_SHA256,
    }
    if normalized["predecessor"] != expected_predecessor:
        raise MaturityPreregistrationV3Error("V3 predecessor binding drifted")
    commitments = semantic_commitments_from_predecessor(predecessor)
    if normalized["semantic_commitments"] != commitments:
        raise MaturityPreregistrationV3Error("V3 semantic commitments drifted")
    pins = current_pins_v3()
    supplied_pins = {
        field: normalized["evaluator_requirements"][field] for field in pins
    }
    if supplied_pins != pins:
        raise MaturityPreregistrationV3Error("V3 current source/schema pins drifted")
    plan_rel = str(PUBLIC_ENTRY_PLAN_PATH.relative_to(ROOT)).replace("\\", "/")
    if (
        normalized["public_entry_semantics"]["authority_plan_path"] != plan_rel
        or normalized["public_entry_semantics"]["authority_plan_sha256"]
        != file_sha256(PUBLIC_ENTRY_PLAN_PATH)
    ):
        raise MaturityPreregistrationV3Error("V3 public-entry authority drifted")
    diff_ref = normalized["semantic_diff_receipt"]
    diff_rel = str(V3_DIFF_PATH.relative_to(ROOT)).replace("\\", "/")
    if diff_ref["path"] != diff_rel or file_sha256(V3_DIFF_PATH) != diff_ref["file_sha256"]:
        raise MaturityPreregistrationV3Error("V3 semantic diff file binding drifted")
    diff = load_json(V3_DIFF_PATH, "V3 semantic diff")
    if diff.get("receipt_sha256") != diff_ref["receipt_sha256"]:
        raise MaturityPreregistrationV3Error("V3 semantic diff receipt binding drifted")
    validate_semantic_diff_v3(diff, normalized, predecessor)
    return normalized


def validate_protocol_design_v3(protocol: dict[str, Any]) -> dict[str, Any]:
    normalized = _validate_protocol_structure_v3(protocol)
    if (
        normalized["status"] != "draft_unfrozen"
        or normalized["frozen_at"] is not None
        or normalized["protocol_sha256"] is not None
    ):
        raise MaturityPreregistrationV3Error("V3 design is not draft_unfrozen")
    return normalized


def validate_preregistered_protocol_v3(protocol: dict[str, Any]) -> dict[str, Any]:
    normalized = _validate_protocol_structure_v3(protocol)
    if normalized["status"] != "design_frozen":
        raise MaturityPreregistrationV3Error("V3 protocol is not design_frozen")
    _parse_time(normalized["frozen_at"], "frozen_at")
    if normalized["protocol_sha256"] != protocol_sha256_v3(normalized):
        raise MaturityPreregistrationV3Error("V3 protocol self-hash does not recompute")
    return normalized


def tree_entries(root: Path) -> list[dict[str, Any]]:
    entries = []
    for path in sorted((path for path in root.rglob("*") if path.is_file()), key=lambda p: p.as_posix()):
        relative = path.relative_to(root).as_posix()
        entries.append(
            {"relative_path": relative, "size_bytes": path.stat().st_size, "sha256": file_sha256(path)}
        )
    return entries


def build_fixture_receipt_v3(
    *,
    protocol: dict[str, Any],
    sample_id: str,
    fixture_root: Path,
    materializer_path: Path,
    mode: str,
    predecessor_item: dict[str, Any],
    predecessor_receipt: dict[str, Any],
    bound_at: str | None = None,
    first_run_not_before: str | None = None,
    declared_fixture_root: Path | None = None,
) -> dict[str, Any]:
    predecessor = reopen_predecessor_v3(verify_payloads=True)
    sample_map = {sample["sample_id"]: sample for sample in predecessor["protocol"]["samples"]}
    sample = sample_map.get(sample_id)
    if sample is None:
        raise MaturityPreregistrationV3Error(f"unknown V3 sample: {sample_id}")
    entries = tree_entries(fixture_root)
    if entries != predecessor_receipt["entries"]:
        raise MaturityPreregistrationV3Error(
            f"V3 fixture payload is not byte-exact V2: {sample_id}"
        )
    receipt = {
        "contract": "paperspine5.maturity-fixture-freeze-v3",
        "contract_version": "3.0",
        "mode": mode,
        "eligible_for_official_runs": mode == "official",
        "authority": "paperspine5-authenticated-host-fixture-freezer-v3",
        "sample_id": sample_id,
        "fixture_family_id": sample["fixture_family_id"],
        "fixture_provenance": sample["fixture_provenance"],
        "benchmark_lineage": sample["benchmark_lineage"],
        "author_facts_are_fixture_only": True,
        "protocol_subject_sha256": protocol.get("protocol_sha256")
        or design_subject_sha256_v3(protocol),
        "protocol_file_sha256": file_sha256(V3_PROTOCOL_PATH),
        "semantic_diff_receipt_sha256": protocol["semantic_diff_receipt"]["receipt_sha256"],
        "canonical_surface_adapter_sha256": file_sha256(CANONICAL_ADAPTER_PATH),
        "materializer_path": str(materializer_path.resolve()),
        "materializer_sha256": file_sha256(materializer_path),
        "fixture_root": str((declared_fixture_root or fixture_root).resolve()),
        "entries": entries,
        "file_count": len(entries),
        "total_bytes": sum(entry["size_bytes"] for entry in entries),
        "fixture_tree_sha256": canonical_sha256(entries),
        "material_snapshot_sha256": predecessor_item["material_snapshot_sha256"],
        "predecessor_fixture_receipt_file_sha256": predecessor_item["receipt_file_sha256"],
        "predecessor_fixture_receipt_sha256": predecessor_item["receipt_sha256"],
        "predecessor_fixture_tree_sha256": predecessor_item["fixture_tree_sha256"],
        "predecessor_material_snapshot_sha256": predecessor_item["material_snapshot_sha256"],
        "bound_at": bound_at,
        "first_run_not_before": first_run_not_before,
        "external_action_authorized": False,
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    return verify_fixture_receipt_v3(
        protocol=protocol,
        receipt=receipt,
        fixture_root=fixture_root,
        materializer_path=materializer_path,
        predecessor=predecessor,
        declared_fixture_root=declared_fixture_root,
    )


def verify_fixture_receipt_v3(
    *,
    protocol: dict[str, Any],
    receipt: dict[str, Any],
    fixture_root: Path,
    materializer_path: Path,
    predecessor: dict[str, Any] | None = None,
    declared_fixture_root: Path | None = None,
) -> dict[str, Any]:
    normalized = copy.deepcopy(receipt)
    _validate_schema(normalized, FIXTURE_RECEIPT_SCHEMA_PATH, "V3 fixture receipt")
    if normalized["receipt_sha256"] != _self_hash(normalized, "receipt_sha256"):
        raise MaturityPreregistrationV3Error("V3 fixture receipt self-hash does not recompute")
    reopened = predecessor or reopen_predecessor_v3(verify_payloads=True)
    item_map = {item["sample_id"]: item for item in reopened["index"]["fixtures"]}
    old_item = item_map.get(normalized["sample_id"])
    old_receipt = reopened["receipts"].get(normalized["sample_id"])
    if old_item is None or old_receipt is None:
        raise MaturityPreregistrationV3Error("V3 fixture does not bind a V2 sample")
    entries = tree_entries(fixture_root)
    expected = {
        "entries": old_receipt["entries"],
        "file_count": old_item["file_count"],
        "total_bytes": old_item["total_bytes"],
        "fixture_tree_sha256": old_item["fixture_tree_sha256"],
        "material_snapshot_sha256": old_item["material_snapshot_sha256"],
        "predecessor_fixture_receipt_file_sha256": old_item["receipt_file_sha256"],
        "predecessor_fixture_receipt_sha256": old_item["receipt_sha256"],
        "predecessor_fixture_tree_sha256": old_item["fixture_tree_sha256"],
        "predecessor_material_snapshot_sha256": old_item["material_snapshot_sha256"],
        "canonical_surface_adapter_sha256": file_sha256(CANONICAL_ADAPTER_PATH),
        "materializer_path": str(materializer_path.resolve()),
        "materializer_sha256": file_sha256(materializer_path),
        "fixture_root": str((declared_fixture_root or fixture_root).resolve()),
        "protocol_file_sha256": file_sha256(V3_PROTOCOL_PATH),
        "semantic_diff_receipt_sha256": protocol["semantic_diff_receipt"]["receipt_sha256"],
    }
    if entries != old_receipt["entries"]:
        raise MaturityPreregistrationV3Error("V3 fixture payload bytes drifted")
    for field, value in expected.items():
        if normalized.get(field) != value:
            raise MaturityPreregistrationV3Error(f"V3 fixture receipt drifted: {field}")
    expected_subject = protocol.get("protocol_sha256") or design_subject_sha256_v3(protocol)
    if normalized["protocol_subject_sha256"] != expected_subject:
        raise MaturityPreregistrationV3Error("V3 fixture protocol subject drifted")
    if normalized["mode"] == "official":
        bound = _parse_time(normalized["bound_at"], "bound_at")
        first = _parse_time(normalized["first_run_not_before"], "first_run_not_before")
        frozen = _parse_time(protocol["frozen_at"], "frozen_at")
        if not frozen <= bound <= first:
            raise MaturityPreregistrationV3Error("V3 fixture chronology is invalid")
    return normalized


def validate_freeze_record_v3(
    value: dict[str, Any], *, journal: bool
) -> dict[str, Any]:
    normalized = copy.deepcopy(value)
    schema = JOURNAL_SCHEMA_PATH if journal else FREEZE_RECEIPT_SCHEMA_PATH
    label = "V3 freeze journal" if journal else "V3 freeze receipt"
    field = "journal_sha256" if journal else "receipt_sha256"
    _validate_schema(normalized, schema, label)
    if normalized[field] != _self_hash(normalized, field):
        raise MaturityPreregistrationV3Error(f"{label} self-hash does not recompute")
    return normalized


def verify_fixture_index_v3(
    *,
    protocol: dict[str, Any],
    index_path: Path,
    expected_root: Path,
    content_root: Path | None = None,
) -> dict[str, Any]:
    index = load_json(index_path, "V3 fixture index")
    _validate_schema(index, FIXTURE_INDEX_SCHEMA_PATH, "V3 fixture index")
    if index["index_sha256"] != _self_hash(index, "index_sha256"):
        raise MaturityPreregistrationV3Error("V3 fixture index self-hash does not recompute")
    predecessor = reopen_predecessor_v3(verify_payloads=True)
    expected_order = predecessor["sample_order"]
    if [item["sample_id"] for item in index["fixtures"]] != expected_order:
        raise MaturityPreregistrationV3Error("V3 fixture index order drifted")
    actual_root = content_root or expected_root
    fields = {
        "protocol_path": str(V3_PROTOCOL_PATH.resolve()),
        "protocol_file_sha256": file_sha256(V3_PROTOCOL_PATH),
        "protocol_subject_sha256": protocol.get("protocol_sha256")
        or design_subject_sha256_v3(protocol),
        "semantic_diff_receipt_sha256": protocol["semantic_diff_receipt"]["receipt_sha256"],
        "canonical_surface_adapter_sha256": file_sha256(CANONICAL_ADAPTER_PATH),
        "predecessor_fixture_index_file_sha256": EXPECTED_V2_INDEX_FILE_SHA256,
        "predecessor_fixture_index_sha256": EXPECTED_V2_INDEX_SHA256,
        "fixtures_root": str((expected_root / "fixtures").resolve()),
        "receipts_root": str((expected_root / "receipts").resolve()),
    }
    for field, expected in fields.items():
        if index.get(field) != expected:
            raise MaturityPreregistrationV3Error(f"V3 fixture index drifted: {field}")
    if index["mode"] == "official":
        validate_preregistered_protocol_v3(protocol)
        journal_path = Path(index["protocol_freeze_journal_path"])
        receipt_path = Path(index["protocol_freeze_receipt_path"])
        if (
            file_sha256(journal_path) != index["protocol_freeze_journal_file_sha256"]
            or file_sha256(receipt_path) != index["protocol_freeze_receipt_file_sha256"]
        ):
            raise MaturityPreregistrationV3Error("V3 Gate-A evidence file drifted")
        journal = validate_freeze_record_v3(load_json(journal_path, "V3 Gate-A journal"), journal=True)
        freeze_receipt = validate_freeze_record_v3(load_json(receipt_path, "V3 Gate-A receipt"), journal=False)
        if (
            journal["state"] != "committed"
            or journal["journal_sha256"] != index["protocol_freeze_journal_sha256"]
            or freeze_receipt["receipt_sha256"] != index["protocol_freeze_receipt_sha256"]
            or journal["receipt_sha256"] != freeze_receipt["receipt_sha256"]
            or journal["after_file_sha256"] != file_sha256(V3_PROTOCOL_PATH)
            or freeze_receipt["after_file_sha256"] != file_sha256(V3_PROTOCOL_PATH)
        ):
            raise MaturityPreregistrationV3Error("V3 Gate-A evidence binding drifted")
    materializer = Path(index["materializer_path"])
    if file_sha256(materializer) != index["materializer_sha256"]:
        raise MaturityPreregistrationV3Error("V3 materializer binding drifted")
    for item in index["fixtures"]:
        receipt_path = actual_root / item["receipt_relative_path"]
        fixture_root = actual_root / item["fixture_relative_path"]
        if file_sha256(receipt_path) != item["receipt_file_sha256"]:
            raise MaturityPreregistrationV3Error("V3 receipt file drifted")
        receipt = load_json(receipt_path, "V3 fixture receipt")
        if receipt.get("receipt_sha256") != item["receipt_sha256"]:
            raise MaturityPreregistrationV3Error("V3 receipt index binding drifted")
        verified = verify_fixture_receipt_v3(
            protocol=protocol,
            receipt=receipt,
            fixture_root=fixture_root,
            materializer_path=materializer,
            predecessor=predecessor,
            declared_fixture_root=expected_root / item["fixture_relative_path"],
        )
        for field in (
            "fixture_tree_sha256",
            "material_snapshot_sha256",
            "file_count",
            "total_bytes",
        ):
            if item[field] != verified[field]:
                raise MaturityPreregistrationV3Error(
                    f"V3 fixture index item drifted: {field}"
                )
    return index
