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

"""Init command — Initialize inspect configuration."""

from pathlib import Path

import typer
from rich.console import Console

from sanityops_cli.commands.inspect import inspect_app
from sanityops_cli.constants.exit_codes import EXIT_FAILURE

console = Console()

# Default paths
DEFAULT_CONFIG_DIR = ".sanityops"
DEFAULT_CONFIG_FILE = "inspect_config.yaml"


@inspect_app.command("init")
def init_config() -> None:
    """Initialize .sanityops/inspect_config.yaml with a template.

    Creates a new config file with a placeholder project UUID. The project
    stays unbound until the first inspect upload auto-creates it and writes
    the real project id/name back to this file.
    If a config already exists, prompts to backup and replace.
    """
    from datetime import datetime

    config_dir = Path.cwd() / DEFAULT_CONFIG_DIR
    config_file = config_dir / DEFAULT_CONFIG_FILE

    # Handle existing config file
    if config_file.exists():
        console.print(
            f"[yellow]![/yellow] Config file already exists at {config_file}"
        )
        if not typer.confirm("Backup and create new?", default=False):
            console.print("[red]✗[/red] Operation cancelled. Existing config preserved.")
            return  # Using return instead of typer.Exit(0) for test compatibility

        # Backup existing file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = config_dir / f"inspect_config.yaml.bak.{timestamp}"
        try:
            config_file.rename(backup_file)
            console.print(f"[green]✓[/green] Backed up to {backup_file}")
        except OSError as e:
            console.print(f"[red]✗ Cannot backup existing config: {e}[/red]")
            raise typer.Exit(code=EXIT_FAILURE) from None

    # Ensure directory exists
    try:
        config_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        console.print(f"[red]✗ Cannot create .sanityops directory: {e}[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None

    # Load template and generate UUID
    try:
        template_content = _load_template()
    except (FileNotFoundError, ModuleNotFoundError, OSError) as e:
        console.print(f"[red]✗ Internal error: template not found ({e})[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None

    # The placeholder UUID is intentionally left as-is so that the first
    # inspect upload auto-creates the project and writes the real id/name
    # back to this config file.

    # Write config file
    try:
        with open(config_file, "w", encoding="utf-8") as f:
            f.write(template_content)
    except OSError as e:
        console.print(f"[red]✗ Cannot write config file: {e}[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None

    # Keep secrets out of git: the config file holds the API key and the
    # results directory holds scanned source artifacts. A nested .gitignore
    # inside the generated directory covers both without touching the
    # user's repository root .gitignore.
    try:
        (config_dir / ".gitignore").write_text("*\n", encoding="utf-8")
    except OSError as e:
        console.print(f"[yellow]⚠ Could not write {config_dir / '.gitignore'}: {e}[/yellow]")

    console.print("[green]✓[/green] Created .sanityops/inspect_config.yaml")
    console.print("Before running inspect, you need:")
    console.print("- Edit this file to add your prompts, tools, and skills.")
    console.print(
        "- Edit this file to add your provider, api_key, model_id and base_url "
        "(optional. If omitted, the CLI uses LLM_* environment variables)."
    )
    console.print("- To connect to the Sanityops service, configure the server URL and API key:")
    console.print('sanityops-cli config server.base_url "<your-server-url>"')
    console.print('sanityops-cli config server.api_key "<your-api-key>"')


def _load_template() -> str:
    """Load the inspect_config.yaml template as a string.

    Returns:
        Template content with placeholder UUID. Returns as string
        to preserve YAML comments.
    """
    import sys

    # PyInstaller bundles resources in sys._MEIPASS
    if hasattr(sys, "_MEIPASS"):
        template_path = Path(sys._MEIPASS) / "sanityops_cli" / "templates" / "inspect_config.yaml"
    else:
        # Standard importlib.resources for normal Python environments
        import importlib.resources

        template_path = importlib.resources.files("sanityops_cli.templates") / "inspect_config.yaml"
        return template_path.read_text(encoding="utf-8")

    return template_path.read_text(encoding="utf-8")
