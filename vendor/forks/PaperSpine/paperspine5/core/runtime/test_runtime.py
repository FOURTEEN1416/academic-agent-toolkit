from __future__ import annotations

import importlib.util
import io
import json
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[2]
RUNTIME_PATH = Path(__file__).with_name("paperspine5_runtime.py")
SPEC = importlib.util.spec_from_file_location("paperspine5_runtime", RUNTIME_PATH)
assert SPEC and SPEC.loader
runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class RuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.work = Path(tempfile.mkdtemp(prefix=".runtime-test-", dir=Path(__file__).resolve().parent))
        self.paper = self.work / "paper"
        self.figure = self.work / "figures"
        self.final = self.paper / "final_paper"
        self.job = self.work / "integration_job.json"
        write_json(
            self.job,
            {
                "schema_version": "1.0",
                "job_id": "runtime-smoke",
                "host": "codex",
                "project_root": str(ROOT),
                "paper": {
                    "output_dir": str(self.paper),
                    "progress_script": str(ROOT / "01_PaperSpine4" / "src" / "scripts" / "progress_check.py"),
                },
                "figure": {
                    "job_dir": str(self.figure),
                    "figmirror_cli": str(ROOT / "02_PaperFigure" / "01_FigMirror引擎" / "src" / "scripts" / "figmirror.py"),
                    "candidate_count": 2,
                },
                "assembly": {"final_paper_dir": str(self.final), "main_tex": str(self.final / "main.tex")},
                "workflow": {"allow_auto_selection": False},
            },
        )

    def tearDown(self) -> None:
        for server, thread in list(runtime._SERVERS.values()):
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        runtime._SERVERS.clear()
        shutil.rmtree(self.work)

    def test_health_and_all_tools_are_discoverable(self) -> None:
        result = runtime.health(ROOT)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(set(result["hosts"]), {"codex", "claude-code", "dsh", "standalone-skill"})
        response = runtime.handle_mcp({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}, ROOT)
        self.assertEqual(len(response["result"]["tools"]), 7)

    def test_mcp_status_configuration_and_workspace_lifecycle(self) -> None:
        status = runtime.handle_mcp(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "paperspine5_status", "arguments": {"job_path": str(self.job), "host": "dsh"}}},
            ROOT,
        )
        self.assertFalse(status["result"].get("isError", False), status)
        content = json.loads(status["result"]["content"][0]["text"])
        self.assertEqual(content["host_next"]["host"], "dsh")

        configuration = {
            "workflow": "build_from_materials",
            "scene": "journal",
            "target_name": "Synthetic PaperSpine5 host test",
        }
        saved = runtime.dispatch("save_configuration", {"job_path": str(self.job), "configuration": configuration}, ROOT)
        self.assertEqual(saved["status"], "OK")
        self.assertTrue((self.paper / "paper_spine_config.json").is_file())

        opened = runtime.dispatch("open_workspace", {"job_path": str(self.job)}, ROOT)
        self.assertEqual(opened["status"], "READY")
        with urlopen(opened["address"] + "api/snapshot", timeout=5) as response:
            snapshot = json.load(response)
        self.assertEqual(snapshot["job"]["job_id"], "runtime-smoke")

    def test_bridge_envelope_uses_same_dispatch(self) -> None:
        request = {
            "protocol": "paperspine5.host",
            "version": "0.1.0",
            "request_id": "bridge-1",
            "host": "standalone-skill",
            "action": "snapshot",
            "job_path": str(self.job),
            "payload": {},
        }
        output = io.StringIO()
        code = runtime.serve_bridge(ROOT, io.StringIO(json.dumps(request)), output)
        self.assertEqual(code, 0, output.getvalue())
        self.assertEqual(json.loads(output.getvalue())["result"]["host_next"]["host"], "standalone-skill")


if __name__ == "__main__":
    unittest.main()
