"""V3 maturity evaluator bound to the accepted successor protocol and fixtures.

The V3 protocol is a frozen wrapper: current source/adapter authority lives in
that wrapper, while the unchanged 21-case matrix, thresholds and evidence
semantics are reopened from its hash-pinned V2 predecessor.  This module never
re-validates V2 against the current adapter pin and never accepts V2 fixtures as
V3 evidence.
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from . import maturity_acceptance as v1
from . import maturity_acceptance_v2 as v2
from .maturity_preregistration_v3 import (
    CANONICAL_ADAPTER_PATH,
    FIXTURE_INDEX_SCHEMA_PATH,
    FIXTURE_RECEIPT_SCHEMA_PATH,
    PROTOCOL_SCHEMA_PATH,
    SURFACE_RECEIPT_SCHEMA_PATH,
    TARGET_CATALOG_PATH,
    TARGET_REVIEW_SCHEMA_PATH,
    V3_MATERIALIZER_PATH,
    V3_PROTOCOL_PATH,
    file_sha256,
    reopen_predecessor_v3,
    validate_preregistered_protocol_v3,
    verify_fixture_index_v3,
    verify_fixture_receipt_v3,
)


ROOT = Path(__file__).resolve().parents[3]
ACCEPTANCE_ROOT = ROOT / "03_联合开发" / "acceptance" / "ps-gap-014"
V3_FIXTURE_ROOT = ACCEPTANCE_ROOT / "frozen-fixtures-v3"
V3_INDEX_PATH = V3_FIXTURE_ROOT / "index.json"
EVALUATOR_PATH = Path(__file__).resolve()
EVALUATOR_SCHEMA_PATH = (
    ROOT / "03_联合开发" / "contracts" / "maturity-evaluator-receipt-v3.schema.json"
)
EVALUATOR_IDENTITY = "paperspine5-independent-maturity-evaluator-v3"
V3_ALWAYS_REQUIRED_EVIDENCE = v2.V2_ALWAYS_REQUIRED_EVIDENCE
V3_CONDITIONAL_REQUIRED_EVIDENCE = dict(v2.V2_CONDITIONAL_REQUIRED_EVIDENCE)


class MaturityAcceptanceV3Error(ValueError):
    """Raised when V3 authority, evidence, or a persisted receipt drifts."""


def canonical_sha256(value: Any, *, self_hash: str | None = None) -> str:
    subject = copy.deepcopy(value)
    if self_hash and isinstance(subject, dict):
        subject.pop(self_hash, None)
    encoded = (
        json.dumps(subject, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _parse_time(value: Any, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise MaturityAcceptanceV3Error(f"{label} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise MaturityAcceptanceV3Error(f"{label} must include a timezone")
    return parsed


def _schema_validate(value: dict[str, Any]) -> None:
    schema = json.loads(EVALUATOR_SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(
            schema, format_checker=Draft202012Validator.FORMAT_CHECKER
        ).iter_errors(value),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        error = errors[0]
        location = ".".join(str(item) for item in error.absolute_path) or "root"
        raise MaturityAcceptanceV3Error(
            f"V3 evaluator receipt schema violation at {location}: {error.message}"
        )


def current_evaluator_hashes_v3() -> dict[str, str]:
    """Return every live source/schema hash that changes V3 evaluation."""

    return {
        "evaluator_code_sha256": file_sha256(EVALUATOR_PATH),
        "evaluator_schema_sha256": file_sha256(EVALUATOR_SCHEMA_PATH),
        "protocol_validator_sha256": file_sha256(
            Path(__file__).with_name("maturity_preregistration_v3.py")
        ),
        "protocol_schema_sha256": file_sha256(PROTOCOL_SCHEMA_PATH),
        "fixture_receipt_schema_sha256": file_sha256(FIXTURE_RECEIPT_SCHEMA_PATH),
        "fixture_index_schema_sha256": file_sha256(FIXTURE_INDEX_SCHEMA_PATH),
        "target_review_schema_sha256": file_sha256(TARGET_REVIEW_SCHEMA_PATH),
        "canonical_surface_adapter_sha256": file_sha256(CANONICAL_ADAPTER_PATH),
        "surface_receipt_schema_sha256": file_sha256(SURFACE_RECEIPT_SCHEMA_PATH),
        "target_profile_catalog_sha256": file_sha256(TARGET_CATALOG_PATH),
    }


def _authority(
    protocol: dict[str, Any], fixture_receipt: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    normalized = validate_preregistered_protocol_v3(protocol)
    predecessor = reopen_predecessor_v3(verify_payloads=True)
    index = verify_fixture_index_v3(
        protocol=normalized,
        index_path=V3_INDEX_PATH,
        expected_root=V3_FIXTURE_ROOT,
    )
    sample_id = fixture_receipt.get("sample_id")
    indexed = [item for item in index["fixtures"] if item["sample_id"] == sample_id]
    if len(indexed) != 1:
        raise MaturityAcceptanceV3Error("V3 fixture is outside the frozen 21-case index")
    item = indexed[0]
    receipt_path = V3_FIXTURE_ROOT / item["receipt_relative_path"]
    if (
        not receipt_path.is_file()
        or file_sha256(receipt_path) != item["receipt_file_sha256"]
        or fixture_receipt.get("receipt_sha256") != item["receipt_sha256"]
    ):
        raise MaturityAcceptanceV3Error("V3 fixture receipt file/index binding drifted")
    verified_fixture = verify_fixture_receipt_v3(
        protocol=normalized,
        receipt=fixture_receipt,
        fixture_root=V3_FIXTURE_ROOT / item["fixture_relative_path"],
        materializer_path=V3_MATERIALIZER_PATH,
        predecessor=predecessor,
        declared_fixture_root=V3_FIXTURE_ROOT / item["fixture_relative_path"],
    )
    samples = {
        sample["sample_id"]: sample for sample in predecessor["protocol"]["samples"]
    }
    sample = samples.get(sample_id)
    if sample is None:
        raise MaturityAcceptanceV3Error("V3 fixture has no predecessor sample semantics")
    return normalized, predecessor["protocol"], verified_fixture, sample


def _required_evidence(sample: dict[str, Any]) -> set[str]:
    required = set(V3_ALWAYS_REQUIRED_EVIDENCE)
    required.update(V3_CONDITIONAL_REQUIRED_EVIDENCE.get(sample["figure_mode"], ()))
    return required


def derive_hard_checks_v3(
    semantics: dict[str, Any],
    sample: dict[str, Any],
    fixture: dict[str, Any],
    entry_mode: str,
    evidence: dict[str, dict[str, Any]],
    subject: dict[str, Any],
) -> dict[str, str]:
    """Recompute V2-preserved hard semantics from V3-bound artifact bytes."""

    v1_names = set(v1.ALWAYS_REQUIRED_EVIDENCE)
    v1_names.update(v1.CONDITIONAL_REQUIRED_EVIDENCE.get(sample["figure_mode"], ()))
    if not v1_names.issubset(evidence):
        raise MaturityAcceptanceV3Error("V3 receipt lacks base hard-check evidence")
    base = {name: evidence[name] for name in v1_names}
    try:
        checks = v1._derive_hard_checks(  # noqa: SLF001 - frozen predecessor semantics
            semantics, sample, fixture, entry_mode, base, subject
        )
        _path, target_review = v1._load_evidence(  # noqa: SLF001
            evidence["target_review_receipt"], subject
        )
        if target_review is None:
            raise MaturityAcceptanceV3Error("V3 target review must be typed JSON")
        context = v2.authoritative_context_from_evidence(evidence, subject)
        target = v2.evaluate_target_adaptation_v2(
            semantics,
            sample,
            target_review,
            subject=subject,
            authoritative_context=context,
        )
    except (v1.MaturityAcceptanceError, v2.MaturityAcceptanceV2Error) as exc:
        raise MaturityAcceptanceV3Error(str(exc)) from exc
    checks["target_adaptation"] = target["target_adaptation"]
    return checks


def _validate_receipt(
    protocol: dict[str, Any], receipt: dict[str, Any]
) -> dict[str, Any]:
    normalized = validate_preregistered_protocol_v3(protocol)
    value = copy.deepcopy(receipt)
    _schema_validate(value)
    pins = current_evaluator_hashes_v3()
    expected_protocol_pins = {
        "protocol_validator_sha256": normalized["evaluator_requirements"][
            "validator_code_sha256"
        ],
        "protocol_schema_sha256": normalized["evaluator_requirements"][
            "protocol_schema_sha256"
        ],
        "fixture_receipt_schema_sha256": normalized["evaluator_requirements"][
            "fixture_receipt_schema_sha256"
        ],
        "fixture_index_schema_sha256": normalized["evaluator_requirements"][
            "fixture_index_schema_sha256"
        ],
        "target_review_schema_sha256": normalized["evaluator_requirements"][
            "target_review_schema_sha256"
        ],
        "canonical_surface_adapter_sha256": normalized["evaluator_requirements"][
            "canonical_surface_adapter_sha256"
        ],
        "surface_receipt_schema_sha256": normalized["evaluator_requirements"][
            "surface_receipt_schema_sha256"
        ],
        "target_profile_catalog_sha256": normalized["semantic_commitments"][
            "target_profile_catalog_sha256"
        ],
    }
    if any(pins[key] != expected for key, expected in expected_protocol_pins.items()):
        raise MaturityAcceptanceV3Error("V3 evaluator live source differs from protocol pins")
    if (
        value["contract"] != "paperspine5.maturity-independent-evaluation-v3"
        or value["contract_version"] != "3.0"
        or value["protocol_file_sha256"] != file_sha256(V3_PROTOCOL_PATH)
        or value["protocol_sha256"] != normalized["protocol_sha256"]
        or value["predecessor_protocol_file_sha256"]
        != normalized["predecessor"]["protocol_file_sha256"]
        or value["predecessor_protocol_sha256"]
        != normalized["predecessor"]["protocol_sha256"]
        or value["evaluator_identity"] != EVALUATOR_IDENTITY
        or value["producer_identity"] == value["evaluator_identity"]
        or value["external_action_authorized"] is not False
        or value["receipt_sha256"]
        != canonical_sha256(value, self_hash="receipt_sha256")
        or any(value[key] != expected for key, expected in pins.items())
    ):
        raise MaturityAcceptanceV3Error("V3 evaluator identity/source/self-hash drift")
    return value


def build_independent_evaluation_receipt_v3(
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
    normalized, semantics, fixture, sample = _authority(protocol, fixture_receipt)
    if not run_id.startswith("psgap014-v3."):
        raise MaturityAcceptanceV3Error("V3 evaluator run_id namespace drift")
    if entry_mode != sample["entry_mode"]:
        raise MaturityAcceptanceV3Error("entry mode differs from V3 registered semantics")
    if attempt not in range(1, semantics["consecutive_runs_per_entry"] + 1):
        raise MaturityAcceptanceV3Error("attempt is outside the frozen V3 matrix")
    if subject.get("material_snapshot_sha256") != fixture["material_snapshot_sha256"]:
        raise MaturityAcceptanceV3Error("V3 subject material differs from the fixture")
    if evaluator_identity != EVALUATOR_IDENTITY or producer_identity == evaluator_identity:
        raise MaturityAcceptanceV3Error("producer cannot act as the V3 evaluator")
    if _parse_time(evaluated_at, "evaluated_at") < _parse_time(
        fixture["first_run_not_before"], "first_run_not_before"
    ):
        raise MaturityAcceptanceV3Error("V3 evaluation predates first_run_not_before")
    if set(evidence) != _required_evidence(sample):
        raise MaturityAcceptanceV3Error("V3 evaluator evidence is incomplete or unknown")
    fixture_ref = evidence["fixture_freeze_receipt"]
    fixture_path = Path(fixture_ref["path"]).resolve()
    if (
        fixture_ref.get("subject") != subject
        or not fixture_path.is_file()
        or file_sha256(fixture_path) != fixture_ref.get("sha256")
        or json.loads(fixture_path.read_text(encoding="utf-8")).get("receipt_sha256")
        != fixture["receipt_sha256"]
    ):
        raise MaturityAcceptanceV3Error("V3 fixture evidence binding drift")
    hard_checks = derive_hard_checks_v3(
        semantics, sample, fixture, entry_mode, evidence, subject
    )
    pins = current_evaluator_hashes_v3()
    receipt = {
        "contract": "paperspine5.maturity-independent-evaluation-v3",
        "contract_version": "3.0",
        "run_id": run_id,
        "sample_id": sample["sample_id"],
        "entry_mode": entry_mode,
        "attempt": attempt,
        "protocol_file_sha256": file_sha256(V3_PROTOCOL_PATH),
        "protocol_sha256": normalized["protocol_sha256"],
        "predecessor_protocol_file_sha256": normalized["predecessor"][
            "protocol_file_sha256"
        ],
        "predecessor_protocol_sha256": normalized["predecessor"]["protocol_sha256"],
        "fixture_receipt_file_sha256": file_sha256(fixture_path),
        "fixture_receipt_sha256": fixture["receipt_sha256"],
        "producer_identity": producer_identity,
        "evaluator_identity": evaluator_identity,
        **pins,
        "evaluated_at": evaluated_at,
        "subject": copy.deepcopy(subject),
        "evidence": copy.deepcopy(evidence),
        "hard_checks": hard_checks,
        "status": "PASS" if set(hard_checks.values()) == {"PASS"} else "FAIL",
        "external_action_authorized": False,
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    return _validate_receipt(normalized, receipt)


def verify_independent_evaluation_receipt_v3(
    protocol: dict[str, Any],
    fixture_receipt: dict[str, Any],
    receipt: dict[str, Any],
) -> dict[str, Any]:
    normalized, semantics, fixture, sample = _authority(protocol, fixture_receipt)
    value = _validate_receipt(normalized, receipt)
    if (
        value["fixture_receipt_sha256"] != fixture["receipt_sha256"]
        or value["sample_id"] != fixture["sample_id"]
        or value["entry_mode"] != sample["entry_mode"]
        or value["subject"]["material_snapshot_sha256"]
        != fixture["material_snapshot_sha256"]
        or value["fixture_receipt_file_sha256"]
        != value["evidence"]["fixture_freeze_receipt"]["sha256"]
    ):
        raise MaturityAcceptanceV3Error("V3 evaluator fixture/subject binding drift")
    if set(value["evidence"]) != _required_evidence(sample):
        raise MaturityAcceptanceV3Error("V3 persisted evidence is incomplete or unknown")
    recomputed = derive_hard_checks_v3(
        semantics,
        sample,
        fixture,
        value["entry_mode"],
        value["evidence"],
        value["subject"],
    )
    expected_status = "PASS" if set(recomputed.values()) == {"PASS"} else "FAIL"
    if value["hard_checks"] != recomputed or value["status"] != expected_status:
        raise MaturityAcceptanceV3Error("V3 evaluator hard checks/status do not recompute")
    if _parse_time(value["evaluated_at"], "evaluated_at") < _parse_time(
        fixture["first_run_not_before"], "first_run_not_before"
    ):
        raise MaturityAcceptanceV3Error("V3 evaluation predates first_run_not_before")
    return copy.deepcopy(value)


__all__ = [
    "EVALUATOR_IDENTITY",
    "EVALUATOR_PATH",
    "EVALUATOR_SCHEMA_PATH",
    "MaturityAcceptanceV3Error",
    "V3_ALWAYS_REQUIRED_EVIDENCE",
    "V3_CONDITIONAL_REQUIRED_EVIDENCE",
    "build_independent_evaluation_receipt_v3",
    "current_evaluator_hashes_v3",
    "derive_hard_checks_v3",
    "verify_independent_evaluation_receipt_v3",
]
