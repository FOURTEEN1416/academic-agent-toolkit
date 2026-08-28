"""运行日志与审计报告测试"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.run_logger import RunLogger


def test_logger_records_events(tmp_path):
    logger = RunLogger(tmp_path / "logs")
    logger.log("wf-1", "s-1", "prob-analysis", "started", "开始分析")
    logger.log("wf-1", "s-1", "prob-analysis", "completed", "分析完成", output_size=1500)
    assert len(logger._entries) == 2
    assert logger._entries[0].event == "started"
    assert logger._entries[1].metadata["output_size"] == 1500


def test_logger_saves_to_file(tmp_path):
    logger = RunLogger(tmp_path / "logs")
    logger.log("wf-1", "s-1", "prob-analysis", "started")
    path = logger.save("wf-1")
    assert path.exists()
    import json
    data = json.loads(path.read_text(encoding="utf-8"))
    assert len(data) == 1
    assert data[0]["workflow_id"] == "wf-1"


def test_generate_report(tmp_path):
    logger = RunLogger(tmp_path / "logs")
    logger.log("wf-1", "s-1", "prob-analysis", "started")
    logger.log("wf-1", "s-1", "prob-analysis", "completed")
    logger.log("wf-1", "s-2", "modeling", "started")
    logger.log("wf-1", "s-2", "modeling", "checkpoint", "等待审批")
    report = logger.generate_report("wf-1", "测试工作流", {"ok": True})
    assert report["workflow_name"] == "测试工作流"
    assert report["steps_completed"] == 1
    assert report["checkpoints"] == 1
    assert report["quality_gates"]["ok"] is True