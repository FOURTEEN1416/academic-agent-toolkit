"""CLI entry point for agent-in-the-loop workflow engine (host-agnostic).

任意 Agent 使用方式（无需 OpenCode/ZCode）：
  python -m engine.workflow_cli boot                # 驱动协议契约
  python -m engine.workflow_cli probe               # 能力探测 + TOOL_GAP
  python -m engine.workflow_cli forge --tool ...    # 自适应铸造工具/技能
  python -m engine.workflow_cli caps                # 可选运行时命令能力
  python -m engine.workflow_cli start --template comp_cumcm --workspace ./ws
  python -m engine.workflow_cli next --wf <id>      # 获取下一步动作
  python -m engine.workflow_cli retry --wf <id> --by <操作者>
  python -m engine.workflow_cli approve --checkpoint <UUID> --by <批准人>
  python -m engine.workflow_cli stall --wf <id> [--hours 12]
  python -m engine.workflow_cli backfill --wf <id> --step <skill_name> --artifact <path>
  python -m engine.workflow_cli report --wf <id>
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from .agent_bridge import StepResult
from .agent_protocol import bootstrap as agent_bootstrap
from .capability_probe import probe as capability_probe
from .runtime_adapter import RuntimePaths
from .tool_forge import forge_adapter, forge_skill, forge_tool, forge_from_gap


def _load_runner_types():
    """惰性加载重型引擎依赖（quality_gates→fitz 等），使 boot/probe/forge 可在最小环境运行。"""
    from .workflow_runner import WorkflowRunner
    from .workflow_store import WorkflowStore
    return WorkflowRunner, WorkflowStore


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


def _action_payload(action) -> dict:
    """StepAction 的 CLI JSON 序列化（next/retry 共用，保持输出风格一致）。"""
    return {
        "step_id": action.step_id,
        "position": action.position,
        # 手册口径步号（1 起始）：消除 next 输出 position=0 与手册 1-14 的错位困惑
        # （A5 摩擦日志 ②；仅 CLI 输出层字段，不改 StepAction schema）
        "step_number_manual": action.position + 1,
        "skill_name": action.skill_name,
        "display_name": action.display_name,
        "workspace": str(action.workspace),
        "skill_path": str(action.skill_path),
        "output_files": action.output_files,
        "primary_output": action.primary_output,
        "has_checkpoint": action.has_checkpoint,
        "checkpoint_type": action.checkpoint_type,
        "companion_skills": action.companion_skills,
        # C2 资产机制（2026-09-12）：每步非技能资产清单随 next/retry 输出下发
        "assets": action.assets,
        # D3 门禁前移（2026-09-13）：true 时 agent 须在回报 complete 前跑 quick_gates 轻检
        "quick_gates": action.quick_gates,
        "instructions": action.execution_instructions(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="宿主中立的 Agent 工作流引擎（任意智能体可驱动）")
    sub = parser.add_subparsers(dest="command", required=True)

    # 驱动协议契约
    sub.add_parser("boot")

    # 能力检测（旧）
    sub.add_parser("caps")

    # 完整能力探测 + TOOL_GAP
    sub.add_parser("probe")

    # 自适应工具/技能铸造
    forge = sub.add_parser("forge")
    forge.add_argument("--tool", default="", help="铸造 tools/<name>.py")
    forge.add_argument("--skill", default="", help="铸造 skills/<name>/SKILL.md")
    forge.add_argument("--adapter", default="", help="铸造 agents/adapters/<name>/adapter.json")
    forge.add_argument("--purpose", default="", help="铸造目的（写入骨架契约）")
    forge.add_argument("--linked-tool", default="", help="技能骨架关联的工具名（默认与 skill 同名）")
    forge.add_argument("--force", action="store_true", help="覆盖已存在文件")
    forge.add_argument("--gap", default="", help="probe 输出的 gaps 条目 JSON；按 gap 自动建议/铸造")

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

    # 重试失败步骤（A2 审计修复：FAILED 后此前无带内恢复路径，恢复被迫手改 SQLite）
    retry = sub.add_parser("retry")
    retry.add_argument("--wf", required=True, help="工作流 ID")
    retry.add_argument("--by", default="", help="操作者标识（落入 step_retry 审计事件）")
    retry.add_argument("--db", default="")

    # D1 断链告警：扫描停滞步骤（RUNNING 超时未回报 / checkpoint 等批悬置）
    stall = sub.add_parser("stall")
    stall.add_argument("--wf", required=True, help="工作流 ID")
    stall.add_argument("--hours", type=float, default=12.0,
                       help="停滞阈值（小时，默认 12；命中输出 alert=true 且退出码 1）")
    stall.add_argument("--db", default="")

    # D1 手工补录：绕开 runner 完成的步骤把产物哈希/真实命令补进审计链
    backfill = sub.add_parser("backfill")
    backfill.add_argument("--wf", required=True, help="工作流 ID")
    backfill.add_argument("--step", required=True, help="步骤 skill_name（如 comp-code）")
    backfill.add_argument("--artifact", action="append", default=[],
                          help="产物相对路径（相对工作区根，可多次）")
    backfill.add_argument("--command", action="append", dest="backfill_commands", default=[],
                          help="手工执行的真实命令（可多次，进 STEP_MANIFEST.commands）")
    backfill.add_argument("--note", default="", help="补录说明（进事件 payload）")
    backfill.add_argument("--by", default="", help="补录人标识（建议必填，落 step_backfilled 事件）")
    backfill.add_argument("--db", default="")

    # 批准检查点
    approve = sub.add_parser("approve")
    approve.add_argument("--checkpoint", required=True)
    approve.add_argument("--by", default="",
                         help="批准人标识（必填非空，写入批准事件防 agent 自批准无痕）")
    approve.add_argument("--db", default="")

    # 审计报告
    report = sub.add_parser("report")
    report.add_argument("--wf", required=True)
    report.add_argument("--db", default="")
    report.add_argument("--out", required=True)

    # 最终交付审计
    final_audit = sub.add_parser("final-audit")
    final_audit.add_argument("--workspace", required=True)
    final_audit.add_argument("--db", default="")
    final_audit.add_argument("--out", default="")

    # 操作审计（读取 plugin 的 operations.jsonl + SQLite + evidence）
    audit = sub.add_parser("audit")
    audit.add_argument("--workspace", required=True, help="工作区路径（含 .engine/evidence 与 workflow.sqlite）")
    audit.add_argument("--out", default="", help="操作审计输出路径（默认 workspace/OPERATION_AUDIT_REPORT.json）")
    audit.add_argument("--db", default="")

    args = parser.parse_args()

    if args.command == "boot":
        print(json.dumps(agent_bootstrap(ROOT), ensure_ascii=False, indent=2))
        return 0

    if args.command == "caps":
        print(json.dumps(RuntimePaths.discover(ROOT).capabilities(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "probe":
        print(json.dumps(capability_probe(ROOT), ensure_ascii=False, indent=2))
        return 0

    if args.command == "forge":
        force = bool(getattr(args, "force", False))
        purpose = str(getattr(args, "purpose", "") or "")
        gap_raw = str(getattr(args, "gap", "") or "").strip()
        results = []
        if gap_raw:
            try:
                gap = json.loads(gap_raw)
            except json.JSONDecodeError as exc:
                print(json.dumps({"status": "error", "message": f"gap JSON 无效: {exc}"},
                                 ensure_ascii=False, indent=2))
                return 2
            results.append(forge_from_gap(gap if isinstance(gap, dict) else {}, ROOT, force=force))
        tool_name = str(getattr(args, "tool", "") or "").strip()
        skill_name = str(getattr(args, "skill", "") or "").strip()
        adapter_name = str(getattr(args, "adapter", "") or "").strip()
        if tool_name:
            results.append(forge_tool(tool_name, purpose, ROOT, force=force))
        if skill_name:
            linked = str(getattr(args, "linked_tool", "") or "").strip() or None
            results.append(forge_skill(skill_name, purpose, ROOT, tool_name=linked, force=force))
        if adapter_name:
            results.append(forge_adapter(adapter_name, purpose, ROOT, force=force))
        if not results:
            print(json.dumps({
                "status": "error",
                "message": "forge 需要 --tool/--skill/--adapter/--gap 之一",
                "example": (
                    "python -m engine.workflow_cli forge --tool my-tool "
                    "--purpose \"...\" [--skill my-skill] [--force]"
                ),
            }, ensure_ascii=False, indent=2))
            return 2
        print(json.dumps({"status": "ok", "results": results}, ensure_ascii=False, indent=2))
        return 0

    # 以下命令需要完整引擎（store/runner/quality_gates）
    WorkflowRunner, WorkflowStore = _load_runner_types()

    workspace_for_db = Path(args.workspace) if args.command in {"start", "audit", "final-audit"} else None
    if args.db:
        db = Path(args.db)
    elif workspace_for_db is not None:
        db = default_workflow_db(workspace_for_db)
    elif args.command in {"next", "complete", "retry", "report", "stall", "backfill"}:
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
                output["action"] = _action_payload(result.action)
            if result.checkpoint_id:
                # A5 ⑦ 修复：blocked 时直接给出待批 checkpoint UUID
                output["checkpoint_id"] = result.checkpoint_id
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
            if result.checkpoint_id:
                # A5 ⑦ 修复：waiting_checkpoint 时直接给出待批 checkpoint UUID
                output["checkpoint_id"] = result.checkpoint_id
            print(json.dumps(output, ensure_ascii=False, indent=2))
            return 0 if result.status in ("advanced", "completed", "waiting_checkpoint") else 1

        if args.command == "retry":
            result = runner.retry_last_failed(args.wf, by=str(args.by or "").strip())
            output = {
                "status": result.status,
                "step_id": result.step_id,
                "message": result.message,
            }
            if result.action:
                output["action"] = _action_payload(result.action)
            print(json.dumps(output, ensure_ascii=False, indent=2))
            return 0 if result.status in ("advanced", "completed") else 1

        if args.command == "stall":
            report = runner.detect_stalled(args.wf, stall_hours=float(args.hours))
            print(json.dumps(report, ensure_ascii=False, indent=2))
            # 告警即非零退出，便于脚本/钩子感知断链
            return 1 if report["alert"] else 0

        if args.command == "backfill":
            result = runner.backfill_step(
                args.wf, str(args.step).strip(),
                artifacts=[a.strip() for a in args.artifact if a.strip()],
                commands=[c for c in args.backfill_commands if c.strip()],
                note=str(args.note or ""), by=str(args.by or "").strip())
            output = {
                "status": result.status,
                "step_id": result.step_id,
                "message": result.message,
            }
            print(json.dumps(output, ensure_ascii=False, indent=2))
            return 0 if result.status in ("advanced", "completed") else 1

        if args.command == "approve":
            by = str(getattr(args, "by", "") or "").strip()
            if not by:
                parser.error(
                    "approve 缺少必填的 --by <批准人标识>：批准事件必须记录谁批准了检查点"
                    "（防 agent 自批准且无痕）。正确用法: "
                    "python -m engine.workflow_cli approve --checkpoint <UUID> "
                    "[--db <workflow.sqlite 路径>] --by <批准人>"
                )
            result = runner.approve_checkpoint(args.checkpoint, {"approved": True, "approved_by": by})
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

        if args.command == "final-audit":
            from .audit_store import write_final_audit_report
            workspace = Path(args.workspace)
            out = Path(args.out) if args.out else workspace / "AUDIT_REPORT.json"
            target = write_final_audit_report(workspace, ROOT.parent, out, workflow_db=db)
            print(f"最终审计报告已保存: {target}")
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
