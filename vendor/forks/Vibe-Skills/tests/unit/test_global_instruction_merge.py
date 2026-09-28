from __future__ import annotations

from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER_CORE_SRC = REPO_ROOT / "packages" / "installer-core" / "src"
CONTRACTS_SRC = REPO_ROOT / "packages" / "contracts" / "src"
for src in (INSTALLER_CORE_SRC, CONTRACTS_SRC):
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))

from vgo_installer.global_instruction_merge import (  # type: ignore[attr-defined]
    ManagedBlockMutationError,
    merge_managed_block_text,
    parse_managed_blocks,
    remove_managed_block_text,
    render_managed_block,
)


def _marker_count(text: str) -> int:
    return text.count("<!-- VIBESKILLS:BEGIN managed-block")


def test_merge_managed_block_inserts_new_block_into_missing_file() -> None:
    result = merge_managed_block_text(
        None,
        body="Use canonical vibe for explicit $vibe and /vibe.",
        host_id="codex",
        block_id="global-vibe-bootstrap",
        version=1,
    )

    assert result.action == "inserted"
    assert _marker_count(result.text) == 1
    assert "Use canonical vibe" in result.text
    assert "host=codex" in result.text
    assert "block=global-vibe-bootstrap" in result.text


def test_merge_managed_block_preserves_existing_content_when_inserting() -> None:
    existing = "# Personal rules\n\n- Keep my own guidance.\n"

    result = merge_managed_block_text(
        existing,
        body="Use canonical vibe for explicit $vibe and /vibe.",
        host_id="claude-code",
        block_id="global-vibe-bootstrap",
        version=1,
    )

    assert result.action == "inserted"
    assert "# Personal rules" in result.text
    assert "Keep my own guidance." in result.text
    assert _marker_count(result.text) == 1


def test_merge_managed_block_is_idempotent_when_content_matches() -> None:
    first = merge_managed_block_text(
        None,
        body="Use canonical vibe for explicit $vibe and /vibe.",
        host_id="opencode",
        block_id="global-vibe-bootstrap",
        version=1,
    )

    second = merge_managed_block_text(
        first.text,
        body="Use canonical vibe for explicit $vibe and /vibe.",
        host_id="opencode",
        block_id="global-vibe-bootstrap",
        version=1,
    )

    assert second.action == "unchanged"
    assert second.text == first.text
    assert _marker_count(second.text) == 1


def test_merge_managed_block_updates_existing_block_in_place() -> None:
    first = merge_managed_block_text(
        None,
        body="Use canonical vibe for explicit $vibe and /vibe.",
        host_id="codex",
        block_id="global-vibe-bootstrap",
        version=1,
    )

    second = merge_managed_block_text(
        first.text,
        body="Use canonical vibe first. Report blocked instead of silent fallback.",
        host_id="codex",
        block_id="global-vibe-bootstrap",
        version=2,
    )

    assert second.action == "updated"
    assert _marker_count(second.text) == 1
    assert "silent fallback" in second.text
    assert "version=2" in second.text


def test_merge_managed_block_rejects_duplicate_blocks() -> None:
    first = merge_managed_block_text(
        None,
        body="Use canonical vibe for explicit $vibe and /vibe.",
        host_id="codex",
        block_id="global-vibe-bootstrap",
        version=1,
    )
    duplicated = first.text + "\n" + first.text

    with pytest.raises(ManagedBlockMutationError, match="duplicate"):
        merge_managed_block_text(
            duplicated,
            body="Use canonical vibe for explicit $vibe and /vibe.",
            host_id="codex",
            block_id="global-vibe-bootstrap",
            version=1,
        )


def test_merge_managed_block_rejects_corrupted_delimiters() -> None:
    corrupted = (
        "<!-- VIBESKILLS:BEGIN managed-block host=codex block=global-vibe-bootstrap version=1 hash=deadbeef -->\n"
        "Use canonical vibe.\n"
    )

    with pytest.raises(ManagedBlockMutationError, match="corrupt"):
        merge_managed_block_text(
            corrupted,
            body="Use canonical vibe for explicit $vibe and /vibe.",
            host_id="codex",
            block_id="global-vibe-bootstrap",
            version=1,
        )


def test_parse_managed_blocks_ignores_literal_end_marker_inside_user_markdown() -> None:
    block, _ = render_managed_block(
        body="Use canonical vibe for explicit $vibe and /vibe.",
        host_id="codex",
        block_id="global-vibe-bootstrap",
        version=1,
    )
    mixed_text = (
        block
        + "\n# User notes\n\n```md\n"
        + "<!-- VIBESKILLS:END managed-block -->\n"
        + "```\n"
    )

    parsed = parse_managed_blocks(mixed_text)

    assert len(parsed) == 1
    assert parsed[0].block_id == "global-vibe-bootstrap"
    assert parsed[0].host_id == "codex"


def test_remove_managed_block_only_removes_owned_block() -> None:
    existing = "# User rules\n\n- keep me\n"
    merged = merge_managed_block_text(
        existing,
        body="Use canonical vibe for explicit $vibe and /vibe.",
        host_id="claude-code",
        block_id="global-vibe-bootstrap",
        version=1,
    )

    removed = remove_managed_block_text(
        merged.text,
        block_id="global-vibe-bootstrap",
    )

    assert removed.action == "removed"
    assert "# User rules" in removed.text
    assert "keep me" in removed.text
    assert _marker_count(removed.text) == 0
