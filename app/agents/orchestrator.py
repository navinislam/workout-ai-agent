from __future__ import annotations

"""
Agents Orchestrator
-------------------
Coordinates the Programmer → Verifier sequence using Agents SDK-based agents.
"""

from typing import Dict, Any, List, Set
import os

from app.models.schemas import UserProfile, WorkoutPlan
from app.agents.programmer import generate_plan, revise_plan
from app.agents.verifier import verify_plan
from app.agents.subber import suggest_substitutions
from app.agents.edit_applier import apply_substitutions, apply_edits, split_edits


def _extract_issue_fingerprint(report: Dict[str, Any]) -> Set[str]:
    """Extract a fingerprint of issues from verification report for convergence tracking."""
    issues: Set[str] = set()

    # Time fit issues
    time_fit = report.get("time_fit", {})
    if not time_fit.get("ok"):
        per_day = time_fit.get("per_day_minutes", [])
        limit = time_fit.get("limit", 60)
        for day_idx, mins in enumerate(per_day):
            if mins > limit * 1.15:
                issues.add(f"time_day_{day_idx}_over")

    # Balance issues
    balance = report.get("balance", {})
    if not balance.get("ok"):
        presence = balance.get("weekly_presence_days", {})
        for pattern, count in presence.items():
            if count < 1:
                issues.add(f"balance_{pattern}_missing")

    # Avoidance violations
    avoidance = report.get("avoidance", {})
    violations = avoidance.get("violations", [])
    for v in violations:
        issues.add(f"avoid_{v[:20]}")  # Truncate for consistency

    # Progression issues
    progression = report.get("progression", {})
    prog_issues = progression.get("issues", [])
    for issue in prog_issues:
        issues.add(f"prog_{issue[:30]}")  # Truncate

    return issues


def _detect_stagnation(issue_history: List[Set[str]], current_issues: Set[str]) -> bool:
    """Detect if same issues persist across iterations."""
    if len(issue_history) < 2:
        return False
    # If current issues are same as last iteration, we're stagnant
    if issue_history and current_issues == issue_history[-1]:
        return True
    return False


def _detect_regression(issue_history: List[Set[str]], current_issues: Set[str]) -> bool:
    """Detect if new issues appeared that weren't in previous iterations."""
    if not issue_history:
        return False
    # If current has more issues than we started with, that's regression
    initial_issues = issue_history[0]
    new_issues = current_issues - initial_issues
    return len(new_issues) > 0


def program_and_verify(profile: UserProfile) -> Dict[str, Any]:
    """Generate a plan and verify it via LLM-first orchestration with iterative refinement.

    Flow:
    1) Programmer generates initial plan
    2) Apply substitutions deterministically
    3) Verify plan (fast + semantic checks)
    4) If issues exist:
       a) Apply mechanical edits deterministically
       b) Extract semantic issues for Programmer
       c) Programmer revises plan semantically
       d) Repeat up to MAX_REVISIONS times with convergence tracking

    Returns:
        Comprehensive response with plan, verification, iteration log
    """
    max_revisions = int(os.getenv("MAX_REVISIONS", "2"))

    print("\n" + "="*70)
    print("🏋️  WORKOUT PLAN ORCHESTRATION STARTED")
    print("="*70)

    # Step 1: Generate initial plan
    print("\n📝 Step 1: Generating initial plan...")
    plan = generate_plan(profile)

    # Step 2: Get and apply substitutions deterministically
    print(f"\n🔄 Step 2: Getting substitution suggestions...")
    sub_suggestions = suggest_substitutions(plan, profile)
    if sub_suggestions:
        print(f"   ✓ Applying {len(sub_suggestions)} substitutions deterministically")
        plan = apply_substitutions(plan, sub_suggestions)
    else:
        print(f"   ✓ No substitutions needed")

    # Step 3: Iterative verification and refinement
    print(f"\n🔍 Step 3: Iterative verification (max {max_revisions} revisions)")
    issue_history: List[Set[str]] = []
    iterations_log: List[Dict[str, Any]] = []
    final_verification: Dict[str, Any] = {}

    for iteration in range(max_revisions + 1):  # +1 to include initial verification
        print(f"\n   🔄 Iteration {iteration}:")
        # Verify plan (semantic_only=True after first iteration to skip fast checks if they passed)
        semantic_only = iteration > 0 and issue_history and len(issue_history[-1]) == 0
        verification = verify_plan(profile, plan, semantic_only=semantic_only)

        # Extract issue fingerprint for convergence tracking
        current_issues = _extract_issue_fingerprint(verification)
        issue_history.append(current_issues)

        # Log iteration
        iterations_log.append({
            "iteration": iteration,
            "ok": verification.get("ok", False),
            "issue_count": len(current_issues),
            "issues": list(current_issues),
        })

        print(f"      {'✅' if verification.get('ok') else '❌'} {len(current_issues)} issues found")

        # Check if we're done
        if verification.get("ok", False):
            print(f"      ✅ Plan verified successfully!")
            final_verification = verification
            break

        # Check for convergence problems
        if iteration > 0:
            if _detect_stagnation(issue_history, current_issues):
                print(f"      ⚠️  Stagnation detected - same issues persist")
                final_verification = verification
                final_verification["stopped_reason"] = "stagnation"
                break
            if _detect_regression(issue_history, current_issues):
                print(f"      ⚠️  Regression detected - new issues appeared")
                final_verification = verification
                final_verification["stopped_reason"] = "regression"
                break

        # If we've hit max iterations, stop
        if iteration >= max_revisions:
            print(f"      🛑 Max iterations reached")
            final_verification = verification
            final_verification["stopped_reason"] = "max_iterations"
            break

        # Apply edits and revise
        suggested_edits = verification.get("suggested_edits", [])
        if suggested_edits:
            mechanical_edits, semantic_edits = split_edits(suggested_edits)

            # Apply mechanical edits deterministically
            if mechanical_edits:
                print(f"      🔧 Applying {len(mechanical_edits)} mechanical edits (deterministic)")
                plan = apply_edits(plan, mechanical_edits)

            # Extract semantic issues for Programmer
            semantic_issues: List[str] = []
            for edit in semantic_edits:
                reason = edit.get("reason", "")
                if reason:
                    semantic_issues.append(reason)

            # Add progression issues as semantic
            progression = verification.get("progression", {})
            prog_issues = progression.get("issues", [])
            semantic_issues.extend(prog_issues)

            # Revise plan if there are semantic issues
            if semantic_issues:
                print(f"      🤖 Revising plan for {len(semantic_issues)} semantic issues")
                plan = revise_plan(plan, profile, semantic_issues)
        else:
            # No edits suggested but not ok - stop to avoid infinite loop
            print(f"      ⚠️  No edits suggested but plan not OK - stopping")
            final_verification = verification
            final_verification["stopped_reason"] = "no_edits_suggested"
            break

    print("\n" + "="*70)
    print(f"✨ ORCHESTRATION COMPLETE")
    print(f"   Total iterations: {len(iterations_log)}")
    print(f"   Final status: {'✅ VERIFIED' if final_verification.get('ok') else '⚠️  ISSUES REMAIN'}")
    if not final_verification.get('ok'):
        stop_reason = final_verification.get('stopped_reason', 'unknown')
        print(f"   Stop reason: {stop_reason}")
    print("="*70 + "\n")

    return {
        "profile": profile.model_dump(),
        "plan": plan.model_dump(),
        "verification": final_verification,
        "substitution_suggestions": sub_suggestions,
        "iterations": len(iterations_log),
        "iterations_log": iterations_log,
        "assumptions": {
            "days": profile.days_per_week,
            "minutes_per_day": profile.minutes_per_day,
            "goal": profile.goal,
        },
    }
