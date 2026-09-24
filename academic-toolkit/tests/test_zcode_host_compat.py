"""ZCode 宿主适配面测试（2026-09-24 拆分后收窄为 C/D 两段）。

⚠️ 拆分注记（2026-09-24 审计裁决 D3）：原 A 段（模型三级解析）与 B 段（strict 门禁
联动）是 **engine.quality_gates 的宿主无关契约**，已迁出至
`test_model_config_contract.py`——避免将来"去宿主化"整文件删除时连带丢掉泛化守卫。
本文件只保留 ZCode 专有面：

  C. ZCode L1 hook 脚本（zcode_audit_l1.py）的落账/拦截/容错行为与 audit_store 格式兼容；
  D. .zcode/config.json hooks 注册契约（enabled、三事件、脚本存在）——**冻结契约快照**。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

SUITE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SUITE_ROOT.parent
sys.path.insert(0, str(SUITE_ROOT))

# ---------------- C. ZCode L1 hook ----------------

HOOK = SUITE_ROOT / "hooks" / "zcode_audit_l1.py"


def _outside_repo_dir(tmp_path: Path, sub: str) -> Path:
    """返回一个**确在仓库外**的目录（供"cwd 漂出仓库"场景使用）。

    ⚠️ 不能只依赖 pytest 的 tmp_path：basetemp 可能落在**仓库内**
    （如 `--basetemp=dev-docs/_pt_tmp`），此时"仓库外 cwd"前提不成立，用例会以
    难以定位的形态失败（2026-09-23 审计实测：仓内 basetemp 下本文件 2 项必红：
    `test_hook_passes_from_foreign_cwd` 的前提断言、`test_bootstrap_fails_open_
    outside_any_repo` 的"定位失败"留痕断言；默认 basetemp 下 23 项全绿）。
    basetemp 在仓内时自动回退到系统临时目录，保持用例意图（cwd 在仓库外）不变。
    """
    base = tmp_path
    if str(base.resolve()).startswith(str(REPO_ROOT.resolve())):
        base = Path(tempfile.gettempdir()) / f"acat-outside-{os.getpid()}"
    d = base / sub
    d.mkdir(parents=True, exist_ok=True)
    return d


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
    foreign_cwd = _outside_repo_dir(tmp_path, "somewhere/else")
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


# ---------------- D. hook 注册契约（⚠️ 冻结契约快照：hooks 已按用户裁定保持清除态，
# 工作区 config 缺席时校验 git 历史定稿版——"将来重注册照此契约"的**有意冻结**，
# 并非活文档失真；校验逻辑见 _hook_contract_cfg 的动态锚点解析） ----------------

_HOOK_MODES = {"PreToolUse": "pre", "PostToolUse": "post", "PostToolUseFailure": "fail"}
_VALID_HOOK_FIELDS = {"type", "command", "args", "timeoutMs", "statusMessage"}
_VALID_EVENTS = {"SessionStart", "UserPromptSubmit", "PreToolUse", "PermissionRequest",
                 "PostToolUse", "PostToolUseFailure", "Stop"}


def _hook_contract_cfg() -> dict:
    """hook 契约的配置源解析（2026-09-10 用户裁定：hooks 保持清除态；
    2026-09-23 起 .zcode/config.json 不入库）。

    工作区 config 若存在且含 hooks 块（本地已注册）→ 直接按契约校验（活契约，注册错了必红）；
    文件缺席或为"清除态"（仅剩 mcp）→ 回退 git 定稿版校验引导器契约
    （动态解析：取"最后一个 .zcode/config.json 含 hooks 块的提交"，注册形态冻结在该历史点，
    将来重注册照此契约）；两处皆无注册版 → skip（本文件行为测试仍守着脚本本体）。

    2026-09-23 收尾修复：此前硬编码 `4ef9c55^` 锚点——该短哈希随历史演进失效致 6 项
    skip；改动态解析，对历史重写免疫。
    """
    try:
        cfg = json.loads((REPO_ROOT / ".zcode" / "config.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, NotADirectoryError):
        cfg = {}
    if "hooks" in cfg:
        return cfg
    # 动态解析：按时间倒序列出触及 .zcode/config.json 的提交，取第一个能从其
    # blob 中解出含 hooks 块的版本（改名前最后含注册版的提交即冻结契约）。
    log = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "log", "--format=%H", "--", ".zcode/config.json",
         "科研工具箱/.zcode/config.json"],
        capture_output=True, text=True, encoding="utf-8", timeout=30)
    for sha in [s.strip() for s in (log.stdout or "").splitlines() if s.strip()]:
        show = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "show", f"{sha}:.zcode/config.json"],
            capture_output=True, text=True, encoding="utf-8", timeout=30)
        if show.returncode != 0:
            continue
        try:
            candidate = json.loads(show.stdout)
        except ValueError:
            continue
        if "hooks" in candidate:
            return candidate
    pytest.skip("hooks 已按用户裁定清除且 git 历史无注册版（重注册须按本段契约）")
    return cfg


def test_zcode_config_registers_l1_hooks():
    cfg = _hook_contract_cfg()
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
    cfg = _hook_contract_cfg()
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
    cfg = _hook_contract_cfg()
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
    cfg = _hook_contract_cfg()
    code = cfg["hooks"]["events"]["PreToolUse"][0]["hooks"][0]["args"][1]
    # 冻结契约定稿于 2026-09-23 改名前（路径字面量为 科研工具箱/hooks）；
    # 套件目录更名 academic-toolkit 后，行为测试按当前布局换算路径字面量，
    # 契约本体（结构/事件/机制）仍以 git 历史冻结版为准。
    return code.replace("科研工具箱", "academic-toolkit")


def _fake_repo(tmp_path: Path) -> Path:
    """构造含 academic-toolkit/hooks/zcode_audit_l1.py 的伪仓库。

    脚本 _audit_dir 在无 env 时回退 __file__.parents[2]，审计目录恰落在伪仓库根。
    """
    hook_dir = tmp_path / "academic-toolkit" / "hooks"
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
    """deny 语义经引导器+runpy 必须保真：exit 2 透传 + 治理理由 + permission 留痕。"""
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
    assert "定位失败" in p.stderr, "fail-open 必须 stderr 警告留痕（宿主日志可查）"
