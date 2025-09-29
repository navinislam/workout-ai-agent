from __future__ import annotations

"""
LLM Programmer Agent (via Agents SDK)
-------------------------------------
This module now delegates to the primary Agents SDK-based programmer to
avoid duplicated logic and heuristics.
"""

from app.models.schemas import UserProfile, WorkoutPlan
from app.agents.programmer import generate_plan


def generate_plan_llm(profile: UserProfile) -> WorkoutPlan | None:
    """Compatibility wrapper that uses the Agents SDK programmer implementation."""
    return generate_plan(profile)
