from pathlib import Path


ROOT = Path(__file__).parents[1]
VENDOR = ROOT / "tools" / "codesucker-core"


def test_vendored_core_has_provenance_and_license():
    provenance = (VENDOR / "UPSTREAM.md").read_text(encoding="utf-8")
    assert "b065a1825f4e32dca4c4b7fd8bccf3e020a77c5c" in provenance
    assert "Apache-2.0" in provenance
    assert (VENDOR / "LICENSE").is_file()
    assert (VENDOR / "NOTICE").is_file()


def test_vendored_core_exposes_expected_modules():
    src = VENDOR / "packages" / "core" / "src"
    for name in ("index.ts", "discover.ts", "clean.ts", "select.ts", "render.ts", "audit.ts"):
        assert (src / name).is_file(), name
