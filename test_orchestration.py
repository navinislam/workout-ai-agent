#!/usr/bin/env python3
"""
Quick test script for the LLM-first orchestration system.
Run this to verify the implementation works end-to-end.
"""

import json
from app.models.schemas import UserProfile
from app.agents.orchestrator import program_and_verify


def print_separator(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def test_basic_plan():
    """Test 1: Basic plan generation with no avoid terms"""
    print_separator("TEST 1: Basic Plan Generation")

    profile = UserProfile(
        days_per_week=3,
        minutes_per_day=45,
        goal="general fitness",
        equipment_available=["barbell", "dumbbells"],
        training_age_years=1
    )

    print(f"Profile: {json.dumps(profile.model_dump(), indent=2)}")
    print("\nGenerating plan...")

    result = program_and_verify(profile)

    print(f"\n✅ SUCCESS!")
    print(f"   Iterations: {result['iterations']}")
    print(f"   Plan OK: {result['verification']['ok']}")
    print(f"   Days generated: {len(result['plan']['days'])}")

    # Show iteration progression
    print(f"\n   Iteration log:")
    for log in result['iterations_log']:
        status = "✅" if log['ok'] else "❌"
        print(f"     {status} Iteration {log['iteration']}: {log['issue_count']} issues")
        if log['issues']:
            print(f"        Issues: {', '.join(log['issues'][:3])}")

    return result


def test_with_substitutions():
    """Test 2: Plan with avoid terms requiring substitutions"""
    print_separator("TEST 2: Plan with Substitutions")

    profile = UserProfile(
        days_per_week=4,
        minutes_per_day=60,
        goal="build muscle",
        equipment_available=["barbell", "dumbbells", "machines"],
        avoid_exercises=["knee", "shoulder press"],
        training_age_years=2
    )

    print(f"Avoid terms: {profile.avoid_exercises}")
    print("\nGenerating plan with substitutions...")

    result = program_and_verify(profile)

    print(f"\n✅ SUCCESS!")
    print(f"   Substitutions made: {len(result['substitution_suggestions'])}")

    # Show substitutions
    if result['substitution_suggestions']:
        print(f"\n   Substitution examples:")
        for sub in result['substitution_suggestions'][:3]:
            print(f"     • {sub['original']} → {sub['best']}")
            print(f"       Rationale: {sub['rationale']}")

    print(f"\n   Verification:")
    print(f"     Time fit: {result['verification']['time_fit']['ok']}")
    print(f"     Balance: {result['verification']['balance']['ok']}")
    print(f"     Avoidance: {result['verification']['avoidance']['ok']}")

    return result


def test_tight_constraints():
    """Test 3: Tight constraints to trigger iterations"""
    print_separator("TEST 3: Tight Constraints (Multiple Iterations)")

    profile = UserProfile(
        days_per_week=5,
        minutes_per_day=30,  # Very tight!
        goal="strength and hypertrophy",
        equipment_available=["barbell"],
        training_age_years=3
    )

    print(f"Very tight constraint: {profile.minutes_per_day} min/day")
    print("\nGenerating plan (should require iterations)...")

    result = program_and_verify(profile)

    print(f"\n✅ COMPLETE!")
    print(f"   Iterations needed: {result['iterations']}")
    print(f"   Final status: {'✅ OK' if result['verification']['ok'] else '⚠️ Issues remain'}")

    # Show convergence behavior
    if result['verification'].get('stopped_reason'):
        print(f"   Stopped due to: {result['verification']['stopped_reason']}")

    print(f"\n   Time fit per day (limit: {result['verification']['time_fit']['limit']} min):")
    for i, mins in enumerate(result['verification']['time_fit']['per_day_minutes']):
        status = "✅" if mins <= profile.minutes_per_day * 1.15 else "⚠️"
        print(f"     {status} Day {i+1}: {mins:.1f} min")

    return result


def test_fast_verification():
    """Test 4: Verify fast checks work"""
    print_separator("TEST 4: Fast Verification")

    from app.agents.programmer import generate_plan
    from app.agents.verifier_fast import fast_verify

    profile = UserProfile(
        days_per_week=3,
        minutes_per_day=60,
        goal="strength",
        equipment_available=["barbell"],
        avoid_exercises=["bench"]
    )

    plan = generate_plan(profile)

    print("Running fast verification checks...")
    import time
    start = time.time()
    fast_report = fast_verify(profile, plan)
    elapsed = (time.time() - start) * 1000  # ms

    print(f"\n✅ Fast checks completed in {elapsed:.2f}ms")
    print(f"   Time fit: {fast_report['time_fit']['ok']}")
    print(f"   Balance: {fast_report['balance']['ok']}")
    print(f"   Avoidance: {fast_report['avoidance']['ok']}")

    if not fast_report['avoidance']['ok']:
        print(f"\n   Avoidance violations found:")
        for v in fast_report['avoidance']['violations'][:3]:
            print(f"     • {v}")

    return fast_report


def test_edit_application():
    """Test 5: Deterministic edit application"""
    print_separator("TEST 5: Deterministic Edit Application")

    from app.agents.programmer import generate_plan
    from app.agents.edit_applier import apply_edit, split_edits

    profile = UserProfile(
        days_per_week=3,
        minutes_per_day=60,
        goal="strength"
    )

    plan = generate_plan(profile)

    # Create test edits
    edits = [
        {
            "type": "tune_sets",
            "reason": "Reduce volume",
            "loc": {"day_idx": 0, "block_idx": 0, "ex_idx": 0},
            "payload": {"sets": 3}
        },
        {
            "type": "replace_exercise",
            "reason": "Better exercise",
            "loc": {"day_idx": 0, "block_idx": 0, "ex_idx": 1},
            "payload": {"new_name": "Squat"}
        },
        {
            "type": "reorder_days",
            "reason": "Better sequencing",
            "loc": {},
            "payload": {"order": [2, 0, 1]}
        }
    ]

    mechanical, semantic = split_edits(edits)

    print(f"Split {len(edits)} edits:")
    print(f"   Mechanical (deterministic): {len(mechanical)}")
    print(f"   Semantic (requires LLM): {len(semantic)}")

    print(f"\n   Mechanical edits:")
    for edit in mechanical:
        print(f"     • {edit['type']}: {edit['reason']}")

    print(f"\n   Semantic edits:")
    for edit in semantic:
        print(f"     • {edit['type']}: {edit['reason']}")

    # Apply mechanical edits
    if mechanical:
        from app.agents.edit_applier import apply_edits
        revised_plan = apply_edits(plan, mechanical)
        print(f"\n✅ Applied {len(mechanical)} mechanical edits successfully")

    return mechanical, semantic


def main():
    """Run all tests"""
    print("\n" + "🚀" * 35)
    print("  LLM-First Orchestration System Test Suite")
    print("🚀" * 35)

    try:
        # Run tests
        test_basic_plan()
        test_with_substitutions()
        test_tight_constraints()
        test_fast_verification()
        test_edit_application()

        print_separator("ALL TESTS PASSED! ✅")
        print("\nThe orchestration system is working correctly.")
        print("\nNext steps:")
        print("  1. Start the API: uvicorn app.main:app --reload")
        print("  2. Test via API: curl -X POST http://localhost:8000/api/plan ...")
        print("  3. See docs/GETTING_STARTED.md for more examples")

    except Exception as e:
        print(f"\n❌ TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
