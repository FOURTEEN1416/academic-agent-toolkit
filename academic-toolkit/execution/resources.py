"""技能/资产发现与真实读取；候选与语义贡献分别对待。"""
from __future__ import annotations
import hashlib
import json

class ResourceCatalog:
    def __init__(self, context):
        self.context = context
        self.action = context.action
        self.skills_root = self.action.skill_path.parents[1]
        self.repo = context.repo

    def read_resource(self, name: str, kind: str = "skill", member: str = "") -> dict:
        if kind == "skill":
            base = (self.skills_root / name / "SKILL.md").resolve()
            if not base.is_relative_to(self.skills_root.resolve()):
                raise ValueError("技能路径越界")
            path = base
        elif kind == "asset":
            assets = {str(a["name"]): a for a in self.action.assets}
            if name not in assets:
                ledger = self.skills_root.parent / "data/asset_catalog.json"
                catalog = json.loads(ledger.read_text(encoding="utf-8")) if ledger.is_file() else {}
                registered = next((a for a in catalog.get("assets", []) if a.get("id") == name), None)
                if registered is None:
                    raise ValueError("资产不在步骤清单或真实资产台账中")
                assets[name] = registered
            base = (self.repo / assets[name]["path"]).resolve()
            path = (base / member).resolve() if member else base
            if not base.is_relative_to(self.repo) or not path.is_relative_to(base if base.is_dir() else base.parent):
                raise ValueError("资产路径越界")
        else:
            raise ValueError("resource kind 必须为 skill 或 asset")
        if not path.is_file():
            raise ValueError(f"请指定实际文件而非目录: {path}")
        raw = path.read_bytes()
        if len(raw) > 256_000:
            raise ValueError("资源超过上下文预算，请通过任务工具提取需要的段落，不整包灌入")
        text = raw.decode("utf-8-sig")
        record = {"kind": kind, "name": name, "path": str(path),
                  "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
                  "observation": "content_returned_to_executor"}
        op = self.context.begin("resource", f"resource:{kind}:{name}:{path}", record)
        self.context.finish(op, "succeeded", record)
        return {**record, "content": text, "operation_id": op}


    def resources(self, query: str = "") -> dict:
        """只读完整索引，不读取全库正文；词法候选由执行者作最终语义选择。"""
        from tools.skill_trigger_audit import route
        index_path = self.skills_root.parent / "data/skill_routing_index.json"
        entries = json.loads(index_path.read_text(encoding="utf-8")).get("skills", {}) if index_path.is_file() else {}
        records = {name: {"description": entry.get("full_description", "")}
                   for name, entry in entries.items()
                   if (self.skills_root / name / "SKILL.md").is_file()}
        hits = route(query, records=records, top_k=3) if query else []
        names = list(dict.fromkeys([*self.action.companion_skills, *(h["skill"] for h in hits)]))
        asset_index = self.skills_root.parent / "data/asset_catalog.json"
        ledger = json.loads(asset_index.read_text(encoding="utf-8")) if asset_index.is_file() else {}
        from tools.skill_trigger_audit import route_tokens
        terms = route_tokens(query)
        suggested = []
        for asset in ledger.get("assets", []):
            text = str(asset.get("description", "")) + " " + str(asset.get("when_to_use", ""))
            overlap = terms & route_tokens(text)
            owner = self.action.skill_name in asset.get("owner_skills", [])
            if owner or overlap:
                suggested.append({"id": asset["id"], "path": asset["path"],
                    "purpose": asset.get("when_to_use", ""), "score": len(overlap) + (10 if owner else 0),
                    "available": (self.repo / asset["path"]).exists()})
        suggested.sort(key=lambda a: (-a["score"], a["id"]))
        return {"mandatory": self.action.skill_binding.get("mandatory", []),
                "candidates": [{"skill": n, "description": records.get(n, {}).get("description", ""),
                                "source": "step_contract" if n in self.action.companion_skills else "task_query"}
                               for n in names],
                "assets": [{**a, "available": (self.repo / a.get("path", "")).exists()} for a in self.action.assets],
                "asset_candidates": suggested[:3],
                "selection_boundary": "候选不是使用证明；主技能/必用技能正文随context提供，其他按需read"}
