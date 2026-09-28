from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class MaterialInventoryTests(unittest.TestCase):
    def test_inventory_classifies_common_materials(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "materials"
            output = Path(tmp) / "out"
            root.mkdir()
            for name in [
                "result_plot.png",
                "literature_review.pdf",
                "notes.docx",
                "draft.tex",
                "references.bib",
                "experiment_data.csv",
            ]:
                (root / name).write_bytes(b"x")

            result = subprocess.run(
                [
                    sys.executable,
                    "src/scripts/material_inventory.py",
                    str(root),
                    "--output-dir",
                    str(output),
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            data = json.loads((output / "source_inventory.json").read_text())
            by_name = {item["path"]: item for item in data}
            self.assertEqual(by_name["result_plot.png"]["file_type"], "image")
            self.assertEqual(by_name["literature_review.pdf"]["file_type"], "pdf")
            self.assertEqual(by_name["notes.docx"]["file_type"], "word_text")
            self.assertEqual(by_name["draft.tex"]["file_type"], "latex")
            self.assertEqual(by_name["experiment_data.csv"]["file_type"], "data")


if __name__ == "__main__":
    unittest.main()
