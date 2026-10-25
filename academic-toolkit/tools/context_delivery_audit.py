#!/usr/bin/env python3
"""投递账本只读审计：技能读取分布、通道分布与 retry 归因。

用法：
  python academic-toolkit/tools/context_delivery_audit.py <workspace 目录 或 .engine/workflow.sqlite>

只以 ``file:...?mode=ro`` URI 打开，绝不写库（运行前后 DB mtime 不变）。

输出（JSON）：
- ``skill_reads`` / ``bytes`` / ``unique_skills`` / ``max_per_attempt``：来自
  ``execution_operations`` 中 ``kind=resource`` 且 ``payload.kind=skill`` 的纯读取
  统计（不依赖归因逻辑，可用于历史库）；
- ``attempts[]``：每次 attempt 的技能读取次数/字节/技能集合/通道分布；
- ``channel_distribution``：有 ``context_deliveries`` 账本行的 attempt 取实记
  channel（next/context/finish_next）；无账本行的历史 attempt 按「该 attempt
  首个技能读取前最近的 ``step_retry`` 事件」归因为 ``retry_then_context``，
  否则记为 ``context``（历史默认路径）；
- ``dedup_projection``：按 ``(workflow, step, attempt, skill, sha256)`` 去重后的
  读取数与字节（proxy 投影，不是真实投递次数）。

验收边界（显式）：历史库 ``execution_operations`` 无 channel 字段，且 needs_work
历史不落 ``step_retry`` 事件——channel 分布与 retry 归因只对 P0 上线后的新链数据
可信，历史数据仅为 proxy。
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


def _resolve_db(target: str | Path) -> Path:
    path = Path(target)
    if path.is_dir():
        path = path / ".engine" / "workflow.sqlite"
    return path


def _open_read_only(db_path: Path) -> sqlite3.Connection:
    """只读打开：mode=ro URI，物理上不可能写库。"""
    uri = db_path.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _table_exists(connection: sqlite3.Connection, name: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def _load_skill_reads(connection: sqlite3.Connection) -> list[dict]:
    """技能读取事实：resource 操作里 payload.kind == skill。"""
    rows = connection.execute(
        "SELECT workflow_id, step_id, attempt_id, payload, created_at "
        "FROM execution_operations WHERE kind='resource' ORDER BY created_at, rowid").fetchall()
    reads = []
    for row in rows:
        try:
            payload = json.loads(row["payload"])
        except (TypeError, ValueError):
            continue
        if not isinstance(payload, dict) or payload.get("kind") != "skill":
            continue
        reads.append({
            "workflow_id": row["workflow_id"], "step_id": row["step_id"],
            "attempt_id": row["attempt_id"], "name": str(payload.get("name", "")),
            "sha256": str(payload.get("sha256", "")),
            "bytes": int(payload.get("bytes") or 0),
            "created_at": str(row["created_at"]),
        })
    return reads


def _load_step_retries(connection: sqlite3.Connection) -> list[dict]:
    """step_retry 事件（payload 里带 step_id 时按其限定步骤）。"""
    if not _table_exists(connection, "events"):
        return []
    rows = connection.execute(
        "SELECT workflow_id, payload, created_at FROM events WHERE event_type='step_retry' "
        "ORDER BY created_at, rowid").fetchall()
    retries = []
    for row in rows:
        try:
            payload = json.loads(row["payload"])
        except (TypeError, ValueError):
            payload = {}
        retries.append({
            "workflow_id": row["workflow_id"],
            "step_id": str((payload or {}).get("step_id") or ""),
            "created_at": str(row["created_at"]),
        })
    return retries


def _load_recorded_deliveries(connection: sqlite3.Connection) -> dict[tuple, list[dict]]:
    """context_deliveries 实记通道（新链数据）；旧库无该表时返回空。"""
    recorded: dict[tuple, list[dict]] = {}
    if not _table_exists(connection, "context_deliveries"):
        return recorded
    rows = connection.execute(
        "SELECT workflow_id, step_id, attempt_id, channel, name, bytes, delivery_ordinal "
        "FROM context_deliveries ORDER BY created_at, rowid").fetchall()
    for row in rows:
        key = (row["workflow_id"], row["step_id"], row["attempt_id"])
        recorded.setdefault(key, []).append(dict(row))
    return recorded


def _retried_before(retries: list[dict], workflow_id: str, step_id: str,
                    first_read_at: str) -> bool:
    """该 attempt 首个技能读取前是否存在同工作流（同步骤）的 step_retry 事件。"""
    hits = [retry for retry in retries
            if retry["workflow_id"] == workflow_id
            and (not retry["step_id"] or retry["step_id"] == step_id)
            and retry["created_at"] <= first_read_at]
    return bool(hits)


def audit(target: str | Path) -> dict:
    """只读审计一个 workspace 的投递账本投影。"""
    db_path = _resolve_db(target)
    if not db_path.is_file():
        raise FileNotFoundError(f"workflow database not found: {db_path}")
    connection = _open_read_only(db_path)
    try:
        reads = _load_skill_reads(connection)
        retries = _load_step_retries(connection)
        recorded = _load_recorded_deliveries(connection)
    finally:
        connection.close()

    grouped: dict[tuple, list[dict]] = {}
    for read in reads:
        grouped.setdefault(
            (read["workflow_id"], read["step_id"], read["attempt_id"]), []).append(read)

    attempts: list[dict] = []
    channel_distribution: dict[str, int] = {}
    for key in sorted(grouped):
        workflow_id, step_id, attempt_id = key
        items = grouped[key]
        first_read_at = min(item["created_at"] for item in items)
        recorded_rows = recorded.get(key, [])
        if recorded_rows:
            channels: dict[str, int] = {}
            for row in recorded_rows:
                channel = str(row["channel"])
                channels[channel] = channels.get(channel, 0) + 1
            attribution = "recorded"
        else:
            attribution = ("retry_then_context"
                           if _retried_before(retries, workflow_id, step_id, first_read_at)
                           else "context")
            channels = {attribution: len(items)}
        for channel, count in channels.items():
            channel_distribution[channel] = channel_distribution.get(channel, 0) + int(count)
        attempts.append({
            "workflow_id": workflow_id, "step_id": step_id, "attempt_id": attempt_id,
            "skill_reads": len(items),
            "bytes": sum(item["bytes"] for item in items),
            "skills": sorted({item["name"] for item in items}),
            "channels": channels,
            "attribution": attribution,
        })

    dedup: dict[tuple, int] = {}
    for read in reads:
        dedup[(read["workflow_id"], read["step_id"], read["attempt_id"],
               read["name"], read["sha256"])] = read["bytes"]

    return {
        "database": str(db_path),
        "skill_reads": len(reads),
        "bytes": sum(read["bytes"] for read in reads),
        "unique_skills": len({read["name"] for read in reads}),
        "max_per_attempt": max((attempt["skill_reads"] for attempt in attempts), default=0),
        "attempts": attempts,
        "channel_distribution": {channel: count for channel, count in channel_distribution.items()
                                 if count},
        "dedup_projection": {"reads": len(dedup), "bytes": sum(dedup.values())},
        "attribution_note": (
            "历史库 execution_operations 无 channel 字段、needs_work 历史不落 step_retry "
            "事件：channel 分布与 retry_then_context 归因只对 P0 上线后的新链数据可信，"
            "历史数据为 proxy 投影。"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="投递账本只读审计（mode=ro，绝不写库）")
    parser.add_argument("target", help="workspace 目录或其 .engine/workflow.sqlite 路径")
    args = parser.parse_args(argv)
    try:
        result = audit(args.target)
    except (OSError, sqlite3.Error) as exc:
        print(f"审计失败: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
