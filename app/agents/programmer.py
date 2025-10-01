from __future__ import annotations

from app.rag.templates_rag import search_templates

"""
Programmer Agent (Agents SDK)
-----------------------------
Generates a `WorkoutPlan` using the Agents SDK with a tool that searches
the exercise RAG index. Heuristic selection logic has been removed.
"""

import json
from typing import List, Optional

from agents import Agent, RunResult, function_tool
from app.models.schemas import UserProfile, WorkoutPlan, WorkoutDay, WorkoutBlock, WorkoutExercise, TrainingHistory
from app.agents.constraints import resolve_avoid_terms
from app.agents.utils import run_agent_sync
from app.rag.milvus_rag import search_exercises


@function_tool
def search_exercise(query: str, pattern: str | None = None, top_k: int = 10) -> List[dict]:
    """Search exercises via the RAG index and return top matches as dicts."""
    try:
        print(f"      🔍 Tool called: search_exercise(query='{query}', pattern={pattern})")
        results = search_exercises(query=query, pattern=pattern, top_k=top_k)
        print(f"         → Found {len(results)} exercises")
        return results
    except Exception as e:
        print(f"         → Search failed: {str(e)}")
        return []

@function_tool
def search_template(query: str,
    *,
    days: int | None = None,
    equipment: str,
    top_k: int = 5):
    """Search templates via the RAG index and return top matches as dicts."""
    try:
        print(f"      🔍 Tool called: search_template(query='{query}', days={days}, equipment='{equipment}')")
        results = search_templates(query=query, days=days, equipment=equipment, top_k=top_k)
        print(f"         → Found {len(results)} templates")
        return results
    except Exception as e:
        print(f"         → Search failed: {str(e)}")
        return []

programmer_agent = Agent(
    name="Workout Programmer",
    instructions=(
        "You are a seasoned strength/bodybuilding coach. Create a weekly workout plan that fits the user's constraints. "
        "WORKFLOW: 1) First, call search_template to find a relevant template matching the user's goal, days, and equipment. "
        "2) If a good template is found, adapt it to the user's constraints. If not, generate from scratch. "
        "3) Use search_exercise to validate exercise names and find alternatives. "
        "Return STRICT JSON with schema: {days:[{name, focus, blocks:[{name, exercises:[{name, sets:int, reps:str, intensity?:str, rest_seconds?:int}]}]}], metadata:{notes:str}}. "
    ),
    tools=[search_exercise, search_template],
)


def _coerce_to_workout_plan(data: dict) -> WorkoutPlan:
    """Helper to convert LLM JSON output to WorkoutPlan Pydantic model."""
    days_out: List[WorkoutDay] = []
    for d in data.get("days", []):
        blocks_out: List[WorkoutBlock] = []
        for b in d.get("blocks", []):
            exs: List[WorkoutExercise] = []
            for ex in b.get("exercises", []):
                exs.append(
                    WorkoutExercise(
                        name=str(ex.get("name", "Exercise")),
                        sets=int(ex.get("sets", 3)),
                        reps=str(ex.get("reps", "5-8")),
                        intensity=ex.get("intensity"),
                        rest_seconds=ex.get("rest_seconds"),
                        notes=ex.get("notes"),
                    )
                )
            blocks_out.append(WorkoutBlock(name=str(b.get("name", "Block")), exercises=exs))
        days_out.append(WorkoutDay(name=str(d.get("name", "Day")), focus=d.get("focus"), blocks=blocks_out))
    metadata = data.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {"notes": "LLM-generated plan"}
    return WorkoutPlan(days=days_out, metadata=metadata)

def _volume_suggestions(training_history: Optional[TrainingHistory]) -> Optional[str]:
    """Generate volume suggestions based on training history."""
    if training_history:
        if training_history == TrainingHistory.beginner:
            return "Make sure volume is low"
        elif training_history == TrainingHistory.intermediate:
            return "Make sure volume is medium"
        elif training_history == TrainingHistory.advanced:
            return "Make sure volume is high"
    return None


def generate_plan(profile: UserProfile) -> WorkoutPlan:
    """Run the programmer agent and coerce the output into `WorkoutPlan`."""
    days = max(2, min(6, profile.days_per_week or 4))
    expanded_avoids, _ = resolve_avoid_terms(profile.avoid_exercises or [])
    equipment = profile.equipment_available or []
    volume_suggestions = _volume_suggestions(training_history=profile.training_history)

    req = {
        "days_per_week": days,
        "minutes_per_day": int(profile.minutes_per_day or 60),
        "goal": profile.goal or "general strength",
        "equipment_available": equipment,
        "volume_suggestions": volume_suggestions,
    }
    prompt = (
        "Generate a weekly plan that meets these constraints. \n" +
        json.dumps(req, ensure_ascii=False) +
        "\nReturn STRICT JSON only in the required schema."
    )
    print(f"🤖 Using LLM for: generate_plan ({days} days, {profile.goal})")
    result: RunResult = run_agent_sync(programmer_agent, input=prompt)
    out = result.final_output or "{}"

    try:
        data = json.loads(out)
        return _coerce_to_workout_plan(data)
    except Exception:
        return WorkoutPlan(days=[], metadata={"notes": "LLM-generated plan (parse failed)"})


def revise_plan(
    current_plan: WorkoutPlan,
    profile: UserProfile,
    issues: List[str],
) -> WorkoutPlan:
    """Revise an existing plan based on high-level issue descriptions.

    This function handles semantic revisions that require reasoning:
    - Rebalancing volume across days
    - Adjusting progression schemes
    - Improving exercise selection for goals
    - Fixing programming logic issues

    Mechanical edits (name swaps, set/rep tweaks) should be applied
    deterministically by the orchestrator before calling this.

    Args:
        current_plan: The plan to revise
        profile: User constraints
        issues: High-level descriptions of what needs fixing

    Returns:
        Revised WorkoutPlan
    """
    if not issues:
        return current_plan

    req = {
        "profile": profile.model_dump(),
        "current_plan": current_plan.model_dump(),
        "issues": issues,
    }

    prompt = (
        "You are revising an existing workout plan based on identified issues. "
        "The issues require semantic reasoning and programming wisdom to fix. "
        "Maintain the overall structure where possible, but make necessary changes to address the issues. "
        "Return STRICT JSON in the same schema as generate_plan.\n\n"
        "Context:\n" + json.dumps(req, ensure_ascii=False)
    )

    print(f"🤖 Using LLM for: revise_plan ({len(issues)} issues)")
    result: RunResult = run_agent_sync(programmer_agent, input=prompt)
    out = result.final_output or "{}"

    try:
        data = json.loads(out)
        revised = _coerce_to_workout_plan(data)
        # Preserve some metadata
        revised.metadata["revision_count"] = current_plan.metadata.get("revision_count", 0) + 1
        revised.metadata["last_issues"] = issues
        return revised
    except Exception:
        # On failure, return current plan with error note
        current_plan.metadata["revision_failed"] = True
        return current_plan
