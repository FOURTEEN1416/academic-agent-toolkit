"""AutoResearchClaw Human-in-the-Loop (HITL) Co-Pilot System.

Provides human-AI collaboration capabilities for the 23-stage research pipeline.
Supports multiple intervention modes from fully automatic to deep collaboration.
"""

from __future__ import annotations

from researchclaw.hitl.config import (
    HITLConfig,
    InterventionMode,
    StagePolicy,
)
from researchclaw.hitl.intervention import (
    HumanAction,
    HumanInput,
    Intervention,
    InterventionType,
    PauseReason,
    WaitingState,
)
from researchclaw.hitl.session import HITLSession, SessionState

__all__ = [
    "HITLConfig",
    "HITLSession",
    "HumanAction",
    "HumanInput",
    "Intervention",
    "InterventionMode",
    "InterventionType",
    "PauseReason",
    "SessionState",
    "StagePolicy",
    "WaitingState",
]
