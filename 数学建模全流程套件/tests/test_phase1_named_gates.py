import json

from engine.quality_gates import QualityGate


def test_paper_consistency_gate_rejects_paper_without_result_numbers(tmp_path):
    paper = tmp_path / "paper"
    figures = tmp_path / "figures"
    paper.mkdir()
    figures.mkdir()
    (paper / "main.tex").write_text(
        "\\documentclass{article}\\begin{document}No numbers here.\\end{document}", encoding="utf-8"
    )
    (figures / "all_results.json").write_text(json.dumps({"objective": 42.5}), encoding="utf-8")

    result = QualityGate(tmp_path).check_paper_consistency()

    assert result["ok"] is False
    assert "未引用任何结果关键数字" in result["reason"]


def test_paper_consistency_gate_accepts_cited_result_number(tmp_path):
    paper = tmp_path / "paper"
    figures = tmp_path / "figures"
    paper.mkdir()
    figures.mkdir()
    (paper / "main.tex").write_text(
        "\\documentclass{article}\\begin{document}The objective is 42.5\\end{document}", encoding="utf-8"
    )
    (figures / "all_results.json").write_text(json.dumps({"objective": 42.5}), encoding="utf-8")

    result = QualityGate(tmp_path).check_paper_consistency()

    assert result["ok"] is True
    assert result["hits"] >= 1


def test_paper_consistency_gate_accepts_rounded_result_number(tmp_path):
    paper = tmp_path / "paper"
    figures = tmp_path / "figures"
    paper.mkdir()
    figures.mkdir()
    (paper / "main.tex").write_text(
        "\\documentclass{article}\\begin{document}Error rate 0.1234\\end{document}", encoding="utf-8"
    )
    (figures / "all_results.json").write_text(json.dumps({"err": 0.1234}), encoding="utf-8")

    result = QualityGate(tmp_path).check_paper_consistency()

    assert result["ok"] is True
    assert result["hits"] >= 1


def test_citation_integrity_rejects_invalid_doi(tmp_path):
    paper = tmp_path / "paper"
    paper.mkdir()
    (paper / "references.bib").write_text(
        "@article{a,\n  title={A},\n  author={B},\n  year={2024},\n  doi={not-a-doi}\n}\n",
        encoding="utf-8",
    )

    result = QualityGate(tmp_path).check_citation_integrity()

    assert result["ok"] is False
    assert result["invalid_dois"]


def test_citation_integrity_accepts_valid_entries(tmp_path):
    paper = tmp_path / "paper"
    paper.mkdir()
    (paper / "references.bib").write_text(
        "@article{a,\n  title={A},\n  author={B},\n  year={2024},\n  doi={10.1000/example}\n}\n",
        encoding="utf-8",
    )

    result = QualityGate(tmp_path).check_citation_integrity()

    assert result["ok"] is True
    assert result["entries"] == 1


def test_experiment_reproduc_requires_manifest_deps_and_command(tmp_path):
    result = QualityGate(tmp_path).check_experiment_reproduc()

    assert result["ok"] is False
    assert "STEP_MANIFEST.json" in result["failures"][0]


def test_experiment_reproduc_accepts_full_manifest(tmp_path):
    from engine.step_manifest import write_manifest

    (tmp_path / "RESULTS.md").write_text("# Results\nseed=42\n", encoding="utf-8")
    write_manifest(
        workspace=tmp_path,
        step_name="experiment-bridge",
        config={"seed": 42},
        outputs=[tmp_path / "RESULTS.md"],
        backend="python 3.12",
        commands=[{"command": "python code/main.py", "exitCode": 0}],
        dependencies={"numpy": "2.4.6"},
    )

    result = QualityGate(tmp_path).check_experiment_reproduc()

    assert result["ok"] is True


def test_figure_provenance_rejects_orphan_pngs(tmp_path):
    figures = tmp_path / "figures"
    figures.mkdir()
    (figures / "fig_a.png").write_bytes(b"PNG")

    result = QualityGate(tmp_path).check_figure_provenance()

    assert result["ok"] is False
    assert "溯源" in result["reason"]


def test_figure_provenance_accepts_data_source(tmp_path):
    figures = tmp_path / "figures"
    figures.mkdir()
    (figures / "fig_a.png").write_bytes(b"PNG")
    (figures / "all_results.json").write_text('{"a": 1}', encoding="utf-8")

    result = QualityGate(tmp_path).check_figure_provenance()

    assert result["ok"] is True


def test_compilation_log_rejects_fatal_errors(tmp_path):
    paper = tmp_path / "paper"
    paper.mkdir()
    (paper / "main.log").write_text("! LaTeX Error: File not found.\n", encoding="utf-8")

    result = QualityGate(tmp_path).check_compilation_log()

    assert result["ok"] is False
    assert result["fatals"] >= 1


def test_compilation_log_accepts_clean_log(tmp_path):
    paper = tmp_path / "paper"
    paper.mkdir()
    (paper / "main.log").write_text("Output written on main.pdf.\n", encoding="utf-8")

    result = QualityGate(tmp_path).check_compilation_log()

    assert result["ok"] is True


def test_run_all_routes_new_named_gates(tmp_path):
    (tmp_path / "paper").mkdir()
    (tmp_path / "figures").mkdir()
    (tmp_path / "paper" / "main.tex").write_text("obj 42", encoding="utf-8")
    (tmp_path / "figures" / "all_results.json").write_text('{"objective": 42}', encoding="utf-8")

    result = QualityGate(tmp_path).run_all(
        "comp-paper-zh",
        declared_outputs=["paper/main.tex"],
        required_checks=["paper_consistency", "figure_provenance"],
    )

    assert result["checks"]["paper_consistency"]["ok"] is True
    assert "figure_provenance" in result["checks"]
    assert result["ok"] is False  # figure_provenance 缺来源 → 整体失败