import re
from pathlib import Path
from typing import List, Dict
import click


def split_markdown(text: str, max_chars: int = 800, overlap: int = 100) -> List[str]:
    paragraphs = re.split(r"\n\s*\n", text)
    chunks = []
    buff = ""
    for para in paragraphs:
        if len(buff) + len(para) + 2 <= max_chars:
            buff = (buff + "\n\n" + para).strip()
        else:
            if buff:
                chunks.append(buff)
                # create overlap
                buff = buff[-overlap:] + "\n\n" + para
            else:
                # very long paragraph, hard split
                for i in range(0, len(para), max_chars):
                    chunks.append(para[i:i+max_chars])
                buff = ""
    if buff:
        chunks.append(buff)
    return chunks


def chunk_files(paths: List[Path], max_chars: int = 800, overlap: int = 100) -> List[Dict]:
    rows: List[Dict] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for idx, chunk in enumerate(split_markdown(text, max_chars=max_chars, overlap=overlap)):
            rows.append({
                "source": str(path),
                "chunk_id": idx,
                "text": chunk,
            })
    return rows


@click.command()
@click.option("--glob", "glob_pat", default="content/*.md", help="Glob of files to chunk")
@click.option("--max", "max_chars", default=800, help="Max chars per chunk")
@click.option("--overlap", default=100, help="Overlap in chars between chunks")
def cli(glob_pat: str, max_chars: int, overlap: int):
    paths = [Path(p) for p in Path.cwd().glob(glob_pat)]
    rows = chunk_files(paths, max_chars=max_chars, overlap=overlap)
    click.echo(f"Chunks: {len(rows)} from {len(paths)} files")


if __name__ == "__main__":
    cli()

