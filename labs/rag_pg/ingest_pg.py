import os
import json
from pathlib import Path
from typing import List, Dict
import click
from dotenv import load_dotenv
import psycopg2
from labs.rag_core.chunk import chunk_files
from labs.rag_core.embed import embed_texts


def connect():
    url = os.getenv("SUPABASE_URL")
    if not url:
        raise SystemExit("Missing SUPABASE_URL; include credentials in the URL or use a local psql tunnel")
    return psycopg2.connect(url)


@click.command()
@click.option("--glob", "glob_pat", default="content/*.md")
@click.option("--spec", type=click.Path(exists=True), help="Optional extra file to include, e.g. SPEC.md")
def cli(glob_pat: str, spec: str | None):
    load_dotenv()
    paths = [Path(p) for p in Path.cwd().glob(glob_pat)]
    if spec:
        paths.append(Path(spec))
    rows = chunk_files(paths)
    embeddings = embed_texts([r["text"] for r in rows])
    for r, e in zip(rows, embeddings):
        r["embedding"] = e

    conn = connect()
    cur = conn.cursor()
    cur.execute("create extension if not exists vector;")
    cur.execute("""
        create table if not exists documents (
          id bigserial primary key,
          source text,
          chunk text,
          embedding vector(1536)
        );
    """)
    for r in rows:
        cur.execute(
            "insert into documents(source, chunk, embedding) values (%s, %s, %s)",
            (r["source"], r["text"], r["embedding"]),
        )
    conn.commit()
    print(f"Inserted {len(rows)} rows into documents")


if __name__ == "__main__":
    cli()

