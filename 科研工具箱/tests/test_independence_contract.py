from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LEGACY_APP = "Modex" + "-MH-Agent"
LEGACY_ENV = "MODEX" + "_ROOT"


def test_active_python_contains_no_modex_dependency():
    for path in (PROJECT_ROOT / "engine").rglob("*.py"):
        assert LEGACY_APP not in path.read_text(encoding="utf-8"), path
        assert LEGACY_ENV not in path.read_text(encoding="utf-8"), path


def test_active_agent_documentation_names_desktop_as_sole_coordinator():
    text = (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "OpenCode Desktop 是唯一主控" in text
    assert LEGACY_APP not in text
