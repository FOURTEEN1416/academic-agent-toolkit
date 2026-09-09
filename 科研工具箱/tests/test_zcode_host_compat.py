"""ZCode 赛时主控兼容性测试（2026-09-09 用户裁定：不预设模型 + ZCode 主控 + hook L1）。

覆盖：
  A. 模型配置三级解析（contest 配置槽 > 宿主 agents > 无配置），仓库出厂零预设；
  B. strict 门禁在"配置槽填了模型"后恢复硬拦截、在"两处皆空"时降级 warn；
  C. ZCode L1 hook 脚本（zcode_audit_l1.py）的落账/拦截/容错行为与 audit_store 格式兼容；
  D. .zcode/config.json hooks 注册契约（enabled、三事件、脚本存在）。
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SUITE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SUITE_ROOT.parent
sys.path.insert(0, str(SUITE_ROOT))

from engine.quality_gates import (  # noqa: E402
    QualityGate,
    load_configured_role_models,
    model_config_provenance,
)

ROLES = ["reviewer", "visual_reviewer", "editor", "final_reviewer"]


# ---------------- A. 三级解析 ----------------

def test_contest_slot_ships_with_zero_preset_models():
    """出厂仓库的配置槽必须全空——'不预设模型'是用户裁定，任何预填都是回归。"""
    data = json.loads((SUITE_ROOT / "engine" / "modex-core" / "contest_models.json")
                      .read_text(encoding="utf-8"))
    for role in ROLES:
        assert not data["roles"].get(role), f"配置槽不得预设 {role} 模型（比赛时再配置）"


def test_contest_slot_wins_over_agents_dir(tmp_path, monkeypatch):
    contest = tmp_path / "models.json"
    contest.write_text(json.dumps({"roles": {r: f"contest/{r}-model" for r in ROLES}}),
                       encoding="utf-8")
    agents = tmp_path / "agents"
    agents.mkdir()
    for f in ("数模审稿人.md", "数模视觉审查.md", "数模编辑.md", "数模专家.md"):
        (agents / f).write_text("---\nmodel: host/wrong-model\n---\n", encoding="utf-8")
    monkeypatch.setenv("ACAT_CONTEST_MODELS", str(contest))
    monkeypatch.setenv("OPENCODE_AGENTS_DIR", str(agents))

    models = load_configured_role_models()
    assert models == {r: f"contest/{r}-model" for r in ROLES}
    assert set(model_config_provenance().values()) == {"contest_models"}


def test_fallback_to_agents_per_role(tmp_path, monkeypatch):
    """配置槽只填一个角色 → 该角色用配置槽，其余回退宿主 agents 目录。"""
    contest = tmp_path / "models.json"
    contest.write_text(json.dumps({"roles": {"visual_reviewer": "glm/glm-vision-flash"}}),
                       encoding="utf-8")
    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "数模审稿人.md").write_text("---\nmodel: host/reviewer-x\n---\n", encoding="utf-8")
    monkeypatch.setenv("ACAT_CONTEST_MODELS", str(contest))
    monkeypatch.setenv("OPENCODE_AGENTS_DIR", str(agents))

    models = load_configured_role_models()
    assert models["visual_reviewer"] == "glm/glm-vision-flash"
    assert models["reviewer"] == "host/reviewer-x"
    assert models["editor"] == ""
    prov = model_config_provenance()
    assert prov["visual_reviewer"] == "contest_models"
    assert prov["reviewer"] == "opencode_agents"
    assert prov["editor"] == "none"


def test_missing_slot_file_degrades_to_agents(tmp_path, monkeypatch):
    monkeypatch.setenv("ACAT_CONTEST_MODELS", str(tmp_path / "not_exist.json"))
    monkeypatch.setenv("OPENCODE_AGENTS_DIR", str(tmp_path / "no_agents"))
    assert load_configured_role_models() == {r: "" for r in ROLES}


# ---------------- B. strict 门禁联动 ----------------

def _review_files(ws: Path):
    for name in ("COMP_REVIEW.md", "VISUAL_REVIEW.md", "EDITOR_CHANGELOG.md", "FINAL_REVIEW.md"):
        (ws / name).write_text(f"# {name}\n", encoding="utf-8")
    (ws / "COMP_REVIEW_VERDICT.json").write_text('{"findings": [], "fatal_count": 0}', encoding="utf-8")
    (ws / "VISUAL_REVIEW_VERDICT.json").write_text(
        '{"findings": [], "fatal_count": 0, "status": "pass"}', encoding="utf-8")
    (ws / "FINAL_REVIEW_VERDICT.json").write_text('{"findings": [], "fatal_count": 0}', encoding="utf-8")


def _provenance(ws: Path, models: dict) -> dict:
    files = {"reviewer": "COMP_REVIEW_VERDICT.json",
             "visual_reviewer": "VISUAL_REVIEW_VERDICT.json",
             "editor": "EDITOR_CHANGELOG.md",
             "final_reviewer": "FINAL_REVIEW_VERDICT.json"}
    roles = {}
    for role, fname in files.items():
        roles[role] = {
            "session_id": f"sess_{role}", "model": models[role],
            "output_file": fname, "completed_at": "2026-09-09T00:00:00+00:00",
            "output_sha256": hashlib.sha256((ws / fname).read_bytes()).hexdigest(),
        }
    return {"schema_version": 1, "roles": roles}


def test_strict_blocks_against_contest_slot_model(tmp_path, monkeypatch):
    """比赛时配置槽填了模型 → strict 比对硬拦截（防线不因去预设而失效）。"""
    contest = tmp_path / "models.json"
    contest.write_text(json.dumps({"roles": {r: "contest/right-model" for r in ROLES}}),
                       encoding="utf-8")
    monkeypatch.setenv("ACAT_CONTEST_MODELS", str(contest))
    _review_files(tmp_path)
    models = {r: "contest/right-model" for r in ROLES}
    models["reviewer"] = "contest/wrong-model"
    (tmp_path / "REVIEW_EXECUTION_EVIDENCE.json").write_text(
        json.dumps(_provenance(tmp_path, models)), encoding="utf-8")

    result = QualityGate(tmp_path).check_review_evidence("full", strict_model_match=True)
    assert result["ok"] is False, result.get("reason")
    assert "wrong-model" in result.get("reason", "")


def test_strict_warns_without_blocking_when_unconfigured(tmp_path, monkeypatch):
    """两处皆空（未做比赛配置）→ strict 无从比对：warn 留痕、不阻断、更不默认放行成静默。"""
    monkeypatch.setenv("ACAT_CONTEST_MODELS", str(tmp_path / "absent.json"))
    monkeypatch.setenv("OPENCODE_AGENTS_DIR", str(tmp_path / "no_agents"))
    _review_files(tmp_path)
    models = {r: "whatever/model-at-contest" for r in ROLES}
    (tmp_path / "REVIEW_EXECUTION_EVIDENCE.json").write_text(
        json.dumps(_provenance(tmp_path, models)), encoding="utf-8")

    result = QualityGate(tmp_path).check_review_evidence("full", strict_model_match=True)
    assert result["ok"] is True, "未配置时不得拿假想模型阻断"
    assert any("无配置模型" in w for w in result.get("warnings", []))


# ---------------- C. ZCode L1 hook ----------------

HOOK = SUITE_ROOT / "hooks" / "zcode_audit_l1.py"


def _run_hook(payload: str, mode: str, tmp_path: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "ZCODE_PROJECT_DIR": str(tmp_path)}
    return subprocess.run([sys.executable, str(HOOK), mode],
                          input=payload, capture_output=True, text=True, env=env, timeout=30)


def test_hook_records_tool_call_in_plugin_format(tmp_path):
    p = _run_hook(json.dumps({"hook_event_name": "PreToolUse", "session_id": "s1",
                              "tool_name": "Bash",
                              "tool_input": {"command": "python tools/check_provenance.py"}}),
                  "pre", tmp_path)
    assert p.returncode == 0
    line = json.loads((tmp_path / ".engine" / "audit" / "operations.jsonl")
                      .read_text(encoding="utf-8").splitlines()[-1])
    assert line["type"] == "tool_call" and line["tool"] == "bash"
    assert line["detail"]["command"] == "python tools/check_provenance.py"
    assert line["sessionID"] == "s1" and "ts" in line


def test_hook_denies_git_add_all_with_exit2(tmp_path):
    p = _run_hook(json.dumps({"hook_event_name": "PreToolUse", "session_id": "s1",
                              "tool_name": "Bash",
                              "tool_input": {"command": "cd x; git add -A && git commit"}}),
                  "pre", tmp_path)
    assert p.returncode == 2, "PreToolUse deny 约定 = exit 2"
    assert "逐文件点名" in p.stderr
    line = json.loads((tmp_path / ".engine" / "audit" / "operations.jsonl")
                      .read_text(encoding="utf-8").splitlines()[-1])
    assert line["type"] == "permission" and line["event"] == "deny", "拦截必须留痕"


def test_hook_does_not_deny_bare_mention(tmp_path):
    p = _run_hook(json.dumps({"hook_event_name": "PreToolUse", "session_id": "s1",
                              "tool_name": "Bash",
                              "tool_input": {"command": 'echo "git add . is banned"'}}),
                  "pre", tmp_path)
    assert p.returncode == 0, "echo 里提及不得误伤"


def test_hook_records_result_and_failure(tmp_path):
    _run_hook(json.dumps({"hook_event_name": "PostToolUse", "session_id": "s1",
                          "tool_name": "Edit",
                          "tool_input": {"file_path": "D:/a.md", "old_string": "x",
                                         "new_string": "yy"}}), "post", tmp_path)
    _run_hook(json.dumps({"hook_event_name": "PostToolUseFailure", "session_id": "s1",
                          "tool_name": "Bash", "tool_input": {"command": "false"},
                          "error": "exit 1"}), "fail", tmp_path)
    ops = tmp_path / ".engine" / "audit" / "operations.jsonl"
    lines = [json.loads(l) for l in ops.read_text(encoding="utf-8").splitlines()]
    ok_line = lines[0]
    assert ok_line["type"] == "tool_result" and ok_line["ok"] is True
    fail_line = lines[1]
    assert fail_line["ok"] is False and "exit 1" in fail_line["detail"]["error"]
    # audit_store 兼容读取（同格式即同工具）
    from engine.audit_store import AuditStore
    store = AuditStore(tmp_path)
    s = store.stats()
    assert s["tool_results"] == 2 and s["failed_tool_calls"] == 1


def test_hook_never_breaks_session_on_garbage(tmp_path):
    p = _run_hook("not json at all {{{", "post", tmp_path)
    assert p.returncode == 0, "任何异常输入都必须静默 0，绝不打断主控会话"


# ---------------- D. hook 注册契约 ----------------

def test_zcode_config_registers_l1_hooks():
    cfg = json.loads((REPO_ROOT / ".zcode" / "config.json").read_text(encoding="utf-8"))
    hooks = cfg["hooks"]
    assert hooks["enabled"] is True, "配置文件 hooks 默认关闭——必须显式 enabled"
    for event in ("PreToolUse", "PostToolUse", "PostToolUseFailure"):
        entries = hooks["events"][event]
        assert any(h["type"] == "process" for e in entries for h in e["hooks"])
    script = "${ZCODE_PROJECT_DIR}/科研工具箱/hooks/zcode_audit_l1.py"
    for event in ("PreToolUse", "PostToolUse", "PostToolUseFailure"):
        found = [h for e in hooks["events"][event] for h in e["hooks"] if script in h["args"][0]]
        assert found, f"{event} 未注册审计脚本"
    assert HOOK.is_file()
