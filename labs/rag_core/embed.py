import os
import json
from typing import Iterable, List, Dict
from dotenv import load_dotenv
from openai import OpenAI
import click


def batched(it: Iterable, n: int):
    buf = []
    for x in it:
        buf.append(x)
        if len(buf) == n:
            yield buf
            buf = []
    if buf:
        yield buf


def embed_texts(texts: List[str], model: str = "text-embedding-3-small") -> List[List[float]]:
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")
    client = OpenAI(api_key=api_key)

    out: List[List[float]] = []
    for batch in batched(texts, 64):
        resp = client.embeddings.create(model=model, input=batch)
        out.extend([r.embedding for r in resp.data])
    return out


@click.command()
@click.argument("input_jsonl")
@click.argument("output_jsonl")
def cli(input_jsonl: str, output_jsonl: str):
    """
    Read JSONL with {text, ...}, write JSONL with {text, embedding, ...}
    """
    rows: List[Dict] = []
    with open(input_jsonl, "r", encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    embeddings = embed_texts([r["text"] for r in rows])
    with open(output_jsonl, "w", encoding="utf-8") as f:
        for r, e in zip(rows, embeddings):
            r["embedding"] = e
            f.write(json.dumps(r) + "\n")
    click.echo(f"Embedded {len(rows)} rows → {output_jsonl}")


if __name__ == "__main__":
    cli()

