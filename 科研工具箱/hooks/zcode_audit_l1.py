#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""zcode_audit_l1.py — ZCode 宿主的 L1 拦截式审计钩子（OpenCode audit-trail 插件等价物）。

背景（2026-09-09 用户裁定）：比赛以 ZCode 为主控。OpenCode 侧 L1 由
`.opencode/plugins/audit-trail.ts` 逐条记录工具调用（不可绕过）；ZCode 无该插件机制，
但有 hook 事件（PreToolUse / PostToolUse / PostToolUseFailure，宿主层触发、agent 无法跳过），
本脚本把这三个事件落到与 OpenCode 插件**同一格式**的
`<仓库根>/.engine/audit/operations.jsonl`，使 L2/L3 交叉比对
（audit_store.detect_unreported_operations / workflow_cli audit）在 ZCode 下同样生效。

事件载荷（宿主 JSON 经 stdin 传入，Claude-Code 风格 hook input）：
  {"hook_event_name": "...", "session_id": "...", "tool_name": "...",
   "tool_input": {...}, "tool_response": {...}}
字段名按两套命名兼容（tool_input 内 filePath / file_path 均可）。

拦截策略（PreToolUse，exit 2 = deny，stderr 为理由）：
  - `git add .` / `git add -A` / `git add --all` → 拒绝（用户治理铁律：逐文件点名）。
  - 其余一律放行（本钩子默认只记录不干预；扩展拦截规则在 _DENY_RULES 增加）。

设计铁律：脚本自身任何异常都必须静默退出 0——审计钩子绝不能弄挂主控会话。

用法（由 .zcode/config.json hooks 注册，也可手动喂 stdin 测试）：
  echo '<hook json>' | python zcode_audit_l1.py pre|post|fail
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# ZCode/宿主工具名 → 审计存储的规范小写名（与 OpenCode 插件的 tool 字段对齐）
TOOL_MAP = {
    "Bash": "bash", "Read": "read", "Write": "write", "Edit": "edit",
    "ApplyPatch": "edit", "Grep": "grep", "Glob": "glob",
    "Agent": "task", "Task": "task", "Skill": "skill",
    "WebFetch": "webfetch", "TodoWrite": "todowrite",
}


def _clip(v, n: int = 500) -> str:
    if v is None:
        return ""
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    return s[:n] + "...[TRUNC]" if len(s) > n else s


def _pick(d: dict, *keys, default=""):
    """按候选键取第一个非空值（兼容 filePath/file_path 两套命名）。"""
    for k in keys:
        if isinstance(d, dict) and d.get(k) not in (None, ""):
            return d[k]
    return default


def _extract_detail(tool: str, args: dict) -> dict:
    """与 OpenCode 插件 extract() 同构的可审计要点（不记录敏感全文，只记长度）。"""
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


# PreToolUse 拦截规则：(编译好的正则, 拒绝理由)。仅拦用户治理铁律已明文禁止的命令。
# git 必须位于命令段起始（串首或 ; & | 分隔符后），避免误伤 echo/文档示例等场景。
_DENY_RULES = [
    (re.compile(r"(?:^|[;&|]\s*)git\s+add\s+(?:\.|-A|--all)(?:\s|$)"),
     "治理铁律：禁止 git add . / -A / --all，请逐文件点名 add（见全局 AGENTS.md 删除与 Git 纪律）"),
]


def _audit_dir() -> Path:
    root = os.environ.get("ZCODE_PROJECT_DIR") or os.environ.get("CLAUDE_PROJECT_DIR")
    if root:
        base = Path(root)
    else:
        # hooks/ 的上上级 = 仓库根（科研工具箱/hooks/x.py → repo root）
        base = Path(__file__).resolve().parents[2]
    return base / ".engine" / "audit"


def main() -> int:
    mode = (sys.argv[1] if len(sys.argv) > 1 else "post").lower()
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
        # 审计写入失败绝不影响主控会话
        pass


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
