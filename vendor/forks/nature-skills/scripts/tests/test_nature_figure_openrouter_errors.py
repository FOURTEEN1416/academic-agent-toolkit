from __future__ import annotations

import argparse
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[2] / "skills/nature-figure/scripts/generate_openrouter_schematic.py"
SPEC = importlib.util.spec_from_file_location("generate_openrouter_schematic_test", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def make_args(outdir: str = ".") -> argparse.Namespace:
    return argparse.Namespace(
        api_key_env="TEST_OPENROUTER_KEY",
        api_url="http://127.0.0.1:9/",
        site_url="",
        app_name="",
        timeout=1,
        outdir=outdir,
        basename="fig",
        output_format="png",
    )


class OpenRouterErrorTests(unittest.TestCase):
    def test_request_timeout_is_a_clean_exit_not_a_traceback(self) -> None:
        with mock.patch.dict(os.environ, {"TEST_OPENROUTER_KEY": "x"}), mock.patch.object(
            MODULE.urllib.request, "urlopen", side_effect=TimeoutError("timed out")
        ):
            with self.assertRaises(SystemExit) as raised:
                MODULE.request_images({"model": "m"}, make_args())
        self.assertIn("Image request failed", str(raised.exception))

    def test_connection_reset_while_reading_is_a_clean_exit(self) -> None:
        with mock.patch.dict(os.environ, {"TEST_OPENROUTER_KEY": "x"}), mock.patch.object(
            MODULE.urllib.request, "urlopen", side_effect=ConnectionResetError("reset")
        ):
            with self.assertRaises(SystemExit):
                MODULE.request_images({"model": "m"}, make_args())

    def test_image_url_download_failure_is_a_clean_exit(self) -> None:
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            MODULE.urllib.request, "urlopen", side_effect=TimeoutError("timed out")
        ):
            with self.assertRaises(SystemExit) as raised:
                MODULE.save_outputs({"data": [{"url": "http://example.invalid/a.png"}]}, {}, make_args(directory))
        self.assertIn("Image download failed", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
