"""工作流运行日志与审计报告生成"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class RunLogEntry:
    timestamp: str
    workflow_id: str
    step_id: str | None
    step_name: str | None
    event: str  # started | advanced | checkpoint | retry | failed | completed
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class RunLogger:
    """记录工作流运行日志并生成审计报告"""

    def __init__(self, log_dir: str | Path):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._entries: list[RunLogEntry] = []

    def log(self, workflow_id: str, step_id: str | None, step_name: str | None,
            event: str, message: str = "", **metadata) -> RunLogEntry:
        entry = RunLogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            workflow_id=workflow_id,
            step_id=step_id,
            step_name=step_name,
            event=event,
            message=message,
            metadata=metadata,
        )
        self._entries.append(entry)
        return entry

    def save(self, workflow_id: str, filename: str | None = None) -> Path:
        """保存运行日志到文件。

        filename 为空时使用时间戳命名（保留多份历史）；显式传入时覆盖同
        workflow 的日志（审计文件位置确定，便于门禁/报告定位）。
        """
        name = filename or f"run_{workflow_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        path = self.log_dir / name
        path.write_text(
            json.dumps([asdict(e) for e in self._entries], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def generate_report(self, workflow_id: str, workflow_name: str,
                        gates_result: dict | None = None) -> dict:
        """生成审计报告"""
        steps = [e for e in self._entries if e.workflow_id == workflow_id]
        completed = [e for e in steps if e.event == "completed"]
        failed = [e for e in steps if e.event == "failed"]
        retries = [e for e in steps if e.event == "retry"]
        checkpoints = [e for e in steps if e.event == "checkpoint"]
        return {
            "workflow_id": workflow_id,
            "workflow_name": workflow_name,
            "total_events": len(steps),
            "steps_completed": len(completed),
            "steps_failed": len(failed),
            "retries": len(retries),
            "checkpoints": len(checkpoints),
            "quality_gates": gates_result or {},
            "timeline": [asdict(e) for e in steps],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="工作流运行日志记录")
    sub = parser.add_subparsers(dest="cmd")

    report = sub.add_parser("report", help="生成目录中所有运行的报告")
    report.add_argument("log_dir", help="日志目录")
    report.add_argument("out", help="报告输出 JSON 路径")

    args = parser.parse_args()

    if args.cmd == "report":
        log_dir = Path(args.log_dir)
        if not log_dir.is_dir():
            print(f"日志目录不存在: {log_dir}")
            raise SystemExit(1)
        summaries = []
        for f in sorted(log_dir.glob("run_*.json")):
            data = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(data, list):
                summaries.append({
                    "file": f.name,
                    "events": len(data),
                    "events_by_type": {e.get("event"): data.count(e) for e in data} if False else _count_by(data, "event"),
                })
        Path(args.out).write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"已生成报告: {args.out} ({len(summaries)} 个运行)")
    else:
        parser.print_help()


def _count_by(entries: list[dict], key: str) -> dict:
    from collections import Counter
    return dict(Counter(e.get(key, "") for e in entries))