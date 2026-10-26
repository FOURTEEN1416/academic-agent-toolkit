"""投递账本：技能正文投递与返修轮次的只读埋点（零判定变更）。

本模块只写事实，不读判定、不写步骤状态：

- ``record_delivery`` 记录一次技能正文投递。``channel`` 区分
  ``next``（workflow_cli next 注入）/ ``context``（显式 context 领取）/
  ``finish_next``（finish 推进后自动注入下一步）；``delivered`` 区分
  ``full``（完整正文）与 ``continuation``（P1 单次投递下的续接说明）。
- ``last_full_delivery`` 只读查询本 attempt 内某技能是否已投过正文，供 P1
  判定「本次只发续接说明」。
- ``record_validation_round`` 记录一次 needs_work 返修轮次：round 在
  ``BEGIN IMMEDIATE`` 事务内分配（该 (workflow, step) 已有行数 + 1 后同事务
  INSERT），UNIQUE 冲突时事务内重分配；只计数，不改 status、不推进 attempt、
  不伪造 checkpoint。

用法（P0 只读埋点，不改验收判定）：

- 表结构由 ``WorkflowStore._initialize`` 建表（additive，旧库自动迁移）；
- 调用方负责把自身错误收口——埋点失败不得击穿 context()/finish 主链路；
- 本模块不 import ``workflow_runner``（无判定耦合）。
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

# 投递来源：next=workflow_cli next 注入；context=显式 context；finish_next=finish 后的下一步注入。
# channel 与 delivered 正交：channel 记来源，delivered 记本次投的是正文还是续接说明。
DELIVERY_CHANNELS = ("next", "context", "finish_next")

# delivered 取值：full=完整正文；continuation=本 attempt 内已投过正文，本次只投续接说明
# （P1 单次投递，出厂关闭；开启后同一 attempt 的后续 context() 不再重发正文）。
DELIVERY_MODES = ("full", "continuation")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_delivery(store, workflow_id: str, step_id: str, attempt_id: str, channel: str,
                    name: str, sha256: str, bytes: int, delivered: str,
                    operation_id: str) -> int:
    """追加一行技能正文投递记录，返回本 attempt 内该技能的「第几次投递」。

    序号口径：同一 (workflow_id, step_id, attempt_id, name) 的已投递行数 + 1，
    因此 retry 换了 attempt_id 后自动从 1 重计。分配与插入在同一个
    ``BEGIN IMMEDIATE`` 事务内完成，多个连接并发时由写锁串行化。
    """
    if channel not in DELIVERY_CHANNELS:
        raise ValueError(f"unknown delivery channel: {channel!r}")
    if delivered not in DELIVERY_MODES:
        raise ValueError(f"unknown delivery mode: {delivered!r}")
    with store._lock:
        connection = store._connection
        try:
            connection.execute("BEGIN IMMEDIATE")
            prior = connection.execute(
                "SELECT COUNT(*) FROM context_deliveries WHERE workflow_id=? AND step_id=? "
                "AND attempt_id=? AND name=?",
                (workflow_id, step_id, attempt_id, name)).fetchone()[0]
            ordinal = int(prior) + 1
            connection.execute(
                "INSERT INTO context_deliveries (id, workflow_id, step_id, attempt_id, channel, "
                "name, sha256, bytes, delivered, delivery_ordinal, operation_id, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (str(uuid4()), workflow_id, step_id, attempt_id, channel, str(name),
                 str(sha256), int(bytes), str(delivered), ordinal, str(operation_id), _now()))
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    return ordinal


def last_full_delivery(store, workflow_id: str, step_id: str, attempt_id: str,
                       name: str) -> dict | None:
    """查本 attempt 内某技能的首次全量投递；无记录（含旧库缺表/读取失败）返回 None。

    只读查询，不写库、不改判定。返回 ``name/sha256/bytes/operation_id``：正文的身份
    （sha256/bytes）与首次读取操作号，供 P1 续接说明引用「仍然有效的那份正文」。
    无记录时调用方按现状全量投递——埋点失败不会导致正文被省略。
    """
    try:
        row = store._connection.execute(
            "SELECT name, sha256, bytes, operation_id FROM context_deliveries "
            "WHERE workflow_id=? AND step_id=? AND attempt_id=? AND name=? AND delivered='full' "
            "ORDER BY rowid LIMIT 1",
            (workflow_id, step_id, attempt_id, str(name))).fetchone()
    except sqlite3.Error:
        return None
    if row is None:
        return None
    return {"name": str(row["name"]), "sha256": str(row["sha256"]),
            "bytes": int(row["bytes"]), "operation_id": str(row["operation_id"])}


def record_validation_round(store, workflow_id: str, step_id: str, attempt_id: str,
                            report: dict) -> int:
    """追加一行 needs_work 返修轮次，返回分配的 round 号。

    ``codes`` = 本次失败检查名（只取稳定检查名，不掺 reason/字节数，保证同一
    失败集合指纹稳定）；``fingerprint`` = 排序后检查名的 sha256。
    """
    checks = report.get("checks") if isinstance(report, dict) else {}
    checks = checks if isinstance(checks, dict) else {}
    codes = sorted(str(name) for name, check in checks.items()
                   if not (isinstance(check, dict) and check.get("ok") is True))
    fingerprint = hashlib.sha256("|".join(codes).encode("utf-8")).hexdigest()
    codes_json = json.dumps(codes, ensure_ascii=True, sort_keys=True)
    with store._lock:
        connection = store._connection
        # BEGIN IMMEDIATE 已串行化写入；循环仅兜底「round 不连续」等 UNIQUE 冲突
        # （冲突时回滚重分配，不丢轮次、不重号）。
        for _ in range(8):
            try:
                connection.execute("BEGIN IMMEDIATE")
                existing = connection.execute(
                    "SELECT COUNT(*) FROM step_validation_rounds "
                    "WHERE workflow_id=? AND step_id=?",
                    (workflow_id, step_id)).fetchone()[0]
                round_number = int(existing) + 1
                connection.execute(
                    "INSERT INTO step_validation_rounds (workflow_id, step_id, attempt_id, round, "
                    "fingerprint, codes_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (workflow_id, step_id, attempt_id, round_number, fingerprint,
                     codes_json, _now()))
                connection.commit()
                return round_number
            except sqlite3.IntegrityError:
                connection.rollback()
                continue
            except Exception:
                connection.rollback()
                raise
    raise sqlite3.IntegrityError("step_validation_rounds 轮次分配重试耗尽")
