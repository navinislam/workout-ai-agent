from __future__ import annotations

import os

from pymilvus import Collection, FieldSchema, DataType, CollectionSchema
from pymilvus.orm import utility

from app.rag import connect_milvus, embed_texts

"""
Templates RAG Utilities (Starter Wiring)
----------------------------------------
Purpose: allow the Programmer to select a best-matching SBS template and
transform it into a WorkoutPlan.

This starter wiring uses filesystem-backed JSONs in `sbs/` and provides
extension points to add embeddings/Milvus later.

Functions to implement (suggested):
- search_templates(query: str, *, days: int | None, equipment: list[str] | None, top_k: int) -> list[dict]
- get_template(path: str) -> dict
- map_sbs_to_workout_plan(template_json: dict, profile: UserProfile) -> WorkoutPlan

Current implementation provides minimal scanning/filtering so the pipeline
stays functional; replace the internals with your own logic.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.models.schemas import UserProfile, WorkoutPlan, WorkoutDay, WorkoutBlock, WorkoutExercise


SBS_DIR = Path("sbs")
WORKOUT_COLLECTION= 'templates'
WORKOUT_DIM = int(os.getenv("RAG_EMBED_DIM", "1536"))  # text-embedding-3-small

@dataclass
class TemplateHit:
    path: str
    title: str
    days_per_week: Optional[int]
    equipment_required: str | None
    score: float


def ensure_workout_collection() -> Collection:
    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="name", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=4096),
        FieldSchema(name="days", dtype=DataType.INT8),
        FieldSchema(name="equipment", dtype=DataType.VARCHAR, max_length=512),
        FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=512),
        FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=WORKOUT_DIM),
    ]
    schema = CollectionSchema(fields, description="Workout templates for RAG")
    if utility.has_collection(WORKOUT_COLLECTION):
        col = Collection(WORKOUT_COLLECTION)
    else:
        col = Collection(WORKOUT_COLLECTION, schema)
    try:
        col.create_index(
            field_name="vector",
            index_params={
                "index_type": "IVF_FLAT",
                "metric_type": "COSINE",
                "params": {"nlist": 1024},
            },
        )
    except Exception:
        pass
    # Sanity check vector dim
    try:
        vec_field = next((f for f in col.schema.fields if f.name == "vector"), None)
        vec_dim = None
        if vec_field is not None:
            vec_dim = getattr(vec_field, "params", {}).get("dim") if hasattr(vec_field, "params") else None
            if vec_dim is None:
                vec_dim = getattr(vec_field, "dim", None)
        if vec_dim is not None and int(vec_dim) != int(WORKOUT_DIM):
            raise ValueError(
                f"Milvus collection '{WORKOUT_COLLECTION}' vector dim {vec_dim} != RAG_EMBED_DIM {WORKOUT_DIM}."
            )
    except Exception:
        pass
    col.load()
    return col

def _workout_text(tpl: Dict[str, Any]) -> str:
    """Build a semantic text blob for a workout template JSON."""
    parts: List[str] = []
    parts.append(str(tpl.get("title", "")))
    summ = tpl.get("summary") or {}
    if summ:
        for k in ["main_goal", "workout_type", "training_level", "program_duration", "days_per_week", "time_per_workout", "equipment_required"]:
            v = summ.get(k)
            if v:
                parts.append(f"{k.replace('_',' ').title()}: {v}")
    desc = tpl.get("description")
    if desc:
        parts.append(str(desc))
    sched = tpl.get("workout_schedule") or {}
    if isinstance(sched, dict):
        day_lines: List[str] = []
        for day_name, info in sched.items():
            mg = (info or {}).get("muscle_groups")
            exs = ", ".join(str(e.get("name")) for e in (info or {}).get("exercises", []) if e.get("name"))
            line = f"{day_name}: {mg or ''} | {exs}".strip()
            if line:
                day_lines.append(line)
        if day_lines:
            parts.append("Schedule: " + " | ".join(day_lines))
    return "\n".join([p for p in parts if p])


def ingest_workouts(dir_path: str = "sbs") -> int:
    """Ingest SBS workout templates into Milvus `workouts` collection.

    - Builds a semantic text per template for retrieval.
    - Stores fields: name (title), text (blob), days (int8), source (url or filename), vector.
    - Returns number of inserted templates.
    """
    connect_milvus()
    col = ensure_workout_collection()

    # Gather records
    recs: List[Dict[str, Any]] = []
    for entry in os.scandir(dir_path):
        if not entry.is_file() or not entry.name.endswith(".json"):
            continue
        try:
            data = json.loads(Path(entry.path).read_text(encoding="utf-8"))
        except Exception:
            continue
        title = str(data.get("title") or Path(entry.path).stem)
        summary = data.get("summary") or {}
        days_val = summary.get("days_per_week")
        try:
            days = int(str(days_val)) if days_val is not None else 0
        except Exception:
            days = 0
        equipment_req = str(summary.get("equipment_required") or "").lower()
        src = entry.name
        text = _workout_text(data)
        recs.append({"name": title, "text": text, "days": days, "equipment": equipment_req, "source": src})

    if not recs:
        return 0

    # Embed
    vectors = embed_texts([r["text"] for r in recs])

    # Prepare column-wise data following schema order excluding auto-id
    data_cols: List[List[Any]] = []
    fields = {f.name: f for f in col.schema.fields}
    ordered = ["name", "text", "days", "equipment", "source", "vector"]
    for fname in ordered:
        if fname not in fields:
            continue
        if fname == "vector":
            data_cols.append(vectors)
        else:
            data_cols.append([r[fname] for r in recs])

    col.insert(data_cols)
    col.flush()
    return len(recs)







def _coerce_int(val: Any) -> Optional[int]:
    try:
        if val is None:
            return None
        return int(str(val).strip())
    except Exception:
        return None


def search_templates(
    query: str,
    *,
    days: int | None = None,
    equipment: str,
    top_k: int = 5,
) -> List[TemplateHit]:
    """Semantic search over ingested templates in Milvus.

    Returns TemplateHit entries; if the `source` of a hit is a local filename
    under `sbs/`, the `path` is populated accordingly; otherwise left as the
    `source` string for the caller to handle.
    """
    connect_milvus()
    col = Collection(WORKOUT_COLLECTION)
    col.load()
    q_vec = embed_texts([query])[0]

    out_fields = ["name", "text", "days", "equipment", "source"]
    raw_limit = max(top_k * 10, 20)  # pull more to rerank
    expr = None
    if isinstance(days, int):
        expr = f"days >= {days - 1} and days <= {days + 1}"
    res = col.search(
        data=[q_vec],
        anns_field="vector",
        param={"metric_type": "COSINE", "params": {"nprobe": 16}},
        limit=raw_limit,
        output_fields=out_fields,
        expr=expr,
    )

    hits: List[TemplateHit] = []
    for hit in res[0]:
        name = hit.entity.get("name")
        days_val = hit.entity.get("days")
        equip_val = hit.entity.get("equipment") or ""
        source = hit.entity.get("source") or ""
        # Resolve to local path if possible
        local_path = str(SBS_DIR / source) if source and (SBS_DIR / source).is_file() else source
        hits.append(
            TemplateHit(
                path=local_path,
                title=name,
                days_per_week=int(days_val) if days_val is not None else None,
                equipment_required=str(equip_val).lower() or None,
                score=float(hit.distance),
            )
        )
    # Optional client-side equipment filtering
    if equipment:
        equip_list = equipment.split(',')
        want = {e.strip().lower() for e in equip_list}
        def parse_eq(s: str | None) -> set[str]:
            if not s:
                return set()
            parts = [p.strip().lower() for p in s.split(",") if p.strip()]
            # normalize plurals
            norm = set()
            for p in parts:
                norm.add(p)
                if p.endswith("s"):
                    norm.add(p[:-1])
                else:
                    norm.add(p + "s")
            return norm
        filtered: List[TemplateHit] = []
        for h in hits:
            have = parse_eq(h.equipment_required)
            if not have:
                filtered.append(h)
                continue
            # Keep if user's equipment covers at least one listed requirement
            if want & have:
                filtered.append(h)
        return filtered

    # Sort by closeness to requested days (smaller gap first), then by Milvus score
    def day_gap(h: TemplateHit) -> int:
        if days is None or h.days_per_week is None:
            return 0 if days is None else 10**6
        try:
            return abs(int(h.days_per_week) - int(days))
        except Exception:
            return 10**6

    hits.sort(key=lambda h: (day_gap(h), h.score))
    return hits[:top_k]


def get_template(path: str) -> Dict[str, Any]:
    """Load a template JSON from `sbs/` by path."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(path)
    return json.loads(p.read_text(encoding="utf-8"))


def _parse_rest_seconds(additional_info: Dict[str, Any] | None) -> int:
    text = "" if not additional_info else str(additional_info.get("rest_periods") or "")
    t = text.lower()
    if not t:
        return 90
    import re
    nums = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", t)]
    if not nums:
        return 90
    if "minute" in t:
        return int((sum(nums) / len(nums)) * 60)
    return int(sum(nums) / len(nums))


def map_sbs_to_workout_plan(template_json: Dict[str, Any], profile: UserProfile) -> WorkoutPlan:
    """Transform an SBS template JSON into a WorkoutPlan.

    Rules:
    - Skip rest days; include only days with exercises.
    - One block per day named "Workout"; focus comes from `muscle_groups`.
    - Coerce sets to int; keep reps string; apply default rest from additional info.
    - Fit count to `profile.days_per_week` by trimming or cycling.
    """
    schedule = template_json.get("workout_schedule") or {}
    addl = template_json.get("additional_info") or {}
    rest_default = _parse_rest_seconds(addl)

    training_days: List[WorkoutDay] = []
    for name, info in schedule.items():
        if not isinstance(info, dict):
            continue
        mg = info.get("muscle_groups")
        if isinstance(mg, str) and "rest" in mg.lower():
            continue
        exercises = info.get("exercises") or []
        if not exercises:
            continue
        exs: List[WorkoutExercise] = []
        for ex in exercises:
            try:
                sets_raw = ex.get("sets")
                sets = int(str(sets_raw).split("-")[0]) if sets_raw is not None else 3
            except Exception:
                sets = 3
            reps = str(ex.get("reps", "8-12"))
            exs.append(WorkoutExercise(name=str(ex.get("name", "Exercise")), sets=sets, reps=reps, rest_seconds=rest_default))
        if not exs:
            continue
        training_days.append(WorkoutDay(name=str(name), focus=str(mg) if mg else None, blocks=[WorkoutBlock(name="Workout", exercises=exs)]))

    desired = max(1, int(profile.days_per_week or 4))
    out_days: List[WorkoutDay] = []
    if not training_days:
        out_days = []
    elif len(training_days) >= desired:
        out_days = training_days[:desired]
    else:
        idx = 0
        while len(out_days) < desired:
            src = training_days[idx % len(training_days)]
            suffix = 1 + len(out_days) // len(training_days)
            name = src.name if suffix == 1 else f"{src.name} ({suffix})"
            # Deep copy blocks
            new_blocks: List[WorkoutBlock] = []
            for b in src.blocks:
                new_blocks.append(WorkoutBlock(name=b.name, exercises=[WorkoutExercise(**e.model_dump()) for e in b.exercises]))
            out_days.append(WorkoutDay(name=name, focus=src.focus, blocks=new_blocks))
            idx += 1

    metadata = {
        "notes": f"Derived from template: {template_json.get('title', 'SBS Template')}",
        "source_url": template_json.get("url"),
        "template_days": len(training_days),
        "from_sbs": True,
    }
    return WorkoutPlan(days=out_days, metadata=metadata)
