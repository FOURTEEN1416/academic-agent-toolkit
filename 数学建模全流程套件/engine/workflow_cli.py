"""CLI entry point for agent-in-the-loop workflow engine.

Agent 使用方式：
  python -m engine.workflow_cli caps              # 检测运行时能力
  python -m engine.workflow_cli start --template comp_cumcm --workspace ./ws  # 创建工作流
  python -m engine.workflow_cli next --wf <id>     # 获取下一步动作（agent 用）
  python -m engine.workflow_cli report --wf <id>   # 生成审计报告
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from .opencode_bridge import StepResult
from .runtime_adapter import RuntimePaths
from .workflow_runner import WorkflowRunner
from .workflow_store import WorkflowStore
from .run_logger import RunLogger


ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_INDEX = ROOT / ".engine" / "workflow-index.json"


def default_workflow_db(workspace: Path | str) -> Path:
    """Return the workspace-local workflow database used by default."""
    return Path(workspace) / ".engine" / "workflow.sqlite"


def _read_workflow_index() -> dict[str, str]:
    try:
        data = json.loads(WORKFLOW_INDEX.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def register_workflow_database(workflow_id: str, database: Path | str) -> None:
    """Persist the database location so later CLI commands need only --wf."""
    index = _read_workflow_index()
    index[workflow_id] = str(Path(database).resolve())
    WORKFLOW_INDEX.parent.mkdir(parents=True, exist_ok=True)
    WORKFLOW_INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_workflow_db(workflow_id: str) -> Path:
    """Resolve a workflow database registered by the start command."""
    value = _read_workflow_index().get(workflow_id)
    if not value:
        raise KeyError(f"workflow database is unknown: {workflow_id}; pass --db explicitly")
    return Path(value).resolve()


def resolve_checkpoint_db(checkpoint_id: str) -> Path:
    """Find the unique registered database containing a checkpoint ID."""
    matches = []
    for value in sorted(set(_read_workflow_index().values())):
        database = Path(value).resolve()
        if not database.is_file():
            continue
        try:
            connection = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
            found = connection.execute(
                "SELECT 1 FROM checkpoints WHERE id = ? LIMIT 1", (checkpoint_id,)
            ).fetchone()
            connection.close()
            if found:
                matches.append(database)
        except sqlite3.Error:
            continue
    if len(matches) != 1:
        raise KeyError(f"checkpoint database is unknown or ambiguous: {checkpoint_id}; pass --db explicitly")
    return matches[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenCode 桌面版驱动的工作流引擎")
    sub = parser.add_subparsers(dest="command", required=True)

    # 能力检测
    sub.add_parser("caps")

    # 创建工作流
    start = sub.add_parser("start")
    start.add_argument("--template", required=True)
    start.add_argument("--workspace", required=True)
    start.add_argument("--db", default="")
    start.add_argument("--params", default="{}")

    # 获取下一步动作
    next_cmd = sub.add_parser("next")
    next_cmd.add_argument("--wf", required=True, help="工作流 ID")
    next_cmd.add_argument("--db", default="")

    # 完成当前步骤（agent 执行后调用）
    complete = sub.add_parser("complete")
    complete.add_argument("--wf", required=True)
    complete.add_argument("--ok", default="true")
    complete.add_argument("--artifacts", default="")
    complete.add_argument("--stderr", default="")
    complete.add_argument("--evidence", default="{}", help="Desktop execution evidence as a JSON object")
    complete.add_argument("--db", default="")

    # 批准检查点
    approve = sub.add_parser("approve")
    approve.add_argument("--checkpoint", required=True)
    approve.add_argument("--db", default="")

    # 审计报告
    report = sub.add_parser("report")
    report.add_argument("--wf", required=True)
    report.add_argument("--db", default="")
    report.add_argument("--out", required=True)

    # 操作审计（读取 plugin 的 operations.jsonl + SQLite + evidence）
    audit = sub.add_parser("audit")
    audit.add_argument("--workspace", required=True, help="工作区路径（含 .engine/evidence 与 workflow.sqlite）")
    audit.add_argument("--out", default="", help="操作审计输出路径（默认 workspace/OPERATION_AUDIT_REPORT.json）")
    audit.add_argument("--db", default="")

    args = parser.parse_args()

    if args.command == "caps":
        print(json.dumps(RuntimePaths.discover(ROOT).capabilities(), ensure_ascii=False, indent=2))
        return 0

    workspace_for_db = Path(args.workspace) if args.command in {"start", "audit"} else None
    if args.db:
        db = Path(args.db)
    elif workspace_for_db is not None:
        db = default_workflow_db(workspace_for_db)
    elif args.command in {"next", "complete", "report"}:
        try:
            db = resolve_workflow_db(args.wf)
        except KeyError as exc:
            parser.error(str(exc))
    elif args.command == "approve":
        try:
            db = resolve_checkpoint_db(args.checkpoint)
        except KeyError as exc:
            parser.error(str(exc))
    else:
        db = ROOT / ".engine" / "workflow.sqlite"
    db.parent.mkdir(parents=True, exist_ok=True)
    catalog = json.loads((ROOT / "engine" / "modex-core" / "templates.json").read_text(encoding="utf-8"))

    with WorkflowStore(db) as store:
        runner = WorkflowRunner(store, catalog, ROOT / "skills", audit_root=ROOT.parent)

        if args.command == "start":
            workflow = runner.start(args.template, Path(args.workspace), json.loads(args.params))
            register_workflow_database(workflow.id, db)
            result = json.dumps({
                "workflow_id": workflow.id,
                "status": workflow.status,
                "created_at": workflow.created_at,
            }, ensure_ascii=False, indent=2)
            print(result)
            return 0

        if args.command == "next":
            result = runner.next_action(args.wf)
            output = {
                "status": result.status,
                "message": result.message,
            }
            if result.action:
                output["action"] = {
                    "step_id": result.action.step_id,
                    "position": result.action.position,
                    "skill_name": result.action.skill_name,
                    "display_name": result.action.display_name,
                    "workspace": str(result.action.workspace),
                    "skill_path": str(result.action.skill_path),
                    "output_files": result.action.output_files,
                    "primary_output": result.action.primary_output,
                    "has_checkpoint": result.action.has_checkpoint,
                    "checkpoint_type": result.action.checkpoint_type,
                    "instructions": result.action.execution_instructions(),
                }
            print(json.dumps(output, ensure_ascii=False, indent=2))
            return 0 if result.status in ("advanced", "completed") else 1

        if args.command == "complete":
            step_result = StepResult(
                ok=args.ok.lower() == "true",
                artifacts=[a.strip() for a in args.artifacts.split(",") if a.strip()],
                stderr=args.stderr,
                metadata={"execution_evidence": json.loads(args.evidence)},
            )
            result = runner.complete_step(args.wf, step_result)
            output = {
                "status": result.status,
                "step_id": result.step_id,
                "message": result.message,
            }
            print(json.dumps(output, ensure_ascii=False, indent=2))
            return 0 if result.status in ("advanced", "completed", "waiting_checkpoint") else 1

        if args.command == "approve":
            result = runner.approve_checkpoint(args.checkpoint, {"approved": True})
            output = {"status": result.status, "message": result.message}
            if result.action:
                output["action"] = {
                    "skill_name": result.action.skill_name,
                    "workspace": str(result.action.workspace),
                    "instructions": result.action.execution_instructions(),
                }
            print(json.dumps(output, ensure_ascii=False, indent=2))
            return 0

        if args.command == "report":
            report = store.workflow_timeline(args.wf)
            Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"报告已保存: {args.out}")
            return 0

        if args.command == "audit":
            from .audit_store import write_audit_report
            workspace = Path(args.workspace)
            out = Path(args.out) if args.out else workspace / "OPERATION_AUDIT_REPORT.json"
            target = write_audit_report(workspace, ROOT.parent, out, workflow_db=db)
            print(f"审计报告已保存: {target}")
            return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
