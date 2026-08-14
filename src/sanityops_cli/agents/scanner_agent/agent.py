from pathlib import Path

import anyio
from rich.console import Console

from sanityops_cli.agents.scanner_agent.models.finding import FindingsResult
from sanityops_cli.agents.scanner_agent.prompts import (
    # New analyzer prompts
    ANALYZE_PARENT_PROMPT,
    INSPECT_PARENT_PROMPT,
    PROMPT_ANALYZER_PROMPT,
    PROMPT_FINDER_RULES,
    SKILL_ANALYZER_PROMPT,
    SKILL_FINDER_RULES,
    TOOL_ANALYZER_PROMPT,
    TOOL_FINDER_RULES,
)
from sanityops_cli.exceptions.base_exceptions import ValidationError
from sanityops_cli.logging.logger import Logger

# ============================================================================
# ScannerAgent Class
# ============================================================================

console = Console()


class ScannerAgent:

    def __init__(
        self,
        provider,
        max_loops: int = 30,
        timeout: int = 120,
        verbose: bool = False,
        console: Console | None = None,
        logger: Logger | None = None,
    ):
        self.provider = provider
        self.max_loops = max_loops
        self.timeout = timeout
        self.verbose = verbose
        self.console = console or Console()
        self.logger = logger

    async def scan(
        self,
        directory: str,
        depth: int = 5,
    ) -> FindingsResult:
        path = Path(directory).resolve()
        if not path.exists() or not path.is_dir():
            raise ValidationError(f"Directory does not exist: {directory}")

        abs_directory = str(path)

        from sanityops_agent.agents import AgentFactory
        from sanityops_agent.core.agent import AgentConfig, TerminationReason
        from sanityops_agent.hooks.base import HookExecutor
        from sanityops_agent.tools import ToolRegistry
        from sanityops_agent.tools.builtins import GlobTool, TaskTool

        from sanityops_cli.agents.scanner_agent.tools.grep_tool import GrepTool
        from sanityops_cli.agents.scanner_agent.tools.listfiles_tool import ListFilesTool
        from sanityops_cli.agents.scanner_agent.tools.readfile_tool import FileReadTool
        from sanityops_cli.agents.scanner_agent.tools.storefindings_tool import StoreFindingsTool

        registry = ToolRegistry()
        registry.register(FileReadTool())
        registry.register(ListFilesTool())
        registry.register(GlobTool())
        registry.register(GrepTool())
        registry.register(TaskTool())
        registry.register(StoreFindingsTool())

        StoreFindingsTool._findings.clear()

        system_prompt = self._build_system_prompt(abs_directory, depth)

        config = AgentConfig(
            max_loops=self.max_loops,
            total_timeout=self.timeout,
            system_prompt=system_prompt,
        )

        hook_executor = HookExecutor()
        if self.verbose:
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

        result = await agent.run(f"Inspect {abs_directory}")

        if self.verbose:
            self.console.print()

        if result.termination_reason != TerminationReason.END_TURN:
            error_msg = result.error or f"Agent terminated: {result.termination_reason.value}"
            if result.error_detail:
                error_detail_str = "\n".join(
                    f"  - {e.error_type}: {e.message}"
                    for e in result.error_detail
                )
                error_msg += f"\nError Detail:\n{error_detail_str}"
            raise ValidationError(f"Agent execution failed: {error_msg}")

        return self._build_result(abs_directory, result)

    async def analyze_files(
        self,
        prompts: list[str],
        tools: list[str],
        skills: list[str],
    ) -> FindingsResult:
        """Analyze explicit artifact files and extract structured metadata.

        Args:
            prompts: List of absolute paths to prompt files
            tools: List of absolute paths to tool files
            skills: List of absolute paths to skill.md files

        Returns:
            FindingsResult with structured content for each artifact
        """
        from sanityops_agent.agents import AgentFactory
        from sanityops_agent.core.agent import AgentConfig, TerminationReason
        from sanityops_agent.hooks.base import HookExecutor
        from sanityops_agent.tools import ToolRegistry
        from sanityops_agent.tools.builtins import GlobTool, TaskTool

        from sanityops_cli.agents.scanner_agent.tools.grep_tool import GrepTool
        from sanityops_cli.agents.scanner_agent.tools.listfiles_tool import ListFilesTool
        from sanityops_cli.agents.scanner_agent.tools.readfile_tool import FileReadTool
        from sanityops_cli.agents.scanner_agent.tools.storefindings_tool import StoreFindingsTool

        # Validate at least one artifact provided
        if not prompts and not tools and not skills:
            return FindingsResult(
                directory="",
                skills=[],
                tools=[],
                prompts=[],
                meta={"time_elapsed": 0, "loops_used": 0, "tokens_used": 0}
            )

        # Validate all paths are absolute and exist
        for path_list, name in [(prompts, "prompts"), (tools, "tools"), (skills, "skills")]:
            for p in path_list:
                path = Path(p)
                if not path.is_absolute():
                    raise ValidationError(f"{name} path must be absolute: {p}")
                if not path.exists():
                    raise ValidationError(f"{name} path does not exist: {p}")

        # Build tool registry
        registry = ToolRegistry()
        registry.register(FileReadTool())
        registry.register(ListFilesTool())
        registry.register(GlobTool())
        registry.register(GrepTool())
        registry.register(TaskTool())
        registry.register(StoreFindingsTool())

        # Clear previous findings
        StoreFindingsTool._findings.clear()

        # Build system prompt
        system_prompt = self._build_analyze_prompt(prompts, tools, skills)

        config = AgentConfig(
            max_loops=self.max_loops,
            total_timeout=self.timeout,
            system_prompt=system_prompt,
        )

        # Setup hooks
        hook_executor = HookExecutor()
        if self.verbose:
            from sanityops_cli.agents.scanner_agent.hooks.progress_hook import ProgressHook
            hook_executor.register(
                ProgressHook(self.console, verbose=self.verbose, logger=self.logger)
            )

        # Create and run agent
        factory = AgentFactory(
            provider=self.provider,
            config=config,
            tool_registry=registry,
            hook_executor=hook_executor,
        )
        agent = factory.create_parent_agent(system_prompt=system_prompt)

        if self.verbose:
            self.console.print()

        result = await agent.run("Analyze provided artifact files")

        if self.verbose:
            self.console.print()

        if result.termination_reason != TerminationReason.END_TURN:
            error_msg = result.error or f"Agent terminated: {result.termination_reason.value}"
            if result.error_detail:
                error_detail_str = "\n".join(
                    f"  - {e.error_type}: {e.message}"
                    for e in result.error_detail
                )
                error_msg += f"\nError Detail:\n{error_detail_str}"
            raise ValidationError(f"Agent execution failed: {error_msg}")

        return self._build_result("", result)

    def analyze_files_sync(
        self,
        prompts: list[str],
        tools: list[str],
        skills: list[str],
    ) -> FindingsResult:
        """Synchronous wrapper for analyze_files."""
        return anyio.run(self.analyze_files, prompts, tools, skills)

    def scan_sync(
        self,
        directory: str,
        depth: int = 5,
    ) -> FindingsResult:
        return anyio.run(self.scan, directory, depth)

    def _build_system_prompt(self, directory: str, depth: int) -> str:
        formatted_skill_rules = SKILL_FINDER_RULES.format(
            directory=directory, depth=depth
        )
        formatted_tool_rules = TOOL_FINDER_RULES.format(
            directory=directory, depth=depth
        )
        formatted_prompt_rules = PROMPT_FINDER_RULES.format(
            directory=directory, depth=depth
        )
        return INSPECT_PARENT_PROMPT.format(
            directory=directory,
            depth=depth,
            SKILL_FINDER_RULES=formatted_skill_rules,
            TOOL_FINDER_RULES=formatted_tool_rules,
            PROMPT_FINDER_RULES=formatted_prompt_rules,
        )

    def _build_analyze_prompt(
        self,
        prompts: list[str],
        tools: list[str],
        skills: list[str],
    ) -> str:
        """Build system prompt for file analysis mode."""
        # Format file lists as bullet points
        skill_files_str = "\n".join(f"- {p}" for p in skills) if skills else "(none)"
        tool_files_str = "\n".join(f"- {p}" for p in tools) if tools else "(none)"
        prompt_files_str = "\n".join(f"- {p}" for p in prompts) if prompts else "(none)"

        formatted_skill_analyzer = SKILL_ANALYZER_PROMPT.format(
            skill_files=skill_files_str
        )
        formatted_tool_analyzer = TOOL_ANALYZER_PROMPT.format(
            tool_files=tool_files_str
        )
        formatted_prompt_analyzer = PROMPT_ANALYZER_PROMPT.format(
            prompt_files=prompt_files_str
        )

        return ANALYZE_PARENT_PROMPT.format(
            skill_count=len(skills),
            tool_count=len(tools),
            prompt_count=len(prompts),
            SKILL_ANALYZER_PROMPT=formatted_skill_analyzer,
            TOOL_ANALYZER_PROMPT=formatted_tool_analyzer,
            PROMPT_ANALYZER_PROMPT=formatted_prompt_analyzer,
        )

    def _build_result(
        self,
        directory: str,
        agent_result,
    ) -> FindingsResult:
        from sanityops_cli.agents.scanner_agent.models.finding import FindingType
        from sanityops_cli.agents.scanner_agent.tools.storefindings_tool import StoreFindingsTool

        findings = StoreFindingsTool._findings
        skills = [f for f in findings if f.type == FindingType.SKILL]
        tools = [f for f in findings if f.type == FindingType.TOOL]
        prompts = [f for f in findings if f.type == FindingType.PROMPT]

        return FindingsResult(
            directory=directory,
            skills=skills,
            tools=tools,
            prompts=prompts,
            meta={
                "time_elapsed": agent_result.time_elapsed,
                "loops_used": agent_result.loops_used,
                "tokens_used": agent_result.tokens_used,
            }
        )
