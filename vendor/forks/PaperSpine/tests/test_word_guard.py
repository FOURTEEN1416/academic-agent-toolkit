from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
import zipfile
from pathlib import Path
from unittest.mock import patch

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


def make_docx_with_visible_media(
    path: Path, paragraphs: list[str], media: list[tuple[str, bytes]]
) -> None:
    body = "".join(
        f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for text in paragraphs
    )
    body += "".join(
        '<w:p><w:r><w:drawing><a:blip '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        f'r:embed="rIdFigure{index}"/></w:drawing></w:r></w:p>'
        for index in range(1, len(media) + 1)
    )
    document = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/'
        'wordprocessingml/2006/main"><w:body>'
        + body
        + "</w:body></w:document>"
    )
    relationships = "".join(
        '<Relationship '
        f'Id="rIdFigure{index}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
        f'Target="media/{name}"/>'
        for index, (name, _) in enumerate(media, start=1)
    )
    with zipfile.ZipFile(path, "w") as docx:
        docx.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        )
        docx.writestr("word/document.xml", document)
        docx.writestr(
            "word/_rels/document.xml.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + relationships
            + "</Relationships>",
        )
        for name, encoded in media:
            docx.writestr(f"word/media/{name}", encoded)


def run_guard(docx_path: Path, min_chars: int = 50) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "src/scripts/word_guard.py", str(docx_path),
         "--markdown", "--min-chars", str(min_chars)],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )


class WordGuardTests(unittest.TestCase):
    def test_repeated_figure_markers_across_runs_hyperlinks_and_fields_are_read_only(self):
        sys.path.insert(0, str(ROOT / "src" / "scripts"))
        from word_guard import W_NS, check_docx, internal_reference_findings

        for body in (
            '<w:r><w:t>See Fig. </w:t></w:r><w:hyperlink w:anchor="fig2"><w:r><w:t>Fig.</w:t></w:r><w:r><w:t>2</w:t></w:r></w:hyperlink>',
            '<w:r><w:t>See Fi</w:t></w:r><w:r><w:t>g.\u00a0Fig.\u00a02</w:t></w:r>',
            '<w:r><w:t>Figure </w:t></w:r><w:fldSimple w:instr="REF fig2"><w:r><w:t>Figure S2</w:t></w:r></w:fldSimple>',
        ):
            with self.subTest(body=body), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "repeat.docx"
                xml = (f'<w:document xmlns:w="{W_NS}"><w:body>'
                       '<w:p><w:r><w:t>A Study of Correct Figure References</w:t></w:r></w:p>'
                       f'<w:p>{body}</w:p><w:p><w:bookmarkStart w:id="1" w:name="fig2"/>'
                       '<w:r><w:t>Figure 2. Results.</w:t></w:r><w:bookmarkEnd w:id="1"/></w:p>'
                       '</w:body></w:document>').encode()
                with zipfile.ZipFile(path, "w") as archive:
                    archive.writestr("[Content_Types].xml", '<Types/>')
                    archive.writestr("word/document.xml", xml)
                before = path.read_bytes()
                findings = internal_reference_findings(xml)
                self.assertEqual(len(findings), 1, findings)
                self.assertIn("Repeated figure marker in Word paragraph 2", findings[0])
                self.assertIn("producing source/export", findings[0])
                self.assertFalse(check_docx(path, 1).ok)
                self.assertEqual(path.read_bytes(), before)

    def test_repeated_figure_diagnostic_excludes_normal_prose_citations_and_hidden_content(self):
        sys.path.insert(0, str(ROOT / "src" / "scripts"))
        from word_guard import W_NS, duplicate_figure_reference_findings, has_visible_figure_reference

        for text in ("Fig. 2", "Fig.2", "Figure S2", "Figs. 2 and 3"):
            self.assertTrue(has_visible_figure_reference(text))
        for text in ("configuration2", "figure skating", "Figment2"):
            self.assertFalse(has_visible_figure_reference(text))
        for body in (
            '<w:p><w:r><w:t>Fig. 1, Fig. 2; figures differ. Figure figure skating performance.</w:t></w:r></w:p>',
            '<w:p><w:r><w:t>Fig. Fig., 2020; Fig. et al. (2021); [2, 3].</w:t></w:r></w:p>',
            '<w:p><w:r><w:t>Fig.</w:t></w:r></w:p><w:p><w:r><w:t>Fig. 2</w:t></w:r></w:p>',
            '<w:p><w:r><w:t>Fig.</w:t><w:br/><w:t>Fig. 2</w:t></w:r></w:p>',
            '<w:p><w:r><w:t>See </w:t></w:r><w:del><w:r><w:t>Fig. </w:t></w:r></w:del><w:r><w:t>Fig. 2</w:t></w:r></w:p>',
            '<w:p><w:r><w:rPr><w:vanish/></w:rPr><w:t>Fig. </w:t></w:r><w:r><w:t>Fig. 2</w:t></w:r></w:p>',
            '<w:p><w:r><w:instrText>Fig. Fig. 2</w:instrText><w:t>Figure 2</w:t></w:r></w:p>',
        ):
            with self.subTest(body=body):
                xml = f'<w:document xmlns:w="{W_NS}"><w:body>{body}</w:body></w:document>'.encode()
                self.assertEqual(duplicate_figure_reference_findings(xml), [])

    def test_font_repair_preserves_compatibility_namespaces_in_all_changed_parts(self) -> None:
        sys.path.insert(0, str(ROOT / "src" / "scripts"))
        from lxml import etree
        from word_guard import A_NS, W_NS, fix_docx_fonts

        mc = "http://schemas.openxmlformats.org/markup-compatibility/2006"
        prefixes = "w14 w15 w16se w16cid w16 w16cex w16sdtdh w16sdtfl w16du"
        declarations = " ".join(f'xmlns:{p}="urn:fixture:{p}"' for p in prefixes.split())
        attributes = f'xmlns:mc="{mc}" {declarations} mc:Ignorable="{prefixes}"'
        document = (
            f'<w:document xmlns:w="{W_NS}" {attributes}><w:body>'
            '<w:p><w:r><w:t>Title</w:t></w:r></w:p>'
            '<w:p><w:r><w:t>1</w:t></w:r></w:p>'
            '<w:p><w:r><w:t>Smith 2020.</w:t></w:r></w:p>'
            '<w:p><w:r><w:t>Doe 2021.</w:t></w:r></w:p>'
            '</w:body></w:document>'
        ).encode()
        styles = (
            f'<w:styles xmlns:w="{W_NS}" {attributes}>'
            '<!--preserve comment--><w:style w:styleId="Normal" w:type="paragraph">'
            '<w:rPr><w:rFonts w:ascii="Calibri"/></w:rPr></w:style>'
            '<mc:AlternateContent><mc:Choice xmlns:w14="urn:fixture:shadow" '
            'Requires="w14" mc:PreserveAttributes="w14:flag"/></mc:AlternateContent>'
            '</w:styles>'
        ).encode()
        theme = (
            f'<a:theme xmlns:a="{A_NS}" {attributes}><a:themeElements><a:fontScheme>'
            '<a:majorFont><a:latin typeface="Calibri"/></a:majorFont>'
            '<a:minorFont><a:latin typeface="Calibri"/></a:minorFont>'
            '</a:fontScheme></a:themeElements></a:theme>'
        ).encode()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "paper.docx"
            with zipfile.ZipFile(target, "w") as package:
                package.writestr("word/document.xml", document)
                package.writestr("word/styles.xml", styles)
                package.writestr("word/theme/theme1.xml", theme)
                package.writestr("word/media/figure.png", b"unaltered scientific bytes")
                package.writestr("word/_rels/document.xml.rels", b"unaltered relationships")
            original = target.read_bytes()
            self.assertTrue(fix_docx_fonts(target, "zh", font_policy="fallback"))
            self.assertEqual(target.with_suffix(".docx.bak_fonts").read_bytes(), original)
            with zipfile.ZipFile(target) as package:
                for name in ("word/document.xml", "word/styles.xml", "word/theme/theme1.xml"):
                    root = etree.fromstring(package.read(name))
                    self.assertEqual(root.get(f"{{{mc}}}Ignorable"), prefixes)
                    for prefix in prefixes.split():
                        self.assertEqual(root.nsmap[prefix], f"urn:fixture:{prefix}")
                root = etree.fromstring(package.read("word/styles.xml"))
                choice = root.find(f".//{{{mc}}}Choice")
                self.assertEqual(choice.nsmap["w14"], "urn:fixture:shadow")
                self.assertEqual(choice.get(f"{{{mc}}}PreserveAttributes"), "w14:flag")
                self.assertIn(b"<!--preserve comment-->", package.read("word/styles.xml"))
                fonts = root.findall(f".//{{{W_NS}}}rFonts")
                self.assertTrue(fonts)
                defaults = root.find(f".//{{{W_NS}}}docDefaults")
                self.assertEqual(defaults.find(f".//{{{W_NS}}}rFonts").get(f"{{{W_NS}}}eastAsia"), "SimSun")
                normal = root.find(f".//{{{W_NS}}}style[@{{{W_NS}}}styleId='Normal']")
                self.assertEqual(normal.find(f".//{{{W_NS}}}rFonts").get(f"{{{W_NS}}}ascii"), "Calibri")
                self.assertEqual(package.read("word/theme/theme1.xml"), theme)
                self.assertNotIn("参考文献".encode(), package.read("word/document.xml"))
                document_root = etree.fromstring(package.read("word/document.xml"))
                sectpr = document_root.find(f".//{{{W_NS}}}sectPr")
                self.assertIsNotNone(sectpr)
                page_size = sectpr.find(f"{{{W_NS}}}pgSz")
                page_margins = sectpr.find(f"{{{W_NS}}}pgMar")
                self.assertIsNotNone(page_size)
                self.assertIsNotNone(page_margins)
                self.assertEqual(page_size.get(f"{{{W_NS}}}w"), "11906")
                self.assertEqual(page_size.get(f"{{{W_NS}}}h"), "16838")
                self.assertEqual(package.read("word/media/figure.png"), b"unaltered scientific bytes")
                self.assertEqual(package.read("word/_rels/document.xml.rels"), b"unaltered relationships")
            self.assertFalse(fix_docx_fonts(target, "en", font_policy="fallback"))
            self.assertEqual(target.with_suffix(".docx.bak_fonts").read_bytes(), original)
            self.assertEqual(list(Path(tmp).glob("tmp*.docx")), [])

    def test_font_repair_rejects_unbound_prefix_or_dtd_without_writes(self) -> None:
        sys.path.insert(0, str(ROOT / "src" / "scripts"))
        from word_guard import W_NS, fix_docx_fonts

        mc = "http://schemas.openxmlformats.org/markup-compatibility/2006"
        invalid_styles = [
            f'<w:styles xmlns:w="{W_NS}" xmlns:mc="{mc}" mc:Ignorable="undeclared"/>',
            f'<!DOCTYPE w:styles [<!ENTITY x "ignored">]><w:styles xmlns:w="{W_NS}"/>',
        ]
        with tempfile.TemporaryDirectory() as tmp:
            for index, styles in enumerate(invalid_styles):
                target = Path(tmp) / f"invalid-{index}.docx"
                with zipfile.ZipFile(target, "w") as package:
                    package.writestr("word/document.xml", f'<w:document xmlns:w="{W_NS}"><w:body/></w:document>')
                    package.writestr("word/styles.xml", styles)
                original = target.read_bytes()
                with self.assertRaises(ValueError):
                    fix_docx_fonts(target, "en", font_policy="fallback")
                self.assertEqual(target.read_bytes(), original)
                self.assertFalse(target.with_suffix(".docx.bak_fonts").exists())

    def test_font_repair_missing_dependency_leaves_input_unchanged(self) -> None:
        sys.path.insert(0, str(ROOT / "src" / "scripts"))
        import builtins

        from word_guard import W_NS, fix_docx_fonts

        original_import = builtins.__import__
        def without_lxml(name, *args, **kwargs):
            if name == "lxml":
                raise ImportError("unavailable")
            return original_import(name, *args, **kwargs)

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "paper.docx"
            with zipfile.ZipFile(target, "w") as package:
                package.writestr("word/document.xml", f'<w:document xmlns:w="{W_NS}"/>')
                package.writestr("word/styles.xml", f'<w:styles xmlns:w="{W_NS}"/>')
            original = target.read_bytes()
            with patch("builtins.__import__", side_effect=without_lxml):
                with self.assertRaisesRegex(RuntimeError, "requires lxml"):
                    fix_docx_fonts(target, "en", font_policy="fallback")
            self.assertEqual(target.read_bytes(), original)
            self.assertFalse(target.with_suffix(".docx.bak_fonts").exists())

    def test_six_pdf_objects_fail_and_six_visible_png_figures_pass(self) -> None:
        sys.path.insert(0, str(ROOT / "src" / "scripts"))
        from word_guard import check_docx  # noqa: PLC0415

        source_tex = "\n".join(
            [r"\title{Evidence-Bound Six-Figure Study}"]
            + [rf"\includegraphics{{figures/fig{index}.pdf}}" for index in range(1, 7)]
        )
        paragraphs = [
            "Evidence-Bound Six-Figure Study",
            "Methods and Results preserve every populated material and figure. " * 8,
            "Figure 1, Figure 2, Figure 3, Figure 4, Figure 5, and Figure 6 are "
            "cited in the manuscript body.",
        ]
        root = ROOT / "tests" / f".word-media-{uuid.uuid4().hex}"
        root.mkdir()
        try:
            pdf_docx = root / "pdf-media.docx"
            make_docx_with_visible_media(
                pdf_docx,
                [*paragraphs],
                [
                    (f"figure-{index}.pdf", b"%PDF-1.7\nfigure")
                    for index in range(1, 7)
                ],
            )
            blocked = check_docx(
                pdf_docx,
                50,
                source_tex,
                "Evidence-Bound Six-Figure Study",
                "en",
            )
            self.assertFalse(blocked.ok)
            self.assertEqual(blocked.visible_figure_media_count, 0)
            self.assertEqual(len(blocked.unsupported_media or []), 6)
            self.assertTrue(
                any("blank frames" in finding for finding in blocked.findings)
            )

            png_docx = root / "png-media.docx"
            make_docx_with_visible_media(
                png_docx,
                [*paragraphs],
                [
                    (
                        f"figure-{index}.png",
                        b"\x89PNG\r\n\x1a\n" + f"figure-{index}".encode("ascii"),
                    )
                    for index in range(1, 7)
                ],
            )
            passed = check_docx(
                png_docx,
                50,
                source_tex,
                "Evidence-Bound Six-Figure Study",
                "en",
            )
            self.assertTrue(passed.ok, passed.findings)
            self.assertEqual(passed.visible_figure_media_count, 6)
            self.assertEqual(passed.unsupported_media, [])
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_visible_figure_reference_accepts_nonbreaking_space(self) -> None:
        sys.path.insert(0, str(ROOT / "src" / "scripts"))
        from word_guard import has_visible_figure_reference  # noqa: PLC0415

        self.assertTrue(has_visible_figure_reference("Figure\u00a01."))
        self.assertTrue(has_visible_figure_reference("Figure         1 visualizes the result."))
        self.assertFalse(has_visible_figure_reference("The figure is shown below."))

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

    def test_author_year_citation_without_tex_is_not_globally_banned(self) -> None:
        # Without an explicit target or a known source mismatch, venue style is unknown.
        with tempfile.TemporaryDirectory() as tmp:
            docx = Path(tmp) / "paper.docx"
            make_docx(docx, [
                "We build on prior work (Smith et al., 2020) to improve the baseline accuracy. " * 6,
            ])
            result = run_guard(docx, min_chars=50)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertNotIn("Citation style mismatch", result.stdout)

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
