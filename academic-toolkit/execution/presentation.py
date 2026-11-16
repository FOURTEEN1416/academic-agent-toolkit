"""只呈现任务结果与待解决问题，不向模型堆叠机器账本。"""

# ENG-3 高频打回消息码化：三类高频失败（技能绑定缺咨询痕迹、execution evidence
# 字段不合规、outputs 与声明不符）+ 两个同类申报门禁，用户视图压缩为
# 「错误码 + 一行原因 + 修复示例」；完整教学文案仍保留在 diagnostics.checks.*.reason
# 与 step_failed 事件 payload 供程序读取（只裁剪展示面，不改判定）。
# 顺序敏感：具体申报类前缀先于通用 "invalid execution evidence" 匹配。
_FAILURE_CODES = (
    ("技能绑定不合规", "EVIDENCE_BINDING",
     "执行时真实读取绑定技能 SKILL.md 并把该命令记入 evidence.commands"),
    ("辅助技能申报不合规", "EVIDENCE_COMPANION",
     '按 {"used": [...], "skipped": [{"skill": ..., "reason": ...}]} 恰好覆盖推荐清单'),
    ("步骤资产申报不合规", "EVIDENCE_ASSETS",
     '按 {"used": [...], "skipped": [{"name": ..., "reason": ...}]} 恰好覆盖资产清单'),
    ("declared outputs validation", "OUTPUTS_MISMATCH",
     "让 finish 的 artifacts 与步骤声明 output_files 完全一致（缺则补产，多则修正声明）"),
    ("invalid execution evidence", "EVIDENCE_INVALID",
     "按 next 返回的 evidence_template 照抄结构；commands 填真实执行的命令"),
)


def _one_line(reason: str, limit: int = 120) -> str:
    """取原因首段做一行摘要：剥掉「invalid execution evidence: XX不合规——」前缀，
    在句号/分号处截断，超长再截断。"""
    flat = " ".join(str(reason or "").split())
    if "——" in flat:
        flat = flat.split("——", 1)[1]
    for sep in ("。", "；"):
        idx = flat.find(sep)
        if idx > 0:
            flat = flat[:idx]
            break
    return flat[:limit] + ("…" if len(flat) > limit else "")


def coded_reason(reason: str) -> str:
    """把高频打回的长教学文案压缩为「错误码 + 一行原因 + 修复示例」短消息。

    未命中任何错误码的 reason 原样返回（低频失败不强行归类）。
    """
    text = str(reason or "")
    for marker, code, fix in _FAILURE_CODES:
        if marker in text:
            return f"[{code}] {_one_line(text)}｜修复：{fix}（完整原因见 diagnostics）"
    return text


def user_view(result: dict) -> dict:
    """默认只向模型展示任务、结果与待修问题；hash/返回码/事实账留在程序内部。"""
    if "documents" in result:
        return {**result, "documents": [{"name": r["name"], "content": r["content"]}
                                         for r in result["documents"]]}
    if "content" in result and "sha256" in result:
        return {"name": result["name"], "kind": result["kind"], "content": result["content"]}
    if result.get("status") == "executed" or "failed_node" in result:
        view = {k: result[k] for k in ("status", "executed", "reused", "failed_node") if k in result}
        view["operations"] = [{k: operation[k] for k in
            ("node", "status", "declared_outputs", "duration_seconds", "stdout", "stderr", "error")
            if k in operation} for operation in result.get("operations", [])]
        if "completion" in result:
            view["completion"] = user_view(result["completion"])
        return view
    if "workflow_id" in result and "status" in result:
        view = {k: result[k] for k in ("status", "message", "checkpoint_id", "replayed")
                if result.get(k) is not None}
        checks = result.get("diagnostics", {}).get("checks", {})
        view["issues"] = [{"check": k, "reason": coded_reason(v.get("reason", ""))}
                          for k, v in checks.items() if v.get("ok") is not True]
        delivery = result.get("diagnostics", {}).get("delivery")
        if delivery:
            view["delivery"] = delivery
        for key in ("next", "machine_audit"):
            if key in result:
                view[key] = user_view(result[key])
        return view
    if "outputs_snapshot" in result and "operation_id" in result:
        return {"status": result["status"], "outputs": list(result["outputs_snapshot"])}
    return result
