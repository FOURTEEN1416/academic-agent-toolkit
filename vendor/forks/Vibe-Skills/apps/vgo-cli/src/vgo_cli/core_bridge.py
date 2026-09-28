from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Sequence

from .process import invoke_python_core
from .workspace import extend_workspace_package_path


def run_installer_core(repo_root: Path, argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    extend_workspace_package_path(repo_root)
    from vgo_installer.install_runtime import main as installer_main

    return invoke_python_core(installer_main, list(argv))


def run_uninstaller_core(repo_root: Path, argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    extend_workspace_package_path(repo_root)
    from vgo_installer.uninstall_runtime import main as uninstaller_main

    return invoke_python_core(uninstaller_main, list(argv))


def run_router_core(repo_root: Path, argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    extend_workspace_package_path(repo_root)
    from vgo_runtime.runtime_bridge import main as router_main

    return invoke_python_core(router_main, list(argv))


def run_canonical_entry_core(repo_root: Path, argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    extend_workspace_package_path(repo_root)
    from vgo_runtime.canonical_entry import main as canonical_entry_main

    return invoke_python_core(canonical_entry_main, list(argv))


def run_skill_index_core(repo_root: Path, argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    extend_workspace_package_path(repo_root)
    from vgo_runtime.kernel.skill_index import main as skill_index_main

    return invoke_python_core(skill_index_main, list(argv))


def run_local_kernel_core(repo_root: Path, argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    extend_workspace_package_path(repo_root)
    from vgo_runtime.kernel.loop import main as local_kernel_main

    return invoke_python_core(local_kernel_main, list(argv))


def run_inspect_run_core(repo_root: Path, argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    extend_workspace_package_path(repo_root)
    from vgo_runtime.kernel.loop import inspect_main as inspect_run_main

    return invoke_python_core(inspect_run_main, list(argv))


def run_entry_locator_core(repo_root: Path, argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    extend_workspace_package_path(repo_root)
    from vgo_runtime.entry_locator import main as entry_locator_main

    return invoke_python_core(entry_locator_main, list(argv))


def run_compatibility_exit_core(repo_root: Path, argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    extend_workspace_package_path(repo_root)
    from vgo_runtime.compatibility_exit import main as compatibility_exit_main

    return invoke_python_core(compatibility_exit_main, list(argv))
