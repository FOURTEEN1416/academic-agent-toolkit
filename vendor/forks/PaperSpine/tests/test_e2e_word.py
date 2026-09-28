from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORD_GUARD = ROOT / "src" / "scripts" / "word_guard.py"

MAIN_TEX = r"""\documentclass{article}
\title{A Lightweight Method for Document Conversion Fidelity}
\author{Jane Doe and John Smith}
\begin{document}
\maketitle
\begin{abstract}
We evaluate a lightweight method for document conversion fidelity. The pipeline
is reproducible, inexpensive to run, and produces faithful output across the
evaluated configurations.
\end{abstract}
\section{Introduction}
This report evaluates a lightweight method for document conversion fidelity.
Prior work \cite{devlin2019} established strong baselines for language
understanding, and we build on that foundation in a controlled setting with a
reproducible pipeline and a small, well-documented configuration.
\section{Results}
Our experiments show consistent improvements across the evaluated
configurations, with no regressions observed on the held-out set. The approach
remains simple to reproduce and inexpensive to run end to end.
\bibliography{references}
\end{document}
"""

REFERENCES_BIB = """@article{devlin2019,
  title={BERT: Pre-training of Deep Bidirectional Transformers},
  author={Devlin, Jacob and Chang, Ming-Wei},
  journal={NAACL},
  year={2019}
}
"""


@unittest.skipUnless(shutil.which("pandoc"), "pandoc not installed")
class WordEndToEndTests(unittest.TestCase):
    """End-to-end: LaTeX -> pandoc docx -> word_guard, exercising the real chain.

    The Word build in PaperSpine V4 always runs word_guard with --fix-fonts, which
    normalizes the docx to Times New Roman and black headings (pandoc's default
    theme uses Aptos / colored headings) before validating. This mirrors the real
    pipeline: pandoc produces the docx, then word_guard fixes-and-checks it.
    """

    def test_build_docx_from_latex_and_validate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            final_paper = Path(tmp) / "final_paper"
            final_paper.mkdir(parents=True)
            (final_paper / "main.tex").write_text(MAIN_TEX, encoding="utf-8")
            (final_paper / "references.bib").write_text(REFERENCES_BIB, encoding="utf-8")
            docx = final_paper / "paper.docx"

            pandoc = subprocess.run(
                [
                    "pandoc", "main.tex", "-o", "paper.docx",
                    "--from", "latex", "--to", "docx",
                    "--resource-path=.", "--number-sections",
                    "--citeproc", "--bibliography=references.bib",
                ],
                cwd=final_paper, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertEqual(pandoc.returncode, 0, pandoc.stderr)
            self.assertTrue(docx.exists(), "pandoc did not produce paper.docx")
            self.assertGreater(docx.stat().st_size, 0)

            guard = subprocess.run(
                [sys.executable, str(WORD_GUARD), str(docx),
                 "--fix-fonts", "--language", "en", "--markdown"],
                cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertEqual(guard.returncode, 0, guard.stdout + guard.stderr)
            self.assertIn("Status: PASS", guard.stdout)


if __name__ == "__main__":
    unittest.main()
