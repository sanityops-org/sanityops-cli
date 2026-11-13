"""inspect command — deeplogic CLI Tool.

Skill-based two-agent pipeline (design 2026-11-05):
  Step 1  QC lint (17-item checklist v2, program channel + hybrid pre-screen)
  Step 2  ExtractAgent (skill pre-inspect-extract, store_artifacts protocol)
  Step 3  InspectAgent (skill deeplogic-inspect-lite, seven-stage flow)
  Step 4  CLI render + persist + exit code matrix (design §9)
"""

from __future__ import annotations

import inspect as inspect_mod
import os
from contextlib import nullcontext
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from time import perf_counter

import typer
import yaml
from rich.console import Console
from rich.status import Status
from rich.table import Table
from rich.text import Text

from deeplogic_cli.code_contract_checker.models import DefectStatus
from deeplogic_cli.constants.config_defaults import DEFAULT_SERVER_BASE_URL
from deeplogic_cli.constants.exit_codes import EXIT_DEFECTS_FOUND, EXIT_FAILURE, EXIT_SUCCESS
from deeplogic_cli.exceptions.base_exceptions import ValidationError
from deeplogic_cli.inspect_pipeline.token_estimator import DEFAULT_CONTEXT_WINDOW, estimate_tokens
from deeplogic_cli.logging import LogConfig, LogManager, load_log_config
from deeplogic_cli.utils.config_loader import (
    InspectConfigLoader,
    read_file_with_encoding_fallback,
)
from deeplogic_cli.utils.config_resolver import ConfigResolver
from deeplogic_cli.utils.llm_config import resolve_llm_config

console = Console()
inspect_app = typer.Typer()

#: Per-request LLM timeout. The aidynamic-agent providers default to 120s,
#: which is too short for calls that emit a whole 6KB chunk in one response.
DEFAULT_LLM_TIMEOUT = 600.0

#: Design §6.6: hard artifact-manifest cap before ExtractAgent; split the
#: inspect config into multiple runs beyond this.
MAX_MANIFEST_FILES = 50

#: Design §6.6 effective token-budget floors per agent.
EXTRACT_TOKEN_BUDGET_FLOOR = 200_000
INSPECT_TOKEN_BUDGET_FLOOR = 300_000


def _count_label(count: int, singular: str) -> str:
    """按数量生成简单英文单复数标签。"""
    suffix = "" if count == 1 else "s"
    return f"{count} {singular}{suffix}"


def _format_artifact_counts(*, prompts: int, tools: int, skills: int) -> str:
    """生成终端使用的 Artifact 数量摘要。"""
    return ", ".join(
        (
            _count_label(prompts, "prompt"),
            _count_label(tools, "tool"),
            _count_label(skills, "skill"),
        )
    )


def _print_extraction_retries(resends: int, recovered_keys: list[str]) -> None:
    if resends or recovered_keys:
        console.print(
            Text(
                f"  Chunk resends accepted: {resends} · artifacts recovered: {len(recovered_keys)}"
            )
        )
    if recovered_keys:
        console.print(Text(f"  Recovered: {', '.join(recovered_keys)}", style="green"))


def _print_section(title: str) -> None:
    """在 verbose 模式中标记一段新的执行阶段。"""
    console.print(f"\n[bold cyan][{title}][/]")


def _package_version(distribution: str) -> str:
    """读取已安装依赖版本；开发环境缺少元数据时返回 unknown。"""
    try:
        return version(distribution)
    except PackageNotFoundError:
        return "unknown"


def _stage_status(message: str):
    """TTY 使用动态 spinner，CI 和重定向输出保留静态开始行。"""
    if console.is_terminal and not os.environ.get("CI"):
        return console.status(f"[bold cyan]{message}[/]")
    console.print(message)
    return nullcontext()


def _terminal_path(path: Path) -> str:
    cwd = Path.cwd()
    return str(path.relative_to(cwd) if path.is_relative_to(cwd) else path)


def _short_error(exc: BaseException, limit: int = 300) -> str:
    """Collapse a provider error into a single short line for the console."""
    text = " ".join(str(exc).split())
    return text if len(text) <= limit else text[:limit] + "..."


def _load_agent_config(config_path: Path) -> dict:
    """Read the optional `agent:` section from inspect_config.yaml.

    Returns {} when the section is absent or malformed — callers then fall
    back to their own defaults. Known keys: max_loops, token_budget, timeout.
    """
    try:
        content = read_file_with_encoding_fallback(config_path)
        if not content:
            return {}
        data = yaml.safe_load(content)
        section = (data or {}).get("agent")
        if not isinstance(section, dict):
            return {}
        out: dict = {}
        for key in ("max_loops", "token_budget", "timeout"):
            value = section.get(key)
            if isinstance(value, int) and value > 0:
                out[key] = value
        return out
    except Exception:
        return {}


def _load_inspect_settings(config_path: Path) -> dict:
    """Read the pipeline-level settings from inspect_config.yaml.

    Known keys (design §2/§6.5/§6.6/§7.2):
    - ``report_language``: str (default "en")
    - ``attribution``: auto|single|collection (default "auto")
    - ``model.context_window`` (fallback: top-level ``context_window``): int (default 200000)
    - ``model.enable_thinking``: bool | None (default None -> inherit ProviderConfig/env)
    - ``qc_lint.declared_dependencies``: list[str] enabling QC-1.2
    Returns {} defaults when the file is absent or malformed.
    """
    defaults: dict = {
        "report_language": "en",
        "attribution": "auto",
        "context_window": DEFAULT_CONTEXT_WINDOW,
        "enable_thinking": None,
        "declared_dependencies": None,
    }
    try:
        content = read_file_with_encoding_fallback(config_path)
        if not content:
            return defaults
        data = yaml.safe_load(content) or {}
    except Exception:
        return defaults

    language = data.get("report_language")
    if isinstance(language, str) and language.strip():
        defaults["report_language"] = language.strip()

    attribution = data.get("attribution")
    if attribution in ("auto", "single", "collection"):
        defaults["attribution"] = attribution

    model_section = data.get("model")
    model_cw = model_section.get("context_window") if isinstance(model_section, dict) else None
    top_cw = data.get("context_window")
    for candidate_cw in (model_cw, top_cw):
        if (
            isinstance(candidate_cw, int)
            and not isinstance(candidate_cw, bool)
            and candidate_cw > 0
        ):
            defaults["context_window"] = candidate_cw
            break

    if isinstance(model_section, dict):
        enable_thinking = model_section.get("enable_thinking")
        if isinstance(enable_thinking, bool):
            defaults["enable_thinking"] = enable_thinking

    qc_lint = data.get("qc_lint")
    if isinstance(qc_lint, dict):
        deps = qc_lint.get("declared_dependencies")
        if isinstance(deps, list) and all(isinstance(d, str) for d in deps):
            defaults["declared_dependencies"] = deps

    return defaults


def _build_provider_config(llm_config: dict[str, str], enable_thinking: bool | None = None):
    """Build aidynamic-agent ProviderConfig, forwarding enable_thinking only when explicitly set."""
    from aidynamic_agent.config import ProviderConfig

    kwargs: dict = {
        "PROVIDER": llm_config["llm_provider"],
        "API_KEY": llm_config["llm_api_key"],
        "MODEL_ID": llm_config["llm_model_id"],
        "BASE_URL": llm_config["llm_base_url"] or None,
    }
    if enable_thinking is not None:
        kwargs["ENABLE_THINKING"] = enable_thinking
    return ProviderConfig(**kwargs)


def _create_provider(provider_config, timeout: float = DEFAULT_LLM_TIMEOUT):
    """Build the LLM provider and widen its per-request timeout.

    ProviderFactory.create() does not forward a timeout, so providers keep
    their 120s default. The underlying client is created lazily on first use,
    so overriding the attribute here takes effect before any request.
    """
    from aidynamic_agent.llm.factory import ProviderFactory

    provider = ProviderFactory.create(provider_config)
    if hasattr(provider, "timeout"):
        try:
            provider.timeout = timeout
        except (AttributeError, TypeError):
            pass
    if hasattr(provider, "temperature"):
        try:
            provider.temperature = 0.0
        except (AttributeError, TypeError):
            pass
    return provider


def _print_user_error(
    title: str,
    message: str,
    hint: str | None = None,
    log_path: Path | None = None,
) -> None:
    """Print a user-friendly error message with actionable guidance.

    Args:
        title: Short error title (e.g., "Configuration Error").
        message: Human-readable description of what went wrong.
        hint: Optional next-step suggestion for the user.
        log_path: Path to the log file for debugging.
    """
    console.print()
    console.print(f"[bold red]✗ {title}[/]")
    console.print(f"  {message}")
    if hint:
        console.print(f"[dim]  → {hint}[/]")
    if log_path and log_path.exists():
        console.print(f"[dim]  → Full details: {log_path}[/]")
    console.print()


def _print_error_from_exception(
    exc: Exception,
    category: str,
    log_path: Path | None = None,
) -> None:
    """Map common exceptions to user-friendly error messages.

    Args:
        exc: The caught exception.
        category: Error context (config, agent, extract, inspect, network).
        log_path: Path to the log file for debugging.
    """
    exc_name = type(exc).__name__
    exc_msg = str(exc)[:200]  # Truncate long messages

    # Configuration errors
    if category == "config":
        if "api_key" in exc_msg.lower() or "key" in exc_msg.lower():
            _print_user_error(
                "Configuration Error",
                "LLM API key is missing or invalid.",
                hint="Set LLM_API_KEY environment variable or configure api_key in .deeplogic/inspect_config.yaml",
                log_path=log_path,
            )
        elif "model" in exc_msg.lower():
            _print_user_error(
                "Configuration Error",
                "LLM model configuration is incomplete.",
                hint="Configure model.provider and model.model_id in .deeplogic/inspect_config.yaml",
                log_path=log_path,
            )
        else:
            _print_user_error(
                "Configuration Error",
                f"Failed to load configuration: {exc_msg}",
                hint="Check .deeplogic/inspect_config.yaml for syntax errors or missing fields",
                log_path=log_path,
            )
        return

    # Network / API errors
    if exc_name in ("ConnectionError", "TimeoutError", "ClientConnectorError"):
        _print_user_error(
            "Network Error",
            "Could not connect to the LLM service.",
            hint="Check your internet connection and LLM_BASE_URL configuration",
            log_path=log_path,
        )
        return

    if exc_name in ("AuthenticationError", "PermissionDenied"):
        _print_user_error(
            "Authentication Error",
            "API key was rejected by the LLM provider.",
            hint="Verify your API key is correct and has not expired",
            log_path=log_path,
        )
        return

    if exc_name == "RateLimitError":
        _print_user_error(
            "Rate Limit Exceeded",
            "Too many requests to the LLM provider.",
            hint="Wait a moment and try again, or check your usage quota",
            log_path=log_path,
        )
        return

    # Agent errors (extraction / inspection)
    if category in ("extract", "inspect"):
        titles = {"extract": "Extraction Failed", "inspect": "Inspection Failed"}
        if "exceeds context_window=" in exc_msg:
            _print_user_error(
                "Model Input Context Limit Exceeded",
                exc_msg,
                hint="Reduce the artifact set or set context_window to the model's supported input size",
                log_path=log_path,
            )
        elif "timeout" in exc_msg.lower():
            _print_user_error(
                titles[category],
                "The agent took too long to complete.",
                hint="Increase --timeout or reduce the artifact set (split inspect_config.yaml)",
                log_path=log_path,
            )
        else:
            _print_user_error(
                titles[category],
                exc_msg,
                hint="Try again with --verbose for more details, or check LLM connectivity",
                log_path=log_path,
            )
        return

    # Report errors (non-fatal)
    if category == "report":
        console.print(f"[yellow]⚠ Could not save markdown report: {exc_msg}[/yellow]")
        return

    # Fallback for unclassified errors
    _print_user_error(
        "Unexpected Error",
        f"Something went wrong: {exc_msg}",
        hint="Run with --log-level DEBUG and check the log file for details",
        log_path=log_path,
    )


class _VerboseFlowStatus:
    """在 verbose 全流程底部保留一个可更新的 Rich spinner。"""

    def __init__(self, enabled: bool):
        self.enabled = enabled
        self._status: Status | None = None
        self._last_message: str | None = None

    def start(self, message: str) -> None:
        """启动底部 spinner；非 TTY 环境退化为静态阶段行。"""
        if not self.enabled:
            return
        self._last_message = message
        if console.is_terminal and not os.environ.get("CI"):
            self._status = console.status(f"[bold cyan]{message}[/]")
            self._status.start()
        else:
            console.print(message)

    def update(self, message: str) -> None:
        """更新当前阶段文案，同时保持 spinner 位于日志底部。"""
        if not self.enabled or message == self._last_message:
            return
        self._last_message = message
        if self._status is not None:
            self._status.update(f"[bold cyan]{message}[/]")
        else:
            console.print(message)

    def stop(self) -> None:
        """幂等停止 spinner，供正常结束和 Click 清理回调共同调用。"""
        if self._status is not None:
            self._status.stop()
            self._status = None


# ============================================================================
# Pipeline helpers
# ============================================================================


def _extract_without_agent(
    prompt_files: list[str],
    tool_files: list[str],
    skill_files: list[str],
):
    """--skip-extract path (design §3): inject config files directly.

    Every configured file becomes a ``completeness="full original"`` artifact;
    the deterministic tool-registry expansion runs exactly as in the agent
    path. No upload is triggered downstream.
    """
    from deeplogic_cli.agents.extract_agent.tools.tool_registry import (
        extract_tool_candidates,
    )
    from deeplogic_cli.inspect_pipeline.models import (
        ExtractedArtifact,
        ExtractionResult,
    )

    artifacts = []

    for path in prompt_files:
        text = read_file_with_encoding_fallback(Path(path)) or ""
        artifacts.append(
            ExtractedArtifact(
                type="prompt",
                name=Path(path).stem,
                content=text,
                completeness="full original",
                L="undetermined",
                evidence="config file injected verbatim (--skip-extract)",
                source=str(path),
                extraction_method="deterministic",
            )
        )

    candidates, unresolved_tools = extract_tool_candidates(tool_files)
    for candidate in candidates:
        artifacts.append(
            ExtractedArtifact(
                type="tool",
                name=candidate["name"],
                schema=candidate.get("schema") or {},
                completeness="full original",
                L="undetermined",
                evidence=f"tool registry entry in {candidate.get('source', 'unknown')}",
                source=candidate.get("source", str(tool_files[0] if tool_files else "")),
                extraction_method="deterministic",
            )
        )
    for path in unresolved_tools:
        text = read_file_with_encoding_fallback(Path(path)) or ""
        artifacts.append(
            ExtractedArtifact(
                type="tool",
                name=Path(path).stem,
                content=text,
                completeness="not inspectable",
                L="undetermined",
                reason="tool registry format not recognized (deterministic fallback)",
                source=str(path),
                extraction_method="deterministic",
            )
        )

    for path in skill_files:
        skill_path = Path(path)
        if skill_path.is_dir():
            skill_md = skill_path / "SKILL.md"
            content = (
                (read_file_with_encoding_fallback(skill_md) or "") if skill_md.is_file() else ""
            )
        else:
            content = read_file_with_encoding_fallback(skill_path) or ""
        artifacts.append(
            ExtractedArtifact(
                type="skill",
                name=skill_path.stem,
                content=content,
                completeness="full original",
                L="undetermined",
                evidence="config file injected verbatim (--skip-extract)",
                source=str(path),
                extraction_method="deterministic",
            )
        )

    return ExtractionResult(artifacts=artifacts)


def _qc_findings_and_candidates(qc_result):
    """Split QC results into the two report channels (design §7.3).

    Returns (definitive_findings, candidates):
    - definitive program-channel defects become findings[] entries directly;
    - hybrid pre-screen hits become candidate dicts for the InspectAgent to
      confirm or reject (they never enter the report from the CLI side).
    """
    findings: list[dict] = []
    candidates: list[dict] = []

    for artifact_result in qc_result.all_artifacts:
        for defect in artifact_result.defects:
            if defect.status == DefectStatus.CANDIDATE:
                candidates.append(
                    {
                        "id": str(defect.rule_id),
                        "severity": str(defect.severity),
                        "location": defect.location,
                        "model_prompt": defect.model_prompt or defect.description,
                    }
                )
                continue
            if defect.status != DefectStatus.DEFINITIVE:
                continue  # Not Executed markers surface as warnings, not findings
            findings.append(
                {
                    "stage": "A",
                    "module": "QC",
                    "artifact": artifact_result.artifact_name,
                    "id": str(defect.rule_id),
                    "severity": str(defect.severity),
                    "description": defect.description[:120],
                }
            )
    return findings, candidates


def _merge_qc_findings(parsed, qc_result) -> None:
    """Fold program-channel QC findings into the parsed summary in place.

    counts are recomputed from the merged findings set so the header numbers
    stay consistent with the panels (EX → risk_explicit, everything else →
    inspect; Explicit·P0 is a risk signal, never a defect count).
    """
    from deeplogic_cli.inspect_pipeline.report_parser import counts_from_findings

    qc_findings, _ = _qc_findings_and_candidates(qc_result)
    parsed.findings.extend(qc_findings)
    parsed.counts = counts_from_findings(parsed.findings)


def _qc_payload_block(qc_result, *, qc_skipped: bool) -> str:
    """Markdown block appended to the inspection payload (design §7.3)."""
    lines = ["## QC lint (program channel, ran before this inspection)"]
    if qc_skipped:
        lines.append("- QC lint was skipped (--skip-qc-lint).")
        return "\n".join(lines)
    gate = qc_result.gate_result.value if qc_result else "PASS"
    lines.append(f"- QC gate: {gate} (Definitive P0: {qc_result.p0_count})")
    not_executed = qc_result.not_executed_rule_ids
    if not_executed:
        lines.append(
            f"- Not executed (missing context, treat as no signal): {', '.join(not_executed)}"
        )
    if gate == "FAIL":
        lines.append(
            "- QC-0 did not pass: Stage A QC-1~4 checks MUST be skipped per the "
            "skill's entry-gate semantics."
        )
    return "\n".join(lines)


def _resolve_attribution(settings: dict, extraction_result):
    """Design §6.5: resolve the attribution statement at the CLI boundary.

    Returns (attribution_status, attribution_note) for the InspectAgent
    contract appendix. ``collection`` mode maps to ``pending`` — the skill
    red line then skips Stage B / Stage C-D / Stage E NL-B.
    """
    from deeplogic_cli.inspect_pipeline.models import Attribution

    configured = settings.get("attribution", "auto")
    reported = extraction_result.attribution or Attribution(status="pending", note="")
    status, note = reported.status, reported.note

    if configured == "single":
        return (
            "single",
            "config attribution=single: all configured artifacts form one agent set",
        )
    if configured == "collection":
        return (
            "pending",
            "config attribution=collection: cross-artifact stages must report " "Not Executed",
        )

    # auto
    if status == "single":
        return status, note or "extraction confirmed a single-agent artifact set"

    if console.is_terminal and not os.environ.get("CI"):
        console.print(
            "[yellow]⚠ Extraction could not confirm that all artifacts belong "
            "to one agent set.[/yellow]"
        )
        treat_single = typer.confirm(
            "Treat the configured artifacts as one agent set (full cross-artifact flow)?",
            default=False,
        )
        if treat_single:
            return "single", "user confirmed single-agent artifact set interactively"
        return "pending", "user chose collection mode: cross-artifact stages Not Executed"

    # auto + non-TTY: safe degrade to collection with a prominent warning.
    console.print(
        "[bold yellow]⚠ Attribution unconfirmed and session is non-interactive — "
        "degrading to collection mode. Stage B / Stage C-D / Stage E NL-B will "
        "report Not Executed.[/]"
    )
    return (
        "pending",
        (note + "; " if note else "") + "non-interactive session degraded to collection mode",
    )


def _auto_upload(
    project_id: str | None,
    extraction_result,
    *,
    config_path: Path | None = None,
) -> None:
    """Auto upload extracted artifacts to the server (design §2).

    Data source = the extraction result (store tool records / deterministic
    expansion); the server contract is unchanged. Flow:
    - no API key configured: skip (no-op);
    - API key without project binding: create a project first, then push;
    - API key with project binding: push directly.

    Args:
        project_id: Resolved project ID (None if not bound / placeholder).
        extraction_result: ExtractionResult from the extract stage.
        config_path: Resolved inspect_config.yaml path used for this run.
    """
    from deeplogic_cli.api.client import DeeplogicClient
    from deeplogic_cli.commands.project import (
        _get_project_config_path,
        _read_project_config,
        _write_project_config,
    )
    from deeplogic_cli.utils.artifact_packer import pack_extracted

    effective_config_path = config_path or _get_project_config_path()

    # No API key configured -> cannot upload, skip silently
    api_key = ConfigResolver(
        "server.api_key",
        "DEEPLOGIC_API_KEY",
        project_config_path=effective_config_path,
    ).resolve()
    if not api_key:
        console.print("[dim]API key not configured, skip auto upload.[/dim]")
        return

    base_url = (
        ConfigResolver(
            "server.base_url",
            "DEEPLOGIC_BASE_URL",
            DEFAULT_SERVER_BASE_URL,
            project_config_path=effective_config_path,
        ).resolve()
        or DEFAULT_SERVER_BASE_URL
    )
    client = DeeplogicClient(base_url, api_key)

    console.print("\n[bold]Packing artifacts...[/]")
    try:
        packed = pack_extracted(extraction_result)
    except Exception as e:
        _print_user_error(
            "Packaging Error",
            f"Failed to pack artifacts for upload: {e}",
            hint="This is a non-fatal error; the inspect result is still valid",
        )
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
        config = _read_project_config(effective_config_path)
        raw_project = config.get("project")
        configured_name = raw_project.get("name") if isinstance(raw_project, dict) else None
        project_root = (
            effective_config_path.parent.parent
            if effective_config_path.parent.name == ".deeplogic"
            else effective_config_path.parent
        )
        default_name = (
            configured_name.strip()
            if isinstance(configured_name, str) and configured_name.strip()
            else (project_root.name or Path.cwd().name or "my-project")
        )
        console.print(f"\n[bold]Creating new project [cyan]{default_name}[/]...[/]")
        try:
            result = client.create_project(default_name, None)
        except Exception as e:
            _print_user_error(
                "Project Creation Failed",
                f"Could not create project: {e}",
                hint="Check your DEEPLOGIC_API_KEY and network connectivity",
            )
            raise

        new_project_id = result.get("project_id") or result.get("id")
        if not new_project_id:
            console.print("[red]✗ Server returned no project ID[/red]")
            return

        # Persist the new project binding for subsequent pushes
        if not isinstance(config.get("project"), dict):
            config["project"] = {}
        config["project"]["id"] = new_project_id
        config["project"]["name"] = default_name
        _write_project_config(config, effective_config_path)

        project_id = new_project_id
        console.print(f"[green]✓[/] Created project (id: {project_id})")
    else:
        console.print(f"\n[bold]Using existing project: [cyan]{project_id}[/][/]")

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
        _print_user_error(
            "Upload Failed",
            f"Could not upload artifacts: {e}",
            hint="This is a non-fatal error; the inspect result is still valid",
        )
        raise

    version_id = result.get("version_id") or result.get("id")
    if version_id:
        console.print(f"[green]✓[/] Created version [cyan]{version_id}[/]")

    prompts = [a for a in extraction_result.artifacts if a.type == "prompt"]
    tools = [a for a in extraction_result.artifacts if a.type == "tool"]
    skills = [a for a in extraction_result.artifacts if a.type == "skill"]
    if prompts:
        console.print(f"  Prompts: {len(prompts)}")
    if tools:
        console.print(f"  Tools:   {len(tools)}")
    if skills:
        console.print(f"  Skills:  {len(skills)}")
    console.print()


@inspect_app.callback(invoke_without_command=True)
def inspect(
    ctx: typer.Context,
    config: str | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to inspect_config.yaml. If omitted, looks for .deeplogic/inspect_config.yaml in cwd.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help=(
            "Enable verbose output: per-loop progress, tool calls, token usage, and timing info."
        ),
    ),
    skip_extract: bool = typer.Option(
        False,
        "--skip-extract",
        help=(
            "Skip the ExtractAgent stage: inject configured files verbatim as "
            "full-original artifacts (no upload). Use when extraction already "
            "happened server-side or for offline re-inspection."
        ),
    ),
    timeout: int = typer.Option(
        1800,
        "--timeout",
        help=(
            "Agent execution timeout in seconds per stage (default: 1800, 30min). "
            "Increase for large projects; decrease for fast-fail in CI."
        ),
    ),
    token_budget: int = typer.Option(
        200000,
        "--token-budget",
        help=(
            "Cumulative token budget per agent (default: 200000; the inspect stage floors "
            "at 300000). Increase for large projects."
        ),
    ),
    log_enabled: bool = typer.Option(
        True,
        "--log/--no-log",
        help="Enable/disable execution logging to file (default: enabled).",
    ),
    log_level: str = typer.Option(
        None,
        "--log-level",
        help="Override log level: DEBUG, INFO, WARNING, ERROR (default: INFO).",
    ),
    strict: bool = typer.Option(
        False,
        "--strict",
        "--fail-on-defect",
        help=(
            "Exit with code 1 (EXIT_DEFECTS_FOUND) when the QC gate fails or "
            "P0 defects are found, and enforce stage completeness "
            "(missing stages or incomplete structured findings also exit 1)."
        ),
    ),
    skip_qc_lint: bool = typer.Option(
        False,
        "--skip-qc-lint",
        help="Skip the Code Contract lint check before LLM analysis.",
    ),
):
    """Inspect the configured artifacts with the skill-based two-agent pipeline."""
    # When a subcommand (e.g. `inspect repair`) is invoked, the group callback
    # must not run the full inspect workflow — only the subcommand body runs.
    if ctx.invoked_subcommand is not None:
        return

    # Validate log level
    if log_level and log_level.upper() not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
        console.print(
            f"[red]✗ Invalid log level: {log_level} (must be DEBUG/INFO/WARNING/ERROR)[/red]"
        )
        raise typer.Exit(code=EXIT_FAILURE)

    # Step 1a: Create config loader (resolve config path)
    try:
        loader = InspectConfigLoader(config, require_project_id=False)
    except Exception as e:
        # Even loader creation failed - initialize basic logging with defaults
        log_config = LogConfig()
        log_manager = LogManager(log_config, command="inspect")
        log_manager.start_session()
        log_manager.exception("config", "Failed to initialize config loader")
        _print_user_error(
            "Configuration Error",
            f"Could not initialize configuration loader: {e}",
            hint="Check that the config file path exists and is readable",
        )
        log_manager.end_session("failed")
        raise typer.Exit(code=EXIT_FAILURE) from e

    # Setup logging (config_path is now available from loader)
    log_config = load_log_config(loader.config_path)
    log_config.apply_cli_overrides(
        enabled=log_enabled,
        level=log_level,
    )
    log_manager = LogManager(log_config, command="inspect")
    run_started = perf_counter()
    run_timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = log_manager.start_session()

    if log_path and log_config.effective_enabled:
        console.print(Text(f"Log file: {_terminal_path(log_path)}", style="dim"))

    settings = _load_inspect_settings(loader.config_path)

    # Step 1b: Load and validate config content
    try:
        artifacts = loader.load()
    except ValidationError as e:
        log_manager.exception("config", "Configuration validation failed")
        _print_user_error(
            "Configuration Error",
            f"Configuration validation failed: {e}",
            hint="Check .deeplogic/inspect_config.yaml for syntax errors or missing required fields",
            log_path=log_manager.log_file,
        )
        log_manager.end_session("failed", {"error": "config_validation"})
        raise typer.Exit(code=EXIT_FAILURE) from None

    project_id = artifacts["project_id"]
    prompt_files = artifacts["prompts"]
    tool_files = artifacts["tools"]
    skill_files = artifacts["skills"]

    log_manager.info("config", "Configuration loaded", project_id=project_id or "not set")

    # Step 1c: Reject an empty manifest early (design §9: exit 2)
    if not prompt_files and not tool_files and not skill_files:
        _print_user_error(
            "No Artifacts Configured",
            "inspect_config.yaml lists no prompts, tools, or skills.",
            hint="Add artifact paths under prompts:/tools:/skills: in the config",
        )
        log_manager.end_session("failed", {"error": "no_artifacts"})
        raise typer.Exit(code=EXIT_FAILURE)

    manifest_total = len(prompt_files) + len(tool_files) + len(skill_files)
    if manifest_total > MAX_MANIFEST_FILES:
        _print_user_error(
            "Too Many Artifacts",
            f"{manifest_total} files configured (limit {MAX_MANIFEST_FILES}).",
            hint="Split the inspect config into multiple runs",
        )
        log_manager.end_session("failed", {"error": "manifest_too_large"})
        raise typer.Exit(code=EXIT_FAILURE)

    # Step 2: Display resolved artifacts
    if verbose:
        project_root = loader.config_path.parent
        if project_root.name == ".deeplogic":
            project_root = project_root.parent
        table = Table(title="[bold]Inspect Artifacts[/]", border_style="blue")
        table.add_column("Type", style="bold cyan", no_wrap=True)
        table.add_column("Source Path", style="white")
        for kind, files in (("Prompt", prompt_files), ("Tool", tool_files), ("Skill", skill_files)):
            for file in files:
                source = Path(file)
                display = (
                    source.relative_to(project_root)
                    if source.is_relative_to(project_root)
                    else source
                )
                table.add_row(kind, Text(str(display)))
        console.print(table)
        console.print(f"[dim]Project ID: {project_id or 'not set'}[/dim]")
    input_counts = _format_artifact_counts(
        prompts=len(prompt_files), tools=len(tool_files), skills=len(skill_files)
    )
    console.print(f"[dim]Configured sources: {input_counts}[/dim]")

    log_manager.info(
        "artifacts",
        "Resolved artifacts",
        prompts=len(prompt_files),
        tools=len(tool_files),
        skills=len(skill_files),
    )

    flow_status = _VerboseFlowStatus(verbose)

    # Step 3: QC lint (program channel + hybrid pre-screen; design §7)
    qc_result = None
    if not skip_qc_lint:
        from deeplogic_cli.code_contract_checker.checker import CodeContractChecker
        from deeplogic_cli.code_contract_checker.renderer import QCRenderer

        qc_checker = CodeContractChecker(
            verbose=verbose,
            declared_dependencies=settings.get("declared_dependencies"),
        )
        if verbose:
            _print_section("Code Contract Inspection (QC Lint)")
            flow_status.update("Running QC lint checks...")
            console.print("  Checking: 17-item checklist v2 (program + hybrid pre-screen)")

        qc_started = perf_counter()
        qc_result = qc_checker.check_from_paths(
            prompts=prompt_files,
            tools=tool_files,
            skills=skill_files,
        )
        qc_elapsed = perf_counter() - qc_started

        if qc_result.total_defects == 0:
            console.print(
                f"[green]✓[/] QC lint passed ({qc_result.total_artifacts} artifacts, "
                f"0 defects, {qc_elapsed:.2f}s)"
            )
        else:
            QCRenderer(console).render(qc_result)

        log_manager.info(
            "qc_lint",
            "Code Contract inspection completed",
            duration=f"{qc_elapsed:.2f}s",
            total_defects=qc_result.total_defects,
            definitive=qc_result.total_defects
            - qc_result.candidate_count
            - qc_result.not_executed_count,
            candidates=qc_result.candidate_count,
            not_executed=qc_result.not_executed_count,
            p0=qc_result.p0_count,
            gate=qc_result.gate_result,
        )

        # Strict mode: QC gate fails -> exit before any LLM spend
        if strict and qc_result.gate_result.value == "FAIL":
            console.print(
                "[red]X QC Gate failed with P0 defects. Consider fixing them before continuing.[/red]"
            )
            log_manager.end_session(
                "failed", {"error": "qc_gate_fail", "p0_count": qc_result.p0_count}
            )
            raise typer.Exit(code=EXIT_DEFECTS_FOUND)
    else:
        log_manager.info("qc_lint", "Code Contract lint check skipped")
        console.print("[dim]QC lint check skipped (--skip-qc-lint).[/dim]")

    # Step 4: Resolve LLM configuration + provider
    agent_cfg = _load_agent_config(loader.config_path)

    try:
        llm_config = resolve_llm_config(config)
        log_manager.debug(
            "config", "LLM configuration resolved", provider=llm_config.get("llm_provider")
        )
    except Exception as e:
        log_manager.exception("config", "Failed to resolve LLM configuration")
        _print_error_from_exception(e, "config", log_path=log_manager.log_file)
        log_manager.end_session("failed", {"error": "llm_config_resolution"})
        raise typer.Exit(code=EXIT_FAILURE) from None

    if not llm_config.get("llm_api_key", "").strip():
        log_manager.error("config", "LLM configuration incomplete: missing API key")
        console.print("[red]✗ LLM configuration is incomplete.[/red]")
        console.print("  Missing: API key")
        console.print()
        console.print(
            "Configure the provider, api_key, model_id and base_url in "
            ".deeplogic/inspect_config.yaml."
        )
        raise typer.Exit(code=EXIT_FAILURE)

    effective_timeout = timeout if timeout != 1800 else agent_cfg.get("timeout", timeout)
    effective_budget = (
        token_budget if token_budget != 200000 else max(agent_cfg.get("token_budget", 0), 200000)
    )

    provider_config = _build_provider_config(
        llm_config, enable_thinking=settings["enable_thinking"]
    )
    provider = _create_provider(provider_config)

    # Step 5: Materialize vendored skills (design §10)
    from deeplogic_cli.inspect_pipeline.skill_runtime import (
        materialize_skills,
        validate_vendor,
    )

    try:
        skills_dir = materialize_skills()
        for warning in validate_vendor(skills_dir):
            console.print(f"[yellow]⚠ {warning}[/yellow]")
            log_manager.warning("skills", warning)
        log_manager.info("skills", "Vendor skills materialized", path=str(skills_dir))
    except Exception as e:
        log_manager.exception("skills", "Failed to materialize vendored skills")
        _print_user_error(
            "Skill Runtime Error",
            f"Could not materialize vendored skills: {e}",
            hint="Reinstall the package so src/deeplogic_cli/skills is intact",
        )
        log_manager.end_session("failed", {"error": "skill_materialize"})
        raise typer.Exit(code=EXIT_FAILURE) from None

    # Step 6: ExtractAgent (or --skip-extract verbatim injection)
    if skip_extract:
        log_manager.info("extract", "Extraction skipped (--skip-extract)")
        console.print(
            "[dim]Extraction skipped (--skip-extract): injecting config files verbatim.[/dim]"
        )
        extraction_result = _extract_without_agent(prompt_files, tool_files, skill_files)
        extract_elapsed = 0.0
    else:
        from deeplogic_cli.agents.extract_agent.agent import (
            ExtractAgent,
            IncompleteExtractionError,
        )

        extract_budget = max(effective_budget, EXTRACT_TOKEN_BUDGET_FLOOR)
        if effective_budget < EXTRACT_TOKEN_BUDGET_FLOOR:
            console.print(
                f"[yellow]⚠ Token budget {effective_budget} below the extract-stage floor; "
                f"using {EXTRACT_TOKEN_BUDGET_FLOOR}.[/yellow]"
            )
        extract_agent = ExtractAgent(
            provider,
            skills_dir=skills_dir,
            timeout=effective_timeout,
            token_budget=extract_budget,
            context_window=settings["context_window"],
            verbose=verbose,
            console=console,
            log_manager=log_manager,
            report_language=settings["report_language"],
        )
        if verbose:
            _print_section("Artifact Extraction")
            flow_status.start("Extracting artifacts (agent loop)...")
            ctx.call_on_close(flow_status.stop)

        extract_started = perf_counter()
        try:
            if verbose:
                extraction_result = extract_agent.extract_sync(
                    prompts=prompt_files,
                    tools=tool_files,
                    skills=skill_files,
                )
            else:
                with _stage_status("Extracting artifacts (agent loop)..."):
                    extraction_result = extract_agent.extract_sync(
                        prompts=prompt_files,
                        tools=tool_files,
                        skills=skill_files,
                    )
        except IncompleteExtractionError as e:
            # Design §5.3/§9: incomplete chunk streams never reach inspection.
            log_manager.exception("extract", "Extraction chunk stream incomplete")
            _print_user_error(
                "Extraction Incomplete",
                str(e),
                hint="Re-run; if it persists, check the model's adherence via --verbose",
                log_path=log_manager.log_file,
            )
            _print_extraction_retries(e.resends, e.recovered_keys)
            flow_status.stop()
            log_manager.end_session(
                "failed",
                {
                    "error": "extraction_incomplete",
                    "exit_code": EXIT_FAILURE,
                    "incomplete_artifacts": e.incomplete_keys,
                    "recovered_artifacts": e.recovered_keys,
                    "resends": e.resends,
                },
            )
            raise typer.Exit(code=EXIT_FAILURE) from None
        except Exception as e:
            log_manager.exception("extract", "Artifact extraction failed")
            _print_error_from_exception(e, "extract", log_path=log_manager.log_file)
            flow_status.stop()
            log_manager.end_session("failed", {"error": "extraction"})
            raise typer.Exit(code=EXIT_FAILURE) from None
        extract_elapsed = perf_counter() - extract_started

    # Design §9: distinguish "nothing configured" (handled above) from
    # "extraction identified nothing".
    if not extraction_result.artifacts:
        _print_user_error(
            "Empty Extraction",
            "The extraction stage did not identify any artifacts (every input "
            "may have been classified Tier X / not inspectable).",
            hint="Verify the configured files contain actual prompts/tools/skills",
            log_path=log_manager.log_file,
        )
        flow_status.stop()
        log_manager.end_session("failed", {"error": "empty_extraction"})
        raise typer.Exit(code=EXIT_FAILURE)

    meta = extraction_result.meta
    counts_label = _format_artifact_counts(
        prompts=sum(1 for a in extraction_result.artifacts if a.type == "prompt"),
        tools=sum(1 for a in extraction_result.artifacts if a.type == "tool"),
        skills=sum(1 for a in extraction_result.artifacts if a.type == "skill"),
    )
    if not skip_extract:
        console.print(f"[green]✓[/] Extraction completed in {extract_elapsed:.1f}s")
    console.print(f"  Artifacts: {counts_label}")
    _print_extraction_retries(len(meta.resends), meta.recovered_keys)
    log_manager.info(
        "extract",
        "Artifacts ready",
        duration=f"{extract_elapsed:.1f}s",
        artifacts=len(extraction_result.artifacts),
        deterministic_candidates=meta.deterministic_candidates,
        resends=len(meta.resends),
        recovered_artifacts=meta.recovered_keys,
    )

    # Step 7: Write per-document IR files (audit only; design §8)
    results_dir = loader.config_path.parent / "results"
    run_id: str | None = None
    ir_batch_dir: Path | None = None
    try:
        from deeplogic_cli.inspect_pipeline.ir_writer import (
            allocate_run_id,
            write_ir_files,
        )

        run_id = allocate_run_id(results_dir, timestamp=run_timestamp, reserve=True)
        ir_paths = write_ir_files(extraction_result, results_dir / "ir", run_id=run_id)
        ir_batch_dir = results_dir / "ir" / run_id
        count = _count_label(len(ir_paths), "file")
        console.print(Text(f"IR saved: {_terminal_path(ir_batch_dir)} ({count})", style="dim"))
        log_manager.info(
            "ir", "Document IR files written", count=len(ir_paths), ir_dir=str(ir_batch_dir)
        )
    except Exception:
        # IR is an audit artifact only — never fail the pipeline on it.
        log_manager.exception("ir", "Could not write document IR files")

    # Step 8: Auto upload (design §2: data source = extraction result;
    # --skip-extract does not upload)
    if not skip_extract:
        if verbose:
            flow_status.update("Synchronizing artifacts...")
            _print_section("Artifact Synchronization")
        try:
            if "config_path" in inspect_mod.signature(_auto_upload).parameters:
                _auto_upload(project_id, extraction_result, config_path=loader.config_path)
            else:
                _auto_upload(project_id, extraction_result)
        except Exception:
            # _auto_upload 内部已打印用户友好提示，这里只记录日志
            log_manager.exception("upload", "Auto upload failed")
            # 上传失败不阻止检查
    else:
        log_manager.info("upload", "Auto upload skipped (--skip-extract)")

    # Step 9: InspectAgent over the extraction IR (design §6)
    flow_status.update("Preparing inspection...")
    from deeplogic_cli.agents.inspect_agent.agent import (
        InspectAgent,
        InspectionFailedError,
    )
    from deeplogic_cli.inspect_pipeline.ir_writer import render_injection_payload

    injection_payload = render_injection_payload(extraction_result)
    injection_payload += "\n\n" + _qc_payload_block(qc_result, qc_skipped=qc_result is None)

    attribution_status, attribution_note = _resolve_attribution(settings, extraction_result)

    qc_findings, qc_candidates = (
        _qc_findings_and_candidates(qc_result) if qc_result is not None else ([], [])
    )
    _ = qc_findings  # program-channel findings merge into the summary later

    inspect_budget = max(effective_budget, INSPECT_TOKEN_BUDGET_FLOOR)
    if effective_budget < INSPECT_TOKEN_BUDGET_FLOOR:
        console.print(
            f"[yellow]⚠ Token budget {effective_budget} below the inspect-stage floor; "
            f"using {INSPECT_TOKEN_BUDGET_FLOOR}.[/yellow]"
        )

    from deeplogic_cli import __version__

    header_data = {
        "cli": f"deeplogic-cli v{__version__}",
        "framework": "DeepLogic Framework v1.1",
        "model": llm_config["llm_model_id"],
        "date": datetime.now().strftime("%Y-%m-%d"),
        "project": project_id or "not set",
    }

    inspect_agent = InspectAgent(
        provider,
        skills_dir=skills_dir,
        injection_payload=injection_payload,
        header_data=header_data,
        attribution=attribution_status,
        attribution_note=attribution_note,
        qc_candidates=qc_candidates,
        max_loops=agent_cfg.get("max_loops", 80),
        timeout=effective_timeout,
        token_budget=inspect_budget,
        context_window=settings["context_window"],
        verbose=verbose,
        console=console,
        log_manager=log_manager,
        report_language=settings["report_language"],
    )

    if verbose:
        _print_section("Defect Inspection")
        console.print(f"  Provider:     {llm_config['llm_provider']}")
        console.print(f"  Model:        {llm_config['llm_model_id']}")
        console.print(f"  Timeout:      {effective_timeout}s")
        console.print(f"  Token budget (cumulative): {inspect_budget:,}")
        console.print(f"  Model input limit per request: {settings['context_window']:,} tokens")
        console.print(f"  Attribution:  {attribution_status}")
        console.print(f"  Payload:      ≈{estimate_tokens(injection_payload):,} tokens")
        console.print(f"  QC candidates: {len(qc_candidates)}")
        flow_status.update("Running seven-stage inspection (agent loop)...")

    inspect_started = perf_counter()
    try:
        outcome = inspect_agent.inspect_sync()
    except InspectionFailedError as e:
        # Design §9: report best-effort + prominent warning, exit 2.
        log_manager.exception("inspect", "Inspection agent failed")
        partial = getattr(e, "partial", None)
        report_path = None
        if partial is not None:
            try:
                from deeplogic_cli.inspect_pipeline.markdown_reporter import (
                    save_inspection_report,
                )
                from deeplogic_cli.inspect_pipeline.report_parser import (
                    extract_tail_block,
                    parse_summary,
                )

                partial_summary = parse_summary(
                    partial.tail_text,
                    partial.section_parts,
                    partial.missing_stages,
                    part_findings=partial.part_findings,
                    unstructured_stages=partial.unstructured_stages,
                )
                partial_summary.status = "failed"
                partial_summary.counts_partial = True
                if qc_result is not None:
                    _merge_qc_findings(partial_summary, qc_result)
                partial_meta = {
                    "model": llm_config["llm_model_id"],
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "status": "failed",
                }
                if ir_batch_dir is not None:
                    partial_meta["ir_dir"] = str(ir_batch_dir)
                report_path = save_inspection_report(
                    partial.section_parts,
                    partial.missing_stages,
                    extract_tail_block(partial.tail_text),
                    results_dir,
                    meta=partial_meta,
                    timestamp=run_id,
                    summary=partial_summary,
                )
            except Exception:
                log_manager.exception("report", "Could not save partial report")
        _print_error_from_exception(e, "inspect", log_path=log_manager.log_file)
        if report_path:
            console.print(
                Text(f"⚠ Partial report saved: {report_path.resolve()}", style="yellow"),
                soft_wrap=True,
            )
        flow_status.stop()
        log_manager.end_session("failed", {"error": "inspection"})
        raise typer.Exit(code=EXIT_FAILURE) from None
    inspect_elapsed = perf_counter() - inspect_started
    flow_status.stop()

    # Step 10: Parse tail JSON (fail-closed ladder), merge QC, render, persist
    from deeplogic_cli.inspect_pipeline.markdown_reporter import save_inspection_report
    from deeplogic_cli.inspect_pipeline.renderer import render_inspection_summary
    from deeplogic_cli.inspect_pipeline.report_parser import (
        extract_tail_block,
        parse_summary,
    )

    parsed = parse_summary(
        outcome.tail_text,
        outcome.section_parts,
        outcome.missing_stages,
        part_findings=outcome.part_findings,
        unstructured_stages=outcome.unstructured_stages,
    )
    if qc_result is not None:
        _merge_qc_findings(parsed, qc_result)

    log_manager.info(
        "inspect",
        "Inspection result",
        status=parsed.status,
        duration=f"{inspect_elapsed:.1f}s",
        loops=outcome.loops_used,
        tokens=outcome.tokens_used,
        missing_stages=parsed.missing_stages,
        unstructured_stages=parsed.unstructured_stages,
        counts=parsed.counts,
        counts_partial=parsed.counts_partial,
    )
    for warning in parsed.warnings:
        log_manager.warning("inspect", warning)
    for rule_id in qc_result.not_executed_rule_ids if qc_result is not None else []:
        console.print(f"[dim]QC {rule_id}: not executed (missing context)[/dim]")

    render_inspection_summary(console, parsed, verbose=verbose, duration=inspect_elapsed)

    tail_block = extract_tail_block(outcome.tail_text)
    try:
        report_meta = {
            "model": llm_config["llm_model_id"],
            "date": datetime.now().strftime("%Y-%m-%d"),
            "project": project_id or "not set",
            "attribution": attribution_status,
        }
        if ir_batch_dir is not None:
            report_meta["ir_dir"] = str(ir_batch_dir)
        report_path = save_inspection_report(
            outcome.section_parts,
            outcome.missing_stages,
            tail_block,
            results_dir,
            meta=report_meta,
            timestamp=run_id,
            summary=parsed,
        )
        console.print(Text(f"Report saved: {report_path.resolve()}", style="dim"), soft_wrap=True)
        portal_url = f"{DEFAULT_SERVER_BASE_URL}/"
        console.print(f"SaaS portal: [link={portal_url}]{portal_url}[/link]")
        log_manager.info("report", f"Markdown report saved: {report_path}")
    except Exception as e:
        # Report persistence is best-effort; do not fail the command.
        log_manager.exception("report", "Could not save markdown report")
        _print_error_from_exception(e, "report", log_path=log_manager.log_file)

    # Step 11: Exit code matrix (design §9)
    exit_code = EXIT_SUCCESS
    if parsed.status == "failed":
        if parsed.source == "none":
            console.print("[bold red]✗ Inspection summary could not be parsed.[/]")
        exit_code = EXIT_FAILURE
    elif strict and (parsed.inspect_p0 > 0 or parsed.missing_stages or parsed.unstructured_stages):
        if parsed.inspect_p0 > 0:
            console.print(f"[red]✗ P0 defect gate: {parsed.inspect_p0} recorded defect(s).[/]")
        if parsed.missing_stages:
            console.print(
                f"[red]✗ Stage completeness gate: not received "
                f"({', '.join(parsed.missing_stages)}).[/]"
            )
        if parsed.unstructured_stages:
            console.print(
                f"[red]✗ Finding completeness gate: incomplete stages "
                f"({', '.join(parsed.unstructured_stages)}).[/]"
            )
        exit_code = EXIT_DEFECTS_FOUND

    console.print(f"[dim]Total time: {perf_counter() - run_started:.1f}s[/dim]")
    session_status = {"completed": "success", "partial": "partial", "failed": "failed"}
    log_manager.end_session(
        "failed" if exit_code else session_status[parsed.status],
        {
            "exit_code": exit_code,
            "inspection_status": parsed.status,
            "artifacts": len(extraction_result.artifacts),
            "inspect_p0": parsed.inspect_p0,
            "missing_stages": parsed.missing_stages,
            "unstructured_stages": parsed.unstructured_stages,
        },
    )
    if exit_code:
        raise typer.Exit(code=exit_code)


# ============================================================================
# inspect repair — generate repaired artifacts from a local inspection report
# ============================================================================


def _find_latest_report(report_dir: Path) -> Path | None:
    """Return the newest inspect-*.md report in report_dir, or None."""
    if not report_dir.is_dir():
        return None
    candidates = sorted(report_dir.glob("inspect-*.md"), key=lambda p: p.stat().st_mtime)
    return candidates[-1] if candidates else None


def _write_repairs_markdown(
    repairs: list[dict],
    output_dir: Path,
    *,
    report_path: Path,
    project_id: str | None,
) -> Path:
    """Persist repaired artifact content into a single markdown file."""
    from datetime import datetime

    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = output_dir / f"repair-{timestamp}.md"

    type_labels = {"skill": "Skill", "tool": "Tool", "prompt": "Prompt"}
    lines: list[str] = [
        "# Repair Report",
        "",
        "> **Disclaimer**: This tool lacks business context. The repair content is for reference only. Please verify and apply fixes carefully based on your business logic.",
        "",
        f"- **Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **Source report**: {report_path}",
        f"- **Project ID**: {project_id or 'not set'}",
        f"- **Artifacts repaired**: {len(repairs)}",
        "",
    ]

    for index, repair in enumerate(repairs, start=1):
        label = type_labels.get(repair.get("artifact_type", ""), "Artifact")
        artifact_path = repair.get("artifact_path", "")
        artifact_name = repair.get("artifact_name")
        heading_title = (
            f"{artifact_name} ({Path(artifact_path).name})"
            if artifact_name
            else Path(artifact_path).name
        )
        content = repair.get("repaired_content", "")
        # CommonMark safe fence: if content contains backticks, use more ticks than any inner block
        import re

        backtick_matches = re.findall(r"`{4,}", content)
        max_backticks = max((len(m) for m in backtick_matches), default=3)
        fence = "`" * max(4, max_backticks + 1)

        lines.extend(
            [
                "---",
                "",
                f"## {index}. {label} — {heading_title}",
                "",
                f"- **Source**: `{artifact_path}`",
                f"- **Summary**: {repair.get('summary', '')}",
                "",
                "### Repaired content",
                "",
                f"{fence}markdown",
                content,
                f"{fence}",
                "",
            ]
        )

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# @inspect_app.command("repair")  # Disabled: repair command is closed
def repair(
    ctx: typer.Context,
    report: str | None = typer.Option(
        None,
        "--report",
        "-r",
        help=(
            "Path to the inspection report (.md) to repair from. "
            "If omitted, uses the newest .deeplogic/results/inspect-*.md."
        ),
    ),
    config: str | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to inspect_config.yaml. If omitted, looks for .deeplogic/inspect_config.yaml in cwd.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output: per-loop progress, tool calls, and timing info.",
    ),
    timeout: int = typer.Option(
        1800,
        "--timeout",
        help="Agent execution timeout in seconds (default: 1800, 30min).",
    ),
    token_budget: int = typer.Option(
        0,
        "--token-budget",
        help=(
            "Token budget for repair agent (default: auto-scaled by artifact count). "
            "Set explicitly for large projects."
        ),
    ),
    llm_timeout: float = typer.Option(
        DEFAULT_LLM_TIMEOUT,
        "--llm-timeout",
        help=(
            "Per-request LLM timeout in seconds (default: 600). Raise it when "
            "repaired artifacts are large and the model needs longer to answer."
        ),
    ),
    log_enabled: bool = typer.Option(
        True,
        "--log/--no-log",
        help="Enable/disable execution logging to file (default: enabled).",
    ),
    log_level: str | None = typer.Option(
        None,
        "--log-level",
        help="Override log level: DEBUG, INFO, WARNING, ERROR (default: INFO).",
    ),
) -> None:
    """Generate repaired artifacts locally from an inspection report.

    Reads the latest inspection report (or --report), asks a local repair
    agent to rewrite every defective artifact, and writes the repaired
    content to `.deeplogic/repairs/repair-<timestamp>.md`. Nothing is
    uploaded and no source file is modified.
    """
    if log_level and log_level.upper() not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
        console.print(
            f"[red]✗ Invalid log level: {log_level} (must be DEBUG/INFO/WARNING/ERROR)[/red]"
        )
        raise typer.Exit(code=EXIT_FAILURE)

    # Step 1: Resolve config + artifacts
    try:
        loader = InspectConfigLoader(config, require_project_id=False)
        artifacts = loader.load()
    except Exception as e:
        console.print(f"[red]✗ Configuration Error: {e}[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None

    project_id = artifacts.get("project_id")
    artifact_paths = {
        "prompts": artifacts.get("prompts") or [],
        "tools": artifacts.get("tools") or [],
        "skills": artifacts.get("skills") or [],
    }
    total = sum(len(v) for v in artifact_paths.values())
    if not total:
        console.print("[red]✗ No artifacts configured in inspect_config.yaml[/red]")
        raise typer.Exit(code=EXIT_FAILURE)

    # Step 2: Resolve report path
    results_dir = loader.config_path.parent / "results"
    report_path: Path | None = None
    if report:
        report_path = Path(report).expanduser().resolve()
        if not report_path.is_file():
            console.print(f"[red]✗ Report not found: {report}[/red]")
            raise typer.Exit(code=EXIT_FAILURE)
    else:
        report_path = _find_latest_report(results_dir)
        if report_path is None:
            console.print(f"[red]✗ No inspection report found in {results_dir}[/red]")
            console.print("  Run `deeplogic-cli inspect` first, or pass --report <path>.")
            raise typer.Exit(code=EXIT_FAILURE)

    # Step 3: Setup logging
    log_config = load_log_config(loader.config_path)
    log_config.apply_cli_overrides(enabled=log_enabled, level=log_level)
    log_manager = (
        LogManager(log_config, command="inspect") if log_config.effective_enabled else None
    )
    if log_manager:
        log_manager.start_session()

    console.print()
    console.print("[bold]Repairing artifacts from inspection report[/]")
    console.print(f"  Report:    {report_path}")
    console.print(
        f"  Artifacts: {total} ({len(artifact_paths['prompts'])}p, "
        f"{len(artifact_paths['tools'])}t, {len(artifact_paths['skills'])}s)"
    )

    # Step 4: Resolve LLM config + provider
    try:
        llm_config = resolve_llm_config(config)
    except Exception as e:
        console.print(f"[red]✗ Failed to resolve LLM configuration: {e}[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None

    if not llm_config.get("llm_api_key", "").strip():
        console.print("[red]✗ LLM configuration is incomplete (missing API key).[/red]")
        console.print(
            "  Configure model.provider/api_key/model_id in .deeplogic/inspect_config.yaml."
        )
        raise typer.Exit(code=EXIT_FAILURE)

    settings = _load_inspect_settings(loader.config_path)
    provider_config = _build_provider_config(
        llm_config, enable_thinking=settings["enable_thinking"]
    )
    provider = _create_provider(provider_config, timeout=llm_timeout)

    # Step 5: Run the repair agent
    from deeplogic_cli.agents.repair_agent.agent import RepairAgent, _is_rate_limit_error
    from deeplogic_cli.agents.repair_agent.tools.store_repairs_tool import StoreRepairsTool

    # Clear any leftover state from previous invocations (ClassVar persistence).
    StoreRepairsTool.clear()

    # Honor the optional `agent:` section in inspect_config.yaml
    # (max_loops / token_budget / timeout); CLI flags still win. Repair
    # defaults are more generous than the SDK's: reasoning-heavy models burn
    # budget fast when rewriting whole artifacts, so the floor here is 500K.
    agent_cfg = _load_agent_config(loader.config_path)
    effective_timeout = timeout if timeout != 1800 else agent_cfg.get("timeout", timeout)
    # Reasoning-heavy models burn 20-50K tokens per rewritten artifact, so a
    # fixed budget either starves big projects or over-provisions small ones.
    # Scale with the artifact count, and never go below what the config asks.
    # CLI --token-budget takes precedence when explicitly set (> 0).
    if token_budget > 0:
        effective_budget = token_budget
    else:
        auto_budget = 300_000 + 150_000 * total
        effective_budget = max(agent_cfg.get("token_budget", 0), auto_budget)
    agent = RepairAgent(
        provider=provider,
        max_loops=agent_cfg.get("max_loops", 60),
        timeout=effective_timeout,
        token_budget=effective_budget,
        verbose=verbose,
        log_manager=log_manager,
    )
    agent.console = console

    console.print("  Provider:  " + llm_config["llm_provider"])
    console.print("  Model:     " + llm_config["llm_model_id"])
    console.print(f"  Budget:    {effective_budget} tokens / {effective_timeout}s")
    console.print()

    try:
        repairs = agent.repair_sync(
            report_path=str(report_path),
            artifacts=artifact_paths,
            project_root=str(loader.config_path.parent.parent),
        )
    except Exception as e:
        if log_manager:
            log_manager.exception("repair", "Repair agent failed")
            log_manager.end_session("failed", {"error": "repair_agent"})
        # Rate-limit / proxy failures produce a huge provider stack; surface a
        # short actionable message instead of dumping it on the user.
        if _is_rate_limit_error(e):
            console.print("[red]✗ Repair failed: the LLM service is rate limited.[/red]")
            console.print(
                "  The server-side model quota is exhausted (the proxy may allow "
                "as little as 1 request/minute)."
            )
            console.print("  Wait a minute and re-run, or raise the backend quota.")
        else:
            console.print(f"[red]✗ Repair failed: {_short_error(e)}[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None

    if not repairs:
        console.print("[yellow]⚠[/] No repairs generated (report may contain no defects).")
        if log_manager:
            log_manager.end_session("success", {"repairs": 0})
        return

    # Step 6: Persist repairs to .deeplogic/repairs/
    repairs_dir = loader.config_path.parent / "repairs"
    try:
        out_path = _write_repairs_markdown(
            repairs,
            repairs_dir,
            report_path=report_path,
            project_id=project_id,
        )
        console.print(f"[green]✓[/] Repaired {len(repairs)} artifact(s)")
        console.print(f"  Saved to: {out_path}")
        if log_manager:
            log_manager.info("repair", f"Repair report saved: {out_path}")
            log_manager.end_session("success", {"repairs": len(repairs)})
    except Exception as e:
        if log_manager:
            log_manager.exception("repair", "Could not save repair report")
            log_manager.end_session("failed", {"error": "repair_report"})
        console.print(f"[red]✗ Could not save repair report: {e}[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None


# ============================================================================
# inspect cover — apply the newest repair report's artifacts to source files
# ============================================================================


def _parse_repairs_markdown(report_path: Path) -> list[dict]:
    """Parse a repair-*.md file back into repair entries.

    Each entry section looks like:

        ## N. <Type> — <filename>
        - **Source**: `<absolute path>`
        - **Summary**: ...
        ### Repaired content
        ````markdown
        <content>
        ````
    """
    import re

    text = report_path.read_text(encoding="utf-8")
    entries: list[dict] = []

    # Fields are matched independently (blank lines may sit between them).
    header_re = re.compile(r"^## \d+\. .+? — .+?$", re.M)
    source_re = re.compile(r"^- \*\*Source\*\*: `(.+?)`\s*$", re.M)
    summary_re = re.compile(r"^- \*\*Summary\*\*: (.+?)\s*$", re.M)
    fence_open_re = re.compile(r"^(`{4,})markdown\s*$", re.M)

    headers = list(header_re.finditer(text))
    for index, header in enumerate(headers):
        segment_start = header.end()
        segment_end = headers[index + 1].start() if index + 1 < len(headers) else len(text)
        segment = text[segment_start:segment_end]

        source_match = source_re.search(segment)
        if not source_match:
            continue
        summary_match = summary_re.search(segment)

        fence_match = fence_open_re.search(segment)
        if not fence_match:
            continue
        fence_ticks = fence_match.group(1)
        content_start = fence_match.end()
        # Skip the newline right after the opening fence.
        if segment[content_start : content_start + 1] == "\n":
            content_start += 1

        # Look for closing fence matching the exact tick pattern on its own line
        closing_re = re.compile(rf"^{fence_ticks}\s*$", re.M)
        closing_matches = list(closing_re.finditer(segment, content_start))
        if not closing_matches:
            fence_close = segment.rfind(f"\n{fence_ticks}")
            if fence_close == -1 or fence_close < content_start:
                continue
        else:
            fence_close = closing_matches[-1].start()
            if fence_close > 0 and segment[fence_close - 1] == "\n":
                fence_close -= 1

        content = segment[content_start:fence_close]

        entries.append(
            {
                "label": header.group(0).strip(),
                "artifact_path": source_match.group(1).strip(),
                "summary": (summary_match.group(1).strip() if summary_match else ""),
                "repaired_content": content,
            }
        )
    return entries


# @inspect_app.command("cover")  # Disabled: cover command depends on repair
def cover(
    ctx: typer.Context,
    repair_report: str | None = typer.Option(
        None,
        "--report",
        "-r",
        help=(
            "Path to the repair report (.md) to apply. "
            "If omitted, uses the newest .deeplogic/repairs/repair-*.md."
        ),
    ),
    config: str | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to inspect_config.yaml. If omitted, looks for .deeplogic/inspect_config.yaml in cwd.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be overwritten without writing any file.",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip the confirmation prompt (useful in CI).",
    ),
) -> None:
    """Overwrite local artifacts with repaired content from a repair report.

    Takes the newest repair-*.md in .deeplogic/repairs/ (or --report), and for
    each entry writes the repaired content back to the source artifact path,
    backing up the original to <path>.bak first. Prompts for confirmation
    unless --yes is given.
    """
    # Step 1: Resolve config (for the .deeplogic dir location)
    try:
        loader = InspectConfigLoader(config, require_project_id=False)
        loader.load()
    except Exception as e:
        console.print(f"[red]✗ Configuration Error: {e}[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None

    repairs_dir = loader.config_path.parent / "repairs"

    # Step 2: Resolve the repair report
    report_path: Path | None = None
    if repair_report:
        report_path = Path(repair_report).expanduser().resolve()
        if not report_path.is_file():
            console.print(f"[red]✗ Repair report not found: {repair_report}[/red]")
            raise typer.Exit(code=EXIT_FAILURE)
    else:
        candidates = sorted(repairs_dir.glob("repair-*.md"), key=lambda p: p.stat().st_mtime)
        report_path = candidates[-1] if candidates else None
        if report_path is None:
            console.print(f"[red]✗ No repair report found in {repairs_dir}[/red]")
            console.print("  Run `deeplogic-cli inspect repair` first, or pass --report <path>.")
            raise typer.Exit(code=EXIT_FAILURE)

    # Step 3: Parse entries
    entries = _parse_repairs_markdown(report_path)
    if not entries:
        console.print(f"[red]✗ No repair entries parsed from {report_path}[/red]")
        raise typer.Exit(code=EXIT_FAILURE)

    # Step 4: Show plan and confirm
    console.print()
    console.print("[bold]Applying repair report[/]")
    console.print(f"  Report: {report_path}")
    console.print(f"  Entries: {len(entries)}")

    # Resolve allowed roots for path safety: project config dir + cwd
    project_root = loader.config_path.parent.parent.resolve()
    cwd_root = Path.cwd().resolve()
    allowed_roots = {project_root, cwd_root}

    # Pre-validate all paths before showing the plan
    safe_entries: list[dict] = []
    for entry in entries:
        target = Path(entry["artifact_path"]).resolve()
        # Security check: ensure target is within an allowed root
        is_safe = any(
            str(target).startswith(str(root) + os.sep) or target == root for root in allowed_roots
        )
        if not is_safe:
            console.print(f"[red]✗ Path traversal detected: {target} is outside project root[/red]")
            raise typer.Exit(code=EXIT_FAILURE)
        safe_entries.append(entry)

    console.print()
    for index, entry in enumerate(safe_entries, start=1):
        target = Path(entry["artifact_path"])
        exists = "overwrite" if target.exists() else "[yellow]new file[/yellow]"
        console.print(f"  {index}. {target} ({exists})")

    if dry_run:
        console.print("\n[dim]--dry-run: no files were written.[/dim]")
        return

    if not yes:
        console.print()
        try:
            confirmed = typer.confirm("Overwrite these files? (originals backed up to .bak)")
        except typer.Abort:
            console.print("\n[yellow]Cancelled.[/yellow]")
            raise typer.Exit() from None
        if not confirmed:
            console.print("\n[yellow]Cancelled.[/yellow]")
            raise typer.Exit()

    # Step 5: Write files with .bak backup (same policy as project repair)
    console.print()
    written = 0
    for entry in safe_entries:
        target = Path(entry["artifact_path"])
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                import shutil

                bak = target.with_suffix(target.suffix + ".bak")
                shutil.copy2(target, bak)

            tmp = target.with_suffix(target.suffix + ".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(entry["repaired_content"])
            tmp.replace(target)
        except OSError as e:
            console.print(f"[red]✗ {target}: {e}[/red]")
            continue
        backup_note = " (backup: *.bak)" if target.exists() else ""
        console.print(f"  [green]✓[/] {target}{backup_note}")
        written += 1

    console.print(f"\n[bold]Cover summary:[/] {written}/{len(safe_entries)} written")
    if written < len(safe_entries):
        raise typer.Exit(code=EXIT_FAILURE)
