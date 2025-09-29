import json
import click
import requests


@click.command()
@click.option("--tool", required=True, help="Tool name, e.g., milvus.search")
@click.option("--args", "args_json", default="{}", help='JSON, e.g. {"query":"hi"}')
@click.option("--base", default="http://127.0.0.1:8000", help="Server base URL")
def cli(tool: str, args_json: str, base: str):
    payload = {"name": tool, "args": json.loads(args_json)}
    r = requests.post(f"{base}/tools/call", json=payload, timeout=30)
    r.raise_for_status()
    print(json.dumps(r.json(), indent=2))


if __name__ == "__main__":
    cli()

