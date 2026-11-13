"""Init command — Initialize inspect configuration."""

from pathlib import Path

import typer
from rich.console import Console

from deeplogic_cli.commands.inspect import inspect_app
from deeplogic_cli.constants.exit_codes import EXIT_FAILURE

console = Console()

# Default paths
DEFAULT_CONFIG_DIR = ".deeplogic"
DEFAULT_CONFIG_FILE = "inspect_config.yaml"


@inspect_app.command("init")
def init_config() -> None:
    """Initialize .deeplogic/inspect_config.yaml with a template.

    Creates a new config file with a placeholder project UUID. The project
    stays unbound until 'project create' or 'project bind' is run.
    If a config already exists, prompts to backup and replace.
    """
    from datetime import datetime

    config_dir = Path.cwd() / DEFAULT_CONFIG_DIR
    config_file = config_dir / DEFAULT_CONFIG_FILE

    # Handle existing config file
    if config_file.exists():
        console.print(f"[yellow]![/yellow] Config file already exists at {config_file}")
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
        console.print(f"[red]✗ Cannot create .deeplogic directory: {e}[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None

    # Load template and generate UUID
    try:
        template_content = _load_template()
    except (FileNotFoundError, ModuleNotFoundError, OSError) as e:
        console.print(f"[red]✗ Internal error: template not found ({e})[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None

    # The placeholder UUID is intentionally left as-is so that 'project status'
    # can correctly report the project as unbound. Real project binding happens
    # via 'deeplogic-cli project create <name>' or 'project bind <id>'.

    # Write config file
    try:
        with open(config_file, "w", encoding="utf-8") as f:
            f.write(template_content)
    except OSError as e:
        console.print(f"[red]✗ Cannot write config file: {e}[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None

    console.print("[green]✓[/green] Created .deeplogic/inspect_config.yaml")
    console.print("Before running inspect, you need:")
    console.print("-Edit this file to add your prompts, tools, and skills.")
    console.print(
        "-Edit this file to add your provider, api_key, model_id and base_url "
        "(optional. If omitted, the CLI uses LLM_* environment variables)."
    )
    console.print("-To connect to the Deeplogic service, configure the server URL and API key:")
    console.print('deeplogic-cli config server.base_url "<your-server-url>"')
    console.print("deeplogic-cli config server.api_key")


def _load_template() -> str:
    """Load the inspect_config.yaml template as a string.

    Returns:
        Template content with placeholder UUID. Returns as string
        to preserve YAML comments.
    """
    import sys

    # PyInstaller bundles resources in sys._MEIPASS
    if hasattr(sys, "_MEIPASS"):
        template_path = Path(sys._MEIPASS) / "deeplogic_cli" / "templates" / "inspect_config.yaml"
        return template_path.read_text(encoding="utf-8")

    # Standard importlib.resources for normal Python environments
    import importlib.resources

    template = importlib.resources.files("deeplogic_cli.templates") / "inspect_config.yaml"
    return template.read_text(encoding="utf-8")
