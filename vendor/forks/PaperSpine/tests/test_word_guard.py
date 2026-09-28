from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def make_docx(path: Path, paragraphs: list[str], images: bool = False) -> None:
    body = "".join(
        f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for text in paragraphs
    )
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    )
    types = '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>'
    with zipfile.ZipFile(path, "w") as docx:
        docx.writestr("[Content_Types].xml", types)
        docx.writestr("word/document.xml", document)
        if images:
            docx.writestr("word/media/image1.png", b"\x89PNG\r\n\x1a\n")


def run_guard(docx_path: Path, min_chars: int = 50) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "src/scripts/word_guard.py", str(docx_path),
         "--markdown", "--min-chars", str(min_chars)],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )


class WordGuardTests(unittest.TestCase):
    def test_valid_docx_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docx = Path(tmp) / "paper.docx"
            make_docx(docx, ["This is a generated paragraph with enough text. " * 10])
            result = run_guard(docx, min_chars=100)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("Status: PASS", result.stdout)

    def test_placeholder_docx_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docx = Path(tmp) / "paper.docx"
            make_docx(docx, ["TODO replace this section with real content. " * 10])
            result = run_guard(docx, min_chars=50)
            self.assertEqual(result.returncode, 1)
            self.assertIn("placeholder", result.stdout)

    def test_empty_docx_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docx = Path(tmp) / "paper.docx"
            make_docx(docx, [])
            result = run_guard(docx, min_chars=10)
            self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
            self.assertIn("no non-empty paragraphs", result.stdout)

    def test_short_text_below_min_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docx = Path(tmp) / "paper.docx"
            make_docx(docx, ["Short."])
            result = run_guard(docx, min_chars=200)
            self.assertEqual(result.returncode, 1)
            self.assertIn("too short", result.stdout)

    def test_corrupt_zip_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docx = Path(tmp) / "paper.docx"
            docx.write_text("not a zip file", encoding="utf-8")
            result = run_guard(docx)
            self.assertEqual(result.returncode, 1)
            self.assertIn("not a valid zip", result.stdout)

    def test_missing_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docx = Path(tmp) / "nonexistent.docx"
            result = run_guard(docx)
            self.assertEqual(result.returncode, 1)

    def test_non_docx_extension_warns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docx = Path(tmp) / "paper.pdf"
            make_docx(docx, ["Content here. " * 15])
            result = run_guard(docx)
            self.assertIn("file extension", result.stdout)

    def test_images_without_text_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docx = Path(tmp) / "paper.docx"
            make_docx(docx, [], images=True)
            result = run_guard(docx, min_chars=10)
            self.assertEqual(result.returncode, 1)
            self.assertIn("Images found", result.stdout)
            self.assertIn("no non-empty paragraphs", result.stdout)

    def test_chinese_text_passes_with_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docx = Path(tmp) / "paper.docx"
            paragraphs = [
                "本文提出了一种新的轨迹对齐知识蒸馏方法，用于高效文本到图像扩散模型。" * 8,
                "实验结果表明，学生模型在仅需约三分之一参数量的情况下，" * 8,
            ]
            make_docx(docx, paragraphs)
            result = run_guard(docx, min_chars=100)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_chinese_garbled_text_warns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docx = Path(tmp) / "paper.docx"
            garbled = "鍚堢悊鐨勫紩鐢ㄦ牸寮? 浠ョ爺绌惰儗鏅? " * 6
            make_docx(docx, [garbled])
            result = run_guard(docx, min_chars=100)
            self.assertIn(result.returncode, (0, 1))  # may pass or fail depending on threshold

    def test_missing_document_xml_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docx = Path(tmp) / "paper.docx"
            types = '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>'
            with zipfile.ZipFile(docx, "w") as z:
                z.writestr("[Content_Types].xml", types)
            # No word/document.xml
            result = run_guard(docx, min_chars=10)
            self.assertEqual(result.returncode, 1)
            self.assertIn("missing word/document.xml", result.stdout)

    def test_normal_english_paper_content_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docx = Path(tmp) / "paper.docx"
            paragraphs = [
                "We propose a novel approach to trajectory-aligned knowledge distillation. " * 10,
                "Experimental results demonstrate significant improvements over baseline methods. " * 10,
                "The method achieves state-of-the-art performance on standard benchmarks. " * 10,
            ]
            make_docx(docx, paragraphs)
            result = run_guard(docx, min_chars=200)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)


    def test_leaked_latex_commands_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docx = Path(tmp) / "paper.docx"
            make_docx(docx, [
                "As shown by prior work \\cite{smith2020}, the method is effective. " * 6,
                "See \\ref{fig:overview} for the architecture diagram. " * 6,
            ])
            result = run_guard(docx, min_chars=50)
            self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
            self.assertIn("Unrendered LaTeX commands", result.stdout)

    def test_citeproc_leftover_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docx = Path(tmp) / "paper.docx"
            make_docx(docx, [
                "Recent advances [@smith2020] improved the baseline substantially. " * 6,
            ])
            result = run_guard(docx, min_chars=50)
            self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
            self.assertIn("Unresolved citation markers", result.stdout)

    def test_raw_inline_math_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docx = Path(tmp) / "paper.docx"
            make_docx(docx, [
                "The loss is defined as $\\alpha + \\beta$ over all samples in the batch. " * 6,
            ])
            result = run_guard(docx, min_chars=50)
            self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
            self.assertIn("Raw inline LaTeX math", result.stdout)

    def test_currency_dollar_not_flagged_as_math(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docx = Path(tmp) / "paper.docx"
            make_docx(docx, [
                "The project raised $5 million in funding for the new lab facility. " * 6,
            ])
            result = run_guard(docx, min_chars=50)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_custom_macro_with_argument_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docx = Path(tmp) / "paper.docx"
            make_docx(docx, [
                "The result \\mymetric{0.93} exceeds all prior baselines by a wide margin. " * 6,
            ])
            result = run_guard(docx, min_chars=50)
            self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
            self.assertIn("Unrendered LaTeX commands", result.stdout)

    def test_broken_crossref_marker_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docx = Path(tmp) / "paper.docx"
            make_docx(docx, [
                "The architecture is summarized in Figure [?] of the methods section. " * 6,
            ])
            result = run_guard(docx, min_chars=50)
            self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
            self.assertIn("Broken cross-references", result.stdout)

    def test_subscript_math_without_backslash_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docx = Path(tmp) / "paper.docx"
            make_docx(docx, [
                "The hidden state $h_t$ updates at each step over the full sequence length. " * 6,
            ])
            result = run_guard(docx, min_chars=50)
            self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
            self.assertIn("Raw inline LaTeX math", result.stdout)

    def test_currency_with_underscore_identifier_not_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docx = Path(tmp) / "paper.docx"
            make_docx(docx, [
                "Each file_name row costs $5 to process and $10 to archive in the system. " * 6,
            ])
            result = run_guard(docx, min_chars=50)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_numeric_bibstyle_rendered_authordate_warns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docx = Path(tmp) / "paper.docx"
            (Path(tmp) / "main.tex").write_text(
                "\\documentclass{article}\\bibliographystyle{ieeetr}\\begin{document}x\\end{document}",
                encoding="utf-8")
            make_docx(docx, [
                "As shown by prior work (Devlin et al. 2019) the method is effective overall. " * 6,
            ])
            result = run_guard(docx, min_chars=50)
            self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
            self.assertIn("Citation style mismatch", result.stdout)

    def test_numeric_bibstyle_with_numeric_citations_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docx = Path(tmp) / "paper.docx"
            (Path(tmp) / "main.tex").write_text(
                "\\bibliographystyle{plain}", encoding="utf-8")
            make_docx(docx, [
                "As shown by prior work [1] the method is effective over the full benchmark suite. " * 6,
            ])
            result = run_guard(docx, min_chars=50)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_authordate_bibstyle_does_not_warn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docx = Path(tmp) / "paper.docx"
            (Path(tmp) / "main.tex").write_text(
                "\\bibliographystyle{plainnat}", encoding="utf-8")
            make_docx(docx, [
                "As shown by prior work (Devlin et al. 2019) the method is effective overall. " * 6,
            ])
            result = run_guard(docx, min_chars=50)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_author_year_citation_without_tex_fails(self) -> None:
        # Regression: a docx rendered author-year with no source .tex used to pass
        # silently. The skill's default rule is plain numeric [1].
        with tempfile.TemporaryDirectory() as tmp:
            docx = Path(tmp) / "paper.docx"
            make_docx(docx, [
                "We build on prior work (Smith et al., 2020) to improve the baseline accuracy. " * 6,
            ])
            result = run_guard(docx, min_chars=50)
            self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
            self.assertIn("Author-year citation", result.stdout)

    def test_docx_starting_with_abstract_without_title_fails(self) -> None:
        # Regression: word_guard used to skip past a leading 'Abstract' wrapper and
        # accept the abstract body as the title. The Word output must OPEN with the title.
        with tempfile.TemporaryDirectory() as tmp:
            docx = Path(tmp) / "paper.docx"
            make_docx(docx, [
                "Abstract",
                "This work studies trajectory alignment for efficient diffusion model distillation. " * 6,
                "Introduction",
                "Diffusion models are expensive to deploy in production settings at scale. " * 6,
            ])
            result = run_guard(docx, min_chars=50)
            self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
            self.assertIn("section/wrapper heading", result.stdout)

    def test_fix_fonts_temp_is_beside_docx_not_cross_drive(self) -> None:
        # Regression: fix_docx_fonts must create its temp in the docx's OWN dir.
        # A system-temp temp + os.replace fails across drives on Windows
        # (WinError 17) when the project is on a different drive than %TEMP%.
        src = (ROOT / "src" / "scripts" / "word_guard.py").read_text(encoding="utf-8")
        self.assertIn("dir=str(docx_path.parent)", src)
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "sub"
            d.mkdir()
            docx = d / "paper.docx"
            make_docx(docx, ["Title paragraph with enough text to check. " * 20])
            res = subprocess.run(
                [sys.executable, "src/scripts/word_guard.py", str(docx), "--fix-fonts", "--language", "en"],
                cwd=ROOT, text=True, capture_output=True, check=False,
            )
            self.assertNotIn("WinError 17", res.stdout + res.stderr)
            self.assertNotIn("Traceback", res.stdout + res.stderr)
            self.assertEqual([p.name for p in d.glob("tmp*.docx")], [])

    def test_extract_title_from_tex_drops_linebreaks(self) -> None:
        # Regression: \title{A \\ B} kept the literal '\\' in the extracted title,
        # which then never matched the docx where '\\' renders as a line break.
        sys.path.insert(0, str(ROOT / "src" / "scripts"))
        from word_guard import extract_title_from_tex  # noqa: PLC0415

        with tempfile.TemporaryDirectory() as tmp:
            tex = Path(tmp) / "main.tex"
            tex.write_text(
                "\\title{Alpha Beta Gamma \\\\[2mm] Delta Epsilon Study}\n",
                encoding="utf-8",
            )
            self.assertEqual(
                extract_title_from_tex(tex), "Alpha Beta Gamma Delta Epsilon Study"
            )

    def test_title_with_latex_linebreak_matches_split_paragraphs(self) -> None:
        # Regression: a \title{...} with a '\\' line break renders as TWO docx
        # paragraphs; the title check used to FAIL because the extracted expected
        # title still carried the literal '\\'. End-to-end via --tex.
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            docx = d / "paper.docx"
            make_docx(docx, [
                "Parameter-Efficient Fine-Tuning",
                "for Multilingual Sequence Labeling Tasks",
                "Abstract",
                "This work studies parameter-efficient adaptation across languages. " * 6,
            ])
            tex = d / "main.tex"
            tex.write_text(
                "\\title{Parameter-Efficient Fine-Tuning \\\\ for Multilingual Sequence Labeling Tasks}\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, "src/scripts/word_guard.py", str(docx),
                 "--tex", str(tex), "--language", "en", "--markdown", "--min-chars", "50"],
                cwd=ROOT, text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertNotIn("not found in first 5 paragraphs", result.stdout)


if __name__ == "__main__":
    unittest.main()
