from app.models.schemas import UserProfile
from app.agents.programmer import generate_plan
from app.agents.verifier import verify_plan
from app.tools.exercise_db import ExerciseDB


def test_verifier_avoidance_respected():
    profile = UserProfile(days_per_week=4, minutes_per_day=60, goal="general strength", avoid_exercises=["squats"], equipment_available=["barbell", "dumbbell", "machine"])
    plan = generate_plan(profile, db=ExerciseDB())
    report = verify_plan(profile, plan)
    assert report["avoidance"]["ok"], f"Found forbidden exercises: {report['avoidance']['violations']}"

