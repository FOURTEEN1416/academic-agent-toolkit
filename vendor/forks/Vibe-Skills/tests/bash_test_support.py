from __future__ import annotations

from functools import lru_cache
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_path_tool(tool_name: str, flag: str, path: Path) -> str | None:
    tool = shutil.which(tool_name)
    if not tool:
        return None

    try:
        converted = subprocess.run(
            [tool, flag, str(path.resolve())],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None

    value = converted.stdout.strip()
    return value or None


def _path_looks_like_wsl_bash(path: str) -> bool:
    normalized = path.replace("/", "\\").lower()
    return normalized.endswith("\\windows\\system32\\bash.exe") or normalized.endswith("\\windowsapps\\bash.exe")


def _where_bash_candidates() -> list[str]:
    where = shutil.which("where.exe")
    if not where:
        return []

    try:
        completed = subprocess.run(
            [where, "bash"],
            check=True,
            capture_output=True,
            text=True,
            errors="replace",
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return []

    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


@lru_cache(maxsize=1)
def resolve_bash_for_tests() -> str | None:
    bash = shutil.which("bash") or shutil.which("bash.exe")
    if bash and not _path_looks_like_wsl_bash(bash):
        return bash

    for candidate in _where_bash_candidates():
        if not _path_looks_like_wsl_bash(candidate):
            return candidate
    return bash


def bash_looks_like_wsl() -> bool:
    bash = resolve_bash_for_tests()
    return bool(bash and _path_looks_like_wsl_bash(bash))


def to_bash_path(path: Path) -> str:
    resolved_path = path.resolve()
    resolved = str(resolved_path).replace("\\", "/")
    if len(resolved) >= 3 and resolved[1:3] == ":/":
        if not bash_looks_like_wsl():
            converted = _run_path_tool("cygpath", "-u", resolved_path) or _run_path_tool(
                "wslpath",
                "-u",
                resolved_path,
            )
            if converted:
                return converted
        return f"/mnt/{resolved[0].lower()}/{resolved[3:]}"
    return resolved


def capture_text_kwargs() -> dict[str, object]:
    return {
        "capture_output": True,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
    }


def _is_windows_absolute_path_text(value: Any) -> bool:
    text = str(value)
    return len(text) >= 3 and text[1] == ":" and text[2] in {"\\", "/"}


def _normalize_windows_bash_path_arg(value: Any) -> str:
    text = str(value)
    converted = to_bash_path(Path(text))
    if text.endswith(("\\", "/")) and not converted.endswith("/"):
        return converted + "/"
    return converted


def _is_bash_command(value: Any) -> bool:
    leaf = Path(str(value).replace("/", "\\")).name.casefold()
    return leaf in {"bash", "bash.exe"}


def is_bash_command_args(args: Any) -> bool:
    return isinstance(args, (list, tuple)) and bool(args) and _is_bash_command(args[0])


def normalize_bash_command_args(args: Any) -> Any:
    if is_bash_command_args(args):
        command = resolve_bash_for_tests() or args[0]
        normalized = [command] + [
            _normalize_windows_bash_path_arg(arg) if _is_windows_absolute_path_text(arg) else arg
            for arg in args[1:]
        ]
        return normalized if isinstance(args, list) else tuple(normalized)
    return args


@lru_cache(maxsize=1)
def ensure_bash_test_python_bin() -> Path | None:
    python_exe = Path(sys.executable).resolve()
    if not python_exe.exists():
        return None

    bin_dir = REPO_ROOT / ".tmp" / "bash-test-bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    python_posix = to_bash_path(python_exe)
    for name in ("python3", "python"):
        launcher = bin_dir / name
        launcher.write_text(f'#!/bin/sh\nexec "{python_posix}" "$@"\n', encoding="utf-8")
        launcher.chmod(0o755)
    return bin_dir


def _has_explicit_python_path_override(path_value: str) -> bool:
    original_path = os.environ.get("PATH", "")
    if not original_path or not path_value.endswith(original_path):
        return False

    prefix = path_value[: -len(original_path)].rstrip(";:")
    if not prefix:
        return False

    candidates = [prefix]
    if ";" in prefix:
        candidates = [part for part in prefix.split(";") if part]

    for candidate in candidates:
        root = Path(candidate)
        if any((root / name).exists() for name in ("python3", "python3.exe", "python", "python.exe")):
            return True
    return False


def bash_test_env(base_env: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ if base_env is None else base_env)
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    if base_env is not None and _has_explicit_python_path_override(env.get("PATH", "")):
        return env

    bin_dir = ensure_bash_test_python_bin()
    if bin_dir is None:
        return env

    current_path = env.get("PATH", "")
    env["PATH"] = str(bin_dir) + (os.pathsep + current_path if current_path else "")
    return env
