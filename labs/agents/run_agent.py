import click
from .agent import run_agent


@click.command()
@click.option("--query", required=True, help="User question")
def cli(query: str):
    answer = run_agent(query)
    print(answer)


if __name__ == "__main__":
    cli()

