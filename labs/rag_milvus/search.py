import os
from typing import List, Dict
from dotenv import load_dotenv
from openai import OpenAI
from pymilvus import connections, Collection
from labs.rag_core.embed import embed_texts


def connect():
    host = os.getenv("MILVUS_HOST", "localhost")
    port = os.getenv("MILVUS_PORT", "19530")
    connections.connect(alias="default", host=host, port=port)


def search(collection: str, query: str, top_k: int = 5) -> List[Dict]:
    q_vec = embed_texts([query])[0]
    col = Collection(collection)
    col.load()
    res = col.search(
        data=[q_vec],
        anns_field="vector",
        param={"metric_type": "COSINE", "params": {"nprobe": 16}},
        limit=top_k,
        output_fields=["text", "source"],
    )
    out = []
    for hit in res[0]:
        out.append({
            "text": hit.entity.get("text"),
            "source": hit.entity.get("source"),
            "score": float(hit.distance),
        })
    return out

