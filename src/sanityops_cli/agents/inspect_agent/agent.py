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
from sanityops_agent.core.context import CompactConfig
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
from sanityops_cli.agents.termination import _termination_message
from sanityops_cli.inspect_pipeline.context_guard import ArtifactAwareContext
from sanityops_cli.inspect_pipeline.skill_runtime import attach_skill_tools

#: Design §6.6: the inspection run loads the skill body plus domain files;
#: below this floor compaction would start evicting checklists mid-stage.
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
        verbose: bool = False,
        console=None,
        logger=None,
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
        self.logger = logger
        self.report_language = report_language
        if token_budget < MIN_TOKEN_BUDGET:
            token_budget = MIN_TOKEN_BUDGET  # design §6.6: floor, clamped
        self.token_budget = token_budget

        self.report_tool = WriteReportTool()

    async def inspect(self) -> InspectionOutcome:
        # The agent reads vendor skill references (path hints) and nothing else.
        registry = ToolRegistry()
        registry.register(ScopedReadFileTool(allowed_roots=[self.skills_dir.resolve()]))
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
        if self.verbose or self.logger:
            hook_executor.register(
                LoggingProgressHook(
                    self.console, logger=self.logger, verbose=self.verbose
                )
            )

        factory = AgentFactory(
            provider=self.provider,
            config=config,
            tool_registry=registry,
            hook_executor=hook_executor,
            inject_skill_info=True,
        )
        agent = factory.create_parent_agent(system_prompt=system_prompt)

        # Pre-assign the compaction-safe context; the framework skips its own
        # system-prompt injection for pre-assigned contexts, so add the
        # factory-enhanced prompt manually.
        agent.context = ArtifactAwareContext(
            compact_config=CompactConfig(
                trigger_token_threshold=int(config.token_budget * 0.8),
                preserve_recent_count=5,
            )
        )
        if agent.config.system_prompt:
            await agent.context.add_message(
                Message.from_text(Role.SYSTEM, agent.config.system_prompt)
            )

        result = await agent.run(build_task_message(self.injection_payload))

        if result.termination_reason != TerminationReason.END_TURN:
            detail = [e.message for e in result.error_detail]
            partial = InspectionOutcome(
                report_markdown=self.report_tool.render(),
                tail_text=result.text,
                section_parts=self.report_tool.section_parts(),
                missing_stages=self.report_tool.missing_stages(),
                termination_reason=result.termination_reason.value,
                loops_used=result.loops_used,
                tokens_used=result.tokens_used,
                time_elapsed=result.time_elapsed,
            )
            raise InspectionFailedError(
                _termination_message("inspection", result.termination_reason, detail),
                detail=detail,
                partial=partial,
            )

        return InspectionOutcome(
            report_markdown=self.report_tool.render(),
            tail_text=result.text,
            section_parts=self.report_tool.section_parts(),
            missing_stages=self.report_tool.missing_stages(),
            termination_reason=result.termination_reason.value,
            loops_used=result.loops_used,
            tokens_used=result.tokens_used,
            time_elapsed=result.time_elapsed,
        )

    def inspect_sync(self) -> InspectionOutcome:
        return anyio.run(self.inspect)
