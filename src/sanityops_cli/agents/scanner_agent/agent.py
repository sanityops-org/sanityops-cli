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

import re
from pathlib import Path

import anyio
import yaml
from rich.console import Console

from sanityops_cli.agents.scanner_agent.models.finding import (
    Finding,
    FindingsResult,
    FindingType,
    PromptContent,
    Section,
    SkillContent,
)
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
        token_budget: int = 200000,
        verbose: bool = False,
        console: Console | None = None,
        logger: Logger | None = None,
    ):
        self.provider = provider
        self.max_loops = max_loops
        self.timeout = timeout
        self.token_budget = token_budget
        self.verbose = verbose
        self.console = console or Console()
        self.logger: Logger | None = logger

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
            token_budget=self.token_budget,
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
            token_budget=self.token_budget,
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

        findings_result = self._build_result("", result)

        # Deterministic artifact capture: LLM transcription of prompt and
        # skill files is lossy (random truncation/frontmatter loss), so
        # replace the LLM's findings for those artifacts with content read
        # verbatim from disk.
        prompt_findings: list[Finding] = []
        for prompt_path in prompts:
            try:
                content = Path(prompt_path).read_text(encoding="utf-8")
            except (FileNotFoundError, PermissionError, UnicodeDecodeError, IsADirectoryError) as e:
                raise ValidationError(f"Failed to read prompt file {prompt_path}: {e}") from e
            prompt_findings.append(
                Finding(
                    type=FindingType.PROMPT,
                    relative=prompt_path,  # Absolute path (validated upstream)
                    content=PromptContent(content=content),
                )
            )
        findings_result.prompts = prompt_findings

        skill_findings: list[Finding] = []
        for skill_path in skills:
            try:
                raw = Path(skill_path).read_text(encoding="utf-8")
            except (FileNotFoundError, PermissionError, UnicodeDecodeError, IsADirectoryError) as e:
                raise ValidationError(f"Failed to read skill file {skill_path}: {e}") from e

            # Parse frontmatter: handle both standard format and EOF edge case
            # Standard: "---\n<yaml>\n---\n<body>"
            # EOF case: "---\n<yaml>\n---" (no trailing newline)
            frontmatter: dict = {}
            body = raw
            if raw.startswith("---"):
                # Try standard pattern first, then EOF pattern
                match = re.match(r"^---\s*\n(.*?)\n---\s*\n?", raw, re.DOTALL)
                if match:
                    yaml_content = match.group(1)
                    try:
                        parsed = yaml.safe_load(yaml_content)
                        if isinstance(parsed, dict):
                            frontmatter = parsed
                    except yaml.YAMLError as e:
                        # Log warning but continue with empty frontmatter
                        if self.logger:
                            self.logger.warning(f"YAML parse error in {skill_path}: {e}")
                        frontmatter = {}
                    body = raw[match.end():]

            sections: list[Section] = []
            current_title = "Overview"
            current_lines: list[str] = []
            for line in body.split("\n"):
                if line.startswith("## "):
                    if current_lines:
                        sections.append(
                            Section(
                                title=current_title,
                                content="\n".join(current_lines).strip(),
                            )
                        )
                    current_title = line[3:].strip()
                    current_lines = []
                else:
                    current_lines.append(line)
            if current_lines:
                sections.append(
                    Section(
                        title=current_title,
                        content="\n".join(current_lines).strip(),
                    )
                )

            skill_findings.append(
                Finding(
                    type=FindingType.SKILL,
                    relative=skill_path,  # Absolute path (validated upstream)
                    content=SkillContent(
                        name=str(frontmatter.get("name", "")),
                        description=str(frontmatter.get("description", "")),
                        frontmatter=frontmatter,
                        sections=sections,
                    ),
                )
            )
        findings_result.skills = skill_findings

        return findings_result

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
