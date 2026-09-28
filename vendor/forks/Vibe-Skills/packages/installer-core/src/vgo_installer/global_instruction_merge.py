from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re


END_MARKER = "<!-- VIBESKILLS:END managed-block -->"
BEGIN_PATTERN = re.compile(
    r"^<!-- VIBESKILLS:BEGIN managed-block host=(?P<host>\S+) block=(?P<block>\S+) version=(?P<version>\d+) hash=(?P<hash>[a-f0-9]+) -->$",
    re.MULTILINE,
)
END_PATTERN = re.compile(r"^<!-- VIBESKILLS:END managed-block -->$", re.MULTILINE)


class ManagedBlockMutationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class ManagedBlockMutation:
    action: str
    text: str
    block_id: str
    host_id: str
    version: int
    content_hash: str


@dataclass(frozen=True, slots=True)
class ParsedManagedBlock:
    block_id: str
    host_id: str
    version: int
    content_hash: str
    start: int
    end: int
    raw: str


def _matching_blocks(
    blocks: list[ParsedManagedBlock],
    *,
    block_id: str,
    host_id: str | None,
) -> list[ParsedManagedBlock]:
    return [
        block
        for block in blocks
        if block.block_id == block_id and (host_id is None or block.host_id == host_id)
    ]


def compute_content_hash(body: str) -> str:
    normalized = normalize_body(body).encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()[:16]


def normalize_body(body: str) -> str:
    normalized = body.replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    return normalized + "\n"


def render_managed_block(*, body: str, host_id: str, block_id: str, version: int) -> tuple[str, str]:
    normalized_body = normalize_body(body)
    content_hash = compute_content_hash(normalized_body)
    block = (
        f"<!-- VIBESKILLS:BEGIN managed-block host={host_id} block={block_id} version={version} hash={content_hash} -->\n"
        f"{normalized_body}"
        f"{END_MARKER}\n"
    )
    return block, content_hash


def parse_managed_blocks(text: str) -> list[ParsedManagedBlock]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    begin_matches = list(BEGIN_PATTERN.finditer(normalized))
    if not begin_matches:
        return []

    blocks: list[ParsedManagedBlock] = []
    search_from = 0
    for index, match in enumerate(begin_matches):
        if match.start() < search_from:
            raise ManagedBlockMutationError("error_corrupt_managed_block", "corrupt managed block nesting")
        next_begin_start = begin_matches[index + 1].start() if index + 1 < len(begin_matches) else None
        end_match = None
        for candidate in END_PATTERN.finditer(normalized, match.end()):
            if next_begin_start is not None and candidate.start() > next_begin_start:
                break
            end_match = candidate
            break
        if end_match is None:
            raise ManagedBlockMutationError("error_corrupt_managed_block", "corrupt managed block terminator")
        block_end = end_match.end()
        if block_end < len(normalized) and normalized[block_end:block_end + 1] == "\n":
            block_end += 1
        blocks.append(
            ParsedManagedBlock(
                block_id=match.group("block"),
                host_id=match.group("host"),
                version=int(match.group("version")),
                content_hash=match.group("hash"),
                start=match.start(),
                end=block_end,
                raw=normalized[match.start():block_end],
            )
        )
        search_from = block_end
    return blocks


def _replace_slice(text: str, start: int, end: int, replacement: str) -> str:
    return text[:start] + replacement + text[end:]


def _append_block(existing_text: str, block: str) -> str:
    normalized = existing_text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.strip():
        return block
    base = normalized.rstrip("\n")
    return base + "\n\n" + block


def merge_managed_block_text(
    existing_text: str | None,
    *,
    body: str,
    host_id: str,
    block_id: str,
    version: int,
) -> ManagedBlockMutation:
    source = (existing_text or "").replace("\r\n", "\n").replace("\r", "\n")
    blocks = parse_managed_blocks(source)
    matching = _matching_blocks(blocks, block_id=block_id, host_id=host_id)
    if len(matching) > 1:
        raise ManagedBlockMutationError("error_duplicate_managed_blocks", "duplicate managed block detected")

    rendered_block, content_hash = render_managed_block(
        body=body,
        host_id=host_id,
        block_id=block_id,
        version=version,
    )

    if not matching:
        return ManagedBlockMutation(
            action="inserted",
            text=_append_block(source, rendered_block),
            block_id=block_id,
            host_id=host_id,
            version=version,
            content_hash=content_hash,
        )

    current = matching[0]
    if current.raw == rendered_block:
        return ManagedBlockMutation(
            action="unchanged",
            text=source,
            block_id=block_id,
            host_id=host_id,
            version=version,
            content_hash=content_hash,
        )

    updated = _replace_slice(source, current.start, current.end, rendered_block)
    return ManagedBlockMutation(
        action="updated",
        text=updated,
        block_id=block_id,
        host_id=host_id,
        version=version,
        content_hash=content_hash,
    )


def remove_managed_block_text(
    existing_text: str,
    *,
    block_id: str,
    host_id: str | None = None,
) -> ManagedBlockMutation:
    source = existing_text.replace("\r\n", "\n").replace("\r", "\n")
    blocks = parse_managed_blocks(source)
    matching = _matching_blocks(blocks, block_id=block_id, host_id=host_id)
    if len(matching) > 1:
        raise ManagedBlockMutationError("error_duplicate_managed_blocks", "duplicate managed block detected")
    if not matching:
        return ManagedBlockMutation(
            action="unchanged",
            text=source,
            block_id=block_id,
            host_id="",
            version=0,
            content_hash="",
        )

    current = matching[0]
    updated = source[:current.start].rstrip("\n")
    tail = source[current.end:].lstrip("\n")
    if updated and tail:
        next_text = updated + "\n\n" + tail
    else:
        next_text = updated or tail
    if next_text:
        next_text += "\n"
    return ManagedBlockMutation(
        action="removed",
        text=next_text,
        block_id=block_id,
        host_id=current.host_id,
        version=current.version,
        content_hash=current.content_hash,
    )
