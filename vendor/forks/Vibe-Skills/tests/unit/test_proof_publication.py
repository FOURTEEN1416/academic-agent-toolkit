from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
VERIFY_SRC = REPO_ROOT / "packages" / "verification-core" / "src"
if str(VERIFY_SRC) not in sys.path:
    sys.path.insert(0, str(VERIFY_SRC))

from vgo_verify.proof_publication import (  # noqa: E402
    aggregate_proofs,
    main,
    run_command,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_run_command_writes_attributed_proof_and_artifact_digests(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "result.txt"
    artifact_path.write_text("verified\n", encoding="utf-8")
    proof_path = tmp_path / "proofs" / "command.json"

    proof = run_command(
        repo_root=tmp_path,
        command=[sys.executable, "-c", "print('proof-output')"],
        output_path=proof_path,
        artifact_paths=[artifact_path],
        commit_sha="0123456789abcdef",
        label="unit-proof",
    )

    stored = json.loads(proof_path.read_text(encoding="utf-8"))
    assert proof == stored
    assert stored["command"]["argv"][:2] == [sys.executable, "-c"]
    assert stored["command"]["label"] == "unit-proof"
    assert stored["result"] == "PASS"
    assert stored["exit_code"] == 0
    assert stored["commit_sha"] == "0123456789abcdef"
    assert stored["environment"]["python_version"]
    assert stored["environment"]["platform"]
    digests = {item["path"]: item for item in stored["artifacts"]}
    assert digests["result.txt"]["sha256"] == _sha256(artifact_path)
    assert digests["proofs/command.stdout.log"]["sha256"] == _sha256(
        proof_path.with_suffix(".stdout.log")
    )
    assert "proof-output" in proof_path.with_suffix(".stdout.log").read_text(
        encoding="utf-8"
    )


def test_run_command_records_failures_without_losing_proof(tmp_path: Path) -> None:
    proof_path = tmp_path / "failed.json"

    proof = run_command(
        repo_root=tmp_path,
        command=[sys.executable, "-c", "raise SystemExit(7)"],
        output_path=proof_path,
        commit_sha="fedcba9876543210",
    )

    assert proof["result"] == "FAIL"
    assert proof["exit_code"] == 7
    assert proof_path.is_file()


def test_run_command_fails_when_a_declared_artifact_is_missing(tmp_path: Path) -> None:
    proof = run_command(
        repo_root=tmp_path,
        command=[sys.executable, "-c", "print('completed')"],
        output_path="proof.json",
        artifact_paths=["missing-result.json"],
        commit_sha="fedcba9876543210",
    )

    assert proof["result"] == "FAIL"
    assert proof["exit_code"] == 0
    assert proof["missing_artifact_count"] == 1
    assert any(item.get("missing") for item in proof["artifacts"])
    assert (tmp_path / "proof.json").is_file()


def test_aggregate_proofs_generates_bundle_and_current_state(tmp_path: Path) -> None:
    passing_path = tmp_path / "proofs" / "passing.json"
    failing_path = tmp_path / "proofs" / "failing.json"
    run_command(
        repo_root=tmp_path,
        command=[sys.executable, "-c", "print('pass')"],
        output_path=passing_path,
        commit_sha="abc123",
        label="passing",
    )
    run_command(
        repo_root=tmp_path,
        command=[sys.executable, "-c", "raise SystemExit(2)"],
        output_path=failing_path,
        commit_sha="abc123",
        label="failing",
    )

    outputs = aggregate_proofs(
        repo_root=tmp_path,
        proof_paths=[passing_path, failing_path],
        output_directory=tmp_path / "published",
    )

    bundle = json.loads(outputs["proof_bundle"].read_text(encoding="utf-8"))
    current_state = json.loads(
        outputs["current_state_json"].read_text(encoding="utf-8")
    )
    current_state_markdown = outputs["current_state_markdown"].read_text(
        encoding="utf-8"
    )
    assert bundle["result"] == "FAIL"
    assert [item["command"]["label"] for item in bundle["proofs"]] == [
        "passing",
        "failing",
    ]
    assert all(item["sha256"] for item in bundle["artifact_digests"])
    assert current_state["result"] == "FAIL"
    assert current_state["commit_sha"] == "abc123"
    assert current_state["proof_bundle"]["sha256"] == _sha256(
        outputs["proof_bundle"]
    )
    assert "Generated Current State" in current_state_markdown
    assert "FAIL" in current_state_markdown


def test_aggregate_proofs_records_absent_inputs_and_generates_state(
    tmp_path: Path,
) -> None:
    passing_path = tmp_path / "proofs" / "passing.json"
    missing_path = tmp_path / "proofs" / "missing.json"
    run_command(
        repo_root=tmp_path,
        command=[sys.executable, "-c", "print('pass')"],
        output_path=passing_path,
        commit_sha="abc123",
        label="passing",
    )

    outputs = aggregate_proofs(
        repo_root=tmp_path,
        proof_paths=[passing_path, missing_path],
        output_directory=tmp_path / "published",
    )

    bundle = json.loads(outputs["proof_bundle"].read_text(encoding="utf-8"))
    current_state = json.loads(
        outputs["current_state_json"].read_text(encoding="utf-8")
    )
    current_state_markdown = outputs["current_state_markdown"].read_text(
        encoding="utf-8"
    )
    assert bundle["result"] == "FAIL"
    assert bundle["absent_proofs"] == ["proofs/missing.json"]
    assert any(
        item.get("artifact_kind") == "command_proof" and item.get("missing")
        for item in bundle["missing_artifacts"]
    )
    assert current_state["absent_proofs"] == ["proofs/missing.json"]
    assert "Missing Proofs" in current_state_markdown
    assert "proofs/missing.json" in current_state_markdown


def test_aggregate_proofs_generates_failure_state_when_every_input_is_absent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_SHA", "fedcba9876543210")

    outputs = aggregate_proofs(
        repo_root=tmp_path,
        proof_paths=["proofs/first.json", "proofs/second.json"],
        output_directory="published",
    )

    bundle = json.loads(outputs["proof_bundle"].read_text(encoding="utf-8"))
    assert bundle["result"] == "FAIL"
    assert bundle["commit_sha"] == "fedcba9876543210"
    assert bundle["proofs"] == []
    assert bundle["absent_proofs"] == [
        "proofs/first.json",
        "proofs/second.json",
    ]


def test_aggregate_proofs_records_missing_declared_artifacts(
    tmp_path: Path,
) -> None:
    proof_path = tmp_path / "passing.json"
    run_command(
        repo_root=tmp_path,
        command=[sys.executable, "-c", "print('pass')"],
        output_path=proof_path,
        commit_sha="abc123",
    )

    outputs = aggregate_proofs(
        repo_root=tmp_path,
        proof_paths=[proof_path],
        artifact_paths=["missing-contract.json"],
        output_directory="published",
    )

    bundle = json.loads(outputs["proof_bundle"].read_text(encoding="utf-8"))
    assert bundle["result"] == "FAIL"
    assert bundle["absent_proofs"] == []
    assert bundle["missing_artifacts"] == [
        {"path": "missing-contract.json", "missing": True}
    ]


def test_aggregate_proofs_rejects_empty_and_mixed_commit_inputs(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="at least one command proof"):
        aggregate_proofs(
            repo_root=tmp_path,
            proof_paths=[],
            output_directory="published",
        )

    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"
    for path, commit_sha in ((first_path, "first"), (second_path, "second")):
        run_command(
            repo_root=tmp_path,
            command=[sys.executable, "-c", "print('pass')"],
            output_path=path,
            commit_sha=commit_sha,
        )
    with pytest.raises(ValueError, match="same commit SHA"):
        aggregate_proofs(
            repo_root=tmp_path,
            proof_paths=[first_path, second_path],
            output_directory="published",
        )


def test_aggregate_cli_returns_nonzero_for_a_failed_bundle(tmp_path: Path) -> None:
    proof_path = tmp_path / "failed.json"
    run_command(
        repo_root=tmp_path,
        command=[sys.executable, "-c", "raise SystemExit(2)"],
        output_path=proof_path,
        commit_sha="abc123",
    )

    exit_code = main(
        [
            "aggregate",
            "--repo-root",
            str(tmp_path),
            "--proof",
            str(proof_path),
            "--output-directory",
            str(tmp_path / "published"),
        ]
    )

    assert exit_code == 1
