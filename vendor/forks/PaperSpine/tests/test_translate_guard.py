"""Tests for translate_guard.py."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "scripts"))
from translate_guard import (
    TranslationFinding,
    TranslationGuardReport,
    check_content_density,
    check_file_completeness,
    check_full_paper_coverage,
    check_manifest,
    check_structural_preservation,
    to_markdown,
)


def _make_fixture(**files: str) -> tuple[Path, Path]:
    tmp = Path(tempfile.mkdtemp())
    trans = tmp / "translation_zh"
    trans.mkdir()
    for name, content in files.items():
        p = tmp / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return tmp, trans


class TranslateGuardTests(unittest.TestCase):
    def test_report_blocked_with_blockers(self) -> None:
        report = TranslationGuardReport("test", "rewrite_existing", [
            TranslationFinding("T-001", "BLOCKER", "missing", "fix", "teach"),
        ])
        self.assertTrue(report.blocked)

    def test_report_not_blocked_with_only_warnings(self) -> None:
        report = TranslationGuardReport("test", "rewrite_existing", [
            TranslationFinding("T-001", "WARNING", "low density", "fix"),
        ])
        self.assertFalse(report.blocked)

    def test_check_file_completeness_detects_missing(self) -> None:
        out, trans = _make_fixture(**{"paper_spine_config.json": '{"workflow": "rewrite_existing"}'})
        config = {"workflow": "rewrite_existing"}
        findings = check_file_completeness(trans, out, config)
        self.assertTrue(any(f.severity == "BLOCKER" for f in findings))

    def test_check_file_completeness_all_present(self) -> None:
        config = {"workflow": "rewrite_existing"}
        files = {"paper_spine_config.json": json.dumps(config)}
        from translate_guard import TRANSLATION_COMMON, TRANSLATION_REWRITE
        for f in TRANSLATION_COMMON + TRANSLATION_REWRITE:
            files[f"translation_zh/{f}"] = "# translated"
        out, trans = _make_fixture(**files)
        findings = check_file_completeness(trans, out, config)
        self.assertTrue(any(f.id == "FILE-000" for f in findings))

    def test_check_structural_preservation_row_mismatch(self) -> None:
        import json as _json
        out, trans = _make_fixture(
            **{
                "paper_spine_config.json": _json.dumps({"workflow": "rewrite_existing"}),
                "writing_rationale_matrix.md": "| A | B |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |",
                "translation_zh/writing_rationale_matrix.zh.md": "| A | B |\n|---|---|\n| 1 | 2 |",
            }
        )
        findings = check_structural_preservation(trans, out)
        self.assertTrue(any("missing" in f.what.lower() for f in findings))

    def test_check_content_density_low_ratio(self) -> None:
        import json as _json
        en_text = "x " * 200
        zh_text = "y" * 50
        out, trans = _make_fixture(
            **{
                "paper_spine_config.json": _json.dumps({"workflow": "rewrite_existing"}),
                "research_dossier.md": en_text,
                "translation_zh/research_dossier.zh.md": zh_text,
            }
        )
        findings = check_content_density(trans, out)
        self.assertTrue(any("density" in f.what.lower() for f in findings))

    def test_check_full_paper_missing(self) -> None:
        out, trans = _make_fixture(**{"paper_spine_config.json": '{"workflow": "rewrite_existing"}'})
        findings = check_full_paper_coverage(trans, out)
        self.assertTrue(any("FULL-001" in f.id for f in findings))

    def test_check_full_paper_too_short(self) -> None:
        out, trans = _make_fixture(
            **{
                "paper_spine_config.json": '{"workflow": "rewrite_existing"}',
                "translation_zh/full_paper_translation.zh.md": "short",
            }
        )
        findings = check_full_paper_coverage(trans, out)
        self.assertTrue(any(f.severity == "BLOCKER" for f in findings))

    def test_check_full_paper_chinese_translation_not_blocked(self) -> None:
        # Regression: a complete natural Chinese translation matched none of the
        # English section keywords and was wrongly BLOCKED as missing every section.
        para = (
            "本文提出一种基于轨迹对齐的高效扩散模型知识蒸馏方法，"
            "通过在对齐的时间步上让学生模型匹配教师模型的采样轨迹，"
            "在显著降低参数量的同时保持生成质量并加快推理速度。"
        ) * 8
        zh = "\n\n".join([
            "# 基于轨迹对齐的高效扩散模型知识蒸馏",
            "## 摘要", para,
            "## 引言", para,
            "## 方法", para,
            "## 实验", para,
            "## 结果", para,
            "## 讨论", "本节讨论方法的局限与不足。" + para,
            "## 结论", para,
            "## 致谢", "感谢相关基金资助。",
            "## 附录", "图 1：整体架构示意（图注）。表 1：主要实验结果。",
        ])
        out, trans = _make_fixture(**{
            "paper_spine_config.json": '{"workflow": "rewrite_existing"}',
            "translation_zh/full_paper_translation.zh.md": zh,
        })
        findings = check_full_paper_coverage(trans, out)
        self.assertFalse(
            any(f.severity == "BLOCKER" for f in findings),
            [f"{f.id}:{f.what}" for f in findings],
        )

    def test_check_manifest_missing(self) -> None:
        out, trans = _make_fixture(**{"paper_spine_config.json": '{"workflow": "rewrite_existing"}'})
        findings = check_manifest(trans, {"workflow": "rewrite_existing"})
        self.assertTrue(any("MANIFEST-001" in f.id for f in findings))

    def test_check_manifest_reports_missing(self) -> None:
        out, trans = _make_fixture(
            **{
                "paper_spine_config.json": '{"workflow": "rewrite_existing"}',
                "translation_zh/manifest.md": "# Manifest\n\nmissing",
            }
        )
        findings = check_manifest(trans, {"workflow": "rewrite_existing"})
        self.assertTrue(any(f.severity == "BLOCKER" for f in findings))

    def test_to_markdown_includes_status(self) -> None:
        report = TranslationGuardReport("test", "rewrite_existing", [
            TranslationFinding("T-001", "BLOCKER", "what", "fix", "teaching"),
            TranslationFinding("T-000", "INFO", "all good", "", ""),
        ])
        md = to_markdown(report)
        self.assertIn("BLOCKED", md)
        self.assertIn("teaching", md)


if __name__ == "__main__":
    unittest.main()
