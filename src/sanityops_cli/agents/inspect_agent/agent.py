"""InspectAgent — skill-driven seven-stage inspection (design §6).

Same wrapper pattern as ExtractAgent: the agent loads the vendored
``sanityops-inspect-lite`` skill on demand (SKILL.md first, then only the
domain checklists the artifact set needs), applies the checks, and reports
incrementally through ``write_report``. The CLI renders the assembled
markdown and parses the tail JSON with a fail-closed ladder.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import anyio
from sanityops_agent.agents import AgentFactory
from sanityops_agent.core.agent import AgentConfig, TerminationReason
from sanityops_agent.core.message import Message, Role
from sanityops_agent.hooks.base import HookExecutor
from sanityops_agent.tools.registry import ToolRegistry

from sanityops_cli.agents.extract_agent.tools.read_file_tool import ScopedReadFileTool
from sanityops_cli.agents.inspect_agent.prompts import (
    build_system_appendix,
    build_task_message,
)
from sanityops_cli.agents.inspect_agent.tools.write_report_tool import WriteReportTool
from sanityops_cli.agents.progress_hook import LoggingProgressHook
from sanityops_cli.inspect_pipeline.context_guard import (
    ArtifactAwareContext,
    ContextLimitedProvider,
)
from sanityops_cli.inspect_pipeline.skill_runtime import (
    attach_skill_tools,
    rewrite_reference_for_cli,
)
from sanityops_cli.inspect_pipeline.token_estimator import DEFAULT_CONTEXT_WINDOW

#: Minimum cumulative usage budget for the inspection stage.
MIN_TOKEN_BUDGET = 300_000

DEFAULT_MAX_LOOPS = 80


class InspectionFailedError(RuntimeError):
    """The inspection agent did not finish cleanly (design §9: exit 2)."""

    def __init__(
        self,
        message: str,
        detail: list[str] | None = None,
        partial: InspectionOutcome | None = None,
    ) -> None:
        super().__init__(message)
        self.detail = detail or []
        #: Whatever the report tool had already received when the agent died —
        #: the CLI persists it best-effort (design §9, "报告尽力落盘").
        self.partial = partial


@dataclass
class InspectionOutcome:
    """Everything the CLI needs after the inspection run."""

    report_markdown: str
    tail_text: str  # final assistant message; expected to hold the tail JSON
    section_parts: dict[str, list[str]] = field(default_factory=dict)
    missing_stages: list[str] = field(default_factory=list)
    termination_reason: str = ""
    loops_used: int = 0
    tokens_used: int = 0
    time_elapsed: float = 0.0
    part_findings: list[dict] | None = None
    unstructured_stages: list[str] = field(default_factory=list)


class InspectAgent:
    """Run the seven-stage inspection over the injected extraction IR."""

    def __init__(
        self,
        provider,
        *,
        skills_dir: Path,
        injection_payload: str,
        header_data: dict[str, str],
        attribution: str,
        attribution_note: str = "",
        qc_candidates: list[dict] | None = None,
        max_loops: int = DEFAULT_MAX_LOOPS,
        timeout: int = 1800,
        token_budget: int = MIN_TOKEN_BUDGET,
        context_window: int = DEFAULT_CONTEXT_WINDOW,
        verbose: bool = False,
        console=None,
        log_manager=None,
        report_language: str = "en",
    ) -> None:
        self.provider = provider
        self.skills_dir = Path(skills_dir)
        self.injection_payload = injection_payload
        self.header_data = header_data
        self.attribution = attribution
        self.attribution_note = attribution_note
        self.qc_candidates = qc_candidates or []
        self.max_loops = max_loops
        self.timeout = timeout
        self.verbose = verbose
        self.console = console
        self.log_manager = log_manager
        self.report_language = report_language
        if token_budget < MIN_TOKEN_BUDGET:
            token_budget = MIN_TOKEN_BUDGET  # design §6.6: floor, clamped
        self.token_budget = token_budget
        self.context_window = context_window

        self.report_tool = WriteReportTool(require_findings=True)

    async def inspect(self) -> InspectionOutcome:
        # The agent reads vendor skill references (path hints) and nothing else.
        registry = ToolRegistry()
        registry.register(
            ScopedReadFileTool(
                allowed_roots=[self.skills_dir.resolve()],
                content_transform=rewrite_reference_for_cli,
            )
        )
        registry.register(self.report_tool)
        attach_skill_tools(registry, self.skills_dir)

        system_prompt = build_system_appendix(
            header_data=self.header_data,
            attribution=self.attribution,
            attribution_note=self.attribution_note,
            qc_candidates=self.qc_candidates,
            report_language=self.report_language,
        )
        config = AgentConfig(
            max_loops=self.max_loops,
            total_timeout=self.timeout,
            token_budget=self.token_budget,
            system_prompt=system_prompt,
        )

        hook_executor = HookExecutor()
        progress_hook = LoggingProgressHook(
            self.console,
            log_manager=self.log_manager,
            verbose=self.verbose,
            token_budget=self.token_budget,
            stage="Inspection",
        )
        if self.verbose or self.log_manager:
            hook_executor.register(progress_hook)

        context = ArtifactAwareContext(self.context_window)
        factory = AgentFactory(
            provider=ContextLimitedProvider(self.provider, context),
            config=config,
            tool_registry=registry,
            hook_executor=hook_executor,
            inject_skill_info=True,
        )
        agent = factory.create_parent_agent(system_prompt=system_prompt)

        # Pre-assign the compaction-safe context; the framework skips its own
        # system-prompt injection for pre-assigned contexts, so add the
        # factory-enhanced prompt manually.
        agent.context = context
        if agent.config.system_prompt:
            await agent.context.add_message(
                Message.from_text(Role.SYSTEM, agent.config.system_prompt)
            )

        try:
            result = await agent.run(build_task_message(self.injection_payload))
        finally:
            progress_hook.stop_waiting()

        outcome = InspectionOutcome(
            report_markdown=self.report_tool.render(),
            tail_text=result.text,
            section_parts=self.report_tool.section_parts(),
            missing_stages=self.report_tool.missing_stages(),
            termination_reason=result.termination_reason.value,
            loops_used=result.loops_used,
            tokens_used=max(result.tokens_used, progress_hook.tokens_used),
            time_elapsed=result.time_elapsed,
            part_findings=self.report_tool.findings(),
            unstructured_stages=self.report_tool.unstructured_stages(),
        )
        if result.termination_reason != TerminationReason.END_TURN:
            detail = [e.message for e in result.error_detail]
            raise InspectionFailedError(
                f"inspection agent terminated abnormally: "
                f"{result.termination_reason.value}"
                + (f"; last error: {detail[-1]}" if detail else ""),
                detail=detail,
                partial=outcome,
            )

        return outcome

    def inspect_sync(self) -> InspectionOutcome:
        return anyio.run(self.inspect)
