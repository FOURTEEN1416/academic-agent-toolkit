from __future__ import annotations

import importlib
from pathlib import Path
import subprocess
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
CLI_SRC = REPO_ROOT / 'apps' / 'vgo-cli' / 'src'
if str(CLI_SRC) not in sys.path:
    sys.path.insert(0, str(CLI_SRC))

from vgo_cli import external as cli_external


def test_optional_install_timeout_defaults_when_env_is_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('VGO_OPTIONAL_INSTALL_TIMEOUT_SECONDS', 'not-a-number')

    module = importlib.reload(cli_external)

    assert module.OPTIONAL_INSTALL_TIMEOUT_SECONDS == 15


def test_run_optional_install_uses_bounded_timeout_and_does_not_raise(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    recorded: dict[str, object] = {}

    def fake_run(command: list[str], *, capture_output: bool, text: bool, timeout: int) -> subprocess.CompletedProcess[str]:
        recorded['command'] = command
        recorded['capture_output'] = capture_output
        recorded['text'] = text
        recorded['timeout'] = timeout
        raise subprocess.TimeoutExpired(command, timeout)

    monkeypatch.setattr(cli_external.subprocess, 'run', fake_run)

    cli_external._run_optional_install(['npm', 'install', '-g', '@th0rgal/ralph-wiggum'])

    assert recorded == {
        'command': ['npm', 'install', '-g', '@th0rgal/ralph-wiggum'],
        'capture_output': True,
        'text': True,
        'timeout': cli_external.OPTIONAL_INSTALL_TIMEOUT_SECONDS,
    }
    assert 'timed out' in capsys.readouterr().out
