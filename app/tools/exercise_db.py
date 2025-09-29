from __future__ import annotations

import json
import os
from typing import List, Dict, Any, Iterable

from app.models.schemas import Exercise


def _normalize(s: str) -> str:
    return s.lower().replace("_", " ")


class ExerciseDB:
    def __init__(self, path: str = "exercises/exercises.json") -> None:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Could not find exercises dataset at {path}")
        with open(path, "r") as f:
            raw = json.load(f)
        self.exercises: List[Exercise] = [Exercise(**e) for e in raw]

    def search_by_keywords(self, keywords: Iterable[str]) -> List[Exercise]:
        keys = [_normalize(k) for k in keywords]
        out: List[Exercise] = []
        for ex in self.exercises:
            text = _normalize(ex.name)
            if any(k in text for k in keys):
                out.append(ex)
        return out

    def filter(
        self,
        *,
        include_keywords: Iterable[str] | None = None,
        exclude_keywords: Iterable[str] | None = None,
        primary_muscles: Iterable[str] | None = None,
        equipment_any_of: Iterable[str] | None = None,
        category_any_of: Iterable[str] | None = None,
    ) -> List[Exercise]:
        def ok(ex: Exercise) -> bool:
            if include_keywords:
                if not any(_normalize(k) in _normalize(ex.name) for k in include_keywords):
                    return False
            if exclude_keywords:
                if any(_normalize(k) in _normalize(ex.name) for k in exclude_keywords):
                    return False
            if primary_muscles:
                if not any(m.lower() in [pm.lower() for pm in ex.primaryMuscles] for m in primary_muscles):
                    return False
            if equipment_any_of:
                if ex.equipment is None:
                    return False
                if not any(eq.lower() in ex.equipment.lower() for eq in equipment_any_of):
                    return False
            if category_any_of:
                if ex.category is None:
                    return False
                if not any(cat.lower() == ex.category.lower() for cat in category_any_of):
                    return False
            return True

        return [ex for ex in self.exercises if ok(ex)]

    def best_candidate(
        self,
        *,
        include_keywords: Iterable[str] | None = None,
        exclude_keywords: Iterable[str] | None = None,
        primary_muscles: Iterable[str] | None = None,
        equipment_preference: Iterable[str] | None = None,
    ) -> Exercise | None:
        cands = self.filter(
            include_keywords=include_keywords,
            exclude_keywords=exclude_keywords,
            primary_muscles=primary_muscles,
        )
        if not cands:
            return None
        if not equipment_preference:
            return cands[0]
        pref = [e.lower() for e in equipment_preference]
        # Simple heuristic: prefer first matching preferred equipment
        for p in pref:
            for ex in cands:
                if ex.equipment and p in ex.equipment.lower():
                    return ex
        return cands[0]

