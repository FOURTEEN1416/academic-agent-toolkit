"""Install one exact suite into one disposable Codex profile for PS-GAP-014.

The adapter is the only official bridge from an approved candidate archive to a
matrix run's isolated ``CODEX_HOME``.  It never reads or copies credentials.  A
test-only bundle/command double is accepted only when ``test_mode=True`` and the
resulting receipt is permanently ineligible for official evidence.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[3]
PROFILE_SCHEMA_PATH = (
    ROOT
    / "03_联合开发"
    / "contracts"
    / "maturity-official-profile-receipt-v2.schema.json"
)
MAX_PROCESS_OUTPUT = 2 * 1024 * 1024
TRANSACTION_PHASES = (
    "prepared",
    "source_placed",
    "managed_placed",
    "skill_placed",
    "plugin_activated",
    "receipt_committed",
)


class ProfilePlacementError(RuntimeError):
    """Raised when isolated candidate placement cannot be proven exactly."""


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


def tree_identity(root: str | Path) -> dict[str, Any]:
    base = Path(root).resolve()
    if not base.is_dir():
        raise ProfilePlacementError(f"tree root is missing: {base}")
    digest = hashlib.sha256()
    files = 0
    total = 0
    for path in sorted(
        (item for item in base.rglob("*") if item.is_file()),
        key=lambda item: item.relative_to(base).as_posix(),
    ):
        relative = path.relative_to(base).as_posix().encode("utf-8")
        content = path.read_bytes()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
        files += 1
        total += len(content)
    if files == 0:
        raise ProfilePlacementError(f"tree is empty: {base}")
    return {"files": files, "bytes": total, "sha256": digest.hexdigest()}


def _file_ref(path: str | Path) -> dict[str, str]:
    target = Path(path).resolve()
    if not target.is_file():
        raise ProfilePlacementError(f"referenced file is missing: {target}")
    return {"path": str(target), "sha256": file_sha256(target)}


def _verify_ref(ref: Mapping[str, Any], label: str) -> Path:
    if set(ref) != {"path", "sha256"}:
        raise ProfilePlacementError(f"{label} reference fields drift")
    path = Path(str(ref["path"])).resolve()
    if not path.is_file() or file_sha256(path) != ref["sha256"]:
        raise ProfilePlacementError(f"{label} reference hash drift")
    return path


def _read_json(path: str | Path, label: str) -> dict[str, Any]:
    target = Path(path).resolve()
    if not target.is_file():
        raise ProfilePlacementError(f"{label} is missing: {target}")
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProfilePlacementError(f"{label} is not UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ProfilePlacementError(f"{label} must be an object")
    return value


def _write_new(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ProfilePlacementError(f"immutable profile artifact collision: {path}")
    stage = path.with_name(f".{path.name}.stage")
    if stage.exists():
        if stage.read_bytes() != data:
            raise ProfilePlacementError(f"profile artifact stage collision: {stage}")
        if path.exists():
            raise ProfilePlacementError(f"profile artifact appeared before recovery: {path}")
        os.replace(stage, path)
        return
    owned = False
    try:
        with stage.open("xb") as handle:
            owned = True
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            raise ProfilePlacementError(f"profile artifact appeared before publish: {path}")
        os.replace(stage, path)
    except Exception:
        if owned and stage.exists():
            stage.unlink()
        raise


def _write_json_new(path: Path, value: dict[str, Any]) -> None:
    _write_new(
        path,
        (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
            "utf-8"
        ),
    )


def _replace_json_owned(
    path: Path, value: dict[str, Any], *, expected_previous: dict[str, Any]
) -> None:
    if _read_json(path, "profile transaction journal") != expected_previous:
        raise ProfilePlacementError("profile transaction journal changed concurrently")
    encoded = (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    stage = path.with_name(f".{path.name}.stage")
    if stage.exists():
        if stage.read_bytes() != encoded:
            raise ProfilePlacementError("foreign profile journal stage collision")
    else:
        with stage.open("xb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    if _read_json(path, "profile transaction journal") != expected_previous:
        raise ProfilePlacementError("profile transaction journal changed before publish")
    os.replace(stage, path)


def _transaction_owner(
    request: Mapping[str, Any],
    request_file: Path,
    receipt_file: Path,
    prestate: Mapping[str, Any],
) -> dict[str, Any]:
    owner = {
        "contract": "paperspine5.maturity-profile-transaction-owner-v2",
        "contract_version": "2.0",
        "run_id": request["run_id"],
        "operation_id": request["operation_id"],
        "request": _file_ref(request_file),
        "receipt_path": str(receipt_file),
        "prestate": copy.deepcopy(dict(prestate)),
        "external_action_authorized": False,
    }
    owner["owner_sha256"] = canonical_sha256(owner)
    return owner


def _new_journal(owner: Mapping[str, Any], prestate: Mapping[str, Any]) -> dict[str, Any]:
    journal = {
        "contract": "paperspine5.maturity-profile-transaction-journal-v2",
        "contract_version": "2.0",
        "owner_sha256": owner["owner_sha256"],
        "phase": "prepared",
        "prestate": copy.deepcopy(dict(prestate)),
        "receipt": None,
        "external_action_authorized": False,
    }
    journal["journal_sha256"] = canonical_sha256(journal)
    return journal


def _read_journal(path: Path, owner: Mapping[str, Any]) -> dict[str, Any]:
    journal = _read_json(path, "profile transaction journal")
    if (
        journal.get("journal_sha256")
        != canonical_sha256(journal, self_hash="journal_sha256")
        or journal.get("owner_sha256") != owner["owner_sha256"]
        or journal.get("phase") not in TRANSACTION_PHASES
        or journal.get("external_action_authorized") is not False
    ):
        raise ProfilePlacementError("profile transaction journal identity drift")
    return journal


def _advance_journal(
    path: Path,
    journal: dict[str, Any],
    phase: str,
    *,
    receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    current_index = TRANSACTION_PHASES.index(journal["phase"])
    wanted_index = TRANSACTION_PHASES.index(phase)
    if current_index > wanted_index:
        return journal
    if current_index == wanted_index:
        if phase == "receipt_committed" and journal.get("receipt") != receipt:
            raise ProfilePlacementError("committed profile journal receipt drift")
        return journal
    if wanted_index != current_index + 1:
        raise ProfilePlacementError("profile transaction phase skipped")
    updated = copy.deepcopy(journal)
    updated["phase"] = phase
    if receipt is not None:
        updated["receipt"] = copy.deepcopy(dict(receipt))
    updated["journal_sha256"] = canonical_sha256(
        updated, self_hash="journal_sha256"
    )
    _replace_json_owned(path, updated, expected_previous=journal)
    return updated


def _tree_map(root: Path, *, exclude: set[str] | None = None) -> dict[str, str]:
    ignored = exclude or set()
    return {
        path.relative_to(root).as_posix(): file_sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.relative_to(root).as_posix() not in ignored
    }


def _verify_candidate_tree(
    api: Any,
    root: Path,
    expected: Mapping[str, Any],
    label: str,
) -> dict[str, Any]:
    try:
        verification = api.verify_bundle(root)
    except Exception as exc:
        raise ProfilePlacementError(f"{label} failed strict release verification") from exc
    if (
        _candidate_identity(verification) != dict(expected)
        or verification.get("discovered_skills") not in (None, [])
    ):
        raise ProfilePlacementError(f"{label} does not match the exact candidate")
    return dict(verification)


def _load_release_api(path: Path, expected_sha256: str) -> Any:
    if not path.is_file() or file_sha256(path) != expected_sha256:
        raise ProfilePlacementError("release verifier path/hash drift")
    spec = importlib.util.spec_from_file_location(
        "paperspine5_official_profile_suite_release", path
    )
    if spec is None or spec.loader is None:
        raise ProfilePlacementError("release verifier cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _candidate_identity(verification: Mapping[str, Any]) -> dict[str, Any]:
    manifest = verification.get("manifest")
    if not isinstance(manifest, Mapping):
        raise ProfilePlacementError("candidate verification lacks a manifest")
    return {
        "build_id": verification.get("build_id"),
        "content_index_id": verification.get("content_index_sha256"),
        "manifest_sha256": verification.get("manifest_sha256"),
    }


def _bounded_environment(profile: Path, user_home: Path) -> dict[str, str]:
    allowed = (
        "APPDATA",
        "COMSPEC",
        "LOCALAPPDATA",
        "PATH",
        "PATHEXT",
        "SystemRoot",
        "TEMP",
        "TMP",
        "WINDIR",
    )
    env = {key: os.environ[key] for key in allowed if key in os.environ}
    env["CODEX_HOME"] = str(profile)
    env["HOME"] = str(user_home)
    env["USERPROFILE"] = str(user_home)
    drive, tail = os.path.splitdrive(str(user_home))
    if drive:
        env["HOMEDRIVE"] = drive
        env["HOMEPATH"] = tail
    return env


def _run_process(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    output_root: Path,
    label: str,
    command_runner: Callable[[list[str], Path, dict[str, str]], tuple[int, bytes, bytes]]
    | None,
    failure_injector: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    result_path = output_root / f"{label}.result.json"
    result_stage = result_path.with_name(f".{result_path.name}.stage")
    intent_path = output_root / f"{label}.intent.json"
    intent = {
        "contract": "paperspine5.maturity-profile-process-intent-v2",
        "contract_version": "2.0",
        "label": label,
        "argv": list(argv),
        "cwd": str(cwd.resolve()),
        "external_action_authorized": False,
    }
    intent["intent_sha256"] = canonical_sha256(intent)
    if intent_path.exists():
        if _read_json(intent_path, f"{label} process intent") != intent:
            raise ProfilePlacementError(f"{label} process intent drift")
    else:
        _write_json_new(intent_path, intent)

    def validate_result(result: dict[str, Any]) -> dict[str, Any]:
        _verify_ref(result["stdout"], f"{label} stdout")
        _verify_ref(result["stderr"], f"{label} stderr")
        if result.get("argv") != argv or result.get("exit_code") != 0:
            raise ProfilePlacementError(f"{label} persisted process result drift")
        return result

    if result_path.exists():
        return validate_result(_read_json(result_path, f"{label} process result"))
    if result_stage.exists():
        staged = validate_result(_read_json(result_stage, f"{label} result stage"))
        if result_path.exists():
            raise ProfilePlacementError(f"{label} result appeared before stage recovery")
        os.replace(result_stage, result_path)
        return staged
    if command_runner is None:
        completed = subprocess.run(
            argv,
            cwd=str(cwd),
            env=env,
            capture_output=True,
            timeout=180,
            check=False,
        )
        code, stdout, stderr = completed.returncode, completed.stdout, completed.stderr
    else:
        code, stdout, stderr = command_runner(list(argv), cwd, dict(env))
    if failure_injector:
        failure_injector(f"{label}:command_returned")
    if len(stdout) > MAX_PROCESS_OUTPUT or len(stderr) > MAX_PROCESS_OUTPUT:
        raise ProfilePlacementError(f"{label} output exceeded the hard cap")
    stdout_path = output_root / f"{label}.stdout"
    stderr_path = output_root / f"{label}.stderr"
    if stdout_path.exists():
        if stdout_path.read_bytes() != stdout:
            raise ProfilePlacementError(f"{label} stdout differs on recovery")
    else:
        _write_new(stdout_path, stdout)
    if failure_injector:
        failure_injector(f"{label}:stdout_published")
    if stderr_path.exists():
        if stderr_path.read_bytes() != stderr:
            raise ProfilePlacementError(f"{label} stderr differs on recovery")
    else:
        _write_new(stderr_path, stderr)
    if failure_injector:
        failure_injector(f"{label}:stderr_published")
    result = {
        "argv": list(argv),
        "exit_code": int(code),
        "stdout": _file_ref(stdout_path),
        "stderr": _file_ref(stderr_path),
    }
    if code != 0:
        raise ProfilePlacementError(f"{label} failed with exit code {code}")
    encoded = (
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    if result_stage.exists():
        if result_stage.read_bytes() != encoded:
            raise ProfilePlacementError(f"{label} foreign result stage collision")
    else:
        with result_stage.open("xb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    if failure_injector:
        failure_injector(f"{label}:result_staged")
    if result_path.exists():
        raise ProfilePlacementError(f"{label} result appeared before publish")
    os.replace(result_stage, result_path)
    if failure_injector:
        failure_injector(f"{label}:result_published")
    return result


def _parse_plugin_list(process: Mapping[str, Any]) -> dict[str, Any]:
    stdout = _verify_ref(process["stdout"], "plugin list stdout")
    try:
        payload = json.loads(stdout.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ProfilePlacementError("plugin list stdout is not JSON") from exc
    if not isinstance(payload, dict):
        raise ProfilePlacementError("plugin list stdout must be an object")
    return payload


def _plugin_row(payload: Mapping[str, Any]) -> dict[str, Any]:
    installed = payload.get("installed")
    if not isinstance(installed, list):
        raise ProfilePlacementError("plugin list lacks installed entries")
    rows = [
        row
        for row in installed
        if isinstance(row, dict) and row.get("pluginId") == "paperspine5@personal"
    ]
    if len(rows) != 1 or rows[0].get("installed") is not True or rows[0].get("enabled") is not True:
        raise ProfilePlacementError("isolated profile does not have one enabled paperspine5 plugin")
    return rows[0]


def _optional_plugin_row(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    installed = payload.get("installed")
    if not isinstance(installed, list):
        raise ProfilePlacementError("plugin list lacks installed entries")
    rows = [
        row
        for row in installed
        if isinstance(row, dict) and row.get("pluginId") == "paperspine5@personal"
    ]
    if not rows:
        return None
    if len(rows) != 1 or rows[0].get("installed") is not True or rows[0].get("enabled") is not True:
        raise ProfilePlacementError("isolated plugin activation state is ambiguous")
    return rows[0]


def _skill_name(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("name:"):
            return line.split(":", 1)[1].strip()
    raise ProfilePlacementError(f"Skill frontmatter name is missing: {path}")


def _discovery(profile: Path, user_home: Path, build_id: str) -> dict[str, Any]:
    roots = (profile / "skills", user_home / ".agents" / "skills")
    skill_files = sorted(
        {
            path.resolve()
            for root in roots
            if root.is_dir()
            for path in root.rglob("SKILL.md")
            if path.is_file()
        },
        key=lambda path: path.as_posix(),
    )
    names = [_skill_name(path) for path in skill_files]
    result = {
        "paper_spine": names.count("paper-spine"),
        "paperFig": names.count("paperFig"),
        "workspace": names.count("paperspine5-workspace"),
        "skill_files": [_file_ref(path) for path in skill_files],
        "build_id": build_id,
    }
    if result["paper_spine"] != 1 or result["paperFig"] or result["workspace"] or len(skill_files) != 1:
        raise ProfilePlacementError("isolated profile discovery is not exact 1/0/0")
    return result


def _schema_validate(receipt: dict[str, Any]) -> None:
    schema = _read_json(PROFILE_SCHEMA_PATH, "profile receipt schema")
    errors = sorted(
        Draft202012Validator(
            schema, format_checker=Draft202012Validator.FORMAT_CHECKER
        ).iter_errors(receipt),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        first = errors[0]
        location = ".".join(str(item) for item in first.absolute_path) or "root"
        raise ProfilePlacementError(
            f"profile receipt schema violation at {location}: {first.message}"
        )


def validate_profile_receipt(
    receipt_path: str | Path,
    request: Mapping[str, Any],
    *,
    request_path: str | Path,
    expected_test_only: bool,
    release_api: Any | None = None,
) -> dict[str, Any]:
    receipt = _read_json(receipt_path, "isolated profile receipt")
    if receipt.get("receipt_sha256") != canonical_sha256(
        receipt, self_hash="receipt_sha256"
    ):
        raise ProfilePlacementError("isolated profile receipt self-hash drift")
    _schema_validate(receipt)
    expected_candidate = {
        "archive": {
            "path": str(Path(request["archive_path"]).resolve()),
            "sha256": request["archive_sha256"],
        },
        "build_id": request["build_id"],
        "content_index_id": request["content_index_id"],
        "manifest_sha256": request["manifest_sha256"],
    }
    if (
        receipt["run_id"] != request["run_id"]
        or receipt["operation_id"] != request["operation_id"]
        or receipt["profile_root"] != str(Path(request["profile_root"]).resolve())
        or receipt["user_home_root"] != str(Path(request["user_home_root"]).resolve())
        or receipt["candidate"] != expected_candidate
        or receipt["release_verifier"]
        != {
            "path": str(Path(request["release_verifier_path"]).resolve()),
            "sha256": request["release_verifier_sha256"],
        }
        or receipt["test_only"] is not expected_test_only
        or receipt["status"] != "committed"
    ):
        raise ProfilePlacementError("isolated profile receipt subject/candidate drift")
    _verify_ref(receipt["candidate"]["archive"], "candidate archive")
    release_path = _verify_ref(receipt["release_verifier"], "release verifier")
    api = release_api or _load_release_api(
        release_path, request["release_verifier_sha256"]
    )
    archive_verification = api.verify_bundle(
        Path(receipt["candidate"]["archive"]["path"])
    )
    expected_identity = {
        "build_id": request["build_id"],
        "content_index_id": request["content_index_id"],
        "manifest_sha256": request["manifest_sha256"],
    }
    if (
        _candidate_identity(archive_verification) != expected_identity
        or archive_verification.get("discovered_skills") not in (None, [])
    ):
        raise ProfilePlacementError("candidate archive no longer verifies exactly")
    for label, process in (
        ("activation", receipt["plugin"]["activation"]["process"]),
        ("plugin list", receipt["plugin"]["cli_list"]),
    ):
        _verify_ref(process["stdout"], f"{label} stdout")
        _verify_ref(process["stderr"], f"{label} stderr")
        if process["exit_code"] != 0:
            raise ProfilePlacementError("profile activation process did not exit successfully")
    plugin_row = _plugin_row(_parse_plugin_list(receipt["plugin"]["cli_list"]))
    profile = Path(receipt["profile_root"]).resolve()
    user_home = Path(receipt["user_home_root"]).resolve()
    plugin_root = Path(receipt["plugin"]["source_root"]).resolve()
    cache_root = Path(receipt["plugin"]["cache_root"]).resolve()
    skill_root = Path(receipt["skill"]["root"]).resolve()
    managed_root = Path(receipt["skill"]["managed_suite_root"]).resolve()
    plugin_verification = _verify_candidate_tree(
        api, plugin_root, expected_identity, "plugin source"
    )
    cache_verification = _verify_candidate_tree(
        api, cache_root, expected_identity, "enabled plugin cache"
    )
    managed_verification = _verify_candidate_tree(
        api, managed_root, expected_identity, "managed suite"
    )
    if (
        _candidate_identity(plugin_verification)
        != _candidate_identity(cache_verification)
        or _candidate_identity(plugin_verification)
        != _candidate_identity(managed_verification)
        or tree_identity(plugin_root) != tree_identity(cache_root)
        or tree_identity(plugin_root) != tree_identity(managed_root)
        or tree_identity(plugin_root) != receipt["plugin"]["source_tree"]
        or tree_identity(cache_root) != receipt["plugin"]["cache_tree"]
        or tree_identity(skill_root) != receipt["skill"]["tree"]
        or tree_identity(managed_root) != receipt["skill"]["managed_suite_tree"]
        or file_sha256(skill_root / "SKILL.md")
        != receipt["skill"]["skill_file_sha256"]
        or Path(str((plugin_row.get("source") or {}).get("path", ""))).resolve()
        != plugin_root
    ):
        raise ProfilePlacementError("isolated profile plugin/Skill tree identity drift")
    projection = plugin_root / "standalone" / "paper-spine"
    if _tree_map(projection) != _tree_map(
        skill_root, exclude={"references/installed-suite.json"}
    ):
        raise ProfilePlacementError("canonical Skill projection differs from the candidate")
    pointer_path = Path(receipt["pointer"]["path"]).resolve()
    if file_sha256(pointer_path) != receipt["pointer"]["file_sha256"]:
        raise ProfilePlacementError("installed suite pointer file hash drift")
    pointer = _read_json(pointer_path, "installed suite pointer")
    if (
        pointer.get("build_id") != request["build_id"]
        or pointer.get("content_index_sha256") != request["content_index_id"]
        or Path(str(pointer.get("suite_root", ""))).resolve() != managed_root
        or receipt["pointer"]["suite_root"] != str(managed_root)
    ):
        raise ProfilePlacementError("installed suite pointer identity drift")
    if _discovery(profile, user_home, request["build_id"]) != receipt["discovery"]:
        raise ProfilePlacementError("isolated profile discovery receipt drift")
    owner_path = _verify_ref(receipt["transaction_owner"], "profile transaction owner")
    output_root = owner_path.parent / "profile-transaction"
    expected_owner = _transaction_owner(
        request,
        Path(request_path).resolve(),
        Path(receipt_path).resolve(),
        receipt["prestate"],
    )
    owner = _read_json(owner_path, "profile transaction owner")
    if owner != expected_owner:
        raise ProfilePlacementError("profile transaction owner drift")
    journal = _read_journal(output_root / "journal.json", owner)
    if (
        journal["phase"] != "receipt_committed"
        or journal["receipt"] != _file_ref(receipt_path)
    ):
        raise ProfilePlacementError("profile receipt lacks a committed transaction journal")
    return copy.deepcopy(receipt)


def prepare_candidate_profile(
    request_path: str | Path,
    receipt_path: str | Path,
    *,
    release_api: Any | None = None,
    command_runner: Callable[[list[str], Path, dict[str, str]], tuple[int, bytes, bytes]]
    | None = None,
    test_mode: bool = False,
    now: datetime | None = None,
    failure_injector: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    request_file = Path(request_path).resolve()
    request = _read_json(request_file, "profile placement request")
    if request.get("request_sha256") != canonical_sha256(
        request, self_hash="request_sha256"
    ):
        raise ProfilePlacementError("profile placement request self-hash drift")
    if (
        release_api is not None
        or command_runner is not None
        or failure_injector is not None
    ) and not test_mode:
        raise ProfilePlacementError("injected profile dependencies are forbidden in official mode")
    receipt_file = Path(receipt_path).resolve()
    run_root = Path(request["run_root"]).resolve()
    profile = Path(request["profile_root"]).resolve()
    user_home = Path(request["user_home_root"]).resolve()
    try:
        profile.relative_to(run_root)
        user_home.relative_to(run_root)
        receipt_file.relative_to(run_root)
    except ValueError as exc:
        raise ProfilePlacementError("profile transaction path escapes its run root") from exc
    plugin_root = user_home / "plugins" / "paperspine5"
    skill_root = profile / "skills" / "paper-spine"
    managed_root = (
        user_home
        / ".paperspine5"
        / "skill-updates"
        / "installs"
        / request["build_id"]
    )
    marketplace_path = user_home / ".agents" / "plugins" / "marketplace.json"
    archive = Path(request["archive_path"]).resolve()
    if not archive.is_file() or file_sha256(archive) != request["archive_sha256"]:
        raise ProfilePlacementError("candidate archive path/hash drift")
    release_path = Path(request["release_verifier_path"]).resolve()
    api = release_api or _load_release_api(
        release_path, request["release_verifier_sha256"]
    )
    verification = api.verify_bundle(archive)
    if _candidate_identity(verification) != {
        "build_id": request["build_id"],
        "content_index_id": request["content_index_id"],
        "manifest_sha256": request["manifest_sha256"],
    }:
        raise ProfilePlacementError("candidate archive identity differs from request")
    if verification.get("discovered_skills") not in (None, []):
        raise ProfilePlacementError("candidate plugin exposes a discoverable Skill")
    expected_identity = {
        "build_id": request["build_id"],
        "content_index_id": request["content_index_id"],
        "manifest_sha256": request["manifest_sha256"],
    }
    output_root = run_root / "profile-transaction"
    owner_path = run_root / "profile-transaction.owner.json"
    journal_path = output_root / "journal.json"
    if owner_path.exists():
        owner = _read_json(owner_path, "profile transaction owner")
        if owner.get("owner_sha256") != canonical_sha256(
            owner, self_hash="owner_sha256"
        ):
            raise ProfilePlacementError("profile transaction owner self-hash drift")
        prestate = owner.get("prestate")
        if not isinstance(prestate, dict):
            raise ProfilePlacementError("profile transaction owner lacks prestate")
        expected_owner = _transaction_owner(
            request, request_file, receipt_file, prestate
        )
        if owner != expected_owner:
            raise ProfilePlacementError("foreign profile transaction owner collision")
    else:
        prestate = {
            "profile_absent": not profile.exists(),
            "plugin_absent": not plugin_root.exists(),
            "skill_absent": not skill_root.exists(),
            "fresh_install_registered": bool(request["fresh_install_registered"]),
        }
        if not all(
            prestate[key]
            for key in ("profile_absent", "plugin_absent", "skill_absent")
        ):
            raise ProfilePlacementError("isolated profile prestate is not empty")
        owner = _transaction_owner(request, request_file, receipt_file, prestate)
        _write_json_new(owner_path, owner)
    if output_root.exists():
        if not output_root.is_dir():
            raise ProfilePlacementError("profile transaction root is not a directory")
    else:
        output_root.mkdir(parents=False, exist_ok=False)
    if journal_path.exists():
        journal = _read_journal(journal_path, owner)
    else:
        if any(output_root.iterdir()):
            raise ProfilePlacementError("profile transaction root lacks its first journal")
        journal = _new_journal(owner, prestate)
        _write_json_new(journal_path, journal)
    if receipt_file.exists():
        if journal["phase"] == "plugin_activated":
            journal = _advance_journal(
                journal_path,
                journal,
                "receipt_committed",
                receipt=_file_ref(receipt_file),
            )
        return validate_profile_receipt(
            receipt_file,
            request,
            request_path=request_file,
            expected_test_only=test_mode,
            release_api=api,
        )

    def inject(phase: str) -> None:
        if failure_injector:
            failure_injector(phase)

    def place_bundle(stage_name: str, target: Path, label: str) -> None:
        stage = output_root / stage_name
        if target.exists():
            _verify_candidate_tree(api, target, expected_identity, label)
            return
        if not stage.exists():
            api.extract_verified_bundle(archive, stage)
        _verify_candidate_tree(api, stage, expected_identity, f"{label} stage")
        inject(f"{stage_name}:prepared")
        if target.exists():
            raise ProfilePlacementError(f"{label} appeared before owned promote")
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(stage, target)
        _verify_candidate_tree(api, target, expected_identity, label)

    place_bundle("plugin-source.stage", plugin_root, "plugin source")
    inject("source_promoted")
    journal = _advance_journal(journal_path, journal, "source_placed")
    place_bundle("managed-suite.stage", managed_root, "managed suite")
    inject("managed_promoted")
    journal = _advance_journal(journal_path, journal, "managed_placed")

    projection = plugin_root / "standalone" / "paper-spine"
    if not (projection / "SKILL.md").is_file():
        raise ProfilePlacementError("candidate canonical Skill projection is missing")
    pointer = {
        "contract": "paperspine5.installed-suite-pointer",
        "schema_version": "1.0",
        "product_id": "paperspine5",
        "build_id": request["build_id"],
        "content_index_sha256": request["content_index_id"],
        "suite_root": str(managed_root.resolve()),
    }
    pointer_bytes = (
        json.dumps(pointer, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    skill_stage = output_root / "canonical-skill.stage"
    if not skill_root.exists():
        if not skill_stage.exists():
            shutil.copytree(projection, skill_stage)
            stage_pointer = skill_stage / "references" / "installed-suite.json"
            stage_pointer.parent.mkdir(parents=True, exist_ok=True)
            stage_pointer.write_bytes(pointer_bytes)
        if _tree_map(projection) != _tree_map(
            skill_stage, exclude={"references/installed-suite.json"}
        ):
            raise ProfilePlacementError("canonical Skill stage differs from projection")
        if (skill_stage / "references" / "installed-suite.json").read_bytes() != pointer_bytes:
            raise ProfilePlacementError("canonical Skill stage pointer drift")
        skill_root.parent.mkdir(parents=True, exist_ok=True)
        os.replace(skill_stage, skill_root)
    pointer_path = skill_root / "references" / "installed-suite.json"
    if (
        _tree_map(projection)
        != _tree_map(skill_root, exclude={"references/installed-suite.json"})
        or pointer_path.read_bytes() != pointer_bytes
    ):
        raise ProfilePlacementError("canonical Skill final projection/pointer drift")
    marketplace = {
        "name": "personal",
        "interface": {"displayName": "Personal"},
        "plugins": [
            {
                "name": "paperspine5",
                "source": {"source": "local", "path": "./plugins/paperspine5"},
                "policy": {
                    "installation": "AVAILABLE",
                    "authentication": "ON_INSTALL",
                },
                "category": "Productivity",
            }
        ],
    }
    marketplace_bytes = (
        json.dumps(marketplace, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    if marketplace_path.exists():
        if marketplace_path.read_bytes() != marketplace_bytes:
            raise ProfilePlacementError("personal marketplace bytes drift")
    else:
        _write_new(marketplace_path, marketplace_bytes)
    inject("skill_promoted")
    journal = _advance_journal(journal_path, journal, "skill_placed")

    env = _bounded_environment(profile, user_home)
    codex = str(Path(request["codex_executable"]).resolve())
    list_argv = [codex, "plugin", "list", "--marketplace", "personal", "--json"]
    cache_parent = profile / "plugins" / "cache" / "personal" / "paperspine5"
    current_label = (
        "plugin-list-recovery"
        if cache_parent.is_dir() and any(cache_parent.iterdir())
        else "plugin-list-current"
    )
    cli_current = _run_process(
        list_argv,
        cwd=user_home,
        env=env,
        output_root=output_root,
        label=current_label,
        command_runner=command_runner,
        failure_injector=failure_injector,
    )
    current_row = _optional_plugin_row(_parse_plugin_list(cli_current))
    add_argv = [codex, "plugin", "add", "paperspine5@personal", "--json"]
    if current_row is not None:
        add_result_path = output_root / "plugin-add.result.json"
        add_result_stage = add_result_path.with_name(f".{add_result_path.name}.stage")
        if add_result_stage.exists() and not add_result_path.exists():
            staged_add = _read_json(add_result_stage, "plugin add result stage")
            if (
                staged_add.get("argv") != add_argv
                or staged_add.get("exit_code") != 0
            ):
                raise ProfilePlacementError("plugin add result stage drift")
            _verify_ref(staged_add["stdout"], "plugin add stdout")
            _verify_ref(staged_add["stderr"], "plugin add stderr")
            os.replace(add_result_stage, add_result_path)
        if add_result_path.exists():
            persisted_add = _read_json(add_result_path, "plugin add process result")
            if (
                persisted_add.get("argv") != add_argv
                or persisted_add.get("exit_code") != 0
            ):
                raise ProfilePlacementError("plugin add process result drift")
            _verify_ref(persisted_add["stdout"], "plugin add stdout")
            _verify_ref(persisted_add["stderr"], "plugin add stderr")
            activation = {"method": "plugin_add", "process": persisted_add}
        else:
            activation = {
                "method": "recovered_already_active",
                "process": cli_current,
            }
    else:
        cli_add = _run_process(
            add_argv,
            cwd=user_home,
            env=env,
            output_root=output_root,
            label="plugin-add",
            command_runner=command_runner,
            failure_injector=failure_injector,
        )
        activation = {"method": "plugin_add", "process": cli_add}
    cli_list = _run_process(
        list_argv,
        cwd=user_home,
        env=env,
        output_root=output_root,
        label="plugin-list-final",
        command_runner=command_runner,
        failure_injector=failure_injector,
    )
    row = _plugin_row(_parse_plugin_list(cli_list))
    version = str(row.get("version", ""))
    if not version or Path(version).name != version:
        raise ProfilePlacementError("installed plugin version is unsafe or missing")
    cache_root = profile / "plugins" / "cache" / "personal" / "paperspine5" / version
    _verify_candidate_tree(api, cache_root, expected_identity, "enabled plugin cache")
    if (
        tree_identity(plugin_root) != tree_identity(cache_root)
        or tree_identity(plugin_root) != tree_identity(managed_root)
    ):
        raise ProfilePlacementError("candidate source/cache/managed bytes differ")
    inject("plugin_activated")
    journal = _advance_journal(journal_path, journal, "plugin_activated")
    receipt = {
            "contract": "paperspine5.maturity-isolated-profile-receipt-v2",
            "contract_version": "2.0",
            "run_id": request["run_id"],
            "operation_id": request["operation_id"],
            "profile_root": str(profile),
            "user_home_root": str(user_home),
            "candidate": {
                "archive": _file_ref(archive),
                "build_id": request["build_id"],
                "content_index_id": request["content_index_id"],
                "manifest_sha256": request["manifest_sha256"],
            },
            "release_verifier": _file_ref(release_path),
            "transaction_owner": _file_ref(owner_path),
            "plugin": {
                "source_root": str(plugin_root.resolve()),
                "source_tree": tree_identity(plugin_root),
                "cache_root": str(cache_root.resolve()),
                "cache_tree": tree_identity(cache_root),
                "marketplace": _file_ref(marketplace_path),
                "activation": activation,
                "cli_list": cli_list,
                "enabled": True,
                "discovered_skills": [],
            },
            "skill": {
                "root": str(skill_root.resolve()),
                "tree": tree_identity(skill_root),
                "skill_file_sha256": file_sha256(skill_root / "SKILL.md"),
                "managed_suite_root": str(managed_root.resolve()),
                "managed_suite_tree": tree_identity(managed_root),
            },
            "pointer": {
                "path": str(pointer_path.resolve()),
                "file_sha256": file_sha256(pointer_path),
                "build_id": request["build_id"],
                "content_index_id": request["content_index_id"],
                "suite_root": str(managed_root.resolve()),
            },
            "discovery": _discovery(profile, user_home, request["build_id"]),
            "prestate": prestate,
            "committed_at": (now or datetime.now().astimezone()).isoformat(
                timespec="milliseconds"
            ),
            "requires_fresh_host": True,
            "test_only": test_mode,
            "external_action_authorized": False,
            "status": "committed",
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    _schema_validate(receipt)
    _write_json_new(receipt_file, receipt)
    inject("receipt_published")
    journal = _advance_journal(
        journal_path,
        journal,
        "receipt_committed",
        receipt=_file_ref(receipt_file),
    )
    inject("journal_committed")
    return validate_profile_receipt(
        receipt_file,
        request,
        request_path=request_file,
        expected_test_only=test_mode,
        release_api=api,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True)
    parser.add_argument("--receipt", required=True)
    args = parser.parse_args(argv)
    prepare_candidate_profile(args.request, args.receipt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
