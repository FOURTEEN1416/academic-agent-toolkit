"""Agent-in-the-loop 工作流编排器。

引擎不执行，只编排：
  - next_action() → 告诉 agent 下一步做什么
  - complete_step() → agent 做完后回报结果
  - approve_checkpoint() → 用户确认后继续

Agent（当前驱动本项目的 Agent）按 StepAction 执行，然后调用 complete_step()。
"""
from __future__ import annotations

import json
import hashlib
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .agent_bridge import StepAction, StepResult
from .artifact_manifest import ArtifactManifest, FingerprintSession
from .execution_protocol import validate_execution_evidence, write_execution_evidence
from .quality_gates import QualityGate, _agent_self_reference_hit
from .run_logger import RunLogger
from .template_resolver import resolve_template
from .workflow_store import StepStatus, Workflow, WorkflowStore
from .step_manifest import atomic_write_json, build_manifest, get_step_manifest


def _norm_skill_token(name: str) -> str:
    """技能名归一化口径（与 used 痕迹校验一致）：去首尾空白、小写、'-' 与 '_' 等价。"""
    return str(name).strip().lower().replace("-", "_")


@dataclass(frozen=True)
class RunResult:
    """引擎返回给 agent 的响应。"""
    workflow_id: str
    status: str  # completed | failed | waiting_checkpoint | advanced | blocked
    step_id: str | None = None
    message: str = ""
    action: StepAction | None = None
    # A5 ⑦ 修复：checkpoint UUID 直接随结果输出（此前只能从 report JSON/SQLite 捞）
    checkpoint_id: str | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)
    replayed: bool = False


class WorkflowRunner:
    def __init__(self, store: WorkflowStore, catalog: dict[str, Any], skills_root: Path,
                 logger: RunLogger | None = None, audit_root: Path | None = None):
        self.store = store
        self.catalog = catalog
        self.skills_root = Path(skills_root)
        self.audit_root = Path(audit_root) if audit_root is not None else self.skills_root.parent.parent
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
        """创建持久化工作流；调用 next_action() 获取第一个 StepAction。

        B-02：启动即把有效赛事档案冻结进 metadata（contest_profile_snapshot），
        此后全部消费者读同一份快照；显式声明错误（身份冲突/未知ID/届次无匹配）
        在此直接失败，不创建带错误身份的工作流。
        """
        self.start_params = params
        steps = resolve_template(template, params, self.catalog)
        workspace = Path(workspace).resolve()
        workspace.mkdir(parents=True, exist_ok=True)
        metadata: dict[str, Any] = {
            "workspace": str(workspace),
            "params": params,
            "template": template,
        }
        from .contest_profile import resolve_profile
        profile = resolve_profile(template, params)  # 显式错误直接抛，不静默
        if profile is not None:
            metadata["contest_profile_snapshot"] = profile.to_snapshot()
        workflow = self.store.create_workflow(template, metadata)
        if profile is not None:
            # C→B 接口（B-CLOSE-01，2026-09-27）：bound 快照的机械字段由程序注入
            # 执行环境（.engine/contest_env），LLM 不转录；pending_binding 与非赛事
            # 工作流不注入（无 bound 快照即无口径可注）。
            self._write_contest_env(workspace, profile)
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
            workflow = self.store.get_workflow(workflow_id)
            return RunResult(
                workflow_id, "advanced", running.id,
                message=f"步骤 {running.name} 正在执行，重发当前动作",
                action=self._action_for_step(workflow, running),
            )

        # ⛔ 任何步骤失败后立即阻断：不允许带着失败步骤继续推进后续步骤
        failed = self._has_failed_steps(workflow_id)
        if failed:
            return RunResult(workflow_id, "failed", message=f"步骤 {failed} 已失败，先修复再继续")

        # ⛔ checkpoint 硬闸：存在 blocked 步骤 = 等待用户 approve，禁止 next 越过
        #（2026-09-09 独立审计 P1-2：此前 next 可在未 approve 时启动下一步，检查点形同虚设）
        blocked = self._first_blocked_step(workflow_id)
        if blocked is not None:
            return RunResult(
                workflow_id, "blocked", blocked.id,
                message=(f"步骤 {blocked.name} 的检查点等待用户批准"
                         f"（workflow_cli approve --checkpoint <UUID> --by <批准人>），不得跳过"),
                checkpoint_id=self._latest_checkpoint_id(blocked.id),
            )

        step = self._next_pending_step(workflow_id)
        if step is None:
            # 检查是否有失败的步骤
            failed = self._has_failed_steps(workflow_id)
            if failed:
                return RunResult(workflow_id, "failed", message=f"步骤 {failed} 已失败")
            delivery = self._refresh_delivery(workflow_id)
            return RunResult(workflow_id, "completed", message="所有步骤已完成",
                             diagnostics={"delivery": delivery} if delivery else {})

        workflow = self.store.get_workflow(workflow_id)
        step = self.store.transition_step(step.id, StepStatus.RUNNING)
        self._log(workflow_id, step.id, step.name, "started",
                  f"开始执行 {step.name}", agent=self._agent_label(workflow))
        return RunResult(workflow_id, "advanced", step.id,
                         action=self._action_for_step(workflow, step))

    def _result_target(self, workflow_id: str, result: StepResult):
        raw = result.metadata.get("execution_evidence", {})
        raw = raw if isinstance(raw, dict) else {}
        target = result.step_id or raw.get("step_id")
        if not target:
            raise ValueError("execution evidence/step_id required; refusing to guess the active step")
        step = self.store.get_step(str(target))
        if step.workflow_id != workflow_id or step.status != StepStatus.RUNNING:
            raise ValueError("stale completion: target is not a RUNNING step in this workflow")
        attempt = result.attempt_id or raw.get("attempt_id")
        revision = result.expected_revision if result.expected_revision is not None else raw.get("expected_revision")
        if attempt and attempt != step.attempt_id:
            raise ValueError("stale completion attempt_id")
        if revision is not None and revision != step.revision:
            raise ValueError("stale completion expected_revision")
        # Legacy v1 reports remain usable on a first attempt, but cannot identify a retry.
        if step.revision > 1 and (not attempt or revision is None):
            raise ValueError("retry completion requires attempt_id and expected_revision from next/retry")
        if raw.get("step_id") and raw["step_id"] != step.id:
            raise ValueError("conflicting step_id in execution evidence")
        if raw.get("attempt_id") and raw["attempt_id"] != step.attempt_id:
            raise ValueError("conflicting attempt_id in execution evidence")
        if raw.get("expected_revision") is not None and raw["expected_revision"] != step.revision:
            raise ValueError("conflicting expected_revision in execution evidence")
        return step

    def validate_step(self, workflow_id: str, result: StepResult) -> dict[str, Any]:
        """Write-free preflight. Report every independent failure, without advancing state."""
        workflow = self.store.get_workflow(workflow_id)
        try:
            step = self._result_target(workflow_id, result)
        except (ValueError, KeyError) as exc:
            return {"ok": False, "checks": {"target": {"ok": False, "reason": str(exc)}}}
        return self._validate_step(workflow, step, result, FingerprintSession(Path(workflow.metadata["workspace"])))[0]

    @staticmethod
    def _final_candidate(action, evidence):
        return {"action": {"workflow_id": action.workflow_id, "step_id": action.step_id,
                           "skill_name": action.skill_name, "attempt_id": action.attempt_id,
                           "expected_revision": action.expected_revision,
                           "skill_binding": action.skill_binding}, "evidence": evidence}

    def final_audit_candidate(self, workflow_id: str, evidence: dict[str, Any]):
        """Validate a candidate declaration without accepting or executing it."""
        workflow = self.store.get_workflow(workflow_id)
        outputs = evidence.get("outputs")
        if not isinstance(outputs, list) or not all(isinstance(p, str) for p in outputs):
            raise ValueError("candidate outputs must be a list of paths")
        result = StepResult(ok=True, artifacts=list(outputs),
                            metadata={"execution_evidence": evidence})
        step = self._result_target(workflow_id, result)
        if step.name != "comp-final-audit":
            raise ValueError("candidate evidence requires the current final-audit step")
        action = self._action_for_step(workflow, step)
        normalized = validate_execution_evidence(Path(workflow.metadata["workspace"]), action, result, store=self.store)
        return self._final_candidate(action, normalized)

    def _validate_step(self, workflow, step, result, session):
        workspace = Path(workflow.metadata["workspace"])
        action = self._action_for_step(workflow, step)
        checks: dict[str, Any] = {}
        evidence: dict[str, Any] = {}
        try:
            evidence = validate_execution_evidence(workspace, action, result, store=self.store, fingerprint_session=session)
            checks["protocol"] = {"ok": True}
        except (ValueError, OSError, TypeError) as exc:
            checks["protocol"] = {"ok": False, "reason": f"invalid execution evidence: {exc}"}
        raw = result.metadata.get("execution_evidence", {})
        raw = raw if isinstance(raw, dict) else {}
        for name, validator in (
            ("companion", lambda: self._companion_gate_message(step, evidence, raw)),
            ("binding", lambda: self._binding_gate_message(workflow, step, evidence, raw)),
            ("assets_usage", lambda: self._asset_gate_message(step, evidence, raw)),
        ):
            try:
                message = validator()
                checks[name] = {"ok": not message, "reason": message or ""}
            except (TypeError, ValueError, AttributeError) as exc:
                checks[name] = {"ok": False, "reason": f"invalid {name} declaration: {exc}"}
        # 空输出合同表示由执行者按需求申报；固定合同仍禁止越界新增产物。
        declared = list(action.output_files or result.artifacts)
        extra = raw.get("additional_skills", [])
        errors = []
        if not isinstance(extra, list):
            errors.append("additional_skills must be a list")
        else:
            for use in extra:
                if not isinstance(use, dict) or not isinstance(use.get("skill"), str):
                    errors.append("additional skill requires skill/reason/contribution/output")
                    continue
                name = use["skill"]
                path = (self.skills_root / name / "SKILL.md").resolve()
                if (not path.is_relative_to(self.skills_root.resolve()) or not path.is_file()
                        or not str(use.get("reason", "")).strip()
                        or not str(use.get("contribution", "")).strip()
                        or use.get("output") not in declared):
                    errors.append(f"invalid additional skill contribution: {name}")
        checks["additional_skills"] = {"ok": not errors, "reason": "; ".join(errors)}
        if action.requires_subagent:
            commands = evidence.get("commands", [])
            has_tool = any("tools/" in c["command"] or "_utils/" in c["command"] for c in commands)
            recorded_review = bool(evidence.get("review_receipts")) and bool(evidence.get("collection"))
            ok = bool(str(raw.get("subagent_session", "")).strip()) and (
                recorded_review if raw.get("collection") else has_tool)
            checks["independent_review"] = {"ok": ok, "reason": "" if ok else
                "requires_subagent: 需要真实 subagent_session 和 tools/ 或 skills/_utils 真实工具调用"}
        manifest = ArtifactManifest.validate(workspace, declared, session=session)
        undeclared = sorted(set(result.artifacts) - set(declared))
        checks["declared_outputs"] = {
            "ok": manifest["ok"] and not undeclared and bool(declared),
            "reason": "declared outputs validation: " + json.dumps({
                "missing": manifest["missing"], "invalid": manifest["invalid"], "undeclared": undeclared}, ensure_ascii=False),
        }
        for name, spec in action.output_specs.items():
            if not isinstance(spec, dict):
                continue
            rel = next((o for o in declared if o == name or Path(o).name == name), None)
            if rel is None:
                continue
            path = ArtifactManifest._path(workspace, rel)
            errors = []
            if path is None or not path.is_file():
                errors.append("文件不存在或路径无效")
            else:
                if path.stat().st_size < int(spec.get("min_bytes", 0)):
                    errors.append(f"低于最低规格 {spec['min_bytes']}B（{spec.get('rationale', '目录级薄产物不可验收')}）")
                words = spec.get("require_any", [])
                if words and not any(str(w).lower() in path.read_text(encoding="utf-8", errors="ignore").lower() for w in words):
                    errors.append(f"未含任何实质内容特征词 {words}")
            checks[f"output_spec:{name}"] = {"ok": not errors, "reason": "D7 产物规格下限: " + "; ".join(errors)}
        if step.metadata.get("output_contract"):
            from .output_contracts import check_output_contract
            checks["business_outputs"] = check_output_contract(workspace, step.metadata["output_contract"],
                primary_output=action.primary_output or "", params=workflow.metadata.get("params", {}))
        manifest_data = None
        try:
            if manifest["ok"]:
                manifest_data = self._prepare_step_manifest(workflow, step, evidence, declared, session)
            if step.name == "comp-final-audit":
                from .audit_store import build_final_audit_report
                current_audit = build_final_audit_report(workspace, self.audit_root,
                                                        workflow_db=Path(self.store.db_path),
                                                        workflow_id=workflow.id, fingerprint_session=session,
                                                        candidate=self._final_candidate(action, evidence)
                                                        if checks["protocol"]["ok"] else None)
                saved_audit = json.loads((workspace / "AUDIT_REPORT.json").read_text(encoding="utf-8"))
                checks["final_audit_binding"] = {"ok": isinstance(saved_audit, dict)
                    and saved_audit.get("workflow_id") == workflow.id
                    and saved_audit.get("artifacts") == current_audit["artifacts"],
                    "reason": "预审必须绑定当前 workflow 与当前验收产物集合"}
                checks["final_audit_live_state"] = {
                    "ok": current_audit["delivery_decision"] in {"eligible", "ready"},
                    "reason": "当前工作流与全部前置门禁的实时验收", "gate_outcomes": current_audit["gate_outcomes"]}
            # D3 门禁前移程序化 + B-02 端到端隔离：合规口径只来自 workflow metadata
            # 里冻结的档案快照（单一事实）——早检与编译页检消费同一份，不再双源
            # （早检解析 profile、编译传 workflow.name 的旧分裂已移除）。
            # 无 bound 快照的既有任务显式待绑定：不冒用现盘规则，赛事口径不下发。
            snapshot = workflow.metadata.get("contest_profile_snapshot")
            bound = isinstance(snapshot, dict) and snapshot.get("status") == "bound"
            contest_id = str(snapshot.get("contest_id")) if bound else ""
            page_contract = dict(snapshot.get("operative") or {}) if bound else None
            quick_gates_profile = str(step.metadata.get("compliance_profile") or "")
            if quick_gates_profile and bound and quick_gates_profile != contest_id:
                checks["contest_identity"] = {"ok": False, "reason":
                    f"步骤显式合规口径 {quick_gates_profile!r} 与工作流绑定赛事身份 {contest_id!r} 冲突——"
                    "身份冲突必须拒绝，不以步骤配置改写赛事"}
            elif step.metadata.get("quick_gates") and not quick_gates_profile and bound \
                    and snapshot.get("compliance"):
                quick_gates_profile = contest_id
            explicit_cap = step.metadata.get("quick_gates_max_pages")
            if explicit_cap is None and bound:
                explicit_cap = (snapshot.get("task_preferences") or {}).get("page_cap")
            if explicit_cap is not None and page_contract is not None:
                page_contract = {**page_contract, "cap": int(explicit_cap), "scope": "body",
                                 "status": "explicit_task",
                                 "reason": "任务/步骤显式口径（只影响当前任务）"}
            gate = QualityGate(workspace).run_all(
                step.name, declared_outputs=declared,
                comp_name=contest_id if (step.metadata.get("revalidate_paper_pages")
                    or step.name in {"comp-compile-zh", "comp-compile-en"}) else "",
                page_contract=page_contract,
                requires_figures=step.name.startswith("paper-figure"),
                required_checks=action.required_checks, primary_output=action.primary_output,
                fingerprint_session=session, manifest_data=manifest_data,
                active_final_step_id=step.id if step.name == "comp-final-audit" else "",
                quick_gates=bool(step.metadata.get("quick_gates")),
                quick_gates_max_pages=step.metadata.get("quick_gates_max_pages"),
                compliance_profile=quick_gates_profile,
                compliance_block=dict(snapshot.get("compliance") or {}) if bound else None,
            )
            checks.update({f"quality:{k}": v for k, v in gate["checks"].items()})
            session.assert_unchanged()
        except (ValueError, OSError, TypeError) as exc:
            gate = {"ok": False, "checks": {"validation": {"ok": False, "reason": str(exc)}}}
            checks["validation"] = gate["checks"]["validation"]
        report = {"ok": all(c.get("ok") is True for c in checks.values()), "checks": checks,
                  "step_id": step.id, "attempt_id": step.attempt_id, "expected_revision": step.revision}
        return report, evidence, manifest, gate, manifest_data

    def complete_recorded_step(self, workflow_id: str, step_id: str, attempt_id: str,
                               revision: int, *, subagent_session: str = "") -> RunResult:
        """执行者只交操作身份；证据构造、终审生成与唯一验收链均由引擎拥有。"""
        from .execution_protocol import collect_execution_evidence
        workflow = self.store.get_workflow(workflow_id)
        target = StepResult(ok=True, step_id=step_id, attempt_id=attempt_id, expected_revision=revision)
        step = self._result_target(workflow_id, target)
        action = self._action_for_step(workflow, step)
        evidence = collect_execution_evidence(self.store, workflow, action, subagent_session=subagent_session)
        if step.name == "comp-final-audit":
            from .audit_store import write_final_audit_report
            candidate = self.final_audit_candidate(workflow_id, evidence)
            write_final_audit_report(action.workspace, self.audit_root,
                workflow_db=Path(self.store.db_path), workflow_id=workflow_id, candidate=candidate)
        request_id = hashlib.sha256(json.dumps(evidence, sort_keys=True, ensure_ascii=True).encode()).hexdigest()
        return self.complete_step(workflow_id, StepResult(ok=True, artifacts=evidence["outputs"],
            step_id=step_id, attempt_id=attempt_id, expected_revision=revision,
            request_id=request_id, metadata={"execution_evidence": evidence}),
            keep_running_on_validation_error=True)

    def complete_step(self, workflow_id: str, result: StepResult, *,
                      keep_running_on_validation_error: bool = False) -> RunResult:
        """Validate once and atomically commit a target-bound completion receipt."""
        workflow = self.store.get_workflow(workflow_id)
        raw = result.metadata.get("execution_evidence", {})
        raw = raw if isinstance(raw, dict) else {}
        payload_hash = hashlib.sha256(json.dumps({
            "ok": result.ok, "stderr": result.stderr, "artifacts": result.artifacts,
            "metadata": result.metadata, "step_id": result.step_id, "attempt_id": result.attempt_id,
            "expected_revision": result.expected_revision,
        }, sort_keys=True, ensure_ascii=True).encode()).hexdigest()
        request_id = result.request_id or str(raw.get("request_id") or payload_hash)
        try:
            cached = self.store.completion_receipt(workflow_id, request_id, payload_hash)
            if cached is not None:
                delivery = self._refresh_delivery(workflow_id)
                if delivery:
                    cached["diagnostics"] = {**cached.get("diagnostics", {}), "delivery": delivery}
                return RunResult(workflow_id, **cached, replayed=True)
            step = self._result_target(workflow_id, result)
        except (ValueError, KeyError) as exc:
            return RunResult(workflow_id, "failed", message=str(exc), diagnostics={"target": str(exc)})
        workspace = Path(workflow.metadata["workspace"])
        session = FingerprintSession(workspace)
        if result.ok:
            report, evidence, manifest, gate, manifest_data = self._validate_step(workflow, step, result, session)
        else:
            report = {"ok": False, "checks": {"execution": {"ok": False, "reason": result.stderr}}}
            evidence, manifest, gate, manifest_data = {}, {"artifacts": []}, {}, None
        good = report["ok"]
        if not good and keep_running_on_validation_error:
            # 单入口自动核验：产物仍可返修，不制造FAILED -> retry -> 新attempt的填表循环。
            return RunResult(workflow_id, "needs_work", step.id,
                "尚未验收，当前步骤保持可编辑；一次修复所有diagnostics后再次finish",
                diagnostics=report)
        waiting = good and bool(step.metadata.get("has_checkpoint"))
        other_incomplete = self.store._connection.execute(
            "SELECT COUNT(*) FROM workflow_steps WHERE workflow_id = ? AND id != ? AND status != 'completed'",
            (workflow_id, step.id),
        ).fetchone()[0]
        status = "failed" if not good else ("waiting_checkpoint" if waiting else ("advanced" if other_incomplete else "completed"))
        message = (f"步骤 {step.name} 完成，等待用户确认" if waiting else f"步骤 {step.name} 完成") if good else "; ".join(
            f"{name}: {check.get('reason', 'failed')}" for name, check in report["checks"].items() if check.get("ok") is not True)
        response = {"status": status, "step_id": step.id, "message": message, "diagnostics": report}
        state = {"status": status, "attempt_id": step.attempt_id, "validation": report, "quality_gates": gate}
        event = {"type": "step_completed" if good else "step_failed", "quality_gates": gate,
                 "attempt_id": step.attempt_id, "validation": report, "stderr": "" if good else message}
        def prepare_evidence():
            session.assert_unchanged()
            collection = evidence.get("collection")
            if collection:
                current_ops = self.store.current_operations(step.id, step.attempt_id)
                if (set(collection["operation_ids"]) != {op["id"] for op in current_ops}
                        or any(op["status"] not in {"succeeded", "reused"} for op in current_ops)):
                    raise ValueError("execution collection changed during completion")
            submission = uuid4().hex
            receipt_path = workspace / ".engine" / "manifests" / f"{step.id}_{step.attempt_id}_{submission}.json"
            if not receipt_path.resolve().is_relative_to(workspace.resolve()):
                raise ValueError("manifest directory escapes workspace")
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_json(receipt_path, manifest_data)
            evidence_path = write_execution_evidence(workspace, self._action_for_step(workflow, step),
                                                     evidence, _manifest_payload(manifest), submission_id=submission)
            state.update(evidence_path=evidence_path, manifest=_manifest_payload(manifest),
                         execution_manifest=receipt_path.relative_to(workspace).as_posix())
            event.update(evidence_path=evidence_path, manifest=_manifest_payload(manifest),
                         execution_manifest=state["execution_manifest"])
        try:
            _, checkpoint = self.store.transition_step_with_checkpoint(
                workflow_id, step.id,
                StepStatus.FAILED if not good else (StepStatus.BLOCKED if waiting else StepStatus.COMPLETED),
                state, artifacts=_manifest_artifacts(manifest) if good else [], event=event,
                expected_revision=step.revision,
                receipt={"request_id": request_id, "payload_hash": payload_hash, "response": response},
                prepare_evidence=prepare_evidence if good else None,
            )
        except (ValueError, OSError, sqlite3.Error) as exc:
            try:
                cached = self.store.completion_receipt(workflow_id, request_id, payload_hash)
            except ValueError:
                cached = None
            if cached is not None:
                delivery = self._refresh_delivery(workflow_id)
                if delivery:
                    cached["diagnostics"] = {**cached.get("diagnostics", {}), "delivery": delivery}
                return RunResult(workflow_id, **cached, replayed=True)
            return RunResult(workflow_id, "failed", step.id, str(exc))
        if good:
            self._publish_manifest_view(workflow_id, workspace, manifest_data)
        self._log(workflow_id, step.id, step.name,
                  "checkpoint" if waiting else ("completed" if good else "failed"),
                  message, agent=self._agent_label(workflow))
        self._audit_record(type="engine_event", event=event["type"], workflow_id=workflow_id,
                           step_id=step.id, skill_name=step.name, attempt_id=step.attempt_id,
                           agent=self._agent_label(workflow), evidence_path=event.get("evidence_path", ""),
                           declared_commands=[c.get("command", "") for c in evidence.get("commands", [])])
        if self.logger is not None:
            try:
                self.logger.save(workflow_id, f"run_{workflow_id}.json")
            except OSError:
                pass
        if status == "completed":
            delivery = self._refresh_delivery(workflow_id)
            if delivery:
                response["diagnostics"] = {**response["diagnostics"], "delivery": delivery}
        return RunResult(workflow_id, **response, checkpoint_id=checkpoint.id)

    # ── 申报-痕迹门禁复用件（C1 companion / P4 binding / C2 assets） ──────
    # 三道闸的校验语义与教学文案原样保留（2026-09-22 P4 资产激活批次 B 抽出），
    # complete_step 与 backfill_step 共用同一实现——补录不得弱于在环完成。
    # 返回 None = 无违规；返回 str = 完整失败消息（含"invalid execution evidence:"
    # 前缀与教学文案），调用方负责转 FAILED。

    @staticmethod
    def _effective_commands(evidence: dict) -> list[str]:
        """Discard pure string-printing declarations; traces are not semantic proof."""
        # 该列表仅用于资源痕迹匹配，不伪造命令记录或returncode。
        commands = [str(r.get("path", "")) for r in evidence.get("resource_reads", [])
                    if isinstance(r, dict)]
        for record in evidence.get("commands", []):
            if not isinstance(record, dict):
                continue
            command = str(record.get("command", "")).strip()
            if re.match(r"(?i)^(echo|printf|write-output|write-host)(?:\s|$)", command):
                continue
            commands.append(command)
        return commands

    @staticmethod
    def _trace_blobs(evidence: dict) -> tuple[str, str]:
        """(trace_blob, command_blob)——trace 覆盖命令+产物/输入路径，command 只含命令串；
        归一化口径与抽取前一致（小写、'-'↔'_' 等价；trace 不分路径分隔符）。"""
        parts = (
            WorkflowRunner._effective_commands(evidence)
            + [str(p) for p in evidence.get("inputs", []) or []]
        )
        trace_blob = " ".join(parts).lower().replace("-", "_")
        command_blob = " ".join(WorkflowRunner._effective_commands(evidence)).lower().replace("-", "_")
        return trace_blob, command_blob

    def _companion_gate_message(self, step: Any, evidence: dict, exec_ev: dict) -> str | None:
        """⛔ C1: 辅助技能强制申报（2026-09-11 用户质询"只推荐不强制会便宜行事"）。
        步骤定义了 companion_skills 时，执行证据必须含 companion_skills 申报：
          {"used": [技能名...], "skipped": [{"skill": 名, "reason": 非空理由}...]}
        used ∪ skipped 必须恰好覆盖本步推荐清单（申报 ≠ 强制使用，但"不用"必须留痕给理由）；
        缺申报/覆盖不全/申报了未推荐的技能/格式错 = 违规（消息含正确格式教学）。"""
        recommended = list(step.metadata.get("companion_skills") or [])
        if not recommended:
            return None

        def _reject(detail: str) -> str:
            # 注意：只有第一段是 f-string；后两段是普通字符串，花括号无需转义
            # （2026-09-11 小修：此前 {{...}} 转义残留导致教学格式渲染成双花括号）
            return (f"invalid execution evidence: 辅助技能申报不合规——{detail}。"
                    '正确格式: "companion_skills": {"used": ["技能名"], '
                    '"skipped": [{"skill": "技能名", "reason": "为何跳过"}]}，'
                    "used 与 skipped 须恰好覆盖本步推荐清单。")

        raw_decl = (exec_ev or {}).get("companion_skills")
        if not isinstance(raw_decl, dict):
            return _reject(f"本步推荐了辅助技能 {recommended} 但证据缺少 companion_skills 申报")
        used = raw_decl.get("used", [])
        skipped = raw_decl.get("skipped", [])
        if not isinstance(used, list) or not all(isinstance(s, str) and s.strip() for s in used):
            return _reject("used 必须是非空技能名字符串数组")
        if not isinstance(skipped, list) or not all(
            isinstance(s, dict) and str(s.get("skill", "")).strip() and str(s.get("reason", "")).strip()
            for s in skipped
        ):
            return _reject('skipped 必须是 [{"skill": 技能名, "reason": 非空理由}] 数组')
        declared = set(used) | {str(s["skill"]) for s in skipped}
        unknown = sorted(declared - set(recommended))
        missing = sorted(set(recommended) - declared)
        if unknown:
            return _reject(f"额外技能请通过 additional_skills 申报，不混入推荐清单: {unknown}")
        if missing:
            return _reject(f"推荐技能未逐一申报使用或跳过: {missing}")
        # ⛔ C1 申报自洽（A2 minor 审计修复）：used 与 skipped 不得重叠——同一技能
        # "既声称用了又声称跳过"是自相矛盾申报，留痕必须口径唯一。归一化与痕迹
        # 校验同口径（不区分大小写、'-' 与 '_' 等价），大小写/连字符变体的重叠同样拦截。
        used_norm = {_norm_skill_token(u) for u in used}
        skipped_norm = {_norm_skill_token(s["skill"]) for s in skipped}
        overlap_norm = used_norm & skipped_norm
        if overlap_norm:
            overlap_display = sorted(
                {u for u in used if _norm_skill_token(u) in overlap_norm}
                | {str(s["skill"]) for s in skipped
                   if _norm_skill_token(s["skill"]) in overlap_norm}
            )
            return _reject(
                f"同一技能同时申报了 used 与 skipped: {overlap_display}（自相矛盾申报）。"
                "每个技能只能二选一：真实使用 → 申报 used（须留使用痕迹）；"
                "确未使用 → 申报 skipped 并写明非空理由")
        # ⛔ C1 痕迹绑定（A5 ⑫/A2 major 修复：used 伪报零校验直接过闸）：
        # 覆盖校验通过后，每个 used 技能必须有真实使用痕迹——技能名
        # （不区分大小写，'-' 与 '_' 等价）出现在任一 evidence.commands 命令串
        # 或任一 declared outputs/inputs 路径中才算有痕；无痕 = 步骤失败，
        # 并教学两条出路（如实补记 consult 命令，或改报 skipped+理由）。
        trace_blob, _command_blob = self._trace_blobs(evidence)
        for used_skill in used:
            trace_key = _norm_skill_token(used_skill)
            if trace_key and trace_key not in trace_blob:
                return _reject(
                    f"used 申报的技能 {used_skill} 在命令与产物/输入路径中零使用痕迹"
                    "（伪报 used 直接过闸已被禁止）。两条出路："
                    "① 把 consult 该技能的真实命令（如读取其 SKILL.md 的命令）如实记入 "
                    "evidence.commands；② 若确未使用，改申报为 skipped 并写明理由")
        return None

    def _binding_gate_message(self, workflow: Workflow, step: Any, evidence: dict,
                              exec_ev: dict) -> str | None:
        """⛔ P4: 技能强制绑定（2026-09-19 "步骤不会强制调用 skills" 的机制层修复）。
        声明了 skill_binding 的步骤满足三件事：
          ① 主技能咨询痕迹：主技能名或 skills/<main>/SKILL.md 出现在 commands/inputs；
          ② mandatory 技能不得 skipped，必须 used 且留命令级痕迹；
          ③ 每条 mandatory 至少有一条命令指向该技能目录（不能只在产物路径里蹭名）。
        未声明 skill_binding 的步骤零影响（向后兼容）——绑定是"显式声明才生效"。"""
        binding = step.metadata.get("skill_binding") or {}
        if not (isinstance(binding, dict) and binding):
            return None

        def _reject(detail: str) -> str:
            requirements = "; ".join(self._action_for_step(workflow, step).binding_requirements())
            return (f"invalid execution evidence: 技能绑定不合规——{detail}。"
                    f"本步绑定要求：{requirements or '见模板 metadata.skill_binding'}。"
                    "绑定技能的意义是「契约被真实读取」而非填字段："
                    "请在执行时真的读取对应 SKILL.md 并记入 evidence.commands。")

        main_skill = str(binding.get("main") or step.name).strip()
        trace_blob, command_blob = self._trace_blobs(evidence)

        if binding.get("main_required", True):
            main_key = _norm_skill_token(main_skill)
            if main_key and main_key not in trace_blob:
                return _reject(
                    f"未见主技能 {main_skill} 的咨询痕迹（命令/输入中缺 "
                    f"skills/{main_skill}/SKILL.md 或技能名）——skill_sha256 只能证明文件被读取过，"
                    "不能证明契约被遵守")

        mandatory = [str(s).strip() for s in (binding.get("mandatory") or []) if str(s).strip()]
        if mandatory:
            raw_decl = (exec_ev or {}).get("companion_skills") or {}
            used_norm = {_norm_skill_token(u) for u in (raw_decl.get("used") or [])}
            skipped_norm = {_norm_skill_token(str(s.get("skill", ""))) for s in (raw_decl.get("skipped") or [])
                            if isinstance(s, dict)}
            for skill in mandatory:
                key = _norm_skill_token(skill)
                if key in skipped_norm:
                    return _reject(
                        f"绑定技能 {skill} 被申报为 skipped，但该技能在本步是必用项（不可跳过）")
                if key not in used_norm:
                    return _reject(f"绑定技能 {skill} 未申报 used（必用技能必须申报使用）")
                if key not in trace_blob:
                    return _reject(f"绑定技能 {skill} 在命令与产物/输入路径中零使用痕迹")
                if key not in command_blob:
                    return _reject(
                        f"绑定技能 {skill} 只出现在产物/输入路径，未出现在任何命令中——"
                        f"请把读取其契约的真实命令（如读取 skills/{skill}/SKILL.md）记入 commands")
        return None

    def _asset_gate_message(self, step: Any, evidence: dict, exec_ev: dict) -> str | None:
        """⛔ C2: 步骤资产强制申报（2026-09-12 资产利用率审计落地）。
        步骤定义了 assets（{"name","path","note"} 列表，path 为仓库根相对）时，
        执行证据必须含 assets 申报，语义与 C1 同构：
          {"used": [资产名...], "skipped": [{"name": 资产名, "reason": 非空理由}...]}
        used ∪ skipped 恰好覆盖清单；申报 ≠ 默认强制使用，但"不用"必须留痕给理由；
        used 资产须有真实痕迹（资产名或仓库根相对路径出现在命令/产物/输入路径中）。
        mandatory 档（W2 资产激活试点）：步骤资产标 "mandatory": true 时 skipped
        不被接受——重资产不得零成本跳过，必须真实读取并留命令痕迹。"""
        required_assets = [a for a in (step.metadata.get("assets") or [])
                           if isinstance(a, dict) and str(a.get("name", "")).strip()]
        if not required_assets:
            return None

        def _reject(detail: str) -> str:
            return (f"invalid execution evidence: 步骤资产申报不合规——{detail}。"
                    '正确格式: "assets": {"used": ["资产名"], '
                    '"skipped": [{"name": "资产名", "reason": "为何跳过"}]}，'
                    "used 与 skipped 须恰好覆盖 StepAction.assets 清单。")

        raw_assets_decl = (exec_ev or {}).get("assets")
        asset_names = [str(a["name"]).strip() for a in required_assets]
        if not isinstance(raw_assets_decl, dict):
            return _reject(f"本步给出了资产清单 {asset_names} 但证据缺少 assets 申报")
        assets_used = raw_assets_decl.get("used", [])
        assets_skipped = raw_assets_decl.get("skipped", [])
        if not isinstance(assets_used, list) or not all(isinstance(s, str) and s.strip() for s in assets_used):
            return _reject("used 必须是非空资产名字符串数组")
        if not isinstance(assets_skipped, list) or not all(
            isinstance(s, dict) and str(s.get("name", "")).strip() and str(s.get("reason", "")).strip()
            for s in assets_skipped
        ):
            return _reject('skipped 必须是 [{"name": 资产名, "reason": 非空理由}] 数组')
        assets_declared = set(assets_used) | {str(s["name"]) for s in assets_skipped}
        assets_unknown = sorted(assets_declared - set(asset_names))
        assets_missing = sorted(set(asset_names) - assets_declared)
        if assets_unknown:
            return _reject(f"申报了本步未给出的资产 {assets_unknown}（本步资产清单: {asset_names}）")
        if assets_missing:
            return _reject(f"资产未逐一申报使用或跳过: {assets_missing}")
        if set(assets_used) & {str(s["name"]) for s in assets_skipped}:
            return _reject("同一资产同时申报了 used 与 skipped（自相矛盾申报）。"
                           "真实使用 → used（须留使用痕迹）；确未使用 → skipped+理由")
        # used 痕迹绑定：资产名或路径（归一化大小写与路径分隔符）出现在
        # commands/outputs/inputs 任一串中即有痕。路径按仓库根相对形态匹配，
        # 绝对路径命令天然包含该子串。
        asset_trace_blob = " ".join(
            self._effective_commands(evidence)
            + [str(p) for p in evidence.get("inputs", []) or []]
        ).lower().replace("\\", "/")
        for asset in required_assets:
            if str(asset["name"]).strip() not in assets_used:
                continue
            asset_path_norm = str(asset.get("path", "")).strip().lower().replace("\\", "/")
            name_hit = str(asset["name"]).strip() in asset_trace_blob
            path_hit = bool(asset_path_norm) and asset_path_norm in asset_trace_blob
            if not name_hit and not path_hit:
                return _reject(
                    f"used 申报的资产 {asset['name']} 在命令与产物/输入路径中零使用痕迹。"
                    "两条出路：① 把读取/执行该资产的真实命令如实记入 evidence.commands"
                    "（含资产路径或资产名）；② 若确未使用，改申报为 skipped 并写明理由")
        # W2 mandatory 档：强制使用资产不接受 skipped 申报（试点重资产防零成本跳过）
        skipped_names = {str(s["name"]) for s in assets_skipped}
        for asset in required_assets:
            if asset.get("mandatory") and str(asset["name"]).strip() in skipped_names:
                return _reject(
                    f"资产 {asset['name']} 为 mandatory（强制使用档）：不接受 skipped 申报，"
                    "必须真实读取该资产并把命令记入 evidence.commands")
        return None

    def _gate_obligations(self, step: Any) -> list[str]:
        """步骤声明了哪些申报-痕迹义务（companion / binding / assets）。空 = 补录无绑定负担。"""
        obligations = []
        if step.metadata.get("companion_skills"):
            obligations.append("companion_skills")
        if step.metadata.get("skill_binding"):
            obligations.append("skill_binding")
        if step.metadata.get("assets"):
            obligations.append("assets")
        return obligations

    def approve_checkpoint(self, checkpoint_id: str, response: dict[str, Any]) -> RunResult:
        """用户批准检查点后继续工作流。"""
        candidates = [c for c in self.store.resume_candidates() if c.checkpoint.id == checkpoint_id]
        if not candidates:
            raise KeyError(f"unknown checkpoint: {checkpoint_id}")
        candidate = candidates[0]
        current = self.store.get_step(candidate.step_id)
        approval_workspace = Path(self.store.get_workflow(candidate.workflow_id).metadata["workspace"])
        approval_session = FingerprintSession(approval_workspace)
        if (current.status != StepStatus.BLOCKED
                or self._latest_checkpoint_id(current.id) != checkpoint_id
                or candidate.checkpoint.state.get("status") != "waiting_checkpoint"):
            return RunResult(candidate.workflow_id, "blocked", current.id,
                             "批准被拒：过期检查点或当前步骤并非等待批准")
        # Revalidate content at the approval boundary. A same-size/mtime rewrite
        # must not reuse the fingerprints captured by complete_step.
        if current.metadata.get("output_files"):
            state = candidate.checkpoint.state
            entries = state.get("manifest", {}).get("artifacts", [])
            declared = current.metadata["output_files"]
            if ({a.get("path") for a in entries if isinstance(a, dict)} != set(declared)
                    or state.get("validation", {}).get("ok") is not True):
                return RunResult(candidate.workflow_id, "blocked", current.id,
                                 "批准被拒：检查点缺少已验收的产物版本，请重新验收")
            fresh = ArtifactManifest.validate(approval_workspace, entries, session=approval_session)
            if not fresh["ok"]:
                return RunResult(candidate.workflow_id, "blocked", current.id,
                                 "批准被拒：验收后产物发生变化或缺失", diagnostics=_manifest_payload(fresh))

        if response.get("approved") is not True:
            return RunResult(candidate.workflow_id, "blocked", candidate.step_id,
                             "检查点未批准")

        # G3 治理缺口收口（2026-09-22）：approve 类检查点是人类确认门，署名红线与
        # A7R-F1（视觉人工复核）同源——空署名或 agent 自指词一律硬拦，禁止无痕批准
        # 与子代理自批（视同伪造审核证据）。
        approved_by = str(response.get("approved_by") or "").strip()
        if not approved_by:
            return RunResult(candidate.workflow_id, "blocked", candidate.step_id,
                             "批准被拒：approved_by 为空——检查点须由人类操作者署名批准"
                             "（CLI 口径: approve --checkpoint <UUID> --by <批准人>）")
        hit = _agent_self_reference_hit(approved_by)
        if hit:
            return RunResult(candidate.workflow_id, "blocked", candidate.step_id,
                             f"批准被拒：approved_by 命中 agent 自指词「{hit}」——"
                             "人类确认检查点禁止 agent 自批（视同伪造审核证据）。"
                             "请由操作者本人（如 默默）执行 approve")

        if current.name == "comp-final-audit":
            from .audit_store import build_final_audit_report
            live = build_final_audit_report(
                Path(self.store.get_workflow(candidate.workflow_id).metadata["workspace"]), self.audit_root,
                workflow_db=Path(self.store.db_path), workflow_id=candidate.workflow_id,
                fingerprint_session=approval_session)
            if live["delivery_decision"] != "eligible":
                return RunResult(candidate.workflow_id, "blocked", current.id,
                                 "批准被拒：前置产物或审计状态已变化", diagnostics=live)

        # M3 FIX: 批准记录 + 步骤完成合并为一次原子事务（transition_step_with_checkpoint），
        # 避免两次独立 transition_step 中途失败导致状态不一致（BLOCKED→RUNNING→COMPLETED 非原子）。
        # approve 检查点会附带一次 checkpoint_approved 事件，步骤直接原子转为 COMPLETED。
        try:
            step, _ = self.store.transition_step_with_checkpoint(
                candidate.workflow_id, candidate.step_id, StepStatus.COMPLETED,
                {"status": "approved", "response": {**response, "approved_by": approved_by},
                 "approved_checkpoint_id": checkpoint_id, "attempt_id": current.attempt_id},
                event={"type": "checkpoint_approved", "approved_by": approved_by,
                       "approved_checkpoint_id": checkpoint_id},
                expected_revision=current.revision, expected_checkpoint_id=checkpoint_id,
                prepare_evidence=approval_session.assert_unchanged, finalize_if_complete=True,
            )
        except (ValueError, OSError, sqlite3.Error) as exc:
            return RunResult(candidate.workflow_id, "blocked", current.id, f"批准被拒：{exc}")
        self._log(candidate.workflow_id, candidate.step_id, step.name, "checkpoint",
                  "用户批准检查点", agent=approved_by)
        self._audit_record(type="engine_event", event="checkpoint_approved", workflow_id=candidate.workflow_id,
                           step_id=candidate.step_id, approved_by=approved_by)

        # 最后一个步骤的批准与工作流收尾已在同一事务落账。
        # 尚有 RUNNING/FAILED/BLOCKED 时交由 next_action 返回真实状态。
        return self.next_action(candidate.workflow_id)

    def retry_last_failed(self, workflow_id: str, by: str = "") -> RunResult:
        """FAILED 或 BLOCKED 步骤的显式重新验收路径。

        FAILED→RUNNING 在 _TRANSITIONS 中合法但此前引擎不可达（CLI 无 retry 命令），
        恢复被迫手改 SQLite（未审计通道）。本方法经引擎走合法转移，落 step_retry
        审计事件（含 step_id、by），把恢复行为纳入审计链。
        """
        workflow = self.store.get_workflow(workflow_id)
        row = self.store._connection.execute(
            "SELECT * FROM workflow_steps WHERE workflow_id = ? AND status IN ('failed', 'blocked') "
            "ORDER BY updated_at DESC, position DESC LIMIT 1",
            (workflow_id,),
        ).fetchone()
        if row is None:
            return RunResult(workflow_id, "failed",
                             message="没有 FAILED 步骤或 BLOCKED 检查点可重新验收；正常推进请用 next")
        failed_step = self.store._step_from_row(row)
        if self._last_running_step(workflow_id) is not None:
            return RunResult(workflow_id, "blocked", message="已有 RUNNING 步骤，不能并行重试另一任务")
        try:
            step, _checkpoint = self.store.transition_step_with_checkpoint(
                workflow_id, failed_step.id, StepStatus.RUNNING,
                {"status": "retrying", "by": by},
                event={"type": "step_retry", "step_id": failed_step.id,
                       "skill_name": failed_step.name, "by": by},
                expected_revision=failed_step.revision,
                expected_checkpoint_id=self._latest_checkpoint_id(failed_step.id)
                    if failed_step.status == StepStatus.BLOCKED else None,
            )
        except ValueError as exc:
            return RunResult(workflow_id, "blocked", failed_step.id, str(exc))
        self._log(workflow_id, step.id, step.name, "retry",
                  f"步骤 {step.name} 重试（FAILED→RUNNING 带内恢复）",
                  agent=by or self._agent_label(workflow))
        self._audit_record(type="engine_event", event="step_retry", workflow_id=workflow_id,
                           step_id=step.id, skill_name=step.name, by=by)
        return RunResult(workflow_id, "advanced", step.id,
                         message=f"步骤 {step.name} 已复位为 RUNNING，重新执行后 complete",
                         action=self._action_for_step(workflow, step))

    # ── D1 断链告警与手工补录（2026-09-13 原仓库缺陷修复建议 D1 落地） ─────
    # 背景：engine_step.log（2026-09-12）显示 14 步 runner 推进到 step 3 等待
    # checkpoint 批准后即停，step 4–14 全部绕开 runner 手工完成，引擎无任何
    # "断链"告警，STEP_MANIFEST/事件库对 4–14 步零记录——评审若要求"每步
    # 可复盘"则溯源断档。本段补两条带内通道：stall 停滞告警 + backfill 补录。

    def detect_stalled(self, workflow_id: str, stall_hours: float = 12.0) -> dict[str, Any]:
        """扫描长期无进展的步骤并告警（D1 断链检测）。

        覆盖两类断链：
        - running_stalled：步骤 RUNNING 后超 ``stall_hours`` 小时未回报
          complete（agent 执行中断/会话丢失）；
        - checkpoint_pending：步骤 BLOCKED 等待用户批准超 ``stall_hours``
          （批准悬置，工作流名存实亡）。

        命中任一即写入运行日志（stall_alert）与引擎侧操作审计事件
        （step_stall_alert）；检测本身失败不阻断主流程。返回结构::

            {"workflow_id", "stall_hours", "alert": bool,
             "stalled": [{step_id, skill_name, position, status,
                          stalled_hours, kind}, ...]}
        """
        now = datetime.now(timezone.utc)
        rows = self.store._connection.execute(
            "SELECT id, name, position, status, updated_at FROM workflow_steps "
            "WHERE workflow_id = ? AND status IN ('running','blocked')",
            (workflow_id,),
        ).fetchall()
        stalled: list[dict[str, Any]] = []
        for row in rows:
            try:
                updated = datetime.fromisoformat(str(row["updated_at"]))
            except (TypeError, ValueError):
                continue
            hours = (now - updated).total_seconds() / 3600.0
            if hours < float(stall_hours):
                continue
            stalled.append({
                "step_id": row["id"],
                "skill_name": row["name"],
                "position": row["position"],
                "status": row["status"],
                "stalled_hours": round(hours, 2),
                "kind": "running_stalled" if row["status"] == "running" else "checkpoint_pending",
            })
        report: dict[str, Any] = {
            "workflow_id": workflow_id,
            "stall_hours": float(stall_hours),
            "alert": bool(stalled),
            "stalled": stalled,
        }
        if stalled:
            self._log(workflow_id, None, None, "stall_alert",
                      f"检测到 {len(stalled)} 个停滞步骤（>{stall_hours} 小时无进展）",
                      stalled=stalled)
            self._audit_record(type="engine_event", event="step_stall_alert",
                               workflow_id=workflow_id, stall_hours=float(stall_hours),
                               stalled=stalled)
        return report

    def backfill_step(self, workflow_id: str, skill_name: str, artifacts: list[str],
                      commands: list[str] | None = None, note: str = "",
                      by: str = "", evidence: dict | None = None,
                      waive_binding: bool = False, waive_reason: str = "") -> RunResult:
        """手工补录绕开 runner 完成的步骤（D1 溯源链闭合）。

        把手工步骤的真实产物哈希与命令补进事件库与 STEP_MANIFEST，走带内
        转移（PENDING→RUNNING→COMPLETED，RUNNING 须匹配当前 attempt），不绕过
        审计。事件类型记 ``step_backfilled``（区别于 step_completed，复审时
        可区分"在环执行"与"人工补录"）。产物不存在即拒绝（backfill 只补
        真实存在的产物，防伪造溯源）。

        ⛔ 绑定旁路封堵（2026-09-22 P4 资产激活批次 B）：步骤声明了任一
        申报-痕迹义务（companion_skills / skill_binding / assets）时，补录
        不再允许"产物存在即完成"。两条合法路径，无第三条（禁止静默旁路）：
        ① ``evidence`` 携带与 complete_step 同构的 execution_evidence——走
           同一 ``validate_execution_evidence``（含 skill_sha256 绑定签名对账）
           与同一组 C1/P4/C2 门禁校验，通过后证据落盘 ``.engine/evidence/``；
        ② ``waive_binding=True`` 且 ``waive_reason`` 非空的显式豁免——补录
           放行，但写 ``backfill_binding_waived`` 审计事件 + 运行日志 +
           step_backfilled 事件 payload 三处留痕，复审可逐条追问豁免理由。
        """
        workflow = self.store.get_workflow(workflow_id)
        row = self.store._connection.execute(
            "SELECT * FROM workflow_steps WHERE workflow_id = ? AND name = ? "
            "ORDER BY position LIMIT 1",
            (workflow_id, skill_name),
        ).fetchone()
        if row is None:
            return RunResult(workflow_id, "failed",
                             message=f"未知步骤: {skill_name}（--step 须为模板中的 skill_name）")
        step = self.store._step_from_row(row)
        if step.status == StepStatus.COMPLETED:
            return RunResult(workflow_id, "failed", step.id,
                             f"步骤 {skill_name} 已 COMPLETED，无需补录")
        if step.status == StepStatus.BLOCKED:
            return RunResult(workflow_id, "blocked", step.id,
                             "补录不能代替检查点批准；请先由操作者 approve 当前检查点")
        if step.status == StepStatus.FAILED:
            return RunResult(workflow_id, "failed", step.id,
                             "失败步骤请先 retry，补录不能复用旧 attempt")
        if step.status == StepStatus.PENDING and step.name == "comp-final-audit":
            return RunResult(workflow_id, "blocked", step.id,
                             "终审补录须先 next 领取当前 step/attempt/revision，再生成候选预审并 backfill；"
                             "PENDING 终审不接受预验收，也不自动代替批准")
        if step.status == StepStatus.RUNNING:
            try:
                self._result_target(workflow_id, StepResult(
                    ok=True, step_id=step.id, artifacts=list(artifacts),
                    metadata={"execution_evidence": evidence or {}}))
            except (ValueError, KeyError) as exc:
                return RunResult(workflow_id, "failed", step.id, str(exc))
        workspace = Path(workflow.metadata["workspace"])
        missing = [a for a in artifacts if ArtifactManifest._path(workspace, a) is None
                   or not (workspace / a).exists()]
        if missing:
            return RunResult(workflow_id, "failed", step.id,
                             "补录产物在工作区不存在: " + ", ".join(missing)
                             + "（backfill 只补录真实存在的产物；相对路径基于工作区根）")
        if not artifacts:
            return RunResult(workflow_id, "failed", step.id,
                             "补录至少需要 --artifact 一个产物（防空补录洗白断链）")

        # ⛔ 绑定门（先于任何状态转移——校验不过 = 零副作用失败，不留 RUNNING 残渣）
        obligations = self._gate_obligations(step)
        binding_state = "no_binding"
        ev_path = ""
        if obligations:
            if waive_binding:
                if not str(waive_reason).strip():
                    return RunResult(workflow_id, "failed", step.id,
                                     f"补录被拒：--waive-binding 必须同时给出非空 --waive-reason "
                                     f"（豁免不落理由 = 静默旁路）。本步义务：{obligations}")
                binding_state = "waived"
            else:
                if not isinstance(evidence, dict):
                    return RunResult(workflow_id, "failed", step.id,
                                     f"补录被拒（禁止静默旁路）：步骤 {skill_name} 声明了绑定义务 "
                                     f"{obligations}，backfill 必须携带与 complete_step 同构的 "
                                     "execution_evidence（--evidence JSON，含真实 skill_sha256/"
                                     "commands/申报），或显式 --waive-binding --waive-reason <理由> "
                                     "豁免并落审计事件")
                action = self._action_for_step(workflow, step)
                try:
                    ev = validate_execution_evidence(
                        workflow.metadata["workspace"], action,
                        StepResult(ok=True, artifacts=list(artifacts),
                                   metadata={"execution_evidence": evidence}))
                except ValueError as exc:
                    return RunResult(workflow_id, "failed", step.id,
                                     f"invalid backfill execution evidence: {exc}")
                for message in (self._companion_gate_message(step, ev, evidence),
                                self._binding_gate_message(workflow, step, ev, evidence),
                                self._asset_gate_message(step, ev, evidence)):
                    if message:
                        return RunResult(workflow_id, "failed", step.id, message)
                binding_state = "verified"
                if not commands:
                    commands = [str(c.get("command", "")) for c in ev.get("commands", [])
                                if isinstance(c, dict) and str(c.get("command", "")).strip()]

        # Verified backfills use exactly the same quality validation as complete.
        # Legacy prose-only backfills remain explicitly unverified and cannot make
        # final delivery ready; they never invent exitCode=0.
        gate = {}
        session = FingerprintSession(workspace)
        validation = {"ok": False, "checks": {"historical_execution": {
            "ok": False, "reason": "unverified historical declaration"}}}
        if isinstance(evidence, dict) and not waive_binding:
            candidate_result = StepResult(ok=True, artifacts=list(artifacts), metadata={"execution_evidence": evidence})
            validation, ev, _manifest, gate, _execution_manifest = self._validate_step(
                workflow, step, candidate_result, session)
            if not validation["ok"]:
                return RunResult(workflow_id, "failed", step.id, "补录验收未通过", diagnostics=validation)
            binding_state = "verified"
        elif step.metadata.get("requires_subagent") or step.metadata.get("has_checkpoint"):
            return RunResult(workflow_id, "failed", step.id,
                             "审核/检查点步骤补录必须提供完整真实 execution_evidence，不能用豁免代替验收")
        manifest = _manifest if binding_state == "verified" else ArtifactManifest.validate(workspace, artifacts, session=session)
        if not manifest.get("ok"):
            return RunResult(workflow_id, "failed", step.id, "补录产物无效", diagnostics=_manifest_payload(manifest))
        if binding_state != "verified":
            _execution_manifest = build_manifest(
                workspace=workspace, step_name=step.name,
                config={"workflow_id": workflow.id, "step_name": step.name, "backfill": True,
                        "by": by, "note": note, "params": workflow.metadata.get("params", {})},
                inputs=[], outputs=[workspace / a for a in artifacts], backend="manual-backfill",
                commands=[{"command": c, "verification": "unverified", "exitCode": None}
                          for c in (commands or [])], dependencies={}, session=session)
        if step.status != StepStatus.RUNNING:
            try:
                step = self.store.transition_step(step.id, StepStatus.RUNNING)
            except ValueError as exc:
                return RunResult(workflow_id, "failed", step.id, str(exc))
        waiting = bool(step.metadata.get("has_checkpoint"))
        state = {"status": "waiting_checkpoint" if waiting else "backfilled", "by": by, "note": note,
                 "binding_check": binding_state, "validation": validation, "quality_gates": gate,
                 "manifest": _manifest_payload(manifest)}
        event = {"type": "step_backfilled", "skill_name": step.name, "by": by,
                 "note": note, "artifacts": list(artifacts), "commands": list(commands or []),
                 "binding_check": binding_state, "binding_obligations": obligations,
                 "waive_reason": str(waive_reason or "") if binding_state == "waived" else "",
                 "validation": validation, "quality_gates": gate, "manifest": _manifest_payload(manifest)}
        def prepare_backfill():
            nonlocal ev_path
            session.assert_unchanged()
            submission = uuid4().hex
            manifest_path = workspace / ".engine" / "manifests" / f"{step.id}_{step.attempt_id}_{submission}.json"
            root_manifest = workspace / "STEP_MANIFEST.json"
            if any(not p.resolve().is_relative_to(workspace.resolve()) for p in (manifest_path, root_manifest)):
                raise ValueError("manifest path escapes workspace")
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_json(manifest_path, _execution_manifest)
            if binding_state == "verified":
                ev_path = write_execution_evidence(workspace, self._action_for_step(workflow, step),
                    ev, _manifest_payload(manifest), submission_id=submission)
            event.update(binding_evidence_path=ev_path, manifest_path=str(manifest_path),
                         execution_manifest=manifest_path.relative_to(workspace).as_posix())
            state.update(evidence_path=ev_path, execution_manifest=event["execution_manifest"])
        try:
            _, checkpoint = self.store.transition_step_with_checkpoint(
                workflow_id, step.id, StepStatus.BLOCKED if waiting else StepStatus.COMPLETED,
                state, artifacts=_manifest_artifacts(manifest), event=event,
                expected_revision=step.revision, prepare_evidence=prepare_backfill,
                finalize_if_complete=True)
        except (ValueError, OSError, sqlite3.Error) as exc:
            return RunResult(workflow_id, "failed", step.id, str(exc))
        self._publish_manifest_view(workflow_id, workspace, _execution_manifest)
        _binding_label = {"no_binding": "无绑定义务", "verified": "绑定证据已验",
                          "waived": f"绑定豁免（理由：{str(waive_reason).strip()}）"}[binding_state]
        self._log(workflow_id, step.id, step.name, "backfill",
                  f"步骤 {step.name} 手工补录（by={by or '未署名'}，产物 {len(artifacts)} 项，{_binding_label}）",
                  agent=by or self._agent_label(workflow))
        self._audit_record(type="engine_event", event="step_backfilled",
                           workflow_id=workflow_id, step_id=step.id,
                           skill_name=step.name, by=by, artifacts=list(artifacts),
                           binding_check=binding_state, binding_obligations=obligations)
        if binding_state == "waived":
            # 豁免必须产生独立可检索的审计事件（P4 批次 B：禁止静默旁路）
            self._audit_record(type="engine_event", event="backfill_binding_waived",
                               workflow_id=workflow_id, step_id=step.id,
                               skill_name=step.name, by=by,
                               obligations=obligations, reason=str(waive_reason).strip())
            self._log(workflow_id, step.id, step.name, "backfill_waive",
                      f"步骤 {step.name} 补录豁免绑定校验（by={by or '未署名'}，"
                      f"义务 {obligations}，理由：{str(waive_reason).strip()}）",
                      agent=by or self._agent_label(workflow))
        elif binding_state == "verified":
            self._audit_record(type="engine_event", event="backfill_binding_verified",
                               workflow_id=workflow_id, step_id=step.id,
                               skill_name=step.name, by=by,
                               obligations=obligations, evidence_path=ev_path)

        # 最后一个补录步骤与工作流收尾同事务，报告是可恢复的派生视图。
        if self.store.get_workflow(workflow_id).status == "completed":
            self._log(workflow_id, None, None, "completed",
                      "所有步骤完成（含手工补录）", agent=self._agent_label(workflow))
            delivery = self._refresh_delivery(workflow_id)
            if delivery:
                validation = {**validation, "delivery": delivery}
        return RunResult(workflow_id, "waiting_checkpoint" if waiting else "advanced", step.id,
                         message=f"步骤 {step.name} 补录已落账（验收状态：{binding_state}）",
                         checkpoint_id=checkpoint.id, diagnostics=validation)

    def _latest_checkpoint_id(self, step_id: str) -> str | None:
        """返回步骤最近一次 checkpoint 的 ID（供 next blocked 输出，A5 ⑦ 修复）。"""
        row = self.store._connection.execute(
            "SELECT id FROM checkpoints WHERE step_id = ? ORDER BY created_at DESC, rowid DESC LIMIT 1",
            (step_id,),
        ).fetchone()
        return row[0] if row else None

    def _has_pending_steps(self, workflow_id: str) -> bool:
        """检查工作流是否还有待执行的 pending 步骤。"""
        row = self.store._connection.execute(
            "SELECT COUNT(*) FROM workflow_steps WHERE workflow_id = ? AND status = 'pending'",
            (workflow_id,),
        ).fetchone()
        return row[0] > 0 if row else False

    def _agent_label(self, workflow: Workflow) -> str:
        """返回当前步骤的执行 agent 标签（宿主中立默认值；驱动方可经 params.agent 覆盖）。"""
        from .agent_protocol import default_agent_label

        params = workflow.metadata.get("params", {})
        return default_agent_label(str(params.get("agent", "") or ""))

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

    def _first_blocked_step(self, workflow_id: str):
        """checkpoint 等待批准的步骤（blocked）。2026-09-09 审计 P1-2：blocked 必须是推进硬闸。"""
        row = self.store._connection.execute(
            "SELECT * FROM workflow_steps WHERE workflow_id = ? AND status = 'blocked' ORDER BY position LIMIT 1",
            (workflow_id,),
        ).fetchone()
        if row is None:
            return None
        return self.store._step_from_row(row)

    def _write_contest_env(self, workspace: Path, profile: Any) -> None:
        """把 bound 快照的五字段机械口径写入工作区执行环境文件。

        消费者（quick_gates 等）程序读取，优先级低于调用方显式 --max-pages；
        cap 缺席（口径 None）也如实落空值——读取侧据此 SKIP，不回退默认页限。
        """
        env_dir = workspace / ".engine"
        env_dir.mkdir(parents=True, exist_ok=True)
        operative = profile.operative or {}
        lines = [
            "# contest_env — 引擎自 bound 档案快照程序注入（B-CLOSE-01）；勿手改，口径以本文件为准",
            f"# rules_revision: {profile.rules_revision}",
            f"CONTEST_ID={profile.contest_id}",
            f"PAGE_CAP={operative.get('cap') if operative.get('cap') is not None else ''}",
            f"PAGE_SCOPE={profile.gate_page_scope}",
            f"PAGE_CAP_STATUS={operative.get('status', '')}",
            f"EDITION={profile.edition or ''}",
        ]
        (env_dir / "contest_env").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _dispatch_quick_gates_cap(self, workflow: Workflow, step: Any) -> int | None:
        """派发侧 --max-pages 渲染值（B-CLOSE-01）：步骤显式声明 > bound 快照
        gate_page_cap > None（不渲染旗标，页检 SKIP——不回退默认 30/80）。

        快照 operative 已含任务显式口径（resolve_operative_cap 折入），
        故快照回落不会放大口径范围。"""
        cap = step.metadata.get("quick_gates_max_pages")
        if cap is not None:
            return cap
        snapshot = workflow.metadata.get("contest_profile_snapshot")
        if isinstance(snapshot, dict) and snapshot.get("status") == "bound":
            cap = (snapshot.get("operative") or {}).get("cap")
            if cap is not None:
                return int(cap)
        return None

    def _action_for_step(self, workflow: Workflow, step: Any) -> StepAction:
        return StepAction(
            workflow_id=workflow.id, step_id=step.id, position=step.position, skill_name=step.name,
            display_name=step.metadata.get("display_name", step.name),
            workspace=Path(workflow.metadata["workspace"]), skill_path=self.skills_root / step.name / "SKILL.md",
            output_files=step.metadata.get("output_files", []), primary_output=step.metadata.get("primary_output", ""),
            has_checkpoint=step.metadata.get("has_checkpoint", False), checkpoint_type=step.metadata.get("checkpoint_type"),
            companion_skills=step.metadata.get("companion_skills", []),
            assets=step.metadata.get("assets", []),
            quick_gates=bool(step.metadata.get("quick_gates", False)),
            quick_gates_max_pages=self._dispatch_quick_gates_cap(workflow, step),
            skill_binding=dict(step.metadata.get("skill_binding") or {}),
            params=workflow.metadata.get("params", {}),
            attempt_id=step.attempt_id,
            expected_revision=step.revision,
            required_checks=list(dict.fromkeys(
                list(step.metadata.get("required_checks") or [])
                + (["step_manifest"] if step.metadata.get("output_files") else [])
                + (["review"] if step.name in {"comp-review", "comp-visual-review", "comp-final-review"} else []))),
            output_specs=dict(step.metadata.get("output_specs") or {}),
            requires_subagent=bool(step.metadata.get("requires_subagent")),
            review_scope=str(step.metadata.get("review_scope") or workflow.name),
            skill_sha256=hashlib.sha256((self.skills_root / step.name / "SKILL.md").read_bytes()).hexdigest()
                if (self.skills_root / step.name / "SKILL.md").is_file() else "",
        )

    def _prepare_step_manifest(self, workflow, step, evidence, declared_outputs, session):
        workspace = Path(workflow.metadata["workspace"])
        source_manifest = evidence.get("execution_manifest")
        if source_manifest:
            source = ArtifactManifest._path(workspace, str(source_manifest))
            if source is None or not source.is_file():
                raise ValueError("execution_manifest must be an existing workspace-relative file")
            session.fingerprint(source_manifest)
            existing = json.loads(source.read_text(encoding="utf-8"))
            if not isinstance(existing, dict):
                raise ValueError("execution_manifest must contain a JSON object")
        else:
            existing = get_step_manifest(workspace)
            # 自动生成的根清单只是上次提交的视图，不能约束新 attempt 的产物。
            # 工具原始清单仍严格复验；显式引用旧清单也不得静默重建。
            if (isinstance(existing, dict) and existing.get("backend") in {"workflow-runner", "recorded-execution"}
                    and (existing.get("workflowId") != workflow.id
                         or existing.get("attemptId") != step.attempt_id)):
                existing = None
        if isinstance(existing, dict) and (source_manifest or existing.get("stepName") == step.name):
            def canonical(value):
                path = ArtifactManifest._path(workspace, str(value))
                if path is None:
                    raise ValueError("execution manifest output escapes workspace")
                return path.relative_to(workspace.resolve()).as_posix()
            declared = {canonical(o.get("path", "")) for o in existing.get("outputFiles", []) if isinstance(o, dict)}
            required = {canonical(value) for value in declared_outputs}
            matches = required <= declared if source_manifest else required == declared
            if not matches:
                raise ValueError("execution manifest outputs do not match the active step")
            return existing
        return build_manifest(
            workspace, step.name,
            config={**dict(step.metadata.get("manifest_config") or {}),
                    "workflow_id": workflow.id, "step_name": step.name,
                    "params": workflow.metadata.get("params", {}),
                    "execution": evidence.get("execution_config", {})},
            inputs=[workspace / p for p in evidence.get("inputs", [])],
            outputs=[workspace / p for p in declared_outputs],
            backend=str(step.metadata.get("backend") or evidence.get("backend") or "workflow-runner"),
            commands=evidence.get("commands", []),
            dependencies={**dict(evidence.get("dependencies") or {}), **dict(step.metadata.get("dependencies") or {})},
            extra={"attemptId": step.attempt_id, "workflowId": workflow.id}, session=session,
        )

    def _publish_manifest_view(self, workflow_id, workspace, manifest_data) -> None:
        """Best-effort convenience view, published only after DB commit.

        Accepted versions live in immutable event-referenced manifests, not here.
        A view failure cannot undo or misreport a successful database commit.
        """
        try:
            root = workspace / "STEP_MANIFEST.json"
            if not root.resolve().is_relative_to(workspace.resolve()):
                raise ValueError("execution manifest escapes workspace")
            if get_step_manifest(workspace) != manifest_data:
                atomic_write_json(root, manifest_data)
        except (OSError, ValueError) as exc:
            self._log(workflow_id, None, None, "manifest_view_pending", str(exc))

    def _refresh_delivery(self, workflow_id: str) -> dict[str, Any]:
        """A failed derived report is recoverable; never pretend the commit failed."""
        workflow = self.store.get_workflow(workflow_id)
        if workflow.status != "completed":
            return {}
        from .audit_store import write_final_audit_report
        workspace = Path(workflow.metadata["workspace"])
        if not (workspace / "AUDIT_REPORT.json").is_file():
            return {}
        try:
            path = write_final_audit_report(workspace, self.audit_root,
                out=workspace / "DELIVERY_REPORT.json", workflow_db=Path(self.store.db_path),
                workflow_id=workflow_id)
            return {"report": path.name, "decision": json.loads(path.read_text(encoding="utf-8"))["delivery_decision"]}
        except (OSError, ValueError, sqlite3.Error) as exc:
            return {"decision": "pending", "reason": str(exc),
                    "recovery": "重发 complete / next 或执行 final-audit；不得视为 ready"}


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
                **({"members": artifact.members} if artifact.members is not None else {}),
            }
            for artifact in manifest["artifacts"]
        ],
    }


def _manifest_artifacts(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"name": Path(artifact.path).name, "path": artifact.path,
         "metadata": {"sha256": artifact.sha256, "size": artifact.size, "mime_type": artifact.mime_type,
                      **({"members": artifact.members} if artifact.members is not None else {})}}
        for artifact in manifest["artifacts"]
    ]
