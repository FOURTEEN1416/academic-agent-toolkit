"""Crash-consistent controller for the preregistered PS-GAP-014 V3 matrix.

Official mode has no injectable ProductRunner callback.  It invokes two
hash-bound source-owned subprocess adapters: the Codex app-server public host
entry and the independent evaluator.  Injectable adapters exist only behind a
separate test-only function whose output is permanently ineligible for the
canonical ``results-v3`` root.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
from collections import Counter
from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .maturity_acceptance_v3 import (
    EVALUATOR_PATH,
    EVALUATOR_SCHEMA_PATH,
    V3_ALWAYS_REQUIRED_EVIDENCE,
    V3_CONDITIONAL_REQUIRED_EVIDENCE,
    verify_independent_evaluation_receipt_v3,
)
from .maturity_preregistration_v3 import (
    V3_PROTOCOL_PATH,
    reopen_predecessor_v3,
    validate_preregistered_protocol_v3,
    verify_fixture_index_v3,
)
from .maturity_official_host_adapter import validate_app_server_transcript
from .maturity_official_profile_adapter import validate_profile_receipt


ROOT = Path(__file__).resolve().parents[3]
ACCEPTANCE_ROOT = ROOT / "03_联合开发" / "acceptance" / "ps-gap-014"
V3_FIXTURE_ROOT = ACCEPTANCE_ROOT / "frozen-fixtures-v3"
V3_INDEX_PATH = V3_FIXTURE_ROOT / "index.json"
CONTROLLER_PATH = Path(__file__).resolve()
HOST_ADAPTER_PATH = Path(__file__).with_name("maturity_official_host_adapter.py")
PROFILE_ADAPTER_PATH = Path(__file__).with_name("maturity_official_profile_adapter.py")
EVALUATOR_ADAPTER_PATH = Path(__file__).with_name(
    "maturity_official_evaluator_adapter.py"
)
PROFILE_SCHEMA_PATH = (
    ROOT
    / "03_联合开发"
    / "contracts"
    / "maturity-official-profile-receipt-v2.schema.json"
)
RECOVERY_INSTALL_SCHEMA_PATH = (
    ROOT
    / "03_联合开发"
    / "contracts"
    / "maturity-official-recovery-install-v2.schema.json"
)
RELEASE_VERIFIER_PATH = ROOT / "06_插件化" / "release" / "suite_release.py"
RESULT_SCHEMA_PATH = (
    ROOT / "03_联合开发" / "contracts" / "maturity-official-run-result-v3.schema.json"
)
INDEX_SCHEMA_PATH = (
    ROOT / "03_联合开发" / "contracts" / "maturity-official-run-index-v3.schema.json"
)
AGGREGATE_SCHEMA_PATH = (
    ROOT
    / "03_联合开发"
    / "contracts"
    / "maturity-official-run-aggregate-v3.schema.json"
)
CANONICAL_PLAN_PATH = (
    ROOT
    / "90_临时工作"
    / "TimeB闭环修复"
    / "PS-GAP-014_OFFICIAL_RUN_PLAN_V3.md"
)
CANONICAL_PROTOCOL_PATH = V3_PROTOCOL_PATH
CANONICAL_FIXTURE_ROOT = V3_FIXTURE_ROOT
CANONICAL_RESULT_ROOT = (
    ROOT / "03_联合开发" / "acceptance" / "ps-gap-014" / "results-v3"
)
EVALUATOR_IDENTITY = "paperspine5-independent-maturity-evaluator-v3"
PHASES = (
    "prepared",
    "host_started",
    "product_committed",
    "evaluator_committed",
    "result_verified",
)
STRATA_FIELDS = {
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


class OfficialRunError(ValueError):
    """Raised when an official-run phase, subject or artifact fails closed."""


def canonical_sha256(value: Any, *, self_hash: str | None = None) -> str:
    subject = copy.deepcopy(value)
    if self_hash and isinstance(subject, dict):
        subject.pop(self_hash, None)
    encoded = (
        json.dumps(subject, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: str | Path, label: str) -> dict[str, Any]:
    target = Path(path).resolve()
    if not target.is_file():
        raise OfficialRunError(f"{label} is missing: {target}")
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OfficialRunError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise OfficialRunError(f"{label} must be an object")
    return value


def _read_self_hashed(path: str | Path, field: str, label: str) -> dict[str, Any]:
    value = _read_json(path, label)
    if value.get(field) != canonical_sha256(value, self_hash=field):
        raise OfficialRunError(f"{label} self-hash drift")
    return value


def _exact_fields(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise OfficialRunError(
            f"{label} fields drift: missing={sorted(expected - set(value))}, "
            f"unknown={sorted(set(value) - expected)}"
        )


def _parse_time(value: Any, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise OfficialRunError(f"{label} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise OfficialRunError(f"{label} must include a timezone")
    return parsed


def _schema_validate(value: dict[str, Any], path: Path, label: str) -> None:
    schema = _read_json(path, f"{label} schema")
    errors = sorted(
        Draft202012Validator(
            schema, format_checker=Draft202012Validator.FORMAT_CHECKER
        ).iter_errors(value),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        error = errors[0]
        location = ".".join(str(item) for item in error.absolute_path) or "root"
        raise OfficialRunError(
            f"{label} schema violation at {location}: {error.message}"
        )


def _ref(path: str | Path) -> dict[str, str]:
    target = Path(path).resolve()
    if not target.is_file():
        raise OfficialRunError(f"referenced file is missing: {target}")
    return {"path": str(target), "sha256": file_sha256(target)}


def _verify_ref(ref: Mapping[str, Any], label: str) -> Path:
    if set(ref) != {"path", "sha256"}:
        raise OfficialRunError(f"{label} reference fields drift")
    path = Path(str(ref["path"])).resolve()
    if not path.is_file() or file_sha256(path) != ref["sha256"]:
        raise OfficialRunError(f"{label} reference hash drift")
    return path


def _publish_new(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise OfficialRunError(f"immutable artifact collision: {path}")
    stage = path.with_name(f".{path.name}.stage")
    if stage.exists():
        raise OfficialRunError(f"artifact stage collision: {stage}")
    owned = False
    try:
        with stage.open("xb") as handle:
            owned = True
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            raise OfficialRunError(f"artifact appeared before publish: {path}")
        os.replace(stage, path)
    except Exception:
        if owned and stage.exists():
            stage.unlink()
        raise


def _publish_json(path: Path, value: dict[str, Any]) -> None:
    _publish_new(
        path,
        (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
            "utf-8"
        ),
    )


def _publish_or_verify_bytes(path: Path, data: bytes, label: str) -> None:
    if path.exists():
        if not path.is_file() or path.read_bytes() != data:
            raise OfficialRunError(f"existing {label} collision/tamper")
        return
    _publish_new(path, data)


def _publish_or_verify_json(path: Path, value: dict[str, Any], label: str) -> None:
    encoded = (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    _publish_or_verify_bytes(path, encoded, label)


def _replace_owned_json(
    path: Path, value: dict[str, Any], *, self_hash: str, expected_old: dict[str, Any]
) -> None:
    actual = _read_self_hashed(path, self_hash, f"owned {path.name}")
    if actual != expected_old:
        raise OfficialRunError(f"owned {path.name} changed before replacement")
    stage = path.with_name(f".{path.name}.replacement")
    if stage.exists():
        raise OfficialRunError(f"owned replacement collision: {stage}")
    encoded = (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    owned = False
    try:
        with stage.open("xb") as handle:
            owned = True
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        if _read_self_hashed(path, self_hash, f"owned {path.name}") != expected_old:
            raise OfficialRunError(f"owned {path.name} changed during replacement")
        os.replace(stage, path)
    except Exception:
        if owned and stage.exists():
            stage.unlink()
        raise


def source_hashes() -> dict[str, str]:
    return {
        "controller_sha256": file_sha256(CONTROLLER_PATH),
        "host_adapter_sha256": file_sha256(HOST_ADAPTER_PATH),
        "profile_adapter_sha256": file_sha256(PROFILE_ADAPTER_PATH),
        "evaluator_adapter_sha256": file_sha256(EVALUATOR_ADAPTER_PATH),
        "evaluator_code_sha256": file_sha256(EVALUATOR_PATH),
        "evaluator_schema_sha256": file_sha256(EVALUATOR_SCHEMA_PATH),
        "profile_schema_sha256": file_sha256(PROFILE_SCHEMA_PATH),
        "recovery_install_schema_sha256": file_sha256(
            RECOVERY_INSTALL_SCHEMA_PATH
        ),
        "result_schema_sha256": file_sha256(RESULT_SCHEMA_PATH),
        "index_schema_sha256": file_sha256(INDEX_SCHEMA_PATH),
        "aggregate_schema_sha256": file_sha256(AGGREGATE_SCHEMA_PATH),
    }


def expected_run_matrix(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    validate_preregistered_protocol_v3(protocol)
    semantics = reopen_predecessor_v3(verify_payloads=True)["protocol"]
    if len(semantics["samples"]) != 21 or semantics["consecutive_runs_per_entry"] != 2:
        raise OfficialRunError("official protocol is no longer a 21 x 2 matrix")
    matrix = []
    for attempt in (1, 2):
        for sample in semantics["samples"]:
            run_id = (
                f"psgap014-v3.{sample['sample_id']}.{sample['entry_mode']}.a{attempt:02d}"
            )
            matrix.append(
                {
                    "run_id": run_id,
                    "sample_id": sample["sample_id"],
                    "entry_mode": sample["entry_mode"],
                    "attempt": attempt,
                    **{
                        field: sample[field]
                        for field in STRATA_FIELDS.values()
                    },
                }
            )
    keys = [
        (item["sample_id"], item["entry_mode"], item["attempt"]) for item in matrix
    ]
    if len(matrix) != 42 or len(set(keys)) != 42 or len({item["run_id"] for item in matrix}) != 42:
        raise OfficialRunError("official matrix contains missing/duplicate run identities")
    return matrix


def validate_fixture_authority(
    protocol: dict[str, Any], fixture_root: str | Path
) -> dict[str, Any]:
    try:
        normalized = validate_preregistered_protocol_v3(protocol)
        root = Path(fixture_root).resolve()
        if root != CANONICAL_FIXTURE_ROOT.resolve():
            raise OfficialRunError("official V3 fixture root is not canonical")
        return verify_fixture_index_v3(
            protocol=normalized,
            index_path=V3_INDEX_PATH,
            expected_root=root,
        )
    except Exception as exc:
        raise OfficialRunError(f"official fixture authority is invalid: {exc}") from exc


def _bound_json(ref: Mapping[str, Any], label: str) -> dict[str, Any]:
    return _read_json(_verify_ref(ref, label), label)


def validate_candidate_lock(
    path: str | Path, *, approval_token: str, plan_path: str | Path = CANONICAL_PLAN_PATH
) -> dict[str, Any]:
    lock = _read_self_hashed(path, "lock_sha256", "official candidate lock")
    required = {
        "contract", "contract_version", "status", "operation_id", "plan_file_sha256",
        "source_closed_at", "built_at", "archive", "build_id", "supersedes_build_id",
        "content_index_id", "manifest_sha256", "python_executable", "codex_executable",
        "codex_version", "profile_adapter", "host_adapter", "evaluator_adapter",
        "release_verifier", "source_hashes",
        "plugin_install_receipt", "skill_install_receipt", "installed_pointer_receipt",
        "discovery_receipt", "restart_receipt", "task_start_not_before",
        "approval_token_sha256", "external_action_authorized", "lock_sha256",
    }
    _exact_fields(lock, required, "official candidate lock")
    plan = Path(plan_path).resolve()
    if (
        lock["contract"] != "paperspine5.maturity-official-candidate-lock-v3"
        or lock["contract_version"] != "3.0"
        or lock["status"] != "approved_for_official_run"
        or lock["external_action_authorized"] is not False
        or lock["plan_file_sha256"] != file_sha256(plan)
        or lock["source_hashes"] != source_hashes()
        or hashlib.sha256(approval_token.encode("utf-8")).hexdigest()
        != lock["approval_token_sha256"]
    ):
        raise OfficialRunError("official candidate lock authority/source/approval drift")
    if lock["build_id"] == lock["supersedes_build_id"]:
        raise OfficialRunError("official candidate cannot reuse the installed prestate build")
    if _parse_time(lock["built_at"], "candidate built_at") <= _parse_time(
        lock["source_closed_at"], "candidate source_closed_at"
    ):
        raise OfficialRunError("candidate was not built after controller closure")
    _verify_ref(lock["archive"], "candidate archive")
    _verify_ref(lock["python_executable"], "candidate Python executable")
    _verify_ref(lock["codex_executable"], "candidate Codex executable")
    if (
        lock["profile_adapter"] != _ref(PROFILE_ADAPTER_PATH)
        or lock["host_adapter"] != _ref(HOST_ADAPTER_PATH)
        or lock["evaluator_adapter"] != _ref(EVALUATOR_ADAPTER_PATH)
        or lock["release_verifier"] != _ref(RELEASE_VERIFIER_PATH)
    ):
        raise OfficialRunError("candidate adapters are not the exact source-owned adapters")
    typed = {
        name: _bound_json(lock[name], name)
        for name in (
            "plugin_install_receipt",
            "skill_install_receipt",
            "installed_pointer_receipt",
            "discovery_receipt",
            "restart_receipt",
        )
    }
    for name in ("plugin_install_receipt", "skill_install_receipt"):
        receipt = typed[name]
        if (
            receipt.get("status") != "committed"
            or receipt.get("requested_target_applied") is not True
            or receipt.get("build_id") != lock["build_id"]
            or receipt.get("content_index_id") != lock["content_index_id"]
            or receipt.get("manifest_sha256") != lock["manifest_sha256"]
        ):
            raise OfficialRunError(f"candidate {name} is not an exact committed transaction")
    pointer = typed["installed_pointer_receipt"]
    if any(
        pointer.get(key) != lock[key]
        for key in ("build_id", "content_index_id", "manifest_sha256")
    ):
        raise OfficialRunError("candidate installed pointer identity drift")
    discovery = typed["discovery_receipt"]
    if (
        discovery.get("paper_spine") != 1
        or discovery.get("paperFig") != 0
        or discovery.get("workspace") != 0
        or discovery.get("build_id") != lock["build_id"]
    ):
        raise OfficialRunError("candidate discovery is not exact 1/0/0")
    restart = typed["restart_receipt"]
    if restart.get("build_id") != lock["build_id"] or _parse_time(
        lock["task_start_not_before"], "task_start_not_before"
    ) < _parse_time(restart.get("restarted_at"), "candidate restarted_at"):
        raise OfficialRunError("candidate host restart chronology drift")
    return copy.deepcopy(lock)


def _fixture_item(index: Mapping[str, Any], sample_id: str) -> dict[str, Any]:
    matches = [item for item in index["fixtures"] if item["sample_id"] == sample_id]
    if len(matches) != 1:
        raise OfficialRunError("fixture index does not bind one exact registered sample")
    value = copy.deepcopy(matches[0])
    value["first_run_not_before"] = index["first_run_not_before"]
    return value


def _entry_prompt(spec: Mapping[str, Any], fixture_root: Path) -> str:
    material = str(fixture_root.resolve())
    if spec["entry_mode"] == "natural_language":
        if spec["language"] == "zh":
            return f"请使用 {material} 中的材料制作完整本地论文、PDF、DOCX和可审计交付包。"
        return f"Use the materials in {material} to make the complete local paper, PDF, DOCX, and auditable delivery package."
    if spec["language"] == "zh":
        return f"$paper-spine 使用 {material} 中的材料制作完整本地论文、PDF、DOCX和可审计交付包。"
    return f"$paper-spine Use the materials in {material} to make the complete local paper, PDF, DOCX, and auditable delivery package."


def _build_profile_request(
    spec: Mapping[str, Any],
    *,
    run_root: Path,
    lock: Mapping[str, Any],
    execution_class: str,
) -> Path:
    entry = run_root / "entry"
    entry.mkdir(parents=True, exist_ok=True)
    request = {
        "contract": "paperspine5.maturity-isolated-profile-request-v2",
        "contract_version": "2.0",
        "run_id": spec["run_id"],
        "operation_id": f"{spec['run_id']}.candidate-profile",
        "run_root": str(run_root.resolve()),
        "profile_root": str((run_root / "profile").resolve()),
        "user_home_root": str((run_root / "user-home").resolve()),
        "archive_path": lock["archive"]["path"],
        "archive_sha256": lock["archive"]["sha256"],
        "build_id": lock["build_id"],
        "content_index_id": lock["content_index_id"],
        "manifest_sha256": lock["manifest_sha256"],
        "codex_executable": lock["codex_executable"]["path"],
        "codex_executable_sha256": lock["codex_executable"]["sha256"],
        "release_verifier_path": lock["release_verifier"]["path"],
        "release_verifier_sha256": lock["release_verifier"]["sha256"],
        "fresh_install_registered": spec["recovery_mode"] == "fresh_install",
        "execution_class": execution_class,
        "external_action_authorized": False,
    }
    request["request_sha256"] = canonical_sha256(request)
    path = entry / "profile-request.json"
    if path.exists():
        if _read_self_hashed(path, "request_sha256", "profile request") != request:
            raise OfficialRunError("isolated profile request collision")
    else:
        _publish_json(path, request)
    return path


def _validate_profile_chain(
    request_path: Path,
    receipt_path: Path,
    *,
    spec: Mapping[str, Any],
    lock: Mapping[str, Any],
    execution_class: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    request = _read_self_hashed(
        request_path, "request_sha256", "isolated profile request"
    )
    if (
        request.get("run_id") != spec["run_id"]
        or request.get("build_id") != lock["build_id"]
        or request.get("content_index_id") != lock["content_index_id"]
        or request.get("manifest_sha256") != lock["manifest_sha256"]
        or request.get("archive_sha256") != lock["archive"]["sha256"]
        or request.get("release_verifier_sha256")
        != lock["release_verifier"]["sha256"]
        or request.get("codex_executable_sha256")
        != lock["codex_executable"]["sha256"]
        or bool(request.get("fresh_install_registered"))
        != (spec["recovery_mode"] == "fresh_install")
        or request.get("execution_class") != execution_class
        or request.get("external_action_authorized") is not False
    ):
        raise OfficialRunError("isolated profile request subject/candidate drift")
    try:
        receipt = validate_profile_receipt(
            receipt_path,
            request,
            request_path=request_path,
            expected_test_only=execution_class == "test_only",
        )
    except Exception as exc:
        raise OfficialRunError(f"isolated profile placement is invalid: {exc}") from exc
    if spec["recovery_mode"] == "fresh_install" and not all(
        receipt["prestate"][key]
        for key in ("profile_absent", "plugin_absent", "skill_absent")
    ):
        raise OfficialRunError("fresh-install run did not begin from an absent profile")
    return request, receipt


def _build_entry_request(
    spec: Mapping[str, Any],
    *,
    run_root: Path,
    fixture_path: Path,
    lock: Mapping[str, Any],
    profile_request_path: Path,
    profile_receipt_path: Path,
    profile_receipt: Mapping[str, Any],
    execution_class: str,
) -> Path:
    entry = run_root / "entry"
    entry.mkdir(parents=True, exist_ok=True)
    prompt_path = entry / "request.txt"
    prompt_bytes = _entry_prompt(spec, fixture_path).encode("utf-8")
    if prompt_path.exists():
        if prompt_path.read_bytes() != prompt_bytes:
            raise OfficialRunError("public-entry prompt collision")
    else:
        _publish_new(prompt_path, prompt_bytes)
    profile = run_root / "profile"
    skill_root = profile / "skills" / "paper-spine"
    request = {
        "contract": "paperspine5.maturity-app-server-entry-request-v2",
        "contract_version": "2.0",
        "run_id": spec["run_id"],
        "sample_id": spec["sample_id"],
        "entry_mode": spec["entry_mode"],
        "attempt": spec["attempt"],
        "cwd": str(fixture_path.resolve()),
        "runtime_workspace_roots": [str(fixture_path.resolve()), str((run_root / "output").resolve())],
        "profile_root": str(profile.resolve()),
        "user_data_root": str((run_root / "user-data").resolve()),
        "user_home_root": profile_receipt["user_home_root"],
        "prompt_path": str(prompt_path.resolve()),
        "prompt_sha256": file_sha256(prompt_path),
        "product_journey_path": str((run_root / "task" / "product-journey-receipt.json").resolve()),
        "expected_skill_root": str(skill_root.resolve()),
        "expected_build_id": lock["build_id"],
        "expected_content_index_id": lock["content_index_id"],
        "profile_request": _ref(profile_request_path),
        "profile_receipt": _ref(profile_receipt_path),
        "profile_committed_at": profile_receipt["committed_at"],
        "codex_executable": lock["codex_executable"]["path"],
        "codex_executable_sha256": lock["codex_executable"]["sha256"],
        "execution_class": execution_class,
        "external_action_authorized": False,
    }
    request["request_sha256"] = canonical_sha256(request)
    path = entry / "request.json"
    if path.exists():
        if _read_self_hashed(path, "request_sha256", "public-entry request") != request:
            raise OfficialRunError("public-entry request collision")
    else:
        _publish_json(path, request)
    return path


def _validate_entry_request(
    path: Path, spec: Mapping[str, Any], lock: Mapping[str, Any], execution_class: str
) -> dict[str, Any]:
    request = _read_self_hashed(path, "request_sha256", "public-entry request")
    if (
        request.get("run_id") != spec["run_id"]
        or request.get("sample_id") != spec["sample_id"]
        or request.get("entry_mode") != spec["entry_mode"]
        or request.get("attempt") != spec["attempt"]
        or request.get("expected_build_id") != lock["build_id"]
        or request.get("expected_content_index_id") != lock["content_index_id"]
        or request.get("codex_executable_sha256") != lock["codex_executable"]["sha256"]
        or request.get("execution_class") != execution_class
        or request.get("external_action_authorized") is not False
    ):
        raise OfficialRunError("public-entry request subject/candidate binding drift")
    prompt = Path(request["prompt_path"]).resolve()
    if not prompt.is_file() or file_sha256(prompt) != request["prompt_sha256"]:
        raise OfficialRunError("public-entry prompt hash drift")
    text = prompt.read_text(encoding="utf-8")
    if spec["entry_mode"] == "natural_language":
        if "paper-spine" in text.lower():
            raise OfficialRunError("natural-language entry names the Skill")
    elif not text.startswith("$paper-spine "):
        raise OfficialRunError("explicit entry does not start with $paper-spine")
    profile_request_path = _verify_ref(request["profile_request"], "profile request")
    profile_receipt_path = _verify_ref(request["profile_receipt"], "profile receipt")
    _, profile_receipt = _validate_profile_chain(
        profile_request_path,
        profile_receipt_path,
        spec=spec,
        lock=lock,
        execution_class=execution_class,
    )
    if (
        request.get("profile_root") != profile_receipt["profile_root"]
        or request.get("user_home_root") != profile_receipt["user_home_root"]
        or request.get("profile_committed_at") != profile_receipt["committed_at"]
        or Path(request["expected_skill_root"]).resolve()
        != Path(profile_receipt["skill"]["root"]).resolve()
    ):
        raise OfficialRunError("public entry is not bound to the installed isolated profile")
    return request


def _subject(value: Mapping[str, Any]) -> dict[str, str]:
    direct = value.get("subject")
    if isinstance(direct, Mapping) and set(direct) == {
        "task_id", "revision_id", "build_id", "material_snapshot_sha256"
    }:
        return {key: str(direct[key]) for key in direct}
    task_id = value.get("task_id")
    revision = value.get("revision_id", value.get("revision"))
    build = value.get("build_id", value.get("product_build_id"))
    material = value.get("material_snapshot_sha256")
    inventory = value.get("material_inventory")
    if material is None and isinstance(inventory, Mapping):
        material = inventory.get("snapshot_sha256")
    state = value.get("state")
    runner = state.get("runner") if isinstance(state, Mapping) else None
    if isinstance(runner, Mapping):
        build = build or runner.get("product_build_id", runner.get("build_id"))
        nested_inventory = runner.get("material_inventory")
        if material is None and isinstance(nested_inventory, Mapping):
            material = nested_inventory.get("snapshot_sha256")
    if task_id and revision is not None and build and material:
        return {
            "task_id": str(task_id),
            "revision_id": str(revision),
            "build_id": str(build),
            "material_snapshot_sha256": str(material),
        }
    for key in ("snapshot", "runner", "task_record", "state", "result"):
        nested = value.get(key)
        if isinstance(nested, Mapping):
            try:
                return _subject(nested)
            except OfficialRunError:
                pass
    raise OfficialRunError("surface lacks a typed task/revision/build/material subject")


def _stage(value: Mapping[str, Any]) -> str | None:
    for key in ("stage", "next_stage"):
        if isinstance(value.get(key), str):
            return str(value[key])
    for key in ("snapshot", "runner", "task_record", "state", "result"):
        nested = value.get(key)
        if isinstance(nested, Mapping):
            found = _stage(nested)
            if found:
                return found
    return None


def _required_evidence(protocol: Mapping[str, Any], sample_id: str) -> set[str]:
    if protocol.get("protocol_sha256") != _read_json(
        CANONICAL_PROTOCOL_PATH, "canonical V3 protocol"
    ).get("protocol_sha256"):
        raise OfficialRunError("V3 protocol subject drift in evidence routing")
    semantics = reopen_predecessor_v3(verify_payloads=False)["protocol"]
    sample = next(
        item for item in semantics["samples"] if item["sample_id"] == sample_id
    )
    required = set(V3_ALWAYS_REQUIRED_EVIDENCE)
    required.update(V3_CONDITIONAL_REQUIRED_EVIDENCE.get(sample["figure_mode"], ()))
    return required


def _validate_host_receipt(
    path: Path,
    *,
    request_path: Path,
    request: Mapping[str, Any],
    lock: Mapping[str, Any],
    execution_class: str,
) -> dict[str, Any]:
    receipt = _read_self_hashed(path, "receipt_sha256", "public host receipt")
    if (
        receipt.get("contract") != "paperspine5.public-host-entry-receipt-v2"
        or receipt.get("run_id") != request["run_id"]
        or receipt.get("adapter_path") != str(HOST_ADAPTER_PATH.resolve())
        or receipt.get("adapter_sha256") != lock["host_adapter"]["sha256"]
        or receipt.get("codex_executable_sha256") != lock["codex_executable"]["sha256"]
        or receipt.get("argv")
        != [lock["codex_executable"]["path"], "app-server", "--stdio"]
        or receipt.get("profile_root") != request["profile_root"]
        or receipt.get("request_path") != str(request_path.resolve())
        or receipt.get("request_file_sha256") != file_sha256(request_path)
        or _parse_time(receipt.get("started_at"), "host started_at")
        < _parse_time(request["profile_committed_at"], "profile committed_at")
        or _parse_time(receipt.get("completed_at"), "host completed_at")
        < _parse_time(receipt.get("started_at"), "host started_at")
        or receipt.get("status") != "completed"
        or receipt.get("exit_code") != 0
        or receipt.get("external_action_authorized") is not False
        or bool(receipt.get("test_only")) != (execution_class == "test_only")
    ):
        raise OfficialRunError("public host receipt is not the canonical app-server execution")
    selected = receipt.get("selected_skill") or {}
    if (
        selected.get("name") != "paper-spine"
        or Path(str(selected.get("path", ""))).resolve()
        != Path(request["expected_skill_root"]).resolve() / "SKILL.md"
    ):
        raise OfficialRunError("public host receipt selected a competing/noncandidate Skill")
    transcript_path = _verify_ref(
        {"path": receipt["transcript_path"], "sha256": receipt["transcript_file_sha256"]},
        "public host transcript",
    )
    transcript_payload = _read_json(transcript_path, "public host transcript")
    if set(transcript_payload) != {"events"} or not isinstance(
        transcript_payload["events"], list
    ):
        raise OfficialRunError("public host transcript envelope is invalid")
    try:
        transcript = validate_app_server_transcript(
            transcript_payload["events"], expected_request=dict(request)
        )
    except Exception as exc:
        raise OfficialRunError(f"public host transcript protocol drift: {exc}") from exc
    if (
        transcript["thread_id"] != receipt["thread_id"]
        or transcript["turn_id"] != receipt["turn_id"]
        or transcript["selected_skill"] != receipt["selected_skill"]
    ):
        raise OfficialRunError("public host receipt/transcript identity drift")
    process_tree_path = _verify_ref(
        {
            "path": receipt["process_tree_path"],
            "sha256": receipt["process_tree_file_sha256"],
        },
        "public host process tree",
    )
    process_tree = _read_json(process_tree_path, "public host process tree")
    if set(process_tree) != {
        "root_pid",
        "owned_pre_close",
        "owned_post_close",
        "post_snapshot_sha256",
    }:
        raise OfficialRunError("public host process-tree envelope drift")
    owned_pre = process_tree["owned_pre_close"]
    owned_post = process_tree["owned_post_close"]
    if (
        process_tree["root_pid"] != receipt["pid"]
        or not isinstance(owned_pre, list)
        or not any(item.get("pid") == receipt["pid"] for item in owned_pre)
        or owned_post != []
        or receipt.get("owned_process_count_pre_close") != len(owned_pre)
        or receipt.get("owned_process_count_post_close") != 0
    ):
        raise OfficialRunError("owned app-server/PaperSpine process-tree cleanup drift")
    _verify_ref(
        {
            "path": receipt["stderr_path"],
            "sha256": receipt["stderr_file_sha256"],
        },
        "public host stderr",
    )
    env_hashes = receipt.get("environment_value_sha256") or {}
    if (
        receipt.get("environment_keys") != sorted(env_hashes)
        or env_hashes.get("CODEX_HOME")
        != hashlib.sha256(request["profile_root"].encode("utf-8")).hexdigest()
        or env_hashes.get("PAPERSPINE5_USER_DATA_ROOT")
        != hashlib.sha256(request["user_data_root"].encode("utf-8")).hexdigest()
        or env_hashes.get("HOME")
        != hashlib.sha256(request["user_home_root"].encode("utf-8")).hexdigest()
        or env_hashes.get("USERPROFILE")
        != hashlib.sha256(request["user_home_root"].encode("utf-8")).hexdigest()
    ):
        raise OfficialRunError("public host environment/profile binding drift")
    return receipt


def _validate_recovery_install_evidence(
    evidence_ref: Mapping[str, Any],
    *,
    spec: Mapping[str, Any],
    subject: Mapping[str, Any],
    request: Mapping[str, Any],
    host_receipt_path: Path,
    host: Mapping[str, Any],
    journey_started_at: str,
) -> dict[str, Any]:
    path = _verify_ref(
        {"path": evidence_ref["path"], "sha256": evidence_ref["sha256"]},
        "recovery/install evidence",
    )
    receipt = _read_self_hashed(
        path, "receipt_sha256", "recovery/install evidence"
    )
    _schema_validate(
        receipt, RECOVERY_INSTALL_SCHEMA_PATH, "recovery/install evidence"
    )
    profile_receipt_path = _verify_ref(
        request["profile_receipt"], "bound profile receipt"
    )
    if (
        receipt["run_id"] != spec["run_id"]
        or receipt["mode"] != spec["recovery_mode"]
        or receipt["profile_root"] != request["profile_root"]
        or receipt["build_id"] != request["expected_build_id"]
        or receipt["content_index_id"] != request["expected_content_index_id"]
        or receipt["profile_receipt"] != _ref(profile_receipt_path)
        or receipt["host_receipt"] != _ref(host_receipt_path)
        or receipt["subject"] != subject
        or receipt["install_committed_at"] != request["profile_committed_at"]
        or receipt["host_started_at"] != host["started_at"]
        or receipt["task_started_at"] != journey_started_at
        or receipt["external_action_authorized"] is not False
    ):
        raise OfficialRunError("recovery/install evidence subject/profile chronology drift")
    if not (
        _parse_time(receipt["install_committed_at"], "install committed_at")
        <= _parse_time(receipt["host_started_at"], "host started_at")
        <= _parse_time(receipt["task_started_at"], "task started_at")
    ):
        raise OfficialRunError("install -> host -> task chronology is invalid")
    return receipt


def validate_product_journey(
    protocol: dict[str, Any],
    fixture_item: Mapping[str, Any],
    spec: Mapping[str, Any],
    lock: Mapping[str, Any],
    request_path: Path,
    host_receipt_path: Path,
    journey_path: Path,
    *,
    execution_class: str,
) -> dict[str, Any]:
    request = _validate_entry_request(request_path, spec, lock, execution_class)
    host = _validate_host_receipt(
        host_receipt_path,
        request_path=request_path,
        request=request,
        lock=lock,
        execution_class=execution_class,
    )
    journey = _read_self_hashed(journey_path, "receipt_sha256", "product journey")
    required_fields = {
        "contract", "contract_version", "run_id", "sample_id", "entry_mode", "attempt",
        "host_receipt", "subject", "surfaces", "evidence", "producer_identity",
        "started_at", "completed_at", "status", "external_action_authorized",
        "receipt_sha256",
    }
    _exact_fields(journey, required_fields, "product journey")
    subject = journey["subject"]
    if (
        journey["contract"] != "paperspine5.production-journey-receipt-v3"
        or journey["run_id"] != spec["run_id"]
        or journey["sample_id"] != spec["sample_id"]
        or journey["entry_mode"] != spec["entry_mode"]
        or journey["attempt"] != spec["attempt"]
        or journey["host_receipt"] != _ref(host_receipt_path)
        or subject.get("build_id") != lock["build_id"]
        or subject.get("material_snapshot_sha256") != fixture_item["material_snapshot_sha256"]
        or journey["producer_identity"] == EVALUATOR_IDENTITY
        or journey["status"] != "target_package_ready"
        or journey["external_action_authorized"] is not False
        or _parse_time(journey["started_at"], "journey started_at")
        < _parse_time(fixture_item["first_run_not_before"], "first_run_not_before")
        or _parse_time(journey["completed_at"], "journey completed_at")
        < _parse_time(journey["started_at"], "journey started_at")
    ):
        raise OfficialRunError("product journey subject/status/time binding drift")
    if not host.get("thread_id") or not host.get("turn_id"):
        raise OfficialRunError("product journey lacks real host thread/turn identity")
    surfaces = journey["surfaces"]
    if set(surfaces) != {"task_record", "runner", "web", "flat_json", "flat_markdown"}:
        raise OfficialRunError("product journey surfaces are incomplete/unknown")
    for name in ("task_record", "runner", "web", "flat_json"):
        surface = _read_json(_verify_ref(surfaces[name], f"{name} surface"), f"{name} surface")
        if _subject(surface) != subject or _stage(surface) != "target_package_ready":
            raise OfficialRunError(f"{name} surface task/revision/build/material/stage drift")
    markdown_path = _verify_ref(surfaces["flat_markdown"], "flat Markdown")
    markdown = markdown_path.read_text(encoding="utf-8")
    if any(str(value) not in markdown for value in subject.values()) or "target_package_ready" not in markdown:
        raise OfficialRunError("flat Markdown subject/readiness drift")
    required = _required_evidence(protocol, spec["sample_id"])
    if set(journey["evidence"]) != required:
        raise OfficialRunError("product journey evidence set is incomplete/unknown")
    for name, ref in journey["evidence"].items():
        _verify_ref({"path": ref["path"], "sha256": ref["sha256"]}, f"evidence {name}")
        if ref.get("subject") != subject:
            raise OfficialRunError(f"product evidence subject drift: {name}")
    _validate_recovery_install_evidence(
        journey["evidence"]["recovery_or_install_receipt"],
        spec=spec,
        subject=subject,
        request=request,
        host_receipt_path=host_receipt_path,
        host=host,
        journey_started_at=journey["started_at"],
    )
    return journey


def _verify_evaluator(
    protocol: dict[str, Any],
    fixture_receipt: dict[str, Any],
    journey: Mapping[str, Any],
    evaluator_path: Path,
    verifier: Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    receipt = _read_json(evaluator_path, "independent evaluator receipt")
    verified = verifier(protocol, fixture_receipt, receipt)
    if (
        verified.get("run_id") != journey["run_id"]
        or verified.get("sample_id") != journey["sample_id"]
        or verified.get("entry_mode") != journey["entry_mode"]
        or verified.get("attempt") != journey["attempt"]
        or verified.get("subject") != journey["subject"]
        or verified.get("producer_identity") != journey["producer_identity"]
        or verified.get("evaluator_identity") != EVALUATOR_IDENTITY
        or verified.get("producer_identity") == verified.get("evaluator_identity")
        or verified.get("evidence") != journey["evidence"]
    ):
        raise OfficialRunError("independent evaluator does not bind the product journey")
    return verified


def _build_result(
    *,
    execution_class: str,
    protocol: dict[str, Any],
    fixture_index: Mapping[str, Any],
    fixture_item: Mapping[str, Any],
    spec: Mapping[str, Any],
    lock_path: Path,
    lock: Mapping[str, Any],
    plan_path: Path,
    request_path: Path,
    host_receipt_path: Path,
    journey_path: Path,
    evaluator_path: Path,
    verifier: Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    journey = validate_product_journey(
        protocol,
        fixture_item,
        spec,
        lock,
        request_path,
        host_receipt_path,
        journey_path,
        execution_class=execution_class,
    )
    fixture_receipt_path = CANONICAL_FIXTURE_ROOT / fixture_item["receipt_relative_path"]
    fixture_receipt = _read_json(fixture_receipt_path, "fixture receipt")
    evaluator = _verify_evaluator(
        protocol, fixture_receipt, journey, evaluator_path, verifier
    )
    result = {
        "contract": "paperspine5.maturity-official-run-result-v3",
        "contract_version": "3.0",
        "execution_class": execution_class,
        "run_id": spec["run_id"],
        "sample_id": spec["sample_id"],
        "entry_mode": spec["entry_mode"],
        "attempt": spec["attempt"],
        "protocol_file_sha256": file_sha256(CANONICAL_PROTOCOL_PATH),
        "protocol_sha256": protocol["protocol_sha256"],
        "fixture_index_file_sha256": file_sha256(CANONICAL_FIXTURE_ROOT / "index.json"),
        "fixture_index_sha256": fixture_index["index_sha256"],
        "fixture_receipt_file_sha256": fixture_item["receipt_file_sha256"],
        "fixture_receipt_sha256": fixture_item["receipt_sha256"],
        "plan_file_sha256": file_sha256(plan_path),
        "candidate_lock_file_sha256": file_sha256(lock_path),
        "candidate_lock_sha256": lock["lock_sha256"],
        **source_hashes(),
        "profile_receipt": copy.deepcopy(
            _read_self_hashed(
                request_path, "request_sha256", "public-entry request"
            )["profile_receipt"]
        ),
        "entry_request": _ref(request_path),
        "host_receipt": _ref(host_receipt_path),
        "product_journey": _ref(journey_path),
        "subject": copy.deepcopy(journey["subject"]),
        "surfaces": copy.deepcopy(journey["surfaces"]),
        "evidence": copy.deepcopy(journey["evidence"]),
        "producer_identity": journey["producer_identity"],
        "evaluator_identity": evaluator["evaluator_identity"],
        "evaluator_receipt": _ref(evaluator_path),
        "hard_checks": copy.deepcopy(evaluator["hard_checks"]),
        "started_at": journey["started_at"],
        "completed_at": evaluator["evaluated_at"],
        "status": evaluator["status"],
        "external_action_authorized": False,
    }
    result["receipt_sha256"] = canonical_sha256(result)
    _schema_validate(result, RESULT_SCHEMA_PATH, "official run result")
    return result


def verify_official_run_result(
    path: str | Path,
    *,
    execution_class: str,
    protocol: dict[str, Any],
    fixture_index: Mapping[str, Any],
    spec: Mapping[str, Any],
    lock_path: Path,
    lock: Mapping[str, Any],
    plan_path: Path,
    verifier: Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], dict[str, Any]] = verify_independent_evaluation_receipt_v3,
) -> dict[str, Any]:
    persisted = _read_self_hashed(path, "receipt_sha256", "official run result")
    _schema_validate(persisted, RESULT_SCHEMA_PATH, "official run result")
    fixture_item = _fixture_item(fixture_index, spec["sample_id"])
    rebuilt = _build_result(
        execution_class=execution_class,
        protocol=protocol,
        fixture_index=fixture_index,
        fixture_item=fixture_item,
        spec=spec,
        lock_path=lock_path,
        lock=lock,
        plan_path=plan_path,
        request_path=Path(persisted["entry_request"]["path"]),
        host_receipt_path=Path(persisted["host_receipt"]["path"]),
        journey_path=Path(persisted["product_journey"]["path"]),
        evaluator_path=Path(persisted["evaluator_receipt"]["path"]),
        verifier=verifier,
    )
    if persisted != rebuilt:
        raise OfficialRunError("official result differs from reopened product/evaluator evidence")
    return persisted


def _owner(
    *, operation_id: str, execution_class: str, control_root: Path, output_root: Path,
    pins: Mapping[str, str]
) -> dict[str, Any]:
    value = {
        "contract": "paperspine5.maturity-official-run-owner-v3",
        "contract_version": "3.0",
        "operation_id": operation_id,
        "execution_class": execution_class,
        "control_root": str(control_root.resolve()),
        "output_root": str(output_root.resolve()),
        **dict(pins),
        "external_action_authorized": False,
    }
    value["owner_sha256"] = canonical_sha256(value)
    return value


def _new_journal(owner: Mapping[str, Any], matrix: list[dict[str, Any]]) -> dict[str, Any]:
    value = {
        "contract": "paperspine5.maturity-official-run-phase-journal-v3",
        "contract_version": "3.0",
        "operation_id": owner["operation_id"],
        "owner_sha256": owner["owner_sha256"],
        "matrix_run_ids": [item["run_id"] for item in matrix],
        "runs": {item["run_id"]: {"phase": None, "phase_receipt": None} for item in matrix},
        "state": "prepared",
        "external_action_authorized": False,
    }
    value["journal_sha256"] = canonical_sha256(value)
    return value


def _phase_receipt(
    spec: Mapping[str, Any], phase: str, artifact: Path, previous: str | None
) -> dict[str, Any]:
    value = {
        "contract": "paperspine5.maturity-official-run-phase-v3",
        "contract_version": "3.0",
        "run_id": spec["run_id"],
        "phase": phase,
        "previous_phase": previous,
        "artifact": _ref(artifact),
        "external_action_authorized": False,
    }
    value["receipt_sha256"] = canonical_sha256(value)
    return value


def _advance_phase(
    journal_path: Path,
    journal: dict[str, Any],
    spec: Mapping[str, Any],
    phase: str,
    artifact: Path,
    run_root: Path,
) -> dict[str, Any]:
    current = journal["runs"][spec["run_id"]]
    current_phase = current["phase"]
    phase_path = run_root / "phases" / f"{PHASES.index(phase) + 1:02d}-{phase}.json"
    if current_phase is not None and PHASES.index(current_phase) > PHASES.index(phase):
        receipt = _read_self_hashed(
            phase_path, "receipt_sha256", "historical phase receipt"
        )
        expected_previous = None if phase == "prepared" else PHASES[PHASES.index(phase) - 1]
        if receipt != _phase_receipt(spec, phase, artifact, expected_previous):
            raise OfficialRunError("historical phase receipt/artifact drift")
        return journal
    if current_phase == phase:
        receipt = _read_self_hashed(
            current["phase_receipt"]["path"], "receipt_sha256", "phase receipt"
        )
        if receipt["artifact"] != _ref(artifact):
            raise OfficialRunError("phase receipt artifact drift")
        return journal
    expected_previous = None if phase == "prepared" else PHASES[PHASES.index(phase) - 1]
    if current_phase != expected_previous:
        raise OfficialRunError(
            f"phase order drift for {spec['run_id']}: {current_phase} -> {phase}"
        )
    receipt = _phase_receipt(spec, phase, artifact, expected_previous)
    if phase_path.exists():
        if _read_self_hashed(phase_path, "receipt_sha256", "phase receipt") != receipt:
            raise OfficialRunError("existing phase receipt collision")
    else:
        _publish_json(phase_path, receipt)
    updated = copy.deepcopy(journal)
    updated["runs"][spec["run_id"]] = {
        "phase": phase,
        "phase_receipt": _ref(phase_path),
    }
    if all(item["phase"] == "result_verified" for item in updated["runs"].values()):
        updated["state"] = "results_verified"
    updated["journal_sha256"] = canonical_sha256(updated, self_hash="journal_sha256")
    _replace_owned_json(
        journal_path,
        updated,
        self_hash="journal_sha256",
        expected_old=journal,
    )
    return updated


def _run_subprocess(argv: list[str], *, cwd: Path, label: str) -> None:
    completed = subprocess.run(
        argv,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
        timeout=900,
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr[-4000:]
        raise OfficialRunError(f"{label} failed ({completed.returncode}): {stderr}")


def _invoke_host(
    lock: Mapping[str, Any], request_path: Path, host_receipt_path: Path, run_root: Path
) -> None:
    _run_subprocess(
        [
            lock["python_executable"]["path"],
            lock["host_adapter"]["path"],
            "--request", str(request_path),
            "--receipt", str(host_receipt_path),
        ],
        cwd=run_root,
        label="canonical public host adapter",
    )


def _invoke_profile(
    lock: Mapping[str, Any], request_path: Path, receipt_path: Path, run_root: Path
) -> None:
    _run_subprocess(
        [
            lock["python_executable"]["path"],
            lock["profile_adapter"]["path"],
            "--request",
            str(request_path),
            "--receipt",
            str(receipt_path),
        ],
        cwd=run_root,
        label="canonical isolated-profile adapter",
    )


def _invoke_evaluator(
    lock: Mapping[str, Any],
    fixture_receipt_path: Path,
    journey_path: Path,
    evaluator_path: Path,
    run_root: Path,
) -> None:
    _run_subprocess(
        [
            lock["python_executable"]["path"],
            lock["evaluator_adapter"]["path"],
            "--protocol", str(CANONICAL_PROTOCOL_PATH),
            "--fixture-receipt", str(fixture_receipt_path),
            "--journey", str(journey_path),
            "--result", str(evaluator_path),
        ],
        cwd=run_root,
        label="independent evaluator adapter",
    )


def _strata_counts(
    protocol: Mapping[str, Any], verified: list[dict[str, Any]]
) -> tuple[dict[str, dict[str, int]], bool]:
    if protocol.get("protocol_sha256") != _read_json(
        CANONICAL_PROTOCOL_PATH, "canonical V3 protocol"
    ).get("protocol_sha256"):
        raise OfficialRunError("V3 protocol subject drift in strata routing")
    semantics = reopen_predecessor_v3(verify_payloads=False)["protocol"]
    sample_map = {item["sample_id"]: item for item in semantics["samples"]}
    actual: dict[str, dict[str, int]] = {}
    complete = True
    for coverage_name, sample_field in STRATA_FIELDS.items():
        counts = Counter(sample_map[item["sample_id"]][sample_field] for item in verified)
        expected = Counter(
            sample[sample_field]
            for sample in semantics["samples"]
            for _attempt in (1, 2)
        )
        registered = semantics["coverage_requirements"][coverage_name]
        actual[coverage_name] = {value: counts[value] for value in registered}
        if counts != expected:
            complete = False
    entry_counts = Counter(item["entry_mode"] for item in verified)
    expected_entries = Counter(
        sample["entry_mode"]
        for sample in semantics["samples"]
        for _attempt in (1, 2)
    )
    actual["entry_modes"] = {
        value: entry_counts[value] for value in semantics["required_entry_modes"]
    }
    return actual, complete and entry_counts == expected_entries


def _build_index_and_aggregate(
    *,
    execution_class: str,
    operation_id: str,
    protocol: dict[str, Any],
    fixture_index: Mapping[str, Any],
    matrix: list[dict[str, Any]],
    control_root: Path,
    publish_stage: Path,
    lock_path: Path,
    lock: Mapping[str, Any],
    plan_path: Path,
    verifier: Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], dict[str, Any]],
    now: datetime,
    failure_injector: Callable[[str], None] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    verified: list[dict[str, Any]] = []
    runs = []
    for spec in matrix:
        source = control_root / "runs" / spec["run_id"] / "result.json"
        result = verify_official_run_result(
            source,
            execution_class=execution_class,
            protocol=protocol,
            fixture_index=fixture_index,
            spec=spec,
            lock_path=lock_path,
            lock=lock,
            plan_path=plan_path,
            verifier=verifier,
        )
        verified.append(result)
        destination = publish_stage / "runs" / f"{spec['run_id']}.json"
        _publish_or_verify_bytes(
            destination, source.read_bytes(), f"published run {spec['run_id']}"
        )
        if failure_injector:
            failure_injector(f"publish_run:{spec['run_id']}")
        runs.append(
            {
                "run_id": spec["run_id"],
                "sample_id": spec["sample_id"],
                "entry_mode": spec["entry_mode"],
                "attempt": spec["attempt"],
                "relative_path": destination.relative_to(publish_stage).as_posix(),
                "file_sha256": file_sha256(destination),
                "receipt_sha256": result["receipt_sha256"],
                "status": result["status"],
            }
        )
    index_path = publish_stage / "index.json"
    created_at = (
        _read_self_hashed(index_path, "index_sha256", "partial published index")[
            "created_at"
        ]
        if index_path.exists()
        else now.isoformat(timespec="milliseconds")
    )
    index = {
        "contract": "paperspine5.maturity-official-run-index-v3",
        "contract_version": "3.0",
        "execution_class": execution_class,
        "operation_id": operation_id,
        "plan_file_sha256": file_sha256(plan_path),
        "protocol_file_sha256": file_sha256(CANONICAL_PROTOCOL_PATH),
        "protocol_sha256": protocol["protocol_sha256"],
        "fixture_index_file_sha256": file_sha256(CANONICAL_FIXTURE_ROOT / "index.json"),
        "fixture_index_sha256": fixture_index["index_sha256"],
        "candidate_lock_file_sha256": file_sha256(lock_path),
        "candidate_lock_sha256": lock["lock_sha256"],
        **source_hashes(),
        "run_count": 42,
        "runs": runs,
        "created_at": created_at,
        "product_runs_executed": 42,
        "evaluator_results_created": 42,
        "external_action_authorized": False,
    }
    index["index_sha256"] = canonical_sha256(index)
    _schema_validate(index, INDEX_SCHEMA_PATH, "official result index")
    _publish_or_verify_json(index_path, index, "published index")
    if failure_injector:
        failure_injector("publish_index")
    strata, strata_complete = _strata_counts(protocol, verified)
    hard_fail = any(
        set(item["hard_checks"].values()) != {"PASS"} or item["status"] != "PASS"
        for item in verified
    )
    status = (
        "TEST_ONLY"
        if execution_class == "test_only"
        else "FAIL" if hard_fail else "PASS" if strata_complete else "INCOMPLETE"
    )
    aggregate = {
        "contract": "paperspine5.maturity-official-run-aggregate-v3",
        "contract_version": "3.0",
        "execution_class": execution_class,
        "operation_id": operation_id,
        "index_file_sha256": file_sha256(index_path),
        "index_sha256": index["index_sha256"],
        "protocol_sha256": protocol["protocol_sha256"],
        "candidate_lock_sha256": lock["lock_sha256"],
        "run_count": 42,
        "pass_count": sum(item["status"] == "PASS" for item in verified),
        "fail_count": sum(item["status"] != "PASS" for item in verified),
        "missing_run_ids": [],
        "duplicate_run_ids": [],
        "strata_counts": strata,
        "all_samples_complete": True,
        "all_strata_complete": strata_complete,
        "status": status,
        "maturity_label": reopen_predecessor_v3(verify_payloads=False)["protocol"]
        ["aggregation"]["maturity_pass_label"],
        "external_action_authorized": False,
    }
    aggregate["aggregate_sha256"] = canonical_sha256(aggregate)
    _schema_validate(aggregate, AGGREGATE_SCHEMA_PATH, "official aggregate")
    _publish_or_verify_json(
        publish_stage / "aggregate.json", aggregate, "published aggregate"
    )
    if failure_injector:
        failure_injector("publish_aggregate")
    return index, aggregate


def _verify_published(
    *,
    output_root: Path,
    execution_class: str,
    operation_id: str,
    protocol: dict[str, Any],
    fixture_index: Mapping[str, Any],
    matrix: list[dict[str, Any]],
    lock_path: Path,
    lock: Mapping[str, Any],
    plan_path: Path,
    expected_owner: Mapping[str, Any],
    verifier: Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    owner = _read_self_hashed(output_root / "owner.json", "owner_sha256", "published owner")
    pins = {
        "plan_file_sha256": file_sha256(plan_path),
        "protocol_file_sha256": file_sha256(CANONICAL_PROTOCOL_PATH),
        "protocol_sha256": protocol["protocol_sha256"],
        "fixture_index_file_sha256": file_sha256(
            CANONICAL_FIXTURE_ROOT / "index.json"
        ),
        "fixture_index_sha256": fixture_index["index_sha256"],
        "candidate_lock_file_sha256": file_sha256(lock_path),
        "candidate_lock_sha256": lock["lock_sha256"],
        **source_hashes(),
    }
    recomputed_owner = _owner(
        operation_id=operation_id,
        execution_class=execution_class,
        control_root=Path(expected_owner["control_root"]),
        output_root=Path(expected_owner["output_root"]),
        pins=pins,
    )
    if owner != expected_owner or owner != recomputed_owner:
        raise OfficialRunError("published owner authority/pin drift")
    index = _read_self_hashed(output_root / "index.json", "index_sha256", "published index")
    _schema_validate(index, INDEX_SCHEMA_PATH, "published index")
    if [item["run_id"] for item in index["runs"]] != [item["run_id"] for item in matrix]:
        raise OfficialRunError("published index matrix order/coverage drift")
    verified = []
    expected_runs = []
    for spec, indexed in zip(matrix, index["runs"], strict=True):
        path = output_root / indexed["relative_path"]
        if file_sha256(path) != indexed["file_sha256"]:
            raise OfficialRunError("published run file hash drift")
        result = verify_official_run_result(
                path,
                execution_class=execution_class,
                protocol=protocol,
                fixture_index=fixture_index,
                spec=spec,
                lock_path=lock_path,
                lock=lock,
                plan_path=plan_path,
                verifier=verifier,
            )
        verified.append(result)
        expected_runs.append(
            {
                "run_id": spec["run_id"],
                "sample_id": spec["sample_id"],
                "entry_mode": spec["entry_mode"],
                "attempt": spec["attempt"],
                "relative_path": path.relative_to(output_root).as_posix(),
                "file_sha256": file_sha256(path),
                "receipt_sha256": result["receipt_sha256"],
                "status": result["status"],
            }
        )
    expected_index = {
        "contract": "paperspine5.maturity-official-run-index-v3",
        "contract_version": "3.0",
        "execution_class": execution_class,
        "operation_id": operation_id,
        **pins,
        "run_count": 42,
        "runs": expected_runs,
        "created_at": index["created_at"],
        "product_runs_executed": 42,
        "evaluator_results_created": 42,
        "external_action_authorized": False,
    }
    expected_index["index_sha256"] = canonical_sha256(expected_index)
    if index != expected_index:
        raise OfficialRunError("published index is not the exact 42-run recomputation")
    aggregate = _read_self_hashed(
        output_root / "aggregate.json", "aggregate_sha256", "published aggregate"
    )
    _schema_validate(aggregate, AGGREGATE_SCHEMA_PATH, "published aggregate")
    strata, strata_complete = _strata_counts(protocol, verified)
    hard_fail = any(
        set(item["hard_checks"].values()) != {"PASS"}
        or item["status"] != "PASS"
        for item in verified
    )
    status = (
        "TEST_ONLY"
        if execution_class == "test_only"
        else "FAIL"
        if hard_fail
        else "PASS"
        if strata_complete
        else "INCOMPLETE"
    )
    expected_aggregate = {
        "contract": "paperspine5.maturity-official-run-aggregate-v3",
        "contract_version": "3.0",
        "execution_class": execution_class,
        "operation_id": operation_id,
        "index_file_sha256": file_sha256(output_root / "index.json"),
        "index_sha256": index["index_sha256"],
        "protocol_sha256": protocol["protocol_sha256"],
        "candidate_lock_sha256": lock["lock_sha256"],
        "run_count": 42,
        "pass_count": sum(item["status"] == "PASS" for item in verified),
        "fail_count": sum(item["status"] != "PASS" for item in verified),
        "missing_run_ids": [],
        "duplicate_run_ids": [],
        "strata_counts": strata,
        "all_samples_complete": len(verified) == len(matrix) == 42,
        "all_strata_complete": strata_complete,
        "status": status,
        "maturity_label": reopen_predecessor_v3(verify_payloads=False)["protocol"]
        ["aggregation"]["maturity_pass_label"],
        "external_action_authorized": False,
    }
    expected_aggregate["aggregate_sha256"] = canonical_sha256(expected_aggregate)
    if aggregate != expected_aggregate:
        raise OfficialRunError(
            "published aggregate is not the exact hard-check/strata recomputation"
        )
    return {
        "status": "already_committed",
        "output_root": str(output_root),
        "run_count": 42,
        "index_sha256": index["index_sha256"],
        "aggregate_sha256": aggregate["aggregate_sha256"],
        "aggregate_status": aggregate["status"],
        "external_action_authorized": False,
    }


def _run_matrix(
    *,
    execution_class: str,
    operation_id: str,
    approval_token: str,
    candidate_lock_path: str | Path,
    output_root: str | Path,
    profile_invoker: Callable[[dict[str, Any], Path, Path, Path], None],
    host_invoker: Callable[[dict[str, Any], Path, Path, Path], None],
    evaluator_invoker: Callable[[dict[str, Any], Path, Path, Path, Path], None],
    verifier: Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], dict[str, Any]],
    now: datetime | None,
    failure_injector: Callable[[str], None] | None,
) -> dict[str, Any]:
    if execution_class not in {"official", "test_only"}:
        raise OfficialRunError("execution class is invalid")
    output = Path(output_root).resolve()
    if execution_class == "test_only" and output == CANONICAL_RESULT_ROOT.resolve():
        raise OfficialRunError("test-only controller cannot target canonical results-v3")
    if execution_class == "official" and output != CANONICAL_RESULT_ROOT.resolve():
        raise OfficialRunError("official controller requires canonical results-v3")
    timestamp = now or datetime.now().astimezone()
    protocol = validate_preregistered_protocol_v3(
        _read_json(CANONICAL_PROTOCOL_PATH, "frozen protocol")
    )
    fixture_index = validate_fixture_authority(protocol, CANONICAL_FIXTURE_ROOT)
    if timestamp < _parse_time(fixture_index["first_run_not_before"], "first_run_not_before"):
        raise OfficialRunError("matrix predates first_run_not_before")
    plan = CANONICAL_PLAN_PATH.resolve()
    lock_path = Path(candidate_lock_path).resolve()
    lock = validate_candidate_lock(lock_path, approval_token=approval_token, plan_path=plan)
    matrix = expected_run_matrix(protocol)
    control = output.with_name(f".{output.name}.{operation_id}.control")
    publish_stage = output.with_name(f".{output.name}.{operation_id}.publishing")
    pins = {
        "plan_file_sha256": file_sha256(plan),
        "protocol_file_sha256": file_sha256(CANONICAL_PROTOCOL_PATH),
        "protocol_sha256": protocol["protocol_sha256"],
        "fixture_index_file_sha256": file_sha256(CANONICAL_FIXTURE_ROOT / "index.json"),
        "fixture_index_sha256": fixture_index["index_sha256"],
        "candidate_lock_file_sha256": file_sha256(lock_path),
        "candidate_lock_sha256": lock["lock_sha256"],
        **source_hashes(),
    }
    owner = _owner(
        operation_id=operation_id,
        execution_class=execution_class,
        control_root=control,
        output_root=output,
        pins=pins,
    )
    if output.exists():
        return _verify_published(
            output_root=output,
            execution_class=execution_class,
            operation_id=operation_id,
            protocol=protocol,
            fixture_index=fixture_index,
            matrix=matrix,
            lock_path=lock_path,
            lock=lock,
            plan_path=plan,
            expected_owner=owner,
            verifier=verifier,
        )
    control_owner_path = control / "owner.json"
    journal_path = control / "journal.json"
    if control.exists():
        if _read_self_hashed(control_owner_path, "owner_sha256", "control owner") != owner:
            raise OfficialRunError("control root is foreign or drifted")
        journal = _read_self_hashed(journal_path, "journal_sha256", "phase journal")
    else:
        try:
            control.mkdir(parents=False, exist_ok=False)
        except FileExistsError as exc:
            raise OfficialRunError("control root creation collision") from exc
        _publish_json(control_owner_path, owner)
        journal = _new_journal(owner, matrix)
        _publish_json(journal_path, journal)
    for spec in matrix:
        run_root = control / "runs" / spec["run_id"]
        for name in ("entry", "user-data", "task", "output", "web", "flat", "evaluator", "phases"):
            (run_root / name).mkdir(parents=True, exist_ok=True)
        fixture = _fixture_item(fixture_index, spec["sample_id"])
        fixture_path = CANONICAL_FIXTURE_ROOT / fixture["fixture_relative_path"]
        profile_request_path = _build_profile_request(
            spec,
            run_root=run_root,
            lock=lock,
            execution_class=execution_class,
        )
        profile_receipt_path = run_root / "profile-receipt.json"
        if not profile_receipt_path.exists():
            profile_invoker(
                dict(spec), profile_request_path, profile_receipt_path, run_root
            )
        _, profile_receipt = _validate_profile_chain(
            profile_request_path,
            profile_receipt_path,
            spec=spec,
            lock=lock,
            execution_class=execution_class,
        )
        request_path = _build_entry_request(
            spec,
            run_root=run_root,
            fixture_path=fixture_path,
            lock=lock,
            profile_request_path=profile_request_path,
            profile_receipt_path=profile_receipt_path,
            profile_receipt=profile_receipt,
            execution_class=execution_class,
        )
        journal = _advance_phase(
            journal_path, journal, spec, "prepared", request_path, run_root
        )
        if failure_injector:
            failure_injector(f"prepared:{spec['run_id']}")
        host_path = run_root / "host-entry-receipt.json"
        if not host_path.exists():
            host_invoker(dict(spec), request_path, host_path, run_root)
        request = _validate_entry_request(request_path, spec, lock, execution_class)
        _validate_host_receipt(
            host_path,
            request_path=request_path,
            request=request,
            lock=lock,
            execution_class=execution_class,
        )
        journal = _advance_phase(
            journal_path, journal, spec, "host_started", host_path, run_root
        )
        if failure_injector:
            failure_injector(f"host_started:{spec['run_id']}")
        journey_path = Path(request["product_journey_path"]).resolve()
        journey = validate_product_journey(
            protocol,
            fixture,
            spec,
            lock,
            request_path,
            host_path,
            journey_path,
            execution_class=execution_class,
        )
        journal = _advance_phase(
            journal_path, journal, spec, "product_committed", journey_path, run_root
        )
        if failure_injector:
            failure_injector(f"product_committed:{spec['run_id']}")
        evaluator_path = run_root / "evaluator" / "receipt.json"
        fixture_receipt_path = CANONICAL_FIXTURE_ROOT / fixture["receipt_relative_path"]
        if not evaluator_path.exists():
            evaluator_invoker(
                dict(spec), fixture_receipt_path, journey_path, evaluator_path, run_root
            )
        fixture_receipt = _read_json(fixture_receipt_path, "fixture receipt")
        _verify_evaluator(protocol, fixture_receipt, journey, evaluator_path, verifier)
        journal = _advance_phase(
            journal_path, journal, spec, "evaluator_committed", evaluator_path, run_root
        )
        if failure_injector:
            failure_injector(f"evaluator_committed:{spec['run_id']}")
        result_path = run_root / "result.json"
        expected_result = _build_result(
            execution_class=execution_class,
            protocol=protocol,
            fixture_index=fixture_index,
            fixture_item=fixture,
            spec=spec,
            lock_path=lock_path,
            lock=lock,
            plan_path=plan,
            request_path=request_path,
            host_receipt_path=host_path,
            journey_path=journey_path,
            evaluator_path=evaluator_path,
            verifier=verifier,
        )
        if result_path.exists():
            if _read_self_hashed(result_path, "receipt_sha256", "existing result") != expected_result:
                raise OfficialRunError("existing result collision/tamper")
        else:
            _publish_json(result_path, expected_result)
        verify_official_run_result(
            result_path,
            execution_class=execution_class,
            protocol=protocol,
            fixture_index=fixture_index,
            spec=spec,
            lock_path=lock_path,
            lock=lock,
            plan_path=plan,
            verifier=verifier,
        )
        journal = _advance_phase(
            journal_path, journal, spec, "result_verified", result_path, run_root
        )
        if failure_injector:
            failure_injector(f"result_verified:{spec['run_id']}")
    if publish_stage.exists():
        stage_owner = _read_self_hashed(
            publish_stage / "owner.json", "owner_sha256", "publish-stage owner"
        )
        if stage_owner != owner:
            raise OfficialRunError("publish stage is foreign or drifted")
    else:
        try:
            publish_stage.mkdir(parents=False, exist_ok=False)
        except FileExistsError as exc:
            raise OfficialRunError("publish stage creation collision") from exc
        _publish_json(publish_stage / "owner.json", owner)
    index, aggregate = _build_index_and_aggregate(
        execution_class=execution_class,
        operation_id=operation_id,
        protocol=protocol,
        fixture_index=fixture_index,
        matrix=matrix,
        control_root=control,
        publish_stage=publish_stage,
        lock_path=lock_path,
        lock=lock,
        plan_path=plan,
        verifier=verifier,
        now=timestamp,
        failure_injector=failure_injector,
    )
    _verify_published(
        output_root=publish_stage,
        execution_class=execution_class,
        operation_id=operation_id,
        protocol=protocol,
        fixture_index=fixture_index,
        matrix=matrix,
        lock_path=lock_path,
        lock=lock,
        plan_path=plan,
        expected_owner=owner,
        verifier=verifier,
    )
    if failure_injector:
        failure_injector("before_publish")
    if output.exists():
        raise OfficialRunError("results-v3 appeared before publish")
    os.replace(publish_stage, output)
    if failure_injector:
        failure_injector("after_publish")
    checked = _verify_published(
        output_root=output,
        execution_class=execution_class,
        operation_id=operation_id,
        protocol=protocol,
        fixture_index=fixture_index,
        matrix=matrix,
        lock_path=lock_path,
        lock=lock,
        plan_path=plan,
        expected_owner=owner,
        verifier=verifier,
    )
    checked["status"] = "committed"
    checked["index_sha256"] = index["index_sha256"]
    checked["aggregate_sha256"] = aggregate["aggregate_sha256"]
    return checked


def run_official_matrix(
    *,
    operation_id: str,
    approval_token: str,
    candidate_lock_path: str | Path,
    now: datetime | None = None,
    failure_injector: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Run/recover official bytes using only canonical subprocess adapters."""

    lock_path = Path(candidate_lock_path).resolve()
    lock = validate_candidate_lock(
        lock_path, approval_token=approval_token, plan_path=CANONICAL_PLAN_PATH
    )

    def host(
        _spec: dict[str, Any], request: Path, receipt: Path, run_root: Path
    ) -> None:
        _invoke_host(lock, request, receipt, run_root)

    def profile(
        _spec: dict[str, Any], request: Path, receipt: Path, run_root: Path
    ) -> None:
        _invoke_profile(lock, request, receipt, run_root)

    def evaluator(
        _spec: dict[str, Any], fixture: Path, journey: Path, receipt: Path, run_root: Path
    ) -> None:
        _invoke_evaluator(lock, fixture, journey, receipt, run_root)

    return _run_matrix(
        execution_class="official",
        operation_id=operation_id,
        approval_token=approval_token,
        candidate_lock_path=lock_path,
        output_root=CANONICAL_RESULT_ROOT,
        profile_invoker=profile,
        host_invoker=host,
        evaluator_invoker=evaluator,
        verifier=verify_independent_evaluation_receipt_v3,
        now=now,
        failure_injector=failure_injector,
    )


def run_official_matrix_test_only(
    *,
    operation_id: str,
    approval_token: str,
    candidate_lock_path: str | Path,
    output_root: str | Path,
    profile_invoker: Callable[[dict[str, Any], Path, Path, Path], None],
    host_invoker: Callable[[dict[str, Any], Path, Path, Path], None],
    evaluator_invoker: Callable[[dict[str, Any], Path, Path, Path, Path], None],
    verifier: Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], dict[str, Any]],
    now: datetime,
    failure_injector: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Exercise orchestration only; output is typed TEST_ONLY and never official."""

    return _run_matrix(
        execution_class="test_only",
        operation_id=operation_id,
        approval_token=approval_token,
        candidate_lock_path=candidate_lock_path,
        output_root=output_root,
        profile_invoker=profile_invoker,
        host_invoker=host_invoker,
        evaluator_invoker=evaluator_invoker,
        verifier=verifier,
        now=now,
        failure_injector=failure_injector,
    )


__all__ = [
    "AGGREGATE_SCHEMA_PATH",
    "CANONICAL_FIXTURE_ROOT",
    "CANONICAL_PLAN_PATH",
    "CANONICAL_PROTOCOL_PATH",
    "CANONICAL_RESULT_ROOT",
    "CONTROLLER_PATH",
    "EVALUATOR_ADAPTER_PATH",
    "HOST_ADAPTER_PATH",
    "INDEX_SCHEMA_PATH",
    "OfficialRunError",
    "RESULT_SCHEMA_PATH",
    "canonical_sha256",
    "expected_run_matrix",
    "file_sha256",
    "run_official_matrix",
    "run_official_matrix_test_only",
    "source_hashes",
    "validate_candidate_lock",
    "validate_fixture_authority",
    "validate_product_journey",
    "verify_official_run_result",
]
