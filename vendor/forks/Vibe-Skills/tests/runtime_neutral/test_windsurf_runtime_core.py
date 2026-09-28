from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ADAPTER_REGISTRY_MODULE = REPO_ROOT / "packages" / "installer-core" / "src" / "vgo_installer" / "adapter_registry.py"
CONTRACTS_SRC = REPO_ROOT / "packages" / "contracts" / "src"
INSTALLER_CORE_SRC = REPO_ROOT / "packages" / "installer-core" / "src"


def _load_module(module_name: str, module_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def run_package_install(
    *,
    host: str,
    target_root: Path,
    profile: str = "full",
    extra_env: dict[str, str] | None = None,
) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(CONTRACTS_SRC), str(INSTALLER_CORE_SRC), env.get("PYTHONPATH", "")]).strip(os.pathsep)
    env.update(extra_env or {})
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "vgo_installer.install_runtime",
            "--repo-root",
            str(REPO_ROOT),
            "--target-root",
            str(target_root),
            "--host",
            host,
            "--profile",
            profile,
        ],
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )
    return result, json.loads(result.stdout)


class WindsurfRuntimeCoreTests(unittest.TestCase):
    EXPECTED_WRAPPER_SKILLS = ("vibe",)

    def test_adapter_registry_exposes_windsurf_parallel_root(self) -> None:
        registry = _load_module("installer_adapter_registry_windsurf", ADAPTER_REGISTRY_MODULE)
        payload = registry.resolve_adapter(REPO_ROOT, "windsurf")
        self.assertEqual("windsurf", payload["id"])
        self.assertEqual("runtime-core", payload["install_mode"])
        self.assertEqual(".agents", payload["default_target_root"]["rel"])
        self.assertEqual("shared-home", payload["default_target_root"]["kind"])

    def test_python_installer_uses_runtime_core_without_codex_host_state(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            target_root = Path(tempdir)
            _, payload = run_package_install(host="windsurf", target_root=target_root)

            self.assertEqual("windsurf", payload["host_id"])
            self.assertEqual("runtime-core", payload["install_mode"])
            self.assertIn("host_closure_path", payload)
            self.assertEqual(str(target_root.resolve()), payload["runtime_root"])
            self.assertEqual(str(target_root.resolve()), payload["host_bridge_root"])
            self.assertNotEqual(str(target_root.resolve()), payload["desired_shared_runtime_root"])
            self.assertEqual("legacy-host-root-override", payload["runtime_layout_mode"])
            self.assertTrue((target_root / "skills" / "vibe" / "SKILL.md").exists())
            self.assertFalse((target_root / "skills" / "vibe" / "bundled" / "skills").exists())
            for name in self.EXPECTED_WRAPPER_SKILLS:
                self.assertTrue((target_root / "skills" / name / "SKILL.md").exists())
            self.assertFalse((target_root / "skills" / "verification-before-completion").exists())
            self.assertTrue((target_root / ".vibeskills" / "host-settings.json").exists())
            self.assertTrue((target_root / ".vibeskills" / "host-closure.json").exists())
            self.assertFalse((target_root / "commands").exists())
            self.assertFalse((target_root / "global_workflows").exists())
            self.assertFalse((target_root / "mcp_config.json").exists())
            self.assertFalse((target_root / "settings.json").exists())
            self.assertFalse((target_root / "config" / "plugins-manifest.codex.json").exists())

    def test_shell_install_and_check_use_simplified_skills_dir_without_windsurf_sidecars(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            target_root = Path(tempdir)
            skills_dir = target_root / "skills"
            install_result = subprocess.run(
                [
                    "bash",
                    str(REPO_ROOT / "install.sh"),
                    "--skills-dir",
                    str(skills_dir),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            install_payload = json.loads(install_result.stdout)
            self.assertEqual("vibe-skill-install", install_payload["receipt_kind"])
            self.assertTrue((skills_dir / "vibe" / "SKILL.md").exists())
            self.assertTrue((skills_dir / "vibe" / ".vibeskills" / "install-receipt.json").exists())
            self.assertFalse((target_root / ".vibeskills" / "host-settings.json").exists())
            self.assertFalse((target_root / ".vibeskills" / "host-closure.json").exists())
            self.assertFalse((target_root / "commands").exists())
            self.assertFalse((target_root / "global_workflows").exists())
            self.assertFalse((target_root / "mcp_config.json").exists())
            self.assertFalse((target_root / "settings.json").exists())

            check_result = subprocess.run(
                [
                    "bash",
                    str(REPO_ROOT / "check.sh"),
                    "--skills-dir",
                    str(skills_dir),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            check_payload = json.loads(check_result.stdout)
            self.assertTrue(check_payload["ok"])

    def test_python_installer_can_split_runtime_root_into_shared_agents_home(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            bridge_root = Path(tempdir) / "host-root"
            shared_root = Path(tempdir) / "shared-agents"
            _, payload = run_package_install(
                host="windsurf",
                target_root=bridge_root,
                extra_env={"VIBE_AGENTS_HOME": str(shared_root)},
            )

            self.assertEqual(str(shared_root.resolve()), payload["runtime_root"])
            self.assertEqual(str(bridge_root.resolve()), payload["host_bridge_root"])
            self.assertEqual(str(shared_root.resolve()), payload["desired_shared_runtime_root"])
            self.assertEqual("split-shared-runtime", payload["runtime_layout_mode"])
            self.assertTrue((shared_root / "skills" / "vibe" / "SKILL.md").exists())
            self.assertTrue((bridge_root / "skills" / "vibe" / "SKILL.md").exists())
            self.assertFalse((bridge_root / "skills" / "vibe" / "bundled").exists())

            ledger = json.loads((bridge_root / ".vibeskills" / "install-ledger.json").read_text(encoding="utf-8"))
            closure = json.loads((bridge_root / ".vibeskills" / "host-closure.json").read_text(encoding="utf-8"))

            self.assertEqual(str(shared_root.resolve()), ledger["runtime_root"])
            self.assertEqual(str((shared_root / "skills" / "vibe").resolve()), ledger["canonical_vibe_root"])
            self.assertEqual("split-shared-runtime", ledger["runtime_layout_mode"])
            self.assertEqual(str(shared_root.resolve()), closure["runtime_root"])


if __name__ == "__main__":
    unittest.main()
