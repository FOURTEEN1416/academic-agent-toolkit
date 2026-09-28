"""ARC-Bench framework adapters — one module per competing autonomous-research system.

Each adapter subclasses :class:`FrameworkAdapter` and produces an output
directory in the ResearchClaw stage-artifact layout that the ARC-Bench
judge / evaluator scripts read.
"""

from .base import FrameworkAdapter, FrameworkResult, StandardArtifacts
from .researchclaw_adapter import ResearchClawAdapter
from .ai_scientist_v2_adapter import AIScientistV2Adapter
from .agent_lab_adapter import AgentLabAdapter
from .aide_adapter import AideAdapter

__all__ = [
    "FrameworkAdapter",
    "FrameworkResult",
    "StandardArtifacts",
    "ResearchClawAdapter",
    "AIScientistV2Adapter",
    "AgentLabAdapter",
    "AideAdapter",
]
