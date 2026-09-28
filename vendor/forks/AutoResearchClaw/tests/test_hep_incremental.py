"""Tests for hep-ph mid-stage HITL + incremental Stage 12 re-entry."""

from __future__ import annotations

import json

import pytest

from researchclaw.config import ColliderAgentConfig


def test_collider_agent_config_has_incremental_field_default_false():
    cfg = ColliderAgentConfig()
    assert hasattr(cfg, "incremental")
    assert cfg.incremental is False


def test_collider_agent_config_incremental_can_be_enabled():
    cfg = ColliderAgentConfig(incremental=True)
    assert cfg.incremental is True


def test_run_subparser_accepts_incremental_experiment_flag():
    """The 'researchclaw run --incremental-experiment' flag must parse."""
    from researchclaw.cli import build_parser

    parser = build_parser()
    args = parser.parse_args([
        "run",
        "--config", "config.yaml",
        "--incremental-experiment",
    ])
    assert getattr(args, "incremental_experiment") is True


def test_run_subparser_incremental_experiment_default_false():
    from researchclaw.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["run", "--config", "config.yaml"])
    assert getattr(args, "incremental_experiment") is False


# ---------------------------------------------------------------------------
# Task 3: profile-aware gate_required + CODE_GENERATION rollback
# ---------------------------------------------------------------------------


def test_gate_required_returns_true_for_code_generation_when_profile_is_hep_ph():
    from researchclaw.pipeline.stages import Stage, gate_required

    assert gate_required(Stage.CODE_GENERATION, profile="hep_ph") is True


def test_gate_required_returns_false_for_code_generation_without_profile():
    from researchclaw.pipeline.stages import Stage, gate_required

    assert gate_required(Stage.CODE_GENERATION) is False
    assert gate_required(Stage.CODE_GENERATION, profile=None) is False
    assert gate_required(Stage.CODE_GENERATION, profile="ml_tabular") is False


def test_gate_required_unaffected_for_existing_gates_when_profile_is_passed():
    from researchclaw.pipeline.stages import Stage, gate_required

    assert gate_required(Stage.LITERATURE_SCREEN, profile="hep_ph") is True
    assert gate_required(Stage.LITERATURE_SCREEN, profile="ml_tabular") is True
    assert gate_required(Stage.EXPERIMENT_DESIGN, profile=None) is True


def test_default_rollback_for_code_generation_is_experiment_design():
    from researchclaw.pipeline.stages import Stage, default_rollback_stage

    assert default_rollback_stage(Stage.CODE_GENERATION) is Stage.EXPERIMENT_DESIGN


# ---------------------------------------------------------------------------
# Task 4: collider_output_files alternate on CODE_GENERATION contract
# ---------------------------------------------------------------------------


def test_code_generation_contract_has_collider_alternate_output():
    from researchclaw.pipeline.contracts import CONTRACTS
    from researchclaw.pipeline.stages import Stage

    contract = CONTRACTS[Stage.CODE_GENERATION]
    # Default ML output unchanged
    assert "experiment/" in contract.output_files
    # New: collider-mode alternate
    assert hasattr(contract, "collider_output_files")
    assert contract.collider_output_files == ("collider_plan.md",)


# ---------------------------------------------------------------------------
# Task 5: _select_output_files + executor profile threading
# ---------------------------------------------------------------------------


def _make_rc_config(tmp_path, *, profile="", mode="sandbox"):
    """Build a minimal RCConfig for executor tests."""
    from researchclaw.config import RCConfig

    data = {
        "project": {"name": "rc-test", "mode": "docs-first", "profile": profile},
        "research": {
            "topic": "test",
            "domains": ["ml"],
            "daily_paper_count": 1,
            "quality_threshold": 7.0,
        },
        "runtime": {"timezone": "UTC"},
        "notifications": {
            "channel": "local",
            "on_stage_start": False,
            "on_stage_fail": False,
            "on_gate_required": False,
        },
        "knowledge_base": {"backend": "markdown", "root": str(tmp_path / "kb")},
        "openclaw_bridge": {"use_memory": False, "use_message": False},
        "llm": {
            "provider": "openai-compatible",
            "base_url": "http://localhost:1234/v1",
            "api_key_env": "RC_TEST_KEY",
            "api_key": "inline-test-key",
            "primary_model": "fake-model",
            "fallback_models": [],
        },
        "security": {"hitl_required_stages": []},
        "experiment": {"mode": mode},
    }
    return RCConfig.from_dict(data, project_root=tmp_path, check_paths=False)


def test_select_output_files_picks_collider_mode_alternate(tmp_path):
    from researchclaw.pipeline.contracts import CONTRACTS
    from researchclaw.pipeline.executor import _select_output_files
    from researchclaw.pipeline.stages import Stage

    cfg = _make_rc_config(tmp_path, mode="collider_agent")
    contract = CONTRACTS[Stage.CODE_GENERATION]
    files = _select_output_files(contract, cfg)
    assert files == ("collider_plan.md",)


def test_select_output_files_keeps_default_for_non_collider_mode(tmp_path):
    from researchclaw.pipeline.contracts import CONTRACTS
    from researchclaw.pipeline.executor import _select_output_files
    from researchclaw.pipeline.stages import Stage

    cfg = _make_rc_config(tmp_path, mode="sandbox")
    contract = CONTRACTS[Stage.CODE_GENERATION]
    files = _select_output_files(contract, cfg)
    assert "experiment/" in files
    assert "collider_plan.md" not in files


def test_select_output_files_handles_none_contract():
    from researchclaw.pipeline.executor import _select_output_files

    assert _select_output_files(None, None) == ()


def test_executor_treats_code_generation_as_gate_for_hep_ph(tmp_path, monkeypatch):
    """When profile='hep_ph' and auto_approve_gates=False, Stage 10 yields BLOCKED_APPROVAL."""
    from researchclaw.adapters import AdapterBundle
    from researchclaw.pipeline import executor as exec_mod
    from researchclaw.pipeline._helpers import StageResult
    from researchclaw.pipeline.stages import Stage, StageStatus

    cfg = _make_rc_config(tmp_path, profile="hep_ph", mode="collider_agent")

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    # Required upstream input for Stage 10
    s09 = run_dir / "stage-09"
    s09.mkdir()
    (s09 / "exp_plan.yaml").write_text("plan: stub", encoding="utf-8")

    def _stub_codegen(stage_dir, run_dir, config, adapters, *args, **kwargs):
        # Stub creates the contract's collider output so validation passes
        (stage_dir / "collider_plan.md").write_text("# stub plan\n", encoding="utf-8")
        return StageResult(
            stage=Stage.CODE_GENERATION,
            status=StageStatus.DONE,
            artifacts=("collider_plan.md",),
            evidence_refs=("stage-10/collider_plan.md",),
        )

    monkeypatch.setitem(exec_mod._STAGE_EXECUTORS, Stage.CODE_GENERATION, _stub_codegen)

    adapters = AdapterBundle()
    result = exec_mod.execute_stage(
        Stage.CODE_GENERATION,
        run_dir=run_dir,
        run_id="test-run",
        config=cfg,
        adapters=adapters,
        auto_approve_gates=False,
    )
    assert result.status == StageStatus.BLOCKED_APPROVAL


# ---------------------------------------------------------------------------
# Task 11: disk-guard WARN for cumulative footprint
# ---------------------------------------------------------------------------


def test_incremental_snapshot_warns_when_cumulative_footprint_exceeds_threshold(
    tmp_path, monkeypatch, caplog
):
    """When sum(stage-12*) > 20 GB, log a WARN but do not abort."""
    import logging
    from dataclasses import replace

    from researchclaw.adapters import AdapterBundle
    from researchclaw.experiment import collider_agent_sandbox as ca_mod
    from researchclaw.experiment.sandbox import SandboxResult
    from researchclaw.pipeline.stage_impls import _execution as exec_mod

    run_dir = tmp_path / "r"
    s12 = run_dir / "stage-12"
    s12.mkdir(parents=True)
    runs = s12 / "runs"
    runs.mkdir()
    workspace = runs / "collider_workspace"
    workspace.mkdir()
    (workspace / "models").mkdir()
    (workspace / "models" / "x").mkdir()
    (workspace / "events").mkdir()
    (workspace / "events" / "x").mkdir()

    monkeypatch.setattr(
        exec_mod,
        "_estimate_stage12_footprint_bytes",
        lambda _r: 21 * 1024 * 1024 * 1024,
    )
    monkeypatch.setattr(
        ca_mod.ColliderAgentSandbox, "run",
        lambda self, prompt, timeout_sec=None: SandboxResult(
            returncode=0, stdout="", stderr="", elapsed_sec=0.0, metrics={}, timed_out=False,
        ),
    )

    (run_dir / "stage-09").mkdir()
    (run_dir / "stage-09" / "exp_plan.yaml").write_text("x: 1", encoding="utf-8")
    (run_dir / "stage-10").mkdir()
    (run_dir / "stage-10" / "collider_plan.md").write_text("# delta\n", encoding="utf-8")
    (run_dir / "stage-11").mkdir()
    (run_dir / "stage-11" / "schedule.json").write_text("{}", encoding="utf-8")

    cfg = _make_rc_config(tmp_path, profile="hep_ph", mode="collider_agent")
    cfg = replace(cfg, experiment=replace(
        cfg.experiment,
        collider_agent=replace(cfg.experiment.collider_agent, incremental=True),
    ))

    with caplog.at_level(logging.WARNING, logger=exec_mod.logger.name):
        _ = exec_mod._execute_experiment_run(
            stage_dir=s12, run_dir=run_dir, config=cfg, adapters=AdapterBundle()
        )

    assert any("incremental footprint" in r.message.lower() for r in caplog.records)


def test_estimate_stage12_footprint_bytes_sums_all_versions(tmp_path):
    from researchclaw.pipeline.stage_impls._execution import _estimate_stage12_footprint_bytes

    s12 = tmp_path / "stage-12"
    s12.mkdir()
    (s12 / "a.bin").write_bytes(b"x" * 1000)
    s12_v1 = tmp_path / "stage-12_v1"
    s12_v1.mkdir()
    (s12_v1 / "b.bin").write_bytes(b"y" * 500)
    # Unrelated dir not counted
    (tmp_path / "stage-13").mkdir()
    (tmp_path / "stage-13" / "c.bin").write_bytes(b"z" * 200)

    assert _estimate_stage12_footprint_bytes(tmp_path) == 1500


# ---------------------------------------------------------------------------
# Task 10: Stage 13 passthrough regression test
# ---------------------------------------------------------------------------


def test_stage13_collider_branch_promotes_merged_stage12_results(tmp_path):
    """Stage 13 in collider mode is a passthrough; the merged Stage-12 output
    must appear bit-identical at stage-13/experiment_final/results.json."""
    from researchclaw.adapters import AdapterBundle
    from researchclaw.pipeline.stage_impls._execution import _execute_iterative_refine

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    s12 = run_dir / "stage-12"
    s12.mkdir()
    runs = s12 / "runs"
    runs.mkdir()
    merged_payload = json.dumps({
        "metrics": {"primary_metric": 0.6, "old_only": 1.0, "new_only": 2.0},
        "structured_results": {"artifacts": {"figures": ["a.pdf", "b.pdf"]}},
    })
    (runs / "results.json").write_text(merged_payload, encoding="utf-8")
    (runs / "run-1.json").write_text('{"id": 1}', encoding="utf-8")

    s13 = run_dir / "stage-13"
    s13.mkdir()

    cfg = _make_rc_config(tmp_path, profile="hep_ph", mode="collider_agent")

    _ = _execute_iterative_refine(
        stage_dir=s13,
        run_dir=run_dir,
        config=cfg,
        adapters=AdapterBundle(),
    )

    promoted = s13 / "experiment_final" / "results.json"
    assert promoted.is_file()
    assert promoted.read_text(encoding="utf-8") == merged_payload


# ---------------------------------------------------------------------------
# Task 9: sandbox post-run results.json merge
# ---------------------------------------------------------------------------


def test_sandbox_merges_results_json_in_incremental_mode(tmp_path, monkeypatch):
    """In incremental mode, after Claude writes a new results.json, the
    sandbox merges it with the snapshotted previous one."""
    from researchclaw.config import ColliderAgentConfig
    from researchclaw.experiment.collider_agent_sandbox import ColliderAgentSandbox

    # Layout: run_dir/stage-12/runs/collider_workspace
    run_dir = tmp_path / "run"
    s12 = run_dir / "stage-12"
    runs = s12 / "runs"
    workspace = runs / "collider_workspace"
    workspace.mkdir(parents=True)
    (workspace / "models").mkdir()
    (workspace / "events").mkdir()
    (workspace / "events" / "mp1000").mkdir()

    # Snapshot of prior run already taken
    snap = run_dir / "stage-12_v1"
    snap_runs = snap / "runs"
    snap_runs.mkdir(parents=True)
    (snap_runs / "results.json").write_text(
        json.dumps({
            "metrics": {"primary_metric": 0.5, "old_only": 1.0},
            "structured_results": {"artifacts": {"figures": ["fig1.pdf"]}},
        }),
        encoding="utf-8",
    )

    cfg = ColliderAgentConfig(
        incremental=True,
        install_skills=False,
        claude_binary="/bin/true",
    )
    sandbox = ColliderAgentSandbox(cfg, workspace)

    # Stub subprocess.run so it appears Claude wrote a new results.json
    import subprocess as _sub

    def _fake_run(cmd, **kwargs):
        new_results = {
            "metrics": {"primary_metric": 0.6, "angular_chi2_2500": 2.3},
            "structured_results": {
                "artifacts": {"figures": ["fig1.pdf", "fig_angular.pdf"]}
            },
        }
        (workspace / "results.json").write_text(
            json.dumps(new_results), encoding="utf-8"
        )
        class _Done:
            returncode = 0
            stdout = ""
            stderr = ""
        return _Done()

    monkeypatch.setattr(
        "researchclaw.experiment.collider_agent_sandbox.subprocess.run", _fake_run
    )

    result = sandbox.run("# Add 2.5 TeV", timeout_sec=10)
    assert result.returncode == 0

    merged = json.loads((workspace / "results.json").read_text(encoding="utf-8"))
    assert merged["metrics"]["primary_metric"] == 0.6           # new wins
    assert merged["metrics"]["old_only"] == 1.0                  # preserved from snapshot
    assert merged["metrics"]["angular_chi2_2500"] == 2.3         # added
    figures = merged["structured_results"]["artifacts"]["figures"]
    assert "fig1.pdf" in figures
    assert "fig_angular.pdf" in figures
    assert len(set(figures)) == len(figures)  # deduped

    audit = json.loads((workspace / "incremental_merge.json").read_text(encoding="utf-8"))
    assert any("primary_metric" in k for k in audit["updated_keys"])
    assert any("angular_chi2_2500" in k for k in audit["new_keys"])
    assert any("old_only" in k for k in audit["kept_keys"])


def test_merge_docs_static_logic_handles_missing_snapshots():
    """The _merge_docs helper is robust to None / non-dict inputs."""
    from researchclaw.experiment.collider_agent_sandbox import ColliderAgentSandbox

    merged, kept, updated, new = ColliderAgentSandbox._merge_docs({}, {"metrics": {"x": 1}})
    assert merged == {"metrics": {"x": 1}}
    assert "metrics.x" in new


# ---------------------------------------------------------------------------
# Task 8: sandbox _prepare_workspace delta-prompt assembly + manifest
# ---------------------------------------------------------------------------


def test_prepare_workspace_in_incremental_mode_assembles_delta_prompt(tmp_path):
    from researchclaw.config import ColliderAgentConfig
    from researchclaw.experiment.collider_agent_sandbox import ColliderAgentSandbox

    workspace = tmp_path / "collider_workspace"
    workspace.mkdir()
    (workspace / "models").mkdir()
    (workspace / "models" / "Zprime_UFO").mkdir()
    (workspace / "events").mkdir()
    (workspace / "events" / "mp1000").mkdir()
    (workspace / "collider_plan.md").write_text(
        "# Prior run plan\nDo full mass scan from 1-5 TeV.\n", encoding="utf-8"
    )

    cfg = ColliderAgentConfig(incremental=True, install_skills=False)
    sandbox = ColliderAgentSandbox(cfg, workspace)

    delta_prompt = "## Add mass point 2.5 TeV\nGenerate 5000 ee events at m_Z'=2500.\n"
    final_workspace = sandbox._prepare_workspace(delta_prompt)

    final_prompt = (final_workspace / "collider_plan.md").read_text(encoding="utf-8")
    assert "CONTINUATION CONTEXT" in final_prompt
    assert "PRIOR PLAN" in final_prompt
    assert "Prior run plan" in final_prompt
    assert "NEW / ADDITIONAL TASKS" in final_prompt
    assert "Add mass point 2.5 TeV" in final_prompt
    assert (final_workspace / "workspace_manifest.json").is_file()
    assert (final_workspace / "collider_plan.prev.md").is_file()
    # Manifest should list the artifacts
    manifest = json.loads((final_workspace / "workspace_manifest.json").read_text(encoding="utf-8"))
    paths = [e["path"] for e in manifest["entries"]]
    assert any("Zprime_UFO" in p for p in paths)
    assert any("mp1000" in p for p in paths)


def test_prepare_workspace_non_incremental_unchanged(tmp_path):
    """Without incremental flag, behavior matches original (no continuation block)."""
    from researchclaw.config import ColliderAgentConfig
    from researchclaw.experiment.collider_agent_sandbox import ColliderAgentSandbox

    workspace = tmp_path / "ws_plain"
    cfg = ColliderAgentConfig(incremental=False, install_skills=False)
    sandbox = ColliderAgentSandbox(cfg, workspace)

    final_workspace = sandbox._prepare_workspace("# Plain plan\n")
    final_prompt = (final_workspace / "collider_plan.md").read_text(encoding="utf-8")
    assert "# Plain plan" in final_prompt
    assert "CONTINUATION CONTEXT" not in final_prompt
    assert not (final_workspace / "workspace_manifest.json").exists()
    assert not (final_workspace / "collider_plan.prev.md").exists()


def test_prepare_workspace_incremental_skipped_when_no_artifacts(tmp_path):
    """Even with incremental=True, fresh workspace skips the delta path."""
    from researchclaw.config import ColliderAgentConfig
    from researchclaw.experiment.collider_agent_sandbox import ColliderAgentSandbox

    workspace = tmp_path / "ws_fresh"
    cfg = ColliderAgentConfig(incremental=True, install_skills=False)
    sandbox = ColliderAgentSandbox(cfg, workspace)

    final_workspace = sandbox._prepare_workspace("# Fresh plan\n")
    final_prompt = (final_workspace / "collider_plan.md").read_text(encoding="utf-8")
    assert "CONTINUATION CONTEXT" not in final_prompt
    assert not (final_workspace / "workspace_manifest.json").exists()


# ---------------------------------------------------------------------------
# Task 7: pre-run snapshot in _execute_experiment_run
# ---------------------------------------------------------------------------


def test_stage12_snapshots_existing_workspace_when_incremental(tmp_path, monkeypatch):
    """Re-entering Stage 12 with incremental=True must copy old stage-12 to stage-12_v1."""
    from researchclaw.adapters import AdapterBundle
    from researchclaw.experiment import collider_agent_sandbox as ca_mod
    from researchclaw.experiment.sandbox import SandboxResult
    from researchclaw.pipeline.stage_impls._execution import _execute_experiment_run

    run_dir = tmp_path / "run"
    s12 = run_dir / "stage-12"
    s12.mkdir(parents=True)
    runs = s12 / "runs"
    runs.mkdir()
    workspace = runs / "collider_workspace"
    workspace.mkdir()
    (workspace / "models").mkdir()
    (workspace / "models" / "Zprime_UFO").mkdir()
    (workspace / "events").mkdir()
    (workspace / "events" / "mp1000").mkdir()
    (runs / "results.json").write_text(
        '{"metrics": {"primary_metric": 0.5}, '
        '"structured_results": {"artifacts": {"figures": ["fig1.pdf"]}}}',
        encoding="utf-8",
    )
    (workspace / "collider_plan.md").write_text("# Old plan\n", encoding="utf-8")

    # Required upstream inputs
    (run_dir / "stage-09").mkdir()
    (run_dir / "stage-09" / "exp_plan.yaml").write_text("plan: x", encoding="utf-8")
    (run_dir / "stage-10").mkdir()
    (run_dir / "stage-10" / "collider_plan.md").write_text("# New delta\n", encoding="utf-8")
    (run_dir / "stage-11").mkdir()
    (run_dir / "stage-11" / "schedule.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        ca_mod.ColliderAgentSandbox, "run",
        lambda self, prompt, timeout_sec=None: SandboxResult(
            returncode=0, stdout="", stderr="", elapsed_sec=0.0, metrics={}, timed_out=False,
        ),
    )

    cfg = _make_rc_config(tmp_path, profile="hep_ph", mode="collider_agent")
    from dataclasses import replace
    cfg = replace(cfg, experiment=replace(
        cfg.experiment,
        collider_agent=replace(cfg.experiment.collider_agent, incremental=True),
    ))

    _ = _execute_experiment_run(
        stage_dir=s12,
        run_dir=run_dir,
        config=cfg,
        adapters=AdapterBundle(),
    )

    # Snapshot exists and contains the prior metrics
    assert (run_dir / "stage-12_v1" / "runs" / "results.json").is_file()
    snap_text = (run_dir / "stage-12_v1" / "runs" / "results.json").read_text(encoding="utf-8")
    assert "0.5" in snap_text
    # Live stage-12 still present
    assert (run_dir / "stage-12" / "runs").exists()
    # Incremental audit sidecar
    assert (run_dir / "stage-12_v1" / "INCREMENTAL_SNAPSHOT.txt").is_file()


def test_stage12_no_snapshot_when_workspace_empty(tmp_path, monkeypatch):
    """No prior models/ or events/ artifacts: skip the snapshot even if incremental=True."""
    from dataclasses import replace
    from researchclaw.adapters import AdapterBundle
    from researchclaw.experiment import collider_agent_sandbox as ca_mod
    from researchclaw.experiment.sandbox import SandboxResult
    from researchclaw.pipeline.stage_impls._execution import _execute_experiment_run

    run_dir = tmp_path / "run"
    s12 = run_dir / "stage-12"
    s12.mkdir(parents=True)
    (s12 / "runs").mkdir()
    (run_dir / "stage-09").mkdir()
    (run_dir / "stage-09" / "exp_plan.yaml").write_text("x: 1", encoding="utf-8")
    (run_dir / "stage-10").mkdir()
    (run_dir / "stage-10" / "collider_plan.md").write_text("# fresh\n", encoding="utf-8")
    (run_dir / "stage-11").mkdir()
    (run_dir / "stage-11" / "schedule.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        ca_mod.ColliderAgentSandbox, "run",
        lambda self, prompt, timeout_sec=None: SandboxResult(
            returncode=0, stdout="", stderr="", elapsed_sec=0.0, metrics={}, timed_out=False,
        ),
    )

    cfg = _make_rc_config(tmp_path, profile="hep_ph", mode="collider_agent")
    cfg = replace(cfg, experiment=replace(
        cfg.experiment,
        collider_agent=replace(cfg.experiment.collider_agent, incremental=True),
    ))

    _ = _execute_experiment_run(s12, run_dir, cfg, AdapterBundle())

    # No snapshot because nothing was there to snapshot
    assert not (run_dir / "stage-12_v1").exists()


# ---------------------------------------------------------------------------
# Task 6: incremental-aware _version_rollback_stages
# ---------------------------------------------------------------------------


def test_version_rollback_stages_uses_copytree_when_incremental(tmp_path):
    from researchclaw.pipeline.runner import _version_rollback_stages
    from researchclaw.pipeline.stages import Stage

    s12 = tmp_path / "stage-12"
    s12.mkdir()
    (s12 / "marker.txt").write_text("alive", encoding="utf-8")
    (s12 / "runs").mkdir()
    (s12 / "runs" / "x.json").write_text('{"a": 1}', encoding="utf-8")

    _version_rollback_stages(
        tmp_path,
        rollback_target=Stage.EXPERIMENT_RUN,
        attempt=1,
        incremental=True,
    )

    # Original stage-12 still in place (not renamed)
    assert (tmp_path / "stage-12" / "marker.txt").read_text(encoding="utf-8") == "alive"
    assert (tmp_path / "stage-12_v1" / "marker.txt").read_text(encoding="utf-8") == "alive"
    assert (tmp_path / "stage-12_v1" / "runs" / "x.json").read_text(encoding="utf-8") == '{"a": 1}'


def test_version_rollback_stages_default_still_renames(tmp_path):
    from researchclaw.pipeline.runner import _version_rollback_stages
    from researchclaw.pipeline.stages import Stage

    s13 = tmp_path / "stage-13"
    s13.mkdir()
    (s13 / "data.txt").write_text("hi", encoding="utf-8")

    _version_rollback_stages(tmp_path, rollback_target=Stage.ITERATIVE_REFINE, attempt=1)

    assert not (tmp_path / "stage-13").exists()
    assert (tmp_path / "stage-13_v1" / "data.txt").read_text(encoding="utf-8") == "hi"


def test_executor_does_not_gate_code_generation_for_non_hep_ph(tmp_path, monkeypatch):
    from researchclaw.adapters import AdapterBundle
    from researchclaw.pipeline import executor as exec_mod
    from researchclaw.pipeline._helpers import StageResult
    from researchclaw.pipeline.stages import Stage, StageStatus

    cfg = _make_rc_config(tmp_path, profile="", mode="sandbox")

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    s09 = run_dir / "stage-09"
    s09.mkdir()
    (s09 / "exp_plan.yaml").write_text("x: 1", encoding="utf-8")

    def _stub_codegen(stage_dir, run_dir, config, adapters, *args, **kwargs):
        # Default-mode contract requires experiment/ + experiment_spec.md
        (stage_dir / "experiment").mkdir(parents=True, exist_ok=True)
        (stage_dir / "experiment" / "main.py").write_text("# stub\n", encoding="utf-8")
        (stage_dir / "experiment_spec.md").write_text("# spec\n", encoding="utf-8")
        return StageResult(
            stage=Stage.CODE_GENERATION,
            status=StageStatus.DONE,
            artifacts=("experiment_spec.md",),
        )

    monkeypatch.setitem(exec_mod._STAGE_EXECUTORS, Stage.CODE_GENERATION, _stub_codegen)

    adapters = AdapterBundle()
    result = exec_mod.execute_stage(
        Stage.CODE_GENERATION,
        run_dir=run_dir,
        run_id="test-run-2",
        config=cfg,
        adapters=adapters,
        auto_approve_gates=False,
    )
    assert result.status == StageStatus.DONE
