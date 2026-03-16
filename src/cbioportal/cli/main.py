"""cbio — root CLI entry point."""
from __future__ import annotations

import sys

import typer

from cbioportal.cli.commands import beta, config_cmd, data, search

app = typer.Typer(help="cbio — cBioPortal data access from your terminal")


@app.callback()
def main(
    ctx: typer.Context,
    no_interactive: bool = typer.Option(
        False,
        "--no-interactive",
        help="Disable interactive prompts; for use in scripts/pipelines",
    ),
) -> None:
    ctx.ensure_object(dict)
    ctx.obj["interactive"] = not no_interactive and sys.stdout.isatty()


app.add_typer(search.app, name="search")
app.add_typer(data.app, name="data")
app.add_typer(config_cmd.app, name="config")
app.add_typer(
    beta.app,
    name="beta",
    help="[Beta] Local DuckDB server and sync commands",
)

if __name__ == "__main__":
    app()
