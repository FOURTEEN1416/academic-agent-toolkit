"""Run one disposable real-Codex probe through the Product Web child boundary.

The probe never reads or copies credentials.  Its receipt contains only a
sanitized command shape, process/result identity, and the task-local child tree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

RUNTIME_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = RUNTIME_ROOT.parents[1]

if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))

from web_agent_runtime import (  # noqa: E402
    AgentProfileIsolationUnavailableError,
    AgentResourceLimitError,
    ProductWebAgentRuntime,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _sanitize_command(command: list[str], probe_root: Path) -> list[str]:
    replacements = (
        (str(probe_root), "<PROBE_ROOT>"),
        (str(PROJECT_ROOT), "<PROJECT_ROOT>"),
    )
    sanitized: list[str] = []
    for item in command:
        if item.startswith("sqlite_home="):
            sanitized.append(
                'sqlite_home="<PROBE_ROOT>/workspace/.paperspine5-agent-state/sqlite"'
            )
            continue
        value = item
        for raw, marker in replacements:
            value = value.replace(raw, marker)
            value = value.replace(raw.replace("\\", "/"), marker)
        sanitized.append(value)
    return sanitized


def _metadata_inventory(root: Path, *, include_items: bool) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    if root.is_dir():
        for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
            stat = path.stat()
            items.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "size_bytes": stat.st_size,
                    "mtime_ns": stat.st_mtime_ns,
                    "sha256": _sha256(path),
                }
            )
    encoded = json.dumps(
        items, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    inventory = {
        "file_count": len(items),
        "size_bytes": sum(item["size_bytes"] for item in items),
        "metadata_tree_sha256": hashlib.sha256(encoded).hexdigest(),
    }
    if include_items:
        inventory["items"] = items
    return inventory


def _session_inventory(codex_home: Path) -> dict[str, Any]:
    combined: list[dict[str, Any]] = []
    for name in ("sessions", "archived_sessions"):
        root = codex_home / name
        subtree = _metadata_inventory(root, include_items=True)
        for item in subtree.pop("items", []):
            item["path"] = f"{name}/{item['path']}"
            combined.append(item)
    combined.sort(key=lambda item: item["path"])
    encoded = json.dumps(
        combined, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return {
        "file_count": len(combined),
        "size_bytes": sum(item["size_bytes"] for item in combined),
        "metadata_tree_sha256": hashlib.sha256(encoded).hexdigest(),
        "items": combined,
    }


def _protected_surface_inventory(codex_home: Path) -> dict[str, Any]:
    config = codex_home / "config.toml"
    config_entry: dict[str, Any] | None = None
    if config.is_file():
        stat = config.stat()
        config_entry = {
            "path": "config.toml",
            "size_bytes": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "sha256": _sha256(config),
        }
    return {
        "config": config_entry,
        "plugins": _metadata_inventory(codex_home / "plugins", include_items=False),
        "skills": _metadata_inventory(codex_home / "skills", include_items=False),
    }


def _parent_authenticated_environment(
    manager: ProductWebAgentRuntime, snapshot: dict[str, Any]
) -> dict[str, str]:
    environment = dict(manager.base_environment)
    for name in (
        "CODEX_CI",
        "CODEX_SESSION_ID",
        "CODEX_THREAD_ID",
        "CODEX_APP_TOOLS_PIPE_PATH",
        "CODEX_INTERNAL_ORIGINATOR_OVERRIDE",
    ):
        environment.pop(name, None)
    if not environment.get("CODEX_HOME"):
        environment["CODEX_HOME"] = str(Path.home() / ".codex")
    run_contract = snapshot.get("run_contract")
    configuration = (
        run_contract.get("configuration", {}) if isinstance(run_contract, dict) else {}
    )
    network_policy = (
        configuration.get("network_policy", {})
        if isinstance(configuration, dict)
        else {}
    )
    if isinstance(network_policy, dict) and network_policy.get("allow_network") is True:
        environment.pop("CODEX_SANDBOX_NETWORK_DISABLED", None)
    return environment


class _Kernel:
    def __init__(self, task: dict[str, Any]) -> None:
        self.task = task

    def get_task(self, task_id: str) -> dict[str, Any]:
        if task_id != self.task["task_id"]:
            raise KeyError(task_id)
        return self.task


class _Runner:
    def snapshot(self, task_id: str) -> dict[str, Any]:
        return {
            "task_id": task_id,
            "revision": 0,
            "run_contract": {
                "configuration": {"network_policy": {"allow_network": True}}
            },
            "external_action_authorized": False,
        }


def run_probe(probe_root: Path, *, auth_mode: str) -> dict[str, Any]:
    probe_root = probe_root.resolve()
    if probe_root.exists():
        raise RuntimeError(f"probe root already exists: {probe_root}")
    workspace = probe_root / "workspace"
    run_root = workspace / "runs" / "probe-run"
    workspace.mkdir(parents=True)
    run_root.mkdir(parents=True)
    task = {
        "task_id": "task-real-codex-profile-probe",
        "title": "Disposable real Codex profile isolation probe",
        "revision": 0,
        "workspace_root": str(workspace),
        "run_root": str(run_root),
        "core_root": str(PROJECT_ROOT / "03_联合开发"),
        "material_grants": [],
        "product_manifest": {"build_id": "source-worktree-probe"},
    }
    manager = ProductWebAgentRuntime(
        kernel=_Kernel(task),
        runner=_Runner(),
        project_root=PROJECT_ROOT,
        user_data_root=probe_root,
        runner_writer_owner=lambda task_id: f"probe-owner:{task_id}",
        runner_writer_used=lambda task_id, writer_id: None,
        standalone_skill_path=(
            PROJECT_ROOT / "01_PaperSpine4" / "src" / "skill" / "SKILL.md"
        ),
        codex_executable="codex",
        base_environment=dict(os.environ),
    )
    schema_path = workspace / "probe-result.schema.json"
    result_path = workspace / "probe-result.json"
    log_path = workspace / "probe-agent.log"
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": ["status", "external_action_authorized"],
        "properties": {
            "status": {"const": "ok"},
            "external_action_authorized": {"const": False},
        },
    }
    _write_json(schema_path, schema)
    command = manager._command(task, schema_path, result_path)
    snapshot = _Runner().snapshot(task["task_id"])
    environment = (
        manager._child_environment(task, snapshot)
        if auth_mode == "empty-child-home"
        else _parent_authenticated_environment(manager, snapshot)
    )
    parent_codex_home = Path(environment["CODEX_HOME"]).expanduser().resolve()
    sessions_before = (
        _session_inventory(parent_codex_home) if auth_mode == "parent-home" else None
    )
    protected_before = (
        _protected_surface_inventory(parent_codex_home)
        if auth_mode == "parent-home"
        else None
    )
    process_options = {
        "input": (
            "Return exactly one JSON object with status=\"ok\" and "
            "external_action_authorized=false. Do not call tools and do not add prose."
        ),
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "cwd": str(workspace),
        "env": environment,
        "stderr": subprocess.STDOUT,
        "creationflags": 0,
        "timeout": 180,
        "check": False,
    }
    process_error: str | None = None
    returncode: int | None = None
    try:
        completed = manager._run_codex_process(
            command=command,
            stdout_path=log_path,
            process_options=process_options,
        )
        returncode = completed.returncode
    except (AgentResourceLimitError, AgentProfileIsolationUnavailableError) as exc:
        process_error = exc.code
    except (OSError, subprocess.TimeoutExpired, RuntimeError) as exc:
        process_error = type(exc).__name__

    sessions_after = (
        _session_inventory(parent_codex_home) if auth_mode == "parent-home" else None
    )
    protected_after = (
        _protected_surface_inventory(parent_codex_home)
        if auth_mode == "parent-home"
        else None
    )

    child_home = Path(environment["CODEX_HOME"])
    child_files = []
    if auth_mode == "empty-child-home":
        for path in sorted(item for item in child_home.rglob("*") if item.is_file()):
            child_files.append(
                {
                    "path": path.relative_to(child_home).as_posix(),
                    "size_bytes": path.stat().st_size,
                    "sha256": _sha256(path),
                }
            )
    auth_files = [item for item in child_files if Path(item["path"]).name == "auth.json"]
    session_files = [
        item
        for item in child_files
        if item["path"].startswith("sessions/")
        or item["path"].startswith("archived_sessions/")
    ]
    result: dict[str, Any] | None = None
    result_error: str | None = None
    if result_path.is_file():
        try:
            loaded = json.loads(result_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                result = loaded
            else:
                result_error = "result_not_object"
        except (OSError, json.JSONDecodeError) as exc:
            result_error = type(exc).__name__
    log_bytes = log_path.read_bytes() if log_path.is_file() else b""
    result_bytes = result_path.read_bytes() if result_path.is_file() else b""
    history_payload_detected = any(
        marker in log_bytes or marker in result_bytes
        for marker in (b"data:image", b"EOF while parsing a string")
    )
    credential_like_output_detected = any(
        marker in log_bytes.lower() or marker in result_bytes.lower()
        for marker in (b"authorization: bearer", b"bearer sk-", b'"access_token"')
    )
    sessions_unchanged = sessions_before == sessions_after
    protected_surfaces_unchanged = protected_before == protected_after
    passed = (
        returncode == 0
        and process_error is None
        and result == {"status": "ok", "external_action_authorized": False}
        and not history_payload_detected
        and not credential_like_output_detected
        and (
            (not auth_files and not session_files)
            if auth_mode == "empty-child-home"
            else sessions_unchanged and protected_surfaces_unchanged
        )
    )
    receipt = {
        "contract": "paperspine5.real-codex-profile-isolation-probe",
        "schema_version": "1.0",
        "status": "PASS" if passed else "BLOCKED",
        "auth_mode": auth_mode,
        "command_shape": _sanitize_command(command, probe_root),
        "strict_config": "--strict-config" in command,
        "ephemeral": "--ephemeral" in command,
        "ignore_user_config": "--ignore-user-config" in command,
        "history_persistence_none": 'history.persistence="none"' in command,
        "task_local_sqlite": any(
            item.startswith("sqlite_home=") and "<PROBE_ROOT>" in sanitized
            for item, sanitized in zip(command, _sanitize_command(command, probe_root))
        ),
        "plugins_disabled": "features.plugins=false" in command,
        "multi_agent_disabled": "features.multi_agent=false" in command,
        "mcp_disabled": "mcp_servers={}" in command,
        "returncode": returncode,
        "process_error": process_error,
        "result_error": result_error,
        "result": result,
        "result_sha256": _sha256(result_path) if result_path.is_file() else None,
        "log": (
            {
                "path": log_path.relative_to(probe_root).as_posix(),
                "size_bytes": log_path.stat().st_size,
                "sha256": _sha256(log_path),
            }
            if log_path.is_file()
            else None
        ),
        "child_codex_home": (
            {
                "path": child_home.relative_to(probe_root).as_posix(),
                "files": child_files,
                "auth_file_count": len(auth_files),
                "session_file_count": len(session_files),
            }
            if auth_mode == "empty-child-home"
            else None
        ),
        "parent_session_inventory_before": sessions_before,
        "parent_session_inventory_after": sessions_after,
        "parent_sessions_unchanged": sessions_unchanged,
        "protected_surfaces_before": protected_before,
        "protected_surfaces_after": protected_after,
        "protected_surfaces_unchanged": protected_surfaces_unchanged,
        "history_payload_detected": history_payload_detected,
        "credential_like_output_detected": credential_like_output_detected,
        "credential_handling": "cli_internal_only_uninspected",
        "probe_script_read_copied_or_printed_credentials": False,
        "live_profile_mutated": False,
        "external_action_authorized": False,
    }
    _write_json(probe_root / "probe-receipt.json", receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument(
        "--auth-mode",
        choices=("empty-child-home", "parent-home"),
        default="empty-child-home",
    )
    args = parser.parse_args()
    receipt = run_probe(args.root, auth_mode=args.auth_mode)
    receipt_path = args.root.resolve() / "probe-receipt.json"
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "auth_mode": receipt["auth_mode"],
                "receipt_path": str(receipt_path),
                "receipt_sha256": _sha256(receipt_path),
                "returncode": receipt["returncode"],
                "parent_sessions_unchanged": receipt["parent_sessions_unchanged"],
                "protected_surfaces_unchanged": receipt[
                    "protected_surfaces_unchanged"
                ],
                "history_payload_detected": receipt["history_payload_detected"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
