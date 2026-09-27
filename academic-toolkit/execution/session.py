"""执行会话门面：组织上下文并提交操作事实；领域工作由当前Agent完成。"""
from __future__ import annotations
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from engine.step_manifest import atomic_write_json
from engine.workflow_store import StepStatus
from .context import OperationContext
from .resources import ResourceCatalog
from .workspace import WorkspaceFiles
from .commands import CommandExecutor
from .review import ReviewExchange

# 技能自有的步内业务状态文件（compaction 恢复上下文）。它们只承载轮次/phase
# 记录，永远不决定引擎步骤状态；引擎（workflow SQLite）是唯一状态所有者。
_IN_STEP_STATE_FILES = {
    "REVIEW_STATE.json": "review_round",
    "poster/POSTER_STATE.json": "poster_phase",
    "slides/SLIDES_STATE.json": "slides_phase",
}

class ExecutionSession:
    def __init__(self, runner, workflow_id, action=None):
        self.runner, self.store, self.workflow_id = runner, runner.store, workflow_id
        self.workflow = self.store.get_workflow(workflow_id)
        if action is None:
            outcome = runner.next_action(workflow_id)
            if outcome.action is None:
                raise ValueError(f"{outcome.status}: {outcome.message}")
            action = outcome.action
        if action.workflow_id != workflow_id or self.store.get_step(action.step_id).workflow_id != workflow_id:
            raise ValueError("会话与工作流归属不一致")
        self.action = action
        self.workspace = action.workspace.resolve()
        self.operations = OperationContext(self.store, action, runner.skills_root.parent.parent)
        self.files = WorkspaceFiles(self.operations)
        self.resources = ResourceCatalog(self.operations)
        self.commands = CommandExecutor(self.operations)
        self.review = ReviewExchange(self.operations)

    def _in_step_resume(self) -> dict:
        """步内恢复对账：引擎状态与成果版本是权威，技能状态文件仅是业务上下文。

        同任务已完成时不得因状态文件而自动重开；状态文件声称 completed 而引擎
        步骤仍在 RUNNING（未验收）时，既不能当作已完成交付，也不得静默重开覆盖
        真实成果。此处只读对照、给判定文案，不写状态文件、不维护第二套状态。
        """
        engine = {"step_status": "running", "attempt_id": self.action.attempt_id,
                  "revision": self.action.expected_revision,
                  "outputs_version": {name: hashlib.sha256((self.workspace / name).read_bytes()).hexdigest()[:12]
                                      for name in self.action.output_files
                                      if (self.workspace / name).is_file()}}
        entries = []
        for relative, kind in _IN_STEP_STATE_FILES.items():
            path = self.workspace / relative
            if not path.is_file():
                continue
            try:
                state = json.loads(path.read_text(encoding="utf-8"))
                recorded_status = str(state.get("status", ""))
                progress = state.get("round", state.get("phase"))
            except (OSError, ValueError):
                recorded_status, progress = "unreadable", None
            if recorded_status == "in_progress":
                verdict = "resume"
                guidance = (f"业务状态有效：从记录位置（{kind}={progress}）继续；"
                            "elapsed 时间不使真实工作失效。")
            elif recorded_status == "completed":
                verdict = "conflict_engine_not_accepted"
                guidance = ("状态文件声称 completed，但引擎步骤尚未验收（RUNNING）。"
                            "以引擎为准：先走 finish 统一验收，不得当作已完成交付；"
                            "也不得静默重开覆盖已有成果——重做须操作者明确确认并归档旧状态文件。")
            else:
                verdict = "context_only"
                guidance = "状态文件不可读或无 status，仅作业务参考；恢复判断以引擎状态与磁盘成果为准。"
            entries.append({"file": relative, "kind": kind, "recorded_status": recorded_status,
                            "recorded_progress": progress, "verdict": verdict, "guidance": guidance})
        return {"authority": "engine_workflow_store", "engine": engine, "state_files": entries}

    def context(self, query: str = "") -> dict:
        self.operations.require_active()
        required = list(dict.fromkeys([self.action.skill_name, *self.action.skill_binding.get("mandatory", [])]))
        documents = [self.resources.read_resource(name) for name in required]
        documents.extend(self.resources.read_resource(a["name"], "asset") for a in self.action.assets if a.get("mandatory"))
        ticket = self.workspace / ".engine/sessions" / f"{self.action.attempt_id}.json"
        atomic_write_json(ticket, {"database": str(Path(self.store.db_path).resolve()),
            "workflow_id": self.workflow_id, "step_id": self.action.step_id,
            "attempt_id": self.action.attempt_id, "revision": self.action.expected_revision,
            "audit_root": str(self.runner.audit_root)})
        # 唯一赛事档案快照（B-02 端到端隔离）：context 只消费 workflow metadata 里
        # 冻结的有效档案，不再实时解析现盘规则——全局配置变化不静默改变旧任务。
        # 档案文件变化时以 rules_drift 显式提示重验（规则变化优先重验）。
        # 非赛事模板下发 None；快照机制启用前的赛事工作流显式标 pending_binding，
        # 不拿现盘规则冒充历史快照。
        from engine import contest_profile as cp_mod
        snapshot = self.workflow.metadata.get("contest_profile_snapshot")
        contest_view: dict | None
        if isinstance(snapshot, dict) and snapshot.get("status") == "bound":
            contest_view = dict(snapshot)
            contest_view["consumed_by"] = ["context", "pages", "early_check", "final_audit"]
            current_digest = cp_mod.rules_digest()
            # 比对基线取快照冻结的档案文件哈希；rules_revision 可能是档案显式版本
            # 标签（如"2026年修订稿"），与 64 位哈希不同域，混比会恒报 drift。
            baseline = (snapshot.get("source") or {}).get("rules_sha256") or \
                snapshot.get("rules_revision")
            if current_digest and current_digest != baseline:
                contest_view["rules_drift"] = {
                    "detected": True,
                    "current_rules_sha256": current_digest,
                    "snapshot_rules_revision": snapshot.get("rules_revision"),
                    "guidance": "档案文件已变化：规则变化优先重验（重跑页数/合规检查），"
                                "执行依赖未变化则无需重算（scope-2 执行合同不受影响）",
                }
        elif isinstance(snapshot, dict):
            contest_view = snapshot  # pending_binding 显式标记，原样下发
        elif cp_mod.is_known_contest(self.workflow.name) or \
                isinstance((self.workflow.metadata.get("params") or {}).get("contest"), dict):
            contest_view = cp_mod.pending_binding_snapshot(
                self.workflow.name, self.workflow.metadata.get("params"))
        else:
            contest_view = None
        return {"session": str(ticket), "task": self.action.display_name,
                "review_scope": self.action.review_scope, "parameters": self.workflow.metadata.get("params", {}),
                "outputs": self.action.output_files, "quality_requirements": self.action.required_checks,
                "documents": documents, "resources": self.resources.resources(query),
                "contest_profile": contest_view,
                "in_step_resume": self._in_step_resume(),
                "execution_policy": {
                    "program_owned": ["操作事实与返回码", "身份与内容摘要", "执行清单与证据组装", "合同中已接入的质量检查", "状态推进"],
                    "llm_owned": ["任务理解与领域推理", "方案/方法/论证与实质产出", "结果解释与语义质量", "独立评审和人工决策所需内容"],
                    "quality_ownership": "执行记录、摘要和清单由程序生成；领域检查由合同指定的检查器或真实review/check操作完成。",
                },
                "instructions": "阅读材料用read(kind=workspace)，创作/精确修订用write/edit，工具操作用run。完成后finish一次验收，不手填证据/哈希、不必先preflight；人工批准不可代替。工作区内的 *STATE.json 是技能业务上下文，只用于步内续作；步骤完成与否以引擎状态为准，不得据其自动重开已完成任务。"}


    def finish(self, *, subagent_session=""):
        existing = self.store.get_step(self.action.step_id)
        if existing.attempt_id == self.action.attempt_id and existing.status in {StepStatus.COMPLETED, StepStatus.BLOCKED}:
            result = self.runner.next_action(self.workflow_id)
            return {"status": result.status, "message": result.message, "replayed": True,
                    "checkpoint_id": result.checkpoint_id, "diagnostics": result.diagnostics}
        self.operations.require_active()
        result = self.runner.complete_recorded_step(self.workflow_id, self.action.step_id,
            self.action.attempt_id, self.action.expected_revision, subagent_session=subagent_session)
        payload = asdict(result)
        if result.status == "advanced":
            following = self.runner.next_action(self.workflow_id)
            if following.action is not None:
                session = ExecutionSession(self.runner, self.workflow_id, following.action)
                payload["next"] = session.context()
                step = self.store.get_step(following.action.step_id)
                if (step.name == "comp-final-audit" and step.metadata.get("machine_audit_only") is True
                        and not following.action.requires_subagent):
                    payload["machine_audit"] = session.finish()
        return payload
