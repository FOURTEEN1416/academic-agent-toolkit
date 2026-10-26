"""P4-6 主产物收口：contract_tier 分档 + primary_parseable 正反例。

台账 P4-6 验收：
- 交付档 check_min_size 禁用 rglob 兜底（声明 primary_output 缺失不得被大 md 救回）；
- legacy 调用仍可用兜底（默认档位不改既有调用方语义）；
- 非法 JSON 产物 → parseable 失败；
- 单文件 tex（assembly_faces==[]）main 非空 → parseable 通过。

本文件同时钉死默认参数为 legacy、未知档位显式报错、以及新判据在 severity
注册表中的档位（blocking）——避免「新增检查但未登记」被静默兜底。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.quality_gates import (  # noqa: E402
    CONTRACT_TIERS,
    QualityGate,
    resolve_check_severity,
    unregistered_check_names,
)


def _big_markdown(workspace: Path, name: str = "notes.md", size: int = 12000) -> Path:
    path = workspace / name
    path.write_text("# notes\n" + ("x" * size), encoding="utf-8")
    return path


# ── 档位语义与 min_size 兜底 ───────────────────────────────────────────

def test_default_contract_tier_is_legacy(monkeypatch):
    """run_all 默认档位必须是 legacy：改默认值会打断既有调用方。"""
    captured = {}
    original = QualityGate.check_min_size

    def spy(self, skill_name, primary_output, contract_tier="legacy"):
        captured["tier"] = contract_tier
        return original(self, skill_name, primary_output, contract_tier)

    monkeypatch.setattr(QualityGate, "check_min_size", spy)
    QualityGate(Path(".")).run_all("comp-code", declared_outputs=["RESULTS.md"])
    assert captured["tier"] == "legacy"
    assert "legacy" in CONTRACT_TIERS


def test_unknown_contract_tier_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="contract_tier"):
        QualityGate(tmp_path).run_all("demo", contract_tier="strict")


def test_delivery_tier_min_size_rejects_rglob_fallback(tmp_path):
    _big_markdown(tmp_path)
    gate = QualityGate(tmp_path)

    delivery = gate.check_min_size("comp-paper-zh", None, contract_tier="delivery")
    assert delivery["ok"] is False, delivery
    assert "rglob" in delivery["reason"]

    legacy = gate.check_min_size("comp-paper-zh", None, contract_tier="legacy")
    assert legacy["ok"] is True, legacy


def test_delivery_tier_declared_primary_is_not_rescued_by_big_markdown(tmp_path):
    """声明 primary_output=paper/main.pdf 只放一个大 md → min_size 失败。"""
    _big_markdown(tmp_path)
    gate = QualityGate(tmp_path)
    for tier in ("delivery", "legacy"):
        result = gate.check_min_size("comp-paper-zh", "paper/main.pdf", contract_tier=tier)
        assert result["ok"] is False, (tier, result)
        assert "paper/main.pdf" in result["reason"]


def test_run_all_min_size_uses_delivery_tier(tmp_path):
    _big_markdown(tmp_path)
    report = QualityGate(tmp_path).run_all(
        "comp-paper-zh", declared_outputs=["paper/main.tex"],
        primary_output="paper/main.tex", contract_tier="delivery")
    assert report["ok"] is False
    assert report["checks"]["min_size"]["ok"] is False
    assert "paper/main.tex" in report["checks"]["min_size"]["reason"]


# ── primary_parseable：挂载时机 ────────────────────────────────────────

def test_parseable_check_mounts_only_in_delivery_tier(tmp_path):
    (tmp_path / "AUDIT_REPORT.json").write_text("{not json", encoding="utf-8")
    gate = QualityGate(tmp_path)

    legacy = gate.run_all("demo", declared_outputs=["AUDIT_REPORT.json"], contract_tier="legacy")
    assert "primary_parseable" not in legacy["checks"], legacy["checks"].keys()

    delivery = gate.run_all("demo", declared_outputs=["AUDIT_REPORT.json"],
                            contract_tier="delivery")
    assert "primary_parseable" in delivery["checks"]
    assert delivery["checks"]["primary_parseable"]["ok"] is False
    assert delivery["ok"] is False


def test_unsupported_primary_extension_is_explicitly_skipped(tmp_path):
    (tmp_path / "RESULTS.md").write_text("result ledger", encoding="utf-8")
    result = QualityGate(tmp_path).check_primary_parseable("RESULTS.md")
    assert result["ok"] is True
    assert result["skipped"] is True


def test_parseable_is_registered_blocking():
    assert resolve_check_severity("primary_parseable") == "blocking"
    assert unregistered_check_names(["primary_parseable"]) == []


# ── primary_parseable：JSON ────────────────────────────────────────────

def test_invalid_json_primary_fails_parseable(tmp_path):
    (tmp_path / "AUDIT_REPORT.json").write_text("{not json", encoding="utf-8")
    result = QualityGate(tmp_path).check_primary_parseable("AUDIT_REPORT.json")
    assert result["ok"] is False
    assert "JSON" in result["reason"]

    empty = QualityGate(tmp_path)
    (tmp_path / "AUDIT_REPORT.json").write_text("", encoding="utf-8")
    assert empty.check_primary_parseable("AUDIT_REPORT.json")["ok"] is False


def test_valid_json_primary_passes_parseable(tmp_path):
    (tmp_path / "AUDIT_REPORT.json").write_text(
        json.dumps({"delivery_decision": "eligible"}, ensure_ascii=False), encoding="utf-8")
    result = QualityGate(tmp_path).check_primary_parseable("AUDIT_REPORT.json")
    assert result["ok"] is True and result["kind"] == "json"


def test_missing_primary_is_reported_not_silently_passed(tmp_path):
    result = QualityGate(tmp_path).check_primary_parseable("paper/main.pdf")
    assert result["ok"] is False
    assert "paper/main.pdf" in result["reason"]


# ── primary_parseable：TeX（V10 口径：main 非空 OR 装配面非空） ────────

def test_single_file_tex_with_nonempty_main_passes(tmp_path):
    (tmp_path / "paper").mkdir()
    (tmp_path / "paper" / "main.tex").write_text("\\section{正文} 结论", encoding="utf-8")
    result = QualityGate(tmp_path).check_primary_parseable("paper/main.tex")
    assert result["ok"] is True, result
    assert result["assembly_faces"] == 0  # 单文件论文：装配面为空不得误杀
    assert result["main_nonempty"] is True


def test_empty_tex_without_assembly_fails(tmp_path):
    (tmp_path / "paper").mkdir()
    (tmp_path / "paper" / "main.tex").write_text("  \n\t\n", encoding="utf-8")
    result = QualityGate(tmp_path).check_primary_parseable("paper/main.tex")
    assert result["ok"] is False
    assert result["main_nonempty"] is False


def test_modular_main_assembles_sections(tmp_path):
    (tmp_path / "paper" / "sections").mkdir(parents=True)
    (tmp_path / "paper" / "main.tex").write_text(
        "\\documentclass{article}\\begin{document}\\input{sections/intro}\\end{document}",
        encoding="utf-8")
    (tmp_path / "paper" / "sections" / "intro.tex").write_text("真实正文", encoding="utf-8")
    result = QualityGate(tmp_path).check_primary_parseable("paper/main.tex")
    assert result["ok"] is True, result
    assert result["assembly_faces"] == 1


def test_run_all_delivery_mounts_tex_parseable(tmp_path):
    (tmp_path / "paper").mkdir()
    (tmp_path / "paper" / "main.tex").write_text("\\section{正文}", encoding="utf-8")
    report = QualityGate(tmp_path).run_all(
        "comp-paper-zh", declared_outputs=["paper/main.tex"],
        primary_output="paper/main.tex", contract_tier="delivery")
    assert report["checks"]["primary_parseable"]["ok"] is True
    # 内容体量不足仍由 min_size 挡——可解析不等于达标，两个判据各管一段。
    assert report["checks"]["min_size"]["ok"] is False


# ── primary_parseable：PDF ─────────────────────────────────────────────

def test_pdf_without_header_fails_parseable(tmp_path):
    (tmp_path / "paper").mkdir()
    (tmp_path / "paper" / "main.pdf").write_bytes(b"not a pdf at all")
    result = QualityGate(tmp_path).check_primary_parseable("paper/main.pdf")
    assert result["ok"] is False
    assert "PDF 文件头" in result["reason"]


def test_header_only_corrupt_pdf_is_unknown_not_pass(tmp_path):
    (tmp_path / "paper").mkdir()
    (tmp_path / "paper" / "main.pdf").write_bytes(b"%PDF-1.4\ngarbage\n")
    result = QualityGate(tmp_path).check_primary_parseable("paper/main.pdf")
    assert result["ok"] is False
    assert result.get("status") == "unknown"


def test_real_pdf_passes_parseable(tmp_path):
    pymupdf = pytest.importorskip("pymupdf")
    (tmp_path / "paper").mkdir()
    pdf_path = tmp_path / "paper" / "main.pdf"
    document = pymupdf.open()
    document.new_page()
    document.save(str(pdf_path))
    document.close()
    result = QualityGate(tmp_path).check_primary_parseable("paper/main.pdf")
    assert result["ok"] is True, result
    assert result["pages"] == 1
