from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_DEFAULT_CLOSURE_GATES = [
    "vibe-governed-runtime-contract-gate.ps1",
    "vibe-canonical-entry-truth-gate.ps1",
    "vibe-runtime-execution-proof-gate.ps1",
    "vibe-release-truth-consistency-gate.ps1",
    "vibe-repo-cleanliness-gate.ps1",
]


def _read_default_closure_section() -> str:
    text = (REPO_ROOT / "scripts" / "verify" / "gate-family-index.md").read_text(encoding="utf-8")
    return text.split("## Default release closure", 1)[1].split("## Touched-surface extension gates", 1)[0]


def test_default_closure_story_mentions_only_small_gate_set() -> None:
    text = (REPO_ROOT / "scripts" / "verify" / "gate-family-index.md").read_text(encoding="utf-8")
    section = _read_default_closure_section()
    ordered_lines = [
        line.strip()
        for line in section.splitlines()
        if line.strip() and line.lstrip().startswith(tuple(f"{index}." for index in range(1, 10)))
    ]
    expected_lines = [f"{index}. `{name}`" for index, name in enumerate(EXPECTED_DEFAULT_CLOSURE_GATES, start=1)]

    assert ordered_lines == expected_lines
    assert "10. `vibe-repo-cleanliness-gate.ps1`" not in text
    assert "vibe-pack-routing-smoke.ps1" not in "\n".join(ordered_lines)


def test_check_ps1_uses_simplified_skills_dir_check_without_closure_gate_list() -> None:
    text = (REPO_ROOT / "check.ps1").read_text(encoding="utf-8")

    assert "$DefaultClosureGateNames" not in text
    assert "Default closure gates:" not in text
    assert "'vgo_cli.main', 'check', '--repo-root'" in text
    assert "'--skills-dir'" in text
