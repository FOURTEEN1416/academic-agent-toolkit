"""执行操作的工作区/身份/事实边界；不编排步骤、不执行命令。"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import Any
from engine.artifact_manifest import FingerprintSession
from engine.execution_protocol import execution_contract
from engine.workflow_store import StepStatus

def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def snapshot(root: Path, names: list[str]) -> dict[str, str]:
    session = FingerprintSession(root)
    result = {}
    for name in dict.fromkeys(names):
        item = session.fingerprint(name)
        if not item.exists:
            raise ValueError(f"依赖或产物不存在: {name}")
        result[item.path] = item.sha256
    session.assert_unchanged()
    return result


class OperationContext:
    def __init__(self, store, action, repository):
        self.store = store
        self.action = action
        self.workspace = action.workspace.resolve()
        self.repo = Path(repository).resolve()
        self.workflow_id = action.workflow_id

    def require_active(self) -> None:
        step = self.store.get_step(self.action.step_id)
        if (step.status != StepStatus.RUNNING or step.attempt_id != self.action.attempt_id
                or step.revision != self.action.expected_revision):
            raise ValueError("会话已失效；重新 context 获取当前步骤，不能将旧命令发给下一步")


    def relative(self, value: str) -> str:
        path = Path(value)
        raw = path if path.is_absolute() else self.workspace / path
        for ancestor in (raw, *raw.parents):
            if ancestor == self.workspace:
                break
            if ancestor.is_symlink() or (hasattr(ancestor, "is_junction") and ancestor.is_junction()):
                raise ValueError("任务路径不能经过链接或目录联结")
        resolved = raw.resolve()
        if not resolved.is_relative_to(self.workspace) or ".engine" in resolved.relative_to(self.workspace).parts:
            raise ValueError(f"任务路径必须位于工作区且不能指向引擎状态: {value}")
        return resolved.relative_to(self.workspace).as_posix()


    def begin(self, kind: str, node: str, payload: dict, cache_key: str = "") -> str:
        self.require_active()
        return self.store.begin_operation(self.workflow_id, self.action.step_id,
            self.action.attempt_id, self.action.expected_revision, kind, node, payload, cache_key)


    def finish(self, operation_id: str, status: str, payload: dict) -> dict:
        self.store.finish_operation(operation_id, status, payload)
        return {"operation_id": operation_id, "status": status, **payload}


    def trace_lineage(self, anchors: dict[str, str], adopt: dict[str, str] | None = None) -> dict:
        """追溯字节的已记录生产者并递归继承传递依赖；区分新资料与历史生产依赖。

        anchors: 路径→须匹配的版本（修订前字节/当前声明产物）。
        adopt: 本次重新阅读过的当前版本。仅当旧字节的直接依据产物（第一层）
        被重算并重读为另一版本时，才从新版本接续谱系——"上游重算、重新阅读、
        更新报告"的正路由此放行。第一层以下的继承一律保持历史版本：已有计算
        结果的生产依赖是其产出时刻的事实，不因下游重新阅读而改记（中间结果 v1
        的原始输入仍记 v1，重读 v2 只是新资料，不洗白旧链）。
        reused 行只是复用凭证，不是生产者：溯源穿透到原始执行行。
        """
        rows = self.store._connection.execute(
            "SELECT o.* FROM execution_operations o JOIN workflow_steps s ON s.id=o.step_id "
            "WHERE o.workflow_id=? AND o.status IN ('succeeded','reused') AND o.kind IN ('command','write','review') "
            "AND ((o.step_id=? AND o.attempt_id=?) OR (s.status='completed' AND s.attempt_id=o.attempt_id)) "
            "ORDER BY o.rowid DESC", (self.workflow_id, self.action.step_id, self.action.attempt_id)).fetchall()
        records, by_id = [], {}
        for row in rows:
            payload = json.loads(row["payload"])
            records.append((row["id"], payload))
            by_id[row["id"]] = payload
        adopt = dict(adopt or {})
        sources, dependencies = {}, {}
        queue, enqueued = [], set()

        def enqueue(name: str, version: str, depth: int) -> None:
            if (name, version, depth) not in enqueued:
                enqueued.add((name, version, depth))
                queue.append((name, version, depth))

        def producer_of(name: str, version: str):
            record = next((r for r in records if r[1].get("outputs_snapshot", {}).get(name) == version), None)
            hops, seen = 0, set()
            while record is not None and record[1].get("reused_from") and record[0] not in seen and hops < 8:
                seen.add(record[0])
                origin = by_id.get(record[1]["reused_from"])
                if origin is None:
                    break
                record = (record[1]["reused_from"], origin)
                hops += 1
            return record

        for name, version in anchors.items():
            enqueue(name, version, 0)
        while queue:
            name, version, depth = queue.pop()
            if depth >= 1 and name in adopt and adopt[name] != version:
                # 第一层以下：历史生产依赖不因重读改写，旧版本如实保留并由对账把关。
                if name in dependencies and dependencies[name] != version:
                    raise ValueError(f"产物的传递输入版本冲突: {name}")
                dependencies[name] = version
                continue
            record = producer_of(name, version)
            if record is None:
                # 无记录生产者的叶子（外部输入/预置文件）：如实保留为未溯源依赖。
                if name in dependencies and dependencies[name] != version:
                    raise ValueError(f"产物的传递输入版本冲突: {name}")
                dependencies[name] = version
                continue
            if name in anchors and anchors[name] == version and name not in sources:
                sources[name] = record[0]
            if depth >= 1:
                if name in dependencies and dependencies[name] != version:
                    raise ValueError(f"产物的传递输入版本冲突: {name}")
                dependencies[name] = version
            for dependency, value in {**record[1].get("lineage_inputs", {}),
                                      **record[1].get("inputs_snapshot", {})}.items():
                if dependency in record[1].get("mutates", []) or dependency == name:
                    continue
                if depth == 0 and dependency in adopt and adopt[dependency] != value:
                    # 第一层直接依据被重算重读为新版本：旧版本及其上游被显式取代，
                    # 从新版本接续谱系（新版本的生产行真实存在，链路如实重建）。
                    value = adopt[dependency]
                enqueue(dependency, value, depth + 1)
        if snapshot(self.workspace, list(dependencies)) != dependencies:
            raise ValueError("既有产物上游输入已变化，先重算生产步骤，不能仅修订下游洗白")
        return {"source_operations": sources, "lineage_inputs": dependencies}

    def execution_relevant_contract(self) -> str:
        """缓存键使用的执行相关合同子集：步骤元数据、业务参数与主技能正文。

        全赛种规则摘要仍完整保存于操作记录（contract 字段）；规则变化改变
        验收门禁，不构成确定性命令的重算依据，避免全库规则无条件成为
        每个命令的生产依赖。
        """
        body = {"metadata": self.store.get_step(self.action.step_id).metadata,
                "params": self.store.get_workflow(self.workflow_id).metadata.get("params", {}),
                "skill": self.action.skill_sha256, "session_protocol": 1}
        return digest(body)

    def contract(self):
        workflow = self.store.get_workflow(self.workflow_id)
        step = self.store.get_step(self.action.step_id)
        rules = self.action.skill_path.parents[2] / "engine/modex-core"
        return execution_contract(self.action, step.metadata, workflow.metadata.get("params", {}), rules)
