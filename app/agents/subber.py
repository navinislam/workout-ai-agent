import json
import os
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv
from pydantic import BaseModel
from app.models.schemas import (
    UserProfile,
    WorkoutPlan,
    WorkoutDay,
    WorkoutBlock,
    WorkoutExercise,
)

from app.rag.milvus_rag import ingest_exercises, search_exercises


from agents import Agent, RunResult, function_tool
from app.agents.utils import run_agent_sync


load_dotenv()
"""
-----------------------------------------------------------------------------
In this example, we explore OpenAI's Agents SDK with the following features:
- Tool usage
- Output models
- Internal messages
- Metrics

This example shows the parallelization pattern. We run the agent 
three times in parallel, and pick the best result.
-----------------------------------------------------------------------------
"""


# 1. Define the output model for the weather data
class Exercise(BaseModel):
    name: str



# 2. Define a function tool to get weather information
@function_tool
def search_exercise_sub(
    exercise: str,
    pattern: Optional[str] = None,
    avoid_terms: Optional[str] = None,
    top_k: int = 15,
) -> List[Exercise]:
    """Return substitution candidates, excluding avoid terms and duplicates."""
    print(f"      🔍 Tool called: search_exercise_sub(exercise='{exercise}', pattern={pattern})")
    results = search_exercises(query=exercise, pattern=pattern, top_k=top_k)

    avoid: set[str] = set()
    if isinstance(avoid_terms, str) and avoid_terms.strip():
        avoid = {t.strip().lower() for t in avoid_terms.split(',') if t.strip()}

    out: List[Exercise] = []
    seen: set[str] = set()
    for r in results:
        name = str(r.get('name', '')).strip()
        if not name:
            continue
        lname = name.lower()
        if avoid and any(term in lname for term in avoid):
            continue
        if lname in seen:
            continue
        seen.add(lname)
        out.append(Exercise(name=name))
    print(f"         → Found {len(out)} substitution candidates")
    return out


# 3. Define the agent with the function tool registered
agent = Agent(
    name="Exercise substitution Agent",
    instructions="You are an expert fitness coach who wants to find good substitutions for exercises for clients.",
    tools=[search_exercise_sub],  # Register the function in the agent
)

def return_best_substitution_exercise(
    exercise: Exercise,
    *,
    pattern: Optional[str] = None,
    avoid_terms: Optional[List[str]] = None,
    top_k: int = 15,
) -> Optional[Exercise]:
    """LLM-driven best substitution using the agent + tool only.

    Enforces tool usage and strict JSON schema. Performs a single retry on
    parse/validation failure. Does not fall back to deterministic logic.
    Returns None only if the agent returns an empty candidate set.
    Raises RuntimeError on repeated failure to produce valid JSON.
    """
    avoid_terms = avoid_terms or []
    payload = {
        "target_exercise": exercise.name,
        "pattern": pattern,
        "avoid_terms": avoid_terms,
        "top_k": top_k,
    }
    instructions = (
        "You are selecting a substitution for a target exercise. "
        "You MUST call the tool `search_exercise_sub` with the given payload. "
        "Pass `exercise`, `pattern`, `avoid_terms` as a comma-separated string, and `top_k`. "
        "Prefer biomechanically similar movements and common gym availability. "
        "Return STRICT JSON ONLY in this schema: {"
        "\"best\":{\"name\":string}, \"candidates\":[{\"name\":string}]}."
    )

    def _run_once() -> Optional[Exercise]:
        print(f"🤖 Using LLM for: substitute_exercise ({exercise.name})")
        result: RunResult = run_agent_sync(
            agent,
            input=(instructions + "\nPayload:\n" + json.dumps(payload, ensure_ascii=False)),
        )
        out = result.final_output or "{}"
        data = json.loads(out)
        if not isinstance(data, dict):
            raise ValueError("Agent output is not a JSON object")
        best = data.get("best")
        if not isinstance(best, dict):
            raise ValueError("Missing or invalid 'best' object")
        best_name = str(best.get("name") or "").strip()
        if not best_name:
            # Try first candidate
            cands = data.get("candidates") or []
            if isinstance(cands, list) and cands:
                cand0 = cands[0]
                if isinstance(cand0, dict):
                    best_name = str(cand0.get("name") or "").strip()
        if not best_name:
            return None
        if best_name.lower() == exercise.name.strip().lower():
            # treat echo as invalid so the caller can decide
            return None
        return Exercise(name=best_name)

    try:
        pick = _run_once()
    except Exception as e:
        # Single retry
        try:
            pick = _run_once()
        except Exception as e2:
            raise RuntimeError(f"Substitution agent failed: {e2}")
    return pick
#
# if __name__ == "__main__":
#     asyncio.run(main())


def _infer_pattern_from_focus(focus: Optional[str]) -> Optional[str]:
    if not focus:
        return None
    f = focus.lower()
    if "squat" in f:
        return "squat"
    if "hinge" in f or "deadlift" in f:
        return "hinge"
    if "push" in f or "press" in f:
        return "push"
    if "pull" in f or "row" in f:
        return "pull"
    return None


def substitute_plan_exercises(plan: WorkoutPlan, profile: UserProfile) -> WorkoutPlan:
    """Replace exercises that match avoid terms with suggested alternatives.

    Minimal implementation:
    - Detect exercises whose names contain any `profile.avoid_exercises` term (case-insensitive).
    - Query substitutions via `search_exercise_sub` using inferred pattern from day focus and avoid list.
    - Replace with the first candidate name; keep sets/reps/rest/notes.
    - If search fails or no candidates, keep original exercise.
    """
    avoids = {t.strip().lower() for t in (profile.avoid_exercises or []) if t and t.strip()}
    if not avoids:
        return plan

    new_days: List[WorkoutDay] = []
    for day in plan.days:
        pattern = _infer_pattern_from_focus(day.focus)
        new_blocks: List[WorkoutBlock] = []
        for block in day.blocks:
            new_exs: List[WorkoutExercise] = []
            for ex in block.exercises:
                name_lc = ex.name.lower()
                needs_sub = any(term in name_lc for term in avoids)
                if not needs_sub:
                    new_exs.append(ex)
                    continue
                # Use the agent strictly; allow it to fail silently per-exercise
                replacement_name: Optional[str] = None
                try:
                    pick = return_best_substitution_exercise(
                        Exercise(name=ex.name),
                        pattern=pattern,
                        avoid_terms=sorted(list(avoids)),
                        top_k=15,
                    )
                    if pick is not None:
                        replacement_name = pick.name
                except Exception:
                    replacement_name = None

                if replacement_name:
                    new_exs.append(
                        WorkoutExercise(
                            name=replacement_name,
                            sets=ex.sets,
                            reps=ex.reps,
                            intensity=ex.intensity,
                            rest_seconds=ex.rest_seconds,
                            notes=ex.notes,
                        )
                    )
                else:
                    new_exs.append(ex)
            new_blocks.append(WorkoutBlock(name=block.name, exercises=new_exs))
        new_days.append(WorkoutDay(name=day.name, focus=day.focus, blocks=new_blocks))

    return WorkoutPlan(days=new_days, metadata=dict(plan.metadata))


def suggest_substitutions(plan: WorkoutPlan, profile: UserProfile) -> List[Dict[str, Any]]:
    """Propose exercise substitutions without mutating the input plan.

    Minimal, non-overengineered approach for Phase 1:
    - Identify exercises whose name contains any user-provided avoid term (case-insensitive).
    - For each hit, attempt an LLM-guided best substitution via `return_best_substitution_exercise`.
      - If the LLM step fails, fall back to the first RAG candidate from `search_exercises`.
    - Return a list of dict suggestions with stable keys that downstream code can apply:
        { day_idx, block_idx, ex_idx, original, best, candidates, rationale }

    Notes:
    - We keep this function pure: it only returns suggestions; it does not modify the plan.
    - Rationale is a simple string for now to aid debugging; no extra reasoning is required.
    - This is intentionally light-weight; we will add richer schemas/agents later in Phase 2–4.
    """
    avoids = {t.strip().lower() for t in (profile.avoid_exercises or []) if t and t.strip()}
    if not avoids:
        return []

    suggestions: List[Dict[str, Any]] = []
    for di, day in enumerate(plan.days):
        pattern = _infer_pattern_from_focus(day.focus)
        for bi, block in enumerate(day.blocks):
            for ei, ex in enumerate(block.exercises):
                name_lc = ex.name.lower()
                if not any(term in name_lc for term in avoids):
                    continue

                # Gather RAG candidates first (cheap, non-LLM)
                try:
                    rag_hits = search_exercises(query=ex.name, pattern=pattern, top_k=15)
                except Exception:
                    rag_hits = []
                candidates = [str(h.get("name", "")).strip() for h in rag_hits if h.get("name")]
                candidates = [c for c in candidates if c and c.lower() != name_lc]

                # Try LLM-guided best pick
                best_name: Optional[str] = None
                try:
                    pick = return_best_substitution_exercise(
                        Exercise(name=ex.name),
                        pattern=pattern,
                        avoid_terms=sorted(list(avoids)),
                        top_k=15,
                    )
                    if pick is not None and str(pick.name).strip():
                        best_name = str(pick.name).strip()
                except Exception:
                    best_name = None

                if not best_name:
                    # Fall back to first RAG candidate if available
                    best_name = candidates[0] if candidates else None

                suggestions.append(
                    {
                        "day_idx": di,
                        "block_idx": bi,
                        "ex_idx": ei,
                        "original": ex.name,
                        "best": best_name or ex.name,  # conservative default
                        "candidates": candidates,
                        "rationale": (
                            f"Avoid term matched; pattern={pattern or 'n/a'}; LLM {'picked' if best_name else 'not available'}"
                        ),
                    }
                )

    return suggestions
