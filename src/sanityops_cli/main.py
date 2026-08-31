# Copyright 2026 zipsonken
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

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
        typer.echo(f"sanityops-cli v{__version__}")
        typer.echo("Copyright (C) 2026 zipsonken / Sanity AI Labs")
        typer.echo("License: Apache 2.0 (https://www.apache.org/licenses/LICENSE-2.0)")
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
