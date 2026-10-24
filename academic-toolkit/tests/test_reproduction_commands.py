"""G2 §2.2.4 复现执行回归：真实子进程、冻结输入复制、payload.reproduction 对账。"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.workflow_runner import WorkflowRunner  # noqa: E402
from engine.workflow_store import WorkflowStore  # noqa: E402
from execution.context import digest  # noqa: E402
from execution.session import ExecutionSession  # noqa: E402


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def workdir():
    # 复现目录含 candidate/hash/attempt/submission 四段；Windows MAX_PATH 下
    # pytest 的深层 tmp_path 会超长，用短前缀临时目录承载真实工作区。
    path = Path(tempfile.mkdtemp(prefix="g2-repro-"))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def make_session(tmp_path, skill_name="demo"):
    skills = tmp_path / f"suite/skills/{skill_name}"
    skills.mkdir(parents=True)
    (skills / "SKILL.md").write_text("Real task instructions for the step.", encoding="utf-8")
    rules = tmp_path / "suite/engine/modex-core"
    rules.mkdir(parents=True)
    (rules / "comp_rules.json").write_text("{}", encoding="utf-8")
    store = WorkflowStore(tmp_path / "workflow.sqlite")
    catalog = {skill_name: {"sub_steps": [{
        "skill_name": skill_name, "output_files": ["result.txt"], "primary_output": "result.txt",
        "metadata": {"skill_binding": {"main_required": True}},
    }]}}
    runner = WorkflowRunner(store, catalog, tmp_path / "suite/skills", audit_root=tmp_path)
    workflow = runner.start(skill_name, tmp_path / "work", {})
    session = ExecutionSession(runner, workflow.id)
    session.context()
    return store, workflow, session


def make_candidate(store, workflow, session, *, recipe, target, target_sha,
                   inputs: dict[str, bytes]):
    inputs_json = {}
    frozen = {target: target_sha}
    for name, data in inputs.items():
        sha = _sha(data)
        inputs_json[name] = {"sha256": sha, "kind": "external",
                             "producer_operation_id": None, "depth": 1}
        frozen[name] = sha
    acceptance = {
        "reproduction_targets": [{"path": target, "sha256": target_sha,
                                  "recipe_id": "r1"}],
    }
    candidate = store.create_candidate(
        source_workflow_id=workflow.id,
        source_step_id=session.action.step_id,
        source_attempt_id=session.action.attempt_id,
        roots=[{"path": target, "sha256": target_sha}],
        inputs=inputs_json, frozen_versions=frozen, lineage={},
        recipe={"r1": recipe}, acceptance=acceptance,
        acceptance_sha256=digest(acceptance), created_by="tester",
    )
    store.bind_candidate_workflow(candidate.id, workflow.id)
    return candidate


def _plan(recipe, target, recipe_id="r1"):
    return {"candidate_id": "ignored", "targets": [
        {"target": target, "recipe_id": recipe_id,
         "spec": {**recipe, "recipe_id": recipe_id}}]}


def test_execute_reproduction_copies_inputs_runs_once_and_records_payload(workdir):
    store, workflow, session = make_session(workdir)
    raw = b"x\n1\n2\n"
    script = (b"from pathlib import Path\n"
              b"text = Path('raw.csv').read_text()\n"
              b"Path('mid.txt').write_bytes(text.upper().encode())\n")
    (session.workspace / "raw.csv").write_bytes(raw)
    (session.workspace / "solve.py").write_bytes(script)
    target_sha = _sha(b"X\n1\n2\n")
    recipe = {"argv": [sys.executable, "solve.py"], "cwd": ".",
              "inputs": ["solve.py", "raw.csv"], "outputs": ["mid.txt"], "mutates": [],
              "inputs_snapshot": {"raw.csv": _sha(raw), "solve.py": _sha(script)}}
    candidate = make_candidate(store, workflow, session, recipe=recipe,
                               target="mid.txt", target_sha=target_sha,
                               inputs={"raw.csv": raw, "solve.py": script})

    result = session.commands.execute_reproduction(_plan(recipe, "mid.txt"), candidate.id)

    assert result["ok"] is True and result["status"] == "succeeded", result
    assert result["argv_rewrite"] == "workspace-absolute-to-repro-map-v1"
    operation_id = result["recipes"][0]["operation_id"]
    row = next(row for row in store.execution_operations(session.action.step_id,
                                                         session.action.attempt_id)
               if row["id"] == operation_id)
    payload = row["payload"]
    reproduction = payload["reproduction"]
    assert payload["cacheable"] is False
    assert reproduction["candidate_id"] == candidate.id
    assert reproduction["recipe"] == recipe
    assert reproduction["recipe_sha256"] == digest(recipe)
    assert reproduction["fresh_outputs"] is True
    record = reproduction["targets"][0]
    assert record["target"] == "mid.txt"
    assert record["hash_match"] is True
    assert record["after_sha256"] == target_sha
    assert record["mapped_path"].startswith(
        f"_reproduction/{candidate.id}/{digest(recipe)}/{session.action.attempt_id}/")
    assert (session.workspace / record["mapped_path"]).read_bytes() == b"X\n1\n2\n"
    # 源工作区只读：候选根没有被复现命令改写。
    assert not (session.workspace / "mid.txt").exists()
    store.close()


def test_each_reproduction_uses_a_fresh_submission_directory(workdir):
    store, workflow, session = make_session(workdir)
    raw = b"seed"
    script = b"from pathlib import Path; Path('out.txt').write_text(Path('raw.csv').read_text() + '!')\n"
    (session.workspace / "raw.csv").write_bytes(raw)
    (session.workspace / "solve.py").write_bytes(script)
    recipe = {"argv": [sys.executable, "solve.py"], "cwd": ".",
              "inputs": ["solve.py", "raw.csv"], "outputs": ["out.txt"], "mutates": [],
              "inputs_snapshot": {"raw.csv": _sha(raw), "solve.py": _sha(script)}}
    candidate = make_candidate(store, workflow, session, recipe=recipe,
                               target="out.txt", target_sha=_sha(b"seed!"),
                               inputs={"raw.csv": raw, "solve.py": script})

    first = session.commands.execute_reproduction(_plan(recipe, "out.txt"), candidate.id)
    second = session.commands.execute_reproduction(_plan(recipe, "out.txt"), candidate.id)

    assert first["ok"] is True and second["ok"] is True
    first_path = first["recipes"][0]["targets"][0]["mapped_path"]
    second_path = second["recipes"][0]["targets"][0]["mapped_path"]
    assert first_path != second_path
    assert (session.workspace / first_path).is_file()
    assert (session.workspace / second_path).is_file()
    store.close()


def test_mutates_reproduction_requires_frozen_before_and_rejects_noop(workdir):
    store, workflow, session = make_session(workdir)
    before = b"a"
    script = b"from pathlib import Path\np = Path('data.txt'); p.write_text(p.read_text() + 'b')\n"
    noop = b"from pathlib import Path\npass\n"
    (session.workspace / "data.txt").write_bytes(before)
    (session.workspace / "solve.py").write_bytes(script)
    (session.workspace / "noop.py").write_bytes(noop)
    recipe = {"argv": [sys.executable, "solve.py"], "cwd": ".",
              "inputs": ["data.txt", "solve.py"], "outputs": ["data.txt"],
              "mutates": ["data.txt"],
              "inputs_snapshot": {"data.txt": _sha(before), "solve.py": _sha(script)}}
    candidate = make_candidate(store, workflow, session, recipe=recipe,
                               target="data.txt", target_sha=_sha(b"ab"),
                               inputs={"data.txt": before, "solve.py": script})

    result = session.commands.execute_reproduction(_plan(recipe, "data.txt"), candidate.id)

    assert result["ok"] is True, result
    record = result["recipes"][0]["targets"][0]
    assert record["before_sha256"] == _sha(before)
    assert record["after_sha256"] == _sha(b"ab")
    assert record["hash_match"] is True
    assert (session.workspace / record["mapped_path"]).read_bytes() == b"ab"

    # 同一 recipe 声明 mutates 但命令不改字节：不能冒充 fresh reproduction。
    noop_recipe = {"argv": [sys.executable, "noop.py"], "cwd": ".",
                   "inputs": ["data.txt", "noop.py"], "outputs": ["data.txt"],
                   "mutates": ["data.txt"],
                   "inputs_snapshot": {"data.txt": _sha(before), "noop.py": _sha(noop)}}
    noop_candidate = make_candidate(store, workflow, session, recipe=noop_recipe,
                                    target="data.txt", target_sha=_sha(b"ab"),
                                    inputs={"data.txt": before, "noop.py": noop})
    noop_result = session.commands.execute_reproduction(
        _plan(noop_recipe, "data.txt"), noop_candidate.id)
    assert noop_result["ok"] is False
    assert noop_result["recipes"][0]["targets"][0]["hash_match"] is False
    store.close()


def test_execute_no_cache_disables_reuse(workdir):
    store, workflow, session = make_session(workdir)
    session.files.write("input.txt", "7", inputs=[])
    spec = {"id": "copy", "argv": [sys.executable, "-c",
            "from pathlib import Path;Path('result.txt').write_text(Path('input.txt').read_text())"],
            "inputs": ["input.txt"], "outputs": ["result.txt"],
            "pure": True, "complete_inputs": True}
    first = session.commands.execute(spec)
    reused = session.commands.execute(spec)
    uncached = session.commands.execute(spec, no_cache=True)
    assert first["status"] == "succeeded"
    assert reused["status"] == "reused"
    assert uncached["status"] == "succeeded"
    assert uncached["cacheable"] is False
    assert "reused_from" not in uncached
    store.close()


def test_session_reproduce_writes_report_from_plan_file(workdir):
    store, workflow, session = make_session(workdir)
    raw = b"1\n2\n"
    script = b"from pathlib import Path; Path('sum.txt').write_text(str(sum(int(x) for x in Path('raw.csv').read_text().split())))\n"
    (session.workspace / "raw.csv").write_bytes(raw)
    (session.workspace / "solve.py").write_bytes(script)
    recipe = {"argv": [sys.executable, "solve.py"], "cwd": ".",
              "inputs": ["solve.py", "raw.csv"], "outputs": ["sum.txt"], "mutates": [],
              "inputs_snapshot": {"raw.csv": _sha(raw), "solve.py": _sha(script)}}
    candidate = make_candidate(store, workflow, session, recipe=recipe,
                               target="sum.txt", target_sha=_sha(b"3"),
                               inputs={"raw.csv": raw, "solve.py": script})
    plan_path = session.workspace / "REPRODUCTION_PLAN.json"
    plan_path.write_text(json.dumps(_plan(recipe, "sum.txt")), encoding="utf-8")

    result = session.reproduce("REPRODUCTION_PLAN.json", candidate.id)

    assert result["reproduction"]["ok"] is True, result
    report = json.loads((session.workspace / "REPRODUCTION_REPORT.json").read_text(encoding="utf-8"))
    assert report["candidate_id"] == candidate.id
    assert report["status"] == "succeeded"
    assert report["targets"][0]["hash_match"] is True
    store.close()


def test_cli_registers_inputs_abandon_and_reproduce(tmp_path):
    from engine.workflow_cli import _build_parser
    parser = _build_parser()
    write = parser.parse_args(["session", "write", "--session", "t.json", "--path", "a.txt",
                               "--stdin", "--input", "x.txt", "--input", "y.txt"])
    assert write.input == ["x.txt", "y.txt"]
    edit = parser.parse_args(["session", "edit", "--session", "t.json", "--path", "a.txt",
                              "--changes-file", "c.json", "--input", "z.txt"])
    assert edit.input == ["z.txt"]
    reproduce = parser.parse_args(["session", "reproduce", "--session", "t.json",
                                   "--plan", "REPRODUCTION_PLAN.json", "--candidate", "cand-1"])
    assert reproduce.plan == "REPRODUCTION_PLAN.json"
    assert reproduce.candidate == "cand-1"
    abandon = parser.parse_args(["session", "abandon", "--session", "t.json",
                                 "--reason", "exploratory", "--by", "operator"])
    assert abandon.reason == "exploratory" and abandon.by == "operator"
