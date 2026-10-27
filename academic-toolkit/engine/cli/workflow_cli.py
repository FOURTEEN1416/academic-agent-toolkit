"""CLI entry point for agent-in-the-loop workflow engine (host-agnostic).

任意 Agent 使用方式：
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
  python -m engine.workflow_cli backfill --wf <id> --step <skill_name> --artifact <path> --evidence '<同构 execution_evidence JSON>'
      # 绑定步骤补录二选一：--evidence 全量校验，或 --waive-binding --waive-reason <理由>（落审计）
  python -m engine.workflow_cli report --wf <id>
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

from .._paths import TOOLBOX_ROOT
from ..agent_bridge import StepResult
from ..host.agent_protocol import bootstrap as agent_bootstrap
from ..host.capability_probe import probe as capability_probe
from ..telemetry.run_logger import RunLogger, RunLogEntry
from ..host.runtime_adapter import RuntimePaths
from ..storage.step_manifest import atomic_write_json
from ..host.tool_forge import forge_skill, forge_tool, forge_from_gap


def _load_runner_types():
    """惰性加载重型引擎依赖（quality_gates→fitz 等），使 boot/probe/forge 可在最小环境运行。"""
    from ..orchestration.workflow_runner import WorkflowRunner
    from ..storage.workflow_store import WorkflowStore
    return WorkflowRunner, WorkflowStore


ROOT = TOOLBOX_ROOT
# 2026-09-23 v2.0 改造：引擎运行态（索引/默认库/审计）统一收敛到仓库根 .engine/ 一处
# ——与 L1 hook 的 audit_root=ROOT.parent 同源；套件目录与 engine/ 源码目录内不再落运行态。
STATE_ROOT = ROOT.parent / ".engine"
WORKFLOW_INDEX = STATE_ROOT / "workflow-index.json"


def default_workflow_db(workspace: Path | str) -> Path:
    """Return the workspace-local workflow database used by default."""
    return Path(workspace) / ".engine" / "workflow.sqlite"


class WorkflowCliError(Exception):
    """CLI 业务错误：顶层统一以 {"status":"error"} JSON 输出并以退出码 2 结束。"""


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
    atomic_write_json(WORKFLOW_INDEX, index)


def prune_workflow_index() -> list[str]:
    """B3-2：移除指向已不存在数据库的孤儿注册项，返回被清理的 workflow_id。"""
    index = _read_workflow_index()
    stale = [wf for wf, db in sorted(index.items()) if not Path(db).is_file()]
    if stale:
        for wf in stale:
            index.pop(wf, None)
        atomic_write_json(WORKFLOW_INDEX, index)
    return stale


def resolve_workflow_db(workflow_id: str) -> Path:
    """Resolve a workflow database registered by the start command."""
    value = _read_workflow_index().get(workflow_id)
    if not value:
        raise KeyError(f"workflow database is unknown: {workflow_id}; pass --db explicitly")
    return Path(value).resolve()


def _probe_workflow_db(workflow_id: str) -> Path | None:
    """B3-2：索引未命中时的回退探测——在默认库与各工作区库中直接找 workflow_id。

    索引文件可能缺失/落后（新 clone、手工删除、原子写前崩溃）；此时按位置
    约定扫描，命中唯一库即回退成功（并由调用方回写索引）。
    """
    candidates = [STATE_ROOT / "workflow.sqlite"]
    workspaces_root = ROOT / "workspaces"
    if workspaces_root.is_dir():
        candidates.extend(sorted(workspaces_root.glob("*/.engine/workflow.sqlite")))
    matches: list[Path] = []
    for database in candidates:
        if not database.is_file():
            continue
        try:
            connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
            found = connection.execute(
                "SELECT 1 FROM workflows WHERE id = ? LIMIT 1", (workflow_id,)
            ).fetchone()
            connection.close()
        except sqlite3.Error:
            continue
        if found:
            matches.append(database)
    if len(matches) == 1:
        return matches[0]
    return None


def _keyerror_message(exc: KeyError) -> str:
    return str(exc.args[0]) if exc.args else str(exc)


def resolve_checkpoint_db(checkpoint_id: str) -> Path:
    """Find the unique registered database containing a checkpoint ID."""
    matches = []
    for value in sorted(set(_read_workflow_index().values())):
        database = Path(value).resolve()
        if not database.is_file():
            continue
        try:
            connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
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


def _workflow_workspace(store, workflow_id: str) -> Path | None:
    """从 workflow 元数据反查工作区路径（CLI 每命令一进程，workspace 不在 argv 上）。"""
    row = store._connection.execute(
        "SELECT metadata FROM workflows WHERE id = ?", (workflow_id,)
    ).fetchone()
    if row is None:
        return None
    workspace = json.loads(row["metadata"]).get("workspace") or ""
    return Path(workspace) if workspace else None


def _checkpoint_workflow_id(store, checkpoint_id: str) -> str | None:
    row = store._connection.execute(
        "SELECT workflow_id FROM checkpoints WHERE id = ?", (checkpoint_id,)
    ).fetchone()
    return row["workflow_id"] if row else None


def _merge_existing_run_log(logger: RunLogger, path: Path) -> None:
    """B3-1：把既有 run_<wf>.json 的事件前置合并进本次内存日志。

    CLI 每命令一进程，若不合并，固定名覆盖会把累积时间线冲成仅本次命令的事件。
    """
    try:
        old = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(old, list):
        return
    logger._entries[:0] = [RunLogEntry(**e) for e in old if isinstance(e, dict)]


def _attach_run_logger(runner, store, args) -> str | None:
    """B3-1：CLI 路径上惰性重建 RunLogger（此前恒 None，_log 静默跳过、日志全丢）。

    按 workspace 约定定位日志目录（start 用 --workspace，其余从工作流元数据反查），
    并合并既有 run 日志。返回命令结束时应落盘的 workflow_id（start 为 None，
    因 id 在 start() 里才产生）。
    """
    workflow_id = str(getattr(args, "wf", "") or "") or None
    workspace = Path(args.workspace) if args.command == "start" else None
    if workspace is None and workflow_id:
        workspace = _workflow_workspace(store, workflow_id)
    if workspace is None and args.command == "approve":
        owner = _checkpoint_workflow_id(store, args.checkpoint)
        if owner:
            workspace = _workflow_workspace(store, owner)
    if workspace is None:
        return workflow_id
    log_dir = workspace / ".engine" / "logs"
    logger = RunLogger(log_dir)
    if workflow_id:
        _merge_existing_run_log(logger, log_dir / f"run_{workflow_id}.json")
    runner.logger = logger
    return workflow_id


def _save_run_log(runner, workflow_id: str | None) -> None:
    """B3-1：命令结束前把运行日志落盘（固定名 run_<wf>.json，位置确定可定位）。

    落盘失败不阻断主流程（与 runner._log 的静默语义一致）。
    """
    logger = getattr(runner, "logger", None)
    if logger is None or not workflow_id:
        return
    try:
        logger.save(workflow_id, filename=f"run_{workflow_id}.json")
    except Exception:
        pass


def _read_json_input(inline: str, file_path: str, option: str) -> Any:
    """B3-3：内联 JSON 与 --*-file 二选一解析；文件版缓解 Windows 引号转义地狱。"""
    if file_path:
        if inline and inline.strip() not in ("", "{}"):
            raise WorkflowCliError(f"{option} 与内联 JSON 参数二选一，请勿同时提供")
        try:
            return json.loads(Path(file_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise WorkflowCliError(f"{option} 读取失败: {exc}") from None
    return json.loads(inline)


_SESSION_TICKET_FIELDS = ("database", "workflow_id", "step_id", "attempt_id", "revision")


def _load_session_ticket(path: str) -> dict[str, Any]:
    """读取执行会话 ticket（context 落盘的真实身份）；缺字段即拒绝，不猜。"""
    value = str(path or "").strip()
    if not value:
        raise WorkflowCliError("--session 需要 ticket 路径（工作区 .engine/sessions/<attempt_id>.json）")
    try:
        ticket = json.loads(Path(value).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowCliError(f"--session ticket 读取失败: {exc}") from None
    if not isinstance(ticket, dict):
        raise WorkflowCliError("--session ticket 必须是 JSON 对象")
    missing = [name for name in _SESSION_TICKET_FIELDS if ticket.get(name) in (None, "")]
    if missing:
        raise WorkflowCliError(f"--session ticket 缺少字段: {', '.join(missing)}")
    try:
        int(ticket["revision"])
    except (TypeError, ValueError):
        raise WorkflowCliError("--session ticket 的 revision 必须是整数") from None
    return ticket


def _session_identity(ticket: dict[str, Any]) -> tuple[str, str, str, int]:
    return (str(ticket["workflow_id"]), str(ticket["step_id"]),
            str(ticket["attempt_id"]), int(ticket["revision"]))


def _reject_handbuilt_final_evidence(store, step_id: str, evidence: dict) -> None:
    """终审/终审复审不接受无持久 collection 的手拼证据。

    这两个步骤的证据必须来自真实执行集合（--session / execution.session finish），
    或由集成方提供带 collection 的完整记录；手拼 commands 无法证明"审计真的跑过"。
    其他步骤保留 legacy 兼容（身份字段已由引擎回填）。
    """
    if isinstance(evidence.get("collection"), dict) and evidence.get("collection"):
        return
    target = str(step_id or evidence.get("step_id") or "")
    if not target:
        return  # 身份缺失由 runner 的 target 校验显式拒绝
    try:
        step = store.get_step(target)
        workflow = store.get_workflow(step.workflow_id)
    except (KeyError, ValueError):
        return
    if isinstance(workflow.metadata.get("delivery_candidate"), dict):
        raise WorkflowCliError(
            f"候选交付工作流不接受任何步骤的 legacy --evidence-file 手拼 evidence（步骤 {step.name}）。"
            "候选验收必须走 --session <ticket> 的真实执行集合（preflight/complete）。")
    if step.name in {"comp-final-audit", "comp-final-review"}:
        raise WorkflowCliError(
            f"步骤 {step.name} 不接受没有执行集合（collection）的手拼 evidence。"
            "终审/终审复审证据只能由引擎按真实操作取证：改用 "
            "--session <工作区/.engine/sessions/<attempt_id>.json>"
            "（preflight 只读验收 / complete 提交），或经 execution.session finish 提交。")


def _action_payload(action, *, contract_tier: str = "", requires_collection: bool | None = None) -> dict:
    """StepAction 的 CLI JSON 序列化（next/retry/approve 共用，保持输出风格一致）。"""
    return {
        "workflow_id": action.workflow_id,
        "step_id": action.step_id,
        "attempt_id": action.attempt_id,
        "expected_revision": action.expected_revision,
        "contract_tier": contract_tier or getattr(action, "contract_tier", None) or "delivery",
        "requires_collection": (bool(getattr(action, "requires_collection", False))
                                if requires_collection is None else requires_collection),
        "skill_sha256": action.skill_sha256,
        "required_checks": action.required_checks,
        "output_specs": action.output_specs,
        "requires_subagent": action.requires_subagent,
        "review_scope": action.review_scope,
        "skill_binding": action.skill_binding,
        "quick_gates_max_pages": action.quick_gates_max_pages,
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
        # D3 门禁前移（2026-09-13；W5 起改由引擎执行）：true 时 finish 的
        # early_quality 直接跑页数/字号/泄漏轻检，不再要求 agent 先手跑脚本。
        "quick_gates": action.quick_gates,
        "instructions": action.execution_instructions(),
    }


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    try:
        return _run_command(args, parser)
    except WorkflowCliError as exc:
        # B3-3 错误契约：业务异常以 JSON 输出（与 boot/probe 的 JSON 输出对称），退出码 2
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    except json.JSONDecodeError as exc:
        print(json.dumps({"status": "error", "message": f"JSON 解析失败: {exc}"},
                         ensure_ascii=False, indent=2))
        return 2
    except KeyError as exc:
        # 兜底：runner 内部对未知 workflow/checkpoint 抛裸 KeyError，统一进错误契约
        print(json.dumps({"status": "error",
                          "message": f"未知的 workflow/checkpoint 标识: {_keyerror_message(exc)}"},
                         ensure_ascii=False, indent=2))
        return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="宿主中立的 Agent 工作流引擎（任意智能体可驱动）")
    sub = parser.add_subparsers(dest="command", required=True)

    # 驱动协议契约
    sub.add_parser("boot")

    # 能力检测（旧）
    sub.add_parser("caps")
    from execution.cli import register_parser
    register_parser(sub)

    # 完整能力探测 + TOOL_GAP
    sub.add_parser("probe")

    # 自适应工具/技能铸造
    forge = sub.add_parser("forge")
    forge.add_argument("--tool", default="", help="铸造 tools/<name>.py")
    forge.add_argument("--skill", default="", help="铸造 skills/<name>/SKILL.md")
    forge.add_argument("--purpose", default="", help="铸造目的（写入骨架契约）")
    forge.add_argument("--linked-tool", default="", help="技能骨架关联的工具名（默认与 skill 同名）")
    forge.add_argument("--force", action="store_true", help="覆盖已存在文件")
    forge.add_argument("--gap", default="", help="probe 输出的 gaps 条目 JSON；按 gap 自动建议/铸造")
    forge.add_argument("--evidence-file", default="",
                       help="从 JSON 文件读取 forge 输入（--gap 的文件版；缓解 Windows 引号转义）")

    # 创建工作流
    start = sub.add_parser("start")
    start.add_argument("--template", required=True)
    start.add_argument("--workspace", required=True)
    start.add_argument("--db", default="")
    start.add_argument("--params", default="{}")
    start.add_argument("--mode", choices=["delivery", "explore"], default="delivery",
                       help="交付档 delivery（默认）/ 探索档 explore（剔除终审、无步内 checkpoint）")
    start.add_argument("--candidate", default="",
                       help="候选 ID：只建 promotion-carry/复现/review/终审步骤（审批人白名单只来自候选冻结值）")

    # G2 promotion：从已完成 explore 工作流冻结交付候选（不提供 promote-approve）
    promote = sub.add_parser("promote")
    promote.add_argument("--wf", required=True, help="源 explore 工作流 ID")
    promote.add_argument("--root", action="append", required=True,
                         help="交付根产物（工作区相对路径，可多次）")
    promote.add_argument("--by", required=True, help="promote 操作者署名")
    promote.add_argument("--template", default="", help="交付模板（缺省沿用源工作流模板）")
    promote.add_argument("--db", default="")

    # G2 abandon：仅 explore 档；保留操作事实并使旧 ticket 失效
    abandon = sub.add_parser("abandon")
    abandon.add_argument("--wf", required=True)
    abandon.add_argument("--reason", required=True)
    abandon.add_argument("--by", required=True)
    abandon.add_argument("--db", default="")

    # 获取下一步动作
    next_cmd = sub.add_parser("next")
    next_cmd.add_argument("--wf", required=True, help="工作流 ID")
    next_cmd.add_argument("--db", default="")
    # SKILL_LOST 求救重发：模型上下文丢失技能正文时，执行方带 --resend 重拉全量
    next_cmd.add_argument("--resend", action="store_true",
                          help="强制重发技能正文全文（模型声明 SKILL_LOST 后使用）")

    # 完成当前步骤（agent 执行后调用）
    complete = sub.add_parser(
        "complete",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "首选：--session <ticket>（execution.session context 落盘的 .engine/sessions/<attempt_id>.json）\n"
            "  python -m engine.workflow_cli complete --session .engine/sessions/<attempt_id>.json\n"
            "  身份与证据由引擎按真实操作机械组装，无需手填哈希/返回码。\n"
            "旧式手工证据（legacy 兼容；comp-final-audit / comp-final-review 拒绝无 collection 的手拼证据）：\n"
            "  --evidence-file evidence.json（schema_version + commands/inputs/outputs 必须真实提供）；\n"
            "  agent/attempt_id/expected_revision/skill_name/skill_sha256 由引擎从 StepAction 回填，不必手抄；\n"
            "  commands 缺真实命令、或写成描述性伪命令，照旧拒绝。"
        ),

    )
    complete.add_argument("--wf", default="", help="工作流 ID（--session 时从 ticket 读取）")
    complete.add_argument("--ok", default="true")
    complete.add_argument("--artifacts", default="")
    complete.add_argument("--stderr", default="")
    complete.add_argument("--session", default="",
                          help="执行会话 ticket 路径（首选入口；身份/证据由引擎取证）")
    complete.add_argument("--evidence", default="{}", help="legacy：手工 execution evidence JSON 对象")
    complete.add_argument("--evidence-file", default="",
                          help="legacy：从 JSON 文件读取 execution evidence（与 --evidence 二选一）")
    complete.add_argument("--db", default="")
    complete.add_argument("--step-id", default="", help="next 返回的 step_id，失败回报也必须指定")
    complete.add_argument("--attempt-id", default="")
    complete.add_argument("--expected-revision", type=int, default=None)
    complete.add_argument("--request-id", default="", help="同一提交重发使用同一标识")
    preflight = sub.add_parser("preflight", help="只读批量验收，不推进工作流")
    preflight.add_argument("--wf", default="", help="工作流 ID（--session 时从 ticket 读取）")
    preflight.add_argument("--db", default="")
    preflight.add_argument("--artifacts", default="")
    preflight.add_argument("--session", default="",
                           help="执行会话 ticket 路径：引擎取证后只读验收，不写状态")
    preflight.add_argument("--evidence", default="{}", help="legacy：手工 execution evidence JSON 对象")
    preflight.add_argument("--evidence-file", default="")

    # 重试失败步骤（A2 审计修复：FAILED 后此前无带内恢复路径，恢复被迫手改 SQLite）
    retry = sub.add_parser("retry")
    retry.add_argument("--wf", required=True, help="工作流 ID")
    retry.add_argument("--by", default="", help="操作者标识（落入 step_retry 审计事件）")
    retry.add_argument("--override-reason", default="", dest="override_reason",
                       help="返修预算耗尽（repair_budget_exhausted）时的显式覆盖理由；"
                            "必填且须配 --by，写入 repair_override 审计事件（不是批准）")
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
    backfill.add_argument("--evidence", default="",
                          help="与 complete_step 同构的 execution_evidence JSON（字符串）。"
                               "步骤声明绑定（skill_binding/companion_skills/assets）时必填，"
                               "否则须 --waive-binding；含真实 skill_sha256 绑定签名，走同一校验链")
    backfill.add_argument("--evidence-file", default="",
                          help="从文件读取真实补录证据，与 --evidence 二选一")
    backfill.add_argument("--waive-binding", action="store_true", dest="waive_binding",
                          help="显式豁免补录的绑定校验（必须配 --waive-reason；"
                               "产生 backfill_binding_waived 审计事件，禁止静默旁路）")
    backfill.add_argument("--waive-reason", default="", dest="waive_reason",
                          help="豁免理由（非空必填于 --waive-binding，落审计事件与运行日志）")
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
    final_audit.add_argument("--workspace", default="",
                             help="工作区路径（--session 时可从工作流元数据反查）")
    final_audit.add_argument("--db", default="")
    final_audit.add_argument("--wf", default="", help="绑定指定工作流；缺省按工作区选择")
    final_audit.add_argument("--out", default="")
    final_audit.add_argument("--session", default="",
                             help="执行会话 ticket 路径：引擎取证的只读候选预审")
    final_audit.add_argument("--evidence-file", default="",
                             help="legacy：手工候选 evidence 文件；仅预审对账，不接受产物、不推进状态")

    # 操作审计（读取 plugin 的 operations.jsonl + SQLite + evidence）
    audit = sub.add_parser("audit")
    audit.add_argument("--workspace", required=True, help="工作区路径（含 .engine/evidence 与 workflow.sqlite）")
    audit.add_argument("--out", default="", help="操作审计输出路径（默认 workspace/OPERATION_AUDIT_REPORT.json）")
    audit.add_argument("--db", default="")

    return parser


def _run_command(args, parser) -> int:
    if args.command == "session":
        return args.session_handler(args)
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
        evidence_file = str(getattr(args, "evidence_file", "") or "").strip()
        results = []
        if gap_raw or evidence_file:
            if gap_raw:
                try:
                    gap = json.loads(gap_raw)
                except json.JSONDecodeError as exc:
                    raise WorkflowCliError(f"--gap JSON 无效: {exc}") from None
            else:
                gap = _read_json_input("", evidence_file, "--evidence-file")
            results.append(forge_from_gap(gap if isinstance(gap, dict) else {}, ROOT, force=force))
        tool_name = str(getattr(args, "tool", "") or "").strip()
        skill_name = str(getattr(args, "skill", "") or "").strip()
        if tool_name:
            results.append(forge_tool(tool_name, purpose, ROOT, force=force))
        if skill_name:
            linked = str(getattr(args, "linked_tool", "") or "").strip() or None
            results.append(forge_skill(skill_name, purpose, ROOT, tool_name=linked, force=force))
        if not results:
            print(json.dumps({
                "status": "error",
                "message": "forge 需要 --tool/--skill/--gap 之一",
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

    # 单入口会话（W5）：--session 从 ticket 读取真实身份，--wf/--db 不再是必要条件。
    ticket = None
    if args.command in {"complete", "preflight", "final-audit"} and getattr(args, "session", ""):
        ticket = _load_session_ticket(args.session)
        args.wf = str(ticket["workflow_id"])
        args.db = str(ticket["database"])
    elif args.command in {"complete", "preflight"} and not str(getattr(args, "wf", "") or "").strip():
        raise WorkflowCliError(f"{args.command} 需要 --session <ticket> 或 --wf <工作流 ID>")
    if args.command == "final-audit" and ticket is None \
            and not str(getattr(args, "workspace", "") or "").strip():
        raise WorkflowCliError("final-audit 需要 --workspace <工作区> 或 --session <ticket>")

    workspace_for_db = Path(args.workspace) if args.command in {"start", "audit", "final-audit"} else None
    if args.db:
        db = Path(args.db)
    elif workspace_for_db is not None and str(getattr(args, "workspace", "") or "").strip():
        db = default_workflow_db(workspace_for_db)
    elif args.command in {"next", "complete", "preflight", "retry", "report", "stall",
                          "backfill", "promote", "abandon"}:
        try:
            db = resolve_workflow_db(args.wf)
        except KeyError as exc:
            # B3-2：索引未命中时按位置约定回退探测（索引缺失/落后是常态而非异常）
            db = _probe_workflow_db(args.wf)
            if db is None:
                raise WorkflowCliError(_keyerror_message(exc)) from None
            if args.command != "preflight":
                register_workflow_database(args.wf, db)
    elif args.command == "approve":
        try:
            db = resolve_checkpoint_db(args.checkpoint)
        except KeyError as exc:
            raise WorkflowCliError(_keyerror_message(exc)) from None
    else:
        db = STATE_ROOT / "workflow.sqlite"
    if args.command != "preflight":
        db.parent.mkdir(parents=True, exist_ok=True)
    try:
        catalog = json.loads((ROOT / "engine" / "modex-core" / "templates.json").read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WorkflowCliError(f"templates.json 解析失败: {exc}") from None

    with WorkflowStore(db, read_only=args.command == "preflight") as store:
        runner = WorkflowRunner(store, catalog, ROOT / "skills",
                                audit_root=None if args.command == "preflight" else ROOT.parent)
        # Read-only preflight must not create logs or migrate the DB.
        if args.command != "preflight":
            _attach_run_logger(runner, store, args)

        if args.command == "start":
            try:
                params = json.loads(args.params)
            except json.JSONDecodeError as exc:
                raise WorkflowCliError(f"--params JSON 无效: {exc}") from None
            try:
                workflow = runner.start(args.template, Path(args.workspace), params,
                                        mode=str(getattr(args, "mode", "delivery") or "delivery"),
                                        candidate_id=str(getattr(args, "candidate", "") or ""))
            except KeyError as exc:
                raise WorkflowCliError(f"无法启动工作流: {_keyerror_message(exc)}") from None
            except ValueError as exc:
                raise WorkflowCliError(f"无法启动工作流: {exc}") from None
            register_workflow_database(workflow.id, db)
            _save_run_log(runner, workflow.id)
            result = json.dumps({
                "workflow_id": workflow.id,
                "status": workflow.status,
                "created_at": workflow.created_at,
                "execution_contract": workflow.metadata.get("execution_contract", {}),
                **({"delivery_candidate": workflow.metadata["delivery_candidate"]}
                   if isinstance(workflow.metadata.get("delivery_candidate"), dict) else {}),
            }, ensure_ascii=False, indent=2)
            print(result)
            return 0

        if args.command == "promote":
            try:
                candidate = runner.promote(args.wf, [root for root in args.root if root.strip()],
                                           by=str(args.by or "").strip(),
                                           template=str(getattr(args, "template", "") or ""))
            except (KeyError, ValueError, OSError) as exc:
                raise WorkflowCliError(f"promote 失败: {exc}") from None
            _save_run_log(runner, args.wf)
            payload = {
                "status": "ok",
                "candidate_id": getattr(candidate, "id", ""),
                "candidate_status": getattr(candidate, "status", ""),
                "source_workflow_id": getattr(candidate, "source_workflow_id", args.wf),
                "acceptance_sha256": getattr(candidate, "acceptance_sha256", ""),
                "roots": getattr(candidate, "roots", []),
                "missing": getattr(candidate, "missing", []),
            }
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0

        if args.command == "abandon":
            result = runner.abandon_workflow(args.wf, str(args.reason or "").strip(),
                                             str(args.by or "").strip())
            _save_run_log(runner, args.wf)
            print(json.dumps({"status": result.status, "message": result.message},
                             ensure_ascii=False, indent=2))
            return 0 if result.status == "abandoned" else 1

        if args.command == "next":
            result = runner.next_action(args.wf)
            _save_run_log(runner, args.wf)
            output = {
                "status": result.status,
                "message": result.message,
                "diagnostics": result.diagnostics,
            }
            if result.action:
                workflow = store.get_workflow(args.wf)
                contract = (workflow.metadata.get("execution_contract")
                            if isinstance(workflow.metadata.get("execution_contract"), dict) else {})
                output["action"] = _action_payload(
                    result.action, contract_tier=str(contract.get("tier") or "delivery"),
                    requires_collection=bool(workflow.metadata.get("delivery_candidate")))
                # 默认下发可执行上下文；不让Agent重复计算hash或手建证据。
                # channel 仅为投递账本归因（P0 只读埋点），不改变下发内容；
                # --resend（SKILL_LOST 求救）时投全文并按 resend 通道入账本。
                from execution.session import ExecutionSession
                from execution.presentation import user_view
                output["execution"] = user_view(ExecutionSession(
                    runner, args.wf, result.action).context(
                        channel="resend" if getattr(args, "resend", False) else "next"))
            if result.checkpoint_id:
                # A5 ⑦ 修复：blocked 时直接给出待批 checkpoint UUID
                output["checkpoint_id"] = result.checkpoint_id
            print(json.dumps(output, ensure_ascii=False, indent=2))
            return 0 if result.status in ("advanced", "completed") else 1

        if args.command in {"complete", "preflight"}:
            if ticket is not None:
                identity = _session_identity(ticket)
                if args.command == "preflight":
                    # 只读取证验收：collect_execution_evidence + _validate_step，不落库不推进
                    report = runner.validate_recorded_step(*identity)
                    print(json.dumps(report, ensure_ascii=False, indent=2))
                    return 0 if report["ok"] else 1
                result = runner.complete_recorded_step(*identity)
                _save_run_log(runner, args.wf)
                output = {
                    "status": result.status,
                    "step_id": result.step_id,
                    "message": result.message,
                }
                output["diagnostics"] = result.diagnostics
                output["replayed"] = result.replayed
                if result.checkpoint_id:
                    output["checkpoint_id"] = result.checkpoint_id
                print(json.dumps(output, ensure_ascii=False, indent=2))
                return 0 if result.status in ("advanced", "completed", "waiting_checkpoint") else 1
            evidence = _read_json_input(args.evidence, str(getattr(args, "evidence_file", "") or ""),
                                        "--evidence-file")
            if not isinstance(evidence, dict):
                raise WorkflowCliError("execution evidence 必须是 JSON 对象")
            _reject_handbuilt_final_evidence(store, str(getattr(args, "step_id", "") or ""), evidence)
            step_result = StepResult(
                ok=str(getattr(args, "ok", "true")).lower() == "true",
                artifacts=[a.strip() for a in args.artifacts.split(",") if a.strip()],
                stderr=getattr(args, "stderr", ""),
                metadata={"execution_evidence": evidence},
                step_id=getattr(args, "step_id", ""), attempt_id=getattr(args, "attempt_id", ""),
                expected_revision=getattr(args, "expected_revision", None), request_id=getattr(args, "request_id", ""),
            )
            if args.command == "preflight":
                report = runner.validate_step(args.wf, step_result)
                print(json.dumps(report, ensure_ascii=False, indent=2))
                return 0 if report["ok"] else 1
            result = runner.complete_step(args.wf, step_result)
            _save_run_log(runner, args.wf)
            output = {
                "status": result.status,
                "step_id": result.step_id,
                "message": result.message,
            }
            output["diagnostics"] = result.diagnostics
            output["replayed"] = result.replayed
            if result.checkpoint_id:
                # A5 ⑦ 修复：waiting_checkpoint 时直接给出待批 checkpoint UUID
                output["checkpoint_id"] = result.checkpoint_id
            print(json.dumps(output, ensure_ascii=False, indent=2))
            return 0 if result.status in ("advanced", "completed", "waiting_checkpoint") else 1

        if args.command == "retry":
            result = runner.retry_last_failed(
                args.wf, by=str(args.by or "").strip(),
                override_reason=str(getattr(args, "override_reason", "") or "").strip())
            _save_run_log(runner, args.wf)
            output = {
                "status": result.status,
                "step_id": result.step_id,
                "message": result.message,
                "diagnostics": result.diagnostics,
            }
            if result.action:
                workflow = store.get_workflow(args.wf)
                contract = (workflow.metadata.get("execution_contract")
                            if isinstance(workflow.metadata.get("execution_contract"), dict) else {})
                output["action"] = _action_payload(
                    result.action, contract_tier=str(contract.get("tier") or "delivery"),
                    requires_collection=bool(workflow.metadata.get("delivery_candidate")))
            print(json.dumps(output, ensure_ascii=False, indent=2))
            return 0 if result.status in ("advanced", "completed") else 1

        if args.command == "stall":
            report = runner.detect_stalled(args.wf, stall_hours=float(args.hours))
            _save_run_log(runner, args.wf)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            # 告警即非零退出，便于脚本/钩子感知断链
            return 1 if report["alert"] else 0

        if args.command == "backfill":
            backfill_evidence = None
            if args.evidence_file:
                backfill_evidence = _read_json_input(args.evidence, args.evidence_file, "--evidence-file")
                if not isinstance(backfill_evidence, dict):
                    raise WorkflowCliError("execution evidence 必须是 JSON 对象")
            elif str(getattr(args, "evidence", "") or "").strip():
                try:
                    backfill_evidence = json.loads(args.evidence)
                except json.JSONDecodeError as exc:
                    print(json.dumps({
                        "status": "failed",
                        "message": f"--evidence 不是合法 JSON：{exc}",
                    }, ensure_ascii=False, indent=2))
                    return 1
            result = runner.backfill_step(
                args.wf, str(args.step).strip(),
                artifacts=[a.strip() for a in args.artifact if a.strip()],
                commands=[c for c in args.backfill_commands if c.strip()],
                note=str(args.note or ""), by=str(args.by or "").strip(),
                evidence=backfill_evidence,
                waive_binding=bool(getattr(args, "waive_binding", False)),
                waive_reason=str(getattr(args, "waive_reason", "") or ""))
            _save_run_log(runner, args.wf)
            output = {
                "status": result.status,
                "step_id": result.step_id,
                "message": result.message,
                "diagnostics": result.diagnostics,
                "checkpoint_id": result.checkpoint_id,
            }
            print(json.dumps(output, ensure_ascii=False, indent=2))
            return 0 if result.status in ("advanced", "completed", "waiting_checkpoint") else 1

        if args.command == "approve":
            by = str(getattr(args, "by", "") or "").strip()
            if not by:
                # 用法错误走 argparse 教学式报错（stderr + exit 2），既有测试
                # test_workflow_retry_cli 锁定该契约；JSON 错误契约保留给业务执行异常
                parser.error(
                    "approve 缺少必填的 --by <批准人标识>：批准事件必须记录谁批准了检查点"
                    "（防 agent 自批准且无痕）。正确用法: "
                    "python -m engine.workflow_cli approve --checkpoint <UUID> "
                    "[--db <workflow.sqlite 路径>] --by <批准人>"
                )
            result = runner._approve_checkpoint(args.checkpoint, {"approved": True, "approved_by": by})
            _save_run_log(runner, _checkpoint_workflow_id(store, args.checkpoint))
            output = {"status": result.status, "message": result.message}
            if result.action:
                owner = _checkpoint_workflow_id(store, args.checkpoint) or result.workflow_id
                workflow = store.get_workflow(owner)
                contract = (workflow.metadata.get("execution_contract")
                            if isinstance(workflow.metadata.get("execution_contract"), dict) else {})
                output["action"] = _action_payload(
                    result.action, contract_tier=str(contract.get("tier") or "delivery"),
                    requires_collection=bool(workflow.metadata.get("delivery_candidate")))
            print(json.dumps(output, ensure_ascii=False, indent=2))
            return 0 if result.status in ("advanced", "completed") else 1

        if args.command == "report":
            # B3-2：读侧命令顺带清理指向已消失数据库的孤儿注册
            pruned = prune_workflow_index()
            if pruned:
                print(f"[workflow-index] 已清理孤儿注册: {', '.join(pruned)}")
            report = store.workflow_timeline(args.wf)
            Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"报告已保存: {args.out}")
            return 0

        if args.command == "final-audit":
            from ..audit.audit_store import write_explore_report, write_final_audit_report
            workspace = Path(args.workspace) if str(getattr(args, "workspace", "") or "").strip() else None
            if workspace is None:
                workspace = _workflow_workspace(store, args.wf)
                if workspace is None:
                    raise WorkflowCliError("无法从工作流元数据反查工作区；请显式提供 --workspace")
            out = Path(args.out) if args.out else None
            tier = "delivery"
            audit_workflow_id = str(args.wf or "")
            if not audit_workflow_id:
                # --workspace 模式：取该工作区最新工作流的档位（与
                # write_final_audit_report 的“最新工作流”选择口径一致）。
                rows = store._connection.execute(
                    "SELECT id, metadata FROM workflows ORDER BY created_at DESC, rowid DESC").fetchall()
                for row in rows:
                    meta = json.loads(row["metadata"])
                    if Path(meta.get("workspace", "")).resolve() == workspace.resolve():
                        audit_workflow_id = row["id"]
                        break
            if audit_workflow_id:
                audit_workflow = store.get_workflow(audit_workflow_id)
                contract = (audit_workflow.metadata.get("execution_contract")
                            if isinstance(audit_workflow.metadata.get("execution_contract"), dict) else {})
                tier = str(contract.get("tier") or "delivery")
            if tier == "explore":
                if ticket is not None or args.evidence_file:
                    raise WorkflowCliError("explore 工作流不接受交付候选预审；只生成 EXPLORE_REPORT.json")
                target = write_explore_report(workspace, ROOT.parent, workflow_db=db,
                                              workflow_id=args.wf or None)
                print(f"探索报告已保存: {target}（explore_only）")
                return 1
            candidate = None
            if ticket is not None:
                # 引擎取证的只读候选预审：证据来自真实执行集合，不写库、不推进
                try:
                    candidate = runner.recorded_final_candidate(*_session_identity(ticket))
                except (ValueError, KeyError) as exc:
                    raise WorkflowCliError(f"候选预审证据无效: {exc}") from None
            elif args.evidence_file:
                if not args.wf:
                    raise WorkflowCliError("候选预审必须通过 --wf 指定工作流")
                evidence = _read_json_input("", args.evidence_file, "--evidence-file")
                if not isinstance(evidence, dict):
                    raise WorkflowCliError("execution evidence 必须是 JSON 对象")
                try:
                    candidate = runner.final_audit_candidate(args.wf, evidence)
                except ValueError as exc:
                    raise WorkflowCliError(f"候选预审证据无效: {exc}") from None
            target = write_final_audit_report(workspace, ROOT.parent, out, workflow_db=db,
                                             workflow_id=args.wf or None, candidate=candidate)
            decision = json.loads(target.read_text(encoding="utf-8"))["delivery_decision"]
            print(f"最终审计报告已保存: {target}（{decision}）")
            return 0 if decision in {"eligible", "ready"} else 1

        if args.command == "audit":
            from ..audit.audit_store import write_audit_report
            # B3-2：审计前清理孤儿注册（指向已消失数据库的条目）
            pruned = prune_workflow_index()
            if pruned:
                print(f"[workflow-index] 已清理孤儿注册: {', '.join(pruned)}")
            workspace = Path(args.workspace)
            out = Path(args.out) if args.out else workspace / "OPERATION_AUDIT_REPORT.json"
            target = write_audit_report(workspace, ROOT.parent, out, workflow_db=db)
            print(f"审计报告已保存: {target}")
            return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
