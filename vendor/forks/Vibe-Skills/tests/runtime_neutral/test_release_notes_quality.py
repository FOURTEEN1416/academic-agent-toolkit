from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "verify" / "runtime_neutral" / "release_notes_quality.py"


def load_module():
    spec = importlib.util.spec_from_file_location("runtime_neutral_release_notes_quality", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ReleaseNotesQualityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def _write_note(self, root: Path, name: str, body: str) -> Path:
        path = root / name
        path.write_text(body, encoding="utf-8")
        return path

    def test_good_release_note_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            note = self._write_note(
                root,
                "v1.0.0.md",
                "\n".join(
                    [
                        "# VCO Release v1.0.0",
                        "",
                        "- Date: 2026-03-30",
                        "- Commit(base): abc1234",
                        "",
                        "## Highlights",
                        "",
                        "- Added release operator closure.",
                        "",
                        "## Validation Notes",
                        "",
                        "- pytest -q tests/runtime_neutral/test_release_notes_quality.py",
                        "",
                        "## Migration Notes",
                        "",
                        "- No migration required.",
                        "",
                    ]
                ),
            )
            artifact = self.module.evaluate(root, [note])
            self.assertEqual("PASS", artifact["summary"]["gate_result"])
            self.assertTrue(artifact["notes"][0]["passes"])

    def test_todo_fails_quality_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            note = self._write_note(
                root,
                "v1.0.0.md",
                "# VCO Release v1.0.0\n\n## Highlights\n\n- TODO\n\n## Validation Notes\n\n- pending\n\n## Migration Notes\n\n- none\n",
            )
            artifact = self.module.evaluate(root, [note])
            self.assertEqual("FAIL", artifact["summary"]["gate_result"])
            self.assertEqual([5], artifact["notes"][0]["todo_lines"])

    def test_duplicate_and_missing_headings_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            note = self._write_note(
                root,
                "v1.0.0.md",
                "# VCO Release v1.0.0\n\n## Highlights\n\n- ok\n\n## Migration Notes\n\n- first\n\n## Migration Notes\n\n- second\n",
            )
            artifact = self.module.evaluate(root, [note])
            self.assertEqual("FAIL", artifact["summary"]["gate_result"])
            self.assertEqual(["## Migration Notes"], artifact["notes"][0]["duplicate_headings"])
            self.assertEqual(["## Validation Notes"], artifact["notes"][0]["missing_headings"])

    def test_write_artifacts_emits_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            note = self._write_note(
                root,
                "v1.0.0.md",
                "# VCO Release v1.0.0\n\n## Highlights\n\n- ok\n\n## Validation Notes\n\n- ok\n\n## Migration Notes\n\n- ok\n",
            )
            artifact = self.module.evaluate(root, [note])
            self.module.write_artifacts(root, artifact, tempdir)
            json_path = Path(tempdir) / "vibe-release-notes-quality-gate.json"
            md_path = Path(tempdir) / "vibe-release-notes-quality-gate.md"
            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual("PASS", payload["summary"]["gate_result"])


if __name__ == "__main__":
    unittest.main()
