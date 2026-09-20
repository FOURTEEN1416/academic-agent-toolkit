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
from engine import opencode_bridge  # noqa: E402
from engine.capability_probe import probe  # noqa: E402
from engine.tool_forge import (  # noqa: E402
    forge_adapter,
    forge_from_gap,
    forge_skill,
    forge_tool,
    validate_name,
)


def test_opencode_bridge_is_compat_shim():
    assert opencode_bridge.StepAction is StepAction
    assert opencode_bridge.StepResult is StepResult


def test_bootstrap_contract_is_host_agnostic():
    contract = bootstrap(ROOT)
    assert contract["protocol_version"] == 1
    assert contract["role"] == "executor"
    assert "workflow_cli" in contract["engine"]["module"]
    assert "optional_adapters" in contract
    assert "opencode" in contract["optional_adapters"]
    assert "generic" in contract["optional_adapters"]
    joined = " ".join(contract["hard_rules"])
    assert "只编排" in joined
    assert "TOOL_GAP" in joined
    assert "无证据" in joined
    # 不得把某宿主写成唯一驱动前提
    assert "必须 OpenCode" not in json.dumps(contract, ensure_ascii=False)


def test_default_agent_label_prefers_hint(monkeypatch):
    monkeypatch.delenv("ACAT_AGENT_LABEL", raising=False)
    assert default_agent_label("") == DEFAULT_AGENT_LABEL
    assert default_agent_label("claude-code") == "claude-code"
    monkeypatch.setenv("ACAT_AGENT_LABEL", "cursor")
    assert default_agent_label("") == "cursor"


def test_probe_reports_adapters_and_gaps():
    result = probe(ROOT)
    assert result["drive_ready"] is True
    assert "packages" in result
    assert "cli" in result
    assert "host_adapters" in result
    assert result["host_adapters"]["generic"]["present"] is True
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
    suite = tmp_path / "科研工具箱"
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


def test_forge_adapter_and_gap_advisory(tmp_path):
    suite = tmp_path / "科研工具箱"
    (suite / "engine").mkdir(parents=True)
    adapter = forge_adapter("demo-host", "演示适配器", project_root=suite)
    assert adapter["created"] is True
    payload = json.loads((tmp_path / "agents" / "adapters" / "demo-host" / "adapter.json").read_text(encoding="utf-8"))
    assert payload["required_for_drive"] is False
    assert payload["adapter_id"] == "demo-host"

    advice = forge_from_gap({"kind": "python_package", "id": "fitz", "hint": "pip install pymupdf"}, suite)
    assert advice["forged"] is False
    assert advice["action"] == "advise_only"

    forged = forge_from_gap(
        {"kind": "optional_adapter", "id": "demo-host2", "hint": "another optional host"},
        suite,
    )
    assert forged.get("kind") == "adapter"
    assert forged.get("created") is True


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
    fake_suite = tmp_path / "科研工具箱"
    (fake_suite / "tools").mkdir(parents=True)
    # CLI 固定使用真实 ROOT；这里直接测 forge API + 真实 CLI 的参数校验分支
    missing = subprocess.run(
        [sys.executable, "-m", "engine.workflow_cli", "forge"],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", env=env, timeout=60,
    )
    assert missing.returncode == 2
    assert "forge" in missing.stdout.lower() or "forge" in missing.stderr.lower()
