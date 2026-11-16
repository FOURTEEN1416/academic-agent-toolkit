from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "src" / "scripts" / "paperspine_update.py"
STABLE = ROOT.parent / "06_插件化" / "release" / "stable_updater.py"
if not STABLE.is_file():
    STABLE = ROOT / "paperspine5" / "core" / "06_插件化" / "release" / "stable_updater.py"
spec = importlib.util.spec_from_file_location("preflight_test_wrapper", SCRIPT)
wrapper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wrapper)


class UpdatePreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="paperspine-preflight-")
        # Normalize macOS /var aliases and Windows short-name temp paths before
        # writing installation pointers or constructing exact mock expectations.
        self.root = Path(self.tmp.name).resolve()
        self.skill = self.root / "skills" / "paper-spine"
        self.control = self.root / "control"
        self.suite = self.control / "transactions" / "first" / "suite"
        self.entry = self.suite / "release" / "stable_updater.py"
        self.entry.parent.mkdir(parents=True)
        self.entry.write_bytes(STABLE.read_bytes())
        (self.skill / "scripts").mkdir(parents=True)
        (self.skill / "SKILL.md").write_text("---\nname: paper-spine\n---\n", encoding="utf-8")
        self.pointer = self.skill / "references" / "installed-suite.json"
        wrapper.write_json(self.pointer, {
            "contract": "paperspine5.installed-suite-pointer", "schema_version": "1.0",
            "product_id": "paperspine5", "build_id": "current", "product_version": "0.4.0-alpha.2",
            "content_index_sha256": "0" * 64, "archive_sha256": "1" * 64,
            "suite_root": str(self.suite), "updater_entry": "release/stable_updater.py",
        })
        wrapper.write_json(self.suite / "suite-manifest.json", {
            "contract": "paperspine5.suite-manifest", "schema_version": "1.0",
            "suite": {"product_id": "paperspine5", "build_id": "current", "product_version": "0.4.0-alpha.2"},
            "content": {"index_sha256": "0" * 64, "files": [
                {"path": "release/stable_updater.py", "sha256": hashlib.sha256(self.entry.read_bytes()).hexdigest()}
            ]},
        })
        self.channel = self.root / "channel.json"
        wrapper.write_json(self.channel, {
            "protocol": "paperspine-updater/1", "product": "paperspine",
            "bundles": {key: {"url": "must-not-download.zip", "sha256": "1" * 64,
                               "build_id": "current", "product_version": "0.4.0-alpha.2"}
                        for key in ("windows-amd64", "linux-x86_64", "macos-arm64", "macos-x86_64")},
        })
        wrapper.write_json(self.control / "settings.json", {
            "protocol": "paperspine-updater/1", "skill_root": str(self.skill),
            "channel": str(self.channel), "data_roots": [str(self.root / "papers")],
        })
        self.args = argparse.Namespace(
            preflight=True, check_only=False, skill_root=self.skill, control_root=None, source=None,
            config_home=self.root / "config", repo_archive=None, yes=False,
            target="all", auto=False, force=False, enable_auto_update=False,
            disable_auto_update=False, auto_status=False, interval_hours=None,
        )
        # Do not depend on whether parent packaging has generated the embedded projection yet.
        self.script_patch = mock.patch.object(wrapper, "__file__", str(self.skill / "scripts" / "paperspine_update.py"))
        self.script_patch.start()

    def tearDown(self):
        self.script_patch.stop()
        self.tmp.cleanup()

    def run_quietly(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = wrapper.run(self.args)
        return code, output.getvalue()

    def test_current_suite_uses_real_metadata_check_without_archive_download(self):
        self.args.check_only = True
        code, output = self.run_quietly()
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)["status"], "up_to_date")
        self.assertFalse((self.root / "must-not-download.zip").exists())
        self.assertEqual(list((self.control / "transactions").iterdir()), [self.suite.parent])

    def test_preflight_checks_each_time_and_forwards_saved_control_and_data(self):
        module = mock.Mock()
        module.check.return_value = {"status": "up_to_date"}
        module.auto.return_value = {"status": "up_to_date", "bootstrap_updated": False}
        wrapper.write_json(self.args.config_home / wrapper.UPDATE_POLICY_FILE, {
            **wrapper.default_update_policy(), "auto_update": True,
            "last_checked_at": wrapper.iso_utc(wrapper.utc_now()),
        })
        with mock.patch.object(wrapper, "_load_stable_updater", return_value=module):
            self.assertEqual(self.run_quietly()[0], 0)
            self.assertEqual(self.run_quietly()[0], 0)
        self.assertEqual(module.check.call_count, 2)
        self.assertEqual(module.auto.call_count, 2)
        module.auto.assert_called_with(str(self.channel), skill_root=self.skill, control_root=self.control,
                                      data_roots=[str(self.root / "papers")], confirmed=True)

    def test_explicit_disabled_policy_makes_no_network_check(self):
        wrapper.write_json(self.args.config_home / wrapper.UPDATE_POLICY_FILE,
                           {**wrapper.default_update_policy(), "last_result": "disabled_by_user"})
        with mock.patch.object(wrapper, "_load_stable_updater") as load:
            code, output = self.run_quietly()
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)["status"], "disabled")
        load.assert_not_called()

    def test_check_only_never_installs_available_update(self):
        self.args.check_only = True
        module = mock.Mock()
        module.check.return_value = {"status": "update_available"}
        with mock.patch.object(wrapper, "_load_stable_updater", return_value=module):
            code, output = self.run_quietly()
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(output)["status"], "update_available")
        module.auto.assert_not_called()

    def test_offline_precheck_continues_existing_but_install_failure_is_fatal(self):
        module = mock.Mock()
        module.check.side_effect = urllib.error.URLError("offline")
        with mock.patch.object(wrapper, "_load_stable_updater", return_value=module):
            code, output = self.run_quietly()
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(output)["continue_existing"])
        module.auto.assert_not_called()
        module.check.side_effect = None
        module.check.return_value = {"status": "update_available"}
        module.auto.side_effect = urllib.error.URLError("archive download failed after precheck")
        with mock.patch.object(wrapper, "_load_stable_updater", return_value=module):
            with self.assertRaisesRegex(wrapper.UpdateError, "archive download failed"):
                self.run_quietly()

    def test_embedded_projection_is_preferred_for_old_suite_bootstrap(self):
        embedded = self.skill / "scripts" / "paperspine_stable_update.py"
        embedded.write_bytes(STABLE.read_bytes())
        self.entry.write_text("# old updater without preflight\n", encoding="utf-8")
        suite, pointer, manifest = wrapper._managed_installation(self.skill)
        self.assertEqual(wrapper._stable_entry(suite, pointer, manifest), embedded)
        self.assertTrue(callable(wrapper._load_stable_updater(embedded).auto))

    def test_pointer_drift_and_modified_fallback_updater_fail_before_execution(self):
        self.entry.write_text("raise AssertionError('must not execute')\n", encoding="utf-8")
        with self.assertRaisesRegex(wrapper.UpdateError, "content index"):
            self.run_quietly()
        pointer = wrapper.read_json(self.pointer)
        pointer["build_id"] = "different"
        wrapper.write_json(self.pointer, pointer)
        with self.assertRaisesRegex(wrapper.UpdateError, "identity do not match"):
            self.run_quietly()

    def test_old_bootstrap_without_preflight_does_not_blindly_apply(self):
        old = self.root / "old.py"
        old.write_text("PROTOCOL='paperspine-updater/1'\ndef apply(*args, **kwargs): raise AssertionError('blind apply')\n", encoding="utf-8")
        with self.assertRaisesRegex(wrapper.UpdateError, "no blind apply"):
            wrapper._load_stable_updater(old)

    def test_source_defaults_to_official_channel_without_saved_channel(self):
        settings = wrapper.read_json(self.control / "settings.json")
        settings["channel"] = None
        wrapper.write_json(self.control / "settings.json", settings)
        self.args.check_only = True
        module = mock.Mock()
        module.check.return_value = {"status": "up_to_date"}
        with mock.patch.object(wrapper, "_load_stable_updater", return_value=module):
            self.run_quietly()
        module.check.assert_called_once_with(wrapper.DEFAULT_STABLE_CHANNEL, skill_root=self.skill, control_root=self.control)
        self.assertEqual(wrapper.DEFAULT_STABLE_CHANNEL, "https://raw.githubusercontent.com/WUBING2023/PaperSpine/main/website/downloads/update-channel.json")

    def test_standalone_preflight_keeps_legacy_channel_and_does_not_migrate(self):
        self.pointer.unlink()
        self.args.skill_root = None
        manifest = {"version": "4.0.1"}
        with mock.patch.object(wrapper, "latest_manifest", return_value=manifest), mock.patch.object(wrapper, "run_update", return_value=0) as legacy, mock.patch.object(wrapper, "_load_stable_updater") as load:
            self.assertEqual(self.run_quietly()[0], 0)
        legacy.assert_called_once_with(self.args, checked_manifest=manifest)
        self.assertTrue(self.args.yes)
        load.assert_not_called()

    def test_explicit_control_for_another_installation_is_rejected(self):
        self.args.control_root = self.root / "other-control"
        wrapper.write_json(self.args.control_root / "settings.json", {
            "protocol": "paperspine-updater/1", "skill_root": str(self.root / "other" / "paper-spine")})
        with self.assertRaisesRegex(wrapper.UpdateError, "another Skill installation"):
            self.run_quietly()

    def test_preflight_and_check_only_parse_together(self):
        with mock.patch.object(sys, "argv", ["paperspine_update.py", "--preflight", "--check-only"]):
            args = wrapper.parse_args()
        self.assertTrue(args.preflight)
        self.assertTrue(args.check_only)

    def test_existing_unmanaged_install_uses_embedded_stable_without_legacy_archive(self):
        self.pointer.unlink()
        embedded = self.skill / "scripts" / "paperspine_stable_update.py"
        embedded.write_bytes(STABLE.read_bytes())
        self.args.control_root = self.control
        self.args.check_only = True
        code, output = self.run_quietly()
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(output)["installation"]["kind"], "legacy-standalone")
        self.assertFalse((self.root / "must-not-download.zip").exists())
        self.args.check_only = False
        module = mock.Mock()
        module.check.return_value = {"status": "update_available"}
        module.auto.return_value = {"status": "committed"}
        with mock.patch.object(wrapper, "_load_stable_updater", return_value=module) as load, mock.patch.object(wrapper, "run_update") as legacy:
            code, output = self.run_quietly()
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)["status"], "committed")
        load.assert_called_once_with(embedded)
        module.auto.assert_called_once_with(str(self.channel), skill_root=self.skill, control_root=self.control,
                                            data_roots=[str(self.root / "papers")], confirmed=True)
        legacy.assert_not_called()

    def test_error_result_is_not_reported_as_success(self):
        module = mock.Mock()
        module.check.return_value = {"status": "update_available"}
        module.auto.return_value = {"status": "FAIL", "error": "failed activation"}
        with mock.patch.object(wrapper, "_load_stable_updater", return_value=module):
            with self.assertRaisesRegex(wrapper.UpdateError, "failed activation"):
                self.run_quietly()

    def test_windows_bom_pointer_is_readable(self):
        value = self.pointer.read_text(encoding="utf-8")
        self.pointer.write_text(value, encoding="utf-8-sig")
        self.args.check_only = True
        self.assertEqual(self.run_quietly()[0], 0)



if __name__ == "__main__":
    unittest.main()
