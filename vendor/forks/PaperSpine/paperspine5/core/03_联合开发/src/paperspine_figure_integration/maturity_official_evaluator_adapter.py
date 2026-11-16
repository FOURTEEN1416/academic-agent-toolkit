"""Independent V3 evaluator process adapter for one official PS-GAP-014 run."""

from __future__ import annotations

import argparse
import copy
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from paperspine_figure_integration.maturity_acceptance_v3 import (
    build_independent_evaluation_receipt_v3,
    verify_independent_evaluation_receipt_v3,
)


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} must be an object")
    return value


def _publish(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError(f"evaluator result collision: {path}")
    stage = path.with_name(f".{path.name}.stage")
    if stage.exists():
        raise RuntimeError(f"evaluator stage collision: {stage}")
    owned = False
    try:
        encoded = (
            json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        ).encode("utf-8")
        with stage.open("xb") as handle:
            owned = True
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(stage, path)
    except Exception:
        if owned and stage.exists():
            stage.unlink()
        raise


def evaluate(
    protocol_path: str | Path,
    fixture_receipt_path: str | Path,
    journey_path: str | Path,
    result_path: str | Path,
    *,
    evaluated_at: str | None = None,
) -> dict[str, Any]:
    protocol = _read_json(Path(protocol_path).resolve(), "protocol")
    fixture = _read_json(Path(fixture_receipt_path).resolve(), "fixture receipt")
    journey = _read_json(Path(journey_path).resolve(), "product journey")
    if journey.get("external_action_authorized") is not False:
        raise RuntimeError("product journey does not preserve external=false")
    receipt = build_independent_evaluation_receipt_v3(
        protocol,
        fixture,
        run_id=journey["run_id"],
        entry_mode=journey["entry_mode"],
        attempt=int(journey["attempt"]),
        producer_identity=journey["producer_identity"],
        evaluator_identity=protocol["evaluator_requirements"]["evaluator_identity"],
        evaluated_at=evaluated_at
        or datetime.now().astimezone().isoformat(timespec="milliseconds"),
        subject=copy.deepcopy(journey["subject"]),
        evidence=copy.deepcopy(journey["evidence"]),
    )
    verified = verify_independent_evaluation_receipt_v3(protocol, fixture, receipt)
    _publish(Path(result_path).resolve(), verified)
    return verified


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--fixture-receipt", required=True)
    parser.add_argument("--journey", required=True)
    parser.add_argument("--result", required=True)
    args = parser.parse_args(argv)
    evaluate(args.protocol, args.fixture_receipt, args.journey, args.result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
