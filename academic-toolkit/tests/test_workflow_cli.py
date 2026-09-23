import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import workflow_cli
from engine.workflow_store import WorkflowStore


def test_caps_reports_independent_runtime_capabilities(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["workflow_cli", "caps"])

    assert workflow_cli.main() == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["source"] in {"suite_runtime", "PATH"}
    assert "guidance" in payload


def test_report_writes_persisted_sqlite_timeline(tmp_path, monkeypatch, capsys):
    db = tmp_path / "workflow.sqlite"
    with WorkflowStore(db) as store:
        workflow = store.create_workflow("demo")
        step = store.add_steps(workflow.id, [{"name": "demo"}])[0]
        store.create_checkpoint(workflow.id, step.id, {"status": "completed"}, event={"type": "step_completed"})
    output = tmp_path / "timeline.json"
    monkeypatch.setattr(sys, "argv", ["workflow_cli", "report", "--wf", workflow.id, "--db", str(db), "--out", str(output)])

    assert workflow_cli.main() == 0

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["workflow"]["id"] == workflow.id
    assert payload["events"][0]["type"] == "step_completed"
    assert capsys.readouterr().out
