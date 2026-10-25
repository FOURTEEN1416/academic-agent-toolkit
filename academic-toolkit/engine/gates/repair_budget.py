"""返修预算：按 (workflow, step) 跨 attempt 的轮次上限（裁决 6.5-A）。

本模块是**纯函数 + 配置读取**，不 import ``workflow_runner``、不写库、不改判定：

- ``load_policy()`` 读取 ``modex-core/checkers/repair_budget.json``；损坏即报错，
  不静默退回「不设预算」。
- ``classify_codes(codes, severity_of)`` 把一次失败轮次归入 blocking/fixable/unknown
  三档之一（advisory 只留痕，不单独占预算档）。
- ``summarize(rounds, policy, severity_of)`` 依据已落库轮次计算是否耗尽。

预算口径（台账 P2b-5，出厂启用）：

- ``blocking`` 5：总轮次上限（该 (workflow, step) 跨 attempt 合计）；
- ``fixable`` 3：可返修类失败轮次上限；
- ``unknown`` 2：检查器故障（工具缺失/异常）轮次上限；
- ``same_fingerprint`` 4：同一失败指纹最多出现 4 轮（防「无进展重复提交」）。

``enforce=true`` 时满足任一上限即 ``exhausted=True``（runner 转 FAILED +
``repair_budget_exhausted``，需 ``retry --override-reason``）；``enforce=false``
仍保留为调用方显式关闭的逃生口——此时只计数（``would_exhaust`` 记录本应阻断
的结论）。数值在 P0 账本采集到真实轮次分布（评估项 E4）后再校准。
"""
from __future__ import annotations

import json
from pathlib import Path

DEFAULT_LIMITS = {
    "blocking": 5,
    "fixable": 3,
    "unknown": 2,
    "same_fingerprint": 4,
}

from .._paths import MODEX_CORE

POLICY_PATH = MODEX_CORE / "checkers" / "repair_budget.json"

# 预算分类（advisory 轮次归入 fixable：非阻断内容问题不得无限重试）。
BUDGET_CLASSES = ("blocking", "fixable", "unknown")


class RepairBudgetConfigError(ValueError):
    """预算配置不可用（损坏/档位非法）——必须显式报错，不静默降级。"""


def _validate_policy(data: object, source: str) -> dict:
    if not isinstance(data, dict):
        raise RepairBudgetConfigError(f"repair_budget 策略必须是 JSON 对象: {source}")
    enforce = data.get("enforce", False)
    if not isinstance(enforce, bool):
        raise RepairBudgetConfigError(f"repair_budget.enforce 必须是布尔值: {source}")
    raw_limits = data.get("limits", DEFAULT_LIMITS)
    if not isinstance(raw_limits, dict):
        raise RepairBudgetConfigError(f"repair_budget.limits 必须是对象: {source}")
    limits = dict(DEFAULT_LIMITS)
    for key, value in raw_limits.items():
        if key not in DEFAULT_LIMITS:
            raise RepairBudgetConfigError(f"repair_budget.limits 含未知档位 {key!r}: {source}")
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise RepairBudgetConfigError(f"repair_budget.limits[{key!r}] 必须是正整数: {source}")
        limits[key] = value
    return {"version": int(data.get("version", 1) or 1), "enforce": enforce,
            "limits": limits, "source": source}


def load_policy(path: Path | str | None = None) -> dict:
    """读取并校验预算配置；缺文件=启用默认上限（fail-closed），损坏=报错。"""
    target = Path(path) if path is not None else POLICY_PATH
    try:
        raw = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {"version": 1, "enforce": True, "limits": dict(DEFAULT_LIMITS),
                "source": f"{target}（缺文件，按默认上限启用）"}
    except OSError as exc:
        raise RepairBudgetConfigError(f"repair_budget 配置不可读: {exc}") from None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RepairBudgetConfigError(f"repair_budget 配置不是合法 JSON: {exc}") from None
    return _validate_policy(data, str(target))


def policy_from_mapping(data: object) -> dict:
    """测试/调用方显式注入策略时走同一套校验（注入不能绕过档位/类型校验）。"""
    return _validate_policy(data, "<injected>")


def classify_codes(codes, severity_of) -> str:
    """按检查名归入预算档：任一 blocking → blocking；否则 fixable；全未知 → unknown。

    advisory 归 fixable（非阻断内容问题不得借 advisory 档无限重试）。
    ``severity_of`` 由调用方注入（runner 传 severity 注册表的 resolve 函数），
    本模块不 import quality_gates（避免与引擎检查层耦合）。
    """
    severities = {str(severity_of(str(code))) for code in codes or []}
    if "blocking" in severities:
        return "blocking"
    if "fixable" in severities or "advisory" in severities:
        return "fixable"
    return "unknown"


def summarize(rounds, policy: dict, *, severity_of) -> dict:
    """计算预算摘要。

    ``rounds`` 为已落库轮次（按 round 升序），每项至少含
    ``round`` / ``fingerprint`` / ``codes``（已解析的检查名列表）。
    当前轮次应已包含在内（先记录、后判定，轮次账实一致）。
    """
    rounds = list(rounds or [])
    limits = dict(policy.get("limits") or DEFAULT_LIMITS)
    enforce = bool(policy.get("enforce"))
    by_severity = {name: 0 for name in BUDGET_CLASSES}
    fingerprints: dict[str, int] = {}
    latest_class, latest_fingerprint = "unknown", ""
    for item in rounds:
        codes = item.get("codes")
        if codes is None:
            codes = []
        latest_class = classify_codes(codes, severity_of)
        by_severity[latest_class] = by_severity.get(latest_class, 0) + 1
        latest_fingerprint = str(item.get("fingerprint") or "")
        fingerprints[latest_fingerprint] = fingerprints.get(latest_fingerprint, 0) + 1
    total = len(rounds)
    same_fingerprint = fingerprints.get(latest_fingerprint, 0) if latest_fingerprint else 0

    reasons = []
    if total > limits["blocking"]:
        reasons.append(f"总轮次 {total} 超过上限 {limits['blocking']}")
    if by_severity.get("fixable", 0) > limits["fixable"]:
        reasons.append(f"fixable 轮次 {by_severity['fixable']} 超过上限 {limits['fixable']}")
    if by_severity.get("unknown", 0) > limits["unknown"]:
        reasons.append(f"unknown 轮次 {by_severity['unknown']} 超过上限 {limits['unknown']}")
    if same_fingerprint > limits["same_fingerprint"]:
        reasons.append(
            f"同一失败指纹出现 {same_fingerprint} 轮，超过上限 {limits['same_fingerprint']}")
    would_exhaust = bool(reasons)

    remaining_candidates = [
        limits["blocking"] - total,
        limits[latest_class] - by_severity.get(latest_class, 0),
    ]
    if latest_fingerprint:
        remaining_candidates.append(limits["same_fingerprint"] - same_fingerprint)
    remaining = max(0, min(remaining_candidates)) if rounds else limits["blocking"]

    return {
        "enforced": enforce,
        "exhausted": bool(enforce and would_exhaust),
        "would_exhaust": would_exhaust,
        "severity": latest_class,
        "total": total,
        "by_severity": by_severity,
        "same_fingerprint": same_fingerprint,
        "limits": limits,
        "remaining": remaining,
        "reasons": reasons,
    }
