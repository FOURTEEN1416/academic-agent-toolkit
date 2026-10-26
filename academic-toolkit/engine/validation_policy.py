"""P2b-2 接收者判定（裁决 6.3-A 附带条件 / 整改台账 P2b-2）。

`fixable` 检查失败只有在链上存在**消费方**时才允许降级为可返修
（``needs_work`` + 返修预算）；否则保持 ``blocking``（FAILED），避免
「无接收者的链」把 fixable 当隐式可返修而静默放水。

判定只依据模板/工作流静态结构 + 交付报告，不做运行时猜测：

① 当前步骤或链后续存在带 ``final_audit`` 检查的步骤（步骤名
   ``comp-final-audit``、``required_checks`` 含 ``final_audit``，或产出
   ``AUDIT_REPORT.json``）；
② 交付报告 ``DELIVERY_REPORT.json`` 的 ``open_items`` 存在人工签署项；
③ 当前步骤或链后续存在 ``comp-final-review`` 步骤（该步骤的 ``review``
   检查强制 full 模式，见 quality_gates.run_all）。

三者皆无（如 ``paper_writing`` 以 ``auto-paper-improvement-loop`` 收尾）→
fixable 保持 blocking。

本模块是纯函数 + 只读文件：不 import ``workflow_runner``、不写库、不改判定。
runner 的 finish 判定与终审报告的汇总共用本判定，保证两处口径一致。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from ._paths import MODEX_CORE

FINAL_AUDIT_STEP = "comp-final-audit"
FINAL_REVIEW_STEP = "comp-final-review"
FINAL_AUDIT_CHECK = "final_audit"
FINAL_AUDIT_OUTPUT = "AUDIT_REPORT.json"
DELIVERY_REPORT_NAME = "DELIVERY_REPORT.json"

# 交付报告 open_item 的签署字段（P2b-4 accept-open-item 会写入 signed_by）。
# 兼容 accepted_by / signed=true 的显式布尔写法。
_SIGNED_BY_FIELDS = ("signed_by", "accepted_by")


def _field(value: Any, key: str, default: Any = None) -> Any:
    """同时读取 dataclass/对象属性与 dict 键。"""
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _step_name(step: Any) -> str:
    # 模板 resolve 结果用 skill_name，落库步骤用 name。
    name = _field(step, "name")
    if name is None:
        name = _field(step, "skill_name")
    return str(name or "")


def _step_metadata(step: Any) -> dict[str, Any]:
    metadata = _field(step, "metadata", {})
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except (TypeError, ValueError):
            metadata = {}
    return metadata if isinstance(metadata, dict) else {}


def _step_checks(step: Any) -> list[str]:
    """步骤声明的 required_checks（metadata 内优先，模板 resolve 顶层也认）。"""
    metadata = _step_metadata(step)
    checks = metadata.get("required_checks")
    if checks is None:
        checks = _field(step, "required_checks", [])
    return [str(name) for name in (checks or [])]


def _step_outputs(step: Any) -> list[str]:
    metadata = _step_metadata(step)
    outputs = metadata.get("output_files")
    if outputs is None:
        outputs = _field(step, "output_files", [])
    return [str(name) for name in (outputs or [])]


def _step_position(step: Any, fallback: int) -> int:
    raw = _field(step, "position", fallback)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return fallback


def _is_final_audit_step(step: Any) -> bool:
    return (_step_name(step) == FINAL_AUDIT_STEP
            or FINAL_AUDIT_CHECK in _step_checks(step)
            or FINAL_AUDIT_OUTPUT in _step_outputs(step))


def _is_final_review_step(step: Any) -> bool:
    # comp-final-review 的 review 检查在 run_all 中强制 full 模式；
    # 判定只认步骤名，不读运行时产物（台账：不做运行时猜测）。
    return _step_name(step) == FINAL_REVIEW_STEP


def _template_steps(workflow: Any) -> list[dict[str, Any]]:
    """静态回退：按 workflow.name + params 解析 templates.json。

    仅当调用方未提供实际步骤且 workflow 本身不带 steps 时使用；解析失败
    返回空列表（保守：宁可不认接收者，也不把无接收者的链误判为可返修）。
    """
    name = str(_field(workflow, "name", "") or "")
    metadata = _field(workflow, "metadata", {})
    metadata = metadata if isinstance(metadata, dict) else {}
    params = metadata.get("params") if isinstance(metadata.get("params"), dict) else {}
    if not name:
        return []
    try:
        from .contracts.template_resolver import resolve_template
        catalog = json.loads((MODEX_CORE / "templates.json").read_text(encoding="utf-8"))
        resolved = resolve_template(name, params or {}, catalog)
    except Exception:
        return []
    return [{"name": step.get("skill_name"), "position": index, **step}
            for index, step in enumerate(resolved)]


def workflow_steps_of(workflow: Any, steps: Iterable[Any] | None = None) -> list[Any]:
    """取工作流步骤：显式入参 > workflow.steps > templates.json 静态解析。"""
    if steps is not None:
        return list(steps)
    workflow_steps = _field(workflow, "steps", None)
    if workflow_steps:
        return list(workflow_steps)
    return _template_steps(workflow)


def _current_index(steps: list[Any], step: Any) -> int | None:
    """定位当前步骤下标；优先 id，其次 name，最后位置。"""
    step_id = str(_field(step, "id", "") or "")
    if step_id:
        for index, candidate in enumerate(steps):
            if str(_field(candidate, "id", "") or "") == step_id:
                return index
    name = _step_name(step)
    if name:
        for index, candidate in enumerate(steps):
            if _step_name(candidate) == name:
                return index
    if isinstance(step, str):
        for index, candidate in enumerate(steps):
            if _step_name(candidate) == step:
                return index
    raw_position = _field(step, "position", None)
    if raw_position is not None:
        try:
            target = int(raw_position)
        except (TypeError, ValueError):
            target = None
        if target is not None:
            for index, candidate in enumerate(steps):
                if _step_position(candidate, index) == target:
                    return index
    return None


def _steps_at_or_after(steps: list[Any], step: Any) -> list[Any]:
    """当前步骤及其后续步骤（括号内判定口径，台账写「链后续」）。

    当前步骤自身若已是终审/终审复核环节，它同样消费本步的 fixable 问题，
    因此包含当前步骤；匹配不到当前步骤时返回空列表（保守，不误判接收者）。
    """
    index = _current_index(steps, step)
    if index is None:
        return []
    current = _step_position(steps[index], index)
    return [candidate for position, candidate in enumerate(steps)
            if _step_position(candidate, position) >= current]


def delivery_report_paths(workspace: Path | str | None, workflow_id: str = "") -> list[Path]:
    """交付报告候选路径：workflow-scoped 优先，根目录次之（与审计写出顺序一致）。"""
    if workspace is None:
        return []
    workspace = Path(workspace)
    paths: list[Path] = []
    if workflow_id:
        paths.append(workspace / "reports" / workflow_id / DELIVERY_REPORT_NAME)
    paths.append(workspace / DELIVERY_REPORT_NAME)
    return paths


def _is_signed(item: dict[str, Any]) -> bool:
    if item.get("signed") is True:
        return True
    return any(str(item.get(field) or "").strip() for field in _SIGNED_BY_FIELDS)


def signed_open_items(workspace: Path | str | None, workflow_id: str = "") -> list[dict[str, Any]]:
    """读取交付报告中已人工签署的 open_items（additive，只读）。

    多份报告按 workflow-scoped → 根目录顺序取第一份含 open_items 的；
    未找到/损坏一律返回空列表（= 无签署，fixable 不降级——fail-closed）。
    """
    for path in delivery_report_paths(workspace, workflow_id):
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            continue
        if not isinstance(data, dict):
            continue
        items = data.get("open_items")
        if not isinstance(items, list):
            continue
        return [dict(item) for item in items
                if isinstance(item, dict) and _is_signed(item)]
    return []


def receiver_of(workflow: Any, step: Any = None, *, steps: Iterable[Any] | None = None,
                workspace: Path | str | None = None,
                delivery_report: dict[str, Any] | None = None) -> dict[str, Any]:
    """显式接收者判定（台账 P2b-2）。

    参数：
      workflow          Workflow dataclass / dict（需 name；可选 metadata/steps）
      step              当前步骤；None 表示「整条链」（终审报告汇总口径）
      steps             实际步骤列表（WorkflowStep 或 dict）；优先于 workflow.steps
      workspace         工作区根（读 DELIVERY_REPORT.json）；缺省取 metadata.workspace
      delivery_report   已读入的交付报告（避免重复读盘）

    返回 ``{has_receiver, receivers, final_audit, signed_open_items,
    final_review_full_gate, reason}``。无接收者时 reason 说明三条判定均未命中。
    """
    workflow_steps = workflow_steps_of(workflow, steps)
    if step is None:
        relevant = list(workflow_steps)
    else:
        relevant = _steps_at_or_after(workflow_steps, step)

    final_audit_steps = [_step_name(item) for item in relevant if _is_final_audit_step(item)]
    final_review_steps = [_step_name(item) for item in relevant if _is_final_review_step(item)]

    if workspace is None:
        metadata = _field(workflow, "metadata", {})
        metadata = metadata if isinstance(metadata, dict) else {}
        workspace = metadata.get("workspace")
    workflow_id = str(_field(workflow, "id", "") or "")
    if delivery_report is not None:
        raw_items = delivery_report.get("open_items") if isinstance(delivery_report, dict) else None
        signed = [dict(item) for item in (raw_items or [])
                  if isinstance(item, dict) and _is_signed(item)]
    else:
        signed = signed_open_items(workspace, workflow_id)

    receivers: list[str] = []
    if final_audit_steps:
        receivers.append("final_audit:" + ",".join(dict.fromkeys(final_audit_steps)))
    if signed:
        receivers.append(f"signed_open_items:{len(signed)}")
    if final_review_steps:
        receivers.append("final_review_full_gate:" + ",".join(dict.fromkeys(final_review_steps)))

    has_receiver = bool(receivers)
    reason = "" if has_receiver else (
        "链上无接收者：当前步骤及其后续既无 final_audit 检查步骤，也无 "
        "comp-final-review full gate，交付报告 open_items 也没有人工签署；"
        "fixable 保持 blocking（不得降级为可返修）")
    return {
        "has_receiver": has_receiver,
        "receivers": receivers,
        "final_audit": {"ok": bool(final_audit_steps), "steps": final_audit_steps},
        "signed_open_items": {"ok": bool(signed), "count": len(signed),
                              "checks": [str(item.get("check") or "") for item in signed]},
        "final_review_full_gate": {"ok": bool(final_review_steps), "steps": final_review_steps},
        "reason": reason,
    }
