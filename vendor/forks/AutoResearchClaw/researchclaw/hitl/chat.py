"""HITL chat engine: multi-turn human-AI conversation within a stage."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ChatMessage:
    """A single message in a chat session."""

    role: str  # "human" | "ai" | "system"
    content: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(
            timespec="seconds"
        )
    )
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChatMessage:
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=data.get("timestamp", ""),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ChatSession:
    """Multi-turn conversation between human and AI for a specific stage.

    The chat session provides context-aware conversation by injecting
    stage artifacts and pipeline state into the AI's context window.
    """

    session_id: str = field(
        default_factory=lambda: str(uuid.uuid4())[:12]
    )
    stage_num: int = 0
    stage_name: str = ""
    topic: str = ""
    messages: list[ChatMessage] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    max_turns: int = 50

    @property
    def turn_count(self) -> int:
        return sum(1 for m in self.messages if m.role == "human")

    @property
    def is_at_limit(self) -> bool:
        return self.turn_count >= self.max_turns

    def add_system_message(self, content: str) -> None:
        """Add a system/context message (stage info, artifacts, etc)."""
        self.messages.append(
            ChatMessage(role="system", content=content)
        )

    def add_human_message(self, content: str) -> None:
        """Record a human message."""
        self.messages.append(ChatMessage(role="human", content=content))

    def add_ai_message(
        self, content: str, metadata: dict[str, Any] | None = None
    ) -> None:
        """Record an AI response."""
        self.messages.append(
            ChatMessage(
                role="ai",
                content=content,
                metadata=metadata or {},
            )
        )

    def build_llm_messages(self) -> list[dict[str, str]]:
        """Convert chat history to LLM API message format.

        System messages become system prompts; human/ai become user/assistant.
        """
        llm_messages: list[dict[str, str]] = []
        for msg in self.messages:
            if msg.role == "system":
                llm_messages.append(
                    {"role": "system", "content": msg.content}
                )
            elif msg.role == "human":
                llm_messages.append(
                    {"role": "user", "content": msg.content}
                )
            elif msg.role == "ai":
                llm_messages.append(
                    {"role": "assistant", "content": msg.content}
                )
        return llm_messages

    def get_ai_response(self, llm_client: Any) -> str:
        """Get AI response using the configured LLM client.

        Args:
            llm_client: LLMClient instance with a ``chat()`` method.

        Returns:
            AI response text.
        """
        if self.is_at_limit:
            return (
                "[Chat limit reached. Please finalize your decisions "
                "and approve/reject the stage output.]"
            )

        messages = self.build_llm_messages()

        try:
            response = llm_client.chat(messages)
            text = response.content if hasattr(response, "content") else str(response)
            self.add_ai_message(text)
            return text
        except Exception as exc:
            error_msg = f"[LLM error: {exc}]"
            logger.error("Chat LLM call failed: %s", exc)
            self.add_ai_message(error_msg)
            return error_msg

    def save(self, path: Path) -> None:
        """Save chat history to a JSONL file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            for msg in self.messages:
                fh.write(json.dumps(msg.to_dict()) + "\n")

    @classmethod
    def load(cls, path: Path) -> ChatSession | None:
        """Load a chat session from a JSONL file."""
        if not path.exists():
            return None
        try:
            messages = []
            for line in path.read_text(encoding="utf-8").strip().split("\n"):
                if line:
                    messages.append(ChatMessage.from_dict(json.loads(line)))
            session = cls(messages=messages)
            return session
        except (json.JSONDecodeError, OSError, KeyError) as exc:
            logger.warning("Failed to load chat session: %s", exc)
            return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "stage_num": self.stage_num,
            "stage_name": self.stage_name,
            "topic": self.topic,
            "turn_count": self.turn_count,
            "message_count": len(self.messages),
        }


def build_stage_context(
    stage_num: int,
    stage_name: str,
    topic: str,
    run_dir: Path,
    artifacts: tuple[str, ...] = (),
) -> str:
    """Build a rich context string for the chat system prompt.

    Reads stage outputs and preceding stage summaries to give the AI
    full awareness of the current pipeline state.
    """
    lines = [
        f"You are collaborating with a human researcher on Stage {stage_num} "
        f"({stage_name}) of an automated research pipeline.",
        f"Research topic: {topic}",
        "",
        "## Current Stage Output",
    ]

    stage_dir = run_dir / f"stage-{stage_num:02d}"
    if stage_dir.exists():
        for fname in artifacts:
            fpath = stage_dir / fname
            if fpath.is_file():
                try:
                    content = fpath.read_text(encoding="utf-8")
                    # Truncate very large files
                    if len(content) > 3000:
                        content = content[:3000] + "\n...[truncated]"
                    lines.append(f"\n### {fname}\n```\n{content}\n```")
                except (OSError, UnicodeDecodeError):
                    lines.append(f"\n### {fname}\n[Error reading file]")

    # Include guidance if present
    guidance_file = stage_dir / "hitl_guidance.md" if stage_dir.exists() else None
    if guidance_file and guidance_file.exists():
        try:
            guidance = guidance_file.read_text(encoding="utf-8")
            lines.append(f"\n## Human Guidance\n{guidance}")
        except (OSError, UnicodeDecodeError):
            pass

    lines.extend([
        "",
        "## Instructions",
        "- Help the human researcher improve the stage output.",
        "- Be specific and actionable in your suggestions.",
        "- When the human is satisfied, they will approve the output.",
        "- To edit a file, wrap the full updated content in edit markers:",
        "  <<<FILE: filename>>>",
        "  ...complete file content...",
        "  <<<END_FILE>>>",
        "- Edits are applied automatically when you use this format.",
        "- Only use this format for files listed in the current stage output.",
    ])

    return "\n".join(lines)
