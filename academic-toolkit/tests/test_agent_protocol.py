"""宿主无关驱动协议 / 能力探测 / 工具铸造 测试。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.agent_bridge import StepAction, StepResult  # noqa: E402
from engine.agent_protocol import (  # noqa: E402
    DEFAULT_AGENT_LABEL,
    bootstrap,
    default_agent_label,
)
from engine.capability_probe import probe  # noqa: E402
from engine.tool_forge import (  # noqa: E402
    forge_skill,
    forge_tool,
    validate_name,
)


def test_agent_bridge_has_single_canonical_model():
    assert StepAction.__module__ == "engine.agent_bridge"
    assert StepResult.__module__ == "engine.agent_bridge"
    assert len(list((ROOT / "engine").glob("*bridge*.py"))) == 1


def test_bootstrap_contract_is_host_agnostic():
    contract = bootstrap(ROOT)
    assert contract["protocol_version"] == 1
    assert contract["role"] == "executor"
    assert "workflow_cli" in contract["engine"]["module"]
    assert "optional_adapters" not in contract
    assert "adapter_note" not in contract
    joined = " ".join(contract["hard_rules"])
    assert "只编排" in joined
    assert "TOOL_GAP" in joined
    assert "无证据" in joined
    completion = contract["completion_contract"]
    assert completion["target"] == ["step_id", "attempt_id", "expected_revision"]
    assert "pending" in completion["delivery_recovery"]
    assert "--wf" in completion["delivery_recovery"]
    assert "evidence.execution_manifest" in completion["execution_manifest"]
    assert "--workflow-db WORKSPACE=DB" in completion["resource_statistics"]


def test_default_agent_label_prefers_hint(monkeypatch):
    monkeypatch.delenv("ACAT_AGENT_LABEL", raising=False)
    assert default_agent_label("") == DEFAULT_AGENT_LABEL
    assert default_agent_label("agent-label-x") == "agent-label-x"
    monkeypatch.setenv("ACAT_AGENT_LABEL", "operator-tool-7")
    assert default_agent_label("") == "operator-tool-7"


def test_probe_reports_capabilities_and_gaps():
    result = probe(ROOT)
    assert result["drive_ready"] is True
    assert "packages" in result
    assert "cli" in result
    # 可选适配器子系统已退休：probe 不再输出任何适配器探测段。
    assert "optional_capabilities" not in result
    assert "host_adapters" not in result
    assert isinstance(result["gaps"], list)
    # 探测不泄漏环境变量值
    raw = json.dumps(result, ensure_ascii=False)
    assert "api_key_value" not in raw
    for key, present in result["env_presence"].items():
        assert isinstance(present, bool), key


def test_validate_name_rejects_bad_names():
    assert validate_name("my-tool") == "my-tool"
    with pytest.raises(ValueError):
        validate_name("Bad_Name")
    with pytest.raises(ValueError):
        validate_name("")


def test_forge_tool_and_skill_scaffold(tmp_path):
    suite = tmp_path / "academic-toolkit"
    (suite / "tools").mkdir(parents=True)
    (suite / "skills").mkdir(parents=True)
    tool = forge_tool("demo-probe-tool", "演示用自适应工具", project_root=suite)
    assert tool["created"] is True
    assert (suite / "tools" / "demo-probe-tool.py").is_file()
    text = (suite / "tools" / "demo-probe-tool.py").read_text(encoding="utf-8")
    assert "scaffolded" in text
    assert "implemented" in text

    again = forge_tool("demo-probe-tool", "重复", project_root=suite)
    assert again["created"] is False
    assert again["status"] == "exists"

    skill = forge_skill("demo-probe-skill", "演示技能", project_root=suite, tool_name="demo-probe-tool")
    assert skill["created"] is True
    skill_md = (suite / "skills" / "demo-probe-skill" / "SKILL.md").read_text(encoding="utf-8")
    assert "demo-probe-skill" in skill_md
    assert "TOOL_GAP" in skill_md
    assert skill["catalog_capability_id"] == "demo-probe-skill"


def test_optional_adapter_subsystem_is_retired():
    """可选适配器子系统整体退休：不再提供适配器铸造入口。"""
    import engine.tool_forge as tool_forge

    assert not hasattr(tool_forge, "forge_adapter")


def test_workflow_cli_boot_probe_and_forge(tmp_path, monkeypatch):
    import subprocess

    env = {**__import__("os").environ, "PYTHONPATH": str(ROOT), "PYTHONWARNINGS": "ignore"}
    boot = subprocess.run(
        [sys.executable, "-m", "engine.workflow_cli", "boot"],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", env=env, timeout=60,
    )
    assert boot.returncode == 0, boot.stderr
    boot_text = boot.stdout[boot.stdout.find("{"):] if "{" in boot.stdout else boot.stdout
    contract = json.loads(boot_text)
    assert contract["protocol_version"] == 1

    probe_run = subprocess.run(
        [sys.executable, "-m", "engine.workflow_cli", "probe"],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", env=env, timeout=60,
    )
    assert probe_run.returncode == 0, probe_run.stderr
    probe_text = probe_run.stdout[probe_run.stdout.find("{"):] if "{" in probe_run.stdout else probe_run.stdout
    probed = json.loads(probe_text)
    assert probed["drive_ready"] is True

    # 在临时套件目录 forge，避免污染真实仓库
    fake_suite = tmp_path / "academic-toolkit"
    (fake_suite / "tools").mkdir(parents=True)
    # CLI 固定使用真实 ROOT；这里直接测 forge API + 真实 CLI 的参数校验分支
    missing = subprocess.run(
        [sys.executable, "-m", "engine.workflow_cli", "forge"],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", env=env, timeout=60,
    )
    assert missing.returncode == 2
    assert "forge" in missing.stdout.lower() or "forge" in missing.stderr.lower()
