"""仓库卫生回归：主控文档与公开入口保持驱动方无关的协议表述。"""
from pathlib import Path


SUITE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SUITE_ROOT.parent


def test_agents_documentation_is_runtime_agnostic_protocol():
    text = (SUITE_ROOT / "AGENTS.md").read_text(encoding="utf-8")

    assert "StepAction.workspace" in text
    assert "skills/" in text
    assert "宿主无关" in text
    assert "workflow_cli" in text
    assert "当前驱动本项目的 Agent" in text
    assert "boot" in text and "probe" in text


def test_root_readme_names_runtime_agnostic_entry():
    text = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    # PUBLIC-repo path hygiene（检测针按片段拼接，避免自身成为路径泄漏样例）
    assert "D:" + chr(92) + "Desktop" + chr(92) + "数模竞赛" not in text
    assert "C:" + chr(92) + "Users" + chr(92) + "FOUR" not in text
    assert "git clone" in text
    assert "学术工作流" in text or "项目根" in text or "Academic Agent Toolkit" in text
    assert "宿主" in text or "Agent" in text
    assert "workflow_cli" in text or "boot" in text or "驱动" in text
    assert "DOCSEARCH" in text or "占位符" in text or "路径卫生" in text or "适配" in text
