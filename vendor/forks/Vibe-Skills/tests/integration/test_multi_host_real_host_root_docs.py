from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_active_install_docs_prefer_skills_roots_not_host_roots() -> None:
    docs = [
        (REPO_ROOT / "docs/install/README.md").read_text(encoding="utf-8"),
        (REPO_ROOT / "docs/install/README.en.md").read_text(encoding="utf-8"),
    ]

    for text in docs:
        assert "~/.agents/skills" in text
        assert "~/.codex/skills" in text
        assert "~/.claude/skills" in text
        assert "~/.cursor" not in text
        assert "~/.codeium/windsurf" not in text
        assert "~/.openclaw" not in text
        assert "~/.config/opencode" not in text
