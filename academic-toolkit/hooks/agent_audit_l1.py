#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""agent_audit_l1.py — 通用 L1 拦截式审计钩子。

用途：把 PreToolUse / PostToolUse / PostToolUseFailure 三类工具事件落到
`<项目根>/.engine/audit/operations.jsonl`，供审计报告与证据链交叉核对。

事件载荷（stdin JSON）：
  {"hook_event_name": "...", "session_id": "...", "tool_name": "...",
   "tool_input": {...}, "tool_response": {...}}
`filePath` / `file_path` 两套字段命名均可。

拦截策略（PreToolUse，exit 2 = deny，stderr 为理由）：
  - `git add .` / `git add -A` / `git add --all` → 拒绝（治理铁律：逐文件点名）。
  - 其余一律放行（本钩子默认只记录不干预；扩展拦截规则在 _DENY_RULES 增加）。

设计铁律（fail-open）：
  1. 脚本自身任何异常（含 main() 崩溃）→ stderr 写警告 + exit 0 放行，
     严格区分“钩子故障”（fail-open，绝不拦）与“规则拦截”（唯一 exit 2 出口，
     仅 _DENY_RULES 命中且必须留痕 permission/deny 事件）；
  2. 引导器层 fail-open：脚本定位与执行异常一律 exit 0，绝不让审计钩子
     把驱动会话整体阻断。引导器代码见 `--print-bootstrap`，可嵌入任意
     外部工具事件注册配置。

用法（也可手动喂 stdin 测试）：
  echo '<hook json>' | python agent_audit_l1.py pre|post|fail
  python agent_audit_l1.py --print-bootstrap
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# 工具名 → 审计存储的规范小写名。
TOOL_MAP = {
    "Bash": "bash", "Read": "read", "Write": "write", "Edit": "edit",
    "ApplyPatch": "edit", "Grep": "grep", "Glob": "glob",
    "Agent": "task", "Task": "task", "Skill": "skill",
    "WebFetch": "webfetch", "TodoWrite": "todowrite",
}

HOOK_FILENAME = "agent_audit_l1.py"
PROJECT_DIR_ENV = "ACAT_PROJECT_DIR"


def _clip(v, n: int = 500) -> str:
    if v is None:
        return ""
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    return s[:n] + "...[TRUNC]" if len(s) > n else s


def _pick(d: dict, *keys, default=""):
    """按候选键取第一个非空值（兼容 filePath / file_path 两套命名）。"""
    for k in keys:
        if isinstance(d, dict) and d.get(k) not in (None, ""):
            return d[k]
    return default


def _extract_detail(tool: str, args: dict) -> dict:
    """可审计要点（不记录敏感全文，只记长度）。"""
    if tool == "bash":
        return {"command": _clip(_pick(args, "command"))}
    if tool == "edit":
        return {"filePath": _pick(args, "filePath", "file_path"),
                "oldLen": len(str(_pick(args, "oldString", "old_string", default=""))),
                "newLen": len(str(_pick(args, "newString", "new_string", default="")))}
    if tool == "write":
        return {"filePath": _pick(args, "filePath", "file_path"),
                "contentLen": len(str(_pick(args, "content", default="")))}
    if tool == "read":
        return {"filePath": _pick(args, "filePath", "file_path"),
                "offset": _pick(args, "offset", default=None),
                "limit": _pick(args, "limit", default=None)}
    if tool == "grep":
        return {"pattern": _clip(_pick(args, "pattern")), "path": _pick(args, "path"),
                "include": _pick(args, "include", "glob")}
    if tool == "glob":
        return {"pattern": _pick(args, "pattern", "glob")}
    if tool == "skill":
        return {"skillName": _pick(args, "name", "skill")}
    if tool == "task":
        return {"subagentType": _pick(args, "subagent_type", "subagentType"),
                "description": _clip(_pick(args, "description"), 300)}
    if tool == "webfetch":
        return {"url": _pick(args, "url")}
    if tool == "todowrite":
        return {"todos": _clip(_pick(args, "todos"), 400)}
    return {"args": _clip(args, 400)}


# PreToolUse 拦截规则：(编译好的正则, 拒绝理由)。仅拦治理铁律已明文禁止的命令。
# git 必须位于命令段起始（串首或 ; & | 分隔符后），避免误伤 echo/文档示例等场景。
_DENY_RULES = [
    (re.compile(r"(?:^|[;&|]\s*)git\s+add\s+(?:\.|-A|--all)(?:\s|$)"),
     "治理铁律：禁止 git add . / -A / --all，请逐文件点名 add（见全局 AGENTS.md 删除与 Git 纪律）"),
]


def _audit_dir() -> Path:
    root = os.environ.get(PROJECT_DIR_ENV)
    if root:
        base = Path(root)
    else:
        # hooks/ 的上上级 = 仓库根（academic-toolkit/hooks/x.py → repo root）
        base = Path(__file__).resolve().parents[2]
    return base / ".engine" / "audit"


def main() -> int:
    mode = (sys.argv[1] if len(sys.argv) > 1 else "post").lower()
    if mode in ("--print-bootstrap", "print-bootstrap"):
        print(bootstrap_code())
        return 0
    raw = sys.stdin.read() if not sys.stdin.isatty() else ""
    if not raw.strip():
        return 0
    try:
        payload = json.loads(raw)
    except ValueError:
        # 非 JSON 载荷：落一行 raw 以便排查（不打断会话）
        entry = {"type": "hook_unparsed", "event": mode, "detail": _clip(raw, 300)}
        _write(entry)
        return 0

    tool_name = str(payload.get("tool_name") or payload.get("toolName") or "unknown")
    tool = TOOL_MAP.get(tool_name, tool_name.lower())
    args = payload.get("tool_input") or payload.get("toolInput") or {}
    session = str(payload.get("session_id") or payload.get("sessionID") or "")
    event_name = str(payload.get("hook_event_name") or "")

    # PreToolUse 拦截（deny = exit 2，stderr 给理由；仅白名单治理规则）
    if mode == "pre" or event_name == "PreToolUse":
        if tool == "bash":
            cmd = str(_pick(args, "command", default=""))
            for rule, reason in _DENY_RULES:
                if rule.search(cmd):
                    print(reason, file=sys.stderr)
                    # deny 也要留痕：记录被拦截的调用本身
                    _write({"type": "permission", "event": "deny", "tool": tool,
                            "sessionID": session, "detail": {"command": _clip(cmd), "reason": reason}})
                    return 2
        _write({"type": "tool_call", "event": "before", "tool": tool,
                "sessionID": session, "detail": _extract_detail(tool, args if isinstance(args, dict) else {})})
        return 0

    ok = mode != "fail" and event_name != "PostToolUseFailure"
    entry = {"type": "tool_result", "event": "after", "tool": tool, "sessionID": session, "ok": ok}
    detail = {}
    if not ok:
        err = _pick(payload, "error", "tool_response", default="")
        detail["error"] = _clip(err, 300)
    entry["detail"] = detail
    _write(entry)
    return 0


def _write(entry: dict) -> None:
    try:
        d = _audit_dir()
        d.mkdir(parents=True, exist_ok=True)
        line = {"ts": datetime.now(timezone.utc).isoformat(), **entry}
        with open(d / "operations.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
    except Exception:
        # 审计写入失败绝不影响驱动会话
        pass


def _cli() -> int:
    """fail-open 入口：main() 崩溃 → 警告 + 0（放行）。

    exit 2 只有唯一来源：_DENY_RULES 命中后的主动 deny。SystemExit 直接透传
    （保住 main() 的 2 / 0 语义），BaseException 兜底覆盖 KeyboardInterrupt 等极端情况。
    """
    try:
        return main()
    except SystemExit:
        raise
    except BaseException as exc:  # noqa: BLE001 — 审计钩子自身故障绝不拦截驱动会话
        try:
            print(f"[agent_audit_l1] 审计钩子内部故障，fail-open 放行（勿当作规则拦截）: {exc!r}",
                  file=sys.stderr)
        except Exception:
            pass
        return 0


def bootstrap_code() -> str:
    """返回可嵌入外部注册配置的内联引导器代码。

    引导器负责把“脚本定位”搬进 Python 进程：先看 PROJECT_DIR_ENV，再从 cwd
    逐级上溯；定位或执行失败一律 stderr 警告 + exit 0，避免进程启动层的
    非零退出被误读成规则拦截。
    """
    return f'''import os, runpy, sys
from pathlib import Path

_rel = Path("academic-toolkit") / "hooks" / "{HOOK_FILENAME}"
try:
    _root = os.environ.get("{PROJECT_DIR_ENV}")
    if _root:
        _script = Path(_root) / _rel
        if not _script.is_file():
            raise FileNotFoundError(str(_script))
    else:
        _here = Path.cwd().resolve()
        for _base in [_here, *_here.parents]:
            _candidate = _base / _rel
            if _candidate.is_file():
                _script = _candidate
                break
        else:
            raise FileNotFoundError(str(_rel))
    runpy.run_path(str(_script), run_name="__main__")
except SystemExit:
    raise
except BaseException as _exc:
    print(f"[agent_audit_l1] 引导器定位失败或执行异常，fail-open 放行（勿当作规则拦截）: {{_exc!r}}",
          file=sys.stderr)
    sys.exit(0)
'''


if __name__ == "__main__":
    sys.exit(_cli())
