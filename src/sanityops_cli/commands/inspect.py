"""inspect command — Sanityops CLI Tool"""

import anyio
import typer
from rich.console import Console
from rich.table import Table

from sanityops_cli.agents.scanner_agent.agent import ScannerAgent
from sanityops_cli.constants.exit_codes import EXIT_FAILURE
from sanityops_cli.defect_checker.checker import DefectChecker
from sanityops_cli.defect_checker.llm_config import resolve_llm_config
from sanityops_cli.defect_checker.renderer import DefectRenderer
from sanityops_cli.exceptions.base_exceptions import ValidationError
from sanityops_cli.utils.config_loader import InspectConfigLoader

console = Console()
inspect_app = typer.Typer()


@inspect_app.callback(invoke_without_command=True)
def inspect(
    ctx: typer.Context,
    config: str | None = typer.Option(
        None,
        "--config", "-c",
        help="Path to inspect_config.yaml. If omitted, looks for .sanityops/inspect_config.yaml in cwd.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
    check_level: str = typer.Option(
        "L2",
        "--check-level",
        help="Defect check level: L1 (fast), L2 (standard), L3 (deep).",
    ),
    skip_defect_check: bool = typer.Option(
        False,
        "--skip-defect-check",
        help="Skip the defect check step and only run artifact analysis.",
    ),
):
    """Inspect and defect-check the configured artifacts."""
    if check_level not in {"L1", "L2", "L3"}:
        console.print(f"[red]✗ Invalid check level: {check_level} (must be L1/L2/L3)[/red]")
        raise typer.Exit(code=EXIT_FAILURE)

    # Step 1: Load and validate config
    try:
        loader = InspectConfigLoader(config)
        artifacts = loader.load()
    except ValidationError as e:
        console.print(f"[red]✗ Config error: {e}[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None

    project_id = artifacts["project_id"]
    prompt_files = artifacts["prompts"]
    tool_files = artifacts["tools"]
    skill_files = artifacts["skills"]

    # Step 2: Display resolved artifacts
    table = Table(title="[bold]Inspect Artifacts[/]", border_style="blue")
    table.add_column("Type", style="bold cyan", no_wrap=True)
    table.add_column("Absolute Path", style="white")
    for f in prompt_files:
        table.add_row("Prompt", f)
    for f in tool_files:
        table.add_row("Tool", f)
    for f in skill_files:
        table.add_row("Skill", f)
    console.print(table)
    console.print(f"[dim]Project ID: {project_id}[/dim]")
    console.print(
        f"[dim]Total: {len(prompt_files)} prompts, "
        f"{len(tool_files)} tools, {len(skill_files)} skills[/dim]\n"
    )

    # Step 3: Run ScannerAgent analysis
    try:
        # Pass config path for model section resolution
        # Use the same path that InspectConfigLoader resolved
        llm_config = resolve_llm_config(config)
    except Exception as e:
        console.print(f"[red]✗ Failed to resolve LLM configuration: {e}[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None

    from sanityops_agent.config import ProviderConfig
    from sanityops_agent.llm.factory import ProviderFactory

    # Construct ProviderConfig from resolved llm_config (config file or env vars)
    provider_config = ProviderConfig(
        LLM_PROVIDER=llm_config["llm_provider"],
        API_KEY=llm_config["llm_api_key"],
        MODEL_ID=llm_config["llm_model_id"],
        BASE_URL=llm_config["llm_base_url"] or None,
    )
    provider = ProviderFactory.create(provider_config)
    agent = ScannerAgent(provider=provider, verbose=verbose)
    result = agent.analyze_files_sync(
        prompts=prompt_files,
        tools=tool_files,
        skills=skill_files,
    )

    if not result.skills and not result.tools and not result.prompts:
        console.print("[yellow]No artifacts found to check.[/yellow]")
        raise typer.Exit()

    # Step 4: Run defect check and render (unless skipped)
    if skip_defect_check:
        console.print("[dim]Defect check skipped (--skip-defect-check).[/dim]")
        raise typer.Exit()

    async def run_check():
        checker = DefectChecker(llm_config)
        return await checker.check(result, check_level=check_level)

    try:
        response = anyio.run(run_check)
    except Exception as e:
        console.print(f"[red]✗ Defect check failed: {e}[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None

    DefectRenderer(console).render(response)
