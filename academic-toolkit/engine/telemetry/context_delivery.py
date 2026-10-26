"""P1 技能正文单次投递：开关读取 + 续接说明文案（出厂关闭）。

裁决 6.1 门控前提：机制先落地，**出厂默认关闭**。开关写在
``modex-core/checkers/context_delivery.json`` 的 ``single_delivery``：

- ``false``（出厂值）：``ExecutionSession.context()`` 每次仍全量重读并投递正文，
  默认路径与 P0 现状逐字节等价；
- ``true``：同一 attempt 内同一技能只在首次投递正文，后续 ``context()`` 改发续接
  说明——参照 Modex ``_continuation_prompt`` 语义：声明首条消息里的技能说明仍然
  有效、本次不再重发。

配置放进 ``checkers/`` 子目录而非 modex-core 根：根下 ``glob("*.json")`` 会进
legacy 合同/候选 acceptance 哈希，新增根级 json 会静默改变哈希面。

配置缺失/不可读/非法时一律按出厂关闭处理（fail-open 到现状）：单次投递尚未通过
V4 宿主 A/B，任何配置问题都不得把未验证的行为静默打开。返回值的 ``status`` 字段
保留诊断信息，调用方无需处理。
"""
from __future__ import annotations

import json
from pathlib import Path

from .._paths import MODEX_CORE

POLICY_PATH = MODEX_CORE / "checkers" / "context_delivery.json"

# 出厂默认：关闭。缺省值必须与 P0 现状一致。
DEFAULT_POLICY = {"version": 1, "single_delivery": False}

# 续接说明的稳定前缀（测试与人工排查都按它识别）。
CONTINUATION_PREFIX = "【技能正文续接说明】"


def policy_from_mapping(data: object) -> dict:
    """校验配置对象；类型非法抛 ValueError（由 load_policy 收敛为出厂关闭）。"""
    if not isinstance(data, dict):
        raise ValueError("context_delivery 策略必须是 JSON 对象")
    version = data.get("version", 1)
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise ValueError("context_delivery.version 必须是正整数")
    single_delivery = data.get("single_delivery", False)
    if not isinstance(single_delivery, bool):
        raise ValueError("context_delivery.single_delivery 必须是布尔值")
    return {"version": version, "single_delivery": single_delivery}


def load_policy(path: Path | str | None = None) -> dict:
    """读取开关配置；任何异常都收敛为出厂关闭（附 status 供诊断）。"""
    target = Path(path) if path is not None else POLICY_PATH
    try:
        raw = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {**DEFAULT_POLICY, "status": "missing", "source": str(target)}
    except OSError:
        return {**DEFAULT_POLICY, "status": "unreadable", "source": str(target)}
    except UnicodeDecodeError:
        return {**DEFAULT_POLICY, "status": "invalid", "source": str(target)}
    try:
        polished = policy_from_mapping(json.loads(raw))
    except (json.JSONDecodeError, ValueError):
        return {**DEFAULT_POLICY, "status": "invalid", "source": str(target)}
    return {**polished, "status": "ok", "source": str(target)}


def single_delivery_enabled(policy: dict | None = None) -> bool:
    """单次投递是否开启；显式传入已加载策略时不再读盘。"""
    current = policy if isinstance(policy, dict) else load_policy()
    return current.get("single_delivery") is True


def continuation_notice(name: str, sha256: str, skill_bytes: int) -> str:
    """同一 attempt 后续投递的续接说明：正文仍然有效，本次不重发。"""
    digest = str(sha256 or "")[:12]
    return (f"{CONTINUATION_PREFIX}技能 `{name}` 的完整正文已在本 attempt 的首条消息中投递"
            f"（sha256={digest}…，{int(skill_bytes)} B），该说明仍然有效，本次不再重复投递。"
            "请按已收到的正文继续执行；如确需核对原文，用 read 重新读取该技能。")
