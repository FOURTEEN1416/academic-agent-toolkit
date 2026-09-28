"""Paper Co-Writer: collaborative paper writing workshop (Stages 16-19).

Enables human-AI collaborative paper writing with:
- Section-by-section drafting
- Human editing with AI polishing
- Tracked changes and revision history
- Conference-specific style guidance
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SectionDraft:
    """A draft of a paper section."""

    name: str  # e.g., "Introduction", "Related Work", "Method"
    content: str = ""
    status: str = "pending"  # pending | ai_draft | human_edited | finalized
    ai_version: str = ""
    human_version: str = ""
    revision_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "content": self.content,
            "status": self.status,
            "revision_count": self.revision_count,
        }


class PaperCoWriter:
    """Collaborative paper writing engine.

    Workflow:
    1. AI writes initial draft of each section
    2. Human reviews and edits
    3. AI polishes human edits to match paper style
    4. Human finalizes

    Can operate in different modes:
    - ``ai_first``: AI writes, human edits (default)
    - ``human_first``: Human writes, AI expands/polishes
    - ``interleaved``: Alternate between human and AI paragraphs
    """

    def __init__(
        self,
        run_dir: Path,
        llm_client: Any = None,
        style: str = "neurips",
    ) -> None:
        self.run_dir = run_dir
        self.llm = llm_client
        self.style = style
        self.sections: list[SectionDraft] = []
        self.outline: str = ""

    def load_outline(self, outline_path: Path | None = None) -> str:
        """Load the paper outline from Stage 16 output."""
        if outline_path is None:
            outline_path = self.run_dir / "stage-16" / "outline.md"
        if outline_path.exists():
            self.outline = outline_path.read_text(encoding="utf-8")
            # Parse section names from outline
            self.sections = self._parse_sections_from_outline(self.outline)
        return self.outline

    def write_section(
        self,
        section_name: str,
        context: str = "",
        human_notes: str = "",
    ) -> str:
        """AI writes a section draft.

        Args:
            section_name: Name of the section.
            context: Relevant context (analysis, results, etc).
            human_notes: Human's notes on what to include.

        Returns:
            Generated section text.
        """
        if self.llm is None:
            return f"[Section '{section_name}' requires LLM for generation]"

        try:
            response = self.llm.chat([
                {"role": "system", "content": (
                    f"You are writing the '{section_name}' section of a "
                    f"{self.style.upper()} conference paper. "
                    "Write clear, concise academic prose. "
                    "Include appropriate citations in [Author, Year] format."
                )},
                {"role": "user", "content": (
                    f"## Paper Outline\n{self.outline[:2000]}\n\n"
                    f"## Context\n{context[:2000]}\n\n"
                    + (f"## Human Notes\n{human_notes}\n\n" if human_notes else "")
                    + f"Write the {section_name} section."
                )},
            ])

            # Update section
            section = self._get_or_create_section(section_name)
            section.ai_version = response
            section.content = response
            section.status = "ai_draft"
            return response
        except Exception as exc:
            logger.error("Section writing failed: %s", exc)
            return f"[Error writing section: {exc}]"

    def human_edit_section(
        self, section_name: str, content: str
    ) -> None:
        """Human directly edits a section."""
        section = self._get_or_create_section(section_name)
        section.human_version = content
        section.content = content
        section.status = "human_edited"
        section.revision_count += 1

    def ai_polish(
        self, section_name: str, instructions: str = ""
    ) -> str:
        """AI polishes the human-edited version.

        Args:
            section_name: Section to polish.
            instructions: Specific polishing instructions.

        Returns:
            Polished text.
        """
        section = self._get_or_create_section(section_name)
        if not section.content:
            return ""

        if self.llm is None:
            return section.content

        try:
            response = self.llm.chat([
                {"role": "system", "content": (
                    f"Polish this {self.style.upper()} paper section. "
                    "Improve clarity, academic tone, and flow while "
                    "preserving all technical content and meaning. "
                    "Do not add fabricated citations or results."
                )},
                {"role": "user", "content": (
                    f"## Section: {section_name}\n\n"
                    f"{section.content}\n\n"
                    + (f"## Instructions\n{instructions}" if instructions else "")
                )},
            ])
            section.content = response
            section.status = "ai_polished"
            section.revision_count += 1
            return response
        except Exception as exc:
            logger.error("Polish failed: %s", exc)
            return section.content

    def finalize_section(self, section_name: str) -> None:
        """Mark a section as finalized."""
        section = self._get_or_create_section(section_name)
        section.status = "finalized"

    def compile_paper(self) -> str:
        """Compile all sections into a complete paper draft."""
        parts = []
        for section in self.sections:
            if section.content:
                parts.append(f"## {section.name}\n\n{section.content}")
        return "\n\n".join(parts)

    def get_status(self) -> dict[str, Any]:
        """Return the current writing status."""
        return {
            "total_sections": len(self.sections),
            "completed": sum(
                1 for s in self.sections if s.status == "finalized"
            ),
            "in_progress": sum(
                1 for s in self.sections
                if s.status in ("ai_draft", "human_edited", "ai_polished")
            ),
            "pending": sum(
                1 for s in self.sections if s.status == "pending"
            ),
            "sections": [s.to_dict() for s in self.sections],
        }

    def save(self) -> None:
        """Save paper writing state."""
        hitl_dir = self.run_dir / "hitl"
        hitl_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "style": self.style,
            "sections": [s.to_dict() for s in self.sections],
            "status": self.get_status(),
        }
        (hitl_dir / "paper_cowriter.json").write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )

    def _get_or_create_section(self, name: str) -> SectionDraft:
        for section in self.sections:
            if section.name.lower() == name.lower():
                return section
        section = SectionDraft(name=name)
        self.sections.append(section)
        return section

    def _parse_sections_from_outline(
        self, outline: str
    ) -> list[SectionDraft]:
        """Parse section names from a markdown outline."""
        sections = []
        for line in outline.split("\n"):
            stripped = line.strip()
            if stripped.startswith("## "):
                name = stripped[3:].strip()
                if name:
                    sections.append(SectionDraft(name=name))
            elif stripped.startswith("# ") and not stripped.startswith("# Auto"):
                name = stripped[2:].strip()
                if name:
                    sections.append(SectionDraft(name=name))
        return sections
