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


def test_shared_project_opencode_configuration_is_optional_adapter():
    """OpenCode 配置仍在位，但语义是可选适配器：必须指向技能库与主控文档。"""
    config = json.loads((PROJECT_ROOT / "opencode.json").read_text(encoding="utf-8"))

    assert config["$schema"] == "https://opencode.ai/config.json"
    assert config["default_agent"] == "数模专家"
    assert config["skills"]["paths"] == ["./科研工具箱/skills"]
    assert config["instructions"] == ["科研工具箱/AGENTS.md"]
    assert config["subagent_depth"] == 1
    assert config["share"] == "disabled"
    assert (PROJECT_ROOT / config["skills"]["paths"][0]).is_dir()
    assert (PROJECT_ROOT / config["instructions"][0]).is_file()

    adapter_meta = PROJECT_ROOT / "agents" / "adapters" / "opencode" / "adapter.json"
    assert adapter_meta.is_file()
    meta = json.loads(adapter_meta.read_text(encoding="utf-8"))
    assert meta["required_for_drive"] is False
    assert meta["status"] == "optional"


def test_generic_adapter_always_present():
    generic = PROJECT_ROOT / "agents" / "adapters" / "generic" / "adapter.json"
    assert generic.is_file()
    meta = json.loads(generic.read_text(encoding="utf-8"))
    assert meta["adapter_id"] == "generic"
    assert meta["kind"] == "protocol"


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


def test_agents_documentation_is_host_agnostic_protocol():
    text = (SUITE_ROOT / "AGENTS.md").read_text(encoding="utf-8")

    assert "StepAction.workspace" in text
    assert "skills/" in text
    assert "宿主无关" in text
    assert "workflow_cli" in text
    assert "当前驱动本项目的 Agent" in text
    # 旧宿主仍被记录，但是可选
    assert "OpenCode" in text
    assert "可选" in text
    assert "boot" in text and "probe" in text


def test_root_readme_names_host_agnostic_entry():
    text = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    # PUBLIC-repo path hygiene
    assert r"D:\Desktop\数模竞赛" not in text
    assert r"C:\Users\FOUR" not in text
    assert "git clone" in text
    assert "学术工作流" in text or "项目根" in text or "Academic Agent Toolkit" in text
    assert "宿主" in text or "Agent" in text
    assert "workflow_cli" in text or "boot" in text or "驱动" in text
    assert "DOCSEARCH" in text or "占位符" in text or "路径卫生" in text or "适配" in text


def test_tracked_host_configs_have_no_personal_absolute_paths():
    """opencode.json / .zcode/config.json 不得含本机用户名或过期项目绝对路径。"""
    for rel in ("opencode.json", ".zcode/config.json"):
        raw = (PROJECT_ROOT / rel).read_text(encoding="utf-8")
        assert r"C:\Users\FOUR" not in raw, f"{rel} 含本机用户目录绝对路径"
        assert r"D:\Desktop\数模竞赛" not in raw, f"{rel} 含过期项目根路径"
        if rel.endswith("zcode/config.json"):
            cfg = json.loads(raw)
            hooks = cfg.get("hooks", {}).get("events", {})
            for event, entries in hooks.items():
                for e in entries:
                    for h in e.get("hooks", []):
                        code = "".join(h.get("args", []))
                        assert r"C:\Users" not in code
                        assert "fail-open" in code or "sys.exit(0)" in code
