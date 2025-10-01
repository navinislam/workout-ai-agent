from __future__ import annotations

"""
Verifier Agent (Agents SDK)
---------------------------
Two-phase verification:
1. Fast deterministic checks (Python, <1ms)
2. Semantic checks (LLM, only if fast checks pass)

Returns structured report with suggested_edits for actionable fixes.
"""

import json
from typing import Dict, Any, List

from agents import Agent, RunResult
from app.models.schemas import UserProfile, WorkoutPlan
from app.agents.utils import run_agent_sync
from app.agents.verifier_fast import fast_verify, generate_mechanical_edits_from_fast_check


# Semantic verifier focuses on progression quality and appropriateness
semantic_verifier_agent = Agent(
    name="Workout Semantic Verifier",
    instructions=(
        "Given a user profile and workout plan that passed basic checks, evaluate: "
        "(1) progression quality: is volume progression logical across weeks/sessions? "
        "(2) exercise appropriateness: do exercises match user's goal and experience level? "
        "(3) programming wisdom: any red flags in exercise selection, order, or volume distribution? "
        "Return STRICT JSON with keys: ok:bool, progression:{ok:bool, issues:list[str], notes:str}, "
        "suggested_edits:[{type:str, reason:str, loc:{day_idx?:int, block_idx?:int, ex_idx?:int}, payload:dict}]. "
        "Edit types: replace_exercise, tune_sets, tune_reps, add_rest, remove_exercise, add_exercise, reorder_days, add_note. "
        "Only suggest edits for actual issues, not theoretical improvements."
    ),
)


def verify_plan(profile: UserProfile, plan: WorkoutPlan, semantic_only: bool = False) -> Dict[str, Any]:
    """Run verification with fast checks first, then semantic if needed.

    Args:
        profile: User constraints and preferences
        plan: Workout plan to verify
        semantic_only: If True, skip fast checks (for iterations where fast checks already passed)

    Returns:
        Comprehensive report with suggested_edits array
    """
    if semantic_only:
        # Skip fast checks, go straight to semantic
        fast_report = {
            "ok": True,
            "time_fit": {"ok": True, "per_day_minutes": [], "limit": profile.minutes_per_day or 60},
            "balance": {"ok": True, "weekly_presence_days": {}},
            "avoidance": {"ok": True, "violations": [], "expanded_terms": []},
            "skipped": True,
        }
        mechanical_edits: List[Dict[str, Any]] = []
    else:
        # Run fast deterministic checks
        fast_report = fast_verify(profile, plan)
        mechanical_edits = generate_mechanical_edits_from_fast_check(profile, plan, fast_report)

        # If fast checks fail, return immediately with mechanical edits
        if not fast_report["ok"]:
            return {
                "ok": False,
                "time_fit": fast_report["time_fit"],
                "balance": fast_report["balance"],
                "avoidance": fast_report["avoidance"],
                "progression": {"ok": True, "issues": [], "notes": "Fast checks failed, skipped semantic validation"},
                "suggested_edits": mechanical_edits,
                "fast_check_failed": True,
            }

    # Fast checks passed (or skipped), run semantic validation
    payload = {
        "profile": profile.model_dump(),
        "plan": plan.model_dump(),
        "goal": profile.goal or "general strength",
    }
    prompt = (
        "Evaluate this plan for progression quality and programming wisdom. "
        "Return strict JSON with suggested_edits array.\n" + json.dumps(payload, ensure_ascii=False)
    )

    print(f"🤖 Using LLM for: semantic_verify_plan ({len(plan.days)} days)")
    try:
        result: RunResult = run_agent_sync(semantic_verifier_agent, input=prompt)
        out = result.final_output or "{}"
        data = json.loads(out)

        if not isinstance(data, dict):
            data = {"ok": True, "progression": {"ok": True, "issues": [], "notes": "Parse failed"}, "suggested_edits": []}

        # Merge fast report with semantic report
        progression = data.get("progression", {"ok": True, "issues": [], "notes": ""})
        semantic_edits = data.get("suggested_edits", [])
        all_edits = mechanical_edits + semantic_edits

        overall_ok = fast_report["ok"] and progression.get("ok", True)

        return {
            "ok": overall_ok,
            "time_fit": fast_report["time_fit"],
            "balance": fast_report["balance"],
            "avoidance": fast_report["avoidance"],
            "progression": progression,
            "suggested_edits": all_edits,
        }

    except Exception as e:
        # Fallback on semantic failure
        return {
            "ok": fast_report["ok"],
            "time_fit": fast_report["time_fit"],
            "balance": fast_report["balance"],
            "avoidance": fast_report["avoidance"],
            "progression": {"ok": True, "issues": [], "notes": f"Semantic check failed: {str(e)}"},
            "suggested_edits": mechanical_edits,
        }
