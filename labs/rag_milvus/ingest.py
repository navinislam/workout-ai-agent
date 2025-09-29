import os
import json
from pathlib import Path
from typing import List, Dict
import click
from dotenv import load_dotenv
from pymilvus import connections, Collection
from labs.rag_core.chunk import chunk_files
from labs.rag_core.embed import embed_texts


def connect_milvus():
    host = os.getenv("MILVUS_HOST", "localhost")
    port = os.getenv("MILVUS_PORT", "19530")
    connections.connect(alias="default", host=host, port=port)


@click.command()
@click.option("--glob", "glob_pat", default="content/*.md")
@click.option("--spec", type=click.Path(exists=True), help="Optional extra file to include, e.g. SPEC.md")
@click.option("--collection", default="docs")
def cli(glob_pat: str, spec: str | None, collection: str):
    load_dotenv()
    connect_milvus()

    paths = [Path(p) for p in Path.cwd().glob(glob_pat)]
    if spec:
        paths.append(Path(spec))
    rows = chunk_files(paths)
    embeddings = embed_texts([r["text"] for r in rows])
    for r, e in zip(rows, embeddings):
        r["embedding"] = e

    col = Collection(collection)
    # Prepare fields: id auto, so use None; text, source, vector
    data = [
        [None for _ in rows],
        [r["text"] for r in rows],
        [r["source"] for r in rows],
        [r["embedding"] for r in rows],
    ]
    mr = col.insert(data)
    col.flush()
    print(f"Inserted {len(rows)} rows into {collection}")


if __name__ == "__main__":
    cli()

