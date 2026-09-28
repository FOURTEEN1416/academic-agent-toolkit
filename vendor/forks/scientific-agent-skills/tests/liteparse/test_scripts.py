"""Tests for the liteparse batch directory parser.

Parsing is liteparse's job; the script owns file discovery, serialisation, and
error containment. All three are testable with a stub parser -- and the third
matters most: a batch run over a hundred documents must not abort because one
of them is corrupt.

`parse_one` names its output from the source *stem*, so two sources whose stems
collide overwrite each other. That is pinned below as current behaviour rather
than asserted to be safe.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import pytest

import skill_contract

SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills" / "liteparse"
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

pytest.importorskip("liteparse", reason="liteparse scripts import liteparse")

import batch_parse_dir  # noqa: E402

CliHelpTests = skill_contract.cli.help_test_case(SKILL_ROOT)


def text_item(text: str = "hello"):
    return SimpleNamespace(
        text=text,
        x=1.0,
        y=2.0,
        width=3.0,
        height=4.0,
        font_name="Helvetica",
        font_size=12.0,
        confidence=0.99,
    )


def parse_result(text: str = "hello"):
    page = SimpleNamespace(
        page_num=1, width=612.0, height=792.0, text=text, text_items=[text_item(text)]
    )
    return SimpleNamespace(text=text, pages=[page])


class StubParser:
    """Stands in for LiteParse; raises for any source named `broken*`."""

    def __init__(self) -> None:
        self.seen: list[Path] = []

    def parse(self, path: Path):
        self.seen.append(path)
        if path.stem.startswith("broken"):
            raise RuntimeError("unreadable document")
        return parse_result(f"contents of {path.name}")


class ExtensionTests(unittest.TestCase):
    def test_the_default_set_is_lowercase_and_dotted(self) -> None:
        self.assertTrue(batch_parse_dir.DEFAULT_EXTENSIONS)
        for extension in batch_parse_dir.DEFAULT_EXTENSIONS:
            with self.subTest(extension=extension):
                self.assertTrue(extension.startswith("."))
                self.assertEqual(extension, extension.lower())

    def test_the_documented_document_and_image_families_are_covered(self) -> None:
        defaults = batch_parse_dir.DEFAULT_EXTENSIONS
        for extension in (".pdf", ".docx", ".xlsx", ".pptx", ".csv", ".png", ".tiff"):
            with self.subTest(extension=extension):
                self.assertIn(extension, defaults)


class DiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.root = Path(self._temporary.name)

    def touch(self, relative: str) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
        return path

    def _found(self, **kwargs) -> list[str]:
        kwargs.setdefault("recursive", False)
        kwargs.setdefault("extension", None)
        return [path.name for path in batch_parse_dir.iter_files(self.root, **kwargs)]

    def test_only_supported_extensions_are_yielded(self) -> None:
        self.touch("a.pdf")
        self.touch("b.docx")
        self.touch("c.exe")
        self.assertEqual(self._found(), ["a.pdf", "b.docx"])

    def test_matching_is_case_insensitive(self) -> None:
        self.touch("SCAN.PDF")
        self.assertEqual(self._found(), ["SCAN.PDF"])

    def test_an_explicit_extension_narrows_the_selection(self) -> None:
        self.touch("a.pdf")
        self.touch("b.docx")
        self.assertEqual(self._found(extension=".pdf"), ["a.pdf"])

    def test_an_explicit_extension_is_matched_case_insensitively(self) -> None:
        self.touch("a.PDF")
        self.assertEqual(self._found(extension=".PdF"), ["a.PDF"])

    def test_recursion_is_opt_in(self) -> None:
        self.touch("top.pdf")
        self.touch("nested/deep.pdf")
        self.assertEqual(self._found(), ["top.pdf"])
        self.assertEqual(sorted(self._found(recursive=True)), ["deep.pdf", "top.pdf"])

    def test_directories_are_skipped(self) -> None:
        (self.root / "folder.pdf").mkdir()
        self.assertEqual(self._found(), [])

    def test_the_order_is_deterministic(self) -> None:
        for name in ("c.pdf", "a.pdf", "b.pdf"):
            self.touch(name)
        self.assertEqual(self._found(), ["a.pdf", "b.pdf", "c.pdf"])


class SerialisationTests(unittest.TestCase):
    def test_a_result_becomes_a_json_serialisable_dictionary(self) -> None:
        payload = batch_parse_dir._result_to_dict(parse_result("body text"))
        json.dumps(payload)
        self.assertEqual(payload["text"], "body text")
        self.assertEqual(len(payload["pages"]), 1)

    def test_page_geometry_and_text_items_survive(self) -> None:
        page = batch_parse_dir._result_to_dict(parse_result())["pages"][0]
        self.assertEqual(page["page_num"], 1)
        self.assertEqual(page["width"], 612.0)
        self.assertEqual(len(page["text_items"]), 1)

    def test_a_text_item_keeps_its_position_font_and_confidence(self) -> None:
        item = batch_parse_dir._text_item_dict(text_item("word"))
        self.assertEqual(
            set(item),
            {"text", "x", "y", "width", "height", "font_name", "font_size", "confidence"},
        )
        self.assertEqual(item["text"], "word")
        self.assertEqual(item["font_name"], "Helvetica")
        self.assertEqual(item["confidence"], 0.99)


class ParseOneTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.root = Path(self._temporary.name)
        self.output = self.root / "out"
        self.output.mkdir()
        self.parser = StubParser()

    def test_text_output_writes_the_plain_text(self) -> None:
        ok, source, message = batch_parse_dir.parse_one(
            self.parser, Path("paper.pdf"), self.output, "text"
        )
        self.assertTrue(ok)
        self.assertIn("paper.txt", message)
        self.assertEqual(
            (self.output / "paper.txt").read_text(encoding="utf-8"),
            "contents of paper.pdf",
        )

    def test_json_output_writes_the_structured_result(self) -> None:
        ok, _, message = batch_parse_dir.parse_one(
            self.parser, Path("paper.pdf"), self.output, "json"
        )
        self.assertTrue(ok)
        self.assertIn("paper.json", message)
        payload = json.loads((self.output / "paper.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["text"], "contents of paper.pdf")
        self.assertIn("pages", payload)

    def test_a_failing_document_is_reported_not_raised(self) -> None:
        # One corrupt file must not abort a hundred-document batch.
        ok, source, message = batch_parse_dir.parse_one(
            self.parser, Path("broken.pdf"), self.output, "text"
        )
        self.assertFalse(ok)
        self.assertEqual(source, "broken.pdf")
        self.assertIn("unreadable document", message)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_the_output_name_comes_from_the_source_stem(self) -> None:
        # Consequence: report.pdf and report.docx both write report.txt.
        batch_parse_dir.parse_one(self.parser, Path("report.pdf"), self.output, "text")
        batch_parse_dir.parse_one(self.parser, Path("report.docx"), self.output, "text")
        self.assertEqual(
            [path.name for path in self.output.iterdir()], ["report.txt"]
        )
        self.assertEqual(
            (self.output / "report.txt").read_text(encoding="utf-8"),
            "contents of report.docx",
        )

    def test_an_unknown_format_falls_back_to_text(self) -> None:
        batch_parse_dir.parse_one(self.parser, Path("a.pdf"), self.output, "yaml")
        self.assertTrue((self.output / "a.txt").is_file())


if __name__ == "__main__":
    unittest.main()
