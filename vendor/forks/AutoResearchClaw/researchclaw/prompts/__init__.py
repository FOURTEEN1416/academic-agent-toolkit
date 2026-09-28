"""Prompt externalization for the ResearchClaw pipeline (domain-aware).

Layout
------
* ``manager``  — ``PromptManager``, ``RenderedPrompt``, ``_render``.
  Domain-agnostic. Selects a stage bank at construction time via the
  ``domain`` keyword.
* ``shared``   — ``_DEFAULT_BLOCKS``, ``_DEFAULT_SUB_PROMPTS``,
  ``SECTION_WORD_TARGETS``, ``_SECTION_TARGET_ALIASES``. Used by both
  banks.
* ``ml``       — ML stage bank (default / legacy behaviour). Debate roles
  for innovator / pragmatist / contrarian.
* ``hep``      — HEP-ph (dark matter / BSM / collider) stage bank.
  Debate roles for theorist / phenomenologist / experimentalist.

Public API (backward-compatible)
--------------------------------
``from researchclaw.prompts import PromptManager``           — unchanged
``from researchclaw.prompts import RenderedPrompt``           — unchanged
``from researchclaw.prompts import DEBATE_ROLES_HYPOTHESIS``  — resolves to
the ML bank's roles. ML call sites that imported this constant directly
continue to see the same dict. HEP stages should use
``pm.debate_roles_hypothesis()`` which reads from the manager's domain.
``from researchclaw.prompts import SECTION_WORD_TARGETS``     — unchanged.

Usage
-----
::

    from researchclaw.prompts import PromptManager

    pm = PromptManager()                                # ML defaults
    pm = PromptManager(domain="hep_ph")                 # HEP bank
    pm = PromptManager("my_prompts.yaml", domain="ml")  # with user overrides

    sp = pm.for_stage("topic_init", topic="Z' dilepton search", domains="hep-ph")
    resp = llm.chat(
        [{"role": "user", "content": sp.user}],
        system=sp.system,
        json_mode=sp.json_mode,
        max_tokens=sp.max_tokens,
    )
"""

from __future__ import annotations

from researchclaw.prompts.manager import (
    PromptManager,
    RenderedPrompt,
    SUPPORTED_DOMAINS,
    _render,
)
from researchclaw.prompts.shared import (
    SECTION_WORD_TARGETS,
    _DEFAULT_BLOCKS,
    _DEFAULT_SUB_PROMPTS,
    _SECTION_TARGET_ALIASES,
)

# Legacy ML constants — re-exported so existing call sites keep working.
from researchclaw.prompts.ml import (
    DEBATE_ROLES_ANALYSIS,
    DEBATE_ROLES_HYPOTHESIS,
    STAGES as _DEFAULT_STAGES,
)

__all__ = [
    "PromptManager",
    "RenderedPrompt",
    "SUPPORTED_DOMAINS",
    "_render",
    "SECTION_WORD_TARGETS",
    "_SECTION_TARGET_ALIASES",
    "_DEFAULT_BLOCKS",
    "_DEFAULT_SUB_PROMPTS",
    "_DEFAULT_STAGES",
    "DEBATE_ROLES_HYPOTHESIS",
    "DEBATE_ROLES_ANALYSIS",
]
