"""Installed PaperSpine v1 product launcher for one explicit local profile."""

from __future__ import annotations

import importlib.metadata
import json
import os
import platform
import sys
from pathlib import Path
from typing import Any

try:
    from .suite_release import verify_bundle
except ImportError:
    from suite_release import verify_bundle  # type: ignore


class ProductRuntimeError(RuntimeError):
    pass


PRODUCT_RUNTIME_REVISION = 5


def application_root(install: Path) -> Path:
    """Support the suite layout and an app-wrapped installation equally."""
    return install / "app" if (install / "app" / "03_联合开发").is_dir() else install


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProductRuntimeError(f"PaperSpine installation metadata is unreadable: {path}") from exc
    if not isinstance(value, dict):
        raise ProductRuntimeError("PaperSpine installation metadata must be an object")
    return value


def active_install(profile_root: str | Path) -> tuple[Path, dict[str, Any]]:
    profile = Path(profile_root).resolve()
    state = _read_json(profile / ".paperspine5-lifecycle" / "profile-state.json")
    build_id = state.get("active_build_id")
    entries = [item for item in state.get("enabled_entries", []) if item.get("enabled")]
    if not build_id or len(entries) != 1 or entries[0].get("build_id") != build_id:
        raise ProductRuntimeError("PaperSpine is not installed or its activation is incomplete")
    install = Path(str(entries[0].get("install_root", ""))).resolve()
    expected = (profile / ".paperspine5-lifecycle" / "installs" / str(build_id)).resolve()
    if install != expected:
        raise ProductRuntimeError("PaperSpine activation points outside this profile")
    verified = verify_bundle(install)
    if verified["build_id"] != build_id:
        raise ProductRuntimeError("PaperSpine installed bytes do not match the active version")
    return install, verified


def _current_platform_id() -> str:
    machine = platform.machine().lower()
    if os.name == "nt" and machine in {"amd64", "x86_64"}:
        return "windows-amd64"
    if sys.platform.startswith("linux") and machine in {"amd64", "x86_64"}:
        return "linux-x86_64"
    if sys.platform == "darwin" and machine in {"arm64", "aarch64"}:
        return "macos-arm64"
    if sys.platform == "darwin" and machine in {"amd64", "x86_64"}:
        return "macos-x86_64"
    raise ProductRuntimeError(f"Unsupported PaperSpine runtime platform: {sys.platform}/{machine}")


def runtime_executable(install: Path) -> Path:
    lock = _read_json(install / "runtime_vendor" / "requirements.lock.json")
    relative = str(lock.get("python_executable") or "runtime_vendor/windows-py312/python.exe")
    executable = (install / Path(relative)).resolve()
    try:
        executable.relative_to(install.resolve())
    except ValueError as exc:
        raise ProductRuntimeError("PaperSpine runtime executable escapes the installation") from exc
    if not executable.is_file():
        raise ProductRuntimeError(f"PaperSpine runtime executable is missing: {relative}")
    return executable


def _enable_vendored_runtime(install: Path) -> dict[str, Any]:
    lock = _read_json(install / "runtime_vendor" / "requirements.lock.json")
    expected_platform = str(lock.get("platform") or "windows-amd64")
    current_platform = _current_platform_id()
    if current_platform != expected_platform:
        raise ProductRuntimeError(
            f"PaperSpine suite platform mismatch: package={expected_platform}, current={current_platform}"
        )
    if sys.version_info[:2] != (3, 12):
        raise ProductRuntimeError("PaperSpine requires its packaged Python 3.12 runtime")
    runtime_executable(install)
    runtime_root = str(lock.get("runtime_root") or "windows-py312")
    vendor = install / "runtime_vendor" / runtime_root
    if not vendor.is_dir():
        raise ProductRuntimeError("PaperSpine runtime dependencies are missing")
    if expected_platform == "windows-amd64":
        sys.path[:0] = [str(vendor), str(vendor / "win32"), str(vendor / "win32" / "lib"), str(vendor / "pythonwin")]
        if hasattr(os, "add_dll_directory"):
            globals()["_PYWIN32_DLL_HANDLE"] = os.add_dll_directory(str(vendor / "pywin32_system32"))
    version = importlib.metadata.version("mcp")
    if version != "0.0.1.dev1+d060b36" or lock.get("mcp_sdk_line") != "v2":
        raise ProductRuntimeError("PaperSpine MCP v2 runtime identity does not match its lock")
    for requirement in lock["packages"]:
        name, expected = requirement.split("==", 1)
        if importlib.metadata.version(name) != expected:
            raise ProductRuntimeError(f"PaperSpine dependency does not match its lock: {name}")
    return lock


def migrate_profile(profile_root: str | Path, install: Path, build_id: str) -> dict[str, Any]:
    profile = Path(profile_root).resolve()
    data = profile / "data"
    data.mkdir(parents=True, exist_ok=True)
    config_path = data / "product-config.json"
    previous = _read_json(config_path) if config_path.is_file() else {}
    schema = int(previous.get("schema_version", 0))
    if schema not in {0, 1}:
        raise ProductRuntimeError("PaperSpine data configuration is newer than this product")
    # The Web launcher used ``profile/user`` before suite installation.  Do not
    # strand those task bytes by creating a fresh ``profile/data/tasks`` root.
    legacy_root = profile / "user"
    fresh_root = data / "tasks"
    def has_tasks(root: Path) -> bool:
        task_dir = root / "tasks"
        return task_dir.is_dir() and any(path.is_dir() for path in task_dir.iterdir())
    legacy_has_tasks = has_tasks(legacy_root)
    fresh_has_tasks = has_tasks(fresh_root)
    if legacy_has_tasks and fresh_has_tasks:
        raise ProductRuntimeError("Both the retained Web task root and the suite task root contain tasks; select a verified profile before startup")
    if legacy_has_tasks:
        old_database = legacy_root / "registry" / "application.sqlite3"
        if not old_database.is_file():
            raise ProductRuntimeError("Retained Web task files exist but their registry database is missing; the original profile must be recovered")
        user_data_root = legacy_root
        domain_database = old_database
    else:
        user_data_root = Path(str(previous.get("user_data_root") or fresh_root)).expanduser().resolve()
        domain_database = Path(str(previous.get("domain_database") or data / "domain-events.sqlite3")).expanduser().resolve()
        # A broken earlier installation may have recorded this new empty root;
        # preserve it when there is no populated legacy root to restore.
        user_data_root.mkdir(parents=True, exist_ok=True)
    config = {
        **previous,
        "contract": "paperspine5.product-profile/1.0",
        "schema_version": 1,
        "active_build_id": build_id,
        "user_data_root": str(user_data_root),
        "domain_database": str(domain_database),
    }
    temporary = config_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, config_path)
    return config


def prepare(profile_root: str | Path) -> dict[str, Any]:
    install, verified = active_install(profile_root)
    lock = _enable_vendored_runtime(install)
    config = migrate_profile(profile_root, install, verified["build_id"])
    app = application_root(install)
    source = app / "03_联合开发" / "src"
    sys.path.insert(0, str(source))
    from paperspine_figure_integration.p2_facades import build_application

    service, kernel = build_application(
        user_data_root=config["user_data_root"],
        core_root=install,
        domain_database=config["domain_database"],
        contracts_root=app / "03_联合开发" / "contracts",
    )
    kernel.close()
    return {
        "status": "READY",
        "build_id": verified["build_id"],
        "profile_root": str(Path(profile_root).resolve()),
        "install_root": str(install),
        "user_data_root": config["user_data_root"],
        "domain_database": config["domain_database"],
        "mcp_sdk_line": lock["mcp_sdk_line"],
        "mcp_version": importlib.metadata.version("mcp"),
        "external_action_authorized": False,
    }


def serve(profile_root: str | Path, mode: str, *, principal_id: str, session_id: str,
          reviewer_id: str | None, port: int) -> None:
    ready = prepare(profile_root)
    install = Path(ready["install_root"])
    config = _read_json(Path(profile_root).resolve() / "data" / "product-config.json")
    app = application_root(install)
    sys.path.insert(0, str(app / "03_联合开发" / "src"))
    from paperspine_figure_integration.p2_facades import build_application, create_business_server, create_mcp_server

    service, kernel = build_application(
        user_data_root=config["user_data_root"], core_root=install,
        domain_database=config["domain_database"],
        contracts_root=app / "03_联合开发" / "contracts",
    )
    try:
        if mode == "mcp-stdio":
            create_mcp_server(service, principal_id=principal_id, reviewer_id=reviewer_id).run()
        elif mode == "business-http":
            if reviewer_id is not None:
                raise ProductRuntimeError("reviewer HTTP access requires a credential-bound reviewer launcher")
            server = create_business_server(service, principal_id=principal_id,
                                            session_id=session_id, port=port)
            print(json.dumps({**ready, "port": server.server_port}, ensure_ascii=False), flush=True)
            server.serve_forever()
        else:
            raise ProductRuntimeError("mode must be mcp-stdio or business-http")
    finally:
        kernel.close()
