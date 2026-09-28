from __future__ import annotations

import os
import shutil
import subprocess
import sys

from .errors import CliError


def _load_optional_install_timeout_seconds() -> int:
    raw = os.environ.get('VGO_OPTIONAL_INSTALL_TIMEOUT_SECONDS', '15')
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 15
    return max(1, value)


OPTIONAL_INSTALL_TIMEOUT_SECONDS = _load_optional_install_timeout_seconds()


def report_external_fallback_usage(external_fallback_used: list[str], *, strict_offline: bool) -> None:
    uniq_fallback = ','.join(sorted(set(str(item) for item in external_fallback_used if str(item).strip())))
    if not uniq_fallback:
        return
    if strict_offline:
        raise CliError(f'StrictOffline rejected external fallback usage: {uniq_fallback}')
    print(f'[WARN] External fallback skills were used (non-reproducible install): {uniq_fallback}')


def _run_optional_install(command: list[str]) -> None:
    command_text = ' '.join(command)
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=OPTIONAL_INSTALL_TIMEOUT_SECONDS,
        )
    except (FileNotFoundError, OSError) as exc:
        print(f'[WARN] Optional install skipped for {command_text}: {exc}')
        return
    except subprocess.TimeoutExpired:
        print(
            f'[WARN] Optional install timed out for {command_text} after '
            f'{OPTIONAL_INSTALL_TIMEOUT_SECONDS}s; continuing without it.'
        )
        return

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or '').strip()
        suffix = f': {detail}' if detail else f' (exit {result.returncode})'
        print(f'[WARN] Optional install failed for {command_text}{suffix}')


def maybe_install_external_dependencies(repo_root: object, install_mode: str, *, strict_offline: bool = False) -> None:
    if strict_offline:
        return
    if shutil.which('npm'):
        if install_mode == 'governed':
            _run_optional_install(['npm', 'install', '-g', '@th0rgal/ralph-wiggum'])
    if shutil.which('xan') is None:
        print('[WARN] xan CLI not detected. Install manually (brew/pixi/conda/cargo) to enable large CSV acceleration.')
    ivy_probe = subprocess.run([sys.executable, '-c', 'import ivy'], capture_output=True, text=True)
    if ivy_probe.returncode != 0:
        print('[WARN] ivy Python package not detected. Install manually (pip install ivy) to enable framework-interop analyzer hints.')
    if shutil.which('fuck-u-code') is None:
        print('[WARN] fuck-u-code CLI not detected. Install manually if you want external quality-debt analyzer hints (quality-debt-overlay still works without it).')
