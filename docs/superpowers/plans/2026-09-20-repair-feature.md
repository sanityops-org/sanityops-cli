# Repair Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate local repair functionality from deeplogic-cli to sanityops-cli, enabling users to generate repaired artifact content from inspection reports.

**Architecture:** Create a RepairAgent that reads inspection reports and uses an LLM to rewrite defective artifacts. The agent uses StoreRepairsTool to collect repairs, which are then written to a markdown report file.

**Tech Stack:** Python, Typer, Rich, sanityops-agent, anyio

## Global Constraints

- All output content must be in English
- No TaskTool in repair agent (prevents wandering and token waste)
- Rate-limit retry: 3 retries with 65-second delay
- Token budget auto-scales: 300,000 + 150,000 * artifact_count
- Partial success: return collected repairs even if agent terminates early
- Import path: `sanityops_agent` (not `aidynamic_agent`)
- Exit codes: reuse existing from `constants/exit_codes.py`

---

## File Structure

### New Files
- `src/sanityops_cli/agents/repair_agent/__init__.py` - Package init
- `src/sanityops_cli/agents/repair_agent/agent.py` - RepairAgent class
- `src/sanityops_cli/agents/repair_agent/prompts.py` - System prompt
- `src/sanityops_cli/agents/repair_agent/tools/__init__.py` - Tools package init
- `src/sanityops_cli/agents/repair_agent/tools/store_repairs_tool.py` - StoreRepairsTool
- `tests/unit/agents/repair_agent/__init__.py` - Test package init
- `tests/unit/agents/repair_agent/test_store_repairs_tool.py` - Tool tests
- `tests/unit/agents/repair_agent/test_agent.py` - Agent tests
- `tests/commands/test_inspect_repair.py` - Command integration tests

### Modified Files
- `src/sanityops_cli/commands/inspect.py` - Add repair subcommand

---

### Task 1: Create Repair Agent Package Structure

**Files:**
- Create: `src/sanityops_cli/agents/repair_agent/__init__.py`
- Create: `src/sanityops_cli/agents/repair_agent/tools/__init__.py`
- Create: `tests/unit/agents/repair_agent/__init__.py`

**Interfaces:**
- Produces: Empty `__init__.py` files to establish package structure

- [ ] **Step 1: Create repair_agent package directories**

```python
# src/sanityops_cli/agents/repair_agent/__init__.py
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

"""Repair agent for generating fixed artifact content from inspection reports."""

from .agent import RepairAgent

__all__ = ["RepairAgent"]
```

```python
# src/sanityops_cli/agents/repair_agent/tools/__init__.py
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

"""Repair agent tools."""

from .store_repairs_tool import StoreRepairsTool

__all__ = ["StoreRepairsTool"]
```

```python
# tests/unit/agents/repair_agent/__init__.py
# Test package for repair_agent
```

- [ ] **Step 2: Create the directories and files**

```bash
mkdir -p src/sanityops_cli/agents/repair_agent/tools
mkdir -p tests/unit/agents/repair_agent
```

- [ ] **Step 3: Write the files**

Write all three `__init__.py` files with the content above.

- [ ] **Step 4: Commit**

```bash
git add src/sanityops_cli/agents/repair_agent/ tests/unit/agents/repair_agent/
git commit -m "feat(repair): add repair agent package structure"
```

---

### Task 2: Implement StoreRepairsTool

**Files:**
- Create: `src/sanityops_cli/agents/repair_agent/tools/store_repairs_tool.py`
- Create: `tests/unit/agents/repair_agent/test_store_repairs_tool.py`

**Interfaces:**
- Consumes: `sanityops_agent.tools.base.Tool`, `sanityops_agent.tools.base.ToolResult`
- Produces: `StoreRepairsTool` class with:
  - `name = "store_repair"`
  - `execute(artifact_type, artifact_path, repaired_content, summary) -> ToolResult`
  - `get_repairs() -> list[dict]` (classmethod)
  - `clear() -> None` (classmethod)

- [ ] **Step 1: Write failing tests for StoreRepairsTool**

```python
# tests/unit/agents/repair_agent/test_store_repairs_tool.py
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

import pytest

from sanityops_cli.agents.repair_agent.tools.store_repairs_tool import StoreRepairsTool


class TestStoreRepairsTool:
    """Tests for StoreRepairsTool."""

    def setup_method(self):
        """Clear repairs before each test."""
        StoreRepairsTool.clear()

    def test_tool_attributes(self):
        """Tool has correct name and description."""
        tool = StoreRepairsTool()
        assert tool.name == "store_repair"
        assert "repaired" in tool.description.lower()
        assert "artifact" in tool.description.lower()

    def test_add_repair_success(self):
        """Adding a valid repair succeeds."""
        tool = StoreRepairsTool()
        result = tool._add_repair(
            artifact_type="prompt",
            artifact_path="/abs/path/to/prompt.md",
            repaired_content="# Fixed prompt content",
            summary="Fixed ambiguous pronouns",
        )
        assert result.success is True
        assert "added" in result.content.lower()
        assert len(StoreRepairsTool.get_repairs()) == 1

    def test_add_repair_updates_existing(self):
        """Adding same artifact twice updates the entry."""
        tool = StoreRepairsTool()
        tool._add_repair(
            artifact_type="prompt",
            artifact_path="/abs/path/to/prompt.md",
            repaired_content="version 1",
            summary="First fix",
        )
        tool._add_repair(
            artifact_type="prompt",
            artifact_path="/abs/path/to/prompt.md",
            repaired_content="version 2",
            summary="Second fix",
        )
        repairs = StoreRepairsTool.get_repairs()
        assert len(repairs) == 1
        assert repairs[0]["repaired_content"] == "version 2"

    def test_add_repair_rejects_invalid_type(self):
        """Invalid artifact_type is rejected."""
        tool = StoreRepairsTool()
        result = tool._add_repair(
            artifact_type="invalid_type",
            artifact_path="/abs/path/to/file.md",
            repaired_content="content",
            summary="summary",
        )
        assert result.success is False
        assert "invalid" in result.error.lower()

    def test_add_repair_rejects_relative_path(self):
        """Relative path is rejected."""
        tool = StoreRepairsTool()
        result = tool._add_repair(
            artifact_type="prompt",
            artifact_path="relative/path.md",
            repaired_content="content",
            summary="summary",
        )
        assert result.success is False
        assert "absolute" in result.error.lower()

    def test_add_repair_rejects_empty_content(self):
        """Empty repaired_content is rejected."""
        tool = StoreRepairsTool()
        result = tool._add_repair(
            artifact_type="prompt",
            artifact_path="/abs/path/to/file.md",
            repaired_content="",
            summary="summary",
        )
        assert result.success is False
        assert "empty" in result.error.lower()

    def test_clear_removes_all_repairs(self):
        """Clear removes all stored repairs."""
        tool = StoreRepairsTool()
        tool._add_repair(
            artifact_type="prompt",
            artifact_path="/abs/path/1.md",
            repaired_content="content",
            summary="fix",
        )
        tool._add_repair(
            artifact_type="skill",
            artifact_path="/abs/path/2.md",
            repaired_content="content",
            summary="fix",
        )
        assert len(StoreRepairsTool.get_repairs()) == 2
        StoreRepairsTool.clear()
        assert len(StoreRepairsTool.get_repairs()) == 0

    @pytest.mark.asyncio
    async def test_execute_add_operation(self):
        """Execute with add operation works."""
        tool = StoreRepairsTool()
        result = await tool.execute(
            artifact_type="skill",
            artifact_path="/abs/path/skill.md",
            repaired_content="# Skill content",
            summary="Fixed all defects",
        )
        assert result.success is True
        assert len(StoreRepairsTool.get_repairs()) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/agents/repair_agent/test_store_repairs_tool.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` (class not implemented)

- [ ] **Step 3: Implement StoreRepairsTool**

```python
# src/sanityops_cli/agents/repair_agent/tools/store_repairs_tool.py
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

import json
from pathlib import Path
from typing import ClassVar

from sanityops_agent.tools.base import Tool, ToolResult


class StoreRepairsTool(Tool):
    """Shared-memory store for repaired artifacts produced by the repair agent.

    The agent calls `store_repair` once per defective artifact with the fully
    rewritten content; the CLI flushes everything into a single markdown
    report under `.sanityops/repairs/`.
    """

    name = "store_repair"
    description = "store the repaired content of one artifact"
    parameters = {
        "type": "object",
        "properties": {
            "artifact_type": {
                "type": "string",
                "enum": ["skill", "tool", "prompt"],
                "description": "which kind of artifact was repaired",
            },
            "artifact_path": {
                "type": "string",
                "description": "absolute path of the source artifact file that was repaired",
            },
            "repaired_content": {
                "type": "string",
                "description": "the complete repaired artifact content (full file, not a diff)",
            },
            "summary": {
                "type": "string",
                "description": "one-paragraph summary of the defects addressed",
            },
        },
        "required": ["artifact_type", "artifact_path", "repaired_content", "summary"],
    }
    tags = ["memory", "repair"]

    _repairs: ClassVar[list[dict]] = []

    async def execute(
        self,
        artifact_type: str,
        artifact_path: str,
        repaired_content: str,
        summary: str,
    ) -> ToolResult:
        """Execute the store_repair operation."""
        return self._add_repair(artifact_type, artifact_path, repaired_content, summary)

    def _add_repair(
        self,
        artifact_type: str,
        artifact_path: str,
        repaired_content: str,
        summary: str,
    ) -> ToolResult:
        """Add a repair entry to the shared store."""
        # Validate artifact_type
        if artifact_type not in ("skill", "tool", "prompt"):
            return ToolResult(
                content="",
                success=False,
                error=f"invalid artifact_type: {artifact_type}",
            )

        # Validate absolute path
        path = Path(artifact_path)
        if not path.is_absolute():
            return ToolResult(
                content="",
                success=False,
                error=f"artifact_path must be absolute: {artifact_path}",
            )

        # Validate non-empty content
        if not repaired_content or not repaired_content.strip():
            return ToolResult(
                content="",
                success=False,
                error="repaired_content is empty",
            )

        # Create entry
        entry = {
            "artifact_type": artifact_type,
            "artifact_path": str(path),
            "repaired_content": repaired_content,
            "summary": summary,
        }

        # Update existing entry for same artifact, or add new
        for index, existing in enumerate(self._repairs):
            if existing["artifact_path"] == entry["artifact_path"]:
                self._repairs[index] = entry
                action = "updated"
                break
        else:
            self._repairs.append(entry)
            action = "added"

        return ToolResult(
            content=json.dumps({
                "success": True,
                "message": f"{action} repair for {artifact_type}: {path.name}",
                "count": len(self._repairs),
            }),
            success=True,
        )

    @classmethod
    def get_repairs(cls) -> list[dict]:
        """Return all stored repairs."""
        return list(cls._repairs)

    @classmethod
    def clear(cls) -> None:
        """Clear all stored repairs."""
        cls._repairs.clear()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/unit/agents/repair_agent/test_store_repairs_tool.py -v
```

Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add src/sanityops_cli/agents/repair_agent/tools/store_repairs_tool.py tests/unit/agents/repair_agent/test_store_repairs_tool.py
git commit -m "feat(repair): implement StoreRepairsTool with validation"
```

---

### Task 3: Implement Repair Agent Prompts

**Files:**
- Create: `src/sanityops_cli/agents/repair_agent/prompts.py`

**Interfaces:**
- Produces: `REPAIR_AGENT_PROMPT` constant string

- [ ] **Step 1: Create prompts.py with system prompt**

```python
# src/sanityops_cli/agents/repair_agent/prompts.py
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

"""System prompt for the repair agent."""

REPAIR_AGENT_PROMPT = """\
You are an artifact repair agent. Your job is to fix the defects reported in an
inspection report by rewriting the defective artifacts.

## Inputs

- `{report_path}`: Absolute path to the inspection report (markdown). It lists
  every defect found in the artifacts, grouped per artifact, with severity
  (P0/P1/P2), description, location, impact, and a suggested fix.
- Artifacts live under the project root `{project_root}`. Paths referenced in
  the report (or listed below) are relative to it unless absolute.

## Artifacts Under Repair

The following artifacts were inspected and may require repair:
{artifact_list}

## Workflow (follow strictly)

1. Read the inspection report at `{report_path}` using the `read` tool.
2. Identify every artifact that has at least one defect in the report.
   Artifacts whose section says "No defects found" must be skipped entirely.
3. For each defective artifact, in this order:
   a. Read the artifact source file with the `read` tool — use the EXACT
      absolute path from the list above. Never guess, never explore the
      project, never read paths you have not been given.
   b. Rewrite the FULL artifact content so that all reported defects in that
      artifact are resolved. You must not introduce new defects; keep the
      original structure, language, and unrelated content intact. Apply the
      report's suggested fixes unless they conflict with other content, in
      which case use your judgment to keep the artifact consistent.
   c. Call `store_repair` immediately with:
      - artifact_type: "prompt" | "tool" | "skill"
      - artifact_path: absolute path of the artifact file you read
      - repaired_content: the complete rewritten file content
      - summary: one short paragraph listing which defect IDs you addressed
4. Cross-module defects (IDs starting with QD-PT / QD-ST, shown in the
   "Cross" section) describe inconsistencies BETWEEN artifacts. Resolve them
   by editing the artifact(s) the fix suggestion targets; a single cross
   defect may require touching two artifacts — store each repaired artifact
   separately.

## Output Language

- All summaries and repair descriptions must be written in English.
- Preserve the original language of the artifact content itself (Chinese stays
  Chinese, English stays English). Comments and explanations inside the
  repaired content should be minimal.

## Scope discipline (IMPORTANT)

You have exactly two tools and one job. Do NOT:
- explore the project tree, list directories, or glob for other files;
- read the report more than once;
- read any path that is not in the Artifacts list above (a failed read
  wastes a full turn and the token budget);
- rewrite artifacts that have no defects.

Every wasted turn can exhaust the budget before a single repair is stored.

## Rules

- repaired_content MUST be the complete file content, never a diff or snippet.
- Never delete functionality to make a defect disappear unless the report
  explicitly says so; prefer completing or correcting definitions.
- If the report contains no defects at all, store nothing and report that.
- Process artifacts one at a time: read -> repair -> store_repair -> next.
- Token budget is limited. Be economical: do NOT re-read files you have
  already read; do NOT re-store an artifact you already stored (unless you
  are correcting it); think through the repair BEFORE producing output and
  emit the repaired content in one shot — avoid iterating on drafts.

## Available Tools

- `read(file_path)`: read a file from disk. `file_path` must be an absolute path.
- `store_repair(...)`: REQUIRED. Store each repaired artifact exactly as
  specified above.

## Termination

Finish when every defective artifact has been stored via `store_repair`.
Then reply with a one-line summary: how many artifacts repaired, how many
defect IDs addressed.
"""
```

- [ ] **Step 2: Commit**

```bash
git add src/sanityops_cli/agents/repair_agent/prompts.py
git commit -m "feat(repair): add repair agent system prompt"
```

---

### Task 4: Implement RepairAgent Class

**Files:**
- Create: `src/sanityops_cli/agents/repair_agent/agent.py`
- Create: `tests/unit/agents/repair_agent/test_agent.py`

**Interfaces:**
- Consumes: `StoreRepairsTool`, `REPAIR_AGENT_PROMPT`, `FileReadTool` from scanner_agent
- Produces: `RepairAgent` class with:
  - `__init__(provider, max_loops=30, timeout=300, token_budget=None, llm_retries=3, retry_delay=65, verbose=False, console=None, logger=None)`
  - `async repair(report_path, artifacts, project_root) -> list[dict]`
  - `repair_sync(...) -> list[dict]`
- Also produces: `_is_rate_limit_error(exc) -> bool` helper function

- [ ] **Step 1: Write failing tests for RepairAgent**

```python
# tests/unit/agents/repair_agent/test_agent.py
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

import pytest

from sanityops_cli.agents.repair_agent.agent import RepairAgent, _is_rate_limit_error


class TestIsRateLimitError:
    """Tests for _is_rate_limit_error helper."""

    def test_detects_429(self):
        """Detects 429 status code."""
        assert _is_rate_limit_error(Exception("Error 429: Too Many Requests")) is True

    def test_detects_rate_limit_text(self):
        """Detects 'rate limit' in message."""
        assert _is_rate_limit_error(Exception("Rate limit exceeded")) is True

    def test_detects_throttling_error(self):
        """Detects throttling_error marker."""
        assert _is_rate_limit_error(Exception("throttling_error: request blocked")) is True

    def test_detects_too_many_requests(self):
        """Detects 'too many requests' phrase."""
        assert _is_rate_limit_error(Exception("Too many requests, slow down")) is True

    def test_returns_false_for_other_errors(self):
        """Returns False for non-rate-limit errors."""
        assert _is_rate_limit_error(Exception("Connection refused")) is False
        assert _is_rate_limit_error(Exception("File not found")) is False
        assert _is_rate_limit_error(Exception("Invalid API key")) is False


class TestRepairAgentInit:
    """Tests for RepairAgent initialization."""

    def test_default_parameters(self):
        """Agent has sensible defaults."""
        agent = RepairAgent(provider=None)
        assert agent.max_loops == 30
        assert agent.timeout == 300
        assert agent.token_budget is None
        assert agent.llm_retries == 3
        assert agent.retry_delay == 65
        assert agent.verbose is False

    def test_custom_parameters(self):
        """Agent accepts custom parameters."""
        agent = RepairAgent(
            provider="mock_provider",
            max_loops=50,
            timeout=600,
            token_budget=500000,
            llm_retries=5,
            retry_delay=120,
            verbose=True,
        )
        assert agent.max_loops == 50
        assert agent.timeout == 600
        assert agent.token_budget == 500000
        assert agent.llm_retries == 5
        assert agent.retry_delay == 120
        assert agent.verbose is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/agents/repair_agent/test_agent.py -v
```

Expected: `ImportError` (class not implemented)

- [ ] **Step 3: Implement RepairAgent**

```python
# src/sanityops_cli/agents/repair_agent/agent.py
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
            # success: return what was collected with a warning instead of
            # discarding it (budget/loop exhaustion or a mid-run LLM error).
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
    the text keeps this working across provider SDKs.
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/unit/agents/repair_agent/test_agent.py -v
```

Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add src/sanityops_cli/agents/repair_agent/agent.py tests/unit/agents/repair_agent/test_agent.py
git commit -m "feat(repair): implement RepairAgent with rate-limit retry"
```

---

### Task 5: Add Repair Command to inspect.py

**Files:**
- Modify: `src/sanityops_cli/commands/inspect.py`
- Create: `tests/commands/test_inspect_repair.py`

**Interfaces:**
- Consumes: `RepairAgent`, `resolve_llm_config`, `InspectConfigLoader`
- Produces: `inspect repair` CLI subcommand
- Produces: Helper functions `_find_latest_report()`, `_write_repairs_markdown()`

- [ ] **Step 1: Write failing tests for repair command**

```python
# tests/commands/test_inspect_repair.py
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

from pathlib import Path

from typer.testing import CliRunner

from sanityops_cli.commands.inspect import inspect_app

runner = CliRunner()


class TestFindLatestReport:
    """Tests for _find_latest_report helper."""

    def test_returns_none_when_dir_not_exists(self, tmp_path: Path):
        """Returns None when results directory does not exist."""
        from sanityops_cli.commands.inspect import _find_latest_report
        result = _find_latest_report(tmp_path / "nonexistent")
        assert result is None

    def test_returns_none_when_no_reports(self, tmp_path: Path):
        """Returns None when no inspect reports exist."""
        from sanityops_cli.commands.inspect import _find_latest_report
        (tmp_path / "results").mkdir()
        result = _find_latest_report(tmp_path / "results")
        assert result is None

    def test_returns_newest_report(self, tmp_path: Path):
        """Returns the most recently modified report."""
        import time
        from sanityops_cli.commands.inspect import _find_latest_report

        results_dir = tmp_path / "results"
        results_dir.mkdir()

        # Create two reports with different mtimes
        old_report = results_dir / "inspect-20260919-100000.md"
        new_report = results_dir / "inspect-20260920-100000.md"
        old_report.write_text("# Old Report")
        new_report.write_text("# New Report")

        # Ensure different mtimes
        time.sleep(0.1)
        new_report.touch()

        result = _find_latest_report(results_dir)
        assert result == new_report


class TestWriteRepairsMarkdown:
    """Tests for _write_repairs_markdown helper."""

    def test_creates_output_file(self, tmp_path: Path):
        """Creates output file with correct structure."""
        from sanityops_cli.commands.inspect import _write_repairs_markdown
        from datetime import datetime

        repairs = [
            {
                "artifact_type": "prompt",
                "artifact_path": "/abs/path/prompt.md",
                "repaired_content": "# Fixed content",
                "summary": "Fixed all issues",
            }
        ]

        output_dir = tmp_path / "repairs"
        report_path = tmp_path / "results" / "inspect-20260920.md"
        report_path.parent.mkdir(parents=True)
        report_path.write_text("# Report")

        result = _write_repairs_markdown(
            repairs,
            output_dir,
            report_path=report_path,
            project_id="test-project",
        )

        assert result.exists()
        assert result.suffix == ".md"
        content = result.read_text()
        assert "# Repair Report" in content
        assert "test-project" in content
        assert "/abs/path/prompt.md" in content
        assert "Fixed all issues" in content
        assert "# Fixed content" in content

    def test_creates_output_directory(self, tmp_path: Path):
        """Creates output directory if it does not exist."""
        from sanityops_cli.commands.inspect import _write_repairs_markdown

        repairs = [
            {
                "artifact_type": "skill",
                "artifact_path": "/abs/path/skill.md",
                "repaired_content": "content",
                "summary": "summary",
            }
        ]

        output_dir = tmp_path / "new" / "repairs"
        report_path = tmp_path / "report.md"
        report_path.write_text("# Report")

        result = _write_repairs_markdown(
            repairs,
            output_dir,
            report_path=report_path,
            project_id=None,
        )

        assert output_dir.exists()
        assert result.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/commands/test_inspect_repair.py -v
```

Expected: `ImportError` (functions not implemented)

- [ ] **Step 3: Add helper functions to inspect.py**

Add these helper functions after the existing code in `src/sanityops_cli/commands/inspect.py` (before the `@inspect_app.callback` decorator):

```python
# ============================================================================
# Helper functions for repair command
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
        lines.extend(
            [
                "---",
                "",
                f"## {index}. {label} — {Path(artifact_path).name}",
                "",
                f"- **Source**: `{artifact_path}`",
                f"- **Summary**: {repair.get('summary', '')}",
                "",
                "### Repaired content",
                "",
                "````markdown",
                repair.get("repaired_content", ""),
                "````",
                "",
            ]
        )

    path.write_text("\n".join(lines), encoding="utf-8")
    return path
```

- [ ] **Step 4: Add repair command to inspect.py**

Add the repair command after the helper functions:

```python
# ============================================================================
# inspect repair — generate repaired artifacts from a local inspection report
# ============================================================================


@inspect_app.command("repair")
def inspect_repair(
    ctx: typer.Context,
    report: Path | None = typer.Option(
        None,
        "--report", "-r",
        help=(
            "Path to the inspection report (.md) to repair from. "
            "If omitted, uses the newest .sanityops/results/inspect-*.md."
        ),
    ),
    config: str | None = typer.Option(
        None,
        "--config", "-c",
        help="Path to inspect_config.yaml. If omitted, looks for .sanityops/inspect_config.yaml in cwd.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
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
    model: str | None = typer.Option(None, "--model", "-m", help="LLM model ID override"),
    provider: str | None = typer.Option(None, "--provider", "-p", help="LLM provider override"),
) -> None:
    """Generate repaired artifacts locally from an inspection report.

    Reads the latest inspection report (or --report), asks a local repair
    agent to rewrite every defective artifact, and writes the repaired
    content to `.sanityops/repairs/repair-<timestamp>.md`. Nothing is
    uploaded and no source file is modified.
    """
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
        report_path = report.expanduser().resolve()
        if not report_path.is_file():
            console.print(f"[red]✗ Report not found: {report}[/red]")
            raise typer.Exit(code=EXIT_FAILURE)
    else:
        report_path = _find_latest_report(results_dir)
        if report_path is None:
            console.print(f"[red]✗ No inspection report found in {results_dir}[/red]")
            console.print("  Run `sanityops-cli inspect` first, or pass --report <path>.")
            raise typer.Exit(code=EXIT_FAILURE)

    console.print()
    console.print("[bold]Repairing artifacts from inspection report[/]")
    console.print(f"  Report:    {report_path}")
    console.print(
        f"  Artifacts: {total} ({len(artifact_paths['prompts'])}p, "
        f"{len(artifact_paths['tools'])}t, {len(artifact_paths['skills'])}s)"
    )

    # Step 3: Resolve LLM config
    try:
        with tracker.step("Resolving LLM configuration..."):
            llm_config = resolve_llm_config(config)
            # Apply CLI overrides
            if provider:
                llm_config["llm_provider"] = provider
            if model:
                llm_config["llm_model_id"] = model
    except Exception as e:
        console.print(f"[red]✗ Failed to resolve LLM configuration: {escape(str(e))}[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None

    if not llm_config.get("llm_api_key", "").strip():
        console.print("[red]✗ LLM configuration is incomplete (missing API key).[/red]")
        console.print(
            "  Configure model.provider/api_key/model_id in .sanityops/inspect_config.yaml."
        )
        raise typer.Exit(code=EXIT_FAILURE)

    from sanityops_agent.config import ProviderConfig
    from sanityops_agent.llm.factory import ProviderFactory

    provider_config = ProviderConfig(
        LLM_PROVIDER=llm_config["llm_provider"],
        API_KEY=llm_config["llm_api_key"],
        MODEL_ID=llm_config["llm_model_id"],
        BASE_URL=llm_config["llm_base_url"] or None,
    )
    llm_provider = ProviderFactory.create(provider_config)

    # Step 4: Run the repair agent
    from sanityops_cli.agents.repair_agent.agent import RepairAgent, _is_rate_limit_error

    # Token budget auto-scaling
    if token_budget > 0:
        effective_budget = token_budget
    else:
        effective_budget = 300_000 + 150_000 * total

    agent = RepairAgent(
        provider=llm_provider,
        max_loops=60,
        timeout=timeout,
        token_budget=effective_budget,
        verbose=verbose,
        console=console,
        logger=logger,
    )

    console.print(f"  Provider:  {llm_config['llm_provider']}")
    console.print(f"  Model:     {llm_config['llm_model_id']}")
    console.print(f"  Budget:    {effective_budget} tokens / {timeout}s")
    console.print()

    try:
        with tracker.step("Running repair agent..."):
            repairs = agent.repair_sync(
                report_path=str(report_path),
                artifacts=artifact_paths,
                project_root=str(loader.config_path.parent.parent),
            )
    except ValidationError as e:
        if _is_rate_limit_error(e):
            console.print("[red]✗ Repair failed: the LLM service is rate limited.[/red]")
            console.print(
                "  The server-side model quota is exhausted."
            )
            console.print("  Wait a minute and re-run, or raise the backend quota.")
        else:
            console.print(f"[red]✗ Repair failed: {escape(str(e))}[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None
    except Exception as e:
        _report_program_error(logger, "Running repair agent...", e, step_summary_shown=verbose)
        raise typer.Exit(code=EXIT_FAILURE) from None

    tracker.summary()

    if not repairs:
        console.print("[yellow]⚠[/] No repairs generated (report may contain no defects).")
        raise typer.Exit()

    # Step 5: Persist repairs
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
    except Exception as e:
        console.print(f"[red]✗ Could not save repair report: {escape(str(e))}[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/commands/test_inspect_repair.py -v
```

Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add src/sanityops_cli/commands/inspect.py tests/commands/test_inspect_repair.py
git commit -m "feat(repair): add inspect repair subcommand"
```

---

### Task 6: Integration Test

**Files:**
- Modify: `tests/commands/test_inspect_repair.py`

**Interfaces:**
- Produces: Integration test for full repair command

- [ ] **Step 1: Add integration test**

Add to `tests/commands/test_inspect_repair.py`:

```python
class TestInspectRepairCommand:
    """Integration tests for inspect repair command."""

    def test_repair_command_shows_help(self):
        """Repair command shows help without error."""
        result = runner.invoke(inspect_app, ["repair", "--help"])
        assert result.exit_code == 0
        assert "repair" in result.output.lower()

    def test_repair_command_requires_config_or_report(self, tmp_path: Path, monkeypatch):
        """Repair command fails gracefully when no config exists."""
        # Change to temp directory with no config
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(inspect_app, ["repair"])
        # Should fail because no config exists
        assert result.exit_code != 0
```

- [ ] **Step 2: Run integration tests**

```bash
pytest tests/commands/test_inspect_repair.py -v
```

Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add tests/commands/test_inspect_repair.py
git commit -m "test(repair): add integration tests for inspect repair command"
```

---

### Task 7: Final Verification and Documentation

**Files:**
- None (verification only)

- [ ] **Step 1: Run full test suite**

```bash
pytest tests/ -v
```

Expected: All tests pass

- [ ] **Step 2: Run linting/type checking (if configured)**

```bash
# If ruff is configured:
ruff check src/

# If mypy is configured:
mypy src/
```

- [ ] **Step 3: Manual smoke test**

Create a test scenario:
1. Run `sanityops-cli inspect` on a project with defects
2. Run `sanityops-cli inspect repair`
3. Verify repair report is generated in `.sanityops/repairs/`
4. Verify the repair report format matches spec

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat(repair): complete repair feature migration from deeplogic-cli"
```