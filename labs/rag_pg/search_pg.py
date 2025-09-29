import os
import click
import psycopg2
from dotenv import load_dotenv
from labs.rag_core.embed import embed_texts
from openai import OpenAI


SYSTEM = "Use the retrieved context to answer. Cite with [n] and list sources. If unknown, say so." 


def connect():
    url = os.getenv("SUPABASE_URL")
    if not url:
        raise SystemExit("Missing SUPABASE_URL")
    return psycopg2.connect(url)


@click.command()
@click.option("--query", required=True)
@click.option("--k", default=5)
def cli(query: str, k: int):
    load_dotenv()
    q_vec = embed_texts([query])[0]
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "select id, source, chunk, 1 - (embedding <=> %s::vector) as score from documents order by embedding <=> %s::vector asc limit %s",
        (q_vec, q_vec, k),
    )
    rows = cur.fetchall()
    ctx = [
        {"id": r[0], "source": r[1], "text": r[2], "score": float(r[3])}
        for r in rows
    ]
    ctx_str = "\n\n".join([f"[{i+1}] {c['text']}\n(Source: {c['source']})" for i, c in enumerate(ctx)])
    api_key = os.getenv("OPENAI_API_KEY")
    client = OpenAI(api_key=api_key)
    user = f"Context:\n{ctx_str}\n\nQuestion: {query}"
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
        temperature=0,
    )
    print(resp.choices[0].message.content)


if __name__ == "__main__":
    cli()

