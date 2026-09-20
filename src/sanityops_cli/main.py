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

# Windows consoles default to GBK/cp936 in zh-CN locales, which cannot encode
# symbols like ✓/✗/⚠ used throughout the CLI output. Force UTF-8 streams early
# so output never crashes regardless of terminal code page.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass

import typer  # noqa: E402 - must come after stdout reconfiguration
from rich.console import Console  # noqa: E402

from sanityops_cli import __version__  # noqa: E402
from sanityops_cli.commands.config import config_app  # noqa: E402
from sanityops_cli.commands.init import init_config  # noqa: E402
from sanityops_cli.commands.inspect import inspect_app  # noqa: E402
from sanityops_cli.exceptions.base_exceptions import ValidationError  # noqa: E402
from sanityops_cli.help_panel import (  # noqa: E402
    get_advanced_usage_panel,
    get_getting_started_panel,
)

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
app.add_typer(
    config_app,
    name="config",
    help="Get and set sanityops configuration (server base URL, API key, etc.)",
)
app.command("init")(init_config)


def main():
    """Entrance function for the Sanityops CLI application."""
    # Check if --help is requested for the main app only (no subcommand)
    # This means: --help present, no subcommand (first arg after flags would be a command)
    is_help = "--help" in sys.argv or "-h" in sys.argv
    is_version = "--version" in sys.argv or "-V" in sys.argv
    # No subcommand if: only flags, or only the app name
    has_subcommand = any(arg and not arg.startswith("-") for arg in sys.argv[1:])
    # Also show panel when no args (no_args_is_help=True will show help)
    is_no_args_help = len(sys.argv) == 1

    if (is_help or is_no_args_help) and not is_version and not has_subcommand:
        # Use a custom console to capture and extend help output
        console = Console()
        try:
            app()
        except SystemExit as e:
            # Intercept successful exits and help exits. no_args_is_help exits
            # with code 2 (click's UsageError code), so accept 0 and 2 here;
            # re-raise anything else (real usage errors keep failing).
            if e.code not in (0, 2):
                raise
        # Print the Getting Started and Advanced Usage panels
        console.print()
        console.print(get_getting_started_panel())
        console.print()
        console.print(get_advanced_usage_panel())
        return

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
