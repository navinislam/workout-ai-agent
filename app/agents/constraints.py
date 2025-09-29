from __future__ import annotations

"""
Constraints/Avoidance Agent (Agents SDK)
----------------------------------------
Expands ambiguous avoid terms using an Agent and a tool that reads
`data/constraints_guidelines.json`. Heuristic mappings have been removed.
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple

from agents import Agent, Runner, RunResult, function_tool


CONSTRAINTS_PATH = Path("data/constraints_guidelines.json")


@function_tool
def lookup_avoid_variants(term: str) -> Dict:
    """Return structured info for an ambiguous term from constraints data.

    Output keys: term_or_constraint, clarify_options, recommended_alternatives.
    Returns empty object if not found.
    """
    try:
        if not CONSTRAINTS_PATH.exists():
            return {}
        data = json.loads(CONSTRAINTS_PATH.read_text(encoding="utf-8"))
        key = term.lower().strip()
        base = key[:-1] if key.endswith("s") else key
        for item in data:
            t = str(item.get("term_or_constraint", "")).lower().strip()
            tb = t[:-1] if t.endswith("s") else t
            if tb == base:
                return item
        return {}
    except Exception:
        return {}


resolver_agent = Agent(
    name="Constraints Resolver",
    instructions=(
        "Given a list of user-provided avoid terms, expand them into specific exercise names to avoid. "
        "Use the tool to get known clarify options. For unknown terms, include the term itself. "
        "Return STRICT JSON with keys: expanded (list[str]), clarifications (object mapping original term -> variants list)."
    ),
    tools=[lookup_avoid_variants],
)


def resolve_avoid_terms(terms: List[str]) -> Tuple[List[str], Dict[str, List[str]]]:
    """Expand ambiguous avoid terms via the Agent + tool."""
    prompt = (
        "Expand these avoid terms.\n" +
        json.dumps({"terms": terms}, ensure_ascii=False)
    )
    result: RunResult = Runner.run_sync(resolver_agent, input=prompt)
    out = result.final_output or "{}"
    try:
        data = json.loads(out)
        expanded = data.get("expanded", [])
        clar = data.get("clarifications", {})
        if not isinstance(expanded, list):
            expanded = []
        if not isinstance(clar, dict):
            clar = {}
        # Deduplicate while preserving order
        seen = set()
        uniq: List[str] = []
        for x in expanded:
            sx = str(x)
            if sx not in seen:
                seen.add(sx)
                uniq.append(sx)
        # Normalize clarification values
        norm_clar: Dict[str, List[str]] = {}
        for k, v in clar.items():
            if isinstance(v, list):
                norm_clar[str(k)] = [str(i) for i in v]
        return uniq, norm_clar
    except Exception:
        return [], {}
