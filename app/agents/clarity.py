from __future__ import annotations

"""
Clarity Agent (Agents SDK)
--------------------------
Parses a freeform user message into a structured profile patch and 1–3
clarifying questions. Uses the OpenAI Agents SDK and a tool to surface
known constraint options from `data/constraints_guidelines.json`.

Heuristic code has been removed.
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple

from agents import Agent, Runner, RunResult, function_tool


CONSTRAINTS_PATH = Path("data/constraints_guidelines.json")


@function_tool
def get_constraint_options(term: str) -> Dict:
    """Lookup known clarify options and recommendations for an ambiguous term.

    Returns an object with keys: term_or_constraint, clarify_options, recommended_alternatives.
    If no match is found, returns an empty object.
    """
    try:
        if not CONSTRAINTS_PATH.exists():
            return {}
        data = json.loads(CONSTRAINTS_PATH.read_text(encoding="utf-8"))
        base = term.lower().strip()
        base = base[:-1] if base.endswith("s") else base
        for item in data:
            t = str(item.get("term_or_constraint", "")).lower().strip()
            tb = t[:-1] if t.endswith("s") else t
            if tb == base:
                return item
        return {}
    except Exception:
        return {}


clarity_agent = Agent(
    name="Clarity Agent",
    instructions=(
        "You parse a user's freeform training request. "
        "Return STRICT JSON with keys: profile_patch (object: may include days_per_week:int, minutes_per_day:int, equipment_available:list[str], goal:str, avoid_exercises:list[str]) "
        "and questions (array of up to 3 concise clarifying questions). "
        "When ambiguous avoid terms are provided (e.g., 'squats'), use the tool to fetch clarify options and propose a targeted question."
    ),
    tools=[get_constraint_options],
)


async def clarify_profile(message: str) -> Tuple[Dict, List[str]]:
    """Run the clarity agent and return (profile_patch, questions)."""
    print(f"🤖 Using LLM for: clarify_profile (parsing user message)")
    result: RunResult = await Runner.run(clarity_agent, input=message)
    out = result.final_output or "{}"
    try:
        data = json.loads(out)
        patch = data.get("profile_patch", {}) if isinstance(data, dict) else {}
        questions = data.get("questions", []) if isinstance(data, dict) else []
        # Normalize types
        if not isinstance(patch, dict):
            patch = {}
        if not isinstance(questions, list):
            questions = []
        return patch, [str(q) for q in questions][:3]
    except Exception:
        return {}, []
