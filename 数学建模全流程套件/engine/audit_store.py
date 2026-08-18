"""审计存储与报告生成 — 读取 plugin 写入的 operations.jsonl，产出结构化审计报告。

审计数据流：
  1. OpenCode plugin（.opencode/plugins/audit-trail.ts）拦截式记录所有工具调用/文件编辑/会话
     → 共享根/.engine/audit/operations.jsonl（JSONL，每行一个事件）
  2. 引擎侧 workflow_store 记录编排事件（started/completed/checkpoint...）→ workflow.sqlite
  3. 本模块汇总两侧 + evidence 声明，生成审计报告并检测"未申报操作"（防绕过）
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_audit_dir(project_root: Path) -> Path:
    """默认审计目录：共享项目根/.engine/audit。"""
    return Path(project_root).resolve() / ".engine" / "audit"


def audit_log_path(project_root: Path) -> Path:
    """参数级审计日志（本套件 audit-trail 插件）。"""
    return default_audit_dir(project_root) / "operations.jsonl"


def official_logger_paths(project_root: Path) -> list[Path]:
    """官方 opencode-logger 的全事件日志（log.jsonl + 轮转文件）。

    兼容两个可能位置：
      1. 项目根/logs/opencode/log.jsonl（官方默认，未配置环境变量时）
      2. 项目根/.engine/audit/log.jsonl（配置 OPENCODE_LOGGER_DIR=.engine/audit 时）
    """
    candidates = [
        default_audit_dir(project_root),
        Path(project_root).resolve() / "logs" / "opencode",
    ]
    files: list[Path] = []
    for directory in candidates:
        files.extend(sorted(directory.glob("log*.jsonl")))
    # 去重保序
    seen = set()
    unique = []
    for p in files:
        key = p.resolve()
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


class AuditStore:
    """读写 operations.jsonl 审计日志（参数级，audit-trail 插件写入）。"""

    def __init__(self, project_root: Path | str):
        self.root = Path(project_root).resolve()
        self.path = audit_log_path(self.root)

    # ---------- 写入 ----------
    def record(self, entry: dict[str, Any]) -> None:
        """追加一条审计事件（与 plugin 同格式）。"""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps({"ts": _now(), **entry}, ensure_ascii=False)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    # ---------- 读取 ----------
    def events(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        events = []
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    events.append({"type": "corrupt_line", "raw": line[:200]})
        return events

    def tool_calls(self) -> list[dict[str, Any]]:
        return [e for e in self.events() if e.get("type") == "tool_call"]

    def tool_results(self) -> list[dict[str, Any]]:
        return [e for e in self.events() if e.get("type") == "tool_result"]

    def file_edits(self) -> list[dict[str, Any]]:
        return [e for e in self.events() if e.get("type") == "file_edit"]

    def sessions(self) -> list[dict[str, Any]]:
        return [e for e in self.events() if e.get("type") == "session"]

    def permissions(self) -> list[dict[str, Any]]:
        return [e for e in self.events() if e.get("type") == "permission"]

    def stats(self) -> dict[str, Any]:
        """统计审计日志概况。"""
        events = self.events()
        tools = Counter(e.get("tool", "?") for e in events if e.get("type") in ("tool_call", "tool_result"))
        skills = Counter(e.get("detail", {}).get("skillName", "?")
                         for e in events if e.get("type") == "tool_call" and e.get("tool") == "skill")
        bash_cmds = [e.get("detail", {}).get("command", "")
                     for e in events if e.get("type") == "tool_call" and e.get("tool") == "bash"]
        edits = [e.get("detail", {}).get("filePath", "")
                 for e in events if e.get("type") == "tool_call" and e.get("tool") in ("edit", "write")]
        failed = [e for e in events if e.get("type") == "tool_result" and e.get("ok") is False]
        return {
            "total_events": len(events),
            "tool_calls": len(self.tool_calls()),
            "tool_results": len(self.tool_results()),
            "file_edits": len(self.file_edits()),
            "sessions": len(self.sessions()),
            "permission_requests": len(self.permissions()),
            "failed_tool_calls": len(failed),
            "tool_breakdown": dict(tools),
            "skill_usage": dict(skills),
            "bash_commands": bash_cmds,
            "edit_targets": sorted(set(edits)),
            "first_event": events[0]["ts"] if events else None,
            "last_event": events[-1]["ts"] if events else None,
        }

    def official_events(self) -> list[dict[str, Any]]:
        """读取官方 opencode-logger 的全事件流（log.jsonl + 轮转文件）。"""
        events = []
        for path in official_logger_paths(self.root):
            try:
                with path.open("r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            events.append(json.loads(line))
                        except json.JSONDecodeError:
                            events.append({"eventType": "corrupt_line", "raw": line[:200]})
            except OSError:
                continue
        events.sort(key=lambda e: e.get("timestamp", ""))
        return events


# =====================================================
# 防绕过检测：比对"实际审计到的操作"与"evidence 申报的命令/产物"
# =====================================================

def _extract_declared_commands(workspace: Path) -> list[str]:
    """从 .engine/evidence/*.json 提取所有申报命令。"""
    ev_dir = workspace / ".engine" / "evidence"
    if not ev_dir.is_dir():
        return []
    commands = []
    for f in sorted(ev_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            ev = data.get("evidence", {})
            commands.extend(c.get("command", "") for c in ev.get("commands", []))
        except Exception:
            continue
    return commands


def _extract_actual_bash_commands(project_root: Path) -> list[str]:
    """从审计日志提取实际执行的 bash 命令。"""
    store = AuditStore(project_root)
    return [e.get("detail", {}).get("command", "") for e in store.tool_calls() if e.get("tool") == "bash"]


def detect_unreported_operations(workspace: Path, project_root: Path) -> dict[str, Any]:
    """检测"实际发生但未申报"的操作（防绕过核心）。

    返回：
      - unreported_bash: 审计日志中有、但 evidence 未申报的命令
      - unreported_edits: 审计日志中 edit/write 的目标文件，不在任何 evidence 的 outputs/inputs 中
      - verdict: ok / warning（存在未申报操作时告警）
    """
    declared_commands = set(_extract_declared_commands(workspace))
    actual_commands = _extract_actual_bash_commands(project_root)

    # 命令归一化：去掉参数差异，比对"命令程序+脚本"级
    def norm(cmd: str) -> str:
        return re.sub(r"\s+", " ", cmd.strip())[:120]

    declared_norm = {norm(c) for c in declared_commands}
    unreported_bash = [c for c in actual_commands if norm(c) not in declared_norm]

    # 编辑目标比对
    store = AuditStore(project_root)
    declared_paths = set()
    ev_dir = workspace / ".engine" / "evidence"
    if ev_dir.is_dir():
        for f in sorted(ev_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                ev = data.get("evidence", {})
                declared_paths.update(ev.get("outputs", []))
                declared_paths.update(ev.get("inputs", []))
            except Exception:
                continue
    edited_files = []
    for e in store.tool_calls():
        detail = e.get("detail", {})
        if e.get("tool") in ("edit", "write") and detail.get("filePath"):
            edited_files.append(detail["filePath"])
    unreported_edits = sorted({p for p in edited_files if p not in declared_paths})

    return {
        "declared_command_count": len(declared_commands),
        "actual_bash_count": len(actual_commands),
        "unreported_bash": unreported_bash,
        "unreported_edit_targets": unreported_edits,
        "verdict": "ok" if not unreported_bash and not unreported_edits else "warning",
    }


# =====================================================
# 审计报告生成
# =====================================================

def generate_audit_report(workspace: Path, project_root: Path,
                          workflow_db: Path | None = None) -> dict[str, Any]:
    """生成完整审计报告：编排事件 + 审计日志 + evidence + 防绕过检测。"""
    store = AuditStore(project_root)
    stats = store.stats()
    official_events = store.official_events()

    # workflow 事件（若存在 SQLite）
    workflow_events = []
    workflow_steps = []
    sqlite_path = Path(workflow_db) if workflow_db is not None else workspace / ".engine" / "workflow.sqlite"
    if sqlite_path.exists():
        try:
            import sqlite3
            con = sqlite3.connect(str(sqlite_path))
            con.row_factory = sqlite3.Row
            for row in con.execute("SELECT * FROM events ORDER BY created_at"):
                workflow_events.append({
                    "type": row["event_type"], "created_at": row["created_at"],
                    "payload": json.loads(row["payload"]),
                })
            for row in con.execute("SELECT name, position, status, updated_at FROM workflow_steps ORDER BY position"):
                workflow_steps.append(dict(row))
            con.close()
        except Exception:
            pass

    # evidence 清单
    evidence_files = []
    ev_dir = workspace / ".engine" / "evidence"
    if ev_dir.is_dir():
        for f in sorted(ev_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                evidence_files.append({
                    "file": f.name,
                    "skill": data.get("evidence", {}).get("skill_name", "?"),
                    "agent": data.get("evidence", {}).get("agent", "?"),
                    "command_count": len(data.get("evidence", {}).get("commands", [])),
                })
            except Exception:
                evidence_files.append({"file": f.name, "skill": "?", "agent": "?", "command_count": 0})

    unreported = detect_unreported_operations(workspace, project_root)

    return {
        "generated_at": _now(),
        "workspace": str(workspace),
        "workflow_database": str(sqlite_path),
        "audit_log": audit_log_path(project_root).as_posix(),
        "official_logger_events": len(official_events),
        "official_logger_files": [p.as_posix() for p in official_logger_paths(project_root)],
        "official_event_types": dict(Counter(e.get("eventType", "?") for e in official_events)),
        "stats": stats,
        "workflow_events": workflow_events,
        "workflow_steps": workflow_steps,
        "evidence_files": evidence_files,
        "unreported_operations": unreported,
        "overall": {
            "audit_trail_present": stats["total_events"] > 0 or len(official_events) > 0,
            "evidence_present": len(evidence_files) > 0,
            "unreported_operations": unreported["verdict"],
        },
    }


def write_audit_report(workspace: Path, project_root: Path, out: Path | None = None,
                       workflow_db: Path | None = None) -> Path:
    """生成并保存审计报告 JSON。"""
    report = generate_audit_report(workspace, project_root, workflow_db=workflow_db)
    target = out or Path(workspace) / "OPERATION_AUDIT_REPORT.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return target
