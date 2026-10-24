"""统一命令行适配；业务实现位于session/workspace/resources/commands。"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import sys
from engine.step_manifest import atomic_write_json
from engine.workflow_store import WorkflowStore, StepStatus
from .presentation import user_view
SUITE = Path(__file__).resolve().parents[1]

REVIEW_EVIDENCE_FILE = "REVIEW_EXECUTION_EVIDENCE.json"
REVIEW_ROLES = ("reviewer", "visual_reviewer", "editor", "final_reviewer")


def _load_review_roles(path: Path) -> dict:
    """读角色声明文件；角色必须显式命名，不从产物文件名反推。

    接受 {"reviewer": {...}, ...} 或 {"roles": {...}}；四角色必须全员到齐，
    每条只取 session_id/model/output_file（哈希与完成时间由脚本生成）。
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("roles JSON 必须是对象")
    roles = payload.get("roles") if isinstance(payload.get("roles"), dict) else payload
    missing = sorted(set(REVIEW_ROLES) - set(roles))
    extra = sorted(set(roles) - set(REVIEW_ROLES))
    if missing:
        raise ValueError(f"roles JSON 缺少角色: {', '.join(missing)}")
    if extra:
        raise ValueError(f"roles JSON 含未知角色: {', '.join(extra)}")
    cleaned = {}
    for role in REVIEW_ROLES:
        record = roles[role]
        if not isinstance(record, dict):
            raise ValueError(f"{role} 角色记录必须是对象")
        cleaned[role] = {field: record.get(field, "") for field in
                         ("session_id", "model", "output_file")}
    return cleaned


def write_review_evidence(workspace: Path, roles_file: Path) -> dict:
    """由脚本生成 REVIEW_EXECUTION_EVIDENCE.json：哈希与 completed_at 不由模型手填。"""
    from engine.quality_gates import build_review_execution_evidence
    roles = _load_review_roles(roles_file)
    evidence = build_review_execution_evidence(
        workspace, roles, completed_at=datetime.now(timezone.utc).isoformat())
    atomic_write_json(Path(workspace) / REVIEW_EVIDENCE_FILE, evidence)
    return {"status": "ok", "path": REVIEW_EVIDENCE_FILE,
            "roles": {role: {"output_file": record["output_file"],
                             "output_sha256": record["output_sha256"],
                             "completed_at": record["completed_at"]}
                      for role, record in evidence["roles"].items()}}


def register_parser(subparsers):
    parser = subparsers.add_parser("session", help="统一执行会话：阅读/创作/命令/完成")
    sub = parser.add_subparsers(dest="operation", required=True)
    context = sub.add_parser("context", help="领取任务并返回本步技能正文与资源候选")
    context.add_argument("--wf", required=True)
    context.add_argument("--db", required=True)
    context.add_argument("--query", default="")
    context.add_argument("--audit-root", default="")
    for name in ("read", "write", "edit", "run", "finish", "status", "recover",
                 "review-request", "review-receive", "review-evidence", "abandon", "reproduce"):
        command = sub.add_parser(name)
        command.add_argument("--session", required=True)
        if name == "read":
            command.add_argument("--kind", choices=["skill", "asset", "workspace"], default="skill")
            command.add_argument("--name", required=True)
            command.add_argument("--member", default="")
        elif name == "write":
            command.add_argument("--path", required=True)
            source = command.add_mutually_exclusive_group(required=True)
            source.add_argument("--from-file")
            source.add_argument("--stdin", action="store_true")
            command.add_argument("--input", action="append", default=[],
                                 help="显式依赖输入（工作区相对路径，须先 read；可重复）")
        elif name == "edit":
            command.add_argument("--path", required=True)
            change = command.add_mutually_exclusive_group(required=True)
            change.add_argument("--changes-file")
            change.add_argument("--stdin", action="store_true")
            command.add_argument("--input", action="append", default=[],
                                 help="显式依赖输入（工作区相对路径，须先 read；可重复）")
        elif name == "run":
            command.add_argument("--plan", required=True)
            command.add_argument("--force", action="store_true")
            command.add_argument("--finish", action="store_true")
        elif name == "finish":
            command.add_argument("--review-session", default="")
        elif name == "abandon":
            command.add_argument("--reason", required=True)
            command.add_argument("--by", default="")
        elif name == "reproduce":
            command.add_argument("--plan", required=True)
            command.add_argument("--candidate", default="")
        elif name == "review-request":
            command.add_argument("--input", action="append", required=True)
            command.add_argument("--output", required=True)
            command.add_argument("--rubric", required=True)
        elif name == "review-receive":
            command.add_argument("--task", required=True)
            command.add_argument("--response", required=True)
            command.add_argument("--reviewer", required=True)
            command.add_argument("--host-call-id", required=True)
        elif name == "review-evidence":
            command.add_argument("--roles", required=True,
                                 help="角色声明 JSON（四角色各填 session_id/model/output_file）")
        elif name == "recover":
            command.add_argument("--operation-id", required=True)
            command.add_argument("--reason", required=True)
            command.add_argument("--confirm-stopped", action="store_true", required=True)
    parser.set_defaults(session_handler=run_command)
    return parser


def run_command(args):
    from engine.workflow_runner import WorkflowRunner
    from .session import ExecutionSession
    try:
        ticket = None if args.operation == "context" else json.loads(Path(args.session).read_text(encoding="utf-8"))
        db = Path(args.db if ticket is None else ticket["database"]).resolve()
        if not db.is_file():
            raise ValueError("工作流数据库不存在，先启动真实工作流")
        workflow_id = args.wf if ticket is None else ticket["workflow_id"]
        audit_root = Path(args.audit_root or SUITE.parent) if ticket is None else Path(ticket["audit_root"])
        catalog = json.loads((SUITE / "engine/modex-core/templates.json").read_text(encoding="utf-8"))
        with WorkflowStore(db) as store:
            runner = WorkflowRunner(store, catalog, SUITE / "skills", audit_root=audit_root)
            action = None
            if ticket:
                step = store.get_step(ticket["step_id"])
                if (step.attempt_id != ticket["attempt_id"] or
                        (step.revision != ticket["revision"] and not
                         (args.operation == "finish" and step.status in {StepStatus.COMPLETED, StepStatus.BLOCKED}))):
                    raise ValueError("旧会话已失效，不执行或改写下一步")
                action = runner._action_for_step(store.get_workflow(workflow_id), step)
            session = ExecutionSession(runner, workflow_id, action)
            if args.operation == "context":
                result = session.context(args.query)
            elif args.operation == "read":
                result = session.files.read_file(args.name) if args.kind == "workspace" else session.resources.read_resource(args.name, args.kind, args.member)
            elif args.operation == "edit":
                change = json.loads(sys.stdin.read() if args.stdin else Path(args.changes_file).read_text(encoding="utf-8"))
                result = session.files.edit(args.path, change["old"], change["new"],
                                            inputs=getattr(args, "input", None))
            elif args.operation == "write":
                result = session.files.write(args.path, sys.stdin.read() if args.stdin else
                                       Path(args.from_file).read_text(encoding="utf-8"),
                                       inputs=getattr(args, "input", None))
            elif args.operation == "review-request":
                result = session.review.request(args.input, args.output, args.rubric)
            elif args.operation == "review-receive":
                result = session.review.receive(args.task, args.response, args.reviewer, args.host_call_id)
            elif args.operation == "review-evidence":
                result = write_review_evidence(session.workspace, Path(args.roles))
            elif args.operation == "status":
                result = {"status": "ok", "operations": store.execution_operations(action.step_id, action.attempt_id)}
            elif args.operation == "recover":
                operations = store.execution_operations(action.step_id, action.attempt_id)
                if not any(r["id"] == args.operation_id for r in operations):
                    raise ValueError("operation不属于当前步骤")
                store.interrupt_operation(args.operation_id, args.reason)
                result = {"status": "recovered", "execution_success": False}
            elif args.operation == "abandon":
                result = session.abandon(args.reason, args.by)
            elif args.operation == "reproduce":
                result = session.reproduce(args.plan, args.candidate)
            elif args.operation == "run":
                result = session.commands.run_plan(json.loads(Path(args.plan).read_text(encoding="utf-8")), force=args.force)
                if args.finish and result["status"] == "executed":
                    result["completion"] = session.finish()
            else:
                result = session.finish(subagent_session=args.review_session)
        print(json.dumps(user_view(result), ensure_ascii=False, default=str, indent=2))
        completion = result.get("completion", result)
        status = completion.get("machine_audit", completion).get("status", "ok")
        return 1 if status in {"failed", "needs_work", "blocked"} else 0
    except (ValueError, KeyError, OSError, sqlite3.Error) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False))
        return 2
