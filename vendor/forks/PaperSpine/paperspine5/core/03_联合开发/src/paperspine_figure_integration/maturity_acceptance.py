"""Independent, fail-closed preregistration for PS-GAP-014.

The producer cannot submit maturity metrics. A frozen protocol binds evaluator
code/schema; fixture receipts are built from actual file bytes; and the
independent evaluator reopens surfaces and verifies typed authority evidence.
"""

from __future__ import annotations

import copy
import hashlib
import json
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[3]
PROTOCOL_SCHEMA_PATH = ROOT / "03_联合开发" / "contracts" / "maturity-acceptance-protocol.schema.json"
EVALUATOR_SCHEMA_PATH = ROOT / "03_联合开发" / "contracts" / "maturity-evaluator-receipt.schema.json"
EVALUATOR_IDENTITY = "paperspine5-independent-maturity-evaluator"
REQUIRED_COVERAGE = {
    "workflows": {"rewrite_existing", "build_from_materials"},
    "languages": {"en", "zh"},
    "material_forms": {"manuscript", "mixed_materials", "formula_dense", "word_source"},
    "figure_modes": {"no_figures", "multi_figure", "identity_conflict"},
    "literature_modes": {"closed_corpus", "open_literature", "provider_outage"},
    "author_fact_modes": {"complete", "missing"},
    "target_templates": {"oup", "ieee", "generic_latex", "word_heavy"},
    "publication_cycles": {"local_submission", "local_revision", "local_transfer"},
    "recovery_modes": {"uninterrupted_control", "forced_interrupt", "fresh_install"},
}
SAMPLE_FIELD_BY_COVERAGE = {
    "workflows": "workflow",
    "languages": "language",
    "material_forms": "material_form",
    "figure_modes": "figure_mode",
    "literature_modes": "literature_mode",
    "author_fact_modes": "author_facts",
    "target_templates": "target_template",
    "publication_cycles": "publication_cycle",
    "recovery_modes": "recovery_mode",
}
PAIRWISE_FIELDS = tuple(SAMPLE_FIELD_BY_COVERAGE.values())
ALWAYS_REQUIRED_EVIDENCE = (
    "task_snapshot",
    "artifact_ledger",
    "package_manifest",
    "pdf",
    "docx",
    "render_receipt",
    "citation_receipt",
    "target_review_receipt",
    "readiness_receipt",
    "recovery_or_install_receipt",
)
CONDITIONAL_REQUIRED_EVIDENCE = {
    "identity_conflict": ("figure_identity_receipt",),
}


class MaturityAcceptanceError(ValueError):
    """Raised when protocol/evidence is mutable, forged, or incomplete."""


def _canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _without_hash(value: dict[str, Any], field: str) -> dict[str, Any]:
    subject = copy.deepcopy(value)
    subject.pop(field, None)
    return subject


def protocol_sha256(protocol: dict[str, Any]) -> str:
    return _sha256(_without_hash(protocol, "protocol_sha256"))


def current_evaluator_hashes() -> tuple[str, str, str]:
    code_sha256 = _file_sha256(Path(__file__).resolve())
    evaluator_schema_sha256 = _file_sha256(EVALUATOR_SCHEMA_PATH)
    protocol_schema_sha256 = _file_sha256(PROTOCOL_SCHEMA_PATH)
    return code_sha256, evaluator_schema_sha256, protocol_schema_sha256


def _parse_time(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError) as exc:
        raise MaturityAcceptanceError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise MaturityAcceptanceError(f"{field} must include a timezone")
    return parsed


def _schema_errors(value: dict[str, Any], schema_path: Path, label: str) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER).iter_errors(value),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        error = errors[0]
        location = ".".join(str(item) for item in error.absolute_path) or "root"
        raise MaturityAcceptanceError(f"{label} schema violation at {location}: {error.message}")


def _coverage_name(field: str) -> str:
    return next(name for name, sample_field in SAMPLE_FIELD_BY_COVERAGE.items() if sample_field == field)


def validate_protocol_design(protocol: dict[str, Any]) -> dict[str, Any]:
    """Validate a draft without representing it as frozen."""

    if not isinstance(protocol, dict):
        raise MaturityAcceptanceError("protocol must be an object")
    _schema_errors(protocol, PROTOCOL_SCHEMA_PATH, "protocol")
    evaluator = protocol["evaluator_requirements"]
    if tuple(evaluator["required_evidence_types"]) != ALWAYS_REQUIRED_EVIDENCE:
        raise MaturityAcceptanceError(
            "protocol always-required evidence differs from evaluator contract"
        )
    conditional = {
        mode: tuple(evidence_types)
        for mode, evidence_types in evaluator[
            "conditional_required_evidence_types"
        ].items()
    }
    if conditional != CONDITIONAL_REQUIRED_EVIDENCE:
        raise MaturityAcceptanceError(
            "protocol conditional evidence differs from evaluator contract"
        )
    if set(protocol["required_entry_modes"]) != {"natural_language", "explicit_paper_spine"}:
        raise MaturityAcceptanceError("both canonical simple-entry modes are required")
    samples = protocol["samples"]
    sample_ids = [sample["sample_id"] for sample in samples]
    if len(sample_ids) != len(set(sample_ids)):
        raise MaturityAcceptanceError("sample_id values must be unique")
    families = {sample["fixture_family_id"] for sample in samples}
    if len(families) < protocol["minimum_distinct_fixture_families"]:
        raise MaturityAcceptanceError("insufficient distinct fixture families")
    carbon_count = sum(sample["benchmark_lineage"] == "carbon_oup" for sample in samples)
    if carbon_count < 1 or carbon_count * 3 > len(samples):
        raise MaturityAcceptanceError("CARBON/OUP must be present but cannot exceed one third")
    entries = {
        mode: sum(sample["entry_mode"] == mode for sample in samples)
        for mode in protocol["required_entry_modes"]
    }
    if min(entries.values()) == 0 or max(entries.values()) - min(entries.values()) > 1:
        raise MaturityAcceptanceError("natural and explicit entries must be balanced across cases")
    for coverage_name, required_values in REQUIRED_COVERAGE.items():
        if set(protocol["coverage_requirements"][coverage_name]) != required_values:
            raise MaturityAcceptanceError(f"coverage_requirements.{coverage_name} differs")
        field = SAMPLE_FIELD_BY_COVERAGE[coverage_name]
        missing = required_values - {sample[field] for sample in samples}
        if missing:
            raise MaturityAcceptanceError(f"sample matrix misses {coverage_name}: {sorted(missing)}")
    if set(protocol["thresholds"]["required_section_roles"]) != {"methods", "results"}:
        raise MaturityAcceptanceError("Methods and Results roles are mandatory")
    for left_index, left_field in enumerate(PAIRWISE_FIELDS):
        for right_field in PAIRWISE_FIELDS[left_index + 1 :]:
            expected = {
                (left, right)
                for left in REQUIRED_COVERAGE[_coverage_name(left_field)]
                for right in REQUIRED_COVERAGE[_coverage_name(right_field)]
            }
            observed = {(sample[left_field], sample[right_field]) for sample in samples}
            if not expected.issubset(observed):
                raise MaturityAcceptanceError(
                    f"pairwise coverage missing for {left_field}×{right_field}: {sorted(expected - observed)[:5]}"
                )
    return copy.deepcopy(protocol)


def validate_preregistered_protocol(protocol: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    """Reject drafts, future dates, stale evaluator code, and hash drift."""

    normalized = validate_protocol_design(protocol)
    if normalized["status"] != "design_frozen":
        raise MaturityAcceptanceError("protocol is draft_unfrozen and cannot accept results")
    frozen_at = _parse_time(normalized["frozen_at"], "frozen_at")
    if frozen_at > (now or datetime.now().astimezone()):
        raise MaturityAcceptanceError("protocol frozen_at cannot be in the future")
    if normalized["protocol_sha256"] != protocol_sha256(normalized):
        raise MaturityAcceptanceError("protocol_sha256 does not bind the frozen design")
    code_sha256, evaluator_schema_sha256, protocol_schema_sha256 = (
        current_evaluator_hashes()
    )
    evaluator = normalized["evaluator_requirements"]
    if evaluator["evaluator_code_sha256"] != code_sha256:
        raise MaturityAcceptanceError("evaluator code hash differs from frozen protocol")
    if evaluator["evaluator_schema_sha256"] != evaluator_schema_sha256:
        raise MaturityAcceptanceError("evaluator schema hash differs from frozen protocol")
    if evaluator["protocol_schema_sha256"] != protocol_schema_sha256:
        raise MaturityAcceptanceError("protocol schema hash differs from frozen protocol")
    return normalized


def _sample(protocol: dict[str, Any], sample_id: str) -> dict[str, Any]:
    matches = [sample for sample in protocol["samples"] if sample["sample_id"] == sample_id]
    if len(matches) != 1:
        raise MaturityAcceptanceError(f"sample is not uniquely registered: {sample_id}")
    return matches[0]


def _tree_entries(root: Path) -> list[dict[str, Any]]:
    if not root.is_dir():
        raise MaturityAcceptanceError(f"fixture root is not a directory: {root}")
    entries = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink():
            raise MaturityAcceptanceError("fixture trees cannot contain symlinks")
        if path.is_file():
            entries.append({
                "relative_path": path.relative_to(root).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": _file_sha256(path),
            })
    if not entries:
        raise MaturityAcceptanceError("fixture tree must contain versioned material bytes")
    return entries


def build_fixture_freeze_receipt(
    protocol: dict[str, Any], *, sample_id: str, fixture_root: str | Path,
    fixture_provenance: str, freezer_identity: str, bound_at: str,
    first_run_not_before: str,
) -> dict[str, Any]:
    """Hash every fixture byte; never infer real provenance from a digest."""

    normalized = validate_preregistered_protocol(protocol)
    sample = _sample(normalized, sample_id)
    if fixture_provenance != sample["fixture_provenance"]:
        raise MaturityAcceptanceError("fixture provenance differs from preregistration")
    if not freezer_identity or freezer_identity == "producer":
        raise MaturityAcceptanceError("fixture freezer must be a named host authority")
    root = Path(fixture_root).resolve()
    entries = _tree_entries(root)
    bound = _parse_time(bound_at, "bound_at")
    first_run = _parse_time(first_run_not_before, "first_run_not_before")
    frozen = _parse_time(normalized["frozen_at"], "frozen_at")
    if not (frozen <= bound <= first_run):
        raise MaturityAcceptanceError("protocol freeze must precede fixture freeze and runs")
    receipt = {
        "contract": "paperspine5.maturity-fixture-freeze", "contract_version": "1.0",
        "sample_id": sample_id, "fixture_family_id": sample["fixture_family_id"],
        "fixture_provenance": fixture_provenance, "benchmark_lineage": sample["benchmark_lineage"],
        "author_facts_are_fixture_only": True, "protocol_sha256": normalized["protocol_sha256"],
        "fixture_root": str(root), "entries": entries, "file_count": len(entries),
        "total_bytes": sum(entry["size_bytes"] for entry in entries),
        "fixture_tree_sha256": _sha256(entries),
        "material_snapshot_sha256": _sha256({"sample_id": sample_id, "entries": entries}),
        "freezer_identity": freezer_identity, "bound_at": bound_at,
        "first_run_not_before": first_run_not_before, "external_action_authorized": False,
    }
    receipt["receipt_sha256"] = _sha256(receipt)
    return receipt


def verify_fixture_freeze_receipt(protocol: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    normalized = validate_preregistered_protocol(protocol)
    required = {
        "contract", "contract_version", "sample_id", "fixture_family_id", "fixture_provenance",
        "benchmark_lineage", "author_facts_are_fixture_only", "protocol_sha256", "fixture_root",
        "entries", "file_count", "total_bytes", "fixture_tree_sha256", "material_snapshot_sha256",
        "freezer_identity", "bound_at", "first_run_not_before", "external_action_authorized", "receipt_sha256",
    }
    if set(receipt) != required:
        raise MaturityAcceptanceError("fixture freeze fields are missing or unknown")
    sample = _sample(normalized, receipt["sample_id"])
    if (
        receipt["contract"] != "paperspine5.maturity-fixture-freeze"
        or receipt["contract_version"] != "1.0"
        or receipt["fixture_family_id"] != sample["fixture_family_id"]
        or receipt["fixture_provenance"] != sample["fixture_provenance"]
        or receipt["benchmark_lineage"] != sample["benchmark_lineage"]
        or receipt["author_facts_are_fixture_only"] is not True
        or receipt["protocol_sha256"] != normalized["protocol_sha256"]
        or receipt["external_action_authorized"] is not False
        or receipt["receipt_sha256"] != _sha256(_without_hash(receipt, "receipt_sha256"))
    ):
        raise MaturityAcceptanceError("fixture freeze subject/hash/provenance is invalid")
    entries = _tree_entries(Path(receipt["fixture_root"]).resolve())
    if entries != receipt["entries"]:
        raise MaturityAcceptanceError("fixture bytes drifted after freeze")
    if (
        receipt["file_count"] != len(entries)
        or receipt["total_bytes"] != sum(entry["size_bytes"] for entry in entries)
        or receipt["fixture_tree_sha256"] != _sha256(entries)
        or receipt["material_snapshot_sha256"] != _sha256({"sample_id": receipt["sample_id"], "entries": entries})
    ):
        raise MaturityAcceptanceError("fixture inventory totals or hashes are invalid")
    frozen = _parse_time(normalized["frozen_at"], "frozen_at")
    bound = _parse_time(receipt["bound_at"], "bound_at")
    first_run = _parse_time(receipt["first_run_not_before"], "first_run_not_before")
    if not (frozen <= bound <= first_run):
        raise MaturityAcceptanceError("fixture freeze timestamps are out of order")
    return copy.deepcopy(receipt)


def _load_evidence(ref: dict[str, Any], subject: dict[str, Any]) -> tuple[Path, Any]:
    if ref["subject"] != subject:
        raise MaturityAcceptanceError("evidence subject drifted from evaluated task")
    path = Path(ref["path"]).resolve()
    if not path.is_file() or _file_sha256(path) != ref["sha256"]:
        raise MaturityAcceptanceError(f"evidence byte/hash mismatch: {ref['artifact_id']}")
    if path.suffix.lower() != ".json":
        return path, None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("subject") != subject:
        raise MaturityAcceptanceError("typed evidence subject mismatch")
    if payload.get("receipt_sha256") != _sha256(_without_hash(payload, "receipt_sha256")):
        raise MaturityAcceptanceError("typed evidence self-hash mismatch")
    return path, payload


def _pdf_openable(path: Path) -> bool:
    try:
        import fitz

        document = fitz.open(path)
        try:
            return document.page_count > 0 and all(
                document.load_page(index).get_pixmap(matrix=fitz.Matrix(0.2, 0.2)).samples
                for index in range(document.page_count)
            )
        finally:
            document.close()
    except Exception:
        return False


def _docx_openable(path: Path) -> bool:
    try:
        with zipfile.ZipFile(path) as archive:
            return archive.testzip() is None and {"[Content_Types].xml", "word/document.xml"}.issubset(archive.namelist())
    except (OSError, zipfile.BadZipFile):
        return False


def _authority(payload: dict[str, Any], contract: str, authority: str) -> bool:
    return payload.get("contract") == contract and payload.get("authority") == authority


def _valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )


def _linked_file(ref: dict[str, Any], subject: dict[str, Any]) -> dict[str, Any]:
    path, payload = _load_evidence(ref, subject)
    if payload is None:
        raise MaturityAcceptanceError(f"linked evidence must be typed JSON: {path}")
    return payload


def _figure_mode_valid(
    sample: dict[str, Any],
    artifacts: dict[str, Any],
    identity_review: dict[str, Any] | None,
) -> bool:
    expected = artifacts.get("expected_figure_count")
    delivered = artifacts.get("delivered_figure_count")
    source_ids = artifacts.get("figure_source_ids", [])
    source_hashes = artifacts.get("figure_source_hashes", {})
    dispositions = artifacts.get("figure_dispositions", {})
    basic = (
        isinstance(expected, int)
        and isinstance(delivered, int)
        and expected == delivered
        and len(source_ids) == len(set(source_ids)) == expected
        and set(source_hashes) == set(source_ids)
        and all(_valid_sha256(value) for value in source_hashes.values())
        and set(dispositions) == set(source_ids)
        and set(dispositions.values()).issubset({"retained", "transformed"})
    )
    if sample["figure_mode"] == "no_figures":
        return basic and expected == 0 and source_ids == [] and identity_review is None
    if not basic or expected <= 0 or artifacts.get("figure_source_coverage") != 1.0:
        return False
    if sample["figure_mode"] == "multi_figure":
        return identity_review is None
    return bool(
        identity_review
        and _authority(
            identity_review,
            "paperspine5.figure-identity-conflict-resolution",
            "independent-figure-identity-reviewer",
        )
        and identity_review.get("producer_identity")
        != identity_review.get("reviewer_identity")
        and identity_review.get("reviewer_identity")
        == "independent-figure-identity-reviewer"
        and identity_review.get("status") == "PASS"
        and identity_review.get("source_ids") == source_ids
        and identity_review.get("source_hashes") == source_hashes
        and identity_review.get("resolved_canonical_ids") == source_ids
        and identity_review.get("omitted_source_ids") == []
    )


def _citation_mode_valid(sample: dict[str, Any], citation: dict[str, Any]) -> bool:
    if not _authority(
        citation, "paperspine5.maturity-citation-evidence", "citation-audit"
    ):
        return False
    if citation.get("destructive_changes") != 0 or citation.get("unsupported_claims") != 0:
        return False
    if citation.get("provider_semantics_valid") is not True:
        return False
    if sample["literature_mode"] != "provider_outage":
        return citation.get("literature_mode") == sample["literature_mode"]
    forbidden = {"verified", "dead", "retracted", "hallucinated", "not_found"}
    conclusions = set(citation.get("provider_conclusions", []))
    return (
        citation.get("literature_mode") == "provider_outage"
        and citation.get("provider_status") == "unreachable"
        and citation.get("provider_verified") is False
        and citation.get("bibliographic_status") == "unverified"
        and not conclusions.intersection(forbidden)
    )


def _recovery_mode_valid(
    sample: dict[str, Any],
    recovery: dict[str, Any],
    task: dict[str, Any],
    subject: dict[str, Any],
) -> bool:
    if sample["recovery_mode"] == "forced_interrupt":
        cases = recovery.get("cases", [])
        return bool(
            _authority(
                recovery,
                "paperspine5.runner-recovery-matrix-receipt",
                "paperspine5-recovery-harness",
            )
            and recovery.get("ps_gap_013_source_component_accepted") is True
            and {case.get("boundary") for case in cases}
            == {"intake", "citation_research", "drafting_canonical", "latex_rendering"}
            and all(
                case.get("forced_exit") not in {None, 0}
                and case.get("killed_pid") != case.get("recovery_pid")
                and case.get("killed_runtime_id") != case.get("recovery_runtime_id")
                and case.get("task_state_sha256") == task.get("task_state_sha256")
                and case.get("artifact_set_sha256") == task.get("artifact_set_sha256")
                and case.get("package_set_sha256") == task.get("package_set_sha256")
                for case in cases
            )
            and recovery.get("control_hashes")
            == {
                "task_state_sha256": task.get("task_state_sha256"),
                "artifact_set_sha256": task.get("artifact_set_sha256"),
                "package_set_sha256": task.get("package_set_sha256"),
            }
            and recovery.get("material_snapshot_sha256")
            == subject["material_snapshot_sha256"]
        )
    if sample["recovery_mode"] == "fresh_install":
        links = recovery.get("linked_evidence", {})
        if set(links) != {
            "plugin_outer_receipt",
            "skill_outer_receipt",
            "installed_suite_pointer",
            "content_index",
            "suite_manifest",
        }:
            return False
        try:
            linked = {name: _linked_file(ref, subject) for name, ref in links.items()}
            restart_time = _parse_time(recovery["restart_completed_at"], "restart_completed_at")
            task_time = _parse_time(task["task_started_at"], "task_started_at")
            plugin_time = _parse_time(
                linked["plugin_outer_receipt"]["committed_at"],
                "plugin_outer_receipt.committed_at",
            )
            skill_time = _parse_time(
                linked["skill_outer_receipt"]["committed_at"],
                "skill_outer_receipt.committed_at",
            )
            pointer_time = _parse_time(
                linked["installed_suite_pointer"]["installed_at"],
                "installed_suite_pointer.installed_at",
            )
            content_index_time = _parse_time(
                linked["content_index"]["generated_at"],
                "content_index.generated_at",
            )
            manifest_time = _parse_time(
                linked["suite_manifest"]["generated_at"],
                "suite_manifest.generated_at",
            )
        except (KeyError, MaturityAcceptanceError):
            return False
        outer_ok = all(
            _authority(
                linked[name],
                "paperspine5.user-update-receipt",
                "paperspine5-user-updater",
            )
            and linked[name].get("install_kind")
            == ("plugin" if name == "plugin_outer_receipt" else "skill")
            and linked[name].get("status") == "committed"
            and linked[name].get("requested_target_applied") is True
            and linked[name].get("compensation_performed") is False
            and linked[name].get("candidate_build_id") == subject["build_id"]
            and linked[name].get("content_index_id")
            == recovery.get("content_index_id")
            for name in ("plugin_outer_receipt", "skill_outer_receipt")
        )
        pointer = linked["installed_suite_pointer"]
        content_index = linked["content_index"]
        manifest = linked["suite_manifest"]
        return bool(
            _authority(
                recovery,
                "paperspine5.fresh-install-acceptance-receipt",
                "paperspine5-updater-and-host",
            )
            and outer_ok
            and recovery.get("build_id") == subject["build_id"]
            and _valid_sha256(recovery.get("content_index_id"))
            and _authority(
                pointer,
                "paperspine5.installed-suite-pointer",
                "paperspine5-user-updater",
            )
            and pointer.get("build_id") == subject["build_id"]
            and pointer.get("canonical_skill_name") == "paper-spine"
            and pointer.get("content_index_id") == recovery.get("content_index_id")
            and pointer.get("manifest_sha256")
            == _file_sha256(Path(links["suite_manifest"]["path"]))
            and _authority(
                manifest,
                "paperspine5.suite-manifest",
                "paperspine5-release-builder",
            )
            and manifest.get("build_id") == subject["build_id"]
            and manifest.get("content_index_id") == recovery.get("content_index_id")
            and manifest.get("plugin_skills") == []
            and pointer.get("content_index_sha256")
            == _file_sha256(Path(links["content_index"]["path"]))
            and _authority(
                content_index,
                "paperspine5.content-index",
                "paperspine5-release-builder",
            )
            and content_index.get("build_id") == subject["build_id"]
            and content_index.get("content_index_id") == recovery.get("content_index_id")
            and content_index.get("discovered_skills") == []
            and recovery.get("paper_spine_discovery_count") == 1
            and recovery.get("paperfig_discovery_count") == 0
            and recovery.get("workspace_discovery_count") == 0
            and content_index_time <= plugin_time
            and manifest_time <= plugin_time <= skill_time <= pointer_time
            and pointer_time <= restart_time < task_time
        )
    return bool(
        _authority(
            recovery,
            "paperspine5.uninterrupted-control-receipt",
            "paperspine5-recovery-harness",
        )
        and recovery.get("status") == "PASS"
        and recovery.get("material_snapshot_sha256") == subject["material_snapshot_sha256"]
        and recovery.get("task_state_sha256") == task.get("task_state_sha256")
        and recovery.get("artifact_set_sha256") == task.get("artifact_set_sha256")
        and recovery.get("package_set_sha256") == task.get("package_set_sha256")
    )


def _derive_hard_checks(
    protocol: dict[str, Any], sample: dict[str, Any], fixture: dict[str, Any],
    entry_mode: str, evidence: dict[str, dict[str, Any]], subject: dict[str, Any]
) -> dict[str, str]:
    loaded = {name: _load_evidence(ref, subject) for name, ref in evidence.items()}
    task, artifacts, package = loaded["task_snapshot"][1], loaded["artifact_ledger"][1], loaded["package_manifest"][1]
    render, citation = loaded["render_receipt"][1], loaded["citation_receipt"][1]
    target, readiness = loaded["target_review_receipt"][1], loaded["readiness_receipt"][1]
    recovery = loaded["recovery_or_install_receipt"][1]
    identity_review = (
        loaded["figure_identity_receipt"][1]
        if "figure_identity_receipt" in loaded
        else None
    )
    thresholds = protocol["thresholds"]
    package_valid = _authority(package, "paperspine5.maturity-package-evidence", "product-kernel") and all(
        Path(item["path"]).is_file() and _file_sha256(Path(item["path"])) == item["sha256"]
        for item in package.get("files", [])
    )
    registered_task = {
        "sample_id": sample["sample_id"],
        "entry_mode": entry_mode,
        "workflow": sample["workflow"],
        "language": sample["language"],
        "material_form": sample["material_form"],
        "figure_mode": sample["figure_mode"],
        "literature_mode": sample["literature_mode"],
        "author_facts": sample["author_facts"],
        "target_template": sample["target_template"],
        "publication_cycle": sample["publication_cycle"],
        "recovery_mode": sample["recovery_mode"],
        "fixture_tree_sha256": fixture["fixture_tree_sha256"],
        "material_snapshot_sha256": fixture["material_snapshot_sha256"],
    }
    task_binding_valid = all(task.get(field) == value for field, value in registered_task.items())
    recovery_valid = _recovery_mode_valid(sample, recovery, task, subject)
    expected_submission = sample["author_facts"] == "complete"
    checks = {
        "task_authority": _authority(task, "paperspine5.maturity-task-evidence", "product-kernel")
        and task_binding_valid
        and subject["material_snapshot_sha256"] == fixture["material_snapshot_sha256"],
        "material_coverage": _authority(artifacts, "paperspine5.maturity-artifact-evidence", "product-kernel")
        and artifacts.get("material_coverage") == thresholds["material_coverage_min"],
        "methods_results": set(thresholds["required_section_roles"]).issubset(artifacts.get("section_roles_present", [])),
        "figures_preserved": _figure_mode_valid(sample, artifacts, identity_review),
        "references_preserved": artifacts.get("reference_count", 0) > 0,
        "package_hashes": package_valid,
        "pdf_openable": _pdf_openable(loaded["pdf"][0]),
        "docx_openable": _docx_openable(loaded["docx"][0]),
        "render_visible": _authority(render, "paperspine5.maturity-render-evidence", "independent-surface-reviewer")
        and render.get("status") == "PASS" and render.get("blank_figure_frames") == 0,
        "citation_semantics": _citation_mode_valid(sample, citation),
        "target_adaptation": _authority(target, "paperspine5.maturity-target-review-evidence", "independent-target-reviewer")
        and target.get("hard_obligation_ids") == sample["target_obligation_ids"]
        and target.get("all_hard_obligations_satisfied") is True,
        "readiness_layers": _authority(readiness, "paperspine5.maturity-readiness-evidence", "product-kernel")
        and readiness.get("manuscript_ready") is True and readiness.get("delivery_ready") is True
        and readiness.get("submission_ready") is expected_submission
        and readiness.get("external_action_authorized") is False and readiness.get("surface_parity") is True,
        "simple_user_interaction": task.get("initial_user_interactions", 99) <= thresholds["max_total_user_interactions"]
        and task.get("repeat_non_author_questions", 99) <= thresholds["max_unplanned_human_interactions"],
        "bounded_evidence": task.get("agent_log_bytes", 10**18) <= thresholds["max_agent_log_bytes"]
        and task.get("screenshot_bytes", 10**18) <= thresholds["max_screenshot_bytes"]
        and task.get("reviewer_record_bytes", 10**18) <= thresholds["max_reviewer_record_bytes"],
        "recovery_or_install": recovery_valid,
    }
    return {name: "PASS" if passed else "FAIL" for name, passed in checks.items()}


def build_independent_evaluation_receipt(
    protocol: dict[str, Any], fixture_receipt: dict[str, Any], *, run_id: str,
    entry_mode: str, attempt: int, producer_identity: str, evaluator_identity: str,
    evaluated_at: str, subject: dict[str, Any], evidence: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    normalized = validate_preregistered_protocol(protocol)
    fixture = verify_fixture_freeze_receipt(normalized, fixture_receipt)
    sample = _sample(normalized, fixture["sample_id"])
    if entry_mode != sample["entry_mode"]:
        raise MaturityAcceptanceError("entry mode differs from registered case")
    if attempt not in range(1, normalized["consecutive_runs_per_entry"] + 1):
        raise MaturityAcceptanceError("attempt is outside registered consecutive runs")
    if subject.get("material_snapshot_sha256") != fixture["material_snapshot_sha256"]:
        raise MaturityAcceptanceError(
            "evaluation subject material snapshot differs from frozen fixture"
        )
    if producer_identity == evaluator_identity or evaluator_identity != EVALUATOR_IDENTITY:
        raise MaturityAcceptanceError("producer cannot act as independent final evaluator")
    if _parse_time(evaluated_at, "evaluated_at") < _parse_time(fixture["first_run_not_before"], "first_run_not_before"):
        raise MaturityAcceptanceError("evaluation predates frozen fixture/run boundary")
    required_evidence = set(normalized["evaluator_requirements"]["required_evidence_types"])
    required_evidence.update(
        normalized["evaluator_requirements"]["conditional_required_evidence_types"].get(
            sample["figure_mode"], []
        )
    )
    if set(evidence) != required_evidence:
        raise MaturityAcceptanceError("independent evaluator evidence set is incomplete")
    hard_checks = _derive_hard_checks(
        normalized, sample, fixture, entry_mode, evidence, subject
    )
    code_sha256, schema_sha256, _protocol_schema_sha256 = current_evaluator_hashes()
    receipt = {
        "contract": "paperspine5.maturity-independent-evaluation", "contract_version": "1.0",
        "run_id": run_id, "sample_id": sample["sample_id"], "entry_mode": entry_mode,
        "attempt": attempt, "protocol_sha256": normalized["protocol_sha256"],
        "fixture_receipt_sha256": fixture["receipt_sha256"], "producer_identity": producer_identity,
        "evaluator_identity": evaluator_identity, "evaluator_code_sha256": code_sha256,
        "evaluator_schema_sha256": schema_sha256, "evaluated_at": evaluated_at,
        "subject": copy.deepcopy(subject), "evidence": copy.deepcopy(evidence), "hard_checks": hard_checks,
        "status": "PASS" if set(hard_checks.values()) == {"PASS"} else "FAIL",
        "external_action_authorized": False,
    }
    receipt["receipt_sha256"] = _sha256(receipt)
    _schema_errors(receipt, EVALUATOR_SCHEMA_PATH, "evaluator receipt")
    return receipt


def verify_independent_evaluation_receipt(
    protocol: dict[str, Any], fixture_receipt: dict[str, Any], receipt: dict[str, Any]
) -> dict[str, Any]:
    normalized = validate_preregistered_protocol(protocol)
    fixture = verify_fixture_freeze_receipt(normalized, fixture_receipt)
    _schema_errors(receipt, EVALUATOR_SCHEMA_PATH, "evaluator receipt")
    code_sha256, schema_sha256, _protocol_schema_sha256 = current_evaluator_hashes()
    if (
        receipt["protocol_sha256"] != normalized["protocol_sha256"]
        or receipt["fixture_receipt_sha256"] != fixture["receipt_sha256"]
        or receipt["sample_id"] != fixture["sample_id"]
        or receipt["producer_identity"] == receipt["evaluator_identity"]
        or receipt["evaluator_identity"] != EVALUATOR_IDENTITY
        or receipt["evaluator_code_sha256"] != code_sha256
        or receipt["evaluator_schema_sha256"] != schema_sha256
        or receipt["external_action_authorized"] is not False
        or receipt["receipt_sha256"] != _sha256(_without_hash(receipt, "receipt_sha256"))
    ):
        raise MaturityAcceptanceError("independent evaluator identity/hash binding is invalid")
    sample = _sample(normalized, receipt["sample_id"])
    if receipt["subject"].get("material_snapshot_sha256") != fixture[
        "material_snapshot_sha256"
    ]:
        raise MaturityAcceptanceError(
            "evaluation subject material snapshot differs from frozen fixture"
        )
    recomputed = _derive_hard_checks(
        normalized,
        sample,
        fixture,
        receipt["entry_mode"],
        receipt["evidence"],
        receipt["subject"],
    )
    if receipt["hard_checks"] != recomputed:
        raise MaturityAcceptanceError("evaluator hard checks differ from authoritative evidence")
    expected_status = "PASS" if set(recomputed.values()) == {"PASS"} else "FAIL"
    if receipt["status"] != expected_status:
        raise MaturityAcceptanceError("evaluator status differs from recomputed hard checks")
    if _parse_time(receipt["evaluated_at"], "evaluated_at") < _parse_time(fixture["first_run_not_before"], "first_run_not_before"):
        raise MaturityAcceptanceError("evaluation predates fixture freeze")
    return copy.deepcopy(receipt)


def evaluate_preregistered_runs(
    protocol: dict[str, Any], fixture_receipts: list[dict[str, Any]], evaluator_receipts: list[dict[str, Any]]
) -> dict[str, Any]:
    """Aggregate independent receipts; one hard failure makes the round fail."""

    normalized = validate_preregistered_protocol(protocol)
    sample_ids = [receipt.get("sample_id") for receipt in fixture_receipts]
    if len(sample_ids) != len(set(sample_ids)):
        raise MaturityAcceptanceError("duplicate fixture binding for one sample")
    expected_samples = {sample["sample_id"] for sample in normalized["samples"]}
    if set(sample_ids) != expected_samples:
        raise MaturityAcceptanceError("fixture bindings do not exactly cover protocol")
    fixtures = {receipt["sample_id"]: verify_fixture_freeze_receipt(normalized, receipt) for receipt in fixture_receipts}
    run_ids = [receipt.get("run_id") for receipt in evaluator_receipts]
    if len(run_ids) != len(set(run_ids)):
        raise MaturityAcceptanceError("run_id values must be globally unique")
    expected_keys = {
        (sample["sample_id"], sample["entry_mode"], attempt)
        for sample in normalized["samples"]
        for attempt in range(1, normalized["consecutive_runs_per_entry"] + 1)
    }
    observed, failed_runs = {}, []
    for receipt in evaluator_receipts:
        key = (receipt.get("sample_id"), receipt.get("entry_mode"), receipt.get("attempt"))
        if key not in expected_keys:
            raise MaturityAcceptanceError(f"run is outside preregistered matrix: {key}")
        if key in observed:
            raise MaturityAcceptanceError(f"duplicate sample/entry/attempt receipt: {key}")
        verified = verify_independent_evaluation_receipt(normalized, fixtures[key[0]], receipt)
        observed[key] = verified
        if verified["status"] != "PASS":
            failed_runs.append(verified["run_id"])
    missing = sorted(expected_keys - set(observed))
    status = "INCOMPLETE" if missing else "FAIL" if failed_runs else "PASS"
    verdict = {
        "contract": "paperspine5.maturity-acceptance-verdict", "contract_version": "1.0",
        "protocol_id": normalized["protocol_id"], "protocol_sha256": normalized["protocol_sha256"],
        "expected_run_count": len(expected_keys), "observed_run_count": len(observed),
        "missing_runs": [list(key) for key in missing], "failed_runs": failed_runs,
        "status": status, "maturity_verified": status == "PASS",
        "maturity_label": normalized["aggregation"]["maturity_pass_label"] if status == "PASS" else None,
        "external_action_authorized": False,
    }
    verdict["verdict_sha256"] = _sha256(verdict)
    return verdict
