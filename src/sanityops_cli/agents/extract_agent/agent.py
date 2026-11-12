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

"""ExtractAgent — skill-driven artifact extraction (design §5).

A thin wrapper around the sanityops-agent loop (same pattern as the other
CLI agents). The agent loads the vendored ``pre-inspect-extract`` skill on
its first step and reports artifacts through ``store_artifacts``; this class
only assembles the tool registry, injects the compaction-safe context, and
finalizes the records after the run.
"""

from __future__ import annotations

from pathlib import Path

import anyio
from sanityops_agent.agents import AgentFactory
from sanityops_agent.core.agent import AgentConfig, TerminationReason
from sanityops_agent.core.context import CompactConfig
from sanityops_agent.core.message import Message, Role
from sanityops_agent.hooks.base import HookExecutor
from sanityops_agent.tools.registry import ToolRegistry

from sanityops_cli.agents.extract_agent.prompts import (
    build_system_appendix,
    build_task_message,
)
from sanityops_cli.agents.extract_agent.tools.read_file_tool import ScopedReadFileTool
from sanityops_cli.agents.extract_agent.tools.store_artifacts_tool import (
    StoreArtifactsTool,
)
from sanityops_cli.agents.extract_agent.tools.tool_registry import (
    extract_tool_candidates,
)
from sanityops_cli.agents.progress_hook import LoggingProgressHook
from sanityops_cli.agents.termination import _termination_message
from sanityops_cli.inspect_pipeline.context_guard import ArtifactAwareContext
from sanityops_cli.inspect_pipeline.models import ExtractionMeta, ExtractionResult
from sanityops_cli.inspect_pipeline.skill_runtime import attach_skill_tools

#: Hard cap on manifest size before the agent even starts (design §6.6).
MAX_MANIFEST_FILES = 100

#: Loops scale with manifest size: reads + chunked deliveries + corrections.
DEFAULT_MAX_LOOPS = 80


class ExtractionFailedError(RuntimeError):
    """The extraction agent did not finish cleanly (design §9: exit 2)."""

    def __init__(self, message: str, detail: list[str] | None = None) -> None:
        super().__init__(message)
        self.detail = detail or []


class IncompleteExtractionError(ExtractionFailedError):
    """Chunk streams that never reached final=true (design §5.3)."""

    def __init__(self, incomplete_keys: list[str]) -> None:
        listing = "\n".join(f"  - {key}" for key in incomplete_keys)
        super().__init__(
            f"{len(incomplete_keys)} artifact record(s) are incomplete "
            f"(chunk stream never finished):\n{listing}"
        )
        self.incomplete_keys = incomplete_keys


class ExtractAgent:
    """Run the extraction stage over an explicit artifact manifest."""

    def __init__(
        self,
        provider,
        *,
        skills_dir: Path,
        max_loops: int = DEFAULT_MAX_LOOPS,
        timeout: int = 1800,
        token_budget: int = 200_000,
        verbose: bool = False,
        console=None,
        logger=None,
        report_language: str = "en",
    ) -> None:
        self.provider = provider
        self.skills_dir = Path(skills_dir)
        self.max_loops = max_loops
        self.timeout = timeout
        self.token_budget = token_budget
        self.verbose = verbose
        self.console = console
        self.logger = logger
        self.report_language = report_language

    async def extract(
        self,
        prompts: list[str],
        tools: list[str],
        skills: list[str],
        project_root: Path | None = None,
    ) -> ExtractionResult:
        manifest = {"prompts": prompts, "tools": tools, "skills": skills}
        total_files = sum(len(paths) for paths in manifest.values())
        if total_files > MAX_MANIFEST_FILES:
            raise ExtractionFailedError(
                f"manifest has {total_files} files (limit {MAX_MANIFEST_FILES}); "
                f"split the inspect config into multiple runs"
            )

        store = StoreArtifactsTool()
        candidates, unresolved_tools = extract_tool_candidates(tools)
        store.register_candidates(candidates)

        allowed_roots = self._allowed_roots(manifest, project_root)
        registry = ToolRegistry()
        registry.register(ScopedReadFileTool(allowed_roots=allowed_roots))
        registry.register(store)
        attach_skill_tools(registry, self.skills_dir)

        system_prompt = build_system_appendix(
            [str(root) for root in allowed_roots], self.report_language
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

        # Pre-assign the compaction-safe context (BaseAgent.run only builds
        # its own when context is None) and attach the system prompt manually,
        # because the framework skips it for pre-assigned contexts. Use the
        # agent's own config: the factory enhanced it with the Available
        # Skills manifest, which the plain appendix lacks.
        agent.context = ArtifactAwareContext(
            compact_config=CompactConfig(
                trigger_token_threshold=int(self.token_budget * 0.8),
                preserve_recent_count=5,
            )
        )
        if agent.config.system_prompt:
            await agent.context.add_message(
                Message.from_text(Role.SYSTEM, agent.config.system_prompt)
            )

        task = build_task_message(manifest, candidates)
        result = await agent.run(task)

        if result.termination_reason != TerminationReason.END_TURN:
            detail = [e.message for e in result.error_detail]
            raise ExtractionFailedError(
                _termination_message("extraction", result.termination_reason, detail),
                detail=detail,
            )

        artifacts, incomplete = store.finalize()
        if incomplete:
            raise IncompleteExtractionError(incomplete)

        return ExtractionResult(
            artifacts=artifacts,
            references=store.references,
            attribution=store.attribution,
            meta=ExtractionMeta(
                loops_used=result.loops_used,
                tokens_used=result.tokens_used,
                time_elapsed=result.time_elapsed,
                deterministic_candidates=len(candidates),
                resends=store.resend_log,
            ),
        )

    def extract_sync(
        self,
        prompts: list[str],
        tools: list[str],
        skills: list[str],
        project_root: Path | None = None,
    ) -> ExtractionResult:
        return anyio.run(self.extract, prompts, tools, skills, project_root)

    def _allowed_roots(
        self, manifest: dict[str, list[str]], project_root: Path | None
    ) -> list[Path]:
        """Read containment roots: project root + every manifest parent dir.

        Config artifact paths may live outside cwd, so each path's parent is
        an allowed root too; the materialized skills directory is included
        because the skill hint points the agent at reference files in it.
        """
        roots: list[Path] = []
        if project_root is not None:
            roots.append(Path(project_root).resolve())
        for paths in manifest.values():
            for path in paths:
                roots.append(Path(path).resolve().parent)
        roots.append(self.skills_dir.resolve())
        unique: list[Path] = []
        for root in roots:
            if root not in unique:
                unique.append(root)
        return unique
