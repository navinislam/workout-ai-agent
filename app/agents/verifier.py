from __future__ import annotations

"""
Verifier Agent (Agents SDK)
---------------------------
Validates a `WorkoutPlan` against a `UserProfile` using the Agents SDK.
Heuristic calculations have been removed. The agent reasons about:
- Time fit, balance, avoidance, progression sanity.
Returns a structured JSON report matching the previous shape.
"""

import json
from typing import Dict, Any

from agents import Agent, Runner, RunResult
from app.models.schemas import UserProfile, WorkoutPlan
from app.agents.constraints import resolve_avoid_terms


verifier_agent = Agent(
    name="Workout Verifier",
    instructions=(
        "Given a user profile and a workout plan, verify: (1) time fit per day vs minutes_per_day, "
        "(2) weekly balance across squat/hinge/push/pull, (3) avoidance of forbidden exercises, (4) basic progression sanity. "
        "Return STRICT JSON with keys: ok:bool, time_fit:{ok, per_day_minutes:list[number], limit:int} (estimate reasonably), "
        "balance:{ok, weekly_presence_days:{squat_like:int, hinge_like:int, push_like:int, pull_like:int}}, "
        "avoidance:{ok, violations:list[str], expanded_terms:list[str]}, progression:{ok, issues:list[str], notes:str}."
    ),
)


def verify_plan(profile: UserProfile, plan: WorkoutPlan) -> Dict[str, Any]:
    """Run the verifier agent and return a structured report."""
    expanded, _ = resolve_avoid_terms(profile.avoid_exercises or [])
    payload = {
        "profile": profile.model_dump(),
        "plan": plan.model_dump(),
        "avoid_expanded": expanded,
    }
    prompt = "Validate this plan against the profile and avoid terms. Return strict JSON.\n" + json.dumps(payload, ensure_ascii=False)
    result: RunResult = Runner.run_sync(verifier_agent, input=prompt)
    out = result.final_output or "{}"
    try:
        data = json.loads(out)
        if isinstance(data, dict):
            return data
        return {"ok": False, "time_fit": {}, "balance": {}, "avoidance": {}, "progression": {}}
    except Exception:
        return {"ok": False, "time_fit": {}, "balance": {}, "avoidance": {}, "progression": {}}
