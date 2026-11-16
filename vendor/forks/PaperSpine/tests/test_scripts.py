from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


def run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


class ScriptSmokeTests(unittest.TestCase):
    def test_latex_guard_passes_valid_fixture(self) -> None:
        result = run_script(
            "src/scripts/latex_guard.py",
            str(FIXTURES / "mini_paper.tex"),
            "--bib",
            str(FIXTURES / "references.bib"),
            "--markdown",
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("Errors: 0", result.stdout)

    def test_latex_guard_rejects_serialized_double_backslashes(self) -> None:
        # A JSON/Python-escaped source can render as a PDF of visible TeX text;
        # reject it before any renderer or package receipt can accept it.
        with tempfile.TemporaryDirectory() as tmp:
            tex = Path(tmp) / "serialized.tex"
            tex.write_text(
                "\\\\documentclass{article}\n"
                "\\\\begin{document}\n"
                "\\\\end{document}\n",
                encoding="utf-8",
            )
            result = run_script("src/scripts/latex_guard.py", str(tex), "--markdown")
            self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
            self.assertIn("serialized-command", result.stdout)

    def test_latex_guard_respects_venue_and_explicit_numeric_citation_style(self) -> None:
        # Venue style may use author-year; explicit numeric-brackets must still
        # reject those same markers instead of silently accepting mixed styles.
        with tempfile.TemporaryDirectory() as tmp:
            tex = Path(tmp) / "ay.tex"
            tex.write_text(
                r"""\documentclass{article}
\title{Author Year Citation Test}
\begin{document}
\maketitle
\section{Introduction}
Prior work (Smith et al., 2019) and (Jones and Lee, 2021) studied this problem.
\end{document}
""",
                encoding="utf-8",
            )
            result = run_script("src/scripts/latex_guard.py", str(tex), "--markdown")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertNotIn("Author-year citation", result.stdout)
            numeric = run_script(
                "src/scripts/latex_guard.py", str(tex),
                "--citation-style", "numeric-brackets", "--markdown",
            )
            self.assertEqual(numeric.returncode, 1, numeric.stderr + numeric.stdout)
            self.assertIn("Author-year citation", numeric.stdout)

    def test_latex_guard_flags_literal_bracket_citations_without_cite(self) -> None:
        # Regression: in-text [n] typed as literal text with an uncited
        # thebibliography is inert (no linkage); the guard must hard-fail it.
        with tempfile.TemporaryDirectory() as tmp:
            tex = Path(tmp) / "dead.tex"
            tex.write_text(
                r"""\documentclass{article}
\title{Dead Citations}
\begin{document}
\maketitle
\section{Introduction}
Retrieval-augmented generation was introduced [1] and surveyed [2].
\begin{thebibliography}{9}
\bibitem{a} Lewis P, et al. RAG. NeurIPS, 2020.
\bibitem{b} Gao Y, et al. A Survey. arXiv, 2023.
\end{thebibliography}
\end{document}
""",
                encoding="utf-8",
            )
            result = run_script("src/scripts/latex_guard.py", str(tex), "--markdown")
            self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
            self.assertIn("citation-linkage", result.stdout)

    def test_latex_guard_accepts_cite_linked_citations(self) -> None:
        # Counterpart: \cite{key} + thebibliography is properly linked -> no
        # citation-linkage error (numeric style still renders as [1]).
        with tempfile.TemporaryDirectory() as tmp:
            tex = Path(tmp) / "linked.tex"
            tex.write_text(
                r"""\documentclass{article}
\title{Linked Citations}
\begin{document}
\maketitle
\section{Introduction}
Retrieval-augmented generation was introduced \cite{a} and surveyed \cite{b}.
\begin{thebibliography}{9}
\bibitem{a} Lewis P, et al. RAG. NeurIPS, 2020.
\bibitem{b} Gao Y, et al. A Survey. arXiv, 2023.
\end{thebibliography}
\end{document}
""",
                encoding="utf-8",
            )
            result = run_script("src/scripts/latex_guard.py", str(tex), "--markdown")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertNotIn("citation-linkage", result.stdout)

    def test_latex_guard_flags_citation_number_exceeding_bibliography(self) -> None:
        # Numbering desync: a literal [9] with only 2 reference entries.
        with tempfile.TemporaryDirectory() as tmp:
            tex = Path(tmp) / "desync.tex"
            tex.write_text(
                r"""\documentclass{article}
\title{Desync}
\begin{document}
\maketitle
\section{Introduction}
This cites work [9] beyond the list.
\begin{thebibliography}{9}
\bibitem{a} One. 2020.
\bibitem{b} Two. 2021.
\end{thebibliography}
\end{document}
""",
                encoding="utf-8",
            )
            result = run_script("src/scripts/latex_guard.py", str(tex), "--markdown")
            self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
            self.assertIn("out of sync", result.stdout)

    def test_citation_bank_reference_format_is_case_insensitive(self) -> None:
        # Regression: has_reference_format matched only capital-P "Proceedings"/
        # "Journal"/"arXiv", so a legitimate lowercase channel label like
        # "Conference proceedings" was wrongly treated as missing a reference.
        sys.path.insert(0, str(ROOT / "src" / "scripts"))
        from citation_bank_check import has_reference_format  # noqa: PLC0415

        self.assertTrue(has_reference_format(["C1", "Conference proceedings", "2023"]))
        self.assertTrue(has_reference_format(["C2", "arxiv:2305.14314"]))
        self.assertTrue(has_reference_format(["C3", "Journal of ML"]))
        self.assertFalse(has_reference_format(["C4", "just a claim sentence."]))

    def test_section_economy_is_advisory_by_default(self) -> None:
        # Section count guides balanced editorial judgment but does not hard-fail it.
        with tempfile.TemporaryDirectory() as tmp:
            body = "\n".join(
                f"\\section{{S{i}}}\nParagraph one of section {i}. " + ("content " * 40)
                for i in range(1, 9)
            )
            tex = Path(tmp) / "bloated.tex"
            tex.write_text(
                "\\documentclass{article}\n\\title{Bloat}\n\\begin{document}\n\\maketitle\n"
                + body
                + "\n\\end{document}\n",
                encoding="utf-8",
            )
            result = run_script("src/scripts/section_economy_check.py", str(tex), "--markdown")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("PASS_WITH_ADVISORIES", result.stdout)
            self.assertIn("orientation value", result.stdout)

    def test_section_economy_can_be_enforced_in_strict_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            body = "\n".join(
                f"\\section{{S{i}}}\nParagraph one of section {i}. " + ("content " * 40)
                for i in range(1, 9)
            )
            tex = Path(tmp) / "main.tex"
            tex.write_text(
                "\\documentclass{article}\n\\title{Bloat}\n\\begin{document}\n\\maketitle\n"
                + body
                + "\n\\end{document}\n",
                encoding="utf-8",
            )
            result = run_script(
                "src/scripts/section_economy_check.py", str(tex), "--markdown", "--enforce"
            )
            self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
            self.assertIn("Status: FAIL", result.stdout)

    def test_section_economy_passes_within_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            body = "\n".join(
                f"\\section{{S{i}}}\nParagraph of section {i}. " + ("content " * 40)
                for i in range(1, 6)
            )
            tex = Path(tmp) / "lean.tex"
            tex.write_text(
                "\\documentclass{article}\n\\title{Lean}\n\\begin{document}\n\\maketitle\n"
                + body
                + "\n\\end{document}\n",
                encoding="utf-8",
            )
            result = run_script("src/scripts/section_economy_check.py", str(tex), "--markdown")
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("Status: PASS", result.stdout)

    def test_style_metrics_reports_sections(self) -> None:
        result = run_script("src/scripts/style_metrics.py", str(FIXTURES / "mini_paper.tex"), "--markdown")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("# Style Metrics", result.stdout)
        self.assertIn("Introduction", result.stdout)

    def test_revision_audit_reports_similarity(self) -> None:
        result = run_script(
            "src/scripts/revision_audit.py",
            str(FIXTURES / "mini_paper.tex"),
            str(FIXTURES / "mini_paper_revised.tex"),
            "--markdown",
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("# Revision Audit", result.stdout)
        self.assertIn("Near-identical revised paragraphs", result.stdout)

    def test_reference_inventory_indexes_local_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            refs = base / "refs"
            refs.mkdir()
            (refs / "paper.pdf").write_bytes(b"%PDF-1.4\n")
            (refs / "notes.txt").write_text("local reference notes", encoding="utf-8")
            out = base / "out"
            result = run_script(
                "src/scripts/reference_inventory.py",
                str(refs),
                "--output-dir",
                str(out),
                "--mode",
                "specified_paths",
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            index = out / "reference_materials" / "source_index.md"
            self.assertTrue(index.exists())
            text = index.read_text(encoding="utf-8")
            self.assertIn("specified_paths", text)
            self.assertIn(str(refs / "paper.pdf"), text)

    def test_citation_bank_check_enforces_candidate_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bank = Path(tmp) / "citation_support_bank.md"
            lines = [
                "# Citation Support Bank",
                "",
                "| Candidate ID | Reference/BibTeX | Year | Recency | Supports Section | Support Claim Sentence | Why This Paper Fits | Source |",
                "|---|---|---|---|---|---|---|---|",
            ]
            for index in range(1, 61):
                lines.append(
                    f"| C{index:03d} | @article{{ref{index}, year={{2024}}, doi={{10.0000/ref{index}}}}} | 2024 | recent | Introduction | "
                    f"This paper supports one specific manuscript sentence about the literature context and prevents unsupported claims. | "
                    f"It fits the same-field or adjacent-field context needed for background and discussion. | REF{index:03d} |"
                )
            bank.write_text("\n".join(lines), encoding="utf-8")
            result = run_script(
                "src/scripts/citation_bank_check.py",
                str(bank),
                "--target-count",
                "20",
                "--markdown",
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("Status: PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
