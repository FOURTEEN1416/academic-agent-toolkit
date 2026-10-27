"""通用 L1 审计钩子行为与引导器契约测试（14 例：11 行为 + 3 引导器）。

覆盖：
  A. PreToolUse / PostToolUse / PostToolUseFailure 落账格式、治理拦截与 fail-open；
  B. 内联引导器的脚本定位、deny 透传与仓库外 fail-open。

本文件不引用任何产品名或产品注册路径；审计存储格式与 engine.audit_store 兼容。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SUITE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SUITE_ROOT.parent
sys.path.insert(0, str(SUITE_ROOT))

HOOK = SUITE_ROOT / "hooks" / "agent_audit_l1.py"


def _outside_repo_dir(tmp_path: Path, sub: str) -> Path:
    """返回一个确在仓库外的目录（供“cwd 漂出仓库”场景使用）。

    pytest 的 basetemp 可能落在仓库内；此时自动回退到系统临时目录，保持用例
    意图（cwd 在仓库外）不变。
    """
    base = tmp_path
    if str(base.resolve()).startswith(str(REPO_ROOT.resolve())):
        base = Path(tempfile.gettempdir()) / f"acat-outside-{os.getpid()}"
    d = base / sub
    d.mkdir(parents=True, exist_ok=True)
    return d


def _run_hook(payload: str, mode: str, tmp_path: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "ACAT_PROJECT_DIR": str(tmp_path)}
    return subprocess.run([sys.executable, str(HOOK), mode],
                          input=payload, capture_output=True, text=True, env=env, timeout=30)


def _last_line(tmp_path: Path) -> dict:
    path = tmp_path / ".engine" / "audit" / "operations.jsonl"
    return json.loads(path.read_text(encoding="utf-8").splitlines()[-1])


# ---------------- A. 钩子行为（11 例） ----------------

def test_hook_records_tool_call_in_audit_format(tmp_path):
    p = _run_hook(json.dumps({"hook_event_name": "PreToolUse", "session_id": "s1",
                              "tool_name": "Bash",
                              "tool_input": {"command": "python tools/check_provenance.py"}}),
                  "pre", tmp_path)
    assert p.returncode == 0
    line = _last_line(tmp_path)
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
    line = _last_line(tmp_path)
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
    path = tmp_path / ".engine" / "audit" / "operations.jsonl"
    lines = [json.loads(item) for item in path.read_text(encoding="utf-8").splitlines()]
    assert lines[0]["type"] == "tool_result" and lines[0]["ok"] is True
    assert lines[1]["ok"] is False and "exit 1" in lines[1]["detail"]["error"]
    from engine.audit_store import AuditStore
    stats = AuditStore(tmp_path).stats()
    assert stats["tool_results"] == 2 and stats["failed_tool_calls"] == 1


def test_hook_never_breaks_session_on_garbage(tmp_path):
    p = _run_hook("not json at all {{{", "post", tmp_path)
    assert p.returncode == 0, "任何异常输入都必须静默 0，绝不打断驱动会话"


def test_hook_fail_open_on_empty_stdin(tmp_path):
    p = _run_hook("", "pre", tmp_path)
    assert p.returncode == 0


def test_hook_fail_open_on_binary_input(tmp_path):
    p = _run_hook("\x00\x01\x02binary", "pre", tmp_path)
    assert p.returncode == 0


def test_hook_fail_open_on_non_object_json(tmp_path):
    p = _run_hook("[]", "pre", tmp_path)
    assert p.returncode == 0


def test_hook_fail_open_on_wrong_field_types(tmp_path):
    p = _run_hook('{"tool_name": 123, "tool_input": "not-a-dict"}', "pre", tmp_path)
    assert p.returncode == 0


def test_hook_fail_open_with_warning_on_internal_crash(tmp_path):
    """main() 自身崩溃 → stderr 警告 + exit 0，与 exit 2 规则拦截严格区分。"""
    code = (
        "import importlib.util, sys\n"
        f"spec = importlib.util.spec_from_file_location('aah', r'{HOOK}')\n"
        "m = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(m)\n"
        "def boom():\n"
        "    raise RuntimeError('simulated hook crash')\n"
        "m.main = boom\n"
        "sys.exit(m._cli())\n"
    )
    env = {**os.environ, "ACAT_PROJECT_DIR": str(tmp_path)}
    p = subprocess.run([sys.executable, "-c", code], input="{}", capture_output=True,
                       text=True, env=env, timeout=30)
    assert p.returncode == 0, "内部崩溃必须 fail-open 放行"
    assert "fail-open" in p.stderr, "崩溃必须 stderr 警告留痕"
    assert "simulated hook crash" in p.stderr


def test_hook_passes_from_foreign_cwd(tmp_path):
    """shell cwd 漂到仓库外时钩子仍放行不阻断（锁死事故的复现场景）。"""
    foreign_cwd = _outside_repo_dir(tmp_path, "somewhere/else")
    assert not str(foreign_cwd).startswith(str(REPO_ROOT)), "测试前提：cwd 确在仓库外"
    env = {**os.environ, "ACAT_PROJECT_DIR": str(tmp_path)}
    p = subprocess.run(
        [sys.executable, str(HOOK), "pre"],
        input=json.dumps({"hook_event_name": "PreToolUse", "session_id": "foreign-cwd",
                          "tool_name": "Bash",
                          "tool_input": {"command": "echo from foreign cwd"}}),
        capture_output=True, text=True, cwd=str(foreign_cwd), env=env, timeout=30)
    assert p.returncode == 0, f"仓库外 cwd 不得阻断: rc={p.returncode} stderr={p.stderr[:200]}"
    line = _last_line(tmp_path)
    assert line["type"] == "tool_call" and line["sessionID"] == "foreign-cwd"


# ---------------- B. 引导器（3 例） ----------------

def _bootstrap_code() -> str:
    p = subprocess.run([sys.executable, str(HOOK), "--print-bootstrap"],
                       capture_output=True, text=True, timeout=30)
    assert p.returncode == 0, p.stderr
    return p.stdout


def _fake_repo(tmp_path: Path) -> Path:
    """构造含 academic-toolkit/hooks/agent_audit_l1.py 的伪仓库。"""
    hook_dir = tmp_path / "academic-toolkit" / "hooks"
    hook_dir.mkdir(parents=True)
    (hook_dir / "agent_audit_l1.py").write_text(
        HOOK.read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path


def _strip_project_env(monkeypatch):
    monkeypatch.delenv("ACAT_PROJECT_DIR", raising=False)


def test_bootstrap_locates_script_from_repo_subdir_cwd(tmp_path, monkeypatch):
    """双重拼接事故场景回归：cwd 深处、无 env → 引导器上溯定位脚本并正常落账。"""
    fake = _fake_repo(tmp_path)
    deep = fake / "academic-toolkit" / "skills"
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
    """deny 语义经引导器 + runpy 必须保真：exit 2 透传 + 治理理由 + permission 留痕。"""
    fake = _fake_repo(tmp_path)
    deep = fake / "academic-toolkit"
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
    outside = _outside_repo_dir(tmp_path, "elsewhere")
    _strip_project_env(monkeypatch)
    p = subprocess.run(
        [sys.executable, "-c", _bootstrap_code(), "pre"],
        input=json.dumps({"hook_event_name": "PreToolUse", "session_id": "foreign",
                          "tool_name": "Bash", "tool_input": {"command": "echo x"}}),
        capture_output=True, text=True, cwd=str(outside), timeout=30)
    assert p.returncode == 0, f"定位失败必须 fail-open 放行: rc={p.returncode}"
    assert "定位失败" in p.stderr, "fail-open 必须 stderr 警告留痕"
