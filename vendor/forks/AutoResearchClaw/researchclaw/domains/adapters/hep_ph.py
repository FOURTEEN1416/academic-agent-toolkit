"""HEP phenomenology domain prompt adapter.

After the Phase-B refactor, HEP narrative prose lives in the dedicated
:mod:`researchclaw.prompts.hep` bank (selected by the PromptManager when
``domain='hep_ph'``). This adapter therefore contains no stage-level
overlays — it only:

1. Satisfies the abstract contract of :class:`PromptAdapter` by returning
   empty blocks (ML and HEP prompts are domain-native already).
2. Declares the preferred LaTeX template (``jhep``) and any final-pass
   guidance for the export stage.
"""

from __future__ import annotations

from typing import Any

from researchclaw.domains.prompt_adapter import PromptAdapter, PromptBlocks


class HEPPhPromptAdapter(PromptAdapter):
    """Adapter for HEP phenomenology (dark matter, BSM, collider physics)."""

    def get_code_generation_blocks(self, context: dict[str, Any]) -> PromptBlocks:
        return PromptBlocks()

    def get_experiment_design_blocks(self, context: dict[str, Any]) -> PromptBlocks:
        return PromptBlocks()

    def get_result_analysis_blocks(self, context: dict[str, Any]) -> PromptBlocks:
        return PromptBlocks()

    def get_export_publish_blocks(self, context: dict[str, Any]) -> PromptBlocks:
        """Declare preferred physics template for the export pass."""
        guidance = (
            "This is an HEP-phenomenology manuscript; the export pass must preserve "
            "natural units, Feynman-diagram language, and citations to original "
            "experimental papers. Do NOT insert NeurIPS checklists or broader-impact "
            "paragraphs during final formatting."
        )
        return PromptBlocks(
            export_publish_guidance=guidance,
            preferred_template="jhep",
        )
