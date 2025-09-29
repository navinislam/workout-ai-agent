from app.models.schemas import UserProfile
from app.agents.programmer import generate_plan
from app.tools.exercise_db import ExerciseDB


def test_avoid_squats_excluded():
    profile = UserProfile(days_per_week=4, minutes_per_day=60, goal="strength - squat focus", avoid_exercises=["squats"], equipment_available=["barbell", "dumbbell", "machine"])
    plan = generate_plan(profile, db=ExerciseDB())
    for day in plan.days:
        for block in day.blocks:
            for ex in block.exercises:
                assert "squat" not in ex.name.lower()

