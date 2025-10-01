"""
Fast Deterministic Verification
--------------------------------
Pure Python checks that don't require LLM reasoning.
These run quickly (<1ms) and provide immediate feedback.
"""

from typing import Dict, Any, List, Set
import re

from app.models.schemas import UserProfile, WorkoutPlan
from app.agents.constraints import resolve_avoid_terms


def estimate_exercise_time(sets: int, reps: str, rest_seconds: int | None) -> float:
    """Estimate time in minutes for an exercise.

    Assumptions:
    - Each rep takes ~3 seconds
    - Rest time as specified, default 90 seconds
    """
    rest = rest_seconds or 90

    # Parse reps (can be "8-12", "10", "8-10", etc.)
    reps_lower = reps.lower()
    if "amrap" in reps_lower or "max" in reps_lower:
        avg_reps = 15  # Conservative estimate
    else:
        # Extract numbers
        numbers = re.findall(r'\d+', reps)
        if numbers:
            avg_reps = sum(int(n) for n in numbers) / len(numbers)
        else:
            avg_reps = 10  # Default

    work_time = sets * avg_reps * 3  # seconds
    rest_time = (sets - 1) * rest  # rest between sets
    total_seconds = work_time + rest_time

    return total_seconds / 60  # return minutes


def check_time_fit(profile: UserProfile, plan: WorkoutPlan) -> Dict[str, Any]:
    """Check if plan fits within time constraints."""
    limit = int(profile.minutes_per_day or 60)
    per_day_minutes: List[float] = []

    for day in plan.days:
        day_total = 0.0
        for block in day.blocks:
            for ex in block.exercises:
                day_total += estimate_exercise_time(ex.sets, ex.reps, ex.rest_seconds)
        per_day_minutes.append(day_total)

    ok = all(mins <= limit * 1.15 for mins in per_day_minutes)  # Allow 15% buffer

    return {
        "ok": ok,
        "per_day_minutes": [round(m, 1) for m in per_day_minutes],
        "limit": limit,
    }


def check_balance(profile: UserProfile, plan: WorkoutPlan) -> Dict[str, Any]:
    """Check weekly balance of movement patterns."""
    patterns = {
        "squat_like": {"squat", "lunge", "split squat", "leg press", "step up"},
        "hinge_like": {"deadlift", "rdl", "good morning", "hip thrust", "glute bridge"},
        "push_like": {"press", "push", "dip", "fly"},
        "pull_like": {"pull", "row", "chin", "curl", "raise"},
    }

    weekly_presence_days = {k: 0 for k in patterns}

    for day in plan.days:
        day_patterns: Set[str] = set()
        for block in day.blocks:
            for ex in block.exercises:
                name_lower = ex.name.lower()
                for pattern_name, keywords in patterns.items():
                    if any(kw in name_lower for kw in keywords):
                        day_patterns.add(pattern_name)

        for pattern_name in day_patterns:
            weekly_presence_days[pattern_name] += 1

    # Balance check: each major pattern should appear at least once
    min_presence = 1
    ok = all(count >= min_presence for count in weekly_presence_days.values())

    return {
        "ok": ok,
        "weekly_presence_days": weekly_presence_days,
    }


def check_avoidance(profile: UserProfile, plan: WorkoutPlan) -> Dict[str, Any]:
    """Check if plan avoids forbidden exercises."""
    expanded_avoids, _ = resolve_avoid_terms(profile.avoid_exercises or [])
    violations: List[str] = []

    avoid_terms = {term.lower() for term in expanded_avoids}

    for day in plan.days:
        for block in day.blocks:
            for ex in block.exercises:
                name_lower = ex.name.lower()
                for term in avoid_terms:
                    if term in name_lower:
                        violations.append(f"{ex.name} (contains '{term}')")
                        break

    return {
        "ok": len(violations) == 0,
        "violations": violations,
        "expanded_terms": expanded_avoids,
    }


def fast_verify(profile: UserProfile, plan: WorkoutPlan) -> Dict[str, Any]:
    """Run all fast deterministic checks.

    Returns report with same structure as full verification but without progression check.
    """
    time_fit = check_time_fit(profile, plan)
    balance = check_balance(profile, plan)
    avoidance = check_avoidance(profile, plan)

    ok = time_fit["ok"] and balance["ok"] and avoidance["ok"]

    return {
        "ok": ok,
        "time_fit": time_fit,
        "balance": balance,
        "avoidance": avoidance,
        "fast_check_only": True,
    }


def generate_mechanical_edits_from_fast_check(
    profile: UserProfile, plan: WorkoutPlan, fast_report: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Generate mechanical edits from fast check failures.

    These can be applied deterministically without LLM reasoning.
    """
    edits: List[Dict[str, Any]] = []

    # Time fit violations: reduce sets
    time_fit = fast_report.get("time_fit", {})
    if not time_fit.get("ok"):
        per_day = time_fit.get("per_day_minutes", [])
        limit = time_fit.get("limit", 60)
        for day_idx, minutes in enumerate(per_day):
            if minutes > limit * 1.15:
                # Find exercises with most sets and reduce
                try:
                    day = plan.days[day_idx]
                    for block_idx, block in enumerate(day.blocks):
                        for ex_idx, ex in enumerate(block.exercises):
                            if ex.sets > 3:
                                edits.append({
                                    "type": "tune_sets",
                                    "reason": f"Day {day_idx + 1} exceeds time limit ({minutes:.1f}min > {limit}min)",
                                    "loc": {"day_idx": day_idx, "block_idx": block_idx, "ex_idx": ex_idx},
                                    "payload": {"sets": ex.sets - 1},
                                })
                                break  # One edit per day to avoid over-correction
                except IndexError:
                    pass

    # Avoidance violations: flag for replacement (mechanical but needs exercise search)
    avoidance = fast_report.get("avoidance", {})
    if not avoidance.get("ok"):
        violations = avoidance.get("violations", [])
        for violation_str in violations:
            # Parse violation string (format: "Exercise Name (contains 'term')")
            # This is a placeholder - actual replacement requires substitution logic
            # For now, just flag it
            edits.append({
                "type": "add_note",
                "reason": f"Avoidance violation: {violation_str}",
                "loc": {},
                "payload": {"note": f"⚠️ Review: {violation_str}"},
            })

    return edits