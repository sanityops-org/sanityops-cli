"""Project command — version management for artifacts.

Visible commands form the bind-only workflow:
- bind: Bind an existing remote project (hidden but documented in README)

Hidden commands (not ready for general use):
- push: Tool schema parsing has limited format compatibility
- check: Requires JWT token, not API key
- all: Chains push/check (the repair step is disabled)
- create/status/log/show: Legacy git-like commands, use bind instead
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from deeplogic_cli.api.client import DeeplogicClient
from deeplogic_cli.constants.config_defaults import DEFAULT_SERVER_BASE_URL
from deeplogic_cli.constants.exit_codes import EXIT_FAILURE
from deeplogic_cli.exceptions.api_exceptions import (
    APIError,
    AuthenticationError,
    NetworkError,
    ProjectNotFoundError,
)
from deeplogic_cli.utils.config_loader import (
    InspectConfigLoader,
    read_file_with_encoding_fallback,
)
from deeplogic_cli.utils.config_resolver import ConfigResolver

console = Console()

# UUID validation regex
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

# Config paths
DEFAULT_CONFIG_DIR = ".deeplogic"
DEFAULT_CONFIG_FILE = "inspect_config.yaml"

# Placeholder UUID used by init template before project binding
PLACEHOLDER_UUID = "00000000-0000-0000-0000-000000000000"


def _require_api_key() -> tuple[str, str]:
    """Check API key is configured, return (base_url, api_key) or exit.

    Returns:
        Tuple of (base_url, api_key).

    Raises:
        typer.Exit: If API key is not configured.
    """
    api_key = ConfigResolver("server.api_key", "DEEPLOGIC_API_KEY").resolve()
    if not api_key:
        console.print("[red]✗ API key not configured[/red]")
        console.print("\n  Run: deeplogic-cli config server.api_key <your-key>")
        console.print("  Or:  export DEEPLOGIC_API_KEY=<your-key>")
        raise typer.Exit(code=EXIT_FAILURE)

    base_url = ConfigResolver(
        "server.base_url", "DEEPLOGIC_BASE_URL", DEFAULT_SERVER_BASE_URL
    ).resolve()
    # base_url has a default value, so it won't be None
    return base_url or DEFAULT_SERVER_BASE_URL, api_key


def _require_token() -> tuple[str, str]:
    """Check JWT token is configured for server-side defect check / repair.

    Returns a (base_url, token) tuple.

    Raises:
        typer.Exit: If the token is not configured.
    """
    token = ConfigResolver("server.token", "DEEPLOGIC_TOKEN").resolve()
    if not token:
        console.print("[red]✗ JWT token not configured[/red]")
        console.print("\n  Run: deeplogic-cli config server.token <your-jwt>")
        console.print("  Or:  export DEEPLOGIC_TOKEN=<your-jwt>")
        raise typer.Exit(code=EXIT_FAILURE)

    base_url = ConfigResolver(
        "server.base_url", "DEEPLOGIC_BASE_URL", DEFAULT_SERVER_BASE_URL
    ).resolve()
    return base_url or DEFAULT_SERVER_BASE_URL, token


def _is_bound(project_id: str | None) -> bool:
    """Check if a project ID represents a real binding (not placeholder)."""
    return bool(project_id) and project_id != PLACEHOLDER_UUID


def _get_project_config_path() -> Path:
    """Get the path to the project config file."""
    return Path.cwd() / DEFAULT_CONFIG_DIR / DEFAULT_CONFIG_FILE


def _read_project_config(config_path: Path | None = None) -> dict[str, Any]:
    """Read the project config file, return empty dict if not exists."""
    import yaml

    target_path = config_path or _get_project_config_path()
    if not target_path.exists():
        return {}

    content = read_file_with_encoding_fallback(target_path)
    if content is None:
        return {}

    try:
        data = yaml.safe_load(content)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_project_config(data: dict[str, Any], config_path: Path | None = None) -> None:
    """Write the project config file."""
    import yaml

    target_path = config_path or _get_project_config_path()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # Read existing content to preserve structure
    existing = _read_project_config(target_path)
    merged = {**existing, **data}

    # Write without preserving comments (YAML limitation)
    # For comment preservation, we'd need ruamel.yaml
    with open(target_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(merged, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


def _require_project_id() -> str:
    """Check project is bound, return project_id or exit.

    Returns:
        The project UUID string.

    Raises:
        typer.Exit: If no project is bound.
    """
    config = _read_project_config()
    project = config.get("project", {})
    project_id = project.get("id") if isinstance(project, dict) else None

    if not _is_bound(project_id):
        console.print("[red]✗ No project bound to current directory[/red]")
        console.print("\n  Run: deeplogic-cli project create <name>")
        console.print("  Or:  deeplogic-cli project bind <project-id>")
        console.print(
            "\n[dim](These commands are hidden from --help. "
            "See README 'Artifact Version Management' for details.)[/dim]"
        )
        raise typer.Exit(code=EXIT_FAILURE)

    return str(project_id)


def _mask_api_key(api_key: str) -> str:
    """Mask API key for display: show first 4 and last 4 chars."""
    if len(api_key) <= 8:
        return "***"
    return f"{api_key[:4]}...{api_key[-4:]}"


def _build_bind_help() -> str:
    """Build the help text for 'project bind' with the live server base URL.

    The platform URL is resolved from the current config so users can find
    the project ID at the exact server they're configured to use.
    """
    base_url = ConfigResolver(
        "server.base_url", "DEEPLOGIC_BASE_URL", DEFAULT_SERVER_BASE_URL
    ).resolve()
    return (
        "Bind an existing remote project to local config.\n"
        "\n"
        "This command links your local directory to an existing project on the\n"
        "deeplogic server by saving the project ID to .deeplogic/inspect_config.yaml.\n"
        "\n"
        "To find your project ID:\n"
        f"    1. Open the deeplogic platform at: {base_url}\n"
        "    2. Navigate to the project you want to bind\n"
        '    3. Click "Edit Project" and copy the project ID\n'
        "\n"
        "Example:\n"
        "    deeplogic-cli project bind 156d05db-..."
    )


# Create Typer app for project commands
project_app = typer.Typer(
    name="project",
    help="Project version management (subcommands hidden, see README)",
    no_args_is_help=True,
)


@project_app.command("create", hidden=True)
def create_project(
    name: str = typer.Argument(..., help="Project name"),
    description: str = typer.Option(
        None,
        "--description",
        "-d",
        help="Project description",
    ),
) -> None:
    """Create a new remote project and bind it locally.

    This command:
    1. Creates a new project on the deeplogic server
    2. Saves the project ID to local .deeplogic/inspect_config.yaml

    Example:
        deeplogic-cli project create my-agent
        deeplogic-cli project create my-agent -d "AI assistant for X"
    """
    base_url, api_key = _require_api_key()

    console.print(f"Creating project [cyan]{name}[/]...")

    client = DeeplogicClient(base_url, api_key)
    try:
        result = client.create_project(name, description)
    except AuthenticationError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None
    except NetworkError as e:
        console.print(f"[red]✗ Network error: {e}[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None
    except APIError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None

    project_id = result.get("project_id") or result.get("id")
    if not project_id:
        console.print("[red]✗ Server returned no project ID[/red]")
        raise typer.Exit(code=EXIT_FAILURE)

    # Update local config
    config = _read_project_config()
    if "project" not in config:
        config["project"] = {}
    config["project"]["id"] = project_id
    config["project"]["name"] = name
    _write_project_config(config)

    console.print(f"[green]✓[/] Created project [cyan]{name}[/] (id: {project_id})")
    console.print("\n[dim]Next steps:[/]")
    console.print("[dim]  1. Edit .deeplogic/inspect_config.yaml to configure artifacts[/]")
    console.print("[dim]  2. Run 'deeplogic-cli project push -m \"message\"' to upload[/]")


@project_app.command("bind", help=_build_bind_help(), hidden=True)
def bind_project(
    project_id: str = typer.Argument(..., help="Project UUID to bind"),
) -> None:
    """Bind an existing remote project to local config."""
    # Validate UUID format
    if not _UUID_RE.match(project_id):
        console.print(f"[red]✗ Invalid project ID format: {project_id}[/red]")
        console.print("  Expected UUID format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
        raise typer.Exit(code=EXIT_FAILURE)

    base_url, api_key = _require_api_key()

    # Verify project exists and fetch its authoritative name (optional but helpful)
    console.print(f"Verifying project [cyan]{project_id[:8]}...[/]...")

    client = DeeplogicClient(base_url, api_key)
    server_name = None
    try:
        result = client.get_project(project_id)
        server_name = result.get("name")
    except ProjectNotFoundError:
        console.print(f"[red]✗ Project not found: {project_id}[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None
    except AuthenticationError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None
    except NetworkError as e:
        console.print(f"[yellow]![/yellow] Network error during verification: {e}")
        console.print("[yellow]![/yellow] Binding anyway (project ID will be validated on push)")
    except APIError:
        # Other API errors - continue with binding
        pass

    # Update local config (id + authoritative name from server)
    config = _read_project_config()
    if "project" not in config:
        config["project"] = {}
    config["project"]["id"] = project_id
    if server_name:
        config["project"]["name"] = str(server_name)
    else:
        # Could not fetch the name; clear any stale cached name from a
        # previous project so status doesn't show a misleading one.
        config["project"]["name"] = ""
    _write_project_config(config)

    console.print(f"[green]✓[/] Bound project {project_id}")
    if server_name:
        console.print(f"  Name: [cyan]{server_name}[/]")
    console.print("\n[dim]Next steps:[/]")
    console.print("[dim]  1. Edit .deeplogic/inspect_config.yaml to configure artifacts[/]")
    console.print("[dim]  2. Run 'deeplogic-cli project push -m \"message\"' to upload[/]")


def _print_source_group(label: str, files: list[str]) -> None:
    """Print one source group (Prompts/Tools/Skills) with count and file paths.

    Args:
        label: Category label (e.g. "Prompts").
        files: Resolved absolute paths of files to scan.
    """
    # Show paths relative to cwd when possible, fall back to absolute
    rel_paths: list[str] = []
    for f in files:
        try:
            rel_paths.append(str(Path(f).relative_to(Path.cwd())))
        except ValueError:
            rel_paths.append(f)

    noun = "file" if len(rel_paths) == 1 else "files"
    console.print(f"  {label}: {len(rel_paths)} {noun}")
    for p in rel_paths:
        console.print(f"    [dim]- {p}[/dim]")


@project_app.command("status", hidden=True)
def project_status() -> None:
    """Show current project status and configuration.

    Displays:
    - Project name and ID (if bound)
    - API key status (masked)
    - Server URL
    - Local source files configured to scan & push (from inspect_config.yaml)
    """
    config = _read_project_config()

    # Resolve server config once; reused by both the project name fetch and the
    # Server section below.
    base_url = ConfigResolver(
        "server.base_url", "DEEPLOGIC_BASE_URL", DEFAULT_SERVER_BASE_URL
    ).resolve()
    api_key = ConfigResolver("server.api_key", "DEEPLOGIC_API_KEY").resolve()

    # Project info
    project = config.get("project", {})
    project_id = project.get("id") if isinstance(project, dict) else None
    project_name = project.get("name") if isinstance(project, dict) else None

    console.print("\n[bold]Project[/]")
    if _is_bound(project_id):
        console.print(f"  ID:   [cyan]{project_id}[/]")

        # The local name can be stale: 'bind' never writes one, and the name
        # may have been changed on the platform. Fetch the authoritative name
        # from the server when possible, falling back to the cached local value.
        display_name = project_name
        name_is_cached = False
        if api_key:
            try:
                client = DeeplogicClient(base_url or DEFAULT_SERVER_BASE_URL, api_key)
                server_name = client.get_project(str(project_id)).get("name")
                if server_name:
                    display_name = str(server_name)
            except (AuthenticationError, NetworkError, APIError, ProjectNotFoundError):
                name_is_cached = True

        if display_name:
            cached_suffix = " [dim](cached)[/]" if name_is_cached else ""
            console.print(f"  Name: [cyan]{display_name}[/]{cached_suffix}")
    else:
        console.print("  [yellow]Not bound (run 'project create' or 'project bind')[/]")

    # Server info
    console.print("\n[bold]Server[/]")
    console.print(f"  URL: [dim]{base_url}[/]")

    if api_key:
        console.print(f"  API Key: [green]✓ configured[/] ({_mask_api_key(api_key)})")
    else:
        console.print("  API Key: [red]✗ not set[/]")

    # Sources: local files that would be scanned & pushed
    console.print("\n[bold]Sources[/]")
    console.print(f"  [dim]Config: {DEFAULT_CONFIG_DIR}/{DEFAULT_CONFIG_FILE}[/dim]")

    # Resolve actual files the same way `push` does (expands skill directories).
    # These are source files, NOT uploaded artifacts — the real artifact count
    # lives on the server (see 'project log' / 'project show').
    resolved = None
    resolve_error: Exception | None = None
    try:
        loader = InspectConfigLoader(require_project_id=False)
        resolved = loader.load()
    except Exception as e:  # noqa: BLE001 - fall back to raw config for display
        resolve_error = e

    if resolved is not None:
        groups = [
            ("Prompts", resolved.get("prompts") or []),
            ("Tools", resolved.get("tools") or []),
            ("Skills", resolved.get("skills") or []),
        ]
        if any(files for _, files in groups):
            for label, files in groups:
                if files:
                    _print_source_group(label, files)
        else:
            console.print("  [dim]No files configured[/]")
            console.print(
                f"  Edit {DEFAULT_CONFIG_DIR}/{DEFAULT_CONFIG_FILE} "
                "to add prompts, tools, and skills"
            )
    else:
        # Fallback: config exists but files can't be resolved (e.g. missing on disk)
        prompts = config.get("prompts", []) or []
        tools = config.get("tools", []) or []
        skills = config.get("skills", []) or []

        def _count(entries: Any) -> int:
            return len(entries) if isinstance(entries, list) else 0

        if _count(prompts) or _count(tools) or _count(skills):
            console.print(f"  [yellow]![/] Cannot resolve source files: {resolve_error}")
            if _count(prompts):
                console.print(f"  Prompts: {_count(prompts)}")
            if _count(tools):
                console.print(f"  Tools:   {_count(tools)}")
            if _count(skills):
                console.print(f"  Skills:  {_count(skills)}")
        else:
            console.print("  [dim]No files configured[/]")
            console.print(
                f"  Edit {DEFAULT_CONFIG_DIR}/{DEFAULT_CONFIG_FILE} "
                "to add prompts, tools, and skills"
            )

    console.print()


@project_app.command("push", hidden=True)
def push_artifacts(
    message: str = typer.Option(
        None,
        "-m",
        "--message",
        help="Version commit message",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
) -> None:
    """Scan artifacts and push to remote project.

    This command:
    1. Reads artifact paths from .deeplogic/inspect_config.yaml
    2. Packs artifacts directly from the configured paths
    3. Packs artifacts (prompts, tools, skills)
    4. Uploads to the deeplogic server
    5. Creates a new version with the provided message

    The server automatically detects changes and only creates new versions
    for modified artifacts, reusing existing versions for unchanged ones.

    Example:
        deeplogic-cli project push -m "Add new tool"
    """
    base_url, api_key = _require_api_key()
    project_id = _require_project_id()

    # Import artifact processing utilities

    # Load config to get artifact paths
    try:
        loader = InspectConfigLoader(require_project_id=False)
        artifacts = loader.load()
    except Exception as e:
        console.print(f"[red]✗ Failed to load config: {e}[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None

    prompt_files = artifacts.get("prompts", [])
    tool_files = artifacts.get("tools", [])
    skill_files = artifacts.get("skills", [])

    if not prompt_files and not tool_files and not skill_files:
        console.print("[yellow]No artifacts found to upload[/]")
        raise typer.Exit()

    # Pack artifacts directly from the configured file paths. We intentionally
    # skip the ScannerAgent (local-LLM) here: inspect_config.yaml already
    # declares the artifact paths, so the files can be packed deterministically
    # without a slow (multi-minute, token-heavy) LLM scan.
    from deeplogic_cli.utils.artifact_packer import ArtifactPacker

    console.print("\n[bold]Packing artifacts...[/]")
    console.print(f"  Prompts: {len(prompt_files)}")
    console.print(f"  Tools:   {len(tool_files)}")
    console.print(f"  Skills:  {len(skill_files)}")

    try:
        packer = ArtifactPacker(
            prompts=prompt_files,
            tools=tool_files,
            skills=skill_files,
        )
        packed = packer.pack()
    except Exception as e:
        console.print(f"[red]✗ Failed to pack artifacts: {e}[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None

    # Generate default message if not provided
    if not message:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        message = f"Update at {timestamp}"

    console.print("\n[bold]Uploading to server...[/]")
    client = DeeplogicClient(base_url, api_key)

    try:
        result = client.upload_artifacts(
            project_id=project_id,
            prompt_content=packed.get("prompt_content"),
            tools_schema=packed.get("tools_schema"),
            skill_file=packed.get("skill_file"),
            message=message,
        )
    except AuthenticationError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None
    except NetworkError as e:
        console.print(f"[red]✗ Network error: {e}[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None
    except APIError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None

    # Display results
    version_id = result.get("version_id") or result.get("id")
    if version_id:
        console.print(f"[green]✓[/] Created version [cyan]{version_id}[/]")

    # Show packed artifact counts (from the config-declared paths)
    if prompt_files:
        console.print(f"  Prompts: {len(prompt_files)}")
    if tool_files:
        console.print(f"  Tools:   {len(tool_files)}")
    if skill_files:
        console.print(f"  Skills:  {len(skill_files)}")

    console.print()


@project_app.command("log", hidden=True)
def version_log(
    page: int = typer.Option(1, "--page", "-p", help="Page number"),
    size: int = typer.Option(10, "--size", "-s", help="Page size (max 100)"),
) -> None:
    """List project version history.

    Shows a table of versions with their creation time and commit message.

    Example:
        deeplogic-cli project log
        deeplogic-cli project log -p 2 -s 20
    """
    base_url, api_key = _require_api_key()
    project_id = _require_project_id()

    client = DeeplogicClient(base_url, api_key)

    try:
        result = client.list_versions(project_id, page=page, size=size)
    except AuthenticationError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None
    except ProjectNotFoundError:
        console.print(f"[red]✗ Project not found: {project_id}[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None
    except NetworkError as e:
        console.print(f"[red]✗ Network error: {e}[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None
    except APIError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None

    versions = result.get("items", []) or result.get("versions", [])

    if not versions:
        console.print("[yellow]No versions found[/]")
        raise typer.Exit()

    # Create table
    table = Table(title=f"[bold]Version History[/] (page {page})", border_style="blue")
    table.add_column("Version", style="cyan", no_wrap=True)
    table.add_column("Created", style="white")
    table.add_column("Message", style="white")

    for v in versions:
        version_id = v.get("id") or v.get("version_id", "")

        created = v.get("created_at") or v.get("created", "")
        if created:
            # Parse ISO timestamp and format
            try:
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                created = dt.strftime("%Y-%m-%d %H:%M")
            except ValueError:
                pass

        msg = v.get("message") or ""
        if len(msg) > 40:
            msg = msg[:37] + "..."

        table.add_row(version_id, created, msg)

    console.print(table)

    # Show pagination info
    total = result.get("total", 0)
    if total:
        total_pages = (total + size - 1) // size
        console.print(f"\n[dim]Total: {total} versions, page {page}/{total_pages}[/]")


@project_app.command("show", hidden=True)
def show_version(
    version_id: str = typer.Argument(..., help="Version UUID (full or prefix)"),
    full: bool = typer.Option(False, "--full", "-f", help="Show full artifact content"),
) -> None:
    """Show details of a specific version.

    Displays artifact counts, creation time, and commit message.
    Use --full to show detailed artifact content.

    Example:
        deeplogic-cli project show fe57740b
        deeplogic-cli project show fe57740b --full
    """
    base_url, api_key = _require_api_key()
    project_id = _require_project_id()

    client = DeeplogicClient(base_url, api_key)

    # Resolve prefix to full UUID if needed
    resolved_id = version_id
    if not _UUID_RE.match(version_id):
        console.print(f"Resolving version prefix [cyan]{version_id}[/]...")
        try:
            result = client.list_versions(project_id, page=1, size=100)
        except AuthenticationError as e:
            console.print(f"[red]✗ {e}[/red]")
            raise typer.Exit(code=EXIT_FAILURE) from None
        except ProjectNotFoundError:
            console.print(f"[red]✗ Project not found: {project_id}[/red]")
            raise typer.Exit(code=EXIT_FAILURE) from None
        except NetworkError as e:
            console.print(f"[red]✗ Network error: {e}[/red]")
            raise typer.Exit(code=EXIT_FAILURE) from None
        except APIError as e:
            console.print(f"[red]✗ {e}[/red]")
            raise typer.Exit(code=EXIT_FAILURE) from None

        versions = result.get("items", []) or result.get("versions", [])
        matches = []
        for v in versions:
            vid = v.get("id") or v.get("version_id", "")
            if vid.startswith(version_id):
                matches.append(vid)

        if not matches:
            console.print(f"[red]✗ No version matches prefix: {version_id}[/red]")
            raise typer.Exit(code=EXIT_FAILURE)
        if len(matches) > 1:
            console.print(
                f"[red]✗ Ambiguous prefix: {len(matches)} versions match. "
                f"Use a longer prefix.[/red]"
            )
            raise typer.Exit(code=EXIT_FAILURE)
        resolved_id = matches[0]
        console.print(f"  [dim]Resolved to {resolved_id}[/dim]")

    try:
        result = client.get_version(project_id, resolved_id)
    except AuthenticationError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None
    except ProjectNotFoundError:
        console.print(f"[red]✗ Version not found: {resolved_id}[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None
    except NetworkError as e:
        console.print(f"[red]✗ Network error: {e}[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None
    except APIError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None

    # Display version details
    console.print()
    console.print(f"[bold]Version:[/] {resolved_id}")

    created = result.get("created_at") or result.get("created", "")
    if created:
        try:
            dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            console.print(f"[bold]Created:[/] {dt.strftime('%Y-%m-%d %H:%M:%S')}")
        except ValueError:
            console.print(f"[bold]Created:[/] {created}")

    message = result.get("message")
    if message:
        console.print(f"[bold]Message:[/] {message}")

    # Fetch concrete artifact content via the artifacts endpoint
    console.print("\n[bold]Artifacts:[/]")
    try:
        artifacts_result = client.get_project_artifacts(project_id, resolved_id)
    except (AuthenticationError, NetworkError, APIError):
        artifacts_result = None

    if isinstance(artifacts_result, dict):
        prompts = artifacts_result.get("prompts") or []
        tools = artifacts_result.get("tools") or []
        skills = artifacts_result.get("skills") or []

        # Count tools from schema_content
        tool_count = 0
        for t in tools:
            schema_content = t.get("schema_content")
            try:
                arr = (
                    json.loads(schema_content)
                    if isinstance(schema_content, str)
                    else schema_content
                )
                if isinstance(arr, list):
                    tool_count += len(arr)
            except (json.JSONDecodeError, TypeError):
                tool_count += 1

        # Default: show counts only
        if not full:
            if prompts:
                console.print(f"  Prompts: {len(prompts)}")
            if tool_count:
                console.print(f"  Tools:   {tool_count}")
            if skills:
                console.print(f"  Skills:  {len(skills)}")
        else:
            # --full: show detailed content
            if prompts:
                console.print(f"  [bold]Prompts[/] ({len(prompts)}):")
                for p in prompts:
                    name = p.get("name") or p.get("id", "?")
                    content = p.get("content") or ""
                    preview = content[:80].replace("\n", " ")
                    if len(content) > 80:
                        preview += "..."
                    console.print(f"    - {name}: {preview}")
            if tools:
                console.print(f"  [bold]Tools[/] ({tool_count}):")
                for t in tools:
                    name = t.get("name") or t.get("id", "?")
                    schema_content = t.get("schema_content")
                    console.print(f"    - {name}")
                    # Show each tool definition
                    try:
                        arr = (
                            json.loads(schema_content)
                            if isinstance(schema_content, str)
                            else schema_content
                        )
                        if isinstance(arr, list):
                            for tool_def in arr:
                                fn = tool_def.get("function", {})
                                fn_name = fn.get("name", "?")
                                fn_desc = (fn.get("description") or "")[:60]
                                console.print(f"        • {fn_name}: {fn_desc}")
                    except (json.JSONDecodeError, TypeError):
                        pass
            if skills:
                console.print(f"  [bold]Skills[/] ({len(skills)}):")
                for s in skills:
                    name = s.get("skill_name") or s.get("name") or s.get("id", "?")
                    console.print(f"    - {name}")
    else:
        # Fallback: display artifact counts from version refs
        artifacts = result.get("artifacts", [])
        if isinstance(artifacts, list):
            prompt_count = sum(1 for a in artifacts if a.get("artifact_type") == "prompt")
            skill_count = sum(1 for a in artifacts if a.get("artifact_type") == "skill")
            # For tools_schema, count actual tool definitions from schema_content
            tool_count = 0
            for a in artifacts:
                if a.get("artifact_type") == "tools_schema":
                    schema_content = a.get("schema_content")
                    if schema_content:
                        try:
                            tools_arr = (
                                json.loads(schema_content)
                                if isinstance(schema_content, str)
                                else schema_content
                            )
                            if isinstance(tools_arr, list):
                                tool_count += len(tools_arr)
                        except (json.JSONDecodeError, TypeError):
                            tool_count += 1  # fallback: count as 1 artifact
                    else:
                        tool_count += 1  # no content, count as 1 artifact
            if prompt_count:
                console.print(f"  Prompts: {prompt_count}")
            if tool_count:
                console.print(f"  Tools:   {tool_count}")
            if skill_count:
                console.print(f"  Skills:  {skill_count}")
        elif isinstance(artifacts, dict):
            prompt = artifacts.get("prompt", {})
            if prompt:
                hash_val = prompt.get("hash", "N/A")
                status = prompt.get("status", "")
                console.print(f"  Prompt: {hash_val[:12]}... ({status})")

            tools = artifacts.get("tools", {})
            if tools:
                hash_val = tools.get("hash", "N/A")
                status = tools.get("status", "")
                console.print(f"  Tools:  {hash_val[:12]}... ({status})")

            skill = artifacts.get("skill", {})
            if skill:
                hash_val = skill.get("hash", "N/A")
                status = skill.get("status", "")
                console.print(f"  Skill:  {hash_val[:12]}... ({status})")

    console.print()


# ===========================================================================
# Helpers for server-side defect check / repair
# ===========================================================================


def _find_record_for_task(records: dict, task_id: str) -> dict | None:
    """Find the defect-check record for a specific triggered task.

    The records list is newest-first and contains historical entries too, so
    polling must match on result_id (== the task_id returned by the run
    endpoint) instead of taking the first finished record — otherwise a still-
    running new check makes the poller return the previous round's result.
    """
    items = records.get("items") or records.get("list") or records.get("records") or []
    if not isinstance(items, list):
        return None
    finished = {"completed", "failed"}
    for item in items:
        if str(item.get("result_id") or "") != task_id:
            continue
        status = (item.get("status") or "").lower()
        if status in finished:
            return item
        return None  # found our task but still running — keep polling
    return None


def _find_latest_finished_record(records: dict) -> dict | None:
    """Find the most recent finished defect-check record.

    A record is "finished" when its status is 'completed' OR 'failed' — both
    mean the server no longer runs, so a poller can stop waiting. Items with
    status 'running' / 'created' / 'pending' are skipped.

    The records endpoint returns a list where each item carries a result_id and
    status. We pick the newest finished one.
    """
    items = records.get("items") or records.get("list") or records.get("records") or []
    if not isinstance(items, list):
        return None
    finished = {"completed", "failed"}
    for item in items:
        status = (item.get("status") or "").lower()
        if status in finished:
            return item
    return None


def _normalize_result_for_display(result: dict) -> dict:
    """Flatten the server detail response into a simple display structure.

    Returns {summary, modules:{qds,qdt,qdp,cross}} where each module exposes
    aggregate counts only (kept simple for the CLI console output).
    """
    modules = result.get("modules") or {}
    summary = result.get("summary") or {}

    def _count(module: dict, key: str) -> int:
        items = module.get(key) or []
        return len(items) if isinstance(items, list) else 0

    qds = modules.get("qds") or {}
    qdt = modules.get("qdt") or {}
    qdp = modules.get("qdp") or {}
    cross = modules.get("cross") or {}

    return {
        "summary": {
            "totalScore": summary.get("totalScore"),
            "gateResult": summary.get("gateResult"),
            "totalDefects": summary.get("totalDefects"),
            "p0": summary.get("p0Count") or 0,
            "p1": summary.get("p1Count") or 0,
            "p2": summary.get("p2Count") or 0,
        },
        "modules": {
            "qds": {
                "executed": qds.get("executed"),
                "score": qds.get("score"),
                "grade": qds.get("grade"),
                "defectCount": qds.get("defectCount"),
                "skillCount": _count(qds, "skills"),
            },
            "qdt": {
                "executed": qdt.get("executed"),
                "score": qdt.get("score"),
                "defectCount": qdt.get("defectCount"),
                "toolCount": _count(qdt, "tools"),
            },
            "qdp": {
                "executed": qdp.get("executed"),
                "score": qdp.get("score"),
                "grade": qdp.get("grade"),
                "defectCount": qdp.get("defectCount"),
            },
            "cross": {
                "executed": cross.get("executed"),
                "enabled": cross.get("enabled"),
                "status": cross.get("status"),
            },
        },
        "raw": result,
    }


@project_app.command("check", hidden=True)
def check_defects(
    level: str = typer.Option("L1", "--level", help="Check level: L1/L2/L3"),
    project_id: str | None = typer.Option(
        None, "--project-id", help="Project UUID (default: bound project)"
    ),
    result_id: str | None = typer.Option(
        None, "--result-id", help="Skip run and print an existing result"
    ),
    interval: float = typer.Option(3.0, "--interval", help="Poll interval (s)"),
    timeout: float = typer.Option(600.0, "--timeout", help="Poll timeout (s)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show per-defect details"),
) -> None:
    """Run a server-side defect check and print the summary.

    This triggers the deeplogic SaaS defect-check engine (QDS/QDT/QDP) on the
    server, polls to completion, then prints the report. Unlike `inspect`, this
    does NOT run a local LLM — it is the authoritative server-side check.
    """
    base_url, token = _require_token()
    pid = project_id or _require_project_id()
    client = DeeplogicClient(base_url, api_key="", token=token)

    console.print("[bold]Running server-side defect check[/]")
    console.print(f"  Project: {pid}")
    console.print(f"  Level:   {level}")

    # Resolve the result to display
    if result_id:
        console.print(f"  Result:  {result_id} (existing)")
    else:
        try:
            run_result = client.run_defect_check(pid, level=level)
        except (AuthenticationError, NetworkError, APIError) as e:
            console.print(f"[red]✗ {e}[/red]")
            raise typer.Exit(code=EXIT_FAILURE) from None

        task_id = run_result.get("task_id") or run_result.get("id")
        console.print(f"  Task:    {task_id} (running)")
        console.print(f"  Polling every {interval}s up to {timeout}s...")

        import time as _time

        deadline = _time.time() + timeout
        result_id = None
        result_status = None
        while _time.time() < deadline:
            _time.sleep(interval)
            try:
                records = client.get_defect_check_records(pid)
            except (AuthenticationError, NetworkError, APIError):
                continue
            # Only stop when the record for the task we triggered reaches a
            # finished status. Matching on task_id is essential: while the new
            # check is still running, the records list already contains older
            # completed entries, and grabbing "the first finished record"
            # would return a stale previous-round result.
            matched = _find_record_for_task(records, str(task_id)) if task_id else None
            if matched:
                result_id = matched.get("result_id")
                result_status = (matched.get("status") or "").lower()
                break

        if not result_id:
            console.print("[red]✗ Timed out waiting for defect check[/red]")
            raise typer.Exit(code=EXIT_FAILURE) from None
        console.print(f"  Result:  {result_id} ({result_status})")

    try:
        detail = client.get_defect_check_result(pid, str(result_id))
    except (AuthenticationError, NetworkError, APIError) as e:
        console.print(f"[red]✗ {e}[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None

    display = _normalize_result_for_display(detail)
    summary = display["summary"]
    modules = display["modules"]

    console.print()
    console.print("[bold]Defect Check Summary[/]")
    console.print(f"  Total score : {summary['totalScore']}")
    console.print(f"  Gate result : {summary['gateResult']}")
    console.print(
        f"  Total defects: {summary['totalDefects']} "
        f"(P0: {summary['p0']}, P1: {summary['p1']}, P2: {summary['p2']})"
    )

    qds, qdt, qdp, cross = modules["qds"], modules["qdt"], modules["qdp"], modules["cross"]
    console.print(
        f"  QDS (skills): {qds['score']} ({qds['grade']}) — {qds['defectCount']} defects / {qds['skillCount']} skills"
    )
    console.print(
        f"  QDT (tools) : {qdt['score']} — {qdt['defectCount']} defects / {qdt['toolCount']} tools"
    )
    if qdp["executed"] is not None:
        console.print(
            f"  QDP (prompt): {qdp['score']} ({qdp['grade']}) — {qdp['defectCount']} defects"
        )
    if cross.get("enabled"):
        console.print(f"  CROSS       : {cross['status']}")

    if verbose:
        raw = display["raw"]
        _print_defect_details(raw)

    # Expose the result_id for downstream chaining.
    console.print(f"\n[dim]Result id: {result_id}[/dim]")


def _print_defect_details(detail: dict) -> None:
    """Print per-defect details for the verbose mode of `project check`."""
    modules = detail.get("modules") or {}
    qds = modules.get("qds") or {}
    qdt = modules.get("qdt") or {}
    qdp = modules.get("qdp") or {}

    for skill in qds.get("skills") or []:
        defects = skill.get("defects") or []
        for d in defects:
            console.print(
                f"  [yellow][QDS][/] {d.get('id')} ({d.get('severity')}) "
                f"{d.get('name')} — {d.get('suggestion')}"
            )
    for tool in qdt.get("tools") or []:
        issues = tool.get("defects") or []
        for d in issues:
            console.print(
                f"  [yellow][QDT][/] {d.get('id')} ({d.get('severity')}) "
                f"{d.get('name')} — {d.get('suggestion')}"
            )
    for d in qdp.get("defects") or []:
        console.print(
            f"  [yellow][QDP][/] {d.get('code')} ({d.get('severity')}) "
            f"{d.get('name')} — {d.get('repair_suggestion') or d.get('suggestion')}"
        )


# @project_app.command("repair", hidden=True)  # Disabled: repair command is closed
def repair_artifacts(
    project_id: str | None = typer.Option(
        None, "--project-id", help="Project UUID (default: bound project)"
    ),
    result_id: str | None = typer.Option(
        None, "--result-id", help="Defect-check result UUID (default: latest completed)"
    ),
    language: str = typer.Option("zh", "--language", help="Repair language zh/en"),
    all_artifacts: bool = typer.Option(False, "--all", help="Repair every defective artifact"),
    skill_id: str | None = typer.Option(
        None, "--skill", help="Repair a single skill by its artifact UUID"
    ),
    tool_index: int | None = typer.Option(None, "--tool", help="Repair a single tool by its index"),
    regenerate: bool = typer.Option(
        False, "--regenerate", help="Force regeneration (ignore cache)"
    ),
) -> None:
    """Fetch repaired artifacts from the server and write them back to local files.

    For each defective artifact, calls the /repaired-* endpoint, then replaces
    the corresponding local file (resolved from .deeplogic/inspect_config.yaml)
    with the returned repairedContent. Use --all to repair everything, or
    --skill/--tool to target specific artifacts.
    """
    base_url, token = _require_token()
    pid = project_id or _require_project_id()
    client = DeeplogicClient(base_url, api_key="", token=token)

    # Resolve the result to repair against.
    if result_id:
        rid = result_id
    else:
        records = client.get_defect_check_records(pid)
        latest = _find_latest_finished_record(records)
        if not latest or (latest.get("status") or "").lower() != "completed":
            console.print("[red]✗ No completed defect check found. Run: project check[/red]")
            raise typer.Exit(code=EXIT_FAILURE) from None
        rid = str(latest.get("result_id"))
    console.print(f"[bold]Repairing project {pid}[/] (result: {rid})")

    # Load local artifact paths.
    from deeplogic_cli.utils.config_loader import InspectConfigLoader

    loader = InspectConfigLoader(require_project_id=False)
    artifacts = loader.load()
    local_prompts = artifacts.get("prompts") or []
    local_tools = artifacts.get("tools") or []
    local_skills = artifacts.get("skills") or []

    detail = client.get_defect_check_result(pid, rid)
    modules = detail.get("modules") or {}
    qds = modules.get("qds") or {}
    qdt = modules.get("qdt") or {}
    qdp = modules.get("qdp") or {}

    written: list[str] = []
    skipped: list[str] = []

    # ---- Skills ----
    skill_name_to_local = _map_skill_names(local_skills)
    for skill in qds.get("skills") or []:
        defects = skill.get("defects") or []
        if not defects:
            continue
        if not (all_artifacts or (skill_id and str(skill.get("skillId")) == str(skill_id))):
            continue
        sid = str(skill.get("skillId"))
        skill_name = _extract_skill_name(skill.get("skillName"))
        local_path = skill_name_to_local.get(skill_name)
        if not local_path:
            console.print(f"  [yellow]⚠[/] No local file for skill '{skill_name}', skip")
            skipped.append(skill_name)
            continue
        try:
            repaired = client.generate_repaired_skill(pid, rid, sid, language, regenerate)
        except (AuthenticationError, NetworkError, APIError) as e:
            console.print(f"  [red]✗ {skill_name}: {e}[/red]")
            skipped.append(skill_name)
            continue
        content = repaired.get("repairedContent")
        if not content:
            console.print(f"  [yellow]⚠[/] {skill_name}: empty repair, skip")
            skipped.append(skill_name)
            continue
        _write_local_file(local_path, content)
        console.print(f"  [green]✓[/] Repaired skill '{skill_name}' -> {local_path}")
        written.append(local_path)

    # ---- Tools (index-based) ----
    tool_defs = _load_tool_definitions(local_tools)
    for tool in qdt.get("tools") or []:
        issues = tool.get("defects") or []
        if not issues:
            continue
        idx = tool.get("toolIndex")
        if idx is None:
            continue
        if not (all_artifacts or (tool_index is not None and int(tool_index) == int(idx))):
            continue
        tool_name = tool.get("toolName")
        local_path = tool_defs.get("path")
        if not local_path:
            console.print("  [yellow]⚠[/] No local tool file, skip")
            skipped.append(str(tool_name))
            continue
        try:
            repaired = client.generate_repaired_tool(pid, rid, int(idx), language, regenerate)
        except (AuthenticationError, NetworkError, APIError) as e:
            console.print(f"  [red]✗ {tool_name}: {e}[/red]")
            skipped.append(str(tool_name))
            continue
        content = repaired.get("repairedContent")
        if not content:
            console.print(f"  [yellow]⚠[/] {tool_name}: empty repair, skip")
            skipped.append(str(tool_name))
            continue
        # NOTE(risk): the server-side /repaired-tool contract is unverified.
        # If repairedContent is a SINGLE repaired tool definition while the
        # local file holds an array of tools, this overwrite loses all other
        # tools. If it is the full repaired file content, this is correct.
        # TODO: confirm the API contract; if single-tool, parse the local
        # array and replace only the item at index `idx` instead.
        # Original content is still recoverable from the .bak written below.
        _write_local_file(local_path, content)
        console.print(f"  [green]✓[/] Repaired tool '{tool_name}' -> {local_path}")
        written.append(local_path)

    # ---- Prompt ----
    qdp_defects = qdp.get("defects") or []
    if qdp_defects and local_prompts:
        if all_artifacts or not (skill_id or tool_index is not None):
            prompt_path: str = local_prompts[0]
            try:
                repaired = client.generate_repaired_prompt(pid, rid, language, regenerate)
            except (AuthenticationError, NetworkError, APIError) as e:
                console.print(f"  [red]✗ prompt: {e}[/red]")
                skipped.append("prompt")
            else:
                content = repaired.get("repairedContent")
                if content:
                    _write_local_file(prompt_path, content)
                    console.print(f"  [green]✓[/] Repaired prompt -> {prompt_path}")
                    written.append(prompt_path)
                else:
                    console.print("  [yellow]⚠[/] prompt: empty repair, skip")
                    skipped.append("prompt")
    elif qdp_defects and not local_prompts:
        console.print("  [yellow]⚠[/] QDP defects found but no local prompt file configured")

    console.print(f"\n[bold]Repair summary:[/] {len(written)} written, {len(skipped)} skipped")
    if skipped:
        console.print(f"  [dim]{skipped}[/dim]")


def _extract_skill_name(skill_name: str | None) -> str:
    """Extract the plain skill name from a server skillName like 'skills_1 (security)'."""
    if not skill_name:
        return ""
    if "(" in skill_name and ")" in skill_name:
        return skill_name.split("(", 1)[1].rsplit(")", 1)[0].strip()
    return skill_name.strip()


def _map_skill_names(local_skills: list[str]) -> dict[str, str]:
    """Build {frontmatter-name: local-path} for the configured local skill files."""
    mapping: dict[str, str] = {}
    for path in local_skills:
        name = _skill_frontmatter_name(path)
        if name:
            mapping[name] = path
    return mapping


def _skill_frontmatter_name(path: str) -> str:
    """Read 'name:' from a SKILL.md frontmatter block."""
    from pathlib import Path

    from deeplogic_cli.utils.config_loader import read_file_with_encoding_fallback

    content = read_file_with_encoding_fallback(Path(path))
    if not content or not content.startswith("---"):
        return Path(path).stem
    end = content.find("\n---", 4)
    if end == -1:
        return Path(path).stem
    front = content[4:end]
    for line in front.splitlines():
        if line.strip().startswith("name:"):
            return line.split(":", 1)[1].strip().strip('"').strip("'")
    return Path(path).stem


def _load_tool_definitions(local_tools: list[str]) -> dict:
    """Return the single local tools file path (server merges into one array)."""
    if not local_tools:
        return {"path": None}
    return {"path": local_tools[0]}


def _write_local_file(path: str, content: str, backup: bool = True) -> None:
    """Atomically write content to a local file, replacing the original.

    When ``backup`` is True (default), the existing target file is first copied
    to ``<path>.bak`` so the original is recoverable before it is overwritten.
    """
    from pathlib import Path

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if backup and target.exists():
        bak = target.with_suffix(target.suffix + ".bak")
        import shutil

        shutil.copy2(target, bak)
    tmp = target.with_suffix(target.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    tmp.replace(target)


@project_app.command("all", hidden=True)
def all_in_one(
    level: str = typer.Option("L1", "--level", help="Check level: L1/L2/L3"),
    message: str = typer.Option(None, "-m", "--message", help="Version commit message for push"),
    project_id: str | None = typer.Option(
        None, "--project-id", help="Project UUID (default: bound project)"
    ),
    interval: float = typer.Option(3.0, "--interval", help="Check poll interval (s)"),
    timeout: float = typer.Option(600.0, "--timeout", help="Check poll timeout (s)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
) -> None:
    """Run the push-and-check workflow in one shot: push -> check.

    This chains two steps:
      1. push   - pack artifacts from inspect_config.yaml and upload.
      2. check  - run the server-side defect check and print the summary.

    Note: the repair step has been removed (repair functionality is disabled).
    """

    # 1. Push (upload artifacts). Uses API key auth.
    console.print("\n[bold cyan]Step 1/2: Push artifacts[/]")
    try:
        push_artifacts(message=message, verbose=verbose)
    except typer.Exit:
        raise

    # 2. Check (server-side defect check). Uses JWT token auth.
    console.print("\n[bold cyan]Step 2/2: Server-side defect check[/]")
    try:
        check_defects(
            level=level,
            project_id=project_id,
            result_id=None,
            interval=interval,
            timeout=timeout,
            verbose=verbose,
        )
    except typer.Exit:
        raise

    console.print("\n[bold green]Workflow complete.[/]")
    console.print("[dim]Run 'deeplogic-cli project check' to re-verify.[/]")
