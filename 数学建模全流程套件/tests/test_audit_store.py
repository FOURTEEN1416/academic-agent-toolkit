"""审计系统测试：AuditStore 读写、报告生成、未申报操作检测（防绕过）。"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.audit_store import (
    AuditStore,
    audit_log_path,
    default_audit_dir,
    detect_unreported_operations,
    generate_audit_report,
    official_logger_paths,
    write_audit_report,
)


def _make_audit(project_root: Path) -> AuditStore:
    store = AuditStore(project_root)
    store.record({"type": "tool_call", "event": "before", "tool": "bash", "sessionID": "s1",
                  "detail": {"command": "python code/main.py"}})
    store.record({"type": "tool_result", "event": "after", "tool": "bash", "sessionID": "s1",
                  "ok": True, "resultSummary": "exit 0"})
    store.record({"type": "tool_call", "event": "before", "tool": "edit", "sessionID": "s1",
                  "detail": {"filePath": "RESULTS.md", "oldLen": 10, "newLen": 20}})
    store.record({"type": "tool_call", "event": "before", "tool": "skill", "sessionID": "s1",
                  "detail": {"skillName": "comp-modeling"}})
    store.record({"type": "file_edit", "event": "file.edited", "detail": "{}"})
    store.record({"type": "session", "event": "session.created", "sessionID": "s1"})
    return store


def test_audit_store_records_and_reads(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    store = _make_audit(project_root)

    events = store.events()
    assert len(events) == 6
    assert store.tool_calls() and len(store.tool_calls()) == 3
    assert store.tool_results() and len(store.tool_results()) == 1
    assert len(store.file_edits()) == 1
    assert len(store.sessions()) == 1
    assert audit_log_path(project_root).exists()


def test_audit_store_stats(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    store = _make_audit(project_root)

    stats = store.stats()
    assert stats["total_events"] == 6
    assert stats["tool_calls"] == 3
    assert stats["bash_commands"] == ["python code/main.py"]
    assert stats["edit_targets"] == ["RESULTS.md"]
    assert stats["skill_usage"] == {"comp-modeling": 1}
    assert stats["failed_tool_calls"] == 0
    assert stats["first_event"] is not None


def test_audit_store_handles_corrupt_lines(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    path = audit_log_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"ts": "2026-01-01", "type": "ok"}\nNOT_JSON\n', encoding="utf-8")

    store = AuditStore(project_root)
    events = store.events()
    assert len(events) == 2
    assert events[1]["type"] == "corrupt_line"


def test_detect_unreported_bash_commands(tmp_path):
    """防绕过：审计日志有但 evidence 未申报的命令 → warning。"""
    project_root = tmp_path / "project"
    workspace = tmp_path / "ws"
    project_root.mkdir()
    workspace.mkdir()

    # 审计日志记录了一个命令
    store = AuditStore(project_root)
    store.record({"type": "tool_call", "tool": "bash", "detail": {"command": "python hack.py"}})
    # evidence 里申报了另一个命令
    ev_dir = workspace / ".engine" / "evidence"
    ev_dir.mkdir(parents=True)
    (ev_dir / "step1.json").write_text(json.dumps({
        "evidence": {"commands": [{"command": "python legit.py"}], "outputs": ["out.md"], "inputs": []},
    }), encoding="utf-8")

    result = detect_unreported_operations(workspace, project_root)
    assert result["verdict"] == "warning"
    assert "python hack.py" in result["unreported_bash"]


def test_detect_unreported_edits(tmp_path):
    """防绕过：编辑了未申报的文件 → warning。"""
    project_root = tmp_path / "project"
    workspace = tmp_path / "ws"
    project_root.mkdir()
    workspace.mkdir()

    store = AuditStore(project_root)
    store.record({"type": "tool_call", "tool": "edit", "detail": {"filePath": "SECRET.md"}})
    ev_dir = workspace / ".engine" / "evidence"
    ev_dir.mkdir(parents=True)
    (ev_dir / "step1.json").write_text(json.dumps({
        "evidence": {"commands": [], "outputs": ["out.md"], "inputs": []},
    }), encoding="utf-8")

    result = detect_unreported_operations(workspace, project_root)
    assert result["verdict"] == "warning"
    assert "SECRET.md" in result["unreported_edit_targets"]


def test_detect_reports_ok_when_all_declared(tmp_path):
    """全部操作都申报 → ok。"""
    project_root = tmp_path / "project"
    workspace = tmp_path / "ws"
    project_root.mkdir()
    workspace.mkdir()

    store = AuditStore(project_root)
    store.record({"type": "tool_call", "tool": "bash", "detail": {"command": "python code/main.py"}})
    ev_dir = workspace / ".engine" / "evidence"
    ev_dir.mkdir(parents=True)
    (ev_dir / "step1.json").write_text(json.dumps({
        "evidence": {"commands": [{"command": "python code/main.py"}], "outputs": ["out.md"], "inputs": []},
    }), encoding="utf-8")

    result = detect_unreported_operations(workspace, project_root)
    assert result["verdict"] == "ok"


def test_generate_and_write_audit_report(tmp_path):
    """报告生成：包含 stats/workflow/evidence/未申报检测。"""
    project_root = tmp_path / "project"
    workspace = tmp_path / "ws"
    project_root.mkdir()
    workspace.mkdir()
    _make_audit(project_root)
    ev_dir = workspace / ".engine" / "evidence"
    ev_dir.mkdir(parents=True)
    (ev_dir / "step1.json").write_text(json.dumps({
        "evidence": {"skill_name": "comp-code", "agent": "test", "commands": [{"command": "python code/main.py"}],
                     "outputs": [], "inputs": []},
    }), encoding="utf-8")

    report = generate_audit_report(workspace, project_root)
    assert report["stats"]["total_events"] >= 6
    assert len(report["evidence_files"]) == 1
    assert report["overall"]["audit_trail_present"] is True
    assert "unreported_operations" in report

    out = write_audit_report(workspace, project_root)
    assert out.exists()
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["stats"]["total_events"] >= 6


def test_official_logger_paths_and_events(tmp_path):
    """官方 opencode-logger 输出（log.jsonl + 轮转）可被审计报告读取。"""
    project_root = tmp_path / "project"
    project_root.mkdir()
    audit_dir = default_audit_dir(project_root)
    audit_dir.mkdir(parents=True)
    # 模拟官方 logger 输出（eventType 格式）
    (audit_dir / "log.jsonl").write_text(
        json.dumps({"timestamp": "2026-01-01T00:00:00Z", "eventType": "tool.execute.before",
                    "payload": {"tool": "bash"}}) + "\n" +
        json.dumps({"timestamp": "2026-01-01T00:00:01Z", "eventType": "file.edited",
                    "payload": {"path": "a.md"}}) + "\n",
        encoding="utf-8",
    )

    paths = official_logger_paths(project_root)
    assert len(paths) == 1
    store = AuditStore(project_root)
    events = store.official_events()
    assert len(events) == 2
    assert events[0]["eventType"] == "tool.execute.before"

    report = generate_audit_report(tmp_path / "ws" if False else project_root, project_root)
    assert report["official_logger_events"] == 2
