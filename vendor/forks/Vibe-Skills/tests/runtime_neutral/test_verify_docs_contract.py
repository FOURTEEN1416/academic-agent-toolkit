from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_verify_docs_separate_default_closure_from_touched_surface_gates() -> None:
    readme = (REPO_ROOT / "scripts" / "verify" / "README.md").read_text(encoding="utf-8")
    family_index = (REPO_ROOT / "scripts" / "verify" / "gate-family-index.md").read_text(encoding="utf-8")

    required_readme_claims = (
        "default release closure",
        "touched-surface extension gates",
        "`check.ps1` checks installed-copy health and receipt health",
        "does not replace release verification",
    )
    for claim in required_readme_claims:
        assert claim in readme

    required_family_claims = (
        "Default release closure",
        "Touched-surface extension gates",
        "Install receipt / installed-copy health",
    )
    for claim in required_family_claims:
        assert claim in family_index
