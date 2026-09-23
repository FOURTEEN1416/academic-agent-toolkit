"""批次三机制补强：B3-1 RunLogger 落盘链路 / B3-2 workflow-index 原子写与回退 / B3-3 CLI 错误契约。

B3-1 关键断言走 CLI 子进程（真实每命令一进程路径），其余按既有测试惯例 in-process。
索引与数据库一律落 tmp_path，不污染仓库根 .engine/。
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

TOOLBOX = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLBOX))

from engine import workflow_cli
from engine.workflow_store import WorkflowStore


def _cli(*argv, timeout=180):
    """真实子进程驱动 CLI（每命令一进程，与生产驱动路径一致）。"""
    return subprocess.run(
        [sys.executable, "-m", "engine.workflow_cli", *argv],
        cwd=str(TOOLBOX), capture_output=True, text=True, timeout=timeout,
    )


def _start_in_tmp(tmp_path, monkeypatch, capsys=None):
    """in-process 启动 auto_review 工作流（db 与索引均在 tmp），返回 (workflow_id, db)。"""
    registry = tmp_path / "workflow-index.json"
    monkeypatch.setattr(workflow_cli, "WORKFLOW_INDEX", registry)
    db = tmp_path / "ws" / ".engine" / "workflow.sqlite"
    monkeypatch.setattr(sys, "argv", [
        "workflow_cli", "start", "--template", "auto_review",
        "--workspace", str(tmp_path / "ws"), "--db", str(db),
    ])
    assert workflow_cli.main() == 0
    if capsys is not None:
        capsys.readouterr()  # 消费 start 输出，避免污染后续断言
    workflow_id = json.loads(registry.read_text(encoding="utf-8"))
    (workflow_id,) = list(workflow_id)
    return workflow_id, db


def _run_log(workspace: Path, workflow_id: str) -> list[dict]:
    path = workspace / ".engine" / "logs" / f"run_{workflow_id}.json"
    assert path.is_file(), f"运行日志未落盘: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


# ---------- B3-1 RunLogger 落盘链路 ----------

def test_start_persists_run_log_via_subprocess(tmp_path):
    """B3-1 验收口径：tmp workspace 走 CLI 子进程，断言 run_*.json 真落盘且非空。"""
    workspace = tmp_path / "ws"
    registry = TOOLBOX / ".engine" / "workflow-index.json"
    existed_before = registry.is_file()
    payload = None
    try:
        proc = _cli("start", "--template", "auto_review", "--workspace", str(workspace))
        assert proc.returncode == 0, proc.stdout + proc.stderr
        payload = json.loads(proc.stdout)
        entries = _run_log(workspace, payload["workflow_id"])
        assert entries, "运行日志为空"
        assert entries[0]["event"] == "started"
        assert entries[0]["workflow_id"] == payload["workflow_id"]
    finally:
        # 共享索引只清本测试写入的键：删后为空且文件是本测试创建的 → 删文件恢复"索引缺失"常态
        if registry.is_file():
            try:
                data = json.loads(registry.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                data = {}
            if payload:
                data.pop(payload.get("workflow_id"), None)
            if data:
                registry.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            elif not existed_before:
                registry.unlink()


def test_next_merges_existing_events_and_persists(tmp_path, monkeypatch):
    """B3-1：next 命令重建 RunLogger，合并既有 started 事件而非覆盖。"""
    workflow_id, db = _start_in_tmp(tmp_path, monkeypatch)
    workspace = tmp_path / "ws"
    monkeypatch.setattr(sys, "argv", [
        "workflow_cli", "next", "--wf", workflow_id, "--db", str(db),
    ])
    assert workflow_cli.main() == 0

    entries = _run_log(workspace, workflow_id)
    events = [e["event"] for e in entries]
    assert events[0] == "started", "既有事件被覆盖，合并逻辑失效"
    assert "started" in events[1:], "next 未记录步骤开始事件"


def test_complete_failure_persists_run_log(tmp_path, monkeypatch):
    """B3-1：complete（含失败路径）也落盘；此前该路径 logger 恒 None。"""
    workflow_id, db = _start_in_tmp(tmp_path, monkeypatch)
    workspace = tmp_path / "ws"
    monkeypatch.setattr(sys, "argv", [
        "workflow_cli", "next", "--wf", workflow_id, "--db", str(db),
    ])
    assert workflow_cli.main() == 0
    monkeypatch.setattr(sys, "argv", [
        "workflow_cli", "complete", "--wf", workflow_id, "--db", str(db),
        "--ok", "false", "--stderr", "batch3 test failure",
    ])
    assert workflow_cli.main() == 1

    entries = _run_log(workspace, workflow_id)
    assert any(e["event"] == "failed" for e in entries)


# ---------- B3-2 workflow-index 原子写 + 回退 ----------

def test_register_uses_atomic_write_and_leaves_no_tmp(tmp_path, monkeypatch):
    registry = tmp_path / "workflow-index.json"
    monkeypatch.setattr(workflow_cli, "WORKFLOW_INDEX", registry)
    database = tmp_path / "w.sqlite"
    WorkflowStore(database).close()

    workflow_cli.register_workflow_database("wf-a", database)

    assert json.loads(registry.read_text(encoding="utf-8"))["wf-a"] == str(database.resolve())
    assert not list(tmp_path.glob("*.tmp")), "原子写残留临时文件"


def test_prune_workflow_index_removes_orphans(tmp_path, monkeypatch):
    registry = tmp_path / "workflow-index.json"
    monkeypatch.setattr(workflow_cli, "WORKFLOW_INDEX", registry)
    alive = tmp_path / "alive.sqlite"
    WorkflowStore(alive).close()
    workflow_cli.register_workflow_database("wf-alive", alive)
    workflow_cli.register_workflow_database("wf-orphan", tmp_path / "gone.sqlite")

    pruned = workflow_cli.prune_workflow_index()

    assert pruned == ["wf-orphan"]
    index = json.loads(registry.read_text(encoding="utf-8"))
    assert "wf-orphan" not in index and "wf-alive" in index


def test_probe_workflow_db_recovers_from_missing_index(tmp_path, monkeypatch):
    """B3-2：索引缺失时按位置约定扫描各工作区库，命中唯一库即回退。"""
    fake_root = tmp_path / "repo"
    db = fake_root / "workspaces" / "ws-a" / ".engine" / "workflow.sqlite"
    db.parent.mkdir(parents=True)
    with WorkflowStore(db) as store:
        workflow = store.create_workflow("auto_review")
        workflow_id = workflow.id
    monkeypatch.setattr(workflow_cli, "ROOT", fake_root)

    assert workflow_cli._probe_workflow_db(workflow_id) == db
    assert workflow_cli._probe_workflow_db("wf-never-exists") is None


def test_unknown_wf_without_fallback_returns_json_error(tmp_path, monkeypatch, capsys):
    """B3-2/B3-3：回退探测也未命中 → JSON 错误契约 + 退出码 2（原为 argparse usage 文本）。"""
    fake_root = tmp_path / "repo"
    (fake_root / "workspaces").mkdir(parents=True)
    monkeypatch.setattr(workflow_cli, "ROOT", fake_root)
    monkeypatch.setattr(workflow_cli, "WORKFLOW_INDEX", tmp_path / "missing-index.json")
    monkeypatch.setattr(sys, "argv", ["workflow_cli", "next", "--wf", "wf-ghost"])

    assert workflow_cli.main() == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "error"
    assert "wf-ghost" in payload["message"]


def test_resolve_explicit_db_survives_after_probe_fallback(tmp_path, monkeypatch):
    """探测命中后回写索引，后续命令不再重复扫描。"""
    registry = tmp_path / "workflow-index.json"
    fake_root = tmp_path / "repo"
    db = fake_root / "workspaces" / "ws-a" / ".engine" / "workflow.sqlite"
    db.parent.mkdir(parents=True)
    with WorkflowStore(db) as store:
        workflow_id = store.create_workflow("auto_review").id
    monkeypatch.setattr(workflow_cli, "ROOT", fake_root)
    monkeypatch.setattr(workflow_cli, "WORKFLOW_INDEX", registry)

    db_found = workflow_cli._probe_workflow_db(workflow_id)
    assert db_found is not None
    workflow_cli.register_workflow_database(workflow_id, db_found)

    assert workflow_cli.resolve_workflow_db(workflow_id) == db.resolve()


# ---------- B3-3 CLI 错误契约 + --evidence-file ----------

def test_bad_params_json_returns_error_contract(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", [
        "workflow_cli", "start", "--template", "auto_review",
        "--workspace", str(tmp_path / "ws"), "--params", "{not-json",
    ])

    assert workflow_cli.main() == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "error"
    assert "--params" in payload["message"]


def test_complete_evidence_file_is_read(tmp_path, monkeypatch, capsys):
    """--evidence-file 合法 JSON 应被读取并走完 complete（--ok false 时无需 schema 校验）。"""
    workflow_id, db = _start_in_tmp(tmp_path, monkeypatch, capsys)
    workspace = tmp_path / "ws"
    monkeypatch.setattr(sys, "argv", [
        "workflow_cli", "next", "--wf", workflow_id, "--db", str(db),
    ])
    assert workflow_cli.main() == 0
    capsys.readouterr()  # 消费 next 输出

    evidence_file = tmp_path / "evidence.json"
    evidence_file.write_text(json.dumps({"schema_version": 1, "agent": "batch3-test"}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [
        "workflow_cli", "complete", "--wf", workflow_id, "--db", str(db),
        "--ok", "false", "--evidence-file", str(evidence_file),
    ])
    assert workflow_cli.main() == 1  # failed 是业务结果（ok=false），不是解析失败
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"

    entries = _run_log(workspace, workflow_id)
    assert any(e["event"] == "failed" for e in entries)


def test_complete_evidence_file_invalid_json_rejected(tmp_path, monkeypatch, capsys):
    workflow_id, db = _start_in_tmp(tmp_path, monkeypatch, capsys)
    bad = tmp_path / "bad.json"
    bad.write_text("{oops", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [
        "workflow_cli", "complete", "--wf", workflow_id, "--db", str(db),
        "--ok", "true", "--evidence-file", str(bad),
    ])

    assert workflow_cli.main() == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "error"
    assert "--evidence-file" in payload["message"]


def test_complete_evidence_and_file_mutually_exclusive(tmp_path, monkeypatch, capsys):
    workflow_id, db = _start_in_tmp(tmp_path, monkeypatch, capsys)
    evidence_file = tmp_path / "evidence.json"
    evidence_file.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [
        "workflow_cli", "complete", "--wf", workflow_id, "--db", str(db),
        "--evidence", '{"schema_version": 1}', "--evidence-file", str(evidence_file),
    ])

    assert workflow_cli.main() == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "error"


def test_forge_gap_file_invalid_json_rejected(tmp_path, monkeypatch, capsys):
    bad = tmp_path / "gap.json"
    bad.write_text("nope", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [
        "workflow_cli", "forge", "--evidence-file", str(bad),
    ])

    assert workflow_cli.main() == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "error"


def test_complete_help_contains_evidence_example(capsys, monkeypatch):
    """B3-3：--help 补最小可用 evidence 示例（缓解 Windows 引号地狱）。"""
    monkeypatch.setattr(sys, "argv", ["workflow_cli", "complete", "--help"])
    with pytest.raises(SystemExit) as exc_info:
        workflow_cli.main()
    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert "--evidence-file" in out
    assert "schema_version" in out
    assert "skill_sha256" in out


def test_approve_requires_by_teaching_error(tmp_path, monkeypatch, capsys):
    """approve --by 缺失：保持 argparse 教学式报错契约（test_workflow_retry_cli 锁定，
    stderr + exit 2）；JSON 错误契约不覆盖用法错误。"""
    db = tmp_path / "ws" / ".engine" / "workflow.sqlite"
    db.parent.mkdir(parents=True)
    WorkflowStore(db).close()
    monkeypatch.setattr(sys, "argv", [
        "workflow_cli", "approve", "--checkpoint", "cp-none", "--db", str(db),
    ])

    with pytest.raises(SystemExit) as exc_info:
        workflow_cli.main()
    assert exc_info.value.code == 2
    err = capsys.readouterr().err
    assert "--by" in err
    assert "批准人" in err


def test_unknown_checkpoint_json_contract(tmp_path, monkeypatch, capsys):
    registry = tmp_path / "workflow-index.json"
    monkeypatch.setattr(workflow_cli, "WORKFLOW_INDEX", registry)
    monkeypatch.setattr(sys, "argv", [
        "workflow_cli", "approve", "--checkpoint", "cp-ghost", "--by", "reviewer",
    ])

    assert workflow_cli.main() == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "error"


def test_audit_prunes_orphan_registrations(tmp_path, monkeypatch, capsys):
    """B3-2：audit 命令顺带清理孤儿注册。"""
    registry = tmp_path / "workflow-index.json"
    monkeypatch.setattr(workflow_cli, "WORKFLOW_INDEX", registry)
    workflow_cli.register_workflow_database("wf-orphan", tmp_path / "gone.sqlite")
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / ".engine").mkdir()
    WorkflowStore(workspace / ".engine" / "workflow.sqlite").close()
    monkeypatch.setattr(sys, "argv", [
        "workflow_cli", "audit", "--workspace", str(workspace),
    ])

    assert workflow_cli.main() == 0
    out = capsys.readouterr().out
    assert "wf-orphan" in out
    assert json.loads(registry.read_text(encoding="utf-8")) == {}
