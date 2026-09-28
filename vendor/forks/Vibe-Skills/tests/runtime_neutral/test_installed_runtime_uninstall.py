from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_SCRIPT = REPO_ROOT / "install.sh"
UNINSTALL_SCRIPT = REPO_ROOT / "uninstall.sh"


class InstalledRuntimeUninstallTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def install_host(self, host: str, target_root: Path) -> None:
        subprocess.run(
            [
                "bash",
                str(INSTALL_SCRIPT),
                "--skills-dir",
                str(target_root / "skills"),
            ],
            capture_output=True,
            text=True,
            check=True,
        )

    def uninstall_host(self, host: str, target_root: Path) -> dict[str, object]:
        result = subprocess.run(
            [
                "bash",
                str(UNINSTALL_SCRIPT),
                "--skills-dir",
                str(target_root / "skills"),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)

    def test_codex_installed_runtime_uninstall_removes_managed_payload_only(self) -> None:
        target_root = self.root / "codex-root"
        self.install_host("codex", target_root)
        sentinel = target_root / "commands" / "user.md"
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.write_text("user\n", encoding="utf-8")
        installed_root = target_root / "skills" / "vibe"
        self.assertTrue(installed_root.exists())

        payload = self.uninstall_host("codex", target_root)

        self.assertFalse(installed_root.exists())
        self.assertTrue(sentinel.exists())
        self.assertGreater(len(payload["removed_files"]), 0)

    def test_codex_uninstall_preserves_user_agents_file_and_removes_only_managed_block(self) -> None:
        target_root = self.root / "codex-root-user-agents"
        agents_path = target_root / "AGENTS.md"
        agents_path.parent.mkdir(parents=True, exist_ok=True)
        agents_path.write_text("# My rules\n\n- keep me\n", encoding="utf-8")

        self.install_host("codex", target_root)
        self.uninstall_host("codex", target_root)

        self.assertTrue(agents_path.exists())
        remaining = agents_path.read_text(encoding="utf-8")
        self.assertIn("# My rules", remaining)
        self.assertIn("keep me", remaining)
        self.assertNotIn("VIBESKILLS:BEGIN", remaining)

    def test_install_and_uninstall_do_not_create_agents_file(self) -> None:
        target_root = self.root / "codex-root-managed-agents-only"

        self.install_host("codex", target_root)
        self.assertFalse((target_root / "AGENTS.md").exists())
        self.uninstall_host("codex", target_root)

        self.assertFalse((target_root / "AGENTS.md").exists())

    def test_codex_uninstall_preserves_preexisting_empty_agents_file(self) -> None:
        target_root = self.root / "codex-root-empty-agents"
        agents_path = target_root / "AGENTS.md"
        agents_path.parent.mkdir(parents=True, exist_ok=True)
        agents_path.write_text("", encoding="utf-8")

        self.install_host("codex", target_root)
        self.assertEqual("", agents_path.read_text(encoding="utf-8"))

        payload = self.uninstall_host("codex", target_root)

        self.assertTrue(agents_path.exists())
        self.assertEqual("", agents_path.read_text(encoding="utf-8"))
        self.assertGreater(len(payload["removed_files"]), 0)

    def test_install_and_uninstall_preserve_existing_agents_file_with_user_tail(self) -> None:
        target_root = self.root / "codex-root-managed-agents-with-user-tail"
        agents_path = target_root / "AGENTS.md"
        agents_path.parent.mkdir(parents=True, exist_ok=True)
        agents_path.write_text("# user tail\n", encoding="utf-8")

        self.install_host("codex", target_root)
        self.assertEqual("# user tail\n", agents_path.read_text(encoding="utf-8"))

        payload = self.uninstall_host("codex", target_root)

        self.assertTrue(agents_path.exists())
        self.assertEqual("# user tail\n", agents_path.read_text(encoding="utf-8"))
        self.assertGreater(len(payload["removed_files"]), 0)

    def test_shared_target_root_reinstall_does_not_create_host_blocks(self) -> None:
        target_root = self.root / "shared-root-codex-opencode"

        self.install_host("codex", target_root)
        self.install_host("opencode", target_root)
        installed_root = target_root / "skills" / "vibe"
        self.assertTrue(installed_root.exists())
        self.assertFalse((target_root / "AGENTS.md").exists())

        payload = self.uninstall_host("codex", target_root)

        self.assertFalse(installed_root.exists())
        self.assertGreater(len(payload["removed_files"]), 0)
        self.assertFalse((target_root / "AGENTS.md").exists())

    def test_uninstall_removes_receipt_listed_managed_files(self) -> None:
        target_root = self.root / "codex-issue-167-root"
        self.install_host("codex", target_root)
        installed_root = target_root / "skills" / "vibe"
        receipt_path = installed_root / ".vibeskills" / "install-receipt.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        managed_relpaths = [
            str(item["path"])
            for item in receipt["files"]
            if str(item.get("path") or "") in {"SKILL.md", "scripts/runtime/invoke-vibe-runtime.ps1"}
        ]

        self.assertEqual({"SKILL.md", "scripts/runtime/invoke-vibe-runtime.ps1"}, set(managed_relpaths))
        for relpath in managed_relpaths:
            self.assertTrue((installed_root / relpath).exists(), relpath)

        payload = self.uninstall_host("codex", target_root)

        for relpath in managed_relpaths:
            self.assertFalse((installed_root / relpath).exists(), relpath)
        self.assertTrue(set(managed_relpaths).issubset(set(payload["removed_files"])))

    def test_uninstall_removes_vibe_package_and_preserves_user_commands(self) -> None:
        target_root = self.root / "claude-root"
        self.install_host("claude-code", target_root)
        settings_path = target_root / "settings.json"
        sentinel = target_root / "commands" / "user.md"
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.write_text("user\n", encoding="utf-8")
        installed_root = target_root / "skills" / "vibe"
        self.assertTrue(installed_root.exists())
        self.assertFalse(settings_path.exists())

        self.uninstall_host("claude-code", target_root)

        self.assertFalse(installed_root.exists())
        self.assertTrue(sentinel.exists())
        self.assertFalse(settings_path.exists())

    def test_claude_code_uninstall_preserves_preexisting_settings(self) -> None:
        target_root = self.root / "claude-root-preserve"
        settings_path = target_root / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(
            json.dumps(
                {
                    "env": {"ANTHROPIC_API_KEY": "secret"},
                    "model": "claude-sonnet-4-6",
                },
                ensure_ascii=False,
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )

        self.install_host("claude-code", target_root)
        self.uninstall_host("claude-code", target_root)

        self.assertTrue(settings_path.exists())
        mutated = json.loads(settings_path.read_text(encoding="utf-8"))
        self.assertEqual({"ANTHROPIC_API_KEY": "secret"}, mutated["env"])
        self.assertEqual("claude-sonnet-4-6", mutated["model"])
        self.assertNotIn("vibeskills", mutated)
        self.assertNotIn("hooks", mutated)

    def test_uninstall_requires_receipt_and_preserves_unowned_sidecar(self) -> None:
        target_root = self.root / "claude-root-unowned-sidecar"
        sidecar_root = target_root / ".vibeskills"
        note_path = sidecar_root / "user-note.txt"
        note_path.parent.mkdir(parents=True, exist_ok=True)
        note_path.write_text("keep me\n", encoding="utf-8")

        result = subprocess.run(
            [
                "bash",
                str(UNINSTALL_SCRIPT),
                "--skills-dir",
                str(target_root / "skills"),
            ],
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("install-receipt.json", result.stderr + result.stdout)
        self.assertTrue(sidecar_root.exists())
        self.assertTrue(note_path.exists())

    def test_cursor_uninstall_removes_vibe_managed_surface(self) -> None:
        target_root = self.root / "cursor-root"
        self.install_host("cursor", target_root)
        sentinel = target_root / "commands" / "user.md"
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.write_text("user\n", encoding="utf-8")

        self.uninstall_host("cursor", target_root)

        self.assertFalse((target_root / ".vibeskills").exists())
        self.assertTrue(sentinel.exists())
        self.assertFalse((target_root / "settings.json").exists())

    def test_installed_host_uninstall_preserves_workspace_sidecar_created_after_install(self) -> None:
        for host in ("claude-code", "cursor"):
            with self.subTest(host=host):
                target_root = self.root / f"{host}-workspace-sidecar"
                self.install_host(host, target_root)
                project_path = target_root / ".vibeskills" / "project.json"
                requirement_path = target_root / ".vibeskills" / "docs" / "requirements" / "req.md"
                project_path.parent.mkdir(parents=True, exist_ok=True)
                project_path.write_text(
                    json.dumps(
                        {
                            "schema_version": 1,
                            "workspace_root": str(target_root.resolve()),
                            "workspace_sidecar_root": str((target_root / ".vibeskills").resolve()),
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                requirement_path.parent.mkdir(parents=True, exist_ok=True)
                requirement_path.write_text("# runtime artifact\n", encoding="utf-8")

                payload = self.uninstall_host(host, target_root)

                self.assertTrue(project_path.exists())
                self.assertTrue(requirement_path.exists())
                self.assertTrue((target_root / ".vibeskills").exists())
                self.assertFalse(any(str(path).startswith(".vibeskills") for path in payload["removed_files"]))

    def test_windsurf_uninstall_removes_runtime_core_preview_host_payload(self) -> None:
        target_root = self.root / "windsurf-root"
        self.install_host("windsurf", target_root)
        sentinel = target_root / "commands" / "user.md"
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.write_text("user\n", encoding="utf-8")

        self.uninstall_host("windsurf", target_root)

        self.assertFalse((target_root / "global_workflows" / "vibe.md").exists())
        self.assertFalse((target_root / ".vibeskills").exists())
        self.assertTrue(sentinel.exists())

    def test_openclaw_uninstall_removes_runtime_core_preview_host_payload(self) -> None:
        target_root = self.root / "openclaw-root"
        self.install_host("openclaw", target_root)
        sentinel = target_root / "commands" / "user.md"
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.write_text("user\n", encoding="utf-8")

        self.uninstall_host("openclaw", target_root)

        self.assertFalse((target_root / "global_workflows" / "vibe.md").exists())
        self.assertFalse((target_root / ".vibeskills").exists())
        self.assertTrue(sentinel.exists())

    def test_opencode_uninstall_removes_managed_payload_and_preserves_user_json(self) -> None:
        target_root = self.root / "opencode-root"
        self.install_host("opencode", target_root)
        settings_path = target_root / "opencode.json"
        settings_path.write_text(
            json.dumps(
                {
                    "vibeskills": {
                        "host_id": "opencode",
                        "managed": True,
                        "commands_root": str((target_root / "commands").resolve()),
                    },
                    "user.keep": True,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        sentinel = target_root / "commands" / "user.md"
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.write_text("user\n", encoding="utf-8")

        self.uninstall_host("opencode", target_root)

        self.assertFalse((target_root / ".vibeskills").exists())
        self.assertFalse((target_root / "command" / "vibe.md").exists())
        self.assertFalse((target_root / "agents" / "vibe-plan.md").exists())
        self.assertFalse((target_root / "opencode.json.example").exists())
        self.assertTrue(sentinel.exists())
        self.assertTrue(settings_path.exists())
        remaining = json.loads(settings_path.read_text(encoding="utf-8"))
        self.assertIn("vibeskills", remaining)
        self.assertTrue(remaining["user.keep"])

    def test_opencode_uninstall_preserves_user_agents_file_and_removes_only_managed_block(self) -> None:
        target_root = self.root / "opencode-root-user-agents"
        agents_path = target_root / "AGENTS.md"
        agents_path.parent.mkdir(parents=True, exist_ok=True)
        agents_path.write_text("# Existing OpenCode rules\n", encoding="utf-8")

        self.install_host("opencode", target_root)
        self.uninstall_host("opencode", target_root)

        self.assertTrue(agents_path.exists())
        remaining = agents_path.read_text(encoding="utf-8")
        self.assertIn("# Existing OpenCode rules", remaining)
        self.assertNotIn("VIBESKILLS:BEGIN", remaining)


if __name__ == "__main__":
    unittest.main()
