from __future__ import annotations

import builtins
from pathlib import Path
import sys
import types

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
CLI_SRC = REPO_ROOT / 'apps' / 'vgo-cli' / 'src'
if str(CLI_SRC) not in sys.path:
    sys.path.insert(0, str(CLI_SRC))

from vgo_cli.errors import CliError
from vgo_cli.installer_bridge import refresh_install_ledger_payload
import vgo_cli.installer_bridge as installer_bridge


def test_refresh_install_ledger_payload_delegates_to_installer_core(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    recorded: dict[str, object] = {}

    def fake_extend(repo_root: Path) -> None:
        recorded['repo_root'] = repo_root

    def fake_refresh(target_root: Path) -> dict[str, object]:
        recorded['target_root'] = target_root
        return {'ok': True}

    def fake_collect_host_runtime(repo_root: Path, target_root: Path) -> dict[str, object]:
        recorded['runtime_repo_root'] = repo_root
        recorded['runtime_target_root'] = target_root
        return {'vibe_host_ready': True, 'source': 'test'}

    pkg = types.ModuleType('vgo_installer')
    pkg.__path__ = []
    ledger = types.ModuleType('vgo_installer.ledger_service')
    ledger.refresh_install_ledger = fake_refresh
    verify_pkg = types.ModuleType('vgo_verify')
    verify_pkg.__path__ = []
    doctor = types.ModuleType('vgo_verify.bootstrap_doctor_runtime')
    doctor.collect_host_runtime = fake_collect_host_runtime

    monkeypatch.setattr(installer_bridge, 'extend_workspace_package_path', fake_extend)
    monkeypatch.setitem(sys.modules, 'vgo_installer', pkg)
    monkeypatch.setitem(sys.modules, 'vgo_installer.ledger_service', ledger)
    monkeypatch.setitem(sys.modules, 'vgo_verify', verify_pkg)
    monkeypatch.setitem(sys.modules, 'vgo_verify.bootstrap_doctor_runtime', doctor)

    payload = refresh_install_ledger_payload(tmp_path / 'repo', tmp_path / 'target')

    assert payload['ok'] is True
    assert payload['host_runtime'] == {'vibe_host_ready': True, 'source': 'test'}
    assert recorded['repo_root'] == tmp_path / 'repo'
    assert recorded['target_root'] == tmp_path / 'target'
    assert recorded['runtime_repo_root'] == tmp_path / 'repo'
    assert recorded['runtime_target_root'] == tmp_path / 'target'


def test_refresh_install_ledger_payload_returns_core_payload_when_vgo_verify_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fake_refresh(target_root: Path) -> dict[str, object]:
        return {'ok': True, 'target': str(target_root)}

    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == 'vgo_verify.bootstrap_doctor_runtime':
            raise ModuleNotFoundError("No module named 'vgo_verify'", name='vgo_verify')
        return real_import(name, *args, **kwargs)

    pkg = types.ModuleType('vgo_installer')
    pkg.__path__ = []
    ledger = types.ModuleType('vgo_installer.ledger_service')
    ledger.refresh_install_ledger = fake_refresh

    monkeypatch.setattr(installer_bridge, 'extend_workspace_package_path', lambda _: None)
    monkeypatch.setattr(builtins, '__import__', fake_import)
    monkeypatch.setitem(sys.modules, 'vgo_installer', pkg)
    monkeypatch.setitem(sys.modules, 'vgo_installer.ledger_service', ledger)

    payload = refresh_install_ledger_payload(tmp_path / 'repo', tmp_path / 'target')

    assert payload == {'ok': True, 'target': str(tmp_path / 'target')}


def test_refresh_install_ledger_payload_surfaces_nested_doctor_import_errors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fake_refresh(_: Path) -> dict[str, object]:
        return {'ok': True}

    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == 'vgo_verify.bootstrap_doctor_runtime':
            raise ModuleNotFoundError(
                "No module named 'vgo_verify.bootstrap_doctor_runtime'",
                name='vgo_verify.bootstrap_doctor_runtime',
            )
        return real_import(name, *args, **kwargs)

    pkg = types.ModuleType('vgo_installer')
    pkg.__path__ = []
    ledger = types.ModuleType('vgo_installer.ledger_service')
    ledger.refresh_install_ledger = fake_refresh

    monkeypatch.setattr(installer_bridge, 'extend_workspace_package_path', lambda _: None)
    monkeypatch.setattr(builtins, '__import__', fake_import)
    monkeypatch.setitem(sys.modules, 'vgo_installer', pkg)
    monkeypatch.setitem(sys.modules, 'vgo_installer.ledger_service', ledger)

    with pytest.raises(ModuleNotFoundError, match='bootstrap_doctor_runtime'):
        refresh_install_ledger_payload(tmp_path / 'repo', tmp_path / 'target')


def test_refresh_install_ledger_payload_wraps_system_exit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_refresh(_: Path) -> dict[str, object]:
        raise SystemExit('broken')

    pkg = types.ModuleType('vgo_installer')
    pkg.__path__ = []
    ledger = types.ModuleType('vgo_installer.ledger_service')
    ledger.refresh_install_ledger = fake_refresh

    monkeypatch.setattr(installer_bridge, 'extend_workspace_package_path', lambda _: None)
    monkeypatch.setitem(sys.modules, 'vgo_installer', pkg)
    monkeypatch.setitem(sys.modules, 'vgo_installer.ledger_service', ledger)

    with pytest.raises(CliError, match='broken'):
        refresh_install_ledger_payload(tmp_path / 'repo', tmp_path / 'target')
