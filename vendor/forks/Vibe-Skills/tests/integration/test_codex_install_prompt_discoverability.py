from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_simple_install_docs_default_to_shared_agents_skills_root() -> None:
    zh_doc = (REPO_ROOT / "docs/install/README.md").read_text(encoding="utf-8")
    en_doc = (REPO_ROOT / "docs/install/README.en.md").read_text(encoding="utf-8")

    for text in (zh_doc, en_doc):
        assert "~/.agents/skills" in text
        assert "bash ./install.sh --skills-dir" in text
        assert "pwsh -NoProfile -File .\\install.ps1 -SkillsDir" in text
        assert "install-receipt.json" in text
        assert "--host" not in text
        assert "--profile" not in text
