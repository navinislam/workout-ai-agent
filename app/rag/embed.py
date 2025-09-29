from __future__ import annotations

import os
from typing import Iterable, List

from dotenv import load_dotenv
from openai import OpenAI


def _batched(it: Iterable[str], n: int):
    buf: List[str] = []
    for x in it:
        buf.append(x)
        if len(buf) == n:
            yield buf
            buf = []
    if buf:
        yield buf


def embed_texts(texts: List[str], model: str | None = None) -> List[List[float]]:
    """
    Embed a list of texts using OpenAI embeddings.
    Model defaults to env RAG_EMBED_MODEL or 'text-embedding-3-small' (1536-dim).
    """
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set for embeddings")
    model = model or os.getenv("RAG_EMBED_MODEL", "text-embedding-3-small")
    client = OpenAI(api_key=api_key)

    out: List[List[float]] = []
    for batch in _batched(texts, 64):
        resp = client.embeddings.create(model=model, input=batch)
        out.extend([r.embedding for r in resp.data])
    return out

