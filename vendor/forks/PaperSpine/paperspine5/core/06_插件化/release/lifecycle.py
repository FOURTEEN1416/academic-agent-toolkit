"""Transactional local-profile lifecycle candidate for exact PaperSpine5 bundles.

This module intentionally operates only on an explicitly supplied profile root.
It does not know the user's real Codex marketplace and does not execute Codex
installation commands.  The profile contract is a local acceptance harness for
install/update/reload-marker/rollback/uninstall semantics.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from contextlib import AbstractContextManager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:  # Installed bundle and direct-script use.
    from .suite_release import (
        PRODUCT_ID,
        ReleaseError,
        canonical_json_bytes,
        extract_verified_bundle,
        sha256_file,
        verify_bundle,
    )
except ImportError:  # pragma: no cover - exercised by CLI script mode.
    from suite_release import (  # type: ignore
        PRODUCT_ID,
        ReleaseError,
        canonical_json_bytes,
        extract_verified_bundle,
        sha256_file,
        verify_bundle,
    )


PROFILE_CONTRACT = "paperspine5.local-profile-state"
PROFILE_SCHEMA_VERSION = "1.0"
RECEIPT_CONTRACT = "paperspine5.lifecycle-receipt"
RECEIPT_SCHEMA_VERSION = "1.0"
DOCTOR_CONTRACT = "paperspine5.doctor-report"
DOCTOR_SCHEMA_VERSION = "1.0"
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class LifecycleError(RuntimeError):
    """A lifecycle contract error that cannot be represented as a mutation."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _request_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def _safe_id(value: str, field: str) -> str:
    if not isinstance(value, str) or not SAFE_ID.fullmatch(value):
        raise LifecycleError(f"{field} must be a safe non-empty identifier")
    return value


def _profile_root(value: str | Path) -> Path:
    if value is None or not str(value).strip():
        raise LifecycleError("profile_root must be supplied explicitly")
    root = Path(value).resolve()
    if root == Path(root.anchor):
        raise LifecycleError("profile_root cannot be a filesystem root")
    return root


def _paths(profile_root: str | Path) -> dict[str, Path]:
    profile = _profile_root(profile_root)
    control = profile / ".paperspine5-lifecycle"
    return {
        "profile": profile,
        "control": control,
        "state": control / "profile-state.json",
        "installs": control / "installs",
        "staging": control / "staging",
        "quarantine": control / "quarantine",
        "snapshots": control / "snapshots",
        "receipts": control / "receipts",
        "lock": control / "transaction.lock",
        "reload": control / "reload-required.json",
        "reload_ack": control / "reload-ack.json",
        "discovery": profile / "discovery" / "paperspine5.json",
        "data": profile / "data",
    }


def _ensure_control(paths: dict[str, Path]) -> None:
    paths["profile"].mkdir(parents=True, exist_ok=True)
    for key in ("control", "installs", "staging", "quarantine", "snapshots", "receipts"):
        paths[key].mkdir(parents=True, exist_ok=True)


def _write_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(canonical_json_bytes(payload))
    os.replace(temporary, path)


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LifecycleError(f"profile JSON is unreadable: {path}") from exc
    if not isinstance(payload, dict):
        raise LifecycleError(f"profile JSON root must be an object: {path}")
    return payload


def _default_state() -> dict[str, Any]:
    return {
        "contract": PROFILE_CONTRACT,
        "schema_version": PROFILE_SCHEMA_VERSION,
        "product_id": PRODUCT_ID,
        "active_build_id": None,
        "enabled_entries": [],
        "history": [],
        "data_schema": {},
        "suite_object": None,
        "update_target": None,
        "last_operation_id": None,
    }


def _state(paths: dict[str, Path]) -> dict[str, Any]:
    payload = _read_json(paths["state"])
    if payload is None:
        return _default_state()
    if payload.get("contract") != PROFILE_CONTRACT or payload.get("schema_version") != PROFILE_SCHEMA_VERSION:
        raise LifecycleError("profile state contract/version is unsupported")
    if payload.get("product_id") != PRODUCT_ID:
        raise LifecycleError("profile state belongs to a different product")
    return payload


def _tree_digest(root: Path) -> str | None:
    if not root.is_dir():
        return None
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix().encode("utf-8")
        content = path.read_bytes()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def _inventory(paths: dict[str, Path], state: dict[str, Any] | None = None) -> dict[str, Any]:
    current = state or _state(paths)
    installs = sorted(path.name for path in paths["installs"].iterdir() if path.is_dir()) if paths["installs"].is_dir() else []
    staging = sorted(path.name for path in paths["staging"].iterdir()) if paths["staging"].is_dir() else []
    quarantine = sorted(path.name for path in paths["quarantine"].iterdir()) if paths["quarantine"].is_dir() else []
    return {
        "active_build_id": current.get("active_build_id"),
        "enabled_entries": current.get("enabled_entries", []),
        "install_builds": installs,
        "staging_entries": staging,
        "quarantine_entries": quarantine,
        "installs_sha256": _tree_digest(paths["installs"]),
        "staging_sha256": _tree_digest(paths["staging"]),
        "discovery_present": paths["discovery"].is_file(),
        "reload_required": paths["reload"].is_file(),
        "transaction_lock_present": paths["lock"].is_file(),
        "data_present": paths["data"].exists(),
        "data_sha256": _tree_digest(paths["data"]),
    }


def _version_tuple(value: Any) -> tuple[int, ...]:
    if not isinstance(value, str) or not value or any(not part.isdigit() for part in value.split(".")):
        raise LifecycleError(f"schema version is not numeric dotted text: {value!r}")
    return tuple(int(part) for part in value.split("."))


def _in_range(value: str, minimum: str, maximum: str) -> bool:
    item = _version_tuple(value)
    return _version_tuple(minimum) <= item <= _version_tuple(maximum)


def _compatibility_blockers(state: dict[str, Any], manifest: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    current = state.get("data_schema") or {}
    readers = manifest.get("reader_compatibility") or {}
    mappings = {
        "state_repository": "state_repository",
        "integration_state": "integration_state",
        "integration_job": "integration_job",
    }
    for data_key, reader_key in mappings.items():
        version = current.get(data_key)
        if version is None:
            continue
        allowed = readers.get(reader_key)
        if not isinstance(allowed, dict):
            blockers.append({"code": "READER_RANGE_MISSING", "subject": data_key, "version": version})
            continue
        try:
            compatible = _in_range(version, allowed.get("min"), allowed.get("max"))
        except LifecycleError:
            compatible = False
        if not compatible:
            blockers.append(
                {
                    "code": "SCHEMA_INCOMPATIBLE",
                    "subject": data_key,
                    "current": version,
                    "candidate_min": allowed.get("min"),
                    "candidate_max": allowed.get("max"),
                }
            )
    return blockers


def doctor(
    profile_root: str | Path,
    *,
    bundle: str | Path | None = None,
    _ignore_transaction_lock: bool = False,
    _ignore_quarantine_operation: str | None = None,
) -> dict[str, Any]:
    """Read-only inventory and integrity/compatibility report."""
    paths = _paths(profile_root)
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    try:
        state = _state(paths)
    except LifecycleError as exc:
        state = _default_state()
        blockers.append({"code": "PROFILE_STATE_INVALID", "message": str(exc)})
    inventory = _inventory(paths, state)
    enabled = [entry for entry in state.get("enabled_entries", []) if isinstance(entry, dict) and entry.get("enabled") is True]
    if len(enabled) > 1:
        blockers.append({"code": "DOUBLE_ENABLED", "count": len(enabled)})
    active_build = state.get("active_build_id")
    active_verification: dict[str, Any] | None = None
    active_root: Path | None = None
    if active_build:
        matching = [
            entry
            for entry in enabled
            if entry.get("plugin_id") == PRODUCT_ID and entry.get("build_id") == active_build
        ]
        if len(enabled) != 1:
            blockers.append({"code": "ACTIVE_DISCOVERY_COUNT_INVALID", "count": len(enabled)})
        if len(matching) != 1:
            blockers.append({"code": "WRONG_SUITE_OBJECT", "entries": enabled})
        else:
            entry = matching[0]
            try:
                active_root = Path(str(entry.get("install_root"))).resolve()
                active_root.relative_to(paths["installs"].resolve())
            except (ValueError, OSError):
                blockers.append({"code": "WRONG_INSTALL_ROOT", "install_root": entry.get("install_root")})
                active_root = None
            if active_root is not None:
                try:
                    active_verification = verify_bundle(active_root)
                except (ReleaseError, OSError) as exc:
                    blockers.append({"code": "INSTALLED_TAMPER_OR_INCOMPLETE", "message": str(exc)})
                else:
                    if active_verification.get("build_id") != active_build:
                        blockers.append({"code": "ACTIVE_BUILD_MISMATCH"})
        discovery = None
        try:
            discovery = _read_json(paths["discovery"])
        except LifecycleError as exc:
            blockers.append({"code": "DISCOVERY_INVALID", "message": str(exc)})
        if discovery is None:
            blockers.append({"code": "DISCOVERY_MISSING"})
        elif (
            discovery.get("plugin_id") != PRODUCT_ID
            or discovery.get("build_id") != active_build
            or (active_root is not None and Path(str(discovery.get("install_root"))).resolve() != active_root)
        ):
            blockers.append({"code": "DISCOVERY_OBJECT_MISMATCH"})
        target = state.get("update_target")
        if not isinstance(target, dict) or (
            target.get("product_id") != PRODUCT_ID
            or target.get("build_id") != active_build
            or (active_root is not None and Path(str(target.get("install_root"))).resolve() != active_root)
        ):
            blockers.append({"code": "UPDATER_TARGET_MISMATCH"})
    else:
        if enabled:
            blockers.append({"code": "ENABLED_WITHOUT_ACTIVE", "count": len(enabled)})
        if paths["discovery"].exists():
            blockers.append({"code": "DISCOVERY_RESIDUE"})
        warnings.append({"code": "NOT_INSTALLED"})
    if inventory["staging_entries"]:
        blockers.append({"code": "STAGING_RESIDUE", "entries": inventory["staging_entries"]})
    quarantine_residue = [
        item for item in inventory["quarantine_entries"] if item != _ignore_quarantine_operation
    ]
    if quarantine_residue:
        blockers.append({"code": "QUARANTINE_RESIDUE", "entries": quarantine_residue})
    if inventory["transaction_lock_present"] and not _ignore_transaction_lock:
        blockers.append({"code": "TRANSACTION_RESIDUE"})
    allowed_installs = {str(active_build)} if active_build else set()
    for item in state.get("history", []):
        if isinstance(item, dict) and isinstance(item.get("build_id"), str):
            allowed_installs.add(item["build_id"])
    residues = sorted(set(inventory["install_builds"]) - allowed_installs)
    if residues:
        blockers.append({"code": "INSTALL_RESIDUE", "builds": residues})
    if paths["reload"].is_file():
        warnings.append({"code": "RELOAD_REQUIRED"})
    candidate: dict[str, Any] | None = None
    if bundle is not None:
        try:
            candidate = verify_bundle(bundle)
        except (ReleaseError, OSError) as exc:
            blockers.append({"code": "CANDIDATE_INVALID", "message": str(exc)})
        else:
            blockers.extend(_compatibility_blockers(state, candidate["manifest"]))
    suite = active_verification["manifest"]["suite"] if active_verification else None
    claim = active_verification["manifest"]["claim_ceiling"] if active_verification else None
    return {
        "contract": DOCTOR_CONTRACT,
        "schema_version": DOCTOR_SCHEMA_VERSION,
        "status": "PASS" if not blockers else "BLOCKED",
        "profile_root": str(paths["profile"]),
        "inventory": inventory,
        "suite": suite,
        "components": active_verification["manifest"]["components"] if active_verification else None,
        "state": active_verification["manifest"]["state"] if active_verification else state.get("data_schema"),
        "workflow": active_verification["manifest"]["workflow"] if active_verification else None,
        "reader_compatibility": active_verification["manifest"]["reader_compatibility"] if active_verification else None,
        "api": active_verification["manifest"]["api"] if active_verification else None,
        "claim_ceiling": claim,
        "candidate_build_id": candidate.get("build_id") if candidate else None,
        "blockers": blockers,
        "warnings": warnings,
        "external_action_authorized": False,
    }


class _ProfileLock(AbstractContextManager["_ProfileLock"]):
    def __init__(self, paths: dict[str, Path], operation_id: str) -> None:
        self.paths = paths
        self.operation_id = operation_id
        self.handle: int | None = None

    def __enter__(self) -> "_ProfileLock":
        _ensure_control(self.paths)
        try:
            self.handle = os.open(self.paths["lock"], os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise LifecycleError("another lifecycle transaction or stale lock is present") from exc
        os.write(self.handle, canonical_json_bytes({"operation_id": self.operation_id, "created_at": _now()}))
        os.close(self.handle)
        self.handle = None
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if self.handle is not None:
            os.close(self.handle)
        try:
            self.paths["lock"].unlink()
        except FileNotFoundError:
            pass


class LifecycleManager:
    def __init__(self, profile_root: str | Path) -> None:
        self.paths = _paths(profile_root)
        _ensure_control(self.paths)

    def _receipt_path(self, operation_id: str) -> Path:
        return self.paths["receipts"] / f"{_safe_id(operation_id, 'operation_id')}.json"

    def _existing_receipt(self, operation_id: str, request_hash: str) -> dict[str, Any] | None:
        existing = _read_json(self._receipt_path(operation_id))
        if existing is None:
            return None
        if existing.get("request_sha256") != request_hash:
            raise LifecycleError("operation_id was already used for a different lifecycle request")
        return {**existing, "replayed": True}

    def _write_receipt(self, receipt: dict[str, Any]) -> dict[str, Any]:
        _write_atomic(self._receipt_path(receipt["operation_id"]), receipt)
        return receipt

    def _snapshot(self, operation_id: str) -> tuple[Path, dict[str, Any]]:
        state = _read_json(self.paths["state"])
        discovery = _read_json(self.paths["discovery"])
        reload_marker = _read_json(self.paths["reload"])
        snapshot = {
            "contract": "paperspine5.lifecycle-snapshot",
            "schema_version": "1.0",
            "operation_id": operation_id,
            "state": state,
            "discovery": discovery,
            "reload_marker": reload_marker,
            "inventory": _inventory(self.paths, state or _default_state()),
            "data_sha256": _tree_digest(self.paths["data"]),
        }
        root = self.paths["snapshots"] / operation_id
        root.mkdir(parents=True, exist_ok=False)
        path = root / "pre-snapshot.json"
        _write_atomic(path, snapshot)
        return path, snapshot

    def _restore_snapshot(self, snapshot: dict[str, Any]) -> None:
        for key, value in (
            ("state", snapshot.get("state")),
            ("discovery", snapshot.get("discovery")),
            ("reload", snapshot.get("reload_marker")),
        ):
            path = self.paths[key]
            if value is None:
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass
            else:
                _write_atomic(path, value)

    def _remove_control_tree(self, path: Path) -> None:
        resolved = path.resolve()
        control = self.paths["control"].resolve()
        try:
            resolved.relative_to(control)
        except ValueError as exc:
            raise LifecycleError(f"refusing to remove path outside lifecycle control root: {resolved}") from exc
        if resolved == control:
            raise LifecycleError("refusing to remove the lifecycle control root")
        if resolved.is_dir():
            shutil.rmtree(resolved)
        elif resolved.exists():
            resolved.unlink()

    def _base_receipt(
        self,
        *,
        operation: str,
        operation_id: str,
        request_hash: str,
        snapshot_path: Path,
        before: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "contract": RECEIPT_CONTRACT,
            "schema_version": RECEIPT_SCHEMA_VERSION,
            "operation": operation,
            "operation_id": operation_id,
            "request_sha256": request_hash,
            "status": "blocked",
            "recorded_at": _now(),
            "profile_root": str(self.paths["profile"]),
            "pre_snapshot": {
                "path": str(snapshot_path),
                "sha256": sha256_file(snapshot_path),
                "inventory": before,
            },
            "before_active_build_id": before.get("active_build_id"),
            "after_active_build_id": before.get("active_build_id"),
            "rollback_performed": False,
            "blockers": [],
            "removed": [],
            "data_retained": True,
            "replayed": False,
            "external_action_authorized": False,
        }

    def install(
        self,
        bundle: str | Path,
        *,
        operation_id: str,
        fault_at: str | None = None,
    ) -> dict[str, Any]:
        return self._activate("install", bundle, operation_id=operation_id, confirmed=True, fault_at=fault_at)

    def update(
        self,
        bundle: str | Path,
        *,
        operation_id: str,
        confirmed: bool,
        fault_at: str | None = None,
    ) -> dict[str, Any]:
        return self._activate("update", bundle, operation_id=operation_id, confirmed=confirmed, fault_at=fault_at)

    def _activate(
        self,
        operation: str,
        bundle: str | Path,
        *,
        operation_id: str,
        confirmed: bool,
        fault_at: str | None,
    ) -> dict[str, Any]:
        operation_id = _safe_id(operation_id, "operation_id")
        bundle_path = Path(bundle).resolve()
        candidate = verify_bundle(bundle_path)
        request = {
            "operation": operation,
            "operation_id": operation_id,
            "bundle_build_id": candidate["build_id"],
            "bundle_content_index": candidate["content_index_sha256"],
            "confirmed": confirmed,
        }
        request_hash = _request_hash(request)
        replay = self._existing_receipt(operation_id, request_hash)
        if replay is not None:
            return replay
        with _ProfileLock(self.paths, operation_id):
            snapshot_path, snapshot = self._snapshot(operation_id)
            state = snapshot.get("state") or _default_state()
            before = snapshot["inventory"]
            receipt = self._base_receipt(
                operation=operation,
                operation_id=operation_id,
                request_hash=request_hash,
                snapshot_path=snapshot_path,
                before=before,
            )
            receipt["candidate_build_id"] = candidate["build_id"]
            receipt["candidate_content_index_sha256"] = candidate["content_index_sha256"]
            active = state.get("active_build_id")
            if operation == "install" and active:
                receipt["blockers"] = [{"code": "INSTALL_ACTIVE_EXISTS", "active_build_id": active}]
                return self._write_receipt(receipt)
            if operation == "update" and not active:
                receipt["blockers"] = [{"code": "UPDATE_REQUIRES_ACTIVE_INSTALL"}]
                return self._write_receipt(receipt)
            if operation == "update" and not confirmed:
                receipt["blockers"] = [{"code": "UPDATE_CONFIRMATION_REQUIRED"}]
                return self._write_receipt(receipt)
            compatibility = _compatibility_blockers(state, candidate["manifest"])
            if compatibility:
                receipt["blockers"] = compatibility
                return self._write_receipt(receipt)
            pre_doctor = doctor(self.paths["profile"], _ignore_transaction_lock=True)
            allowed_pre_blockers = {"DISCOVERY_RESIDUE"} if operation == "install" and not active else set()
            serious = [item for item in pre_doctor["blockers"] if item.get("code") not in allowed_pre_blockers]
            if serious:
                receipt["blockers"] = [{"code": "PROFILE_PREFLIGHT_BLOCKED", "details": serious}]
                return self._write_receipt(receipt)
            build_id = candidate["build_id"]
            target = self.paths["installs"] / build_id
            stage = self.paths["staging"] / operation_id
            installed_new = False
            try:
                if target.exists():
                    verified_existing = verify_bundle(target)
                    if verified_existing["content_index_sha256"] != candidate["content_index_sha256"]:
                        raise LifecycleError("existing build directory differs from candidate bytes")
                else:
                    stage_bundle = stage / "bundle"
                    stage.mkdir(parents=True, exist_ok=False)
                    extract_verified_bundle(bundle_path, stage_bundle)
                    if fault_at == "after_stage":
                        raise LifecycleError("injected failure after staging")
                    os.replace(stage_bundle, target)
                    installed_new = True
                    self._remove_control_tree(stage)
                if fault_at == "after_install":
                    raise LifecycleError("injected failure after install placement")
                if (target / "release" / "product_probe.py").is_file():
                    try:
                        from .product_probe import probe_install
                    except ImportError:
                        from product_probe import probe_install
                    receipt["runtime_readiness"] = probe_install(target, self.paths["profile"])
                if fault_at == "after_probe":
                    raise LifecycleError("injected failure before activation")
                history = [item for item in state.get("history", []) if isinstance(item, dict)]
                if active and all(item.get("build_id") != active for item in history):
                    old_entry = next(
                        (item for item in state.get("enabled_entries", []) if item.get("build_id") == active),
                        None,
                    )
                    history.append(
                        {
                            "build_id": active,
                            "install_root": old_entry.get("install_root") if isinstance(old_entry, dict) else str(self.paths["installs"] / str(active)),
                        }
                    )
                entry = {
                    "plugin_id": PRODUCT_ID,
                    "build_id": build_id,
                    "install_root": str(target.resolve()),
                    "enabled": True,
                    "source": "transactional-local-candidate",
                }
                data_schema = dict(state.get("data_schema") or {})
                if not data_schema:
                    manifest_state = candidate["manifest"]["state"]
                    data_schema = {
                        "state_repository": manifest_state["repository"]["writer"],
                        "integration_state": manifest_state["integration_state"]["writer"],
                        "integration_job": manifest_state["integration_job"]["writer"],
                    }
                next_state = {
                    **state,
                    "contract": PROFILE_CONTRACT,
                    "schema_version": PROFILE_SCHEMA_VERSION,
                    "product_id": PRODUCT_ID,
                    "active_build_id": build_id,
                    "enabled_entries": [entry],
                    "history": history,
                    "data_schema": data_schema,
                    "suite_object": {
                        "product_id": PRODUCT_ID,
                        "product_version": candidate["product_version"],
                        "build_id": build_id,
                        "content_index_sha256": candidate["content_index_sha256"],
                    },
                    "update_target": {
                        "product_id": PRODUCT_ID,
                        "build_id": build_id,
                        "install_root": str(target.resolve()),
                    },
                    "last_operation_id": operation_id,
                }
                discovery = {
                    "contract": "paperspine5.discovery",
                    "schema_version": "1.0",
                    "plugin_id": PRODUCT_ID,
                    "build_id": build_id,
                    "install_root": str(target.resolve()),
                    "enabled": True,
                }
                reload_marker = {
                    "contract": "paperspine5.reload-marker",
                    "schema_version": "1.0",
                    "operation_id": operation_id,
                    "build_id": build_id,
                    "status": "required",
                }
                _write_atomic(self.paths["state"], next_state)
                _write_atomic(self.paths["discovery"], discovery)
                _write_atomic(self.paths["reload"], reload_marker)
                if fault_at == "after_state":
                    raise LifecycleError("injected failure after activation state")
                post = doctor(self.paths["profile"], _ignore_transaction_lock=True)
                if post["blockers"]:
                    raise LifecycleError(f"post-activation doctor blocked: {post['blockers']}")
                receipt.update(
                    {
                        "status": "committed",
                        "after_active_build_id": build_id,
                        "reload_required": True,
                        "installed_root": str(target.resolve()),
                        "doctor_status": post["status"],
                    }
                )
                return self._write_receipt(receipt)
            except Exception as exc:
                self._restore_snapshot(snapshot)
                if installed_new and target.exists():
                    self._remove_control_tree(target)
                if stage.exists():
                    self._remove_control_tree(stage)
                receipt.update(
                    {
                        "status": "rolled_back",
                        "rollback_performed": True,
                        "after_active_build_id": active,
                        "blockers": [{"code": "TRANSACTION_FAILED", "message": str(exc)}],
                    }
                )
                return self._write_receipt(receipt)

    def reload(self, *, operation_id: str) -> dict[str, Any]:
        operation_id = _safe_id(operation_id, "operation_id")
        request = {"operation": "reload", "operation_id": operation_id}
        request_hash = _request_hash(request)
        replay = self._existing_receipt(operation_id, request_hash)
        if replay is not None:
            return replay
        with _ProfileLock(self.paths, operation_id):
            snapshot_path, snapshot = self._snapshot(operation_id)
            before = snapshot["inventory"]
            receipt = self._base_receipt(
                operation="reload",
                operation_id=operation_id,
                request_hash=request_hash,
                snapshot_path=snapshot_path,
                before=before,
            )
            state = snapshot.get("state") or _default_state()
            marker = snapshot.get("reload_marker")
            if not state.get("active_build_id"):
                receipt["blockers"] = [{"code": "RELOAD_REQUIRES_ACTIVE_INSTALL"}]
                return self._write_receipt(receipt)
            if not isinstance(marker, dict) or marker.get("build_id") != state.get("active_build_id"):
                receipt["blockers"] = [{"code": "RELOAD_MARKER_MISSING_OR_STALE"}]
                return self._write_receipt(receipt)
            acknowledgement = {
                "contract": "paperspine5.reload-ack",
                "schema_version": "1.0",
                "operation_id": operation_id,
                "build_id": state["active_build_id"],
                "marker_only_candidate": True,
                "service_drain_verified": False,
            }
            _write_atomic(self.paths["reload_ack"], acknowledgement)
            self.paths["reload"].unlink()
            receipt.update(
                {
                    "status": "committed",
                    "after_active_build_id": state["active_build_id"],
                    "reload_required": False,
                    "marker_only_candidate": True,
                    "service_drain_verified": False,
                }
            )
            return self._write_receipt(receipt)

    def rollback(self, target_build_id: str, *, operation_id: str) -> dict[str, Any]:
        operation_id = _safe_id(operation_id, "operation_id")
        target_build_id = _safe_id(target_build_id, "target_build_id")
        request = {"operation": "rollback", "operation_id": operation_id, "target_build_id": target_build_id}
        request_hash = _request_hash(request)
        replay = self._existing_receipt(operation_id, request_hash)
        if replay is not None:
            return replay
        with _ProfileLock(self.paths, operation_id):
            snapshot_path, snapshot = self._snapshot(operation_id)
            before = snapshot["inventory"]
            receipt = self._base_receipt(
                operation="rollback",
                operation_id=operation_id,
                request_hash=request_hash,
                snapshot_path=snapshot_path,
                before=before,
            )
            state = snapshot.get("state") or _default_state()
            current = state.get("active_build_id")
            target = self.paths["installs"] / target_build_id
            if not current:
                receipt["blockers"] = [{"code": "ROLLBACK_REQUIRES_ACTIVE_INSTALL"}]
                return self._write_receipt(receipt)
            if not target.is_dir():
                receipt["blockers"] = [{"code": "ROLLBACK_TARGET_MISSING", "target_build_id": target_build_id}]
                return self._write_receipt(receipt)
            try:
                verification = verify_bundle(target)
            except ReleaseError as exc:
                receipt["blockers"] = [{"code": "ROLLBACK_TARGET_INVALID", "message": str(exc)}]
                return self._write_receipt(receipt)
            compatibility = _compatibility_blockers(state, verification["manifest"])
            if compatibility:
                receipt["blockers"] = compatibility
                return self._write_receipt(receipt)
            if (target / "release" / "product_probe.py").is_file():
                try:
                    try:
                        from .product_probe import probe_install
                    except ImportError:
                        from product_probe import probe_install
                    receipt["runtime_readiness"] = probe_install(target, self.paths["profile"])
                except Exception as exc:
                    receipt["blockers"] = [{"code": "ROLLBACK_RUNTIME_NOT_READY", "message": str(exc)}]
                    return self._write_receipt(receipt)
            history = [item for item in state.get("history", []) if isinstance(item, dict)]
            if all(item.get("build_id") != current for item in history):
                history.append({"build_id": current, "install_root": str(self.paths["installs"] / str(current))})
            entry = {
                "plugin_id": PRODUCT_ID,
                "build_id": target_build_id,
                "install_root": str(target.resolve()),
                "enabled": True,
                "source": "transactional-local-candidate",
            }
            next_state = {
                **state,
                "active_build_id": target_build_id,
                "enabled_entries": [entry],
                "history": history,
                "suite_object": {
                    "product_id": PRODUCT_ID,
                    "product_version": verification["product_version"],
                    "build_id": target_build_id,
                    "content_index_sha256": verification["content_index_sha256"],
                },
                "update_target": {
                    "product_id": PRODUCT_ID,
                    "build_id": target_build_id,
                    "install_root": str(target.resolve()),
                },
                "last_operation_id": operation_id,
            }
            _write_atomic(self.paths["state"], next_state)
            _write_atomic(
                self.paths["discovery"],
                {
                    "contract": "paperspine5.discovery",
                    "schema_version": "1.0",
                    "plugin_id": PRODUCT_ID,
                    "build_id": target_build_id,
                    "install_root": str(target.resolve()),
                    "enabled": True,
                },
            )
            _write_atomic(
                self.paths["reload"],
                {
                    "contract": "paperspine5.reload-marker",
                    "schema_version": "1.0",
                    "operation_id": operation_id,
                    "build_id": target_build_id,
                    "status": "required",
                },
            )
            receipt.update(
                {
                    "status": "committed",
                    "after_active_build_id": target_build_id,
                    "reload_required": True,
                    "rollback_target": target_build_id,
                }
            )
            return self._write_receipt(receipt)

    def uninstall(
        self,
        *,
        operation_id: str,
        retain_data: bool = True,
        fault_at: str | None = None,
    ) -> dict[str, Any]:
        operation_id = _safe_id(operation_id, "operation_id")
        if retain_data is not True:
            raise LifecycleError("this candidate only supports the safe retain_data=true uninstall policy")
        request = {"operation": "uninstall", "operation_id": operation_id, "retain_data": True}
        request_hash = _request_hash(request)
        replay = self._existing_receipt(operation_id, request_hash)
        if replay is not None:
            return replay
        with _ProfileLock(self.paths, operation_id):
            snapshot_path, snapshot = self._snapshot(operation_id)
            before = snapshot["inventory"]
            receipt = self._base_receipt(
                operation="uninstall",
                operation_id=operation_id,
                request_hash=request_hash,
                snapshot_path=snapshot_path,
                before=before,
            )
            state = snapshot.get("state") or _default_state()
            removed: list[str] = []
            quarantine = self.paths["quarantine"] / operation_id
            quarantine_installs = quarantine / "installs"
            quarantine_staging = quarantine / "staging"
            installs_moved = False
            staging_moved = False
            try:
                if quarantine.exists():
                    raise LifecycleError("uninstall quarantine already exists")
                quarantine.mkdir(parents=True, exist_ok=False)
                removed.extend(str(child.resolve()) for child in self.paths["installs"].iterdir())
                removed.extend(str(child.resolve()) for child in self.paths["staging"].iterdir())
                os.replace(self.paths["installs"], quarantine_installs)
                installs_moved = True
                self.paths["installs"].mkdir()
                os.replace(self.paths["staging"], quarantine_staging)
                staging_moved = True
                self.paths["staging"].mkdir()
                if fault_at == "after_quarantine":
                    raise LifecycleError("injected failure after uninstall quarantine")
                for key in ("reload", "reload_ack"):
                    if self.paths[key].exists():
                        removed.append(str(self.paths[key].resolve()))
                        self.paths[key].unlink()
                if self.paths["discovery"].exists():
                    removed.append(str(self.paths["discovery"].resolve()))
                    self.paths["discovery"].unlink()
                next_state = {
                    **state,
                    "active_build_id": None,
                    "enabled_entries": [],
                    "suite_object": None,
                    "update_target": None,
                    "last_operation_id": operation_id,
                }
                _write_atomic(self.paths["state"], next_state)
                if fault_at == "after_state":
                    raise LifecycleError("injected failure after uninstall state")
                post = doctor(
                    self.paths["profile"],
                    _ignore_transaction_lock=True,
                    _ignore_quarantine_operation=operation_id,
                )
                if post["blockers"]:
                    raise LifecycleError(f"post-uninstall doctor blocked: {post['blockers']}")
                if fault_at == "cleanup_failure":
                    raise OSError("injected uninstall quarantine cleanup failure")
                self._remove_control_tree(quarantine)
                receipt.update(
                    {
                        "status": "committed",
                        "after_active_build_id": None,
                        "removed": removed,
                        "data_retained": True,
                        "data_sha256": _tree_digest(self.paths["data"]),
                    }
                )
                return self._write_receipt(receipt)
            except Exception as exc:
                committed_state = _read_json(self.paths["state"])
                logical_commit = bool(
                    committed_state is not None
                    and committed_state.get("active_build_id") is None
                    and committed_state.get("last_operation_id") == operation_id
                    and fault_at == "cleanup_failure"
                )
                if logical_commit:
                    receipt.update(
                        {
                            "status": "committed_with_residue",
                            "after_active_build_id": None,
                            "rollback_performed": False,
                            "blockers": [
                                {
                                    "code": "UNINSTALL_CLEANUP_RESIDUE",
                                    "message": str(exc),
                                    "quarantine": str(quarantine.resolve()),
                                }
                            ],
                            "quarantined": removed,
                            "data_sha256": _tree_digest(self.paths["data"]),
                        }
                    )
                    return self._write_receipt(receipt)
                rollback_error: str | None = None
                try:
                    self._restore_snapshot(snapshot)
                    if installs_moved:
                        self._remove_control_tree(self.paths["installs"])
                        os.replace(quarantine_installs, self.paths["installs"])
                    if staging_moved:
                        self._remove_control_tree(self.paths["staging"])
                        os.replace(quarantine_staging, self.paths["staging"])
                    if quarantine.exists():
                        self._remove_control_tree(quarantine)
                    restored = _inventory(self.paths, snapshot.get("state") or _default_state())
                    comparable = {
                        key: value
                        for key, value in restored.items()
                        if key != "transaction_lock_present"
                    }
                    expected = {
                        key: value
                        for key, value in before.items()
                        if key != "transaction_lock_present"
                    }
                    if comparable != expected:
                        raise LifecycleError("uninstall rollback inventory/byte digest mismatch")
                except Exception as restore_exc:
                    rollback_error = str(restore_exc)
                receipt.update(
                    {
                        "status": "rollback_failed" if rollback_error else "rolled_back",
                        "rollback_performed": rollback_error is None,
                        "blockers": [
                            {"code": "UNINSTALL_FAILED", "message": str(exc)},
                            *(
                                [{"code": "UNINSTALL_ROLLBACK_FAILED", "message": rollback_error}]
                                if rollback_error
                                else []
                            ),
                        ],
                    }
                )
                return self._write_receipt(receipt)
