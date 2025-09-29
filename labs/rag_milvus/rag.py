import os
import click
from dotenv import load_dotenv
from openai import OpenAI
from .search import connect, search


SYSTEM = """
You are a concise assistant. Use the retrieved context to answer and include inline citations like [1], [2]. If unknown, say so.
""".strip()


@click.command()
@click.option("--query", required=True)
@click.option("--collection", default="docs")
@click.option("--k", default=5, help="Top-k results")
def cli(query: str, collection: str, k: int):
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("Missing OPENAI_API_KEY")
    client = OpenAI(api_key=api_key)
    connect()
    results = search(collection, query, top_k=k)
    ctx_str = "\n\n".join([f"[{i+1}] {r['text']}\n(Source: {r['source']})" for i, r in enumerate(results)])
    user = f"Context:\n{ctx_str}\n\nQuestion: {query}"
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        temperature=0
    )
    print(resp.choices[0].message.content)


if __name__ == "__main__":
    cli()

