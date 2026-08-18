"""Agent-in-the-loop 工作流编排器。

引擎不执行，只编排：
  - next_action() → 告诉 agent 下一步做什么
  - complete_step() → agent 做完后回报结果
  - approve_checkpoint() → 用户确认后继续

Agent（当前 OpenCode 桌面版 agent）按 StepAction 执行，然后调用 complete_step()。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .opencode_bridge import StepAction, StepResult
from .artifact_manifest import ArtifactManifest
from .execution_protocol import validate_execution_evidence, write_execution_evidence
from .quality_gates import QualityGate
from .run_logger import RunLogger
from .template_resolver import resolve_template
from .workflow_store import StepStatus, Workflow, WorkflowStore


@dataclass(frozen=True)
class RunResult:
    """引擎返回给 agent 的响应。"""
    workflow_id: str
    status: str  # completed | failed | waiting_checkpoint | advanced | blocked
    step_id: str | None = None
    message: str = ""
    action: StepAction | None = None


class WorkflowRunner:
    def __init__(self, store: WorkflowStore, catalog: dict[str, Any], skills_root: Path,
                 logger: RunLogger | None = None, audit_root: Path | None = None):
        self.store = store
        self.catalog = catalog
        self.skills_root = Path(skills_root)
        self.logger = logger
        # 操作审计（共享根 .engine/audit，与 plugin 同库）——引擎侧主动记录，
        # 与 plugin 拦截式记录互补：plugin 记"实际调用"，引擎记"编排决策"。
        self._audit = None
        if audit_root is not None:
            try:
                from .audit_store import AuditStore
                self._audit = AuditStore(audit_root)
            except Exception:
                self._audit = None

    start_params: dict[str, Any] = {}

    def _audit_record(self, **entry) -> None:
        """写入引擎侧审计事件（失败不阻断主流程）。"""
        if self._audit is not None:
            try:
                self._audit.record(entry)
            except Exception:
                pass

    def start(self, template: str, workspace: Path, params: dict[str, Any]) -> Workflow:
        """创建持久化工作流；调用 next_action() 获取第一个 StepAction。"""
        self.start_params = params
        steps = resolve_template(template, params, self.catalog)
        workspace = Path(workspace).resolve()
        workspace.mkdir(parents=True, exist_ok=True)
        workflow = self.store.create_workflow(template, {
            "workspace": str(workspace),
            "params": params,
            "template": template,
        })
        # 默认在工作区 .engine/logs 下建立运行日志（审计闭环）
        if self.logger is None:
            self.logger = RunLogger(workspace / ".engine" / "logs")
        self._log(workflow.id, None, None, "started",
                  f"工作流 {template} 启动（{len(steps)} 步）", agent=params.get("agent", ""))
        self._audit_record(type="engine_event", event="workflow_started", workflow_id=workflow.id,
                           template=template, workspace=str(workspace), step_count=len(steps),
                           agent=params.get("agent", ""))
        step_specs = []
        for s in steps:
            meta = dict(s)
            meta["primary_output"] = s.get("primary_output")
            meta["output_files"] = s.get("output_files", [])
            meta["has_checkpoint"] = s.get("has_checkpoint", False)
            meta["checkpoint_type"] = s.get("checkpoint_type")
            meta["display_name"] = s.get("display_name", s["skill_name"])
            step_specs.append({"name": s["skill_name"], "metadata": meta})
        self.store.add_steps(workflow.id, step_specs)
        return workflow

    def next_action(self, workflow_id: str) -> RunResult:
        """返回下一个要执行的 StepAction，或告知工作流已完成/失败。"""
        running = self._last_running_step(workflow_id)
        if running is not None:
            workflow = self._workflow(workflow_id)
            return RunResult(
                workflow_id, "advanced", running.id,
                message=f"步骤 {running.name} 正在执行，重发当前动作",
                action=self._action_for_step(workflow, running),
            )

        # ⛔ 任何步骤失败后立即阻断：不允许带着失败步骤继续推进后续步骤
        failed = self._has_failed_steps(workflow_id)
        if failed:
            return RunResult(workflow_id, "failed", message=f"步骤 {failed} 已失败，先修复再继续")

        step = self._next_pending_step(workflow_id)
        if step is None:
            # 检查是否有失败的步骤
            failed = self._has_failed_steps(workflow_id)
            if failed:
                return RunResult(workflow_id, "failed", message=f"步骤 {failed} 已失败")
            return RunResult(workflow_id, "completed", message="所有步骤已完成")

        workflow = self._workflow(workflow_id)
        workspace = Path(workflow.metadata["workspace"])
        skill_path = self.skills_root / step.name / "SKILL.md"

        self.store.transition_step(step.id, StepStatus.RUNNING)
        self._log(workflow_id, step.id, step.name, "started",
                  f"开始执行 {step.name}", agent=self._agent_label(workflow))

        action = StepAction(
            workflow_id=workflow_id,
            step_id=step.id,
            position=step.position,
            skill_name=step.name,
            display_name=step.metadata.get("display_name", step.name),
            workspace=workspace,
            skill_path=skill_path,
            output_files=step.metadata.get("output_files", []),
            primary_output=step.metadata.get("primary_output", ""),
            has_checkpoint=step.metadata.get("has_checkpoint", False),
            checkpoint_type=step.metadata.get("checkpoint_type"),
            params=workflow.metadata.get("params", {}),
        )
        return RunResult(workflow_id, "advanced", step.id, action=action)

    def complete_step(self, workflow_id: str, result: StepResult) -> RunResult:
        """agent 执行完一个步骤后调用此方法回报结果。"""
        workflow = self._workflow(workflow_id)
        # 从 RUNNING 状态中找最新的步骤
        step = self._last_running_step(workflow_id)
        if step is None:
            return RunResult(workflow_id, "failed", message="没有正在执行的步骤")

        if not result.ok:
            self.store.transition_step_with_checkpoint(
                workflow_id, step.id, StepStatus.FAILED,
                {"status": "failed", "error": result.stderr},
                artifacts=[{"name": a, "path": a} for a in result.artifacts],
                event={"type": "step_failed", "stderr": result.stderr},
            )
            self._log(workflow_id, step.id, step.name, "failed",
                      f"步骤 {step.name} 失败: {result.stderr[:200]}", agent=self._agent_label(workflow))
            return RunResult(workflow_id, "failed", step.id, result.stderr)

        # 检查执行证据：技能必须有产出文件作为执行证据
        declared_outputs = step.metadata.get("output_files", [])
        has_evidence = bool(result.artifacts) or bool(declared_outputs and any(
            (Path(workflow.metadata["workspace"]) / o).exists()
            for o in declared_outputs
        ))
        if not has_evidence:
            self.store.transition_step_with_checkpoint(
                workflow_id, step.id, StepStatus.FAILED,
                {"status": "failed", "error": "no execution evidence"},
                event={"type": "step_failed", "stderr": "no execution evidence: agent claimed success but produced no artifacts"},
            )
            return RunResult(workflow_id, "failed", step.id,
                             "no execution evidence: agent claimed success but produced no artifacts")

        try:
            evidence = validate_execution_evidence(workflow.metadata["workspace"], self._action_for_step(workflow, step), result)
        except ValueError as exc:
            message = f"invalid execution evidence: {exc}"
            self.store.transition_step_with_checkpoint(
                workflow_id, step.id, StepStatus.FAILED,
                {"status": "failed", "error": message},
                artifacts=[{"name": a, "path": a} for a in result.artifacts],
                event={"type": "step_failed", "stderr": message},
            )
            return RunResult(workflow_id, "failed", step.id, message)

        # ⛔ M5: 审核独立视角强制（防伪造审核——LESSONS 教训 1）
        # 模板步骤标记 requires_subagent=true（审核类：comp-review/comp-visual-review/comp-final-review 等）
        # 时，执行证据必须包含真实只读子智能体会话 ID（subagent_session）。
        # 主 Agent 不得直接提交手写审核产物冒充独立审查。
        # ⛔ P1: 审核步骤的 commands 必须含真实工具调用（tools/ 下脚本），
        # 防 "echo done" 伪命令冒充实际执行。
        if step.metadata.get("requires_subagent"):
            subagent_session = str(result.metadata.get("execution_evidence", {}).get("subagent_session", "")).strip()
            if not subagent_session:
                message = ("invalid execution evidence: 该步骤要求由只读子智能体执行（requires_subagent），"
                           "执行证据缺少 subagent_session（真实子智能体会话 ID）。主 Agent 不得直接提交审核产物。")
                self.store.transition_step_with_checkpoint(
                    workflow_id, step.id, StepStatus.FAILED,
                    {"status": "failed", "error": message},
                    artifacts=[{"name": a, "path": a} for a in result.artifacts],
                    event={"type": "step_failed", "stderr": message},
                )
                return RunResult(workflow_id, "failed", step.id, message)
            # P1: commands 必须含真实工具调用（tools/ 或 skills/_utils 下脚本）
            commands = result.metadata.get("execution_evidence", {}).get("commands", [])
            has_tool_call = any(
                isinstance(c, dict) and ("tools/" in str(c.get("command", "")) or "_utils/" in str(c.get("command", "")))
                for c in commands
            )
            if not has_tool_call:
                message = ("invalid execution evidence: 审核步骤（requires_subagent）的 commands 必须包含"
                           "真实工具调用（tools/ 或 skills/_utils 下脚本），禁止用 echo 等伪命令冒充实际执行。")
                self.store.transition_step_with_checkpoint(
                    workflow_id, step.id, StepStatus.FAILED,
                    {"status": "failed", "error": message},
                    artifacts=[{"name": a, "path": a} for a in result.artifacts],
                    event={"type": "step_failed", "stderr": message},
                )
                return RunResult(workflow_id, "failed", step.id, message)

        workspace = Path(workflow.metadata["workspace"])
        declared_outputs = list(step.metadata.get("output_files", []))
        claimed = set(result.artifacts)
        undeclared = sorted(claimed - set(declared_outputs))
        manifest = ArtifactManifest.validate(workspace, declared_outputs)
        if undeclared or not manifest["ok"]:
            details = []
            if undeclared:
                details.append(f"undeclared artifacts: {', '.join(undeclared)}")
            if manifest["missing"]:
                details.append(f"missing declared outputs: {', '.join(manifest['missing'])}")
            if manifest["invalid"]:
                details.append(f"invalid declared outputs: {', '.join(manifest['invalid'])}")
            message = "declared outputs validation failed: " + "; ".join(details)
            self.store.transition_step_with_checkpoint(
                workflow_id, step.id, StepStatus.FAILED,
                {"status": "failed", "error": message, "manifest": _manifest_payload(manifest)},
                event={"type": "step_failed", "stderr": message},
            )
            return RunResult(workflow_id, "failed", step.id, message)

        action = self._action_for_step(workflow, step)
        evidence_path = write_execution_evidence(workspace, action, evidence, _manifest_payload(manifest))
        self._audit_record(type="engine_event", event="step_completed", workflow_id=workflow_id,
                           step_id=step.id, skill_name=step.name, evidence_path=evidence_path,
                           agent=self._agent_label(workflow),
                           declared_commands=[c.get("command", "") for c in evidence.get("commands", [])])

        gate_result = QualityGate(workspace).run_all(
            step.name,
            declared_outputs=declared_outputs,
            comp_name=workflow.name if step.name in {"comp-compile-zh", "comp-compile-en"} else "",
            requires_figures=step.name.startswith("paper-figure"),
            required_checks=step.metadata.get("required_checks"),
            primary_output=step.metadata.get("primary_output"),
        )
        if not gate_result["ok"]:
            message = "quality gates failed"
            self.store.transition_step_with_checkpoint(
                workflow_id, step.id, StepStatus.FAILED,
                {"status": "failed", "error": message, "quality_gates": gate_result},
                event={"type": "step_failed", "stderr": message, "quality_gates": gate_result},
            )
            self._log(workflow_id, step.id, step.name, "failed",
                      f"步骤 {step.name} 质量门禁失败", agent=self._agent_label(workflow))
            return RunResult(workflow_id, "failed", step.id, message)

        # 检查是否需要检查点
        has_checkpoint = step.metadata.get("has_checkpoint", False)
        if has_checkpoint:
            checkpoint_type = step.metadata.get("checkpoint_type", "approve")
            self.store.transition_step_with_checkpoint(
                workflow_id, step.id, StepStatus.BLOCKED,
                {"status": "waiting_checkpoint", "type": checkpoint_type},
                artifacts=_manifest_artifacts(manifest),
                event={"type": "step_completed", "evidence_path": evidence_path, "manifest": _manifest_payload(manifest), "quality_gates": gate_result},
            )
            self._log(workflow_id, step.id, step.name, "checkpoint",
                      f"步骤 {step.name} 完成，等待用户确认", agent=self._agent_label(workflow))
            # 返回下一个动作（如果有），但标记为 waiting_checkpoint
            next_action = self._next_pending_step(workflow_id)
            if next_action:
                return RunResult(workflow_id, "waiting_checkpoint", step.id,
                                 message=f"步骤 {step.name} 完成，等待用户确认")
            return RunResult(workflow_id, "waiting_checkpoint", step.id,
                             message="所有步骤完成，等待最后检查点确认")

        self.store.transition_step_with_checkpoint(
            workflow_id, step.id, StepStatus.COMPLETED,
            {"status": "completed", "evidence_path": evidence_path, "manifest": _manifest_payload(manifest), "quality_gates": gate_result},
            artifacts=_manifest_artifacts(manifest),
            event={"type": "step_completed", "evidence_path": evidence_path, "manifest": _manifest_payload(manifest), "quality_gates": gate_result},
        )
        self._log(workflow_id, step.id, step.name, "completed",
                  f"步骤 {step.name} 完成，证据: {evidence_path}", agent=self._agent_label(workflow),
                  evidence_path=evidence_path)
        # 每步完成后即时落盘日志（固定文件名覆盖），中断/崩溃也不丢审计链
        if self.logger is not None:
            try:
                self.logger.save(workflow_id, f"run_{workflow_id}.json")
            except Exception:
                pass

        # 检查是否还有下一步
        next_step = self._next_pending_step(workflow_id)
        if next_step is None:
            self.store.complete_workflow(workflow_id)
            self._log(workflow_id, None, None, "completed", "所有步骤完成", agent=self._agent_label(workflow))
            return RunResult(workflow_id, "completed", step.id, "所有步骤完成")

        return RunResult(workflow_id, "advanced", step.id,
                         message=f"步骤 {step.name} 完成，继续下一步")

    def approve_checkpoint(self, checkpoint_id: str, response: dict[str, Any]) -> RunResult:
        """用户批准检查点后继续工作流。"""
        candidates = [c for c in self.store.resume_candidates() if c.checkpoint.id == checkpoint_id]
        if not candidates:
            raise KeyError(f"unknown checkpoint: {checkpoint_id}")
        candidate = candidates[0]

        if response.get("approved") is not True:
            return RunResult(candidate.workflow_id, "blocked", candidate.step_id,
                             "检查点未批准")

        # M3 FIX: 批准记录 + 步骤完成合并为一次原子事务（transition_step_with_checkpoint），
        # 避免两次独立 transition_step 中途失败导致状态不一致（BLOCKED→RUNNING→COMPLETED 非原子）。
        # approve 检查点会附带一次 checkpoint_approved 事件，步骤直接原子转为 COMPLETED。
        step, _ = self.store.transition_step_with_checkpoint(
            candidate.workflow_id, candidate.step_id, StepStatus.COMPLETED,
            {"status": "approved", "response": response},
            event={"type": "checkpoint_approved", "approved_by": response.get("approved_by", "")},
        )
        self._log(candidate.workflow_id, candidate.step_id, step.name, "checkpoint",
                  "用户批准检查点", agent=response.get("approved_by", ""))
        self._audit_record(type="engine_event", event="checkpoint_approved", workflow_id=candidate.workflow_id,
                           step_id=candidate.step_id, approved_by=response.get("approved_by", ""))

        # 返回下一个动作，并在工作流完成时落盘
        next_step = self._next_pending_step(candidate.workflow_id)
        if next_step is None:
            self.store.complete_workflow(candidate.workflow_id)
            return RunResult(candidate.workflow_id, "completed", candidate.step_id,
                             "所有步骤完成")

        # F1 FIX: 即使还有后续步骤，也检查是否所有步骤实际上已完成（无 pending 步骤）
        # 如果没有 pending 步骤，标记工作流完成；否则继续下一步
        all_pending = self._has_pending_steps(candidate.workflow_id)
        if not all_pending:
            self.store.complete_workflow(candidate.workflow_id)
            return RunResult(candidate.workflow_id, "completed", candidate.step_id,
                             "所有步骤完成")

        return self.next_action(candidate.workflow_id)

    def _has_pending_steps(self, workflow_id: str) -> bool:
        """检查工作流是否还有待执行的 pending 步骤。"""
        row = self.store._connection.execute(
            "SELECT COUNT(*) FROM workflow_steps WHERE workflow_id = ? AND status = 'pending'",
            (workflow_id,),
        ).fetchone()
        return row[0] > 0 if row else False

    def _workflow(self, workflow_id: str) -> Workflow:
        row = self.store._connection.execute(
            "SELECT * FROM workflows WHERE id = ?", (workflow_id,)
        ).fetchone()
        if row is None:
            raise KeyError(workflow_id)
        return Workflow(
            row["id"], row["name"], row["status"],
            json.loads(row["metadata"]), row["created_at"], row["updated_at"],
        )

    def _agent_label(self, workflow: Workflow) -> str:
        """返回当前步骤的执行 agent 标签（默认 OpenCode Desktop 数模专家）。"""
        params = workflow.metadata.get("params", {})
        return str(params.get("agent", "") or "OpenCode Desktop 数模专家")

    def _log(self, workflow_id: str, step_id: str | None, step_name: str | None,
             event: str, message: str = "", **metadata) -> None:
        """写入运行日志；日志器未创建时静默跳过（不阻断主流程）。"""
        if self.logger is not None:
            try:
                self.logger.log(workflow_id, step_id, step_name, event, message, **metadata)
            except Exception:
                pass

    def _next_pending_step(self, workflow_id: str):
        row = self.store._connection.execute(
            "SELECT * FROM workflow_steps WHERE workflow_id = ? AND status = 'pending' ORDER BY position LIMIT 1",
            (workflow_id,),
        ).fetchone()
        if row is None:
            return None
        return self.store._step_from_row(row)

    def _last_running_step(self, workflow_id: str):
        row = self.store._connection.execute(
            "SELECT * FROM workflow_steps WHERE workflow_id = ? AND status = 'running' ORDER BY updated_at DESC LIMIT 1",
            (workflow_id,),
        ).fetchone()
        if row is None:
            return None
        return self.store._step_from_row(row)

    def _has_failed_steps(self, workflow_id: str) -> str | None:
        row = self.store._connection.execute(
            "SELECT name FROM workflow_steps WHERE workflow_id = ? AND status = 'failed' ORDER BY position LIMIT 1",
            (workflow_id,),
        ).fetchone()
        return row[0] if row else None

    def _action_for_step(self, workflow: Workflow, step: Any) -> StepAction:
        return StepAction(
            workflow_id=workflow.id, step_id=step.id, position=step.position, skill_name=step.name,
            display_name=step.metadata.get("display_name", step.name),
            workspace=Path(workflow.metadata["workspace"]), skill_path=self.skills_root / step.name / "SKILL.md",
            output_files=step.metadata.get("output_files", []), primary_output=step.metadata.get("primary_output", ""),
            has_checkpoint=step.metadata.get("has_checkpoint", False), checkpoint_type=step.metadata.get("checkpoint_type"),
            params=workflow.metadata.get("params", {}),
        )


def _manifest_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    """Convert artifact dataclasses into JSON-safe audit payloads."""
    return {
        **manifest,
        "artifacts": [
            {
                "path": artifact.path,
                "size": artifact.size,
                "sha256": artifact.sha256,
                "exists": artifact.exists,
                "mime_type": artifact.mime_type,
            }
            for artifact in manifest["artifacts"]
        ],
    }


def _manifest_artifacts(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"name": Path(artifact.path).name, "path": artifact.path,
         "metadata": {"sha256": artifact.sha256, "size": artifact.size, "mime_type": artifact.mime_type}}
        for artifact in manifest["artifacts"]
    ]
