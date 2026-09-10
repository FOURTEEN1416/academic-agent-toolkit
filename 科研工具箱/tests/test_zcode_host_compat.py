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
import re
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


@pytest.mark.parametrize("payload", [
    "",                       # 空 stdin
    "\x00\x01\x02binary",     # 二进制垃圾
    "[]",                     # JSON 但非对象
    '{"tool_name": 123, "tool_input": "not-a-dict"}',  # 字段类型错
])
def test_hook_fail_open_on_hostile_inputs(tmp_path, payload):
    p = _run_hook(payload, "pre", tmp_path)
    assert p.returncode == 0, f"恶意/畸形输入必须放行（got {p.returncode}）: {payload[:40]!r}"


def test_hook_fail_open_with_warning_on_internal_crash(tmp_path):
    """main() 自身崩溃 → stderr 警告 + exit 0（fail-open），与 exit 2 规则拦截严格区分。

    2026-09-09 锁死事故教训：宿主把 hook 的非零退出（尤其 exit 2）当 deny；
    python 找不到脚本时退出码恰好也是 2。本测试保证脚本进程活着时唯一 exit 2
    出口是 _DENY_RULES 主动 deny。
    """
    code = (
        "import importlib.util, sys\n"
        f"spec = importlib.util.spec_from_file_location('zah', r'{HOOK}')\n"
        "m = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(m)\n"
        "def boom():\n"
        "    raise RuntimeError('simulated hook crash')\n"
        "m.main = boom\n"
        "sys.exit(m._cli())\n"
    )
    env = {**os.environ, "ZCODE_PROJECT_DIR": str(tmp_path)}
    p = subprocess.run([sys.executable, "-c", code], input="{}", capture_output=True,
                       text=True, env=env, timeout=30)
    assert p.returncode == 0, "内部崩溃必须 fail-open 放行"
    assert "fail-open" in p.stderr, "崩溃必须 stderr 警告留痕（宿主日志可查）"
    assert "simulated hook crash" in p.stderr


def test_hook_passes_from_foreign_cwd(tmp_path):
    """shell cwd 漂到仓库外时 hook 仍放行不阻断（锁死事故的复现场景）。

    脚本路径由 ${ZCODE_PROJECT_DIR} 绝对展开、审计目录由该变量解析，
    均不依赖进程 cwd——cwd 在仓库外不得产生 exit 2。
    """
    foreign_cwd = tmp_path / "somewhere" / "else"
    foreign_cwd.mkdir(parents=True)
    assert not str(foreign_cwd).startswith(str(REPO_ROOT)), "测试前提：cwd 确在仓库外"
    env = {**os.environ, "ZCODE_PROJECT_DIR": str(tmp_path)}
    p = subprocess.run(
        [sys.executable, str(HOOK), "pre"],
        input=json.dumps({"hook_event_name": "PreToolUse", "session_id": "foreign-cwd",
                          "tool_name": "Bash",
                          "tool_input": {"command": "echo from foreign cwd"}}),
        capture_output=True, text=True, cwd=str(foreign_cwd), env=env, timeout=30)
    assert p.returncode == 0, f"仓库外 cwd 不得阻断: rc={p.returncode} stderr={p.stderr[:200]}"
    line = json.loads((tmp_path / ".engine" / "audit" / "operations.jsonl")
                      .read_text(encoding="utf-8").splitlines()[-1])
    assert line["type"] == "tool_call" and line["sessionID"] == "foreign-cwd"


# ---------------- D. hook 注册契约 ----------------

_HOOK_MODES = {"PreToolUse": "pre", "PostToolUse": "post", "PostToolUseFailure": "fail"}
_VALID_HOOK_FIELDS = {"type", "command", "args", "timeoutMs", "statusMessage"}
_VALID_EVENTS = {"SessionStart", "UserPromptSubmit", "PreToolUse", "PermissionRequest",
                 "PostToolUse", "PostToolUseFailure", "Stop"}


def test_zcode_config_registers_l1_hooks():
    cfg = json.loads((REPO_ROOT / ".zcode" / "config.json").read_text(encoding="utf-8"))
    hooks = cfg["hooks"]
    assert hooks["enabled"] is True, "配置文件 hooks 默认关闭——必须显式 enabled"
    for event in _HOOK_MODES:
        entries = hooks["events"][event]
        assert any(h["type"] == "process" for e in entries for h in e["hooks"])
    assert HOOK.is_file()


def test_zcode_config_hook_fields_official_whitelist():
    """process hook 只接受 command/args/timeoutMs/statusMessage（官方 schema 白名单）。

    混入白名单外字段（如 hook 级 enabled）→ 宿主把整个 hook 静默丢弃（pitfall 7），
    L1 审计将无痕失效——2026-09-09 加固时修掉的回归。
    """
    cfg = json.loads((REPO_ROOT / ".zcode" / "config.json").read_text(encoding="utf-8"))
    for event, entries in cfg["hooks"]["events"].items():
        assert event in _VALID_EVENTS, f"非法事件名 {event}（仅七事件受支持）"
        for e in entries:
            for h in e["hooks"]:
                extra = set(h) - _VALID_HOOK_FIELDS
                assert not extra, f"{event} 的 process hook 含白名单外字段 {extra}（会被宿主丢弃）"
                assert h["type"] == "process"


def test_zcode_config_uses_inline_bootstrap():
    """hook 命令必须是 python -c 内联引导器（2026-09-10 定稿根治方案）。

    历史教训：相对路径与 `${ZCODE_PROJECT_DIR}` 变量两类写法都在 cwd 漂移下
    让 python 在脚本运行**之前**以退出码 2（=宿主语义 deny）死去（漂出仓库=
    找不到脚本；漂进仓库子目录=双重拼接），且脚本内 fail-open 物理上没机会
    执行。引导器把"脚本定位"搬进 python：env 项目根 → cwd 逐级上溯；定位/
    执行失败 fail-open 放行；config 保持随仓可移植，禁止回退路径/变量式写法。
    """
    cfg = json.loads((REPO_ROOT / ".zcode" / "config.json").read_text(encoding="utf-8"))
    for event in _HOOK_MODES:
        found = [h for e in cfg["hooks"]["events"][event] for h in e["hooks"]
                 if h.get("type") == "process"]
        assert found, f"{event} 未注册审计 hook"
        hook = found[0]
        assert hook["command"] == "python"
        args = hook["args"]
        assert args[0] == "-c", f"{event} 必须经 -c 引导器启动，勿回退路径/变量式写法"
        assert args[-1] == _HOOK_MODES[event], f"{event} mode 参数错误: {args[-1]}"
        code = args[1]
        assert "runpy" in code, "必须经 runpy 执行审计脚本（SystemExit 透传保真 deny=2）"
        assert "ZCODE_PROJECT_DIR" in code and "CLAUDE_PROJECT_DIR" in code, \
            "必须先探测项目根 env 变量"
        assert ".parents" in code, "必须支持 cwd 逐级上溯定位（仓库子目录 cwd 事故场景）"
        assert "sys.exit(0)" in code, "定位/执行失败必须 fail-open 放行"
        assert not re.search(r"[A-Za-z]:[\\/]", code), \
            "引导器禁止写死盘符绝对路径（config.json 随 git 分发须保持可移植）"


def _bootstrap_code() -> str:
    cfg = json.loads((REPO_ROOT / ".zcode" / "config.json").read_text(encoding="utf-8"))
    return cfg["hooks"]["events"]["PreToolUse"][0]["hooks"][0]["args"][1]


def _fake_repo(tmp_path: Path) -> Path:
    """构造含 科研工具箱/hooks/zcode_audit_l1.py 的伪仓库。

    脚本 _audit_dir 在无 env 时回退 __file__.parents[2]，审计目录恰落在伪仓库根。
    """
    hook_dir = tmp_path / "科研工具箱" / "hooks"
    hook_dir.mkdir(parents=True)
    (hook_dir / "zcode_audit_l1.py").write_text(
        HOOK.read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path


def _strip_project_env(monkeypatch):
    for var in ("ZCODE_PROJECT_DIR", "CLAUDE_PROJECT_DIR"):
        monkeypatch.delenv(var, raising=False)


def test_bootstrap_locates_script_from_repo_subdir_cwd(tmp_path, monkeypatch):
    """双重拼接事故场景回归：cwd 深处、无 env → 引导器上溯定位脚本并正常落账。"""
    fake = _fake_repo(tmp_path)
    deep = fake / "科研工具箱" / "skills"
    deep.mkdir(parents=True)
    _strip_project_env(monkeypatch)
    p = subprocess.run(
        [sys.executable, "-c", _bootstrap_code(), "pre"],
        input=json.dumps({"hook_event_name": "PreToolUse", "session_id": "subdir-cwd",
                          "tool_name": "Bash",
                          "tool_input": {"command": "echo from subdir"}}),
        capture_output=True, text=True, cwd=str(deep), timeout=30)
    assert p.returncode == 0, f"仓库子目录 cwd 不得阻断: rc={p.returncode} err={p.stderr[:200]}"
    line = json.loads((fake / ".engine" / "audit" / "operations.jsonl")
                      .read_text(encoding="utf-8").splitlines()[-1])
    assert line["type"] == "tool_call" and line["sessionID"] == "subdir-cwd"


def test_bootstrap_preserves_deny_exit2_from_subdir_cwd(tmp_path, monkeypatch):
    """deny 语义经引导器+runpy 必须保真：exit 2 透传 + 治理理由 + permission 留痕。"""
    fake = _fake_repo(tmp_path)
    deep = fake / "科研工具箱"
    _strip_project_env(monkeypatch)
    p = subprocess.run(
        [sys.executable, "-c", _bootstrap_code(), "pre"],
        input=json.dumps({"hook_event_name": "PreToolUse", "session_id": "subdir-deny",
                          "tool_name": "Bash",
                          "tool_input": {"command": "git add -A && git commit"}}),
        capture_output=True, text=True, cwd=str(deep), timeout=30)
    assert p.returncode == 2, "经引导器执行后 exit 2（deny）必须透传保真"
    assert "逐文件点名" in p.stderr
    line = json.loads((fake / ".engine" / "audit" / "operations.jsonl")
                      .read_text(encoding="utf-8").splitlines()[-1])
    assert line["type"] == "permission" and line["event"] == "deny", "拦截必须留痕"


def test_bootstrap_fails_open_outside_any_repo(tmp_path, monkeypatch):
    """cwd 漂出仓库且无 env：定位失败 → stderr 警告 + exit 0 放行（绝不 deny）。"""
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    _strip_project_env(monkeypatch)
    p = subprocess.run(
        [sys.executable, "-c", _bootstrap_code(), "pre"],
        input=json.dumps({"hook_event_name": "PreToolUse", "session_id": "foreign",
                          "tool_name": "Bash", "tool_input": {"command": "echo x"}}),
        capture_output=True, text=True, cwd=str(outside), timeout=30)
    assert p.returncode == 0, f"定位失败必须 fail-open 放行: rc={p.returncode}"
    assert "定位失败" in p.stderr, "fail-open 必须 stderr 警告留痕（宿主日志可查）"
