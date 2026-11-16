from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills/nature-figure/scripts/audit_svg_schematic.py"
NS = 'xmlns="http://www.w3.org/2000/svg"'


def svg(body: str, header: str = 'width="252pt" height="120pt" viewBox="0 0 252 120"') -> bytes:
    return f'<svg {NS} {header} font-size="6.5">{body}</svg>'.encode()


class SvgSchematicAuditTests(unittest.TestCase):
    def run_audit(self, data: bytes, *args: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "figure.svg"
            path.write_bytes(data)
            return subprocess.run(
                [sys.executable, str(SCRIPT), str(path), *args], capture_output=True, text=True
            )

    def test_compliant_figure_passes(self) -> None:
        result = self.run_audit(svg('<text x="10" y="20">Orchestrator</text>'))
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("verdict: PASS", result.stdout)

    def test_small_text_fails(self) -> None:
        result = self.run_audit(svg('<text x="10" y="20" font-size="4">tiny</text>'))
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("text.small", result.stdout)

    def test_viewbox_scale_is_applied(self) -> None:
        # 252 pt wide canvas drawn on a 504-unit viewBox halves a 10-unit font to 5 pt.
        data = svg('<text x="10" y="20" font-size="9">scaled</text>', 'width="252pt" height="120pt" viewBox="0 0 504 240"')
        self.assertEqual(self.run_audit(data).returncode, 1)

    def test_transform_scale_is_applied(self) -> None:
        data = svg('<g transform="scale(0.5)"><text x="10" y="20" font-size="8">half</text></g>')
        self.assertEqual(self.run_audit(data).returncode, 1)

    def test_too_wide_canvas_fails(self) -> None:
        data = svg('<text x="10" y="20">wide</text>', 'width="600pt" height="120pt" viewBox="0 0 600 120"')
        result = self.run_audit(data)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("canvas.width", result.stdout)

    def test_external_reference_and_script_fail(self) -> None:
        for body in (
            '<image href="https://example.com/a.png" x="0" y="0" width="5" height="5"/><text x="1" y="9">a</text>',
            '<script>1</script><text x="1" y="9">a</text>',
        ):
            self.assertEqual(self.run_audit(svg(body)).returncode, 1, body)

    def test_off_canvas_text_fails(self) -> None:
        self.assertEqual(self.run_audit(svg('<text x="400" y="20">gone</text>')).returncode, 1)

    def test_tspan_with_own_small_size_fails(self) -> None:
        data = svg('<text x="10" y="20" style="font-size:6pt">Hi<tspan style="font-size:2pt">x</tspan></text>')
        result = self.run_audit(data)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("text.small", result.stdout)

    def test_size_set_only_on_tspan_is_not_reported_as_missing(self) -> None:
        data = svg('<text x="10" y="20"><tspan style="font-size:6pt">Hi</tspan></text>')
        result = self.run_audit(data)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("text.size", result.stdout)

    def test_translate_moves_text_off_canvas(self) -> None:
        data = svg('<g transform="translate(300,0)"><text x="10" y="10" style="font-size:6pt">A</text></g>')
        result = self.run_audit(data)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("text.off-canvas", result.stdout)

    def test_translate_that_stays_on_canvas_passes(self) -> None:
        data = svg('<g transform="translate(100,50)"><text x="10" y="10" style="font-size:6pt">A</text></g>')
        self.assertEqual(self.run_audit(data).returncode, 0)

    def test_non_svg_and_doctype_are_not_auditable(self) -> None:
        self.assertEqual(self.run_audit(b"just text").returncode, 2)
        bomb = b'<!DOCTYPE svg [<!ENTITY a "x">]><svg xmlns="http://www.w3.org/2000/svg"><text>&a;</text></svg>'
        self.assertEqual(self.run_audit(bomb).returncode, 2)


if __name__ == "__main__":
    unittest.main()
