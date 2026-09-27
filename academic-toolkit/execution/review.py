"""宿主独立评审任务与版本绑定。记录程序可观察事实，不声称能认证模型身份。"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from uuid import uuid4
from engine.step_manifest import atomic_write_json, durable_replace
from .context import snapshot


class ReviewExchange:
    def __init__(self, context):
        self.context = context
        self.store = context.store
        self.action = context.action
        self.workspace = context.workspace

    def _next_round(self) -> int:
        """轮次号由引擎操作记录推导（该 attempt 内已接收的评审数 + 1），不由模型填报。

        重评场景下旧操作被 node_key 折叠取代，此处按历史行计数：真正发生过的
        每次 receive 都计入轮次，与 review_tasks/round_<N>.md 业务记录可对账。
        """
        rows = self.store.execution_operations(self.action.step_id, self.action.attempt_id)
        return sum(1 for row in rows if row["kind"] == "review" and row["status"] == "succeeded") + 1

    def request(self, inputs: list[str], output: str, rubric: str) -> dict:
        self.context.require_active()
        if not inputs or not rubric.strip():
            raise ValueError("评审需真实输入与明确评审标准")
        inputs = [self.context.relative(p) for p in inputs]
        output = self.context.relative(output)
        if output in inputs:
            raise ValueError("评审输出不能覆盖受审输入")
        if self.action.output_files and output not in self.action.output_files:
            raise ValueError("评审返回路径必须是当前步骤合同产物")
        versions = snapshot(self.workspace, inputs)
        task_id = uuid4().hex
        rnd = self._next_round()
        state = {"task_id": task_id, "step_id": self.action.step_id, "attempt_id": self.action.attempt_id,
                 "workflow_id": self.action.workflow_id, "revision": self.action.expected_revision,
                 "round": rnd, "inputs": versions, "output": output, "rubric": rubric,
                 "status": "awaiting_independent_context", "host_attested": False}
        path = self.workspace / ".engine/reviews" / f"{task_id}.json"
        atomic_write_json(path, state)
        return {"review_task": str(path), "status": state["status"], "round": rnd,
                "instructions": "交给独立上下文，只读输入并返回完整原文；当前执行者不代写裁定。",
                "inputs": list(versions), "output": output, "rubric": rubric}

    def receive(self, task_file: str, response_file: str, reviewer: str, host_call_id: str) -> dict:
        self.context.require_active()
        task_path = Path(task_file).resolve()
        if not task_path.is_relative_to(self.workspace / ".engine/reviews"):
            raise ValueError("评审任务不属于工作区")
        task = json.loads(task_path.read_text(encoding="utf-8"))
        if (task.get("step_id") != self.action.step_id or task.get("attempt_id") != self.action.attempt_id
                or task.get("revision") != self.action.expected_revision):
            raise ValueError("评审任务已失效")
        if task.get("status") != "awaiting_independent_context":
            raise ValueError("评审任务已经接收，不能覆盖")
        if not reviewer.strip() or not host_call_id.strip():
            raise ValueError("必须记录实际评审者和宿主调用标识，不能自动编造")
        workflow = self.store.get_workflow(self.action.workflow_id)
        if reviewer == workflow.metadata.get("params", {}).get("agent"):
            raise ValueError("执行者不能把自己声明为独立评审者")
        if snapshot(self.workspace, list(task["inputs"])) != task["inputs"]:
            raise ValueError("评审后输入已改变；重新评审当前版本")
        source = self.workspace / self.context.relative(response_file)
        if not source.is_file() or source.stat().st_size < 40:
            raise ValueError("评审原文缺失或不完整")
        raw = source.read_bytes()
        raw.decode("utf-8")
        output = self.workspace / task["output"]
        payload = {"reviewer": reviewer, "host_call_id": host_call_id, "task_id": task["task_id"],
            "round": task.get("round"),
            "inputs_snapshot": task["inputs"], "response_sha256": hashlib.sha256(raw).hexdigest(),
            "verification_level": "version_bound_received_response; host identity not independently authenticated",
            "backend": "host-independent-review", "contract": self.context.contract()}
        op = self.context.begin("review", "review:" + task["output"], payload)
        try:
            output.parent.mkdir(parents=True, exist_ok=True)
            staged = output.with_name(f".{output.name}.{uuid4().hex}.tmp")
            staged.write_bytes(raw)
            # 复用引擎唯一的原子发布实现（Windows 共享冲突有界重试），不自建第二套。
            durable_replace(staged, output)
            payload["outputs_snapshot"] = snapshot(self.workspace, [task["output"]])
            result = self.context.finish(op, "succeeded", payload)
            atomic_write_json(task_path, {**task, "status": "received", "operation_id": op})
            return result
        except Exception as exc:
            self.context.finish(op, "failed", {**payload, "error": type(exc).__name__})
            raise
