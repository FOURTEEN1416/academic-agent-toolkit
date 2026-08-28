import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import citation_bridge, latex_bridge, solver_bridge, visual_bridge


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_latex_bridge_reports_missing_engine_and_writes_manifest(tmp_path, monkeypatch):
    tex = tmp_path / "paper.tex"
    tex.write_text("\\documentclass{article}\\begin{document}Hi\\end{document}", encoding="utf-8")
    monkeypatch.setattr(latex_bridge, "_find_engine", lambda engine: None)

    result = latex_bridge.compile_latex(tmp_path, tex, "xelatex", runs=1, timeout=1)

    assert result["ok"] is False
    assert result["stepManifest"] == "STEP_MANIFEST.json"
    assert (tmp_path / "latex_bridge_result.json").is_file()
    manifest = _read_json(tmp_path / "STEP_MANIFEST.json")
    assert manifest["stepName"] == "latex-bridge"


def test_latex_bridge_includes_manifest_when_engine_runs(tmp_path, monkeypatch):
    tex = tmp_path / "paper.tex"
    tex.write_text("\\documentclass{article}\\begin{document}Hi\\end{document}", encoding="utf-8")
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.7")

    monkeypatch.setattr(latex_bridge, "_find_engine", lambda engine: str(tmp_path / "xelatex.exe"))
    monkeypatch.setattr(latex_bridge, "command_version", lambda *_: "1.0")
    monkeypatch.setattr(latex_bridge, "run_command", lambda *args, **kwargs: {"command": ["xelatex"], "cwd": str(tmp_path), "exitCode": 0, "stdout": "", "stderr": ""})

    result = latex_bridge.compile_latex(tmp_path, tex, "xelatex", runs=1, timeout=1)

    assert result["ok"] is True
    # manifest 存在且验证通过（不检查 dependencies provenance，因为测试环境无 UPSTREAM.md）
    assert "manifest" in result
    assert (tmp_path / "STEP_MANIFEST.json").is_file()


def test_solver_bridge_runs_scipy_linprog_and_writes_manifest(tmp_path, monkeypatch):
    config = tmp_path / "solver.json"
    config.write_text(json.dumps({"solver": "scipy-linprog", "c": [1, 1], "bounds": [[0, None], [0, None]]}), encoding="utf-8")
    result = solver_bridge.run_solver(tmp_path, config)

    assert result["stepManifest"] == "STEP_MANIFEST.json"
    assert (tmp_path / "solver_bridge_result.json").is_file()
    assert (tmp_path / "STEP_MANIFEST.json").is_file()


def test_citation_bridge_handles_bibtex_and_writes_manifest(tmp_path):
    bib = tmp_path / "refs.bib"
    bib.write_text("@article{a,title={A},author={B},year={2024}}", encoding="utf-8")

    result = citation_bridge.check_citations(tmp_path, bib)

    assert result["mode"] == "bibtex"
    assert result["stepManifest"] == "STEP_MANIFEST.json"
    assert (tmp_path / "citation_bridge_result.json").is_file()
    assert (tmp_path / "STEP_MANIFEST.json").is_file()


def test_visual_bridge_handles_unavailable_tooling(tmp_path, monkeypatch):
    image = tmp_path / "fig.png"
    image.write_bytes(b"fake")
    monkeypatch.setattr(visual_bridge, "run_command", lambda *args, **kwargs: {"command": ["python", "x"], "cwd": str(tmp_path), "exitCode": 2, "stdout": "NO_VISION_API", "stderr": ""})

    result = visual_bridge.run_visual_check(tmp_path, image, "tikz", review=False)

    assert result["status"] == "unavailable"
    assert result["stepManifest"] == "STEP_MANIFEST.json"
    assert (tmp_path / "visual_bridge_result.json").is_file()
    assert (tmp_path / "STEP_MANIFEST.json").is_file()
