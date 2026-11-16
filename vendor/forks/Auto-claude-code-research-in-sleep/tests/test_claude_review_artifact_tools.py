"""The artifact-grounded review path must be able to open its artifacts.

`auto-review-loop` and `research-review` stopped pasting evidence into the
reviewer prompt and now hand over artifact paths ("read the files yourself").
The claude-review bridge, meanwhile, runs Claude with `--tools ""` by default,
which is correct for the prompt-only reviews it was built for but leaves an
artifact-grounded reviewer with no tool to open what the prompt points at — it
answers from the executor's framing, the one thing artifact-grounded review
exists to prevent.

The fix is per-call, not a new global default: blocks that pass paths opt into
read-only tools, prompt-only blocks stay tool-free. These tests pin both halves.
"""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path
from unittest import mock

from tools.generate_codex_claude_review_overrides import (
    ARTIFACT_REVIEW_TOOLS,
    REVIEW_CALL_BLOCK_RE,
    TOOLS_KEY_RE,
    is_artifact_grounded,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
OVERLAY = REPO_ROOT / "skills" / "skills-codex-claude-review"
SERVER_PATH = REPO_ROOT / "mcp-servers" / "claude-review" / "server.py"

SPEC = importlib.util.spec_from_file_location("claude_review_server", SERVER_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

# Which overlay skills hand the reviewer artifact paths, and how many review
# calls in each do so. These protect the frozen snapshot independently of
# subsequent changes to the complete Codex pack.
EXPECTED_ARTIFACT_BLOCKS = {
    "auto-review-loop": 2,      # round-1 artifact review + round-2 changed-files reply
    "research-review": 1,       # "Revised files:" follow-up round
}

# Read-only means read-only: a reviewer never edits the work it reviews.
WRITE_TOOLS = ("Bash", "Edit", "Write", "NotebookEdit", "WebFetch", "Task")


def _review_blocks() -> list[tuple[str, str]]:
    """Every claude-review call block in the overlay, as (skill, block)."""
    blocks = []
    for skill_file in sorted(OVERLAY.rglob("SKILL.md")):
        text = skill_file.read_text(encoding="utf-8")
        for match in REVIEW_CALL_BLOCK_RE.finditer(text):
            blocks.append((skill_file.parent.name, match.group(0)))
    return blocks


class OverlayOptInTests(unittest.TestCase):
    def test_overlay_has_review_blocks_to_check(self) -> None:
        """Guard against a regex/layout change silently emptying every case below."""
        self.assertGreater(len(_review_blocks()), 5)

    def test_tools_opt_in_tracks_artifact_grounded_prompts(self) -> None:
        for skill, block in _review_blocks():
            header = block.splitlines()[1]
            with self.subTest(skill=skill, header=header, prompt=block[:200]):
                self.assertEqual(
                    bool(TOOLS_KEY_RE.search(block)),
                    is_artifact_grounded(block),
                    "a review block must request tools exactly when its prompt "
                    "hands the reviewer artifact paths",
                )

    def test_opt_in_blocks_request_the_readonly_preset(self) -> None:
        for skill, block in _review_blocks():
            if not TOOLS_KEY_RE.search(block):
                continue
            with self.subTest(skill=skill):
                self.assertIn(f'tools: "{ARTIFACT_REVIEW_TOOLS}"', block)

    def test_expected_skills_opt_in(self) -> None:
        counts: dict[str, int] = {}
        for skill, block in _review_blocks():
            if TOOLS_KEY_RE.search(block):
                counts[skill] = counts.get(skill, 0) + 1
        self.assertEqual(
            counts,
            EXPECTED_ARTIFACT_BLOCKS,
            "the frozen overlay artifact-tool contract changed; inspect the "
            "snapshot change and update EXPECTED_ARTIFACT_BLOCKS if intended",
        )


class ReadOnlyPresetTests(unittest.TestCase):
    def test_preset_is_readonly(self) -> None:
        granted = ARTIFACT_REVIEW_TOOLS.split(",")
        self.assertEqual(granted, ["Read", "Grep", "Glob"])
        for tool in WRITE_TOOLS:
            self.assertNotIn(tool, granted)


class BridgeDefaultTests(unittest.TestCase):
    """The bridge default must not move: prompt-only reviews stay tool-free."""

    def _cmd(self, **kwargs) -> list[str]:
        with mock.patch.object(MODULE, "find_claude_bin", return_value="/fake/claude"):
            return MODULE.build_command("review this", **kwargs)

    def test_default_disables_all_tools(self) -> None:
        # DEFAULT_TOOLS is read from CLAUDE_REVIEW_TOOLS at import; pin the
        # fallback so a developer who sets that variable does not fail here.
        with mock.patch.object(MODULE, "DEFAULT_TOOLS", ""):
            cmd = self._cmd()
        self.assertEqual(cmd[cmd.index("--tools") + 1], "")

    def test_explicit_readonly_tools_are_forwarded(self) -> None:
        cmd = self._cmd(tools=ARTIFACT_REVIEW_TOOLS)
        self.assertEqual(cmd[cmd.index("--tools") + 1], "Read,Grep,Glob")

    def test_explicit_empty_string_still_disables_tools(self) -> None:
        """`tools: ""` is an explicit prompt-only request, not "unset"."""
        cmd = self._cmd(tools="")
        self.assertEqual(cmd[cmd.index("--tools") + 1], "")

    def test_reviewer_stays_in_plan_permission_mode(self) -> None:
        """Read-only tools plus plan mode: the reviewer cannot write either way."""
        cmd = self._cmd(tools=ARTIFACT_REVIEW_TOOLS)
        self.assertEqual(cmd[cmd.index("--permission-mode") + 1], "plan")

    def test_tools_are_resent_on_every_resumed_call(self) -> None:
        """Each reply is a fresh `--resume` process, so the opt-in cannot be
        inherited from the round that opened the thread."""
        cmd = self._cmd(session_id="sess-1", tools=ARTIFACT_REVIEW_TOOLS)
        self.assertIn("--resume", cmd)
        self.assertEqual(cmd[cmd.index("--tools") + 1], "Read,Grep,Glob")

    def test_reviewer_cannot_inherit_executor_mcp_servers(self) -> None:
        cmd = self._cmd(tools=ARTIFACT_REVIEW_TOOLS)
        self.assertIn("--strict-mcp-config", cmd)
        self.assertEqual(json.loads(cmd[cmd.index("--mcp-config") + 1]), {"mcpServers": {}})

    def test_all_review_tools_expose_and_forward_cwd(self) -> None:
        listing = MODULE.handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        tools = {tool["name"]: tool for tool in listing["result"]["tools"]}
        for name in ("review", "review_reply", "review_start", "review_reply_start"):
            with self.subTest(tool=name):
                self.assertEqual(tools[name]["inputSchema"]["properties"]["cwd"]["type"], "string")
                function = "start_async_review" if name.endswith("start") else "run_claude_review"
                args = {"prompt": "review", "cwd": "/review/workspace"}
                if "reply" in name:
                    args["threadId"] = "existing-session"
                with mock.patch.object(MODULE, function, return_value=({}, None)) as invoke:
                    MODULE.handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": name, "arguments": args}})
                self.assertEqual(invoke.call_args.kwargs["cwd"], "/review/workspace")
                if "reply" in name:
                    self.assertEqual(invoke.call_args.kwargs["session_id"], "existing-session")


class FrozenOverlayTests(unittest.TestCase):
    def test_regeneration_refuses_without_touching_destinations(self) -> None:
        """New base features must not rewrite legacy linked installations."""
        from tools import generate_codex_claude_review_overrides as gen

        with mock.patch.object(gen, "SRC_ROOT", Path("/missing-base")), \
             mock.patch.object(gen, "DEST_ROOT", Path("/missing-overlay")):
            with self.assertRaisesRegex(RuntimeError, "overlays are frozen"):
                gen.generate_one("research-review")
            with self.assertRaisesRegex(SystemExit, "overlays are frozen"):
                gen.main()


if __name__ == "__main__":
    unittest.main()
