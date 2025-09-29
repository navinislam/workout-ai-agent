from __future__ import annotations

"""
Agents Orchestrator
-------------------
Coordinates the Programmer → Verifier sequence using Agents SDK-based agents.
"""

from typing import Dict, Any
import os

from app.models.schemas import UserProfile, WorkoutPlan
from app.agents.programmer import generate_plan
from app.agents.verifier import verify_plan
from app.agents.subber import suggest_substitutions
from app.rag.templates_rag import search_templates, get_template, map_sbs_to_workout_plan


def program_and_verify(profile: UserProfile) -> Dict[str, Any]:
    """Generate a plan and verify it via the new flow.

    New Flow:
    1) Find the best-matching SBS template (filesystem-backed stub for now).
    2) Map template to a `WorkoutPlan`.
    3) Run Subber to substitute exercises violating constraints.
    4) Verify the final plan.

    Fallback: If template selection or mapping fails, fall back to the
    existing programmer agent.
    """
    # Phase 0: introduce a simple env flag to optionally bootstrap from
    # a template via RAG. Default is false to keep a pure LLM-first flow.
    #
    # USE_TEMPLATE_BOOTSTRAP=true → try RAG template first then fall back to LLM
    # USE_TEMPLATE_BOOTSTRAP=false (default) → go straight to LLM plan
    use_bootstrap = str(os.getenv("USE_TEMPLATE_BOOTSTRAP", "false")).lower() in {"1", "true", "yes"}
    # MAX_REVISIONS reserved for Phase 4 loop; keep a sane default now.
    # Not used yet to avoid overengineering the single-pass flow.
    _max_revisions = int(os.getenv("MAX_REVISIONS", "2"))

    plan: WorkoutPlan | None = None
    if use_bootstrap:
        try:
            query_terms = [profile.goal or "", str(profile.days_per_week or "")]
            query = " ".join(t for t in query_terms if t)
            hits = search_templates(
                query,
                days=profile.days_per_week,
                equipment=",".join(profile.equipment_available or []),
                top_k=1,
            )
            if hits:
                tmpl = get_template(hits[0].path)
                plan = map_sbs_to_workout_plan(tmpl, profile)
        except Exception:
            plan = None

    # Fallback to programmer if needed or when bootstrap disabled
    if plan is None or not getattr(plan, "days", None):
        plan = generate_plan(profile)

    # Step 3: non-mutating substitution suggestions (Phase 1)
    sub_suggestions = suggest_substitutions(plan, profile)

    # Step 4: verification
    verification = verify_plan(profile, plan)
    return {
        "profile": profile.model_dump(),
        "plan": plan.model_dump(),
        "verification": verification,
        "substitution_suggestions": sub_suggestions,
        "assumptions": {
            "days": profile.days_per_week,
            "minutes_per_day": profile.minutes_per_day,
            "goal": profile.goal,
        },
        "citations": [
            # include template source if used
            plan.metadata.get("source_url") if isinstance(getattr(plan, "metadata", {}), dict) else None
        ],
    }
