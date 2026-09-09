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

"""inspect command — Sanityops CLI Tool"""

from __future__ import annotations

import platform
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import anyio
import typer
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from sanityops_cli import __version__
from sanityops_cli.agents.scanner_agent.agent import ScannerAgent
from sanityops_cli.constants.config_defaults import DEFAULT_SERVER_BASE_URL
from sanityops_cli.constants.exit_codes import EXIT_FAILURE
from sanityops_cli.defect_checker.checker import DefectChecker
from sanityops_cli.defect_checker.llm_config import resolve_llm_config
from sanityops_cli.defect_checker.renderer import DefectRenderer
from sanityops_cli.exceptions.base_exceptions import ValidationError
from sanityops_cli.logging.logger import Logger
from sanityops_cli.progress.tracker import ProgressTracker
from sanityops_cli.utils.config_loader import InspectConfigLoader
from sanityops_cli.utils.config_resolver import ConfigResolver

console = Console()
inspect_app = typer.Typer()

#: URL users attach log files to when reporting issues.
ISSUE_URL = "https://github.com/sanityops-org/sanityops-cli/issues"


def _auto_upload(
    project_id: str | None,
    scan_result: Any,
) -> None:
    """Auto upload scanned artifacts to the server.

    Flow:
    - If no API key configured: skip (no-op).
    - If API key configured but no project bound: create a project first,
      then push the artifacts.
    - If API key configured and project bound: push directly.

    Args:
        project_id: Resolved project ID (None if not bound / placeholder).
        scan_result: ScannerAgent result containing skills, tools, prompts.
    """
    from sanityops_cli.api.client import SanityopsClient
    from sanityops_cli.utils.artifact_packer import pack_from_findings

    # No API key configured -> cannot upload, skip silently
    api_key = ConfigResolver("server.api_key", "SANITYOPS_API_KEY").resolve()
    if not api_key:
        console.print("[dim]API key not configured, skip auto upload.[/dim]")
        return

    base_url = (
        ConfigResolver("server.base_url", "SANITYOPS_BASE_URL", DEFAULT_SERVER_BASE_URL).resolve()
        or DEFAULT_SERVER_BASE_URL
    )
    client = SanityopsClient(base_url, api_key)

    # Pack artifacts from scan results
    console.print("\n[bold]Packing artifacts...[/]")
    try:
        packed = pack_from_findings(
            skills=scan_result.skills,
            tools=scan_result.tools,
            prompts=scan_result.prompts,
        )
    except Exception as e:
        console.print(f"[red]✗ Failed to pack artifacts: {escape(str(e))}[/]")
        raise

    if (
        not packed.get("prompt_content")
        and not packed.get("tools_schema")
        and not packed.get("skill_file")
    ):
        console.print("[yellow]No artifacts to upload.[/yellow]")
        return

    # Create a project first if not bound yet
    if not project_id:
        default_name = Path.cwd().name or "my-project"
        console.print(f"\n[bold]Creating new project [cyan]{default_name}[/]...[/]")
        try:
            result = client.create_project(default_name, None)
        except Exception as e:
            console.print(f"[red]✗ Could not create project: {escape(str(e))}[/]")
            console.print("[dim]  Check your SANITYOPS_API_KEY and network connectivity.[/dim]")
            raise

        new_project_id = result.get("project_id")
        if not new_project_id:
            console.print("[red]✗ Server returned no project ID[/]")
            return

        # Persist the new project binding for subsequent pushes
        ConfigResolver.set_project("project.id", new_project_id)
        ConfigResolver.set_project("project.name", default_name)

        project_id = new_project_id
        console.print(f"[green]✓[/] Created project (id: {project_id})")
    else:
        console.print(f"\n[bold]Using existing project: [cyan]{project_id}[/][/")

    # Push artifacts
    message = f"Auto-push at {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    console.print("[bold]Uploading artifacts to server...[/]")
    try:
        result = client.upload_artifacts(
            project_id=project_id,
            prompt_content=packed.get("prompt_content"),
            tools_schema=packed.get("tools_schema"),
            skill_file=packed.get("skill_file"),
            message=message,
        )
    except Exception as e:
        console.print(f"[red]✗ Could not upload artifacts: {escape(str(e))}[/]")
        raise

    version_id = result.get("version_id") or result.get("id")
    if version_id:
        console.print(f"[green]✓[/] Created version [cyan]{version_id}[/]")

    if scan_result.prompts:
        console.print(f"  Prompts: {len(scan_result.prompts)}")
    if scan_result.tools:
        console.print(f"  Tools:   {len(scan_result.tools)}")
    if scan_result.skills:
        console.print(f"  Skills:  {len(scan_result.skills)}")
    console.print()


def _banner_line() -> str:
    """Return a one-line run banner: program version, Python version, platform."""
    return (
        f"sanityops-cli v{__version__} | Python {platform.python_version()} "
        f"| {sys.platform}/{platform.machine()}"
    )


def _report_program_error(
    logger: Logger, step_name: str, error: Exception, *, step_summary_shown: bool = False
) -> None:
    """Print a concise program-error summary and point to the log file.

    In verbose mode the failing step's ``StepContext`` already collapsed to a
    ``✗ {name} ({duration}s)`` line, so the step-error headline is skipped to
    avoid reporting the same failure twice.
    """
    if not step_summary_shown:
        console.print(f"[red]✗ Error in step \"{escape(step_name)}\"[/]")
    console.print(f"  Message: {escape(str(error))}")
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
        console.print(f"[red]✗ Invalid check level: {escape(check_level)} (must be L1/L2/L3)[/red]")
        raise typer.Exit(code=EXIT_FAILURE)

    logger = Logger()
    tracker = ProgressTracker(console, logger, verbose=verbose)

    # Step 1: Load and validate config
    try:
        with tracker.step("Loading configuration..."):
            loader = InspectConfigLoader(config)
            artifacts = loader.load()
    except ValidationError as e:
        console.print(f"[red]✗ Config error: {escape(str(e))}[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None
    except Exception as e:
        _report_program_error(logger, "Loading configuration...", e, step_summary_shown=verbose)
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
    console.print(f"[dim]{_banner_line()}[/dim]")
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
        _report_program_error(logger, "Analyzing artifacts...", e, step_summary_shown=verbose)
        raise typer.Exit(code=EXIT_FAILURE) from None

    if not result.skills and not result.tools and not result.prompts:
        console.print("[yellow]No artifacts found to check.[/yellow]")
        tracker.summary()
        raise typer.Exit()

    # Step 3: Auto upload artifacts after scan completes
    # - If api-key configured and project not bound: create project then push
    # - If api-key configured and project bound: push directly
    try:
        _auto_upload(project_id, result)
    except Exception as e:
        # _auto_upload prints user-friendly error, just continue
        # Upload failure does not block defect check
        logger.debug(f"Auto-upload failed: {e}")

    # Step 4: Run defect check and render (unless skipped)
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
        _report_program_error(logger, "Running defect check...", e, step_summary_shown=verbose)
        raise typer.Exit(code=EXIT_FAILURE) from None

    tracker.summary()
    DefectRenderer(console).render(response)
