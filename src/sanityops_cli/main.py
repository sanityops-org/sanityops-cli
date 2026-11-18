"""sanityops CLI Entrance — Typer Application"""

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
from sanityops_cli.commands.project import project_app  # noqa: E402,F401 - retained for future use
from sanityops_cli.exceptions.base_exceptions import ValidationError  # noqa: E402
from sanityops_cli.help_panel import (  # noqa: E402
    get_advanced_usage_panel,
    get_getting_started_panel,
)

app = typer.Typer(
    name="sanityops-cli",
    help="sanityops CLI Tool — A cli tool for sanityops",
    no_args_is_help=True,
    add_completion=False,
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
    """sanityops CLI callback."""


app.add_typer(
    inspect_app,
    name="inspect",
    help="Static defect inspection of logical artifacts (System Prompts, Skills, Tool Schemas), suitable for local development or CI/CD integration",
)
app.add_typer(
    config_app,
    name="config",
    help="Get and set sanityops configuration (server base URL, API key, etc.)",
)
# Project command group (hidden from --help, see README for details)
app.add_typer(
    project_app,
    name="project",
    help="Project binding (see README for details)",
    hidden=True,
)
app.command("init")(init_config)


def main():
    """Entrance function for the sanityops CLI application."""
    # Show panels only when --help is the sole flag or there are no args.
    # This narrow trigger avoids showing panels on usage errors (-h, --bogus).
    #
    # Note: --version/-V doesn't need explicit handling here because:
    # - `--version` won't match the exact `["--help"]` check
    # - Single-arg `--version` has len > 1, so is_no_args_help is False
    # - It falls through to the normal app() path, which prints version and exits.
    is_only_help = sys.argv[1:] == ["--help"]
    is_no_args_help = len(sys.argv) == 1

    if is_only_help or is_no_args_help:
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
