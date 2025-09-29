from __future__ import annotations

from app.rag.templates_rag import search_templates

"""
Programmer Agent (Agents SDK)
-----------------------------
Generates a `WorkoutPlan` using the Agents SDK with a tool that searches
the exercise RAG index. Heuristic selection logic has been removed.
"""

import json
from typing import List

from agents import Agent, Runner, RunResult, function_tool
from app.models.schemas import UserProfile, WorkoutPlan, WorkoutDay, WorkoutBlock, WorkoutExercise
from app.agents.constraints import resolve_avoid_terms
from app.rag.milvus_rag import search_exercises


@function_tool
def search_exercise(query: str, pattern: str | None = None, top_k: int = 10) -> List[dict]:
    """Search exercises via the RAG index and return top matches as dicts."""
    try:
        return search_exercises(query=query, pattern=pattern, top_k=top_k)
    except Exception:
        return []

@function_tool
def search_template(query: str,
    *,
    days: int | None = None,
    equipment: str,
    top_k: int = 5):
    """Search templates via the RAG index and return top matches as dicts."""
    try:
        return search_templates(query=query, days=days, equipment=equipment, top_k=top_k)
    except Exception:
        return []

programmer_agent = Agent(
    name="Workout Programmer",
    instructions=(
        "You are a seasoned strength coach. Create a weekly workout plan that fits the user's constraints. "
        "Use the search tool(s) to pick realistic templates and exercise names. Return STRICT JSON with schema: {days:[{name, focus, blocks:[{name, exercises:[{name, sets:int, reps:str, intensity?:str, rest_seconds?:int}]}]}], metadata:{notes:str}}. "
    ),
    tools=[search_exercise, search_template],
)


def generate_plan(profile: UserProfile) -> WorkoutPlan:
    """Run the programmer agent and coerce the output into `WorkoutPlan`."""
    days = max(2, min(6, profile.days_per_week or 4))
    expanded_avoids, _ = resolve_avoid_terms(profile.avoid_exercises or [])
    equipment = profile.equipment_available or []
    req = {
        "days_per_week": days,
        "minutes_per_day": int(profile.minutes_per_day or 60),
        "goal": profile.goal or "general strength",
        "equipment_available": equipment,
    }
    prompt = (
        "Generate a weekly plan that meets these constraints.\n" +
        json.dumps(req, ensure_ascii=False) +
        "\nReturn STRICT JSON only in the required schema."
    )
    result: RunResult = Runner.run_sync(programmer_agent, input=prompt)
    out = result.final_output or "{}"

    # Coerce to Pydantic models
    try:
        data = json.loads(out)
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
                        )
                    )
                blocks_out.append(WorkoutBlock(name=str(b.get("name", "Block")), exercises=exs))
            days_out.append(WorkoutDay(name=str(d.get("name", "Day")), focus=d.get("focus"), blocks=blocks_out))
        metadata = data.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {"notes": "LLM-generated plan"}
        return WorkoutPlan(days=days_out, metadata=metadata)
    except Exception:
        # Minimal empty plan if parsing fails
        return WorkoutPlan(days=[], metadata={"notes": "LLM-generated plan (parse failed)"})
