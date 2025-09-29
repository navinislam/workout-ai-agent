import math
from typing import List, Dict, Tuple
import numpy as np


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def top_k(query_vec: List[float], rows: List[Dict], k: int = 5) -> List[Tuple[Dict, float]]:
    q = np.array(query_vec, dtype=np.float32)
    scored = []
    for r in rows:
        v = np.array(r["embedding"], dtype=np.float32)
        scored.append((r, cosine(q, v)))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:k]

