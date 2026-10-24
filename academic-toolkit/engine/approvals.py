"""Store-layer guard for candidate final approvals (G2).

The guard is called unconditionally by :mod:`engine.workflow_store` from
``create_checkpoint`` / ``transition_step_with_checkpoint`` whenever a
candidate-bound workflow records an approval-shaped event.  It is deliberately
independent of ``workflow_runner``/``workflow_store`` (the store is duck-typed)
to avoid an import cycle: the direction is ``workflow_store -> approvals``.

What this module guarantees (normal path):

* the candidate is bound to the workflow that is being approved;
* only the last ``comp-final-audit`` step may be approved;
* ``approval_checkpoint_id`` is the *old blocked* checkpoint of that step, its
  manifest still validates, and it is the latest checkpoint for the step;
* ``approved_by`` comes from the candidate's **frozen** approver whitelist and
  does not hit the agent self-reference blacklist;
* L1 host evidence inside the current workflow window contains at least one
  path-attributed event (pathless events do not count as availability);
* L1 host commands matching the a-f self-approval patterns, or an approve
  event carrying a host ``sessionID`` used by the same workspace, are rejected;
* the candidate event payload is normalised with the computed attestation so
  ``candidate_approval`` can audit what was actually checked.

Boundary (user ruling 2026-10-23): any local process running as the same OS user
can import private functions, write SQLite directly, or forge an L1 log.  That
is the **malicious local process residual class, undefendable in-process**.
This guard provides normal-path correctness plus detection/audit traceability;
it is **not a sandbox** and does not issue self-signed tokens.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

APPROVAL_EVENT_TYPE = "candidate_approved"
NON_APPROVAL_EVENT_TYPES = {"candidate_approval_rejected", "candidate_approval_degraded"}

APPROVAL_BOUNDARY = (
    "任意本地进程以同一 OS 用户运行任意代码（包装脚本 import 引擎模块、直接写 SQLite、"
    "伪造 L1 日志）属于恶意本地进程残余类，进程内无法防御；本 guard 保证正常路径校验"
    "与检测 + 审计追溯，不是沙箱。"
)


class CandidateApprovalError(ValueError):
    """Raised when a candidate approval fails a store-layer guard check."""


def assert_candidate_approval_allowed(
    store: Any,
    *,
    workflow_id: str,
    step_id: str,
    approval_checkpoint_id: str,
    transition_checkpoint_id: str,
    candidate_id: str,
    approved_by: str,
    event_type: str,
    event_payload: Mapping[str, Any],
    audit_root: Path | str | None = None,
) -> None:
    """Validate a candidate approval before the store writes any row.

    Raises :class:`CandidateApprovalError` (a ``ValueError``) on failure.  The
    caller owns the SQLite transaction, so a raised error leaves no checkpoint,
    workflow event, or candidate event behind.
    """
    workflow = _get_workflow(store, workflow_id)
    candidate = _bound_candidate(store, workflow, candidate_id)

    if event_type not in {APPROVAL_EVENT_TYPE, "checkpoint_approved", *NON_APPROVAL_EVENT_TYPES}:
        raise CandidateApprovalError(f"不支持的候选审批事件类型: {event_type!r}")

    step = _get_step(store, step_id)
    if step.workflow_id != workflow_id:
        raise CandidateApprovalError("候选审批步骤不属于当前工作流")

    if event_type in NON_APPROVAL_EVENT_TYPES:
        # rejected/degraded are audit facts produced by the engine before a
        # transition; still require candidate/workflow/step identity.
        _validate_audit_event_identity(store, workflow, candidate, step, approval_checkpoint_id)
        return

    _require_final_audit_step(store, workflow_id, step)
    _require_old_blocked_checkpoint(
        store, workflow, step, approval_checkpoint_id, transition_checkpoint_id)
    if event_type == "checkpoint_approved":
        if str(event_payload.get("event_type") or "") != APPROVAL_EVENT_TYPE:
            raise CandidateApprovalError(
                "候选审批的 checkpoint_approved 事件必须同时携带 candidate_event")
        bound = str(event_payload.get("approved_checkpoint_id") or "")
        if bound != approval_checkpoint_id:
            raise CandidateApprovalError(
                "checkpoint_approved 事件必须绑定旧 blocked checkpoint")
    if event_type == APPROVAL_EVENT_TYPE:
        if str(event_payload.get("checkpoint_id") or "") not in {"", approval_checkpoint_id}:
            raise CandidateApprovalError("候选审批事件 checkpoint_id 与旧 blocked checkpoint 不一致")
        if str(event_payload.get("step_id") or "") not in {"", step_id}:
            raise CandidateApprovalError("候选审批事件 step_id 与 comp-final-audit 不一致")
    policy = _frozen_approval_policy(candidate)
    approver = _require_approver(policy, approved_by)

    evidence = collect_candidate_l1_evidence(
        store, workflow, checkpoint_id=approval_checkpoint_id,
        approved_by=approver, audit_root=audit_root)

    claimed = _claimed_attestation(event_payload)
    if "l1_available" in claimed and claimed.get("l1_available") is not True:
        raise CandidateApprovalError("候选审批事件自报 L1 不可用，不能通过")
    if claimed.get("degraded_host_attestation") not in (None, False):
        raise CandidateApprovalError("候选审批事件自报 degraded_host_attestation=true，不能通过")
    if evidence["degraded_host_attestation"] or not evidence["l1_available"]:
        raise CandidateApprovalError(
            "候选审批缺少当前工作流窗口内、路径归属本工作区的 L1 宿主证据"
            "（degraded_host_attestation=true）")
    if evidence["agent_approve_seen"] or claimed.get("agent_approve_seen") is True:
        raise CandidateApprovalError("L1 检测到 agent 自批/直写审批事实，候选审批被拒")
    if evidence["same_session_approve"] or claimed.get("same_session_approve") is True:
        raise CandidateApprovalError("L1 检测到同一会话发起 approve，候选审批被拒")

    if (event_type == APPROVAL_EVENT_TYPE
            or str(event_payload.get("event_type") or "") == APPROVAL_EVENT_TYPE):
        _normalize_approval_payload(event_payload, evidence, candidate, approver)


def collect_candidate_l1_evidence(
    store: Any,
    workflow: Any,
    *,
    checkpoint_id: str,
    approved_by: str,
    audit_root: Path | str | None = None,
) -> dict[str, Any]:
    """Compute L1 availability/self-approval evidence for a candidate approval.

    The window starts at the later of the delivery workflow creation time and
    the workspace's earliest workflow (same口径 as ``_workflow_window_start``).
    Only events whose ``detail.command`` contains this workspace or whose
    ``detail.filePath`` is inside it are attributed; pathless skill/task events
    never make L1 "available".
    """
    from .audit_store import _parse_event_ts, _workflow_window_start

    metadata = _workflow_metadata(workflow)
    workspace_text = str(metadata.get("workspace") or "").strip()
    if not workspace_text:
        raise CandidateApprovalError("候选工作流缺少 workspace metadata，无法核验 L1")
    workspace = Path(workspace_text).resolve()
    created = _parse_event_ts(getattr(workflow, "created_at", "")) or datetime.now(timezone.utc)
    lower = _workflow_window_start(workspace)
    window_start = max(created, lower) if lower else created

    events = _candidate_audit_events(store, workflow, audit_root=audit_root)
    attributed: list[dict[str, Any]] = []
    ws_norm = str(workspace).replace("\\", "/").lower()
    for event in events:
        if event.get("type") not in {"tool_call", "tool_result"}:
            continue
        ts = _parse_event_ts(event.get("ts"))
        if ts is None or ts < window_start:
            continue
        detail = event.get("detail") if isinstance(event.get("detail"), dict) else {}
        command = str(detail.get("command") or "")
        file_path = str(detail.get("filePath") or "")
        attributed_here = bool(command) and ws_norm in command.replace("\\", "/").lower()
        if file_path:
            try:
                attributed_here = attributed_here or Path(file_path).resolve().is_relative_to(workspace)
            except (OSError, ValueError):
                pass
        if attributed_here:
            attributed.append(event)

    agent_approve_seen = False
    approve_sessions: set[str] = set()
    executing_sessions: set[str] = set()
    attributed_ids = {id(event) for event in attributed}
    for event in attributed:
        detail = event.get("detail") if isinstance(event.get("detail"), dict) else {}
        command = str(detail.get("command") or "")
        session_id = str(detail.get("sessionID") or event.get("sessionID") or "")
        if command and _approval_event_pattern(command):
            agent_approve_seen = True
            if session_id:
                approve_sessions.add(session_id)
        elif session_id:
            executing_sessions.add(session_id)

    # Conservative fallback（设计 §2.2.4 第 3 条）：a-f pattern plus the explicit
    # checkpoint id is enough to reject even when the command was not attributed
    # (for example because --db was relative and control-call parsing returned None).
    for event in events:
        if event.get("type") != "tool_call" or id(event) in attributed_ids:
            continue
        ts = _parse_event_ts(event.get("ts"))
        if ts is None or ts < window_start:
            continue
        detail = event.get("detail") if isinstance(event.get("detail"), dict) else {}
        command = str(detail.get("command") or "")
        if not command or not _approval_event_pattern(command):
            continue
        if (checkpoint_id and checkpoint_id in command) or ws_norm in command.replace("\\", "/").lower():
            agent_approve_seen = True
            session_id = str(detail.get("sessionID") or event.get("sessionID") or "")
            if session_id:
                approve_sessions.add(session_id)

    # A host approve event that carries a session id is agent-originated even if
    # the same session never ran another attributed command (conservative).
    same_session_approve = bool(approve_sessions & executing_sessions) or bool(approve_sessions)
    policy = _frozen_approval_policy(_candidate_for_workflow(store, workflow))
    return {
        "l1_available": bool(attributed),
        "agent_approve_seen": agent_approve_seen,
        "same_session_approve": same_session_approve,
        "degraded_host_attestation": not bool(attributed),
        "l1_window_start": window_start.isoformat(),
        "attributed_event_count": len(attributed),
        "approval_policy_sha256": _canonical_sha256(policy),
        "approved_by": approved_by,
        "candidate_id": _candidate_id_from_metadata(metadata),
    }


def _approval_event_pattern(command: str) -> bool:
    """L1 self-approval/bypass patterns a-f (kept in sync with the runner scan)."""
    text = str(command or "").lower()
    if not text:
        return False
    write_words = ("insert", "update", "sqlite3", "execute", "executemany", "delete", "drop")
    if "workflow_cli approve" in text:  # a)
        return True
    if "approve_checkpoint" in text:  # b)
        return True
    if "workflow_runner" in text and "approve" in text:  # c)
        return True
    if ("candidate_approved" in text or "candidate_events" in text) and any(
            word in text for word in write_words):  # d)
        return True
    if "workflow.sqlite" in text and any(word in text for word in write_words):  # e)
        return True
    # f) wrapper scripts/executables whose name or argument starts with approve
    return bool(re.search(r"(?:^|[\\/\s\"'=])approve[\w.-]*", text))


def _candidate_audit_events(store: Any, workflow: Any,
                            *, audit_root: Path | str | None) -> list[dict[str, Any]]:
    from .audit_store import AuditStore

    roots: list[Path] = []
    metadata = _workflow_metadata(workflow)
    explicit = audit_root or metadata.get("audit_root")
    if explicit:
        roots.append(Path(explicit))
    workspace_text = str(metadata.get("workspace") or "").strip()
    workspace = Path(workspace_text).resolve() if workspace_text else None
    db_path = Path(str(getattr(store, "db_path", ""))).resolve()
    for candidate in (
        db_path.parent,
        db_path.parent.parent,
        workspace,
        workspace.parent if workspace else None,
        Path(__file__).resolve().parents[2],
    ):
        if candidate is not None:
            roots.append(candidate)
    seen_roots: set[str] = set()
    events: list[dict[str, Any]] = []
    seen_events: set[str] = set()
    for root in roots:
        key = str(root).lower()
        if key in seen_roots:
            continue
        seen_roots.add(key)
        if not (root / ".engine" / "audit" / "operations.jsonl").is_file():
            continue
        try:
            root_events = AuditStore(root).events()
        except OSError:
            continue
        for event in root_events:
            try:
                marker = json.dumps(event, sort_keys=True, ensure_ascii=True, default=str)
            except (TypeError, ValueError):
                marker = repr(event)
            if marker in seen_events:
                continue
            seen_events.add(marker)
            events.append(event)
    return events


def _require_final_audit_step(store: Any, workflow_id: str, step: Any) -> None:
    if str(getattr(step, "name", "")) != "comp-final-audit":
        raise CandidateApprovalError("候选批准只能发生在 comp-final-audit 步骤")
    status = getattr(step, "status", None)
    if str(getattr(status, "value", status)) != "blocked":
        raise CandidateApprovalError("候选批准只能发生在 BLOCKED 的终审步骤")
    last = store._connection.execute(
        "SELECT id FROM workflow_steps WHERE workflow_id=? "
        "ORDER BY position DESC, rowid DESC LIMIT 1", (workflow_id,)).fetchone()
    if last is None or str(last["id"]) != str(step.id):
        raise CandidateApprovalError("候选批准只能发生在工作流最后一步")


def _require_old_blocked_checkpoint(store: Any, workflow: Any, step: Any,
                                    approval_checkpoint_id: str,
                                    transition_checkpoint_id: str) -> Any:
    if not str(approval_checkpoint_id or "").strip():
        raise CandidateApprovalError("候选批准缺少旧 blocked checkpoint id")
    if not str(transition_checkpoint_id or "").strip():
        raise CandidateApprovalError("候选批准缺少 transition checkpoint id")
    if approval_checkpoint_id == transition_checkpoint_id:
        raise CandidateApprovalError("旧 blocked checkpoint 不能复用为 transition checkpoint")
    if store._connection.execute(
            "SELECT 1 FROM checkpoints WHERE id=?", (transition_checkpoint_id,)).fetchone():
        raise CandidateApprovalError("transition checkpoint id 已存在")
    row = store._connection.execute(
        "SELECT * FROM checkpoints WHERE id=? AND workflow_id=?",
        (approval_checkpoint_id, getattr(workflow, "id", ""))).fetchone()
    if row is None:
        raise CandidateApprovalError("候选批准 checkpoint 不存在或不属于当前工作流")
    if str(row["step_id"]) != str(step.id):
        raise CandidateApprovalError("候选批准 checkpoint 不属于 comp-final-audit 步骤")
    try:
        state = json.loads(row["state"])
    except (TypeError, json.JSONDecodeError) as exc:
        raise CandidateApprovalError("候选批准 checkpoint state 不是合法 JSON") from exc
    if not isinstance(state, dict) or state.get("status") != "waiting_checkpoint":
        raise CandidateApprovalError("候选批准 checkpoint 不是旧 blocked checkpoint")
    manifest = state.get("manifest")
    artifacts = manifest.get("artifacts") if isinstance(manifest, dict) else None
    if not isinstance(artifacts, list) or not artifacts:
        raise CandidateApprovalError("候选批准 checkpoint 缺少 manifest.artifacts")
    latest = store._connection.execute(
        "SELECT id FROM checkpoints WHERE step_id=? ORDER BY created_at DESC, rowid DESC LIMIT 1",
        (step.id,)).fetchone()
    if latest is None or str(latest["id"]) != str(approval_checkpoint_id):
        raise CandidateApprovalError("候选批准 checkpoint 不是该步骤最新的 blocked checkpoint")
    workspace_text = str(_workflow_metadata(workflow).get("workspace") or "").strip()
    if not workspace_text:
        raise CandidateApprovalError("候选工作流缺少 workspace metadata，无法校验产物 manifest")
    from .artifact_manifest import ArtifactManifest
    validated = ArtifactManifest.validate(Path(workspace_text), list(artifacts))
    if not validated.get("ok"):
        raise CandidateApprovalError(
            "候选批准 checkpoint 的 manifest 已失效（产物缺失或哈希变化）")
    return row


def _frozen_approval_policy(candidate: Any) -> dict[str, Any]:
    acceptance = candidate.acceptance if isinstance(candidate.acceptance, dict) else {}
    if _canonical_sha256(acceptance) != str(candidate.acceptance_sha256 or ""):
        raise CandidateApprovalError("候选验收合同摘要与冻结值不一致")
    policy = acceptance.get("approval_policy") if isinstance(acceptance.get("approval_policy"), dict) else {}
    if policy.get("require_human") is not True:
        raise CandidateApprovalError("候选验收合同未冻结 require_human=true 的审批策略")
    approvers = [str(value).strip() for value in (policy.get("approvers") or [])
                 if str(value).strip()]
    if not approvers:
        raise CandidateApprovalError("候选验收合同的审批人白名单为空")
    return policy


def _require_approver(policy: Mapping[str, Any], approved_by: str) -> str:
    approver = str(approved_by or "").strip()
    if not approver:
        raise CandidateApprovalError("候选批准必须由人类操作者署名（approved_by 为空）")
    approvers = [str(value).strip() for value in (policy.get("approvers") or [])
                 if str(value).strip()]
    if approver not in approvers:
        raise CandidateApprovalError("approved_by 不在候选冻结的审批人白名单内")
    hit = _agent_self_reference_hit(approver)
    if hit:
        raise CandidateApprovalError(f"approved_by 命中 agent 自指词「{hit}」，禁止 agent 自批")
    return approver


def _bound_candidate(store: Any, workflow: Any, candidate_id: str) -> Any:
    metadata = _workflow_metadata(workflow)
    bound_id = _candidate_id_from_metadata(metadata)
    requested = str(candidate_id or "").strip()
    if not requested:
        raise CandidateApprovalError("候选审批缺少 candidate_id")
    if bound_id != requested:
        raise CandidateApprovalError("candidate_id 与工作流 metadata 绑定不一致")
    try:
        candidate = store.get_candidate(requested)
    except KeyError as exc:
        raise CandidateApprovalError(f"未知候选: {requested}") from exc
    if str(candidate.delivery_workflow_id or "") != str(workflow.id):
        raise CandidateApprovalError("候选未绑定到当前交付工作流")
    if str(candidate.status) != "in_delivery":
        raise CandidateApprovalError(f"候选状态不是 in_delivery（当前 {candidate.status}）")
    return candidate


def _candidate_for_workflow(store: Any, workflow: Any) -> Any:
    candidate_id = _candidate_id_from_metadata(_workflow_metadata(workflow))
    if not candidate_id:
        raise CandidateApprovalError("工作流没有绑定候选")
    try:
        return store.get_candidate(candidate_id)
    except KeyError as exc:
        raise CandidateApprovalError(f"未知候选: {candidate_id}") from exc


def _validate_audit_event_identity(store: Any, workflow: Any, candidate: Any,
                                   step: Any, checkpoint_id: str) -> None:
    """identity checks for rejected/degraded audit facts (no approval semantics)."""
    if not str(checkpoint_id or "").strip():
        raise CandidateApprovalError("候选审批事件缺少 checkpoint_id")
    row = store._connection.execute(
        "SELECT * FROM checkpoints WHERE id=? AND workflow_id=?",
        (checkpoint_id, workflow.id)).fetchone()
    if row is None or str(row["step_id"]) != str(step.id):
        raise CandidateApprovalError("候选审批事件 checkpoint 不属于该步骤")
    if str(candidate.delivery_workflow_id or "") != str(workflow.id):
        raise CandidateApprovalError("候选未绑定到当前交付工作流")


def _normalize_approval_payload(event_payload: Mapping[str, Any], evidence: Mapping[str, Any],
                                candidate: Any, approver: str) -> None:
    if not isinstance(event_payload, dict):
        raise CandidateApprovalError("候选审批事件载荷必须是可变映射")
    payload = event_payload.get("payload")
    if not isinstance(payload, dict):
        payload = {}
        event_payload["payload"] = payload
    payload.update({
        "l1_available": True,
        "agent_approve_seen": False,
        "same_session_approve": False,
        "degraded_host_attestation": False,
        "l1_window_start": str(evidence["l1_window_start"]),
        "attributed_event_count": int(evidence["attributed_event_count"]),
        "approval_policy_sha256": str(evidence["approval_policy_sha256"]),
        "approved_by": approver,
        "candidate_id": str(candidate.id),
    })


def _claimed_attestation(event_payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(event_payload, Mapping):
        return {}
    payload = event_payload.get("payload")
    if isinstance(payload, Mapping):
        return dict(payload)
    return dict(event_payload) if event_payload.get("event_type") == APPROVAL_EVENT_TYPE else {}


def _workflow_metadata(workflow: Any) -> dict[str, Any]:
    metadata = getattr(workflow, "metadata", None)
    return metadata if isinstance(metadata, dict) else {}


def _candidate_id_from_metadata(metadata: Mapping[str, Any]) -> str:
    candidate = metadata.get("delivery_candidate") if isinstance(metadata, Mapping) else None
    return str(candidate.get("candidate_id") or "") if isinstance(candidate, Mapping) else ""


def _get_workflow(store: Any, workflow_id: str) -> Any:
    try:
        return store.get_workflow(workflow_id)
    except KeyError as exc:
        raise CandidateApprovalError(f"未知工作流: {workflow_id}") from exc


def _get_step(store: Any, step_id: str) -> Any:
    try:
        return store.get_step(step_id)
    except KeyError as exc:
        raise CandidateApprovalError(f"未知步骤: {step_id}") from exc


def _agent_self_reference_hit(approved_by: str) -> str:
    """Reuse the engine's canonical word list; fall back conservatively."""
    try:
        from .quality_gates import _agent_self_reference_hit as hit
        return str(hit(approved_by))
    except (ImportError, AttributeError, TypeError):
        tokens = re.split(r"[^0-9a-z\u4e00-\u9fff]+", str(approved_by or "").lower())
        for token in tokens:
            if token in {"agent", "assistant", "claude", "gpt", "codex", "openai",
                         "模型", "助手", "智能体", "机器人"}:
                return token
        return ""


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


__all__ = [
    "APPROVAL_BOUNDARY",
    "CandidateApprovalError",
    "assert_candidate_approval_allowed",
    "collect_candidate_l1_evidence",
]
