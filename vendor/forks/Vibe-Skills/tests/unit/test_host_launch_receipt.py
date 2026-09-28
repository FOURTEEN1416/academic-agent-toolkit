from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_SRC = REPO_ROOT / "packages" / "contracts" / "src"
if str(CONTRACTS_SRC) not in sys.path:
    sys.path.insert(0, str(CONTRACTS_SRC))

from vgo_contracts.host_launch_receipt import (
    HOST_LAUNCH_RECEIPT_FILENAME,
    HostLaunchReceipt,
    read_host_launch_receipt,
    write_host_launch_receipt,
)


def _sample_receipt() -> HostLaunchReceipt:
    return HostLaunchReceipt(
        host_id="codex",
        entry_id="vibe",
        launch_mode="canonical-entry",
        launcher_path="scripts/runtime/Invoke-VibeCanonicalEntry.ps1",
        requested_stage_stop="phase_cleanup",
        requested_grade_floor="XL",
        runtime_entrypoint="scripts/runtime/invoke-vibe-runtime.ps1",
        run_id="pytest-run-1",
        created_at="2026-04-16T00:00:00Z",
        launch_status="launched",
    )


def test_host_launch_receipt_roundtrips_from_model_dump() -> None:
    receipt = _sample_receipt()
    payload = receipt.model_dump()

    assert payload["host_id"] == "codex"
    assert payload["entry_id"] == "vibe"
    assert HostLaunchReceipt.model_validate(payload) == receipt


def test_host_launch_receipt_write_and_read(tmp_path: Path) -> None:
    receipt = _sample_receipt()
    receipt_path = tmp_path / HOST_LAUNCH_RECEIPT_FILENAME

    write_host_launch_receipt(receipt_path, receipt)
    restored = read_host_launch_receipt(receipt_path)

    assert restored == receipt


def test_host_launch_receipt_rejects_missing_required_fields(tmp_path: Path) -> None:
    payload = _sample_receipt().model_dump()
    payload.pop("host_id")
    receipt_path = tmp_path / HOST_LAUNCH_RECEIPT_FILENAME
    receipt_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="required field missing or null: host_id"):
        read_host_launch_receipt(receipt_path)


def test_host_launch_receipt_rejects_invalid_json(tmp_path: Path) -> None:
    receipt_path = tmp_path / HOST_LAUNCH_RECEIPT_FILENAME
    receipt_path.write_text("{ not-json }\n", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        read_host_launch_receipt(receipt_path)


def test_host_launch_receipt_rejects_non_object_payload(tmp_path: Path) -> None:
    receipt_path = tmp_path / HOST_LAUNCH_RECEIPT_FILENAME
    receipt_path.write_text("[1, 2, 3]\n", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid host launch receipt payload"):
        read_host_launch_receipt(receipt_path)


def test_host_launch_receipt_rejects_existing_wrong_filename_path(tmp_path: Path) -> None:
    wrong_path = tmp_path / "some-other-receipt.json"
    wrong_path.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="wrong filename"):
        write_host_launch_receipt(wrong_path, _sample_receipt())
