from __future__ import annotations

import os
import json
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection, utility

from app.rag.embed import embed_texts


EX_COLLECTION = os.getenv("RAG_EXERCISE_COLLECTION", "exercises")
EX_DIM = int(os.getenv("RAG_EMBED_DIM", "1536"))  # text-embedding-3-small


def connect_milvus() -> None:
    load_dotenv()
    uri = os.getenv("MILVUS_URI")
    token = os.getenv("MILVUS_TOKEN")
    db = os.getenv("MILVUS_DB_NAME")
    if uri:
        kwargs = {"alias": "default", "uri": uri}
        if token:
            kwargs["token"] = token
        if db:
            kwargs["db_name"] = db
        connections.connect(**kwargs)
    else:
        host = os.getenv("MILVUS_HOST", "localhost")
        port = os.getenv("MILVUS_PORT", "19530")
        kwargs = {"alias": "default", "host": host, "port": port}
        if db:
            kwargs["db_name"] = db
        connections.connect(**kwargs)


def ensure_exercise_collection() -> Collection:
    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="name", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=4096),
        FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=512),
        # CamelCase for compatibility with existing collections
        FieldSchema(name="movementPattern", dtype=DataType.VARCHAR, max_length=512),
        FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=EX_DIM),
    ]
    schema = CollectionSchema(fields, description="Exercise cards for RAG")
    if utility.has_collection(EX_COLLECTION):
        col = Collection(EX_COLLECTION)
    else:
        col = Collection(EX_COLLECTION, schema)
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
        if vec_dim is not None and int(vec_dim) != int(EX_DIM):
            raise ValueError(
                f"Milvus collection '{EX_COLLECTION}' vector dim {vec_dim} != RAG_EMBED_DIM {EX_DIM}."
            )
    except Exception:
        pass
    col.load()
    return col


def classify_pattern(row: Dict[str, Any]) -> str:
    name = (row.get("name") or "").lower()
    pms = [m.lower() for m in (row.get("primaryMuscles") or [])]

    def has(keys: List[str]) -> bool:
        return any(k in name for k in keys)

    if has(["squat", "lunge", "step-up", "leg press", "split squat", "box squat", "hack squat"]):
        return "squat"
    if has(["deadlift", "romanian", "rdl", "good morning", "hip thrust", "back extension", "good-morning"]):
        return "hinge"
    if has(["press", "push-up", "dip", "overhead press", "bench"]):
        return "push"
    if has(["row", "pull-up", "pulldown", "chin-up"]):
        return "pull"
    if has(["carry", "farmer", "suitcase", "yoke"]):
        return "carry"
    if has(["plank", "crunch", "sit-up", "rollout", "rotation", "anti-rotation", "pallof", "side plank"]):
        return "core"
    if "quadriceps" in pms:
        return "squat"
    if any(m in pms for m in ["hamstrings", "glutes", "erector spinae"]):
        return "hinge"
    if any(m in pms for m in ["chest", "deltoids", "shoulders", "triceps"]):
        return "push"
    if any(m in pms for m in ["lats", "middle back", "traps", "biceps"]):
        return "pull"
    return "other"


def _exercise_text(row: Dict[str, Any]) -> str:
    parts: List[str] = []
    parts.append(row.get("name", ""))
    if row.get("category"):
        parts.append(f"Category: {row['category']}")
    if row.get("equipment"):
        parts.append(f"Equipment: {row['equipment']}")
    if row.get("movementPattern"):
        parts.append(f"Pattern: {row['movementPattern']}")
    if row.get("primaryMuscles"):
        parts.append("Primary: " + ", ".join(row.get("primaryMuscles", [])))
    if row.get("secondaryMuscles"):
        parts.append("Secondary: " + ", ".join(row.get("secondaryMuscles", [])))
    instr = row.get("instructions") or []
    if isinstance(instr, list) and instr:
        parts.append("Instructions: " + " ".join(instr))
    return "\n".join([p for p in parts if p])


def ingest_exercises(json_path: str = "exercises/exercises.json") -> int:
    connect_milvus()
    col = ensure_exercise_collection()
    with open(json_path, "r", encoding="utf-8") as f:
        rows: List[Dict[str, Any]] = json.load(f)

    # Normalize movementPattern: prefer dataset field if present, else fallback
    for r in rows:
        if not r.get("movementPattern"):
            mp = r.get("movement_pattern") or r.get("movement_patterns")
            if isinstance(mp, list):
                r["movementPattern"] = mp[0] if mp else ""
            elif isinstance(mp, str):
                r["movementPattern"] = mp
            else:
                r["movementPattern"] = classify_pattern(r)

    texts = [_exercise_text(r) for r in rows]
    embeddings = embed_texts(texts)

    fields = col.schema.fields
    pk_field = next((f for f in fields if getattr(f, "is_primary", False)), None)
    auto_pk = bool(getattr(pk_field, "auto_id", False)) if pk_field else False

    # Identify vector field
    vector_field_name = None
    for f in fields:
        if f.dtype == DataType.FLOAT_VECTOR:
            vector_field_name = f.name
            break
    if not vector_field_name:
        raise ValueError("No FLOAT_VECTOR field found in Milvus collection schema")

    # Helper to build per-field values safely (respect max_length)
    def vals_for(f: FieldSchema) -> List[Any]:
        name = f.name
        lname = name.lower().replace("_", "")
        if auto_pk and pk_field and name == pk_field.name:
            # omit auto id field by returning sentinel None; caller will skip
            return []
        if pk_field and not auto_pk and name == pk_field.name:
            return list(range(1, len(rows) + 1))
        if name == vector_field_name:
            return embeddings
        if f.dtype == DataType.VARCHAR:
            max_len = getattr(f, "max_length", 2048)
            if name.lower() == "name" or "title" in lname:
                return [str(r.get("name", ""))[:max_len] for r in rows]
            if name.lower() == "source":
                return [str(r.get("id", r.get("name", "")))[:max_len] for r in rows]
            if name.lower() == "text" or any(k in lname for k in ["content", "doc", "body"]):
                return [t[:max_len] for t in texts]
            if "movementpattern" in lname or lname == "pattern":
                return [r.get("movementPattern").lower()[:max_len] for r in rows]
            if "equipment" in lname:
                return [str(r.get("equipment", "") or "")[:max_len] for r in rows]
            # Unknown VARCHAR → empty
            return ["" for _ in rows]
        # Unknown dtype → zeros
        return [0 for _ in rows]

    data: List[List[Any]] = []
    for f in fields:
        if auto_pk and pk_field and f.name == pk_field.name:
            continue
        data.append(vals_for(f))

    col.insert(data)
    col.flush()
    return len(rows)


def search_exercises(query: str, top_k: int = 10, *, pattern: Optional[str] = None) -> List[Dict[str, Any]]:
    connect_milvus()
    col = Collection(EX_COLLECTION)
    col.load()
    q_vec = embed_texts([query])[0]
    schema_fields = {f.name for f in col.schema.fields}
    move_field = "movementPattern" if "movementPattern" in schema_fields else (
        "movement_pattern" if "movement_pattern" in schema_fields else None
    )
    out_fields = [f for f in ["name", "text", "source"] if f in schema_fields]
    if move_field:
        out_fields.append(move_field)
    expr = None
    if pattern and move_field:
        expr = f"{move_field} == \"{pattern}\""

    res = col.search(
        data=[q_vec],
        anns_field="vector",
        param={"metric_type": "COSINE", "params": {"nprobe": 16}},
        limit=top_k,
        output_fields=out_fields,
        expr=expr,
    )
    out: List[Dict[str, Any]] = []
    for hit in res[0]:
        item = {
            "name": hit.entity.get("name"),
            "text": hit.entity.get("text"),
            "source": hit.entity.get("source"),
            "score": float(hit.distance),
        }
        if move_field:
            item[move_field] = hit.entity.get(move_field)
        out.append(item)
    return out

