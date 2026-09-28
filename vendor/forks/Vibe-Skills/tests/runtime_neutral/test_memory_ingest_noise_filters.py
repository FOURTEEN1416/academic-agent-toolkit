from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock
from pathlib import Path
from typing import Any

from tests.runtime_neutral.live_contract_fixtures import (
    seed_live_document_contract as _seed_live_document_contract,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_DRIVER = REPO_ROOT / "scripts" / "runtime" / "workspace_memory_driver.py"

def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_workspace_driver_module():
    spec = importlib.util.spec_from_file_location("workspace_memory_driver_module", WORKSPACE_DRIVER)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_workspace_driver(
    *,
    lane: str,
    action: str,
    payload: dict[str, Any],
    repo_root: Path,
    session_root: Path,
    store_path: Path,
    project_key: str | None = None,
) -> dict[str, Any]:
    payload_path = session_root / f"{lane}-{action}-request.json"
    response_path = session_root / f"{lane}-{action}-response.json"
    _write_json(payload_path, payload)

    command = [
        sys.executable,
        str(WORKSPACE_DRIVER),
        "--lane",
        lane,
        "--action",
        action,
        "--repo-root",
        str(repo_root),
        "--session-root",
        str(session_root),
        "--store-path",
        str(store_path),
        "--payload-path",
        str(payload_path),
        "--response-path",
        str(response_path),
    ]
    if project_key:
        command.extend(["--project-key", project_key])

    subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(response_path.read_text(encoding="utf-8"))


class MemoryIngestNoiseFiltersTests(unittest.TestCase):
    def test_noise_only_ruflo_ingest_is_suppressed(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            temp_root = Path(tempdir)
            repo_root = temp_root / "workspace"
            session_root = temp_root / "session"
            repo_root.mkdir(parents=True, exist_ok=True)
            session_root.mkdir(parents=True, exist_ok=True)
            _seed_live_document_contract(repo_root)

            noisy_write = run_workspace_driver(
                lane="ruflo",
                action="write",
                payload={
                    "run_id": "run-noise-01",
                    "task": "telemetry heartbeat write",
                    "cards": [
                        {
                            "scope": "xl",
                            "summary": "telemetry heartbeat tmp write",
                            "items": ["telemetry: latency=4ms", "trace: heartbeat"],
                            "evidence_paths": ["/tmp/vibe/runtime-telemetry.log"],
                            "keywords": ["tmp", "telemetry", "heartbeat"],
                        }
                    ],
                },
                repo_root=repo_root,
                session_root=session_root,
                store_path=temp_root / "legacy-ruflo.jsonl",
                project_key="noise-filter-workspace",
            )
            self.assertEqual("guarded_noise_suppressed", noisy_write["status"])
            self.assertEqual(0, noisy_write["item_count"])
            self.assertEqual(1, noisy_write["suppressed_count"])

            noisy_read = run_workspace_driver(
                lane="ruflo",
                action="read",
                payload={"task": "telemetry heartbeat write", "top_k": 3},
                repo_root=repo_root,
                session_root=session_root,
                store_path=temp_root / "legacy-ruflo.jsonl",
                project_key="noise-filter-workspace",
            )
            self.assertEqual("backend_read_empty", noisy_read["status"])
            self.assertEqual(0, noisy_read["item_count"])

    def test_mixed_serena_ingest_keeps_signal_and_suppresses_noise(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            temp_root = Path(tempdir)
            repo_root = temp_root / "workspace"
            session_root = temp_root / "session"
            repo_root.mkdir(parents=True, exist_ok=True)
            session_root.mkdir(parents=True, exist_ok=True)
            _seed_live_document_contract(repo_root)

            mixed_write = run_workspace_driver(
                lane="serena",
                action="write",
                payload={
                    "decisions": [
                        {
                            "summary": "tmp telemetry",
                            "evidence_paths": ["/tmp/noise.txt"],
                            "keywords": ["tmp", "telemetry"],
                        },
                        {
                            "summary": "Approved decision: preserve compatibility shell around workspace broker.",
                            "evidence_paths": ["docs/requirements/frozen.md"],
                            "keywords": ["approved", "decision", "compatibility", "broker"],
                        },
                    ]
                },
                repo_root=repo_root,
                session_root=session_root,
                store_path=temp_root / "legacy-serena.jsonl",
                project_key="noise-filter-workspace",
            )
            self.assertEqual("backend_write_with_noise_suppressed", mixed_write["status"])
            self.assertEqual(1, mixed_write["item_count"])
            self.assertEqual(1, mixed_write["suppressed_count"])

            read_back = run_workspace_driver(
                lane="serena",
                action="read",
                payload={"task": "compatibility shell decision", "top_k": 3},
                repo_root=repo_root,
                session_root=session_root,
                store_path=temp_root / "legacy-serena.jsonl",
                project_key="noise-filter-workspace",
            )
            self.assertEqual("backend_read", read_back["status"])
            self.assertIn("compatibility shell", " ".join(read_back["items"]).lower())
            self.assertNotIn("tmp telemetry", " ".join(read_back["items"]).lower())

    def test_signal_only_serena_ingest_is_not_suppressed_by_stop_token_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            temp_root = Path(tempdir)
            repo_root = temp_root / "workspace"
            session_root = temp_root / "session"
            repo_root.mkdir(parents=True, exist_ok=True)
            session_root.mkdir(parents=True, exist_ok=True)
            _seed_live_document_contract(repo_root)

            write_result = run_workspace_driver(
                lane="serena",
                action="write",
                payload={
                    "decisions": [
                        {
                            "summary": "approved decision continuity",
                            "keywords": ["approved", "decision", "continuity"],
                            "evidence_paths": ["docs/design/workspace-memory-plane.md"],
                        }
                    ]
                },
                repo_root=repo_root,
                session_root=session_root,
                store_path=temp_root / "legacy-serena.jsonl",
                project_key="signal-only-workspace",
            )

            self.assertEqual("backend_write", write_result["status"])
            self.assertEqual(1, write_result["item_count"])
            self.assertEqual(0, write_result["suppressed_count"])

    def test_concurrent_writes_keep_both_records_in_workspace_plane(self) -> None:
        module = load_workspace_driver_module()

        with tempfile.TemporaryDirectory() as tempdir:
            temp_root = Path(tempdir)
            repo_root = temp_root / "workspace"
            session_root = temp_root / "session"
            repo_root.mkdir(parents=True, exist_ok=True)
            session_root.mkdir(parents=True, exist_ok=True)
            shutil.copytree(REPO_ROOT / "config", repo_root / "config")

            barrier = threading.Barrier(2)
            original_load_jsonl = module.load_jsonl
            failures: list[str] = []

            def synchronized_load_jsonl(path):
                snapshot = original_load_jsonl(path)
                try:
                    barrier.wait(timeout=0.5)
                except threading.BrokenBarrierError:
                    pass
                return snapshot

            def writer(name: str) -> None:
                try:
                    payload_path = session_root / f"{name}-request.json"
                    response_path = session_root / f"{name}-response.json"
                    _write_json(
                        payload_path,
                        {
                            "decisions": [
                                {
                                    "summary": f"Approved decision: preserve {name} continuity.",
                                    "keywords": ["approved", "decision", name],
                                    "evidence_paths": ["docs/design/workspace-memory-plane.md"],
                                }
                            ]
                        },
                    )
                    module.execute(
                        lane="serena",
                        action="write",
                        repo_root=repo_root,
                        payload_path=payload_path,
                        response_path=response_path,
                        project_key="atomic-workspace",
                        driver_mode="workspace_broker",
                    )
                except Exception as exc:  # pragma: no cover - surfaced by assertion
                    failures.append(str(exc))

            with mock.patch.object(module, "load_jsonl", side_effect=synchronized_load_jsonl):
                threads = [threading.Thread(target=writer, args=(name,)) for name in ("alpha", "beta")]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join(timeout=5)

            self.assertEqual([], failures)

            descriptor = module.ensure_workspace_descriptor(repo_root, policy_bundle=module.load_workspace_memory_policy_bundle(repo_root))
            plane_path = module.resolve_plane_path(descriptor)
            rows = original_load_jsonl(plane_path)

            self.assertEqual(2, len(rows))
            self.assertEqual(
                {
                    "Approved decision: preserve alpha continuity.",
                    "Approved decision: preserve beta continuity.",
                },
                {str(row.get("summary") or "") for row in rows},
            )


if __name__ == "__main__":
    unittest.main()
