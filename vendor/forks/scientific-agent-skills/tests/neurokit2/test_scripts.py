#!/usr/bin/env python3
"""Dependency-free and pinned-runtime tests for NeuroKit2 skill helpers."""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills" / "neurokit2"
SCRIPTS = SKILL_ROOT / "scripts"
REFERENCES = SKILL_ROOT / "references"
sys.path.insert(0, str(SCRIPTS))

import _common
import ecg_hrv_pipeline
import eda_pipeline
import generate_synthetic
import inspect_signal
import plan_epochs
import validate_multimodal

HAS_NEUROKIT2 = importlib.util.find_spec("neurokit2") is not None


def run_script(
    name: str,
    *arguments: str,
    cwd: Path | None = None,
    without_site_packages: bool = True,
) -> subprocess.CompletedProcess[str]:
    command = [sys.executable]
    if without_site_packages:
        command.append("-S")
    command.extend([str(SCRIPTS / name), *arguments])
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


class SafetyAndManifestTests(unittest.TestCase):
    def test_scripts_parse_without_dynamic_execution_or_network_imports(self) -> None:
        banned_imports = {
            "aiohttp",
            "httpx",
            "importlib",
            "pickle",
            "requests",
            "socket",
            "subprocess",
            "urllib",
        }
        banned_calls = {"eval", "exec", "compile", "__import__"}
        shadow_names = {
            "csv.py",
            "json.py",
            "neurokit2.py",
            "numpy.py",
            "pandas.py",
            "pathlib.py",
            "pickle.py",
        }
        self.assertFalse({path.name for path in SCRIPTS.glob("*.py")} & shadow_names)
        for path in sorted(SCRIPTS.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    roots = {alias.name.split(".", 1)[0] for alias in node.names}
                    self.assertFalse(roots & banned_imports, path.name)
                if isinstance(node, ast.ImportFrom) and node.module:
                    self.assertNotIn(
                        node.module.split(".", 1)[0], banned_imports, path.name
                    )
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    self.assertNotIn(node.func.id, banned_calls, path.name)
                if isinstance(node, ast.Attribute):
                    self.assertFalse(
                        isinstance(node.value, ast.Name)
                        and node.value.id == "os"
                        and node.attr in {"environ", "getenv"},
                        path.name,
                    )
            self.assertNotIn(".pkl", path.read_text(encoding="utf-8").lower())

    def test_every_cli_help_works_without_site_packages(self) -> None:
        for path in sorted(SCRIPTS.glob("*.py")):
            if path.name == "_common.py":
                continue
            with self.subTest(script=path.name):
                result = run_script(path.name, "--help")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("usage:", result.stdout)
                self.assertNotIn("Traceback", result.stderr)

    def test_build_parsers_are_dependency_free(self) -> None:
        modules = (
            ecg_hrv_pipeline,
            eda_pipeline,
            generate_synthetic,
            inspect_signal,
            plan_epochs,
            validate_multimodal,
        )
        for module in modules:
            with self.subTest(module=module.__name__):
                self.assertIn("usage:", module.build_parser().format_help())

    def test_strict_local_io_rejects_url_symlink_duplicates_and_nan(self) -> None:
        with self.assertRaises(_common.CliError):
            _common.checked_input_file(
                "https://example.invalid/signal.csv",
                root=".",
                suffixes={".csv"},
                max_bytes=1024,
            )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            duplicate = root / "duplicate.json"
            duplicate.write_text('{"x": 1, "x": 2}', encoding="utf-8")
            with self.assertRaises(_common.CliError):
                _common.load_json_object(duplicate, root=root)
            nonfinite = root / "nonfinite.json"
            nonfinite.write_text('{"x": NaN}', encoding="utf-8")
            with self.assertRaises(_common.CliError):
                _common.load_json_object(nonfinite, root=root)
            real = root / "real.csv"
            real.write_text("x\n1\n", encoding="utf-8")
            link = root / "link.csv"
            try:
                link.symlink_to(real)
            except OSError:
                self.skipTest("symlinks unavailable")
            with self.assertRaises(_common.CliError):
                _common.checked_input_file(
                    link,
                    root=root,
                    suffixes={".csv"},
                    max_bytes=1024,
                )

    def test_skill_version_license_references_and_progressive_disclosure(self) -> None:
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertRegex(skill, r'\nmetadata:\n  version: "\d+\.\d+"\n')
        self.assertIn("license: MIT", skill)
        self.assertIn("compatibility:", skill)
        self.assertIn('uv pip install "neurokit2==0.2.13"', skill)
        self.assertNotIn("zipball", skill.lower())
        self.assertLess(len(skill.splitlines()), 500)
        self.assertEqual(
            {path.name for path in REFERENCES.glob("*.md")},
            {
                "bio_module.md",
                "complexity.md",
                "ecg_cardiac.md",
                "eda.md",
                "eeg.md",
                "emg.md",
                "eog.md",
                "epochs_events.md",
                "hrv.md",
                "ppg.md",
                "rsp.md",
                "signal_processing.md",
            },
        )
        for path in REFERENCES.glob("*.md"):
            self.assertIn("2026-07-23", path.read_text(encoding="utf-8"), path.name)


class DependencyFreeWorkflowTests(unittest.TestCase):
    def test_synthetic_generation_is_deterministic_and_inspectable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = run_script(
                "generate_synthetic.py",
                "--output",
                "first.csv",
                "--root",
                str(root),
                "--duration",
                "4",
                "--sampling-rate",
                "100",
                "--seed",
                "7",
            )
            second = run_script(
                "generate_synthetic.py",
                "--output",
                "second.csv",
                "--root",
                str(root),
                "--duration",
                "4",
                "--sampling-rate",
                "100",
                "--seed",
                "7",
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            first_report = json.loads(first.stdout)
            second_report = json.loads(second.stdout)
            self.assertEqual(first_report["sha256"], second_report["sha256"])
            self.assertEqual(
                (root / "first.csv").read_bytes(),
                (root / "second.csv").read_bytes(),
            )
            self.assertEqual(stat.S_IMODE((root / "first.csv").stat().st_mode), 0o600)
            self.assertNotIn(str(root), first.stdout)

            inspected = run_script(
                "inspect_signal.py",
                "--input",
                "first.csv",
                "--root",
                str(root),
                "--columns",
                "ecg,rsp,eda,trigger",
                "--time-column",
                "time_s",
                "--sampling-rate",
                "100",
                "--deidentified",
            )
            self.assertEqual(inspected.returncode, 0, inspected.stderr)
            report = json.loads(inspected.stdout)
            self.assertEqual(report["row_count"], 400)
            self.assertAlmostEqual(report["observed_sampling_rate_hz"], 100.0)
            self.assertEqual(report["path_redacted"], True)

    def test_epoch_planner_reports_sample_exact_boundaries(self) -> None:
        result = run_script(
            "plan_epochs.py",
            "--events",
            "100,500,990",
            "--sampling-rate",
            "100",
            "--recording-samples",
            "1000",
            "--epoch-start",
            "-0.2",
            "--epoch-end",
            "0.5",
            "--baseline-start",
            "-0.2",
            "--baseline-end",
            "0",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["window"]["sample_count"], 70)
        self.assertEqual(report["baseline"]["sample_count"], 20)
        self.assertTrue(report["events"][0]["complete"])
        self.assertFalse(report["events"][-1]["complete"])
        self.assertEqual(report["events"][-1]["pad_after_samples"], 40)

    def test_multimodal_validator_detects_resampling_need(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "ecg.csv").write_text(
                "time_s,ECG\n"
                + "".join(f"{index / 100:.2f},{index % 7}\n" for index in range(101)),
                encoding="utf-8",
            )
            (root / "rsp.csv").write_text(
                "time_s,RSP\n"
                + "".join(f"{index / 50:.2f},{index % 5}\n" for index in range(51)),
                encoding="utf-8",
            )
            manifest = {
                "schema_version": "1.0",
                "streams": [
                    {
                        "name": "ECG",
                        "path": "ecg.csv",
                        "value_column": "ECG",
                        "time_column": "time_s",
                        "sampling_rate_hz": 100,
                        "unit": "mV",
                    },
                    {
                        "name": "RSP",
                        "path": "rsp.csv",
                        "value_column": "RSP",
                        "time_column": "time_s",
                        "sampling_rate_hz": 50,
                        "unit": "a.u.",
                    },
                ],
                "alignment": {
                    "reference_stream": "ECG",
                    "synchronization": "shared_clock",
                    "max_start_offset_ms": 1,
                    "minimum_overlap_s": 0.9,
                },
            }
            (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            result = run_script(
                "validate_multimodal.py",
                "--manifest",
                "manifest.json",
                "--root",
                str(root),
                "--deidentified",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertTrue(report["valid"])
            self.assertFalse(report["bio_process_direct_input_compatible"])
            self.assertGreaterEqual(len(report["warnings"]), 1)


@unittest.skipUnless(HAS_NEUROKIT2, "pinned NeuroKit2 is not installed")
class PinnedNeuroKitSmokeTests(unittest.TestCase):
    def test_pinned_version_and_synthetic_ecg_pipeline(self) -> None:
        from importlib.metadata import version

        self.assertEqual(version("neurokit2"), _common.NEUROKIT2_VERSION)
        result = run_script(
            "ecg_hrv_pipeline.py",
            "--synthetic",
            "--sampling-rate",
            "250",
            "--duration",
            "30",
            "--heart-rate",
            "70",
            "--domains",
            "time",
            without_site_packages=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["neurokit2_version"], "0.2.13")
        self.assertGreater(report["detected_r_peaks"], 20)
        self.assertIn("ECG_Quality", report["output_schema_observed"]["signal_columns"])

    def test_pinned_synthetic_eda_pipeline(self) -> None:
        result = run_script(
            "eda_pipeline.py",
            "--synthetic",
            "--sampling-rate",
            "100",
            "--duration",
            "20",
            "--scr-number",
            "3",
            without_site_packages=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["neurokit2_version"], "0.2.13")
        self.assertIn("EDA_Phasic", report["output_schema_observed"]["signal_columns"])


if __name__ == "__main__":
    unittest.main()
