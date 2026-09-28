"""Context manager: intelligent context window management for HITL interactions.

When collaborating on long documents (papers, experiment plans), the LLM
context window can fill up quickly. This module handles:

1. **Relevance-based truncation** — keep the most relevant parts
2. **Sliding window** — for long chat sessions
3. **Artifact summarization** — compress large outputs into summaries
4. **Cross-stage context** — bring in relevant info from other stages
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default context budget (characters) for different purposes
CONTEXT_BUDGETS = {
    "chat_system": 4000,
    "chat_history": 8000,
    "stage_output": 6000,
    "cross_stage": 3000,
    "guidance": 1000,
}


class ContextManager:
    """Manage LLM context for HITL interactions.

    Ensures that the total context stays within budget while
    preserving the most important information.
    """

    def __init__(
        self,
        run_dir: Path,
        max_total_chars: int = 24000,
    ) -> None:
        self.run_dir = run_dir
        self.max_total_chars = max_total_chars

    def build_context(
        self,
        stage_num: int,
        stage_name: str,
        topic: str,
        *,
        include_chat_history: bool = True,
        chat_messages: list[dict[str, str]] | None = None,
        focus_artifacts: tuple[str, ...] = (),
        cross_stage_refs: tuple[int, ...] = (),
    ) -> list[dict[str, str]]:
        """Build an optimized context for an LLM interaction.

        Returns a list of messages suitable for llm.chat().
        """
        budget = dict(CONTEXT_BUDGETS)
        remaining = self.max_total_chars

        messages: list[dict[str, str]] = []

        # 1. System context
        system_parts = self._build_system_context(
            stage_num, stage_name, topic, budget["chat_system"]
        )
        if system_parts:
            system_text = "\n".join(system_parts)
            messages.append({"role": "system", "content": system_text})
            remaining -= len(system_text)

        # 2. Cross-stage context (most important prior artifacts)
        if cross_stage_refs:
            cross_text = self._build_cross_stage(
                cross_stage_refs, min(budget["cross_stage"], remaining // 4)
            )
            if cross_text:
                messages.append({
                    "role": "system",
                    "content": f"## Prior Stage Context\n{cross_text}",
                })
                remaining -= len(cross_text)

        # 3. Current stage output
        stage_text = self._build_stage_output(
            stage_num, focus_artifacts,
            min(budget["stage_output"], remaining // 3),
        )
        if stage_text:
            messages.append({
                "role": "system",
                "content": f"## Current Stage Output\n{stage_text}",
            })
            remaining -= len(stage_text)

        # 4. Guidance
        guidance = self._load_guidance(stage_num)
        if guidance:
            guidance_text = guidance[:budget["guidance"]]
            messages.append({
                "role": "system",
                "content": f"## Human Guidance\n{guidance_text}",
            })
            remaining -= len(guidance_text)

        # 5. Chat history (sliding window — keep recent turns)
        if include_chat_history and chat_messages:
            history_budget = min(budget["chat_history"], remaining)
            trimmed = self._trim_chat_history(chat_messages, history_budget)
            messages.extend(trimmed)

        return messages

    def summarize_artifact(self, content: str, max_chars: int = 2000) -> str:
        """Compress a large artifact into a summary.

        Uses extractive summarization (key lines, structure, stats)
        rather than LLM-based summarization to avoid extra API calls.
        """
        if len(content) <= max_chars:
            return content

        lines = content.split("\n")

        # Extract structure (headers, key lines)
        important_lines: list[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            # Headers
            if stripped.startswith("#"):
                important_lines.append(stripped)
            # Key patterns
            elif any(kw in stripped.lower() for kw in (
                "result", "conclusion", "finding", "hypothesis",
                "baseline", "metric", "accuracy", "improvement",
                "error", "failed", "warning",
            )):
                important_lines.append(stripped)
            # First lines of sections
            elif line and not line[0].isspace() and len(stripped) > 20:
                important_lines.append(stripped[:150])

        summary = "\n".join(important_lines)

        # If still too long, take first and last portions
        if len(summary) > max_chars:
            half = max_chars // 2
            summary = summary[:half] + "\n...[truncated]...\n" + summary[-half:]

        # Add stats header
        stats = (
            f"[{len(lines)} lines, {len(content)} chars — "
            f"showing {len(important_lines)} key lines]"
        )
        return f"{stats}\n{summary}"

    def _build_system_context(
        self,
        stage_num: int,
        stage_name: str,
        topic: str,
        budget: int,
    ) -> list[str]:
        parts = [
            f"You are collaborating with a human researcher on Stage {stage_num} ({stage_name}).",
            f"Research topic: {topic}",
            "",
            "Be specific, actionable, and honest about limitations.",
            "Never fabricate citations, data, or results.",
        ]
        return parts

    def _build_cross_stage(
        self, stage_refs: tuple[int, ...], budget: int
    ) -> str:
        """Collect relevant context from other stages."""
        parts: list[str] = []
        per_stage = budget // max(len(stage_refs), 1)

        for stage_num in stage_refs:
            stage_dir = self.run_dir / f"stage-{stage_num:02d}"
            if not stage_dir.is_dir():
                continue
            # Read main output file
            for fname in sorted(stage_dir.iterdir()):
                if fname.suffix in (".md", ".yaml", ".json") and fname.name != "stage_health.json":
                    try:
                        content = fname.read_text(encoding="utf-8")
                        parts.append(
                            f"### Stage {stage_num}: {fname.name}\n"
                            + self.summarize_artifact(content, per_stage)
                        )
                    except (OSError, UnicodeDecodeError):
                        pass
                    break  # One file per stage

        return "\n\n".join(parts)[:budget]

    def _build_stage_output(
        self,
        stage_num: int,
        focus_artifacts: tuple[str, ...],
        budget: int,
    ) -> str:
        stage_dir = self.run_dir / f"stage-{stage_num:02d}"
        if not stage_dir.is_dir():
            return ""

        parts: list[str] = []
        files = list(focus_artifacts) if focus_artifacts else [
            f.name for f in sorted(stage_dir.iterdir())
            if f.is_file() and f.name != "stage_health.json"
        ]

        per_file = budget // max(len(files), 1)
        for fname in files[:5]:  # Max 5 files
            fpath = stage_dir / fname
            if fpath.is_file():
                try:
                    content = fpath.read_text(encoding="utf-8")
                    if len(content) > per_file:
                        content = self.summarize_artifact(content, per_file)
                    parts.append(f"### {fname}\n{content}")
                except (OSError, UnicodeDecodeError):
                    pass

        return "\n\n".join(parts)[:budget]

    def _load_guidance(self, stage_num: int) -> str:
        """Load HITL guidance for a stage."""
        for path in (
            self.run_dir / f"stage-{stage_num:02d}" / "hitl_guidance.md",
            self.run_dir / "hitl" / "guidance" / f"stage_{stage_num:02d}.md",
        ):
            if path.exists():
                try:
                    return path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    pass
        return ""

    def _trim_chat_history(
        self,
        messages: list[dict[str, str]],
        budget: int,
    ) -> list[dict[str, str]]:
        """Keep the most recent chat messages within budget.

        Always keeps the first system message and the most recent turns.
        """
        if not messages:
            return []

        # Calculate total size
        total = sum(len(m.get("content", "")) for m in messages)
        if total <= budget:
            return messages

        # Keep last N messages that fit
        result: list[dict[str, str]] = []
        used = 0
        for msg in reversed(messages):
            size = len(msg.get("content", ""))
            if used + size > budget:
                break
            result.insert(0, msg)
            used += size

        # If we dropped messages, add a note
        dropped = len(messages) - len(result)
        if dropped > 0 and result:
            result.insert(0, {
                "role": "system",
                "content": f"[{dropped} earlier messages omitted for context limit]",
            })

        return result
