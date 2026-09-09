from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LEGACY_APP = "Modex" + "-MH-Agent"
LEGACY_ENV = "MODEX" + "_ROOT"


def test_active_python_contains_no_modex_dependency():
    for path in (PROJECT_ROOT / "engine").rglob("*.py"):
        assert LEGACY_APP not in path.read_text(encoding="utf-8"), path
        assert LEGACY_ENV not in path.read_text(encoding="utf-8"), path


def test_active_agent_documentation_names_current_host_as_sole_coordinator():
    """独立性契约（2026-09-09 演化）：执行者=当前宿主主控 Agent，同一时刻唯一主控，
    引擎绝不启动/委派另一个宿主进程——政策从"仅 OpenCode"扩为双宿主后，
    契约核心（拒绝外部 Agent 依赖、单一协调者）不变，只更新被钉的真源措辞。"""
    text = (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "**主控 = 当前宿主的 Agent**" in text
    assert "同一时刻只有一个宿主主控" in text
    assert "不存在" in text and "调用另一个 opencode" in text  # 反委派句仍在
    assert LEGACY_APP not in text
