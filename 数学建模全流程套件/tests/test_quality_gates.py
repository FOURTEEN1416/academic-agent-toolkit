import hashlib
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.artifact_manifest import ArtifactManifest
from engine.quality_gates import QualityGate, build_review_execution_evidence


def test_pdf_page_gate_uses_pdfinfo_page_count(tmp_path):
    """非 CUMCM 竞赛（无 body 语义）仍走总页数路径，依赖 pdfinfo."""
    paper = tmp_path / "paper"
    paper.mkdir()
    (paper / "main.pdf").write_bytes(b"%PDF-1.7")
    gate = QualityGate(tmp_path)

    # 使用 comp_mcm（无 page_scope，走总页数路径）
    with patch("engine.quality_gates.subprocess.run") as run:
        run.return_value.stdout = "Pages:           22\n"
        run.return_value.returncode = 0
        result = gate.check_paper_pages("comp_mcm")

    assert result["ok"] is True
    assert result["pages"] == 22


def test_cumcm_page_gate_excludes_summary_and_unlimited_appendix(tmp_path):
    paper = tmp_path / "paper"
    paper.mkdir()
    (paper / "main.pdf").write_bytes(b"%PDF-1.7")
    page_texts = ["摘要"] + [f"正文 {index}" for index in range(30)] + ["附录", "代码"] * 10

    class Page:
        def __init__(self, text):
            self.text = text

        def get_text(self):
            return self.text

    class Document:
        page_count = len(page_texts)

        def __init__(self, texts):
            self._texts = texts

        def __getitem__(self, index):
            return Page(self._texts[index])

        def close(self):
            pass

    with patch("engine.quality_gates.subprocess.run", side_effect=FileNotFoundError), \
            patch("engine.quality_gates._fitz.open", return_value=Document(page_texts)):
        result = QualityGate(tmp_path).check_paper_pages("comp_cumcm")

    assert result["ok"] is True
    assert result["body_pages"] == 30
    assert result["total_pages"] == len(page_texts)


def test_cumcm_page_gate_rejects_more_than_thirty_body_pages(tmp_path):
    paper = tmp_path / "paper"
    paper.mkdir()
    (paper / "main.pdf").write_bytes(b"%PDF-1.7")
    page_texts = ["摘要"] + [f"正文 {index}" for index in range(31)] + ["附录"]

    class Page:
        def __init__(self, texts, index):
            self._text = texts[index] if index < len(texts) else ""

        def get_text(self):
            return self._text

    class Document:
        page_count = len(page_texts)

        def __init__(self, texts):
            self._texts = texts

        def __getitem__(self, index):
            return Page(self._texts, index)

        def close(self):
            pass

    with patch("engine.quality_gates.subprocess.run", side_effect=FileNotFoundError), \
            patch("engine.quality_gates._fitz.open", return_value=Document(page_texts)):
        result = QualityGate(tmp_path).check_paper_pages("comp_cumcm")

    assert result["ok"] is True
    assert result["body_pages"] == 30
    assert result["total_pages"] == len(page_texts)


def test_cumcm_page_gate_rejects_more_than_thirty_body_pages(tmp_path):
    paper = tmp_path / "paper"
    paper.mkdir()
    (paper / "main.pdf").write_bytes(b"%PDF-1.7")
    page_texts = ["摘要"] + [f"正文 {index}" for index in range(31)] + ["附录"]

    class Page:
        def __init__(self, texts, index):
            self._text = texts[index] if index < len(texts) else ""

        def get_text(self):
            return self._text

    class Document:
        page_count = len(page_texts)

        def __init__(self, texts):
            self._texts = texts

        def __getitem__(self, index):
            return Page(self._texts, index)

        def close(self):
            pass

    with patch("engine.quality_gates.subprocess.run", side_effect=FileNotFoundError), \
            patch("engine.quality_gates._fitz.open", return_value=Document(page_texts)):
        result = QualityGate(tmp_path).check_paper_pages("comp_cumcm")

    assert result["ok"] is False
    assert result["body_pages"] == 31


def test_literature_gate_requires_search_evidence_bib_and_citations(tmp_path):
    paper = tmp_path / "paper"
    literature = tmp_path / "literature"
    paper.mkdir()
    literature.mkdir()
    (tmp_path / "LITERATURE.md").write_text("# Literature\n", encoding="utf-8")
    (literature / "search_evidence.json").write_text('[{"query": "STR mixture", "verified": true}]', encoding="utf-8")
    (paper / "references.bib").write_text("@article{demo,title={Demo}}", encoding="utf-8")
    (paper / "main.tex").write_text("\\documentclass{article}\\begin{document}No citations.\\end{document}", encoding="utf-8")

    result = QualityGate(tmp_path).check_literature_evidence()

    assert result["ok"] is False
    assert "citation" in result["reason"].lower()


def test_literature_search_gate_does_not_require_an_unwritten_paper(tmp_path):
    paper = tmp_path / "paper"
    literature = tmp_path / "literature"
    paper.mkdir()
    literature.mkdir()
    (tmp_path / "LITERATURE.md").write_text("# Literature\n", encoding="utf-8")
    (literature / "search_evidence.json").write_text(
        '[{"query": "STR mixture", "verified": true}]', encoding="utf-8"
    )
    (paper / "references.bib").write_text("@article{demo,title={Demo}}", encoding="utf-8")

    result = QualityGate(tmp_path).run_all(
        "comp-literature",
        declared_outputs=["LITERATURE.md", "literature/search_evidence.json", "paper/references.bib"],
        required_checks=["literature_search"],
    )

    assert result["ok"] is True
    assert result["checks"]["literature_search"]["records"] == 1


def test_review_gate_rejects_missing_or_fatal_verdicts(tmp_path):
    result = QualityGate(tmp_path).check_review_evidence()
    assert result["ok"] is False

    (tmp_path / "COMP_REVIEW.md").write_text("# Review", encoding="utf-8")
    (tmp_path / "VISUAL_REVIEW.md").write_text("# Visual", encoding="utf-8")
    (tmp_path / "EDITOR_CHANGELOG.md").write_text("# Changes", encoding="utf-8")
    (tmp_path / "FINAL_REVIEW.md").write_text("# Final", encoding="utf-8")
    for name in ("COMP_REVIEW_VERDICT.json", "VISUAL_REVIEW_VERDICT.json", "FINAL_REVIEW_VERDICT.json"):
        (tmp_path / name).write_text('{"findings": [], "fatal_count": 1}', encoding="utf-8")

    fatal = QualityGate(tmp_path).check_review_evidence()
    assert fatal["ok"] is False
    assert fatal["fatal_count"] == 3


def test_build_review_execution_evidence_hashes_all_role_outputs(tmp_path):
    outputs = {
        "reviewer": "COMP_REVIEW_VERDICT.json",
        "visual_reviewer": "VISUAL_REVIEW_VERDICT.json",
        "editor": "EDITOR_CHANGELOG.md",
        "final_reviewer": "FINAL_REVIEW_VERDICT.json",
    }
    for role, output in outputs.items():
        (tmp_path / output).write_text(role, encoding="utf-8")

    evidence = build_review_execution_evidence(
        tmp_path,
        {
            role: {"session_id": f"session-{role}", "model": "test-model", "output_file": output}
            for role, output in outputs.items()
        },
        completed_at="2026-08-11T00:00:00+00:00",
    )

    assert set(evidence["roles"]) == set(outputs)
    assert all(len(record["output_sha256"]) == 64 for record in evidence["roles"].values())
    assert all(record["completed_at"] == "2026-08-11T00:00:00+00:00" for record in evidence["roles"].values())


def test_build_review_execution_evidence_rejects_incomplete_roles(tmp_path):
    with pytest.raises(ValueError, match="角色集合不完整"):
        build_review_execution_evidence(tmp_path, {"reviewer": {}}, completed_at="2026-08-11T00:00:00+00:00")


def test_consistency_gate_requires_canonical_result_ledger_and_passing_report(tmp_path):
    result = QualityGate(tmp_path).check_consistency_evidence()
    assert result["ok"] is False


def test_final_audit_gate_rejects_presence_only_report(tmp_path):
    (tmp_path / "AUDIT_REPORT.json").write_text("{}", encoding="utf-8")

    result = QualityGate(tmp_path).check_final_audit_report()

    assert result["ok"] is False
    assert "字段" in result["reason"]


def test_final_audit_gate_accepts_ready_manifest_backed_decision(tmp_path):
    report = {
        "workflow_id": "wf-1",
        "artifacts": [{"path": "paper/main.pdf", "sha256": "a" * 64}],
        "gate_outcomes": {"literature": "pass", "review": "pass", "consistency": "pass"},
        "waivers": [],
        "delivery_decision": "ready",
    }
    (tmp_path / "AUDIT_REPORT.json").write_text(json.dumps(report), encoding="utf-8")

    result = QualityGate(tmp_path).check_final_audit_report()

    assert result["ok"] is True

    (tmp_path / "RESULTS.md").write_text("# Results", encoding="utf-8")
    figures = tmp_path / "figures"
    figures.mkdir()
    (figures / "all_results.json").write_text("{}", encoding="utf-8")
    (tmp_path / "CONSISTENCY_REPORT.json").write_text('{"ok": false, "claims": []}', encoding="utf-8")
    result = QualityGate(tmp_path).check_consistency_evidence()
    assert result["ok"] is False


def test_figure_health_rejects_invalid_png(tmp_path):
    figures = tmp_path / "figures"
    figures.mkdir()
    (figures / "bad.png").write_text("not an image", encoding="utf-8")

    result = QualityGate(tmp_path).check_figure_health()

    assert result["ok"] is False
    assert result["invalid"] == ["figures/bad.png"]


def test_scan_records_sha256_and_size_for_declared_output(tmp_path):
    output = tmp_path / "result.md"
    content = b"declared result\n"
    output.write_bytes(content)

    artifacts = ArtifactManifest.scan(tmp_path, ["result.md"])

    assert len(artifacts) == 1
    assert artifacts[0].path == "result.md"
    assert artifacts[0].size == len(content)
    assert artifacts[0].sha256 == hashlib.sha256(content).hexdigest()
    assert artifacts[0].exists is True


def test_declared_output_hash_mismatch_fails_manifest_validation(tmp_path):
    (tmp_path / "result.md").write_text("actual", encoding="utf-8")

    result = ArtifactManifest.validate(
        tmp_path,
        [{"path": "result.md", "sha256": "0" * 64}],
    )

    assert result["ok"] is False
    assert "result.md" in result["invalid"]


@pytest.mark.parametrize("declared", ["/outside.txt", "../outside.txt", "sub/../../outside.txt"])
def test_declared_output_must_be_relative_and_stay_in_workspace(tmp_path, declared):
    result = ArtifactManifest.validate(tmp_path, [declared])

    assert result["ok"] is False
    assert declared in result["invalid"]


def test_large_unrelated_markdown_cannot_satisfy_missing_declared_output(tmp_path):
    (tmp_path / "unrelated.md").write_text("x" * 5000, encoding="utf-8")

    result = QualityGate(tmp_path).run_all(
        "comp-modeling",
        declared_outputs=["required/result.md"],
    )

    assert result["ok"] is False
    assert result["checks"]["artifacts"]["ok"] is False
    assert "required/result.md" in result["checks"]["artifacts"]["missing"]


def test_run_all_uses_explicit_primary_output_for_minimum_size(tmp_path):
    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "main.py").write_text("x" * 600, encoding="utf-8")
    (tmp_path / "RESULTS.md").write_text("x" * 1200, encoding="utf-8")
    (tmp_path / "figures").mkdir()
    (tmp_path / "figures" / "all_results.json").write_text("{}", encoding="utf-8")

    result = QualityGate(tmp_path).run_all(
        "comp-code",
        declared_outputs=["code/main.py", "RESULTS.md", "figures/all_results.json"],
        primary_output="RESULTS.md",
    )

    assert result["ok"] is True
    assert result["checks"]["min_size"]["size"] == 1200


def test_figures_are_checked_only_when_declared(tmp_path):
    (tmp_path / "result.md").write_text("result", encoding="utf-8")
    (tmp_path / "figures").mkdir()

    without_figures = QualityGate(tmp_path).run_all(
        "comp-review",
        declared_outputs=["result.md"],
    )
    with_figures = QualityGate(tmp_path).run_all(
        "comp-review",
        declared_outputs=["result.md"],
        requires_figures=True,
    )

    assert without_figures["checks"]["figures"]["skipped"] is True
    assert with_figures["checks"]["figures"]["ok"] is False


def test_declared_outputs_do_not_bypass_required_companions(tmp_path):
    (tmp_path / "RESULTS.md").write_text("x" * 2000, encoding="utf-8")

    result = QualityGate(tmp_path).run_all("comp-code", declared_outputs=["RESULTS.md"])

    assert result["ok"] is False
    assert result["checks"]["companions"]["ok"] is False


def test_declared_directory_is_hashed_from_its_files(tmp_path):
    figures = tmp_path / "figures"
    figures.mkdir()
    (figures / "a.json").write_text('{"ok": true}', encoding="utf-8")
    (figures / "b.txt").write_text("evidence", encoding="utf-8")

    result = ArtifactManifest.validate(tmp_path, ["figures/"])

    assert result["ok"] is True
    artifact = result["artifacts"][0]
    assert artifact.exists is True
    assert artifact.size == len('{"ok": true}'.encode()) + len("evidence".encode())
    assert len(artifact.sha256) == 64


def test_min_size_for_directory_uses_contained_files(tmp_path):
    figures = tmp_path / "figures"
    figures.mkdir()
    (figures / "result.json").write_text("x" * 1200, encoding="utf-8")

    result = QualityGate(tmp_path).check_min_size("paper-figure", "figures/")

    assert result["ok"] is True
    assert result["size"] == 1200


def test_literature_gate_requires_doi_overlap_with_search_evidence(tmp_path):
    paper = tmp_path / "paper"
    literature = tmp_path / "literature"
    paper.mkdir()
    literature.mkdir()
    (tmp_path / "LITERATURE.md").write_text("# Literature\n", encoding="utf-8")
    (literature / "search_evidence.json").write_text(json.dumps([
        {"records": [{"key": "searched", "doi": "10.1000/searched"}]}
    ]), encoding="utf-8")
    (paper / "references.bib").write_text(
        "@article{other,title={Other},doi={10.1000/other}}", encoding="utf-8"
    )
    (paper / "main.tex").write_text(
        "\\documentclass{article}\\begin{document}\\cite{other}\\end{document}", encoding="utf-8"
    )

    result = QualityGate(tmp_path).check_literature_evidence()

    assert result["ok"] is False
    assert "overlap" in result["reason"].lower() or "交集" in result["reason"]


def _write_review_files(tmp_path):
    for name in ("COMP_REVIEW.md", "VISUAL_REVIEW.md", "EDITOR_CHANGELOG.md", "FINAL_REVIEW.md"):
        (tmp_path / name).write_text(f"# {name}\n", encoding="utf-8")
    (tmp_path / "COMP_REVIEW_VERDICT.json").write_text('{"findings": [], "fatal_count": 0}', encoding="utf-8")
    (tmp_path / "VISUAL_REVIEW_VERDICT.json").write_text(
        '{"findings": [], "fatal_count": 0, "status": "pass"}', encoding="utf-8"
    )
    (tmp_path / "FINAL_REVIEW_VERDICT.json").write_text('{"findings": [], "fatal_count": 0}', encoding="utf-8")


def _provenance(hashes):
    return {"schema_version": 1, "roles": {
        "reviewer": {"session_id": "s1", "model": "m1", "completed_at": "2026-08-08T00:00:00Z", "output_file": "COMP_REVIEW_VERDICT.json", "output_sha256": hashes["reviewer"]},
        "visual_reviewer": {"session_id": "s2", "model": "m2", "completed_at": "2026-08-08T00:00:00Z", "output_file": "VISUAL_REVIEW_VERDICT.json", "output_sha256": hashes["visual_reviewer"]},
        "editor": {"session_id": "s3", "model": "m3", "completed_at": "2026-08-08T00:00:00Z", "output_file": "EDITOR_CHANGELOG.md", "output_sha256": hashes["editor"]},
        "final_reviewer": {"session_id": "s4", "model": "m4", "completed_at": "2026-08-08T00:00:00Z", "output_file": "FINAL_REVIEW_VERDICT.json", "output_sha256": hashes["final_reviewer"]},
    }}


def test_full_review_gate_requires_role_execution_provenance(tmp_path):
    _write_review_files(tmp_path)

    result = QualityGate(tmp_path).check_review_evidence("full")

    assert result["ok"] is False
    assert "REVIEW_EXECUTION_EVIDENCE.json" in result.get("missing", [])


def test_full_review_gate_rejects_fabricated_provenance_hashes(tmp_path):
    _write_review_files(tmp_path)
    (tmp_path / "REVIEW_EXECUTION_EVIDENCE.json").write_text(json.dumps(_provenance({
        "reviewer": "a1b2c3d4" * 8,
        "visual_reviewer": "b2c3d4e5" * 8,
        "editor": "c3d4e5f6" * 8,
        "final_reviewer": "d4e5f6a1" * 8,
    })), encoding="utf-8")

    result = QualityGate(tmp_path).check_review_evidence("full")

    assert result["ok"] is False
    assert "hash" in result["reason"].lower() or "sha256" in result["reason"].lower()


def test_full_review_gate_accepts_matching_output_hashes(tmp_path):
    _write_review_files(tmp_path)
    hashes = {
        "reviewer": hashlib.sha256((tmp_path / "COMP_REVIEW_VERDICT.json").read_bytes()).hexdigest(),
        "visual_reviewer": hashlib.sha256((tmp_path / "VISUAL_REVIEW_VERDICT.json").read_bytes()).hexdigest(),
        "editor": hashlib.sha256((tmp_path / "EDITOR_CHANGELOG.md").read_bytes()).hexdigest(),
        "final_reviewer": hashlib.sha256((tmp_path / "FINAL_REVIEW_VERDICT.json").read_bytes()).hexdigest(),
    }
    (tmp_path / "REVIEW_EXECUTION_EVIDENCE.json").write_text(json.dumps(_provenance(hashes)), encoding="utf-8")

    result = QualityGate(tmp_path).check_review_evidence("full")

    assert result["ok"] is True
    assert result["mode"] == "full"


def test_full_review_gate_warns_but_does_not_block_model_mismatch(tmp_path, monkeypatch):
    """软校验：证据模型与 agent 配置不一致 → 警告但不阻断（模型策略由 .opencode/agents 决定）。"""
    # 指向一个可控的假 agents 目录
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    for fname, model in (
        ("数模审稿人.md", "opencode/mimo-v2.5-free"),
        ("数模视觉审查.md", "agnes/agnes-2.5-flash"),
        ("数模编辑.md", "opencode/mimo-v2.5-free"),
        ("数模专家.md", "deepseek/deepseek-v4-flash"),
    ):
        (agents_dir / fname).write_text(f"---\nmodel: {model}\n---\n", encoding="utf-8")
    monkeypatch.setenv("OPENCODE_AGENTS_DIR", str(agents_dir))

    _write_review_files(tmp_path)
    hashes = {
        "reviewer": hashlib.sha256((tmp_path / "COMP_REVIEW_VERDICT.json").read_bytes()).hexdigest(),
        "visual_reviewer": hashlib.sha256((tmp_path / "VISUAL_REVIEW_VERDICT.json").read_bytes()).hexdigest(),
        "editor": hashlib.sha256((tmp_path / "EDITOR_CHANGELOG.md").read_bytes()).hexdigest(),
        "final_reviewer": hashlib.sha256((tmp_path / "FINAL_REVIEW_VERDICT.json").read_bytes()).hexdigest(),
    }
    provenance = _provenance(hashes)
    # 让四个角色模型与配置一致（m1/m2/m3/m4 → 配置模型），只把 reviewer 改成旧模型
    provenance["roles"]["reviewer"]["model"] = "opencode/mimo-v2.5-free"
    provenance["roles"]["visual_reviewer"]["model"] = "agnes/agnes-2.5-flash"
    provenance["roles"]["editor"]["model"] = "opencode/mimo-v2.5-free"
    provenance["roles"]["final_reviewer"]["model"] = "deepseek/deepseek-v4-flash"
    # 旧证据模型（已弃用）≠ 配置模型 → 应警告但不阻断
    provenance["roles"]["reviewer"]["model"] = "sensenova/glm-5.2"
    (tmp_path / "REVIEW_EXECUTION_EVIDENCE.json").write_text(json.dumps(provenance), encoding="utf-8")

    result = QualityGate(tmp_path).check_review_evidence("full")

    assert result["ok"] is True, "软校验不得阻断"
    assert len(result.get("warnings", [])) == 1
    assert "glm-5.2" in result["warnings"][0] and "mimo-v2.5-free" in result["warnings"][0]






def test_visual_verdict_requires_status_field(tmp_path):
    """视觉审查裁定缺少 status 字段时门禁必须 FAIL（禁止伪装通过）。"""
    _write_review_files(tmp_path)
    # 模拟旧版视觉裁定：无 status 字段
    (tmp_path / "VISUAL_REVIEW_VERDICT.json").write_text(
        '{"findings": [], "fatal_count": 0}', encoding="utf-8"
    )
    hashes = {
        "reviewer": hashlib.sha256((tmp_path / "COMP_REVIEW_VERDICT.json").read_bytes()).hexdigest(),
        "visual_reviewer": hashlib.sha256((tmp_path / "VISUAL_REVIEW_VERDICT.json").read_bytes()).hexdigest(),
        "editor": hashlib.sha256((tmp_path / "EDITOR_CHANGELOG.md").read_bytes()).hexdigest(),
        "final_reviewer": hashlib.sha256((tmp_path / "FINAL_REVIEW_VERDICT.json").read_bytes()).hexdigest(),
    }
    (tmp_path / "REVIEW_EXECUTION_EVIDENCE.json").write_text(json.dumps(_provenance(hashes)), encoding="utf-8")

    # VISUAL_REVIEW_VERDICT.json 缺 status 字段 → full 模式 FAIL
    result = QualityGate(tmp_path).check_review_evidence("full")
    assert result["ok"] is False
    assert "status" in result["reason"]

    # 补上 status=pass → 通过
    (tmp_path / "VISUAL_REVIEW_VERDICT.json").write_text(
        '{"findings": [], "fatal_count": 0, "status": "pass"}', encoding="utf-8"
    )
    hashes["visual_reviewer"] = hashlib.sha256((tmp_path / "VISUAL_REVIEW_VERDICT.json").read_bytes()).hexdigest()
    (tmp_path / "REVIEW_EXECUTION_EVIDENCE.json").write_text(json.dumps(_provenance(hashes)), encoding="utf-8")
    result = QualityGate(tmp_path).check_review_evidence("full")
    assert result["ok"] is True


def test_visual_verdict_status_unavailable_blocks_pass(tmp_path):
    """视觉 API 不可用时 status=unavailable，不得伪装成 pass 通过门禁。"""
    _write_review_files(tmp_path)
    (tmp_path / "VISUAL_REVIEW_VERDICT.json").write_text(
        '{"findings": [], "fatal_count": 0, "status": "unavailable"}', encoding="utf-8"
    )
    hashes = {
        "reviewer": hashlib.sha256((tmp_path / "COMP_REVIEW_VERDICT.json").read_bytes()).hexdigest(),
        "visual_reviewer": hashlib.sha256((tmp_path / "VISUAL_REVIEW_VERDICT.json").read_bytes()).hexdigest(),
        "editor": hashlib.sha256((tmp_path / "EDITOR_CHANGELOG.md").read_bytes()).hexdigest(),
        "final_reviewer": hashlib.sha256((tmp_path / "FINAL_REVIEW_VERDICT.json").read_bytes()).hexdigest(),
    }
    (tmp_path / "REVIEW_EXECUTION_EVIDENCE.json").write_text(json.dumps(_provenance(hashes)), encoding="utf-8")

    result = QualityGate(tmp_path).check_review_evidence("full")

    assert result["ok"] is False
    assert "unavailable" in result["reason"] or "未通过" in result["reason"]


def test_auto_mode_does_not_silently_downgrade_partial_multi_role_review(tmp_path):
    """auto 模式：只生成了部分多角色文件时不得静默降级为 solo。"""
    (tmp_path / "COMP_REVIEW.md").write_text("# Review", encoding="utf-8")
    (tmp_path / "COMP_REVIEW_VERDICT.json").write_text('{"findings": [], "fatal_count": 0}', encoding="utf-8")
    (tmp_path / "VISUAL_REVIEW.md").write_text("# Visual", encoding="utf-8")  # 只补了一个视觉报告

    result = QualityGate(tmp_path).check_review_evidence("auto")

    assert result["ok"] is False
    assert result["mode"] == "full"  # 不能降级为 solo


def test_literature_gate_counts_only_body_citations_in_pdf(tmp_path):
    """PDF 路径：参考文献列表自身的 [n] 编号不得算作正文引用。"""
    import fitz  # noqa: F401
    paper = tmp_path / "paper"
    literature = tmp_path / "literature"
    paper.mkdir()
    literature.mkdir()
    (tmp_path / "LITERATURE.md").write_text("# Literature\n", encoding="utf-8")
    (literature / "search_evidence.json").write_text(json.dumps([
        {"records": [{"key": "a", "doi": "10.1000/a"}]}
    ]), encoding="utf-8")
    (paper / "references.bib").write_text(
        "@article{a,title={A},doi={10.1000/a}}", encoding="utf-8"
    )

    # 用 fitz 生成真实 PDF：正文含 [1]，参考文献区含 [1]-[9]
    # （fitz 默认字体不支持中文，参考文献标题用英文 References）
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Body cites [1] here.")
    page.insert_text((72, 120), "References")
    for i in range(1, 10):
        page.insert_text((72, 150 + i * 30), f"[{i}] Fake reference {i}")
    pdf_path = paper / "main.pdf"
    doc.save(str(pdf_path))
    doc.close()

    result = QualityGate(tmp_path).check_literature_evidence()

    assert result["ok"] is True
    assert result["citations"] == 1  # 只有正文的 [1] 被计数


def test_literature_gate_rejects_pdf_with_ref_list_only(tmp_path):
    """PDF 中只有参考文献列表编号、正文零引用时门禁 FAIL。"""
    import fitz
    paper = tmp_path / "paper"
    literature = tmp_path / "literature"
    paper.mkdir()
    literature.mkdir()
    (tmp_path / "LITERATURE.md").write_text("# Literature\n", encoding="utf-8")
    (literature / "search_evidence.json").write_text(json.dumps([
        {"records": [{"key": "a", "doi": "10.1000/a"}]}
    ]), encoding="utf-8")
    (paper / "references.bib").write_text(
        "@article{a,title={A},doi={10.1000/a}}", encoding="utf-8"
    )

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Body text without citations.")
    page.insert_text((72, 120), "References")
    page.insert_text((72, 150), "[1] Fake reference")
    pdf_path = paper / "main.pdf"
    doc.save(str(pdf_path))
    doc.close()

    result = QualityGate(tmp_path).check_literature_evidence()

    assert result["ok"] is False
    assert "citation" in result["reason"].lower()

def test_reviewer_client_retries_on_rate_limit(tmp_path, monkeypatch):
    """reviewer_client.call_api 对 429 指数退避重试，复核不会因限流永久失败。"""
    import sys as _sys
    tools_dir = ROOT / "tools"
    if str(tools_dir) not in _sys.path:
        _sys.path.insert(0, str(tools_dir))
    import reviewer_client
    import http.client as _hc
    import json as _json

    class FakeResponse:
        def __init__(self, status, body):
            self.status = status
            self._body = body
        def read(self):
            return self._body

    calls = {"n": 0}

    class FakeConn:
        def __init__(self, *a, **k):
            pass
        def request(self, *a, **k):
            calls["n"] += 1
        def getresponse(self):
            if calls["n"] <= 2:
                return FakeResponse(429, b'{"error":"rate limited"}')
            return FakeResponse(200, _json.dumps({"choices": [{"message": {"content": "复核结果OK"}}]}).encode())
        def close(self):
            pass

    monkeypatch.setattr(reviewer_client.http.client, "HTTPSConnection", FakeConn)
    monkeypatch.setattr(reviewer_client.http.client, "HTTPConnection", FakeConn)

    result = reviewer_client.call_api(
        base_url="https://fake.example.com/v1", api_key="k",
        model="agnes-2.5-flash", messages=[{"role": "user", "content": "复核"}], timeout=5,
    )
    assert calls["n"] == 3, "429 应触发 2 次重试"
    assert result == "复核结果OK"


def test_role_agent_falls_back_across_providers(monkeypatch):
    """RoleAgent._call_llm 主 provider 失败后应 fallback 到备用 provider。"""
    from engine.quality_gates import RoleAgent
    import engine.quality_gates as qg
    import http.client as _hc

    class FakeResponse:
        def __init__(self, status, body):
            self.status = status
            self._body = body
        def read(self):
            return self._body

    attempts = {"n": 0}

    class FakeConn:
        def __init__(self, *a, **k):
            pass
        def request(self, *a, **k):
            attempts["n"] += 1
        def getresponse(self):
            if attempts["n"] < 2:  # 第一次调用（主 provider）失败
                return FakeResponse(500, b'{"error":"boom"}')
            return FakeResponse(200, json.dumps({"choices": [{"message": {"content": "fallback成功"}}]}).encode())
        def close(self):
            pass

    monkeypatch.setattr(_hc, "HTTPSConnection", FakeConn)
    monkeypatch.setattr(_hc, "HTTPConnection", FakeConn)
    # 构造：主 provider 无效 → fallback 到 SENSENOVA
    agent = RoleAgent(api_key="k1", base_url="https://primary.example.com/v1", model="m1")
    monkeypatch.setattr(qg, "env_get", lambda k, d="": {
        "SENSENOVA_BASE_URL": "https://sensenova.example.com/v1",
        "SENSENOVA_API_KEY": "k2",
        "SENSENOVA_MODEL": "deepseek-v4-flash",
    }.get(k, d))

    result = agent.call("reviewer", "请复核")
    assert "fallback成功" in result
    assert attempts["n"] >= 2, "应尝试主 provider + fallback provider"
