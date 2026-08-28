"""Regression tests for the file-level asset ledger."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.build_asset_ledger import build_ledger, classify_path


def test_classify_path_assigns_conservative_categories() -> None:
    assert classify_path(Path("科研工具箱/engine/workflow_cli.py"))[0] == "candidate_public_core"
    assert classify_path(Path("科研工具箱/skills/paper-write/SKILL.md"))[0] == "experimental"
    assert classify_path(Path("数学建模大赛工具集/skills/visualization/SKILL.md"))[0] == "historical_reference"
    assert classify_path(Path("附件2. 2026高教社杯全国大学生数学建模竞赛.pdf"))[0] == "private_extension"
    assert classify_path(Path("科研工具箱/.env"))[0] == "excluded_sensitive"


def test_build_ledger_skips_env_content_and_sorts_records(tmp_path: Path) -> None:
    (tmp_path / "科研工具箱" / "engine").mkdir(parents=True)
    (tmp_path / "科研工具箱" / ".env").write_text("SECRET=must-not-be-read", encoding="utf-8")
    (tmp_path / "科研工具箱" / "engine" / "workflow_cli.py").write_text(
        "print('ok')\n", encoding="utf-8"
    )
    (tmp_path / "z.txt").write_text("z", encoding="utf-8")
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")

    output = tmp_path / "governance"
    summary = build_ledger(tmp_path, output)
    records = [
        json.loads(line)
        for line in (output / "asset-ledger.jsonl").read_text(encoding="utf-8").splitlines()
    ]

    assert [record["path"] for record in records] == sorted(record["path"] for record in records)
    env_record = next(record for record in records if record["path"].endswith("/.env"))
    assert env_record["sha256"] is None
    assert env_record["source_status"] == "not_inspected_sensitive"
    assert summary["total_records"] == len(records)
    assert summary["classification_counts"]["excluded_sensitive"] == 1
