import os
import json
from pathlib import Path
from typing import List, Dict
import click
from dotenv import load_dotenv
from openai import OpenAI
from .embed import embed_texts
from .retrieve import top_k


SYSTEM = """
You are a concise assistant. Answer strictly using the provided context snippets. Cite sources inline as [n] and list sources at the end.
If the answer is not in the context, say you don't know.
""".strip()


def make_prompt(question: str, contexts: List[Dict]) -> List[Dict]:
    header = "Answer the question using the context."
    ctx_str = "\n\n".join([
        f"[{i+1}] {c['text']}\n(Source: {c['source']}#{c['chunk_id']})" for i, c in enumerate(contexts)
    ])
    user = f"{header}\n\nContext:\n{ctx_str}\n\nQuestion: {question}"
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": user},
    ]


@click.command()
@click.option("--corpus", default="rag_corpus.jsonl", help="JSONL with {text, source, chunk_id, embedding}")
@click.option("--query", required=True, help="Question to ask")
@click.option("--k", default=5, help="Top-k")
def cli(corpus: str, query: str, k: int):
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("Missing OPENAI_API_KEY")
    client = OpenAI(api_key=api_key)

    rows: List[Dict] = []
    with open(corpus, "r", encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))

    q_vec = embed_texts([query])[0]
    contexts = [r for r, _ in top_k(q_vec, rows, k=k)]
    messages = make_prompt(query, contexts)
    resp = client.chat.completions.create(model="gpt-4o-mini", messages=messages, temperature=0)
    print(resp.choices[0].message.content)


if __name__ == "__main__":
    cli()

