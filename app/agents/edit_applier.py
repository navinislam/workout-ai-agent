"""
Deterministic Edit Applier
---------------------------
Pure Python implementation for applying mechanical edits to WorkoutPlan.
Handles deterministic transformations without LLM involvement.
"""

from typing import Dict, Any, List
from copy import deepcopy

from app.models.schemas import WorkoutPlan, WorkoutDay, WorkoutBlock, WorkoutExercise


def apply_edit(plan: WorkoutPlan, edit: Dict[str, Any]) -> WorkoutPlan:
    """Apply a single edit to a plan deterministically.

    Supported edit types:
    - replace_exercise: Replace exercise name at location
    - tune_sets: Change sets count at location
    - tune_reps: Change reps string at location
    - add_rest: Set rest_seconds at location
    - remove_exercise: Remove exercise at location
    - add_exercise: Add exercise to block at location
    - add_note: Add note to plan metadata or day

    Returns a new WorkoutPlan with the edit applied.
    Raises ValueError if edit is invalid or location doesn't exist.
    """
    new_plan = deepcopy(plan)
    edit_type = edit.get("type")
    loc = edit.get("loc", {})
    payload = edit.get("payload", {})

    if edit_type == "replace_exercise":
        day_idx = loc.get("day_idx")
        block_idx = loc.get("block_idx")
        ex_idx = loc.get("ex_idx")
        new_name = payload.get("new_name")

        if day_idx is None or block_idx is None or ex_idx is None or not new_name:
            raise ValueError(f"Invalid replace_exercise edit: {edit}")

        try:
            new_plan.days[day_idx].blocks[block_idx].exercises[ex_idx].name = new_name
        except IndexError:
            raise ValueError(f"Location out of bounds: {loc}")

    elif edit_type == "tune_sets":
        day_idx = loc.get("day_idx")
        block_idx = loc.get("block_idx")
        ex_idx = loc.get("ex_idx")
        sets = payload.get("sets")

        if day_idx is None or block_idx is None or ex_idx is None or sets is None:
            raise ValueError(f"Invalid tune_sets edit: {edit}")

        try:
            new_plan.days[day_idx].blocks[block_idx].exercises[ex_idx].sets = int(sets)
        except (IndexError, ValueError):
            raise ValueError(f"Invalid tune_sets edit: {edit}")

    elif edit_type == "tune_reps":
        day_idx = loc.get("day_idx")
        block_idx = loc.get("block_idx")
        ex_idx = loc.get("ex_idx")
        reps = payload.get("reps")

        if day_idx is None or block_idx is None or ex_idx is None or not reps:
            raise ValueError(f"Invalid tune_reps edit: {edit}")

        try:
            new_plan.days[day_idx].blocks[block_idx].exercises[ex_idx].reps = str(reps)
        except IndexError:
            raise ValueError(f"Location out of bounds: {loc}")

    elif edit_type == "add_rest":
        day_idx = loc.get("day_idx")
        block_idx = loc.get("block_idx")
        ex_idx = loc.get("ex_idx")
        rest_seconds = payload.get("rest_seconds")

        if day_idx is None or block_idx is None or ex_idx is None or rest_seconds is None:
            raise ValueError(f"Invalid add_rest edit: {edit}")

        try:
            new_plan.days[day_idx].blocks[block_idx].exercises[ex_idx].rest_seconds = int(rest_seconds)
        except (IndexError, ValueError):
            raise ValueError(f"Invalid add_rest edit: {edit}")

    elif edit_type == "remove_exercise":
        day_idx = loc.get("day_idx")
        block_idx = loc.get("block_idx")
        ex_idx = loc.get("ex_idx")

        if day_idx is None or block_idx is None or ex_idx is None:
            raise ValueError(f"Invalid remove_exercise edit: {edit}")

        try:
            del new_plan.days[day_idx].blocks[block_idx].exercises[ex_idx]
        except IndexError:
            raise ValueError(f"Location out of bounds: {loc}")

    elif edit_type == "add_exercise":
        day_idx = loc.get("day_idx")
        block_idx = loc.get("block_idx")
        ex_data = payload.get("exercise")

        if day_idx is None or block_idx is None or not ex_data:
            raise ValueError(f"Invalid add_exercise edit: {edit}")

        try:
            new_ex = WorkoutExercise(
                name=ex_data.get("name", "Exercise"),
                sets=ex_data.get("sets", 3),
                reps=ex_data.get("reps", "8-12"),
                intensity=ex_data.get("intensity"),
                rest_seconds=ex_data.get("rest_seconds"),
                notes=ex_data.get("notes"),
            )
            new_plan.days[day_idx].blocks[block_idx].exercises.append(new_ex)
        except IndexError:
            raise ValueError(f"Location out of bounds: {loc}")

    elif edit_type == "add_note":
        note = payload.get("note", "")
        if not note:
            raise ValueError(f"Invalid add_note edit: {edit}")

        day_idx = loc.get("day_idx")
        if day_idx is not None:
            # Add note to specific day
            try:
                if not new_plan.days[day_idx].focus:
                    new_plan.days[day_idx].focus = note
                else:
                    new_plan.days[day_idx].focus += f" | {note}"
            except IndexError:
                raise ValueError(f"Location out of bounds: {loc}")
        else:
            # Add note to plan metadata
            if "notes" in new_plan.metadata:
                new_plan.metadata["notes"] += f" | {note}"
            else:
                new_plan.metadata["notes"] = note

    else:
        raise ValueError(f"Unsupported edit type: {edit_type}")

    return new_plan


def apply_edits(plan: WorkoutPlan, edits: List[Dict[str, Any]]) -> WorkoutPlan:
    """Apply multiple edits sequentially to a plan.

    Returns a new WorkoutPlan with all edits applied.
    If any edit fails, returns the plan up to that point with error info in metadata.
    """
    current_plan = plan
    applied_count = 0

    for i, edit in enumerate(edits):
        try:
            current_plan = apply_edit(current_plan, edit)
            applied_count += 1
        except Exception as e:
            # Store error in metadata and stop processing
            current_plan.metadata["edit_error"] = f"Failed at edit {i}: {str(e)}"
            current_plan.metadata["edits_applied"] = applied_count
            break

    return current_plan


def apply_substitutions(plan: WorkoutPlan, substitutions: List[Dict[str, Any]]) -> WorkoutPlan:
    """Apply substitution suggestions deterministically.

    Each substitution has: day_idx, block_idx, ex_idx, original, best, candidates, rationale
    """
    new_plan = deepcopy(plan)

    for sub in substitutions:
        day_idx = sub.get("day_idx")
        block_idx = sub.get("block_idx")
        ex_idx = sub.get("ex_idx")
        best = sub.get("best")

        if day_idx is None or block_idx is None or ex_idx is None or not best:
            continue

        try:
            new_plan.days[day_idx].blocks[block_idx].exercises[ex_idx].name = best
        except IndexError:
            continue

    return new_plan


def is_mechanical_edit(edit: Dict[str, Any]) -> bool:
    """Determine if an edit can be applied deterministically.

    Mechanical edits: replace_exercise, tune_sets, tune_reps, add_rest, remove_exercise, add_exercise
    Semantic edits: reorder_days (requires reasoning about training logic)
    """
    mechanical_types = {
        "replace_exercise",
        "tune_sets",
        "tune_reps",
        "add_rest",
        "remove_exercise",
        "add_exercise",
        "add_note",
    }
    return edit.get("type") in mechanical_types


def split_edits(edits: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Split edits into mechanical (can apply directly) and semantic (need LLM)."""
    mechanical = []
    semantic = []

    for edit in edits:
        if is_mechanical_edit(edit):
            mechanical.append(edit)
        else:
            semantic.append(edit)

    return mechanical, semantic