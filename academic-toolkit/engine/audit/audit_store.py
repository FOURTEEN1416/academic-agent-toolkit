"""审计存储与报告生成 — 读取 plugin 写入的 operations.jsonl，产出结构化审计报告。

审计数据流：
  1. OpenCode plugin（.opencode/plugins/audit-trail.ts）拦截式记录所有工具调用/文件编辑/会话
     → 共享根/.engine/audit/operations.jsonl（JSONL，每行一个事件）
  2. 引擎侧 workflow_store 记录编排事件（started/completed/checkpoint...）→ workflow.sqlite
  3. 本模块汇总两侧 + evidence 声明，生成审计报告并检测"未申报操作"（防绕过）
"""
from __future__ import annotations

import json
import hashlib
import os
import re
import shlex
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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

def _evidence_files(workspace: Path, evidence_paths: set[str] | None = None) -> list[Path]:
    """Use committed references when available; legacy standalone logs stay readable."""
    workspace = Path(workspace).resolve()
    if evidence_paths is None:
        db = workspace / ".engine" / "workflow.sqlite"
        if db.is_file():
            evidence_paths = set()
            import sqlite3
            try:
                con = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True)
                try:
                    for row in con.execute("SELECT payload FROM events WHERE event_type IN ('step_completed', 'step_backfilled')"):
                        payload = json.loads(row[0])
                        evidence_paths.update(str(payload[k]) for k in ("evidence_path", "binding_evidence_path") if payload.get(k))
                finally:
                    con.close()
            except (sqlite3.Error, ValueError, TypeError):
                return []
    files = sorted((workspace / ".engine" / "evidence").glob("*.json"))
    if evidence_paths is None:
        return files
    accepted = {(workspace / p).resolve() for p in evidence_paths}
    return [p for p in files if p.resolve() in accepted and p.resolve().is_relative_to(workspace)]


def _extract_declared_commands(workspace: Path, evidence_paths: set[str] | None = None) -> list[str]:
    """从 .engine/evidence/*.json 提取所有申报命令。"""
    ev_dir = workspace / ".engine" / "evidence"
    if not ev_dir.is_dir():
        return []
    commands = []
    for f in _evidence_files(workspace, evidence_paths):
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


def _workflow_control_call(command: str, workspace: Path, scope: dict[str, Any]) -> str | None:
    """识别单独的、绑定当前库/工作流的控制调用；不证明它已成功执行。

    不接受 shell 拼接、重定向、变量展开、截断记录或任意脚本包装。
    控制调用仍完整展示，产物与状态只能由既有门禁/数据库事件证明。
    """
    if not scope or re.search(r"[;&|<>$`\r\n%]", command) or "[TRUNC]" in command:
        return None
    try:
        tokens = shlex.split(command, posix=False)
    except ValueError:
        return None
    tokens = [t[1:-1] if len(t) >= 2 and t[0] == t[-1] and t[0] in "\"'" else t for t in tokens]
    session_control = _session_control_call(tokens, workspace, scope)
    if session_control:
        return session_control
    if len(tokens) < 4 or tokens[1:3] != ["-m", "engine.workflow_cli"]:
        return None
    executable = tokens[0].replace("\\", "/").rsplit("/", 1)[-1]
    if not re.fullmatch(r"python(?:\d+(?:\.\d+)*)?(?:\.exe)?", executable, re.IGNORECASE):
        return None
    operation = tokens[3]
    options = {
        "final-audit": {"--workspace", "--db", "--wf", "--out", "--evidence-file"},
        "complete": {"--wf", "--db", "--ok", "--artifacts", "--stderr", "--evidence-file",
                     "--step-id", "--attempt-id", "--expected-revision", "--request-id"},
        "preflight": {"--wf", "--db", "--artifacts", "--evidence-file"},
        "backfill": {"--wf", "--db", "--step", "--artifact", "--by", "--note", "--evidence-file"},
        "next": {"--wf", "--db"},
        "retry": {"--wf", "--db", "--by"},
        "approve": {"--checkpoint", "--db", "--by"},
        "promote": {"--wf", "--db", "--root", "--by", "--template"},
        "start": {"--template", "--workspace", "--db", "--params", "--mode", "--candidate"},
        "abandon": {"--wf", "--db", "--reason", "--by"},
    }
    args = tokens[4:]
    if operation not in options or len(args) % 2:
        return None
    parsed = {}
    for key, value in zip(args[::2], args[1::2]):
        if (key not in options[operation] or (key in parsed and key not in {"--artifact", "--root", "--input"})
                or not value or value.startswith("--")):
            return None
        parsed[key] = value

    def same_path(value, target):
        return bool(value) and Path(value).is_absolute() and Path(value).resolve() == Path(target).resolve()

    if not same_path(parsed.get("--db"), scope["database"]):
        return None
    if operation == "approve":
        if parsed.get("--checkpoint") not in scope.get("checkpoint_ids", set()):
            return None
    elif operation == "start":
        # 工作流尚未创建：只校验工作区与数据库归属，不要求 --wf。
        if not same_path(parsed.get("--workspace"), workspace):
            return None
    elif operation == "promote":
        # promote 发生在交付工作流创建前，--wf 指向源 explore 工作流；
        # control_scope 必须显式携带 source_workflow_ids 才认。
        allowed = {str(scope.get("workflow_id") or "")}
        allowed.update(str(value) for value in (scope.get("source_workflow_ids") or []))
        if parsed.get("--wf") not in allowed:
            return None
    elif parsed.get("--wf") != scope["workflow_id"]:
        return None
    if operation == "final-audit":
        if not same_path(parsed.get("--workspace"), workspace):
            return None
        if "--out" in parsed and not any(same_path(parsed["--out"], workspace / name)
                                         for name in ("AUDIT_REPORT.json", "DELIVERY_REPORT.json")):
            return None
    return operation


def _session_control_call(tokens: list[str], workspace: Path, scope: dict) -> str | None:
    """会话包装调用只作控制记录；实际成功仍须由执行表和正常步骤验收证明。"""
    import sqlite3
    if not tokens:
        return None
    executable = tokens[0].replace("\\", "/").rsplit("/", 1)[-1]
    if not re.fullmatch(r"python(?:\d+(?:\.\d+)*)?(?:\.exe)?", executable, re.IGNORECASE):
        return None
    if tokens[1:4] == ["-m", "engine.workflow_cli", "session"]:
        rest = tokens[4:]
    else:
        return None
    if not rest:
        return None
    operation, args = rest[0], rest[1:]
    options = {"context": {"--wf", "--db", "--query", "--audit-root"},
               "read": {"--session", "--kind", "--name", "--member"},
               "write": {"--session", "--path", "--from-file", "--input"},
               "edit": {"--session", "--path", "--changes-file", "--input"},
               "run": {"--session", "--plan"},
               "finish": {"--session", "--review-session"},
               "status": {"--session"},
               "reproduce": {"--session", "--plan", "--candidate"},
               "abandon": {"--session", "--reason", "--by"},
               "review-request": {"--session", "--input", "--output", "--rubric"},
               "review-receive": {"--session", "--task", "--response", "--reviewer", "--host-call-id"}}
    if operation not in options:
        return None
    parsed = {}
    i = 0
    while i < len(args):
        key = args[i]
        if ((operation == "run" and key in {"--finish", "--force"})
                or (operation in {"write", "edit"} and key == "--stdin")):
            i += 1
            continue
        if key not in options[operation] or (key in parsed and key != "--input") or i + 1 >= len(args):
            return None
        parsed[key] = args[i + 1]
        i += 2
    try:
        if operation == "context":
            database = Path(parsed.get("--db", ""))
            if (parsed.get("--wf") != scope["workflow_id"] or not database.is_absolute()
                    or database.resolve() != Path(scope["database"]).resolve()):
                return None
        else:
            ticket_path = Path(parsed.get("--session", ""))
            if (not ticket_path.is_absolute() or not ticket_path.resolve().is_relative_to(
                    workspace.resolve() / ".engine/sessions")):
                return None
            ticket = json.loads(ticket_path.read_text(encoding="utf-8"))
            if (ticket.get("workflow_id") != scope["workflow_id"]
                    or Path(ticket["database"]).resolve() != Path(scope["database"]).resolve()):
                return None
            import sqlite3
            with sqlite3.connect(Path(scope["database"]).resolve().as_uri() + "?mode=ro", uri=True) as con:
                if not con.execute("SELECT 1 FROM workflow_steps WHERE id=? AND workflow_id=? AND attempt_id=?",
                                   (ticket["step_id"], scope["workflow_id"], ticket["attempt_id"])).fetchone():
                    return None
        return "session:" + operation
    except (OSError, ValueError, KeyError, sqlite3.Error):
        return None


def detect_unreported_operations(workspace: Path, project_root: Path, *,
                                 evidence_paths: set[str] | None = None,
                                 candidate_evidence: dict[str, Any] | None = None,
                                 control_scope: dict[str, Any] | None = None) -> dict[str, Any]:
    """检测"实际发生但未申报"的操作（防绕过核心）。

    返回：
      - unreported_bash: 审计日志中有、但 evidence 未申报的命令
      - unreported_edits: 审计日志中 edit/write 的目标文件，不在任何 evidence 的 outputs/inputs 中
      - verdict: ok / warning（存在未申报操作时告警）
    """
    declared_commands = set(_extract_declared_commands(workspace, evidence_paths))
    if candidate_evidence is not None:
        declared_commands.update(c["command"] for c in candidate_evidence["commands"])
    actual_commands = _extract_actual_bash_commands(project_root)

    # 比较完整命令，不截短前缀：长路径后追加另一命令不能冒用已申报操作。
    def norm(cmd: str) -> str:
        return re.sub(r"\s+", " ", cmd.strip())

    declared_norm = {norm(c) for c in declared_commands}
    controls = [{"command": c, "operation": op, "execution_status": "not_attested"}
                for c in actual_commands
                if (op := _workflow_control_call(c, workspace, control_scope or {}))]
    control_commands = {c["command"] for c in controls}
    unreported_bash = [c for c in actual_commands
                       if c not in control_commands and norm(c) not in declared_norm]

    # 编辑目标比对
    store = AuditStore(project_root)
    declared_paths = set()
    ev_dir = workspace / ".engine" / "evidence"
    if ev_dir.is_dir():
        for f in _evidence_files(workspace, evidence_paths):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                ev = data.get("evidence", {})
                declared_paths.update(ev.get("outputs", []))
                declared_paths.update(ev.get("inputs", []))
            except Exception:
                continue
    if candidate_evidence is not None:
        declared_paths.update(candidate_evidence["outputs"])
        declared_paths.update(candidate_evidence["inputs"])
    # L1 宿主常写绝对路径，evidence 契约写相对路径；比较同一工作区规范路径。
    def canonical_path(value):
        path = Path(value)
        return (path if path.is_absolute() else workspace / path).resolve()
    declared_paths = {canonical_path(p) for p in declared_paths}
    edited_files = []
    for e in store.tool_calls():
        detail = e.get("detail", {})
        if e.get("tool") in ("edit", "write") and detail.get("filePath"):
            edited_files.append(detail["filePath"])
    unreported_edits = sorted({p for p in edited_files if canonical_path(p) not in declared_paths})

    return {
        "declared_command_count": len(declared_commands),
        "actual_bash_count": len(actual_commands),
        "workflow_control_calls": controls,
        "unreported_bash": unreported_bash,
        "unreported_edit_targets": unreported_edits,
        "verdict": "ok" if not unreported_bash and not unreported_edits else "warning",
    }


def _parse_event_ts(value: Any) -> datetime | None:
    """宽容解析 L1 事件时间戳（兼容 Z 后缀与 +00:00；naive 视为 UTC）。"""
    text = str(value or "").strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _workflow_window_start(workspace: Path) -> datetime | None:
    """本工作区引擎库中最早 workflow 的创建时刻——L1 事件归属窗口的下界。

    无库/无表/解析失败一律返回 None（不猜测窗口，保持旧宿主行为）。
    """
    db = workspace / ".engine" / "workflow.sqlite"
    if not db.is_file():
        return None
    try:
        import sqlite3
        con = sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            row = con.execute(
                "SELECT created_at FROM workflows ORDER BY created_at ASC LIMIT 1").fetchone()
        finally:
            con.close()
    except Exception:
        return None
    return _parse_event_ts(row[0]) if row else None


def _collected_skill_reads(evidence: dict, database: Path) -> set[str]:
    """独立查询采集事实；不能仅凭evidence里的resource_reads把自述升级为执行事实。"""
    collection = evidence.get("collection") or {}
    if collection.get("source") != "execution-session-v1" or not Path(database).is_file():
        return set()
    import sqlite3
    names = set()
    try:
        with sqlite3.connect(Path(database).resolve().as_uri() + "?mode=ro", uri=True) as con:
            for operation_id in collection.get("operation_ids", []):
                row = con.execute("SELECT payload FROM execution_operations WHERE id=? AND step_id=? "
                    "AND attempt_id=? AND kind='resource' AND status='succeeded'",
                    (operation_id, evidence.get("step_id"), evidence.get("attempt_id"))).fetchone()
                if row:
                    payload = json.loads(row[0])
                    if payload in evidence.get("resource_reads", []) and payload.get("kind") == "skill":
                        names.add(payload["name"])
    except (sqlite3.Error, ValueError, KeyError):
        return set()
    return names


def verify_skill_bindings(workspace: Path, project_root: Path, *,
                          evidence_paths: set[str] | None = None,
                          candidate_action: dict[str, Any] | None = None,
                          candidate_evidence: dict[str, Any] | None = None,
                          workflow_db: Path | None = None) -> dict[str, Any]:
    """技能绑定交叉核验（P4「可验证的强制执行机制」，2026-09-19）。

    为什么需要第二道：`complete_step` 的 skill_binding 闸校验的是 **agent 自己申报的**
    evidence（L3），本质仍是"自述合规"。本函数把同一份声明拿去和 **L1 实际调用记录**
    对账——L1 由宿主 hook / 插件写入，agent 无法跳过：

      - 声明读取主技能 / 必用技能 ⟷ L1 中是否存在该技能的 `skill` 工具调用，
        或对该技能 `SKILL.md` 的 `read` 操作。

    窗口归属（2026-09-26 修复）：L1 日志是全仓共享文件，可能残留**旧宿主/旧赛事**的
    历史事件。以本工作区 .engine/workflow.sqlite 中最早 workflow 创建时刻为下界，
    只把窗口内的宿主 tool_call/tool_result 事件视为"L1 对当届启用"的证据；
    窗口外（含早于本工作区诞生）的事件既不用于证明启用，也不参与绑定匹配。

    三类结论（诚实降级，不伪造通过）：
      - ``unavailable``：窗口内无任何 L1 宿主工具事件（当前宿主未启用 L1）——
        如实标注，不判通过（与仓库根 AGENTS.md「无宿主 hook 记 unavailable、不阻断」对齐）；
      - ``warning``：L1 在窗口内确有宿主事件、但存在"声明了绑定却无对应实际操作"的步骤；
      - ``ok``：全部绑定在窗口内 L1 中可核。

    返回::

        {"verdict", "steps_checked", "unavailable_reason",
         "unverified": [{"step_id", "skill_name", "declared", "missing"}...]}
    """
    ev_dir = workspace / ".engine" / "evidence"
    declared: list[dict[str, Any]] = []
    if ev_dir.is_dir():
        for f in _evidence_files(workspace, evidence_paths):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            action = data.get("action") or {}
            binding = action.get("skill_binding") or {}
            if not isinstance(binding, dict) or not binding:
                continue
            wanted = []
            if binding.get("main_required", True):
                wanted.append(str(binding.get("main") or action.get("skill_name") or "").strip())
            wanted += [str(s).strip() for s in (binding.get("mandatory") or [])]
            wanted = [w for w in wanted if w]
            if wanted:
                declared.append({"step_id": action.get("step_id", f.stem),
                                 "skill_name": action.get("skill_name", ""), "wanted": wanted,
                                 "machine_reads": _collected_skill_reads(data.get("evidence", {}),
                                     workflow_db or workspace / ".engine/workflow.sqlite")})

    if candidate_action:
        binding = candidate_action.get("skill_binding") or {}
        wanted = ([str(binding.get("main") or candidate_action["skill_name"])]
                  if binding and binding.get("main_required", True) else [])
        wanted += list(binding.get("mandatory") or [])
        if wanted:
            declared.append({"step_id": candidate_action["step_id"],
                             "skill_name": candidate_action["skill_name"], "wanted": wanted,
                             "machine_reads": _collected_skill_reads(candidate_evidence or {},
                                 workflow_db or workspace / ".engine/workflow.sqlite")})
    if not declared:
        return {"verdict": "ok", "steps_checked": 0, "unverified": [],
                "unavailable_reason": "无步骤声明技能绑定，无需核验"}

    store = AuditStore(project_root)
    events = store.events()
    window_start = _workflow_window_start(workspace)
    host_events = [e for e in events if e.get("type") in ("tool_call", "tool_result")]
    if window_start is not None:
        host_events = [e for e in host_events
                       if (t := _parse_event_ts(e.get("ts"))) is None or t >= window_start]
    machine_complete = all(set(item["wanted"]) <= item.get("machine_reads", set()) for item in declared)
    if not host_events and machine_complete:
        return {"verdict": "ok", "steps_checked": len(declared), "unverified": [],
                "unavailable_reason": "", "verification_source": "persisted_execution_resource_reads_not_host_L1"}
    if not host_events:
        scope = (f"（窗口={window_start.date()} 起，早于本工作区诞生的旧宿主/旧赛事事件不计入）"
                 if window_start else "")
        return {"verdict": "unavailable", "steps_checked": len(declared), "unverified": [],
                "unavailable_reason": f"L1 审计日志缺失或窗口内无宿主工具事件{scope}"
                                      "（当前宿主未启用 L1 拦截式审计）；"
                                      "绑定声明无法与实际行动对账，如实标记 unavailable 而非判通过"}

    # L1 实际痕迹：skill 工具调用的技能名 + read 操作读过的文件路径
    invoked_skills: set[str] = set()
    read_paths: list[str] = []
    for event in host_events:
        if event.get("type") not in ("tool_call", "tool_result"):
            continue
        tool = str(event.get("tool", ""))
        detail = event.get("detail") or {}
        if tool == "skill":
            name = str(detail.get("skillName") or "").strip()
            if name:
                invoked_skills.add(name.lower().replace("_", "-"))
        elif tool == "read":
            path = str(detail.get("filePath") or "").strip()
            if path:
                read_paths.append(path.lower().replace("\\", "/"))

    def _evidenced(skill: str) -> bool:
        key = skill.lower().replace("_", "-")
        if key in invoked_skills:
            return True
        needle = f"skills/{key}/skill.md"
        return any(needle in p for p in read_paths)

    unverified = []
    for item in declared:
        missing = [s for s in item["wanted"] if not _evidenced(s) and s not in item.get("machine_reads", set())]
        if missing:
            unverified.append({"step_id": item["step_id"], "skill_name": item["skill_name"],
                               "declared": item["wanted"], "missing": missing})
    return {
        "verdict": "warning" if unverified else "ok",
        "steps_checked": len(declared),
        "unverified": unverified,
        "unavailable_reason": "",
    }


# =====================================================
# A2 补丁1：状态-事件一致性核查
# 编排状态（workflow_steps.status）必须能被事件链解释：
#   - 每个 status=completed 的步骤必须存在对应 step_completed 事件；
#   - 每个检查点步骤（has_checkpoint）的完成必须有 checkpoint_approved 事件
#     （blocked 解除必须经用户批准，不允许静默放行）。
# 直改 SQLite 伪造 completed 的事件链缺失，在此被检测并接入交付判定。
# =====================================================

def _check_state_event_consistency(store, workflow_id: str) -> dict[str, Any]:
    """核查最新工作流的状态-事件一致性（事件经 checkpoints.step_id 映射到步骤）。

    "blocked 解除"的判定：步骤存在 state.status=waiting_checkpoint 的检查点
    （即真正进入过检查点等待态，complete_step 的 BLOCKED 分支写入），
    其后续完成必须有 checkpoint_approved 事件。
    """
    violations: list[str] = []
    try:
        steps = store._connection.execute(
            "SELECT id, name, position, status, metadata FROM workflow_steps "
            "WHERE workflow_id = ? ORDER BY position", (workflow_id,)
        ).fetchall()
        checkpoints = store._connection.execute(
            "SELECT step_id, state FROM checkpoints WHERE workflow_id = ?",
            (workflow_id,)
        ).fetchall()
        event_rows = store._connection.execute(
            "SELECT c.step_id AS step_id, e.event_type AS event_type FROM events e "
            "JOIN checkpoints c ON e.checkpoint_id = c.id "
            "WHERE e.workflow_id = ? AND c.workflow_id = ?", (workflow_id, workflow_id)
        ).fetchall()
    except Exception as exc:  # 查询失败按 fail-closed 处理
        return {"checked_steps": 0, "violations": [f"一致性核查查询失败: {exc}"], "ok": False}

    def _entered_blocked(step_id: str) -> bool:
        for cp in checkpoints:
            if cp["step_id"] != step_id:
                continue
            try:
                state = json.loads(cp["state"]) if cp["state"] else {}
            except json.JSONDecodeError:
                state = {}
            if isinstance(state, dict) and state.get("status") == "waiting_checkpoint":
                return True
        return False

    events_by_step: dict[str, set[str]] = {}
    for row in event_rows:
        events_by_step.setdefault(row["step_id"], set()).add(row["event_type"])
    for step in steps:
        try:
            metadata = json.loads(step["metadata"]) if step["metadata"] else {}
        except json.JSONDecodeError:
            metadata = {}
        if not isinstance(metadata, dict):
            metadata = {}
        event_types = events_by_step.get(step["id"], set())
        label = f"步骤[{step['position']}]{step['name']}"
        if step["status"] == "completed":
            if not ({"step_completed", "step_backfilled"} & event_types):
                violations.append(
                    f"{label}: status=completed 但无对应 step_completed 事件"
                    "（疑似绕过引擎直改数据库；合法路径是 workflow_cli complete）")
            if metadata.get("has_checkpoint") and _entered_blocked(step["id"]) \
                    and "checkpoint_approved" not in event_types:
                violations.append(
                    f"{label}: 检查点等待（blocked）未经批准即完成、缺少 checkpoint_approved 事件"
                    "（blocked 解除必须经用户批准；合法路径是 workflow_cli approve）")
    return {"checked_steps": len(steps), "violations": violations, "ok": not violations}


# =====================================================
# A2 补丁2：防绕过检测接入交付判定的工作区归属过滤
# =====================================================

def _workspace_scoped_unreported(workspace: Path, unreported: dict[str, Any]) -> dict[str, list[str]]:
    """把防绕过检测结果过滤为"工作区归属"的未申报操作。

    审计日志（共享根 .engine/audit/operations.jsonl）按项目根聚合了**所有会话**的
    事件：仓库级开发噪声（其他会话的 bash/编辑，如 toolbox 开发、pytest）不属于
    本工作区的交付证据链，若全量拦截，交付判定会永久 blocked（制造 A7-F1 同款
    "永远过不了的闸"）。归属判定规则：
      - 编辑：filePath 为绝对路径且位于工作区内（相对路径视为工作区文件）；
      - bash：命令字符串引用了工作区绝对路径（审计条目无 cwd 字段，属已知精度
        边界，报告中如实披露；跨会话攻击者直改工作区文件通常引用其绝对路径）。
    """
    root = str(Path(workspace).resolve())

    def _in_workspace(path: str) -> bool:
        if not path:
            return False
        candidate = Path(path)
        if not candidate.is_absolute():
            return True
        try:
            candidate.resolve().relative_to(root)
            return True
        except (ValueError, OSError):
            return False

    return {
        "unreported_bash": [c for c in unreported.get("unreported_bash", []) if root in str(c)],
        "unreported_edit_targets": [
            p for p in unreported.get("unreported_edit_targets", []) if _in_workspace(p)
        ],
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
        for f in _evidence_files(workspace):
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
    skill_bindings = verify_skill_bindings(workspace, project_root)

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
        # P4：技能绑定声明 vs L1 实际操作的对账（自述合规 → 可核合规）
        "skill_bindings": skill_bindings,
        "overall": {
            "audit_trail_present": stats["total_events"] > 0 or len(official_events) > 0,
            "evidence_present": len(evidence_files) > 0,
            "unreported_operations": unreported["verdict"],
            "skill_bindings": skill_bindings["verdict"],
        },
    }


def _accepted_coverage(workspace: Path, batches: list[list[dict[str, Any]]]):
    """Fold committed outputs in order; child updates retain sibling coverage.

    A complete parent receipt supersedes its old subtree. New directory receipts
    carry leaf hashes; legacy opaque directories retain their whole-tree check.
    """
    from ..storage.artifact_manifest import ArtifactManifest
    leaves: dict[str, dict[str, Any]] = {}
    directories: dict[str, str] = {}
    errors: dict[str, str] = {}

    def normalize(value):
        path = ArtifactManifest._path(workspace, value)
        if path is None:
            raise ValueError(f"invalid accepted path: {value}")
        # Keep the lexical path so content validation can reject symlinks/junctions.
        relative = Path(os.path.normpath(value)).as_posix()
        return os.path.normcase(relative).replace("\\", "/"), relative

    def below(child, parent):
        return child.startswith(parent + "/") if parent != "." else child != "."

    for entries in batches:
        # Parent first when a single receipt declares both directory and child.
        for artifact in sorted(entries, key=lambda a: len(Path(str(a.get("path", ""))).parts)):
            try:
                key, path = normalize(str(artifact.get("path", "")))
            except (OSError, ValueError, TypeError) as exc:
                errors[str(artifact.get("path", ""))] = str(exc)
                continue
            # Revalidating a whole path replaces only that subtree, never siblings.
            for mapping in (leaves, directories, errors):
                for old in list(mapping):
                    if old == key or below(old, key):
                        mapping.pop(old)
            members = artifact.get("members")
            if members is None:
                leaves[key] = {**artifact, "path": path}
                continue
            directories[key] = path
            if not isinstance(members, dict) or not members:
                errors[key] = f"{path}: invalid directory member receipt"
                continue
            for member, digest in members.items():
                try:
                    leaf_key, leaf_path = normalize(member)
                    if not below(leaf_key, key) or not re.fullmatch(r"[0-9a-fA-F]{64}", str(digest)):
                        raise ValueError("member escapes parent or has invalid SHA-256")
                    leaves[leaf_key] = {"path": leaf_path, "sha256": digest}
                except (OSError, ValueError, TypeError) as exc:
                    errors[key] = f"{path}: {exc}"

    coverage = []
    for parent, path in directories.items():
        members = [a["path"] for key, a in leaves.items() if below(key, parent)]
        coverage.append({"path": path, "members": sorted(members)})
    return leaves, coverage, list(errors.values())


def _accepted_event_batches(checkpoints: list[dict[str, Any]],
                            events: list[dict[str, Any]]) -> tuple[dict[str, list[dict[str, Any]]], set[str]]:
    """Fold step manifests from the event timeline into per-step accepted batches."""
    cp_steps = {c["id"]: c["step_id"] for c in checkpoints}
    accepted_artifacts: dict[str, list[dict[str, Any]]] = {}
    evidence_paths: set[str] = set()
    for event in events:
        if not isinstance(event, dict):
            continue
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            continue
        step_id = cp_steps.get(event.get("checkpoint_id"), "unknown")
        manifest = payload.get("manifest")
        if isinstance(manifest, dict) and manifest.get("artifacts"):
            if event.get("type") in {"step_completed", "step_backfilled"}:
                accepted_artifacts.pop(step_id, None)
                accepted_artifacts[step_id] = list(manifest["artifacts"])
                evidence_paths.update(str(payload[k]) for k in
                                      ("evidence_path", "binding_evidence_path") if payload.get(k))
        if event.get("type") in {"step_failed", "step_retry"}:
            accepted_artifacts.pop(step_id, None)
    return accepted_artifacts, evidence_paths


def accepted_artifacts_by_path(workspace: Path, checkpoints: list[dict[str, Any]],
                               events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Return the latest accepted artifact per logical path (promotion/audit shared).

    Never falls back to filesystem mtime: only event-referenced manifests can
    attest an accepted version.
    """
    batches, _ = _accepted_event_batches(checkpoints, events)
    leaves, _coverage, _errors = _accepted_coverage(workspace, list(batches.values()))
    return leaves


# =====================================================
# G2 candidate readiness：冻结/闭包/复现/审核/批准 五道门
# =====================================================

def _candidate_gate(ok: bool, reason: str = "", *, missing: list[str] | None = None,
                    **detail: Any) -> dict[str, Any]:
    return {"ok": bool(ok), "reason": "" if ok else reason,
            "missing": list(missing or []), **detail}


def _candidate_event_chain_status(store: Any, candidate_id: str) -> dict[str, Any]:
    """Fail-closed wrapper around the store's candidate event chain verifier."""
    verify = getattr(store, "verify_candidate_event_chain", None)
    if not callable(verify):
        return {"ok": False, "broken_at": "store:verify_unavailable", "events": 0}
    try:
        result = verify(str(candidate_id))
    except Exception as exc:  # noqa: BLE001 — unreadable chain must not pass
        return {"ok": False, "broken_at": f"verify_error:{exc}", "events": 0}
    if not isinstance(result, dict):
        return {"ok": False, "broken_at": "store:invalid_verify_result", "events": 0}
    return result


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def _read_sha256(path: Path) -> str:
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return ""


def _candidate_frozen_gate(workspace: Path, project_root: Path,
                           candidate: Any) -> dict[str, Any]:
    """Candidate content and acceptance contract must still match their frozen bytes."""
    acceptance = candidate.acceptance if isinstance(candidate.acceptance, dict) else {}
    if _canonical_sha256(acceptance) != candidate.acceptance_sha256:
        return _candidate_gate(False, "candidate acceptance digest does not match frozen acceptance")
    missing: list[str] = []
    skills_root = Path(project_root) / str(acceptance.get("skills_root") or "academic-toolkit/skills")
    for step in acceptance.get("delivery_steps") or []:
        if not isinstance(step, dict):
            continue
        name = str(step.get("skill_name") or "")
        frozen_sha = str(step.get("skill_sha256") or "")
        if name and frozen_sha:
            current = _read_sha256(skills_root / name / "SKILL.md")
            if current != frozen_sha:
                missing.append(f"skill:{name}")
    rules_root = Path(project_root) / str(acceptance.get("rules_root") or "academic-toolkit/engine/modex-core")
    rules = acceptance.get("rule_files") or acceptance.get("rules") or {}
    if isinstance(rules, dict):
        for relative, frozen_sha in rules.items():
            current = _read_sha256(rules_root / str(relative))
            if str(frozen_sha) != current:
                missing.append(f"rule:{relative}")
    policy = acceptance.get("approval_policy") if isinstance(acceptance.get("approval_policy"), dict) else {}
    if not policy or policy.get("require_human") is not True:
        missing.append("approval_policy")
    else:
        config = Path(workspace) / ".engine" / "approvers.json"
        if not config.is_file() or _read_sha256(config) != str(policy.get("config_sha256") or ""):
            missing.append("approval_policy_config")
    review_inputs = {path for path, meta in (candidate.inputs or {}).items()
                     if isinstance(meta, dict) and meta.get("kind") == "review_input"}
    roots = {str(root.get("path", "")) for root in candidate.roots if isinstance(root, dict)}
    for path, digest in (candidate.frozen_versions or {}).items():
        if path in review_inputs and path not in roots:
            continue
        target = Path(workspace) / str(path)
        try:
            target.resolve().relative_to(Path(workspace).resolve())
        except (OSError, ValueError):
            missing.append(str(path))
            continue
        if not target.is_file() or _read_sha256(target) != str(digest):
            missing.append(str(path))
    return _candidate_gate(not missing,
                           "candidate frozen roots/inputs or acceptance contract changed",
                           missing=missing)


def _candidate_closure_gate(candidate: Any) -> dict[str, Any]:
    unknown = []
    lineage = candidate.lineage if isinstance(candidate.lineage, dict) else {}
    candidate_unknown = lineage.get("unknown_inputs")
    if isinstance(candidate_unknown, list):
        unknown.extend(str(item) for item in candidate_unknown)
    if "closure" in (candidate.missing or []):
        unknown.append("closure")
    return _candidate_gate(not unknown,
                           "unknown write inputs: dependency closure cannot be proven",
                           missing=unknown)


def _candidate_recipe_entry(candidate: Any, recipe_id: str) -> Any:
    recipe = candidate.recipe if isinstance(candidate.recipe, dict) else {}
    entries = recipe.get("recipes") if isinstance(recipe.get("recipes"), dict) else recipe
    if isinstance(entries, dict):
        if recipe_id in entries:
            return entries[recipe_id]
        for value in entries.values():
            if isinstance(value, dict) and str(value.get("recipe_id") or "") == recipe_id:
                return value
    if isinstance(recipe.get("recipes"), list):
        for value in recipe["recipes"]:
            if isinstance(value, dict) and str(value.get("recipe_id") or "") == recipe_id:
                return value
    return None


def _recipe_sha_candidates(candidate: Any, recipe_id: str) -> set[str]:
    entry = _candidate_recipe_entry(candidate, recipe_id)
    if entry is None:
        return set()
    values = {_canonical_sha256(entry)}
    if isinstance(entry, dict) and "recipe_id" in entry:
        values.add(_canonical_sha256({k: v for k, v in entry.items() if k != "recipe_id"}))
    return values


def _candidate_reproduction_gate(store: Any, candidate: Any) -> dict[str, Any]:
    acceptance = candidate.acceptance if isinstance(candidate.acceptance, dict) else {}
    targets = acceptance.get("reproduction_targets") or []
    if not isinstance(targets, list) or not targets:
        return _candidate_gate(False, "candidate has no command reproduction targets")
    workflow_id = candidate.delivery_workflow_id
    if not workflow_id:
        return _candidate_gate(False, "candidate is not bound to a delivery workflow")
    rows = store._connection.execute(
        "SELECT o.payload AS payload, s.status AS step_status FROM execution_operations o "
        "JOIN workflow_steps s ON s.id=o.step_id WHERE o.workflow_id=? AND o.kind='command' "
        "AND o.status='succeeded'", (workflow_id,)).fetchall()
    operations = []
    for row in rows:
        try:
            operations.append((json.loads(row["payload"]), row["step_status"]))
        except (TypeError, json.JSONDecodeError):
            continue
    missing: list[str] = []
    matched_targets = 0
    for target in targets:
        if not isinstance(target, dict):
            missing.append("invalid_target")
            continue
        path = str(target.get("path") or "")
        digest = str(target.get("sha256") or "")
        recipe_id = str(target.get("recipe_id") or "")
        if not path or str((candidate.frozen_versions or {}).get(path) or "") != digest:
            missing.append(f"target_not_frozen:{path or '?'}")
            continue
        expected_shas = _recipe_sha_candidates(candidate, recipe_id)
        if not expected_shas:
            missing.append(f"recipe_missing:{recipe_id or '?'}")
            continue
        satisfied = False
        for payload, step_status in operations:
            if step_status != "completed":
                continue
            reproduction = payload.get("reproduction")
            if not isinstance(reproduction, dict):
                continue
            if str(reproduction.get("candidate_id") or "") != candidate.id:
                continue
            if str(reproduction.get("recipe_sha256") or "") not in expected_shas:
                continue
            if reproduction.get("argv_rewrite") != "workspace-absolute-to-repro-map-v1":
                continue
            if reproduction.get("fresh_outputs") is not True:
                continue
            # 复现目录方案可演进（短哈希段 / 旧四段）：以 payload 自带的 mapped_root 为准，
            # 仅在缺少元数据时回退旧前缀，避免门禁与目录方案硬耦合。
            root_meta = reproduction.get("mapped_root")
            root_path = ""
            root_candidate = ""
            root_recipe = ""
            if isinstance(root_meta, dict):
                root_path = str(root_meta.get("path") or "").replace("\\", "/").rstrip("/")
                root_candidate = str(root_meta.get("candidate_id") or "")
                root_recipe = str(root_meta.get("recipe_sha256") or "")
            else:
                root_path = str(reproduction.get("mapped_root_path") or "").replace("\\", "/").rstrip("/")
            if root_candidate and root_candidate != candidate.id:
                continue
            if root_recipe and root_recipe not in expected_shas:
                continue
            legacy_prefix = f"_reproduction/{candidate.id}/"
            for produced in reproduction.get("targets") or []:
                if not isinstance(produced, dict) or str(produced.get("target") or "") != path:
                    continue
                mapped = str(produced.get("mapped_path") or "").replace("\\", "/")
                if root_path:
                    if not root_path.startswith("_reproduction/"):
                        continue
                    if not mapped.startswith(root_path + "/"):
                        continue
                elif not mapped.startswith(legacy_prefix):
                    continue
                if produced.get("hash_match") is True and str(produced.get("after_sha256") or "") == digest:
                    satisfied = True
                    break
            if satisfied:
                break
        if satisfied:
            matched_targets += 1
        else:
            missing.append(f"target:{path}")
    return _candidate_gate(not missing,
                           "missing fresh reproduction covering every frozen command target",
                           missing=missing, matched_targets=matched_targets,
                           target_count=len(targets))


def _review_step_rows(store: Any, workflow_id: str) -> list[Any]:
    return store._connection.execute(
        "SELECT id, name, position, status FROM workflow_steps WHERE workflow_id=? ORDER BY position",
        (workflow_id,)).fetchall()


def _accepted_origin_by_path(checkpoints: list[dict[str, Any]],
                             events: list[dict[str, Any]]) -> dict[str, str]:
    """Map accepted logical path -> the step id whose accepted manifest last set it."""
    cp_steps = {c["id"]: c["step_id"] for c in checkpoints}
    origin: dict[str, str] = {}
    for event in events:
        if not isinstance(event, dict):
            continue
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            continue
        step_id = cp_steps.get(event.get("checkpoint_id"), "")
        if event.get("type") in {"step_completed", "step_backfilled"}:
            manifest = payload.get("manifest")
            if isinstance(manifest, dict):
                for artifact in manifest.get("artifacts") or []:
                    if isinstance(artifact, dict) and artifact.get("path"):
                        origin[str(artifact["path"]).lower().replace("\\", "/")] = step_id
        elif event.get("type") in {"step_failed", "step_retry"} and step_id:
            for path in [p for p, owner in origin.items() if owner == step_id]:
                origin.pop(path, None)
    return origin


def _candidate_review_gate(store: Any, candidate: Any, workspace: Path) -> dict[str, Any]:
    acceptance = candidate.acceptance if isinstance(candidate.acceptance, dict) else {}
    required = acceptance.get("required_reviews") or []
    if not isinstance(required, list) or not required:
        return _candidate_gate(False, "candidate acceptance has no required review steps")
    workflow_id = candidate.delivery_workflow_id
    if not workflow_id:
        return _candidate_gate(False, "candidate is not bound to a delivery workflow")
    steps = _review_step_rows(store, workflow_id)
    step_by_name = {str(step["name"]): step for step in steps}
    checkpoints = [dict(row) for row in store._connection.execute(
        "SELECT id, step_id, state, created_at FROM checkpoints WHERE workflow_id=? ", (workflow_id,)).fetchall()]
    events = []
    for row in store._connection.execute(
            "SELECT id, checkpoint_id, event_type, payload, created_at FROM events WHERE workflow_id=?",
            (workflow_id,)).fetchall():
        try:
            event_payload = json.loads(row["payload"])
        except (TypeError, json.JSONDecodeError):
            event_payload = {}
        events.append({"id": row["id"], "checkpoint_id": row["checkpoint_id"],
                       "type": row["event_type"], "payload": event_payload,
                       "created_at": row["created_at"]})
    accepted_by_path, _coverage, _errors = _accepted_coverage(
        workspace, list(_accepted_event_batches(checkpoints, events)[0].values()))
    origin = _accepted_origin_by_path(checkpoints, events)
    review_skill_names = {str(item.get("skill_name") if isinstance(item, dict) else item)
                          for item in required}
    prior_outputs_by_step: dict[str, dict[str, str]] = {}
    for path, artifact in accepted_by_path.items():
        owner = origin.get(str(path).lower().replace("\\", "/"))
        if owner and owner in {step["id"] for step in steps if str(step["name"]) in review_skill_names}:
            prior_outputs_by_step.setdefault(owner, {})[str(artifact["path"])] = str(artifact["sha256"])
    frozen = {str(path): str(digest) for path, digest in (candidate.frozen_versions or {}).items()}
    roots = {str(root.get("path", "")): str(root.get("sha256", ""))
             for root in candidate.roots if isinstance(root, dict)}
    missing: list[str] = []
    for item in required:
        if isinstance(item, dict):
            skill_name = str(item.get("skill_name") or "")
            role = str(item.get("role") or "review")
        else:
            skill_name, role = str(item), "review"
        step = step_by_name.get(skill_name)
        if step is None or step["status"] != "completed":
            missing.append(f"review_step:{skill_name}")
            continue
        operations = store._connection.execute(
            "SELECT payload FROM execution_operations WHERE step_id=? AND kind='review' AND status='succeeded'",
            (step["id"],)).fetchall()
        allowed = dict(frozen)
        for previous in steps:
            if previous["position"] >= step["position"]:
                continue
            allowed.update(prior_outputs_by_step.get(previous["id"], {}))
        satisfied = False
        for row in operations:
            try:
                payload = json.loads(row["payload"])
            except (TypeError, json.JSONDecodeError):
                continue
            inputs_snapshot = payload.get("inputs_snapshot")
            if not isinstance(inputs_snapshot, dict) or not inputs_snapshot:
                continue
            if any(str(path) not in allowed or str(digest) != allowed[str(path)]
                   for path, digest in inputs_snapshot.items()):
                continue
            if role == "final" and any(
                    str(path) not in inputs_snapshot or str(inputs_snapshot[str(path)]) != digest
                    for path, digest in roots.items()):
                continue
            satisfied = True
            break
        if not satisfied:
            missing.append(f"review:{skill_name}")
    return _candidate_gate(not missing,
                           "required review steps missing, stale, or reading outside frozen versions",
                           missing=missing)


def _agent_self_reference(value: str) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return True
    try:
        from ..orchestration.workflow_runner import _agent_self_reference_hit
        return bool(_agent_self_reference_hit(value))
    except (ImportError, AttributeError, TypeError):
        pass
    tokens = re.split(r"[^0-9a-z\u4e00-\u9fff]+", text)
    return any(token in {"agent", "assistant", "claude", "gpt", "codex", "openai", "模型", "助手"}
               for token in tokens)


def _candidate_approval_gate(store: Any, candidate: Any, workspace: Path) -> dict[str, Any]:
    acceptance = candidate.acceptance if isinstance(candidate.acceptance, dict) else {}
    policy = acceptance.get("approval_policy") if isinstance(acceptance.get("approval_policy"), dict) else {}
    approvers = [str(value) for value in (policy.get("approvers") or []) if str(value).strip()]
    chain = _candidate_event_chain_status(store, candidate.id)
    if chain.get("ok") is not True:
        return _candidate_gate(
            False, f"candidate event hash chain broken at {chain.get('broken_at') or 'unknown'}")
    events = store.candidate_events(candidate.id, cross_validate=True)
    if not events:
        return _candidate_gate(False, "candidate has no approval event")
    event = events[-1]
    if event.get("event_type") != "candidate_approved":
        return _candidate_gate(False, "latest candidate event is not candidate_approved")
    if event.get("orphan"):
        return _candidate_gate(False, "orphan candidate_approved without workflow checkpoint event")
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    by = str(payload.get("approved_by") or payload.get("by") or "")
    if not by or by not in approvers or _agent_self_reference(by):
        return _candidate_gate(False, "approver is empty, outside frozen whitelist, or agent-like")
    workflow_approval = event.get("checkpoint_approved_payload")
    if not isinstance(workflow_approval, dict):
        return _candidate_gate(False, "workflow checkpoint_approved event is missing")
    event_by = str(workflow_approval.get("approved_by") or workflow_approval.get("by") or "")
    if not event_by or event_by not in approvers:
        return _candidate_gate(False, "workflow event approver is outside the frozen whitelist")
    if payload.get("l1_available") is not True:
        return _candidate_gate(False, "L1 host attestation is unavailable")
    for flag in ("agent_approve_seen", "same_session_approve", "degraded_host_attestation"):
        if payload.get(flag) is not False:
            return _candidate_gate(False, f"approval rejected by {flag}")
    checkpoint = store._connection.execute(
        "SELECT * FROM checkpoints WHERE id=?", (event["checkpoint_id"],)).fetchone()
    if checkpoint is None:
        return _candidate_gate(False, "approval checkpoint is missing")
    try:
        checkpoint_state = json.loads(checkpoint["state"])
    except (TypeError, json.JSONDecodeError):
        checkpoint_state = {}
    if not isinstance(checkpoint_state, dict) or checkpoint_state.get("status") != "waiting_checkpoint":
        return _candidate_gate(False, "approval checkpoint is not an old blocked checkpoint")
    step = store._connection.execute(
        "SELECT * FROM workflow_steps WHERE id=?", (event["step_id"],)).fetchone()
    if step is None or step["name"] != "comp-final-audit":
        return _candidate_gate(False, "approval is not bound to comp-final-audit")
    last = store._connection.execute(
        "SELECT id FROM workflow_steps WHERE workflow_id=? ORDER BY position DESC LIMIT 1",
        (step["workflow_id"],)).fetchone()
    if last is None or last["id"] != step["id"]:
        return _candidate_gate(False, "approval is not bound to the final workflow step")
    workflow = store.get_workflow(step["workflow_id"])
    window_start = _parse_event_ts(payload.get("l1_window_start"))
    workflow_created = _parse_event_ts(workflow.created_at)
    if window_start is None or workflow_created is None or window_start < workflow_created:
        return _candidate_gate(False, "L1 window does not start at the candidate delivery workflow")
    manifest = checkpoint_state.get("manifest") if isinstance(checkpoint_state.get("manifest"), dict) else {}
    from ..storage.artifact_manifest import ArtifactManifest
    validated = ArtifactManifest.validate(workspace, list(manifest.get("artifacts") or []))
    if not validated.get("ok") or not manifest.get("artifacts"):
        return _candidate_gate(False, "old checkpoint manifest is missing or changed")
    return _candidate_gate(True, approved_by=by)


def candidate_readiness(workspace: Path, project_root: Path, workflow_db: Path | str,
                        delivery_candidate_id: str) -> dict[str, Any]:
    """Evaluate all candidate gates against persisted candidate/delivery facts."""
    from ..storage.workflow_store import WorkflowStore

    workspace = Path(workspace).resolve()
    project_root = Path(project_root).resolve()
    gates = {name: _candidate_gate(False, "candidate is missing")
             for name in ("candidate_frozen", "candidate_closure",
                          "candidate_reproduction", "candidate_review",
                          "candidate_approval", "candidate_event_chain")}
    if not delivery_candidate_id:
        return {"ok": False, "gates": gates, "missing": sorted(gates), "roots": [],
                "acceptance_sha256": "", "candidate_status": "",
                "candidate_chain_root": "",
                "candidate_event_chain": {"ok": False, "broken_at": "candidate_missing",
                                          "events": 0}}
    candidate = None
    chain_status: dict[str, Any] = {"ok": False, "broken_at": "candidate_missing", "events": 0}
    chain_root = ""
    try:
        with WorkflowStore(workflow_db, read_only=True) as store:
            candidate = store.get_candidate(delivery_candidate_id)
            chain_status = _candidate_event_chain_status(store, candidate.id)
            gates["candidate_event_chain"] = _candidate_gate(
                chain_status.get("ok") is True,
                f"candidate event hash chain broken at "
                f"{chain_status.get('broken_at') or 'unknown'}",
                events=int(chain_status.get("events", 0) or 0),
                broken_at=chain_status.get("broken_at"))
            root_getter = getattr(store, "candidate_event_chain_root", None)
            if callable(root_getter):
                try:
                    chain_root = str(root_getter(candidate.id) or "")
                except Exception:  # noqa: BLE001 — root is informational, chain gate governs
                    chain_root = ""
            gates["candidate_frozen"] = _candidate_frozen_gate(workspace, project_root, candidate)
            gates["candidate_closure"] = _candidate_closure_gate(candidate)
            gates["candidate_reproduction"] = _candidate_reproduction_gate(store, candidate)
            gates["candidate_review"] = _candidate_review_gate(store, candidate, workspace)
            gates["candidate_approval"] = _candidate_approval_gate(store, candidate, workspace)
    except (KeyError, OSError, ValueError) as exc:
        chain_status = {"ok": False, "broken_at": f"candidate_readiness_unavailable:{exc}",
                        "events": 0}
        for name in gates:
            gates[name] = _candidate_gate(False, f"candidate readiness unavailable: {exc}")
    missing = [name for name, gate in gates.items() if not gate.get("ok")]
    return {
        "ok": not missing,
        "gates": gates,
        "missing": missing,
        "roots": list(candidate.roots) if candidate is not None else [],
        "acceptance_sha256": candidate.acceptance_sha256 if candidate is not None else "",
        "candidate_status": candidate.status if candidate is not None else "",
        "candidate_chain_root": chain_root,
        "candidate_event_chain": chain_status,
    }


def build_final_audit_report(workspace: Path, project_root: Path,
                             workflow_db: Path | None = None, *,
                             workflow_id: str | None = None, fingerprint_session=None,
                             candidate: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build the manifest-backed final delivery audit report.

    The final audit report is derived from persisted workflow state rather than
    handwritten prose. It aggregates completed-step gate outcomes, selects the
    latest delivery artifacts from the workflow timeline, and emits the machine
    contract required by `check_final_audit_report()`.
    """
    workspace = Path(workspace).resolve()
    project_root = Path(project_root).resolve()
    if workflow_db is None:
        workflow_db = workspace / ".engine" / "workflow.sqlite"

    requested_workflow_id = workflow_id
    workflow_id = ""
    workflow_name = ""
    workflow_metadata: dict[str, Any] = {}
    checkpoints: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    timeline_report: dict[str, Any] | None = None
    workflow_steps: list[dict[str, Any]] = []
    state_consistency: dict[str, Any] = {"checked_steps": 0, "violations": [], "ok": True}
    try:
        from ..storage.workflow_store import WorkflowStore

        if Path(workflow_db).is_file():
            with WorkflowStore(workflow_db, read_only=True) as store:
                # A2R-fatal 修复（傀儡工作流致盲）：此前只核查"最新一个"工作流，
                # "直改旧工作流 + 再 start 一个干净工作流"这一带内动作即可让核查
                # 完全致盲。现在遍历数据库中全部 workflows，逐一做状态-事件一致性
                # 核查并聚合 violations——被篡改的非最新工作流同样必须被抓。
                workflow_rows = store._connection.execute(
                    "SELECT id FROM workflows ORDER BY created_at ASC, id ASC"
                ).fetchall()
                all_violations: list[str] = []
                checked_steps_total = 0
                for row in workflow_rows:
                    per_workflow = _check_state_event_consistency(store, row["id"])
                    checked_steps_total += int(per_workflow.get("checked_steps", 0) or 0)
                    all_violations.extend(
                        f"工作流 {row['id']}: {violation}"
                        for violation in per_workflow.get("violations", []))
                # 一致性结论先于时间线赋值：即使 timeline 渲染失败，
                # 已发现的 violations 也不丢（fail-closed）。
                state_consistency = {
                    "checked_workflows": len(workflow_rows),
                    "checked_steps": checked_steps_total,
                    "violations": all_violations,
                    "ok": not all_violations,
                }
                # 时间线信息（工作流元数据/事件流）仍取最新工作流，展示口径不变。
                candidates = store._connection.execute(
                    "SELECT id, metadata FROM workflows ORDER BY created_at DESC, rowid DESC"
                ).fetchall()
                latest = next((r for r in candidates if
                    (not requested_workflow_id or r["id"] == requested_workflow_id)
                    and Path(json.loads(r["metadata"]).get("workspace", "")).resolve() == workspace), None)
                if latest is None:
                    raise ValueError("no matching workflow for workspace/workflow_id")
                timeline_report = store.workflow_timeline(latest["id"])
                columns = {r[1] for r in store._connection.execute("PRAGMA table_info(workflow_steps)")}
                version_fields = ("revision" if "revision" in columns else "0 AS revision") + ", " + (
                    "attempt_id" if "attempt_id" in columns else "'' AS attempt_id")
                workflow_steps = [dict(s) for s in store._connection.execute(
                    "SELECT id, name, position, status, metadata, " + version_fields +
                    " FROM workflow_steps WHERE workflow_id = ? ORDER BY position", (latest["id"],))]
    except Exception as exc:
        timeline_report = None
        # FIX (MED): DB unreadable must NOT leave state_consistency.ok=True.
        # Delivery-ready is blocked via gate_outcomes.state_event_consistency.
        state_consistency = {
            "checked_workflows": 0,
            "checked_steps": 0,
            "violations": [f"workflow database unreadable/unqueryable: {exc}"],
            "ok": False,
            "reason": (
                "DB 不可读=未核验（fail-closed：SQLite 打不开或查询失败时"
                "不得将状态-事件一致性标为通过）"
            ),
        }

    if isinstance(timeline_report, dict):
        workflow = timeline_report.get("workflow", {})
        if isinstance(workflow, dict):
            workflow_id = str(workflow.get("id", ""))
            workflow_name = str(workflow.get("name", ""))
            workflow_metadata = workflow.get("metadata", {}) if isinstance(workflow.get("metadata", {}), dict) else {}
        checkpoints = timeline_report.get("checkpoints", []) if isinstance(timeline_report.get("checkpoints", []), list) else []
        events = timeline_report.get("events", []) if isinstance(timeline_report.get("events", []), list) else []

    contract_tier = "delivery"
    contract_metadata = workflow_metadata.get("execution_contract")
    if isinstance(contract_metadata, dict) and contract_metadata.get("tier") in {"delivery", "explore"}:
        contract_tier = str(contract_metadata["tier"])
    delivery_candidate_metadata = (workflow_metadata.get("delivery_candidate")
                                   if isinstance(workflow_metadata.get("delivery_candidate"), dict) else {})
    delivery_candidate_id = str(delivery_candidate_metadata.get("candidate_id") or "")

    gate_outcomes: dict[str, str] = {}
    latest_artifacts: list[dict[str, Any]] = []
    cp_steps = {c["id"]: c["step_id"] for c in checkpoints}
    latest_checks: dict[str, dict[str, Any]] = {}
    evidence_paths: set[str] = set()
    for event in events:
        if not isinstance(event, dict):
            continue
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            continue
        step_id = cp_steps.get(event.get("checkpoint_id"), "unknown")
        if event.get("type") in {"step_completed", "step_failed", "step_retry", "step_backfilled"}:
            quality = payload.get("quality_gates", {})
            checks = quality.get("checks", {}) if isinstance(quality, dict) else {}
            latest_checks[step_id] = dict(checks) if isinstance(checks, dict) else {}
            if event.get("type") == "step_backfilled":
                latest_checks[step_id]["backfill_verification"] = {
                    "ok": payload.get("validation", {}).get("ok") is True}

    accepted_artifacts, evidence_paths = _accepted_event_batches(checkpoints, events)

    # Current accepted outputs across all steps, with later writers superseding
    # the same logical path. Never select a report merely because its mtime is newer.
    accepted_by_path, directory_coverage, coverage_errors = _accepted_coverage(
        workspace, list(accepted_artifacts.values()))
    scoped_outcomes: dict[str, str] = {}
    for step_id, checks in latest_checks.items():
        for name, check in checks.items():
            outcome = "pass" if isinstance(check, dict) and check.get("ok") is True else "fail"
            scoped_outcomes[f"{step_id}:{name}"] = outcome
            if name not in gate_outcomes or outcome != "pass":
                gate_outcomes[name] = outcome

    # No filesystem/mtime fallback: orphan evidence and freshly hashed files
    # cannot manufacture an accepted artifact version.
    latest_artifacts = [a for p, a in accepted_by_path.items()
                        if p.lower() not in {"audit_report.json", "delivery_report.json"}]

    waivers = [
        key for key, value in workflow_metadata.get("params", {}).items()
        if key.startswith("skip_") and bool(value)
    ] if isinstance(workflow_metadata.get("params", {}), dict) else []

    report_artifacts = [
        {"path": str(a["path"]), "sha256": str(a["sha256"])}
        for a in latest_artifacts
        if a.get("path") and re.fullmatch(r"[0-9a-fA-F]{64}", str(a.get("sha256", "")))
    ]
    readiness: dict[str, Any] | None = None
    if delivery_candidate_id:
        # Candidate delivery reports only the frozen roots; review verdicts are
        # gate evidence, not delivery artifacts.
        readiness = candidate_readiness(workspace, project_root, workflow_db, delivery_candidate_id)
        candidate_roots = readiness.get("roots") if isinstance(readiness.get("roots"), list) else []
        report_artifacts = [
            {"path": str(root.get("path", "")), "sha256": str(root.get("sha256", ""))}
            for root in candidate_roots
            if isinstance(root, dict) and root.get("path")
            and re.fullmatch(r"[0-9a-fA-F]{64}", str(root.get("sha256", "")))
        ]

    # Only persisted event references may attest an accepted delivery. A candidate
    # may explain L1 operations for the running final pre-audit, never its outputs.
    candidate_evidence = None
    candidate_action = None
    if candidate is not None:
        candidate_action = candidate.get("action", {})
        candidate_evidence = candidate.get("evidence", {})
        running_final = next((s for s in workflow_steps if s["id"] == candidate_action.get("step_id")), None)
        if (not running_final or running_final["name"] != "comp-final-audit"
                or running_final["status"] != "running"
                or running_final["id"] != workflow_steps[-1]["id"]
                or candidate_action.get("workflow_id") != workflow_id
                or candidate_action.get("attempt_id") != running_final["attempt_id"]
                or candidate_action.get("expected_revision") != running_final["revision"]
                or candidate_evidence.get("step_id") != running_final["id"]):
            raise ValueError("candidate evidence must match the current RUNNING final step/attempt/revision")
    gate_outcomes["accepted_artifact_coverage"] = (
        "pass" if report_artifacts and not coverage_errors else "fail")
    # A2 补丁2：防绕过检测结果接入交付判定——工作区归属的未申报操作直接 blocked。
    # 候选交付还要把源 explore 工作流纳入 control_scope，否则 promote 会被误判
    # 为未申报 bash。
    source_workflow_ids = sorted({str(value) for value in (
        delivery_candidate_metadata.get("source_workflow_id"),
        workflow_id) if str(value or "")})
    unreported = detect_unreported_operations(workspace, project_root, evidence_paths=evidence_paths,
        candidate_evidence=candidate_evidence,
        control_scope={"workflow_id": workflow_id, "database": workflow_db,
                       "source_workflow_ids": source_workflow_ids,
                       "checkpoint_ids": {c["id"] for c in checkpoints}} if workflow_id else None)
    blocking_unreported = _workspace_scoped_unreported(workspace, unreported)
    operation_audit_ok = (
        not blocking_unreported["unreported_bash"]
        and not blocking_unreported["unreported_edit_targets"]
    )
    consistency_ok = bool(state_consistency.get("ok", True))

    # P4：技能绑定对账接入交付判定。判定映射与理由：
    #   ok          → pass（声明绑定全部在 L1 可核）
    #   warning     → fail（声明了绑定但 L1 无对应操作 = 自述与事实不符）
    #   unavailable → pass + 降级留痕（L1 缺席是宿主治理决策、agent 无法绕过；
    #                 若判 fail 则所有未启用 L1 的宿主都无法交付，属误伤）
    skill_bindings = verify_skill_bindings(workspace, project_root, evidence_paths=evidence_paths,
        candidate_action=candidate_action, candidate_evidence=candidate_evidence, workflow_db=workflow_db)
    binding_verdict = str(skill_bindings.get("verdict", "ok"))
    gate_outcomes["skill_binding"] = "fail" if binding_verdict == "warning" else "pass"

    gate_outcomes["state_event_consistency"] = "pass" if consistency_ok else "fail"
    gate_outcomes["operation_audit"] = "pass" if operation_audit_ok else "fail"

    # A2R-fatal 修复（skip_review 致盲）：waiver 从"只记录不阻断"改为硬闸——
    # 任何 skip_ 豁免参数（最严重形态：skip_review=true 在 start 时静默删除全部
    # 审核步骤，审核防线从未运行过）都强制 delivery_decision=blocked。
    # waivers 字段本身保留作留痕，waiver_detail 注记原因与解除方式。
    waiver_blocked = bool(waivers)
    gate_outcomes["waiver_review"] = "fail" if waiver_blocked else "pass"

    # B-02 赛事合规结论（unknown ≠ PASS，2026-09-27）：从 workflow metadata 冻结的
    # 档案快照导出，不读现盘规则。非赛事 → not_applicable（计 pass，无关建模不受
    # 合规缺证影响）；赛事但无 bound 快照（待绑定）或快照内存在 unverified 约束
    # → unknown → 不计 pass → 正式 ready 不可达成（缺证只阻塞相关合规结论）。
    try:
        from ..contracts.contest_profile import compliance_conclusion, is_known_contest, pending_binding_snapshot
        contest_snapshot = workflow_metadata.get("contest_profile_snapshot")
        contest_params = workflow_metadata.get("params") if isinstance(workflow_metadata.get("params"), dict) else {}
        contest_intent = isinstance(contest_snapshot, dict) or is_known_contest(workflow_name) \
            or isinstance(contest_params.get("contest"), dict)
        contest_conclusion = compliance_conclusion(
            contest_snapshot if isinstance(contest_snapshot, dict) else None,
            contest_intent=contest_intent)
        if contest_conclusion.get("verdict") == "unknown" and not isinstance(contest_snapshot, dict):
            contest_conclusion["binding_hint"] = pending_binding_snapshot(
                workflow_name, contest_params)["reason"]
        gate_outcomes["contest_compliance"] = \
            "pass" if contest_conclusion.get("verdict") in {"pass", "not_applicable"} else "unknown"
    except Exception as exc:  # noqa: BLE001 —— 档案模块不可用时 fail-closed
        contest_conclusion = {"verdict": "unknown", "reason": f"合规结论推导失败: {exc}"}
        gate_outcomes["contest_compliance"] = "unknown"

    from ..storage.artifact_manifest import ArtifactManifest, FingerprintSession
    fingerprint_session = fingerprint_session or FingerprintSession(workspace)
    content = ArtifactManifest.validate_coverage(workspace, report_artifacts, directory_coverage,
                                                 session=fingerprint_session)
    gate_outcomes["artifact_integrity"] = "pass" if report_artifacts and content["ok"] else "fail"
    accepted_content = ArtifactManifest.validate(workspace, list(accepted_by_path.values()), session=fingerprint_session)
    if not accepted_content["ok"]:
        gate_outcomes["artifact_integrity"] = "fail"
    incomplete = [s for s in workflow_steps if s["status"] != "completed"]
    # Pre-audit may run inside the final audit step, but is not delivery-ready.
    pre_audit = (len(incomplete) == 1 and incomplete[0]["name"] == "comp-final-audit"
                 and incomplete[0]["status"] in {"running", "blocked"}
                 and incomplete[0]["id"] == workflow_steps[-1]["id"])
    steps_ok = bool(workflow_steps) and (not incomplete or pre_audit)
    gate_outcomes["workflow_steps"] = "pass" if steps_ok else "fail"
    for step in workflow_steps:
        if step["status"] != "completed":
            continue
        metadata = json.loads(step["metadata"])
        expected = list(metadata.get("required_checks") or [])
        if expected and not all(name in latest_checks.get(step["id"], {}) for name in expected):
            gate_outcomes["required_check_coverage"] = "fail"
    if delivery_candidate_id and isinstance(readiness, dict):
        candidate_gates = readiness.get("gates") if isinstance(readiness.get("gates"), dict) else {}
        for name in ("candidate_frozen", "candidate_closure",
                     "candidate_reproduction", "candidate_review",
                     "candidate_event_chain"):
            gate = candidate_gates.get(name) if isinstance(candidate_gates.get(name), dict) else {}
            gate_outcomes[name] = "pass" if gate.get("ok") is True else "fail"
        # 预审阶段不要求 candidate_approval：批准发生在终审步骤之后，否则会
        # 被候选批准门自己锁死。audit_phase=delivery 时才计入。
        if not pre_audit:
            gate = candidate_gates.get("candidate_approval") if isinstance(
                candidate_gates.get("candidate_approval"), dict) else {}
            gate_outcomes["candidate_approval"] = "pass" if gate.get("ok") is True else "fail"
    if contract_tier == "explore":
        delivery_ready = False
        delivery_decision = "explore_only"
    elif delivery_candidate_id:
        required_gates = ["candidate_frozen", "candidate_closure",
                          "candidate_reproduction", "candidate_review",
                          "candidate_event_chain"]
        if not pre_audit:
            required_gates.append("candidate_approval")
        delivery_ready = (
            bool(report_artifacts) and bool(gate_outcomes)
            and all(value == "pass" for value in gate_outcomes.values())
            and all(gate_outcomes.get(name) == "pass" for name in required_gates)
        )
        delivery_decision = ("eligible" if pre_audit else "ready") if delivery_ready else "blocked"
    else:
        delivery_ready = bool(report_artifacts) and bool(gate_outcomes) and all(
            value == "pass" for value in gate_outcomes.values())
        delivery_decision = ("eligible" if pre_audit else "ready") if delivery_ready else "blocked"
    release_id = ""
    if delivery_decision == "ready":
        if delivery_candidate_id:
            release_id = hashlib.sha256((
                delivery_candidate_id + str(readiness.get("acceptance_sha256") or "")
                + json.dumps(sorted((str(root.get("path")), str(root.get("sha256")))
                                    for root in (readiness.get("roots") or [])),
                             sort_keys=True, ensure_ascii=True)).encode()).hexdigest()
        else:
            release_id = hashlib.sha256((
                str(workflow_id) + json.dumps(sorted((a["path"], a["sha256"])
                                                     for a in report_artifacts),
                                              sort_keys=True, ensure_ascii=True)).encode()).hexdigest()
    report_data = {
        "workflow_id": workflow_id or str(workflow_name or workspace.name),
        "artifacts": report_artifacts,
        "directory_coverage": directory_coverage,
        "coverage_errors": coverage_errors,
        "legacy_directory_policy": "无逐文件回执的历史目录保留整树校验；合法子文件更新后须重验父目录",
        "gate_outcomes": gate_outcomes,
        "contest_compliance_detail": {
            **contest_conclusion,
            "blocking_rule": "contest_compliance=unknown（待绑定或约束 unverified）不计 pass："
                             "正式 ready 不得把 unknown 当 PASS；无关建模步骤不受影响",
        },
        "waivers": waivers,
        "waiver_detail": {
            "blocking_rule": ("skip_ 豁免只留痕、不放行：存在任何 skip_ 豁免参数"
                              "（含 skip_review=true 关闭审核防线）即强制 delivery_decision=blocked。"
                              "解除方式：以不含 skip_ 参数的工作流重新执行被豁免的步骤；"
                              "审核类步骤（comp-review/comp-visual-review/comp-editor/"
                              "comp-final-review）必须真实完成，不允许豁免。"),
            "hit_params": waivers,
        },
        "delivery_decision": delivery_decision,
        "audit_phase": "explore" if contract_tier == "explore" else (
            "pre_completion" if pre_audit else "delivery"),
        "contract_tier": contract_tier,
        "candidate_id": delivery_candidate_id,
        # Tamper-evidence: the last event_sha256 of the candidate event chain.
        # Gate outcome ``candidate_event_chain`` fails when any earlier link
        # does not recompute (broken_at names the first offending event id).
        "candidate_chain_root": (str(readiness.get("candidate_chain_root") or "")
                                 if isinstance(readiness, dict) else ""),
        "candidate_event_chain": (readiness.get("candidate_event_chain", {})
                                  if isinstance(readiness, dict) else {}),
        "release_id": release_id,
        "immutable": delivery_decision == "ready",
        "candidate": ({
            "candidate_id": delivery_candidate_id,
            "status": readiness.get("candidate_status", "") if isinstance(readiness, dict) else "",
            "acceptance_sha256": readiness.get("acceptance_sha256", "") if isinstance(readiness, dict) else "",
            "gates": readiness.get("gates", {}) if isinstance(readiness, dict) else {},
            "missing": readiness.get("missing", []) if isinstance(readiness, dict) else [],
            "chain_root": readiness.get("candidate_chain_root", "") if isinstance(readiness, dict) else "",
            "event_chain": readiness.get("candidate_event_chain", {}) if isinstance(readiness, dict) else {},
        } if delivery_candidate_id else {}),
        "candidate_evidence_scope": candidate_action or {},
        "pre_audit_step_id": incomplete[0]["id"] if pre_audit else "",
        "step_gate_outcomes": scoped_outcomes,
        "workflow_steps": [{k: s[k] for k in ("id", "name", "status", "revision", "attempt_id")} for s in workflow_steps],
        "artifact_integrity_detail": {"missing": content["missing"], "invalid": content["invalid"]},
        "state_event_consistency_detail": state_consistency,
        "skill_binding_detail": {
            "verdict": binding_verdict,
            "steps_checked": skill_bindings.get("steps_checked", 0),
            "unverified": skill_bindings.get("unverified", []),
            "unavailable_reason": skill_bindings.get("unavailable_reason", ""),
            "verification_source": skill_bindings.get("verification_source", "host_L1_or_declared_unavailable"),
            "blocking_rule": ("warning（声明绑定但 L1 无对应操作）→ 交付 blocked；"
                              "unavailable（宿主未启用 L1）→ 不阻断但降级留痕，"
                              "理由：L1 由宿主 hook/插件提供、agent 无法绕过，"
                              "判 fail 会误伤所有未启用 L1 的宿主"),
        },
        "operation_audit_detail": {
            "verdict": unreported["verdict"],
            "declared_command_count": unreported["declared_command_count"],
            "actual_bash_count": unreported["actual_bash_count"],
            "workflow_control_calls": unreported["workflow_control_calls"],
            "control_policy": "绑定当前工作流/库的独立控制调用单列，不作执行成功证据；复合命令不豁免",
            "blocking_rule": ("仅工作区归属的未申报操作触发 blocked；"
                              "bash 归属按命令引用工作区路径判定（审计条目无 cwd 字段，已知精度边界）"),
            **blocking_unreported,
        },
    }
    return report_data


def _read_json_report(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _report_identity(report: dict[str, Any]) -> tuple[str, tuple[tuple[str, str], ...]]:
    artifacts = report.get("artifacts") if isinstance(report.get("artifacts"), list) else []
    return (str(report.get("workflow_id") or ""),
            tuple(sorted((str(item.get("path", "")), str(item.get("sha256", "")))
                         for item in artifacts if isinstance(item, dict))))


def _archive_release(workspace: Path, release_id: str, audit_bytes: bytes | None,
                     delivery_report: dict[str, Any]) -> Path:
    """Archive immutable copies; never overwrite an existing archive."""
    from ..storage.step_manifest import atomic_write_json
    directory = Path(workspace) / "releases" / release_id
    directory.mkdir(parents=True, exist_ok=True)
    audit_path = directory / "AUDIT_REPORT.json"
    delivery_path = directory / "DELIVERY_REPORT.json"
    if audit_bytes is not None and not audit_path.exists():
        audit_path.write_bytes(audit_bytes)
    if not delivery_path.exists():
        atomic_write_json(delivery_path, delivery_report)
    return delivery_path


def write_explore_report(workspace: Path, project_root: Path,
                         workflow_db: Path | None = None, *,
                         workflow_id: str | None = None) -> Path:
    """Write ``EXPLORE_REPORT.json`` for an explore workflow.

    Explore never writes ``AUDIT_REPORT.json`` / ``DELIVERY_REPORT.json`` and
    never enters the immutable release namespace.
    """
    from ..storage.workflow_store import WorkflowStore
    from ..storage.step_manifest import atomic_write_json

    workspace = Path(workspace).resolve()
    if workflow_db is None:
        workflow_db = workspace / ".engine" / "workflow.sqlite"
    with WorkflowStore(workflow_db, read_only=True) as store:
        workflows = store._connection.execute(
            "SELECT id, name, metadata FROM workflows ORDER BY created_at DESC, rowid DESC").fetchall()
        selected = None
        for row in workflows:
            if workflow_id and row["id"] != workflow_id:
                continue
            metadata = json.loads(row["metadata"])
            contract = metadata.get("execution_contract") if isinstance(metadata, dict) else None
            tier = contract.get("tier") if isinstance(contract, dict) else "delivery"
            if tier != "explore":
                continue
            if Path(metadata.get("workspace", "")).resolve() != workspace:
                continue
            selected = (row, metadata)
            break
        if selected is None:
            raise ValueError("no matching explore workflow for workspace/workflow_id")
        row, metadata = selected
        timeline = store.workflow_timeline(row["id"])
        operations = store._connection.execute(
            "SELECT kind, status, COUNT(*) AS count FROM execution_operations "
            "WHERE workflow_id=? GROUP BY kind, status", (row["id"],)).fetchall()
        operation_summary = [{"kind": item["kind"], "status": item["status"],
                              "count": item["count"]} for item in operations]
    checkpoints = timeline.get("checkpoints", [])
    events = timeline.get("events", [])
    accepted = accepted_artifacts_by_path(workspace, checkpoints, events)
    advisories: set[str] = set()
    for event in events:
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        quality = payload.get("quality_gates") if isinstance(payload.get("quality_gates"), dict) else {}
        checks = quality.get("checks") if isinstance(quality.get("checks"), dict) else {}
        advisories.update(str(name) for name, check in checks.items()
                          if not (isinstance(check, dict) and check.get("ok") is True))
    accepted_artifacts = [
        {"path": str(artifact.get("path")), "sha256": str(artifact.get("sha256"))}
        for artifact in accepted.values() if artifact.get("path") and artifact.get("sha256")
    ]
    report = {
        "generated_at": _now(),
        "workflow_id": row["id"],
        "workflow_name": row["name"],
        "contract_tier": "explore",
        "delivery_decision": "explore_only",
        "audit_phase": "explore",
        "release_id": "",
        "immutable": False,
        "accepted_artifacts": accepted_artifacts,
        "operations_summary": operation_summary,
        "advisories": sorted(advisories),
    }
    target = workspace / "EXPLORE_REPORT.json"
    atomic_write_json(target, report)
    return target


def write_final_audit_report(workspace: Path, project_root: Path, out: Path | None = None,
                             workflow_db: Path | None = None, *, workflow_id: str | None = None,
                             candidate: dict[str, Any] | None = None) -> Path:
    """Write delivery reports with workflow-scoped pre-audit and immutable releases."""
    from ..storage.step_manifest import atomic_write_json
    from ..storage.workflow_store import WorkflowStore

    workspace = Path(workspace).resolve()
    report = build_final_audit_report(workspace, project_root, workflow_db=workflow_db,
                                     workflow_id=workflow_id, candidate=candidate)
    if report.get("contract_tier") == "explore":
        raise ValueError("explore workflows use write_explore_report; delivery reports are forbidden")
    report_workflow_id = str(report.get("workflow_id") or "")
    report_dir = workspace / "reports" / report_workflow_id
    report_dir.mkdir(parents=True, exist_ok=True)
    root_audit = workspace / "AUDIT_REPORT.json"
    root_delivery = workspace / "DELIVERY_REPORT.json"
    explicit_out = Path(out) if out is not None else None
    final_completed = any(step["name"] == "comp-final-audit" and step["status"] == "completed"
                          for step in report["workflow_steps"])
    final_blocked = any(step["name"] == "comp-final-audit" and step["status"] == "blocked"
                        for step in report["workflow_steps"])
    decision = str(report.get("delivery_decision") or "blocked")
    old_delivery = _read_json_report(root_delivery)
    old_ready = bool(old_delivery and old_delivery.get("delivery_decision") == "ready")

    if decision in {"blocked", "eligible"}:
        atomic_write_json(report_dir / "AUDIT_REPORT.json", report)
        if old_ready:
            # Root stays the latest ready release; this run is only a working copy.
            working = report_dir / "DELIVERY_REPORT.json"
            atomic_write_json(working, report)
            if explicit_out and explicit_out.resolve() not in {root_audit.resolve(), root_delivery.resolve()}:
                atomic_write_json(explicit_out, report)
                return explicit_out
            return working
        existing_audit = _read_json_report(root_audit)
        if (not root_audit.exists() or not existing_audit
                or existing_audit.get("delivery_decision") == "blocked"):
            if explicit_out and explicit_out.resolve() == root_audit.resolve():
                raise ValueError("已验收预审不可覆盖；请输出 DELIVERY_REPORT.json，或 retry 后重新预审")
            atomic_write_json(root_audit, report)
        if final_completed or final_blocked:
            existing_delivery = _read_json_report(root_delivery)
            if (not root_delivery.exists() or not existing_delivery
                    or existing_delivery.get("delivery_decision") == "blocked"):
                atomic_write_json(root_delivery, report)
        if explicit_out:
            if explicit_out.resolve() == root_audit.resolve():
                raise ValueError("已验收预审不可覆盖；请输出 DELIVERY_REPORT.json，或 retry 后重新预审")
            atomic_write_json(explicit_out, report)
            return explicit_out
        return root_delivery if final_completed else root_audit

    if decision != "ready":
        raise ValueError(f"unsupported delivery decision: {decision}")

    # Ready: pre-audit source must describe the same workflow/artifacts, but its
    # phase fields (eligible/pre_completion/release_id="") are expected to differ.
    source_path = None
    for candidate_path in (report_dir / "AUDIT_REPORT.json", root_audit):
        candidate_report = _read_json_report(candidate_path)
        if candidate_report is not None and _report_identity(candidate_report) == _report_identity(report):
            source_path = candidate_path
            break
    if source_path is None:
        source_bytes = json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8")
    else:
        source_bytes = Path(source_path).read_bytes()
    release_id = str(report.get("release_id") or "")
    if not release_id:
        raise ValueError("ready report is missing release_id")
    archive_delivery = workspace / "releases" / release_id / "DELIVERY_REPORT.json"
    if release_id and archive_delivery.is_file():
        existing = _read_json_report(archive_delivery)
        if existing and existing.get("release_id") == release_id:
            # Idempotent replay: never rewrite bytes. The archived copy is the
            # authoritative immutable release (root may already point elsewhere
            # only if newer releases were written later).
            return archive_delivery
    if old_ready and old_delivery.get("release_id"):
        _archive_release(workspace, str(old_delivery["release_id"]),
                         root_audit.read_bytes() if root_audit.is_file() else None,
                         old_delivery)
    if explicit_out and explicit_out.resolve() == root_audit.resolve():
        raise ValueError("AUDIT_REPORT.json 必须保留预审内容；ready 报告写入 DELIVERY_REPORT.json")
    atomic_write_json(root_delivery, report)
    if source_path is None:
        source_path = report_dir / "AUDIT_REPORT.json"
        source_path.write_bytes(source_bytes)
    if source_path.resolve() != root_audit.resolve():
        root_audit.write_bytes(source_bytes)
    _archive_release(workspace, release_id, source_bytes, report)
    if explicit_out and explicit_out.resolve() not in {root_audit.resolve(), root_delivery.resolve()}:
        atomic_write_json(explicit_out, report)
        target = explicit_out
    else:
        target = root_delivery
    candidate_id = str(report.get("candidate_id") or "")
    if candidate_id:
        with WorkflowStore(workflow_db) as store:
            candidate_row = store.get_candidate(candidate_id)
            if candidate_row.status == "ready" and candidate_row.release_id == release_id:
                pass
            elif not store.set_candidate_status(candidate_id, "in_delivery", "ready",
                                                release_id=release_id,
                                                release_report_path=str(target)):
                raise ValueError("delivery candidate was superseded/abandoned; ready report not promoted")
    return target


def write_audit_report(workspace: Path, project_root: Path, out: Path | None = None,
                       workflow_db: Path | None = None) -> Path:
    """生成并保存审计报告 JSON。"""
    report = generate_audit_report(workspace, project_root, workflow_db=workflow_db)
    target = out or Path(workspace) / "OPERATION_AUDIT_REPORT.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return target
