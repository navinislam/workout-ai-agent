import json
import re
from pathlib import Path


DATA_PATH = Path("exercises/exercises.json")


def contains_any(text: str, keywords):
    t = text.lower()
    for k in keywords:
        # Use word boundaries to avoid accidental substring matches (e.g., 'run' in 'crunch').
        pattern = r"\b" + re.escape(k) + r"\b"
        if re.search(pattern, t):
            return True
    return False


def infer_from_name(name: str):
    n = name.lower()

    # Keyword sets
    rotation_kw = [
        "twist",
        "rotation",
        "rotational",
        "woodchop",
        "wood chop",
        "russian",
        "windmill",
        "around the world",
        "landmine twist",
        "oblique",
        "torso",
        "chop",
    ]
    gait_kw = [
        "walk",
        "jog",
        "run",
        "sprint",
        "carry",
        "farmer",
        "yoke",
        "drag",
        "prowler",
        "march",
        "skip",
        "shuffle",
        "stair",
        "treadmill",
        "hill",
        "ruck",
    ]
    lunge_kw = [
        "lunge",
        "split squat",
        "bulgarian",
        "step-up",
        "step up",
        "pistol",
        "reverse lunge",
        "walking lunge",
        "stride jump",
        "single-leg squat",
        "single leg squat",
        "stepback",
    ]
    squat_kw = [
        "squat",
        "leg press",
        "hack squat",
        "box squat",
        "front squat",
        "back squat",
        "overhead squat",
        "goblet",
    ]
    hinge_kw = [
        "deadlift",
        "romanian",
        "rdl",
        "good morning",
        "hip thrust",
        "thrust",
        "kettlebell swing",
        "swing",
        "clean",
        "snatch",
        "hyperextension",
        "back extension",
        "glute ham",
        "pull-through",
        "pull through",
        "stiff-leg",
        "stiff leg",
        "good-morning",
        "hinge",
        "rollout",
    ]
    pull_kw = [
        "row",
        "pull-up",
        "pull up",
        "pulldown",
        "pull-down",
        "chin-up",
        "chin up",
        "curl",
        "face pull",
        "reverse fly",
        "rear delt",
        "shrug",
        "upright row",
        "high pull",
        "yates",
        "pullover",
    ]
    push_kw = [
        "press",
        "push-up",
        "push up",
        "push",
        "bench",
        "dip",
        "flye",
        "fly",
        "extension",
        "raise",
        "jerk",
        "chest pass",
    ]

    # Precedence: Rotation > Gait > Lunge > Squat > Hinge > Pull > Push
    if contains_any(n, rotation_kw):
        return "Rotation"
    if contains_any(n, gait_kw):
        return "Gait"
    if contains_any(n, lunge_kw):
        return "Lunge"
    # Ensure 'split squat' doesn't get re-mapped to Squat after Lunge check
    if contains_any(n, squat_kw) and "split squat" not in n:
        return "Squat"
    if contains_any(n, hinge_kw):
        return "Hinge"
    if contains_any(n, pull_kw):
        return "Pull"
    if contains_any(n, push_kw):
        return "Push"
    return None


def infer_from_muscles(primary, secondary):
    prim = set((primary or []))
    sec = set((secondary or []))
    muscles = {m.lower() for m in (prim | sec)}

    lower_pull = {"hamstrings", "glutes", "lower back", "erector spinae"}
    lower_push = {"quadriceps", "quads"}
    upper_push = {"chest", "pectorals", "shoulders", "deltoids", "triceps"}
    upper_pull = {"lats", "latissimus dorsi", "middle back", "upper back", "biceps", "forearms", "traps", "trapezius", "rhomboids"}
    core_rot = {"obliques"}
    calves = {"calves", "gastrocnemius", "soleus"}
    adductors = {"adductors", "gluteus medius", "gluteus minimus"}

    if muscles & core_rot:
        return "Rotation"
    if (muscles & lower_pull) and not (muscles & lower_push):
        return "Hinge"
    if (muscles & lower_push):
        return "Squat"
    if muscles & upper_pull:
        return "Pull"
    if muscles & upper_push:
        return "Push"
    if muscles & adductors:
        return "Lunge"
    # Map isolated calf emphasis to gait
    if (muscles & calves) and not (muscles & (lower_pull | lower_push | upper_pull | upper_push | core_rot | adductors)):
        return "Gait"
    return None


def infer_pattern(ex):
    # Try name keywords first
    name = ex.get("name", "")
    pat = infer_from_name(name)
    if pat:
        return pat

    # Try from muscles
    pat = infer_from_muscles(ex.get("primaryMuscles"), ex.get("secondaryMuscles"))
    if pat:
        return pat

    # Fallbacks by category
    cat = (ex.get("category") or "").lower()
    if cat in {"cardio", "plyometrics"}:
        return "Gait"
    if cat in {"powerlifting", "strongman", "olympic weightlifting"}:
        # Power movements typically hinge dominant
        return "Hinge"
    if cat in {"stretching"}:
        # Generic fallback for stretches
        return "Hinge"

    # Last resort
    return "Push"


def main():
    data = json.loads(DATA_PATH.read_text())
    changed = 0
    for ex in data:
        pattern = infer_pattern(ex)
        ex["movementPattern"] = pattern
        changed += 1

    DATA_PATH.write_text(json.dumps(data, indent=2) + "\n")
    print(f"Updated movementPattern for {changed} exercises.")


if __name__ == "__main__":
    main()
