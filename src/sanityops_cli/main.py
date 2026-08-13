"""Sanityops CLI Entrance — Typer Application"""

import sys

import typer

from sanityops_cli import __version__
from sanityops_cli.commands.init import init_config
from sanityops_cli.commands.inspect import inspect_app
from sanityops_cli.exceptions.base_exceptions import ValidationError

app = typer.Typer(
    name="Sanityops-cli",
    help="Sanityops CLI Tool — A cli tool for sanityops",
    no_args_is_help=True,
)


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"sanityops-cli version {__version__}")
        raise typer.Exit()


@app.callback()
def callback(
    _version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show version and exit",
        is_eager=True,
        callback=version_callback,
    ),
):
    """Sanityops CLI callback."""

app.add_typer(inspect_app, name="inspect", help="Static defect inspection of logical artifacts (System Prompts, Skills, Tool Schemas), suitable for local development or CI/CD integration")
app.command("init")(init_config)


def main():
    """Entrance function for the Sanityops CLI application."""
    try:
        app()
    except ValidationError as e:
        print(f"Validation Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unknown Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
