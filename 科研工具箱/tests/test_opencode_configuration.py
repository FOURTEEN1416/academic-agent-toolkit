import json
from pathlib import Path

import yaml


SUITE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SUITE_ROOT.parent
AGENTS = PROJECT_ROOT / ".opencode" / "agents"


def parse_agent_file(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    _, frontmatter, body = text.split("---", 2)
    return yaml.safe_load(frontmatter), body


def parse_agent_frontmatter(path: Path) -> dict:
    frontmatter, _ = parse_agent_file(path)
    return frontmatter


def test_shared_project_opencode_configuration_selects_modeling_agent_and_skills():
    config = json.loads((PROJECT_ROOT / "opencode.json").read_text(encoding="utf-8"))

    assert config["$schema"] == "https://opencode.ai/config.json"
    assert config["default_agent"] == "数模专家"
    assert config["skills"]["paths"] == ["./科研工具箱/skills"]
    assert config["instructions"] == ["科研工具箱/AGENTS.md"]
    assert config["subagent_depth"] == 1
    assert config["share"] == "disabled"
    assert (PROJECT_ROOT / config["skills"]["paths"][0]).is_dir()
    assert (PROJECT_ROOT / config["instructions"][0]).is_file()


def test_shared_project_root_is_the_only_agent_source():
    assert sorted(path.name for path in AGENTS.glob("*.md")) == [
        "数模专家.md", "数模审稿人.md", "数模编辑.md", "数模视觉审查.md",
    ]
    suite_agents = SUITE_ROOT / ".opencode" / "agents"
    assert not suite_agents.exists() or not list(suite_agents.glob("*.md"))


def test_shared_project_configuration_is_discoverable_from_all_workspaces():
    for workspace in (
        PROJECT_ROOT / "解析",
        PROJECT_ROOT / "赛前试炼任务",
        SUITE_ROOT,
    ):
        found = next((parent / "opencode.json" for parent in (workspace, *workspace.parents)
                      if (parent / "opencode.json").is_file()), None)
        assert found == PROJECT_ROOT / "opencode.json"


def test_modeling_agent_contracts():
    primary = parse_agent_frontmatter(AGENTS / "数模专家.md")
    assert primary["mode"] == "primary"
    assert primary["permission"]["task"] == "allow"
    assert primary["permission"]["edit"] == "allow"

    for filename, artifact in {
        "数模审稿人.md": "COMP_REVIEW_VERDICT.json",
        "数模视觉审查.md": "VISUAL_REVIEW_VERDICT.json",
        "数模编辑.md": "EDITOR_CHANGELOG.md",
    }.items():
        frontmatter, body = parse_agent_file(AGENTS / filename)
        assert frontmatter["mode"] == "subagent"
        assert artifact in body

    reviewer = parse_agent_frontmatter(AGENTS / "数模审稿人.md")
    visual = parse_agent_frontmatter(AGENTS / "数模视觉审查.md")
    assert reviewer["permission"]["edit"] == "deny"
    assert visual["permission"]["edit"] == "deny"


def test_agents_documentation_matches_project_configuration():
    text = (SUITE_ROOT / "AGENTS.md").read_text(encoding="utf-8")

    assert "StepAction.workspace" in text
    assert "skills.paths" in text
    assert "数模专家" in text
    assert "不依赖系统 PATH 中存在 `opencode` CLI" in text
    assert "OpenCode Desktop" in text


def test_root_readme_names_shared_desktop_project_root():
    text = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    assert r"D:\Desktop\数模竞赛" in text
    assert "OpenCode Desktop" in text
    assert "不依赖 `opencode` CLI" in text
