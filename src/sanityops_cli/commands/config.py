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

"""config command — Get and set sanityops configuration.

Config keys use dot notation, e.g. ``server.base_url``. They correspond to
the sanityops SaaS backend (NOT the LLM model config, which lives under
``model.*``). Precedence: project-level > global > env var > default.
"""

from __future__ import annotations

import os
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from sanityops_cli.constants.config_defaults import DEFAULT_SERVER_BASE_URL
from sanityops_cli.constants.exit_codes import EXIT_FAILURE
from sanityops_cli.utils.config_resolver import ConfigResolver

console = Console()

# Create a Typer app for config subcommand
config_app = typer.Typer(
    name="config",
    help="Get and set sanityops configuration (server base URL, API key, etc.)",
    no_args_is_help=True,
    context_settings={"allow_interspersed_args": True},
)

# Registry of known config keys: metadata for reading defaults / masking.
# New config keys can be added here without touching resolve logic.
CONFIG_SCHEMA: dict[str, dict[str, Any]] = {
    "server.base_url": {
        "env": "SANITYOPS_BASE_URL",
        "default": DEFAULT_SERVER_BASE_URL,
        "sensitive": False,
    },
    "server.api_key": {
        "env": "SANITYOPS_API_KEY",
        "default": None,
        "sensitive": True,
    },
}


def _is_sensitive_key(key: str) -> bool:
    """Check if a key holds a sensitive value (masked on display)."""
    return bool(CONFIG_SCHEMA.get(key, {}).get("sensitive"))


def _mask_sensitive_value(value: str | None) -> str:
    """Mask a sensitive value for display: first 3 + '***' + last 4 chars.

    Short values (< 8 chars) are fully masked. None -> '(not set)'.
    """
    if value is None:
        return "(not set)"
    if len(value) <= 7:
        return "***"
    return f"{value[:3]}***{value[-4:]}"


def _display_value(key: str, value: str | None) -> str:
    """Return the value as it should be shown, masking sensitive keys."""
    if value is None:
        return ""
    if _is_sensitive_key(key):
        return _mask_sensitive_value(value)
    return str(value)


def _flatten_config(data: dict[str, Any], prefix: str = "") -> list[tuple[str, Any]]:
    """Flatten a nested config dict into (dot.key, value) tuples."""
    result: list[tuple[str, Any]] = []
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            result.extend(_flatten_config(value, full_key))
        else:
            result.append((full_key, value))
    return result


@config_app.callback(invoke_without_command=True)
def config_callback(
    ctx: typer.Context,
    key: str = typer.Argument(None, help="Config key, e.g. server.base_url"),
    value: str = typer.Argument(None, help="Config value (omit to read)"),
    list_all: bool = typer.Option(False, "--list", "-l", help="List all config values"),
    unset: str = typer.Option(None, "--unset", help="Remove a config key"),
    global_config: bool = typer.Option(
        False,
        "--global",
        help="Operate on global config (default behavior)",
    ),
    local_config: bool = typer.Option(
        False,
        "--local",
        help="Operate on project-level config",
    ),
) -> None:
    """Get, set, or list sanityops configuration values.

    Precedence: project-level > global > environment variables > default.

    Examples:
        sanityops-cli config server.base_url               # Read value
        sanityops-cli config server.base_url http://...    # Set (global, default)
        sanityops-cli config server.base_url http://... --local   # Set project-level
        sanityops-cli config server.api_key                # Read (masked) value
        sanityops-cli config --list                         # List all values
        sanityops-cli config --unset server.base_url        # Remove key
    """
    if list_all:
        _list_config()
        return

    if unset:
        _unset_config(unset, local=local_config)
        return

    if not key:
        console.print(ctx.get_help())
        return

    use_local = local_config  # --local overrides; default is global

    if value is None:
        _read_config(key)
    else:
        _write_config(key, value, local=use_local)


def _read_config(key: str) -> None:
    """Read and display a config value."""
    schema = CONFIG_SCHEMA.get(key, {})
    resolver = ConfigResolver(
        config_key=key,
        env_var=schema.get("env"),
        default=schema.get("default"),
    )
    resolved = resolver.resolve()

    if resolved is None:
        console.print(f"[yellow]{key} is not set[/yellow]")
        raise typer.Exit()

    console.print(_display_value(key, resolved))


def _write_config(key: str, value: str, local: bool = False) -> None:
    """Write a config value to the global or project config file."""
    try:
        if local:
            ConfigResolver.set_project(key, value)
            console.print(f"[green]✓[/green] Set {key} in project config")
        else:
            ConfigResolver.set_global(key, value)
            console.print(f"[green]✓[/green] Set {key} in global config")
    except Exception as e:
        console.print(f"[red]✗ Failed to write config: {e}[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None


def _unset_config(key: str, local: bool = False) -> None:
    """Remove a config key from the global or project config file."""
    try:
        removed = ConfigResolver.unset_project(key) if local else ConfigResolver.unset_global(key)
        if removed:
            location = "project config" if local else "global config"
            console.print(f"[green]✓[/green] Removed {key} from {location}")
        else:
            console.print(f"[yellow]{key} was not set[/yellow]")
    except Exception as e:
        console.print(f"[red]✗ Failed to unset config: {e}[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None


def _list_config() -> None:
    """List all config values from global and project configs."""
    global_config = ConfigResolver.list_global()
    project_config = ConfigResolver.list_project()

    if not global_config and not project_config:
        console.print("[yellow]No configuration found[/yellow]")
        console.print("\n  Run: sanityops-cli config server.base_url <url>")
        console.print("  Run: sanityops-cli config server.api_key <key>")
        return

    table = Table(title="[bold]Sanityops Configuration[/]", border_style="blue")
    table.add_column("Key", style="cyan", no_wrap=True)
    table.add_column("Global", style="white")
    table.add_column("Project", style="green")

    # Merge keys from both configs.
    items: dict[str, tuple[Any, Any]] = {}
    for k, v in _flatten_config(global_config):
        items.setdefault(k, (None, None))
        items[k] = (v, items[k][1])
    for k, v in _flatten_config(project_config):
        items.setdefault(k, (None, None))
        items[k] = (items[k][0], v)

    for key in sorted(items):
        global_val, project_val = items[key]
        table.add_row(
            key,
            _display_value(key, global_val),
            _display_value(key, project_val),
        )

    console.print(table)

    # Report which known env vars are set.
    env_set = [
        (env_name, _display_value(key, os_val))
        for key, env_name, os_val in (
            (
                k,
                v["env"],
                os.environ.get(v["env"]),
            )
            for k, v in CONFIG_SCHEMA.items()
            if v.get("env")
        )
        if os_val
    ]
    if env_set:
        console.print("\n[dim]Environment variables set:[/dim]")
        for env_name, val in env_set:
            console.print(f"  [dim]{env_name}={val}[/dim]")
