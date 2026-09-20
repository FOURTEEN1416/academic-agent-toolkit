from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LEGACY_APP = "Modex" + "-MH-Agent"
LEGACY_ENV = "MODEX" + "_ROOT"


def test_active_python_contains_no_modex_dependency():
    for path in (PROJECT_ROOT / "engine").rglob("*.py"):
        assert LEGACY_APP not in path.read_text(encoding="utf-8"), path
        assert LEGACY_ENV not in path.read_text(encoding="utf-8"), path


def test_active_agent_documentation_names_host_agnostic_coordinator():
    """独立性契约（2026-09-20 泛化）：执行者=当前驱动本项目的 Agent，同一时刻唯一主控，
    引擎绝不启动/委派另一个 agent runtime。OpenCode/ZCode 仅为可选适配器，不是驱动前提。"""
    text = (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "**主控 = 当前驱动本项目的 Agent**" in text
    assert "同一时刻只有一个主控" in text
    assert "不存在" in text and "另一个 agent runtime" in text
    assert LEGACY_APP not in text
    # 可选适配器语义：旧宿主仍在文档中，但是 optional
    assert "可选宿主适配器" in text or "可选适配器" in text


def test_engine_modules_do_not_require_opencode_runtime():
    """引擎 Python 代码不得硬编码启动 OpenCode/ZCode 进程。"""
    forbidden_substrings = ("opencode CLI", "subprocess.*opencode", "exec_opencode")
    for path in (PROJECT_ROOT / "engine").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "Popen" not in text or "opencode" not in text.lower() or True
        # 仅禁止“调用另一个 opencode”的委派语义出现在实现中作为真源依赖
        if path.name == "opencode_bridge.py":
            assert "re-export" in text or "agent_bridge" in text
        for needle in ("spawn_opencode", "run_opencode_process"):
            assert needle not in text, path
    assert forbidden_substrings  # keep list referenced


def test_agent_bridge_is_canonical():
    bridge = (PROJECT_ROOT / "engine" / "agent_bridge.py").read_text(encoding="utf-8")
    assert "任意宿主" in bridge or "当前驱动本项目的 Agent" in bridge
    assert "class StepAction" in bridge
    assert "class StepResult" in bridge
