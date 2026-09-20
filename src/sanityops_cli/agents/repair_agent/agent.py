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

"""Repair agent: generate repaired artifact content from a local defect report."""

from pathlib import Path
from typing import TYPE_CHECKING

import anyio
from rich.console import Console

from sanityops_cli.exceptions.base_exceptions import ValidationError

if TYPE_CHECKING:
    from sanityops_cli.logging.logger import Logger

# ============================================================================
# RepairAgent Class
# ============================================================================

console = Console()


class RepairAgent:
    """Runs an LLM agent that rewrites defective artifacts using the report.

    Mirrors ScannerAgent: builds a sanityops_agent parent agent with a tool
    registry (read + store_repair), feeds it the inspection report plus the
    artifact paths, and collects repairs via the shared-memory
    StoreRepairsTool.
    """

    def __init__(
        self,
        provider,
        max_loops: int = 30,
        timeout: int = 300,
        token_budget: int | None = None,
        llm_retries: int = 3,
        retry_delay: float = 65.0,
        verbose: bool = False,
        console: Console | None = None,
        logger: "Logger | None" = None,
    ):
        self.provider = provider
        self.max_loops = max_loops
        self.timeout = timeout
        self.token_budget = token_budget
        self.verbose = verbose
        self.console = console or Console()
        self.logger = logger
        # Rate-limit resilience: the server-side LLM proxy may cap requests
        # far below what one repair run needs (e.g. rpm_limit=1). The SDK's
        # own retry backs off only 1-2s, so we retry the whole run here with
        # a delay long enough to clear a per-minute quota.
        self.llm_retries = llm_retries
        self.retry_delay = retry_delay

    async def repair(
        self,
        report_path: str,
        artifacts: dict[str, list[str]],
        project_root: str,
    ) -> list[dict]:
        """Repair artifacts listed in the report.

        Retries the whole run on rate-limit errors (nothing to lose: repairs
        only materialize after store_repair, and a rate-limited run usually
        dies before storing anything).
        """
        last_error: Exception | None = None
        for attempt in range(self.llm_retries + 1):
            try:
                return await self._run_once(report_path, artifacts, project_root)
            except ValidationError as e:
                last_error = e
                if attempt >= self.llm_retries or not _is_rate_limit_error(e):
                    raise
                self.console.print(
                    f"  [yellow]⚠[/] LLM rate limited — waiting {self.retry_delay:.0f}s "
                    f"before retry {attempt + 1}/{self.llm_retries}..."
                )
                await anyio.sleep(self.retry_delay)
        assert last_error is not None
        raise last_error

    async def _run_once(
        self,
        report_path: str,
        artifacts: dict[str, list[str]],
        project_root: str,
    ) -> list[dict]:
        """Single repair attempt (see repair() for the retry wrapper)."""
        from sanityops_agent.agents import AgentFactory
        from sanityops_agent.core.agent import AgentConfig, TerminationReason
        from sanityops_agent.hooks.base import HookExecutor
        from sanityops_agent.tools import ToolRegistry

        from sanityops_cli.agents.repair_agent.prompts import REPAIR_AGENT_PROMPT
        from sanityops_cli.agents.repair_agent.tools.store_repairs_tool import StoreRepairsTool
        from sanityops_cli.agents.scanner_agent.tools.readfile_tool import FileReadTool

        report = Path(report_path).resolve()
        if not report.is_file():
            raise ValidationError(f"Report not found: {report_path}")

        all_paths = (
            artifacts.get("prompts", []) + artifacts.get("tools", []) + artifacts.get("skills", [])
        )
        if not all_paths:
            raise ValidationError("No artifacts configured to repair")

        for p in all_paths:
            if not Path(p).is_absolute() or not Path(p).exists():
                raise ValidationError(f"Artifact path invalid: {p}")

        # Deliberately NO TaskTool: repair must follow the artifact list
        # exactly, not spawn sub-agents to explore the project. Registering it
        # led agents to wander (listing directories, reading bogus paths) and
        # burn the whole token budget without storing a single repair.
        registry = ToolRegistry()
        registry.register(FileReadTool())
        registry.register(StoreRepairsTool())
        StoreRepairsTool.clear()

        artifact_lines: list[str] = []
        for kind, key in (("prompt", "prompts"), ("tool", "tools"), ("skill", "skills")):
            for p in artifacts.get(key) or []:
                artifact_lines.append(f"- type: {kind}, path: {p}")

        system_prompt = REPAIR_AGENT_PROMPT.format(
            report_path=str(report),
            project_root=project_root,
            artifact_list="\n".join(artifact_lines),
        )

        config_kwargs = {
            "max_loops": self.max_loops,
            "total_timeout": self.timeout,
            "system_prompt": system_prompt,
        }
        if self.token_budget:
            config_kwargs["token_budget"] = self.token_budget

        config = AgentConfig(**config_kwargs)

        hook_executor = HookExecutor()
        if self.verbose and self.logger:
            from sanityops_cli.agents.scanner_agent.hooks.progress_hook import ProgressHook
            hook_executor.register(
                ProgressHook(self.console, verbose=self.verbose, logger=self.logger)
            )

        factory = AgentFactory(
            provider=self.provider,
            config=config,
            tool_registry=registry,
            hook_executor=hook_executor,
        )
        agent = factory.create_parent_agent(system_prompt=system_prompt)

        if self.verbose:
            self.console.print()

        result = await agent.run(f"Repair artifacts listed in report {report}")

        if self.verbose:
            self.console.print()

        repairs = StoreRepairsTool.get_repairs()
        if result.termination_reason != TerminationReason.END_TURN:
            # Any termination after repairs were already stored is a partial
            # success: return collected repairs with a warning instead of
            # discarding them (budget/loop exhaustion or a mid-run LLM error).
            if repairs:
                if self.verbose:
                    self.console.print(
                        f"  [yellow]⚠[/] Agent stopped ({result.termination_reason.value}) "
                        f"after {len(repairs)} repair(s) were collected"
                    )
                return repairs
            error_msg = result.error or f"Agent terminated: {result.termination_reason.value}"
            if result.error_detail:
                error_detail_str = "\n".join(
                    f"  - {e.error_type}: {e.message}" for e in result.error_detail
                )
                error_msg += f"\nError Detail:\n{error_detail_str}"
            raise ValidationError(f"Agent execution failed: {error_msg}")

        return repairs

    def repair_sync(
        self,
        report_path: str,
        artifacts: dict[str, list[str]],
        project_root: str,
    ) -> list[dict]:
        """Synchronous wrapper around repair()."""
        return anyio.run(self.repair, report_path, artifacts, project_root)


def _is_rate_limit_error(exc: BaseException) -> bool:
    """Best-effort detection of a server-side rate limit / throttling error.

    The LLM proxy (litellm) surfaces these as 429 with `throttling_error`, or
    as 5xx wrappers whose message still mentions the rate limit. Matching on
    the text markers keeps this working across provider SDKs.
    """
    text = str(exc).lower()
    markers = (
        "429",
        "rate limit",
        "ratelimiterror",
        "throttling_error",
        "too many requests",
        "no deployments available",
    )
    return any(marker in text for marker in markers)
