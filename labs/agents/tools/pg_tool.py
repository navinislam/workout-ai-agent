import os
from typing import List, Dict
import psycopg2
from dotenv import load_dotenv


def query_supabase(query: str, params: List = None, limit: int = 10) -> List[Dict]:
    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    if not url:
        raise SystemExit("Missing SUPABASE_URL")
    conn = psycopg2.connect(url)
    cur = conn.cursor()
    # Whitelist simple SELECTs only; prevent dangerous ops
    q = query.strip().lower()
    if not q.startswith("select"):
        raise ValueError("Only SELECT queries are allowed")
    if "delete" in q or "update" in q or "insert" in q or ";" in q:
        raise ValueError("Unsafe SQL detected")
    if " limit " not in q:
        q = q + f" limit {int(limit)}"
    cur.execute(q, params or [])
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    return rows

