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
                   "bytes": len(raw), "observation": "workspace_content_returned"}
        op = self.context.begin("observation", f"observation:{relative}", payload)
        self.context.finish(op, "succeeded", payload)
        return {"name": relative, "kind": "workspace", "content": text, **payload}


    def _publish_text(self, target: str, content: str, previous: bytes | None, operation: str) -> dict:
        relative = self.context.relative(target)
        path = self.workspace / relative
        reads = [r["payload"] for r in self.store.current_operations(
            self.action.step_id, self.action.attempt_id) if r["kind"] == "observation" and r["status"] == "succeeded"]
        dependencies = {r["path"]: r["sha256"] for r in reads if r["path"] != relative}
        # 重新阅读过的版本显式采纳：新写作以当前阅读为基础接续谱系；
        # 未重新阅读时继承旧版本链，上游变化会阻断发布，不能靠改下游洗白。
        inherited = (self.context.trace_lineage({relative: hashlib.sha256(previous).hexdigest()},
                                                adopt=dependencies) if previous is not None else {})
        dependencies = {**inherited.get("lineage_inputs", {}), **dependencies}
        if snapshot(self.workspace, list(dependencies)) != dependencies:
            raise ValueError("已阅读的依据文件发生变化，请重新阅读后再写作")
        payload = {"path": relative, "bytes": len(content.encode("utf-8")), "operation": operation,
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


    def write(self, target: str, content: str) -> dict:
        path = self.workspace / self.context.relative(target)
        previous = path.read_bytes() if path.is_file() else None
        return self._publish_text(target, content, previous, "write")


    def edit(self, target: str, old: str, new: str) -> dict:
        """唯一精确替换：Agent只给实际修改，不手工生成指纹或重新写整篇稿件。"""
        path = self.workspace / self.context.relative(target)
        if not path.is_file() or not old or old == new:
            raise ValueError("精确编辑要求已存在文件、非空旧文本及不同的新文本")
        previous = path.read_bytes()
        text = previous.decode("utf-8")
        count = text.count(old)
        if count != 1:
            raise ValueError(f"旧文本须唯一匹配，实际{count}处；不猜测修改位置")
        return self._publish_text(target, text.replace(old, new, 1), previous, "edit")
