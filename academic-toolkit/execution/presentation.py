"""只呈现任务结果与待解决问题，不向模型堆叠机器账本。"""
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
        view["issues"] = [{"check": k, "reason": v.get("reason", "")}
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
