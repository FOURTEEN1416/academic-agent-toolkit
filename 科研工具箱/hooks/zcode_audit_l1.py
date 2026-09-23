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

设计铁律（fail-open，2026-09-09 锁死事故后加固）：宿主 hook 语义为
"exit 0 = 放行 / exit 2 = deny / 其他非零 = 报错"。而 Windows 上 python 找不到
脚本文件时的退出码**恰好也是 2**——hook 进程层面的"自身起不来"会被宿主误读成
"规则拦截"，导致全部工具调用被硬断（2026-09-09 会话锁死事故根因）。因此：
  1. 脚本自身任何异常（含 main() 崩溃）→ stderr 写警告 + exit 0 放行，
     严格区分"hook 故障"（fail-open，绝不拦）与"规则拦截"（唯一 exit 2 出口，
     仅 _DENY_RULES 命中且必须留痕 permission/deny 事件）；
  2. 引导器层 fail-open（2026-09-10 定稿根治）："python 找不到/起不了脚本"发生
     在本脚本**之外**，脚本内 fail-open 物理上没机会执行，故宿主注册不得用
     「python <脚本路径> <mode>」，改为「python -c <内联引导器> <mode>」——
     `-c` 进程永远能启动，"脚本定位"被搬进 python 内部，由引导器自身
     try/except 兜底 fail-open，整类 exit-2 误判物理消失。定位顺序：
       a. env ZCODE_PROJECT_DIR/CLAUDE_PROJECT_DIR → <root>/科研工具箱/hooks/本文件；
       b. os.getcwd() 逐级上溯到盘根，第一个含上述相对路径的目录。
     双 cwd 故障史（a/b 各自对应的复现场景）：
       - 漂出仓库（2026-09-09）：config 写相对路径 + shell 持久 cwd 漂出仓库根
         → python "can't open file" 退出码恰为 2 → 宿主误判 deny → 全会话锁死；
       - 漂进仓库子目录（2026-09-10）：${ZCODE_PROJECT_DIR} 变量式写法在 cd 进
         科研工具箱/ 后展开成双重拼接 科研工具箱/科研工具箱/hooks/... → 同样
         起不来 exit 2 再锁死——变量展开在子目录 cwd 下不可靠，已弃用。
     引导器任何一步失败（找不到/加载失败/执行异常）→ stderr 一行警告 + exit 0
     放行；exit 2 唯一合法来源仍是 _DENY_RULES。引导器契约（保持随仓可移植，
     禁写死盘符）见 tests/test_zcode_host_compat.py D 段（双 cwd 定位 / 无仓库
     fail-open / deny 经 runpy 透传保真）——注册配置不入库，重注册按该契约本地自建。

用法（宿主 hooks 注册——注册配置不入库，按 D 段契约本地注册；也可手动喂 stdin 测试）：
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


def _cli() -> int:
    """fail-open 入口：main() 崩溃 → 警告 + 0（放行），绝不让审计钩子弄挂主控会话。

    exit 2 只有唯一来源：_DENY_RULES 命中后的主动 deny。SystemExit 直接透传
    （保住 main() 的 2 / 0 语义），BaseException 兜底覆盖 KeyboardInterrupt 等极端情况。
    """
    try:
        return main()
    except SystemExit:
        raise
    except BaseException as exc:  # noqa: BLE001 — 审计钩子自身故障绝不拦截主控
        try:
            print(f"[zcode_audit_l1] hook 内部故障，fail-open 放行（勿当作规则拦截）: {exc!r}",
                  file=sys.stderr)
        except Exception:
            pass
        return 0


if __name__ == "__main__":
    sys.exit(_cli())
