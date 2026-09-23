"""OpenCode 可选适配器配置契约。

opencode.json 随库分发（subagent 角色内联其中）：本文件校验其配置契约，并把只读
审稿角色契约落在内联 subagent 上。适配层文件（.opencode/agents、.opencode/plugins、
agents/adapters/）不入库，由 test_host_adapter_layer_files_are_not_tracked 守护
该形态——文件回流即红灯，重引入适配层须显式改写本测试。
"""
import json
from pathlib import Path


SUITE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SUITE_ROOT.parent


def test_shared_project_opencode_configuration_is_optional_adapter():
    """OpenCode 配置仍在库，但语义是可选适配器：必须指向技能库与主控文档。"""
    config = json.loads((PROJECT_ROOT / "opencode.json").read_text(encoding="utf-8"))

    assert config["$schema"] == "https://opencode.ai/config.json"
    assert config["default_agent"] == "数模专家"
    assert config["skills"]["paths"] == ["./科研工具箱/skills"]
    assert config["instructions"] == ["科研工具箱/AGENTS.md"]
    assert config["subagent_depth"] == 1
    assert config["share"] == "disabled"
    assert (PROJECT_ROOT / config["skills"]["paths"][0]).is_dir()
    assert (PROJECT_ROOT / config["instructions"][0]).is_file()


def test_host_adapter_layer_files_are_not_tracked():
    """适配层文件形态守护：以下路径保持缺席，出现即红灯。

    若重新引入宿主适配层，应显式改写本测试，不得悄悄删除断言。
    """
    assert not any((PROJECT_ROOT / ".opencode" / "agents").glob("*.md"))
    assert not (PROJECT_ROOT / ".opencode" / "plugins" / "audit-trail.ts").exists()
    assert not any((PROJECT_ROOT / "agents" / "adapters").rglob("adapter.json"))


def test_review_subagent_contracts_inline_in_opencode_config():
    """只读审稿角色契约（原 .opencode/agents/*.md 契约的内联化，2026-09-23 迁移）：
    审稿人/视觉审查只读（edit=deny），编辑子代理受控可写。"""
    config = json.loads((PROJECT_ROOT / "opencode.json").read_text(encoding="utf-8"))
    agents = config["agent"]

    for name in ("数模审稿人", "数模视觉审查"):
        agent = agents[name]
        assert agent["mode"] == "subagent"
        assert agent["permission"]["edit"] == "deny"
        assert "只读" in agent["description"]
    editor = agents["数模编辑"]
    assert editor["mode"] == "subagent"
    assert editor["permission"]["edit"] == "allow"


def test_shared_project_configuration_is_discoverable_from_all_workspaces():
    for workspace in (
        PROJECT_ROOT / "解析",
        PROJECT_ROOT / "赛前试炼任务",
        SUITE_ROOT,
    ):
        found = next((parent / "opencode.json" for parent in (workspace, *workspace.parents)
                      if (parent / "opencode.json").is_file()), None)
        assert found == PROJECT_ROOT / "opencode.json"


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
    """opencode.json 不得含本机用户名或过期项目绝对路径。"""
    raw = (PROJECT_ROOT / "opencode.json").read_text(encoding="utf-8")
    assert r"C:\Users\FOUR" not in raw, "opencode.json 含本机用户目录绝对路径"
    assert r"D:\Desktop\数模竞赛" not in raw, "opencode.json 含过期项目根路径"
