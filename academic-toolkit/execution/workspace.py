"""工作区阅读/创作/精确修订；记录真实依赖并原子发布。"""
from __future__ import annotations
import hashlib
import os
from uuid import uuid4
from engine.step_manifest import durable_replace
from .context import snapshot

class WorkspaceFiles:
    def __init__(self, context):
        self.context = context
        self.store = context.store
        self.action = context.action
        self.workspace = context.workspace

    def read_file(self, target: str) -> dict:
        """阅读工作区资料/稿件而非仓库技能；阅读记录不冒充执行或产出。"""
        relative = self.context.relative(target)
        path = self.workspace / relative
        if not path.is_file():
            raise ValueError(f"工作区文件不存在: {relative}")
        if path.stat().st_size > 256_000:
            raise ValueError("文件超过上下文预算，请先用读取工具提取所需段落")
        raw = path.read_bytes()
        text = raw.decode("utf-8-sig")
        payload = {"path": relative, "sha256": hashlib.sha256(raw).hexdigest(),
                   "bytes": len(raw), "observation": "workspace_content_returned",
                   "observation_role": "trace_only"}
        op = self.context.begin("observation", f"observation:{relative}", payload)
        self.context.finish(op, "succeeded", payload)
        return {"name": relative, "kind": "workspace", "content": text, **payload}


    def _observed_versions(self, target: str,
                           declared_inputs: list[str] | None) -> tuple[dict[str, str], dict[str, str]]:
        """区分显式声明输入与仅留痕观察。

        依赖版本只取自本 attempt 内成功 observation 行；调用方不能自带哈希。
        未被声明的 observation 保留在 ``trace_only_observations``，不进入依赖、
        不参与发布对账和 finish 对账。
        """
        observed = {}
        for row in self.store.current_operations(self.action.step_id, self.action.attempt_id):
            if row["kind"] == "observation" and row["status"] == "succeeded":
                payload = row["payload"]
                observed[payload["path"]] = payload
        declared_versions = {}
        for value in declared_inputs or []:
            name = self.context.relative(value)
            if name == target:
                raise ValueError(f"显式输入不能包含写入目标自身: {name}")
            if name not in observed:
                raise ValueError(f"显式输入必须先读取: {name}")
            declared_versions[name] = observed[name]["sha256"]
        trace_only = {name: payload["sha256"] for name, payload in observed.items()
                      if name != target and name not in declared_versions}
        return declared_versions, trace_only


    def _publish_text(self, target: str, content: str, previous: bytes | None, operation: str,
                      declared_inputs: list[str] | None = None) -> dict:
        relative = self.context.relative(target)
        path = self.workspace / relative
        declared_versions, trace_only_versions = self._observed_versions(relative, declared_inputs)
        if snapshot(self.workspace, list(declared_versions)) != declared_versions:
            raise ValueError("已阅读的依据文件发生变化，请重新阅读后再写作")
        # 显式输入是锚点而非平边：递归继承其生产者谱系，读写链条仍可向上游对账。
        # 旧版本谱系用 previous 字节继续锚定，上游变化不能靠改下游洗白。
        anchors = dict(declared_versions)
        if previous is not None:
            anchors[relative] = hashlib.sha256(previous).hexdigest()
        inherited = self.context.trace_lineage(anchors, adopt=declared_versions) if anchors else {}
        # 目标是隐式输入（edit 的 previous 字节），不能作为自身的依赖边。
        inherited_inputs = {name: version for name, version in inherited.get("lineage_inputs", {}).items()
                            if name != relative}
        if inherited:
            inherited["lineage_inputs"] = inherited_inputs
        dependencies = {**inherited_inputs, **declared_versions}
        if snapshot(self.workspace, list(dependencies)) != dependencies:
            raise ValueError("已阅读的依据文件发生变化，请重新阅读后再写作")
        payload = {"path": relative, "bytes": len(content.encode("utf-8")), "operation": operation,
                   "declared_inputs": list(declared_versions),
                   "trace_only_observations": trace_only_versions,
                   "dependency_policy": "explicit-declared-inputs-v1",
                   "inputs_snapshot": dependencies, **inherited,
                   "previous_sha256": hashlib.sha256(previous).hexdigest() if previous is not None else None}
        op = self.context.begin("write", f"write:{relative}", payload)
        try:
            if (path.read_bytes() if path.is_file() else None) != previous:
                raise ValueError("文件已被另一写入者修改，请重新阅读后编辑")
            path.parent.mkdir(parents=True, exist_ok=True)
            staged = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
            with staged.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            if (path.read_bytes() if path.is_file() else None) != previous:
                raise ValueError("发布前文件已变化，保留临时产物并拒绝覆盖")
            durable_replace(staged, path)
            payload["outputs_snapshot"] = snapshot(self.workspace, [relative])
            return self.context.finish(op, "succeeded", payload)
        except Exception as exc:
            self.context.finish(op, "failed", {**payload, "error": type(exc).__name__})
            raise


    def write(self, target: str, content: str, *, inputs: list[str] | None = None) -> dict:
        path = self.workspace / self.context.relative(target)
        previous = path.read_bytes() if path.is_file() else None
        return self._publish_text(target, content, previous, "write", declared_inputs=inputs)


    def edit(self, target: str, old: str, new: str, *, inputs: list[str] | None = None) -> dict:
        """唯一精确替换：Agent只给实际修改，不手工生成指纹或重新写整篇稿件。"""
        path = self.workspace / self.context.relative(target)
        if not path.is_file() or not old or old == new:
            raise ValueError("精确编辑要求已存在文件、非空旧文本及不同的新文本")
        previous = path.read_bytes()
        text = previous.decode("utf-8")
        count = text.count(old)
        if count != 1:
            raise ValueError(f"旧文本须唯一匹配，实际{count}处；不猜测修改位置")
        return self._publish_text(target, text.replace(old, new, 1), previous, "edit",
                                  declared_inputs=inputs)
