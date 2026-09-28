from pathlib import Path


def test_local_agent_kernel_entry_writes_standard_truth_artifacts() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    text = (repo_root / "packages" / "runtime-core" / "src" / "vgo_runtime" / "canonical_entry.py").read_text(
        encoding="utf-8"
    )
    assert "build_runtime_truth_packet(" in text
    assert "runtime-input-packet.json" in text
    assert "governance-capsule.json" in text
    assert "stage-lineage.json" in text
    assert "assert_minimum_truth_artifacts(" in text
