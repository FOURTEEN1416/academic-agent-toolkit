"""审计存储与报告生成 — 读取 plugin 写入的 operations.jsonl，产出结构化审计报告。

审计数据流：
  1. OpenCode plugin（.opencode/plugins/audit-trail.ts）拦截式记录所有工具调用/文件编辑/会话
     → 共享根/.engine/audit/operations.jsonl（JSONL，每行一个事件）
  2. 引擎侧 workflow_store 记录编排事件（started/completed/checkpoint...）→ workflow.sqlite
  3. 本模块汇总两侧 + evidence 声明，生成审计报告并检测"未申报操作"（防绕过）
"""
from __future__ import annotations

import json
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
    }
    args = tokens[4:]
    if operation not in options or len(args) % 2:
        return None
    parsed = {}
    for key, value in zip(args[::2], args[1::2]):
        if (key not in options[operation] or (key in parsed and key != "--artifact")
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
               "write": {"--session", "--path", "--from-file"},
               "edit": {"--session", "--path", "--changes-file"},
               "run": {"--session", "--plan"},
               "finish": {"--session", "--review-session"},
               "status": {"--session"},
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
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
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
    from .artifact_manifest import ArtifactManifest
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
        from .workflow_store import WorkflowStore

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
                    "SELECT id, metadata FROM workflows ORDER BY created_at DESC, id DESC"
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

    gate_outcomes: dict[str, str] = {}
    latest_artifacts: list[dict[str, Any]] = []
    cp_steps = {c["id"]: c["step_id"] for c in checkpoints}
    latest_checks: dict[str, dict[str, Any]] = {}
    accepted_artifacts: dict[str, list[dict[str, Any]]] = {}
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
        manifest = payload.get("manifest")
        if isinstance(manifest, dict) and manifest.get("artifacts"):
            if event.get("type") in {"step_completed", "step_backfilled"}:
                accepted_artifacts.pop(step_id, None)
                accepted_artifacts[step_id] = list(manifest["artifacts"])
                evidence_paths.update(str(payload[k]) for k in ("evidence_path", "binding_evidence_path") if payload.get(k))
        if event.get("type") in {"step_failed", "step_retry"}:
            accepted_artifacts.pop(step_id, None)

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
    gate_outcomes["accepted_artifact_coverage"] = "pass" if accepted_by_path and not coverage_errors else "fail"
    # A2 补丁2：防绕过检测结果接入交付判定——工作区归属的未申报操作直接 blocked。
    unreported = detect_unreported_operations(workspace, project_root, evidence_paths=evidence_paths,
        candidate_evidence=candidate_evidence,
        control_scope={"workflow_id": workflow_id, "database": workflow_db,
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
        from .contest_profile import compliance_conclusion, is_known_contest, pending_binding_snapshot
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

    from .artifact_manifest import ArtifactManifest, FingerprintSession
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
    delivery_ready = bool(report_artifacts) and bool(gate_outcomes) and all(
        v == "pass" for v in gate_outcomes.values()
    )
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
        "delivery_decision": ("eligible" if pre_audit else "ready") if delivery_ready else "blocked",
        "audit_phase": "pre_completion" if pre_audit else "delivery",
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


def write_final_audit_report(workspace: Path, project_root: Path, out: Path | None = None,
                             workflow_db: Path | None = None, *, workflow_id: str | None = None,
                             candidate: dict[str, Any] | None = None) -> Path:
    """Keep the accepted pre-audit immutable; derive a separate delivery report."""
    report = build_final_audit_report(workspace, project_root, workflow_db=workflow_db,
                                     workflow_id=workflow_id, candidate=candidate)
    final_completed = any(s["name"] == "comp-final-audit" and s["status"] == "completed"
                          for s in report["workflow_steps"])
    target = Path(out) if out else Path(workspace) / ("DELIVERY_REPORT.json" if final_completed else "AUDIT_REPORT.json")
    if (final_completed or any(s["name"] == "comp-final-audit" and s["status"] == "blocked"
                               for s in report["workflow_steps"])) and target.resolve() == (Path(workspace) / "AUDIT_REPORT.json").resolve():
        raise ValueError("已验收预审不可覆盖；请输出 DELIVERY_REPORT.json，或 retry 后重新预审")
    from .step_manifest import atomic_write_json
    atomic_write_json(target, report)
    return target


def write_audit_report(workspace: Path, project_root: Path, out: Path | None = None,
                       workflow_db: Path | None = None) -> Path:
    """生成并保存审计报告 JSON。"""
    report = generate_audit_report(workspace, project_root, workflow_db=workflow_db)
    target = out or Path(workspace) / "OPERATION_AUDIT_REPORT.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return target
