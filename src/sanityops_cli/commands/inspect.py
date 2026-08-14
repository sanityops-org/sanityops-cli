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
from sanityops_cli.logging.logger import Logger
from sanityops_cli.progress.tracker import ProgressTracker
from sanityops_cli.utils.config_loader import InspectConfigLoader

console = Console()
inspect_app = typer.Typer()

#: URL users attach log files to when reporting issues.
ISSUE_URL = "https://github.com/sanityops-org/sanityops-cli/issues"


def _report_program_error(logger: Logger, step_name: str, error: Exception) -> None:
    """Print a concise program-error summary and point to the log file."""
    console.print(f"[red]✗ Error in step \"{step_name}\"[/]")
    console.print(f"  Message: {error}")
    console.print(f"\nSee log for details: {logger.get_log_path()}")
    console.print("To report this issue, attach the log file to:")
    console.print(ISSUE_URL)


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

    logger = Logger()
    tracker = ProgressTracker(console, logger, verbose=verbose)

    # Step 1: Load and validate config
    try:
        with tracker.step("Loading configuration..."):
            loader = InspectConfigLoader(config)
            artifacts = loader.load()
    except ValidationError as e:
        console.print(f"[red]✗ Config error: {e}[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None
    except Exception as e:
        _report_program_error(logger, "Loading configuration...", e)
        raise typer.Exit(code=EXIT_FAILURE) from None

    project_id = artifacts["project_id"]
    prompt_files = artifacts["prompts"]
    tool_files = artifacts["tools"]
    skill_files = artifacts["skills"]

    # Display resolved artifacts
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

    # Step 2: Run ScannerAgent analysis
    try:
        with tracker.step("Analyzing artifacts...") as step:
            # Resolve LLM config (config file model section or env vars)
            llm_config = resolve_llm_config(config)

            from sanityops_agent.config import ProviderConfig
            from sanityops_agent.llm.factory import ProviderFactory

            provider_config = ProviderConfig(
                LLM_PROVIDER=llm_config["llm_provider"],
                API_KEY=llm_config["llm_api_key"],
                MODEL_ID=llm_config["llm_model_id"],
                BASE_URL=llm_config["llm_base_url"] or None,
            )
            provider = ProviderFactory.create(provider_config)
            agent = ScannerAgent(
                provider=provider,
                verbose=verbose,
                console=step.console,
                logger=logger,
            )
            result = agent.analyze_files_sync(
                prompts=prompt_files,
                tools=tool_files,
                skills=skill_files,
            )
    except Exception as e:
        _report_program_error(logger, "Analyzing artifacts...", e)
        raise typer.Exit(code=EXIT_FAILURE) from None

    if not result.skills and not result.tools and not result.prompts:
        console.print("[yellow]No artifacts found to check.[/yellow]")
        tracker.summary()
        raise typer.Exit()

    # Step 3: Run defect check and render (unless skipped)
    if skip_defect_check:
        console.print("[dim]Defect check skipped (--skip-defect-check).[/dim]")
        tracker.summary()
        raise typer.Exit()

    async def run_check():
        checker = DefectChecker(llm_config)
        return await checker.check(result, check_level=check_level)

    try:
        with tracker.step("Running defect check..."):
            response = anyio.run(run_check)
    except Exception as e:
        _report_program_error(logger, "Running defect check...", e)
        raise typer.Exit(code=EXIT_FAILURE) from None

    tracker.summary()
    DefectRenderer(console).render(response)
