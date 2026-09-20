# Repair Feature Design

**Date:** 2026-09-20
**Status:** Approved
**Source:** Migration from deeplogic-cli

## Overview

Migrate the local `repair` feature from deeplogic-cli to sanityops-cli. The repair feature reads an inspection report and uses an LLM agent to generate fixed artifact content.

## Scope

**In Scope:**
- `inspect repair` subcommand
- `RepairAgent` class
- `StoreRepairsTool` agent tool
- Repair report output (markdown)

**Out of Scope:**
- `inspect cover` command (applying repairs to source files)
- Server-side repair (requires JWT authentication)
- Direct source file modification

## Architecture

```
src/sanityops_cli/
├── agents/
│   ├── scanner_agent/          # Existing
│   └── repair_agent/           # New
│       ├── __init__.py
│       ├── agent.py            # RepairAgent class
│       ├── prompts.py          # System prompt
│       └── tools/
│           ├── __init__.py
│           └── store_repairs_tool.py
├── commands/
│   └── inspect.py              # Modified: add repair subcommand
```

## Components

### 1. RepairAgent

**File:** `agents/repair_agent/agent.py`

```python
class RepairAgent:
    def __init__(
        self,
        provider,              # LLM provider (reuse scanner config)
        max_loops: int = 30,
        timeout: int = 300,
        token_budget: int = None,  # Auto-calculated: 300k + 150k * artifacts
        llm_retries: int = 3,      # Rate limit retry count
        retry_delay: int = 65,     # Retry delay (seconds)
        verbose: bool = False,
        console: Console = None,
        logger: Logger = None,
    ): ...

    async def repair(
        self,
        report_path: Path,      # Inspection report path
        artifacts: list[str],   # Artifact path list
        project_root: Path,
    ) -> list[dict]:            # Returns list of repair results

    def repair_sync(...) -> list[dict]:  # Sync wrapper
```

**Key Design Decisions:**

1. **No TaskTool** - Prevents agent from "wandering" and wasting token budget
2. **Rate-limit retry** - Built-in 3 retries with 65-second delay
3. **Token budget auto-scaling** - Dynamically calculated based on artifact count
4. **Partial success handling** - Returns collected repairs even if agent terminates early

### 2. StoreRepairsTool

**File:** `agents/repair_agent/tools/store_repairs_tool.py`

```python
class StoreRepairsTool(Tool):
    name = "store_repair"
    description = "Store repaired artifact content with defect references"
    parameters = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["add", "list", "clear", "count"],
            },
            "repair": {
                "type": "object",
                "properties": {
                    "artifact_path": {"type": "string"},
                    "original_content": {"type": "string"},
                    "repaired_content": {"type": "string"},
                    "defect_ids": {"type": "array", "items": {"type": "string"}},
                    "fix_description": {"type": "string"},
                },
            },
        },
        "required": ["operation"],
    }
    tags = ["memory", "repair"]

    _repairs: ClassVar[list[dict]] = []

    async def execute(self, operation: str, repair: dict = None) -> ToolResult:
        ...
```

### 3. CLI Command

**File:** `commands/inspect.py`

```python
@inspect_app.command("repair")
def inspect_repair(
    ctx: typer.Context,
    report: Path | None = typer.Option(
        None, "--report", "-r",
        help="Path to inspection report. Default: latest in .sanityops/results/"
    ),
    config: str | None = typer.Option(None, "--config", "-c"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    model: str | None = typer.Option(None, "--model", "-m"),
    provider: str | None = typer.Option(None, "--provider", "-p"),
    output: Path | None = typer.Option(
        None, "--output", "-o",
        help="Output path for repair report. Default: .sanityops/repairs/repair-<timestamp>.md"
    ),
):
    """
    Repair artifacts based on inspection report findings.

    Reads defect report and uses LLM to generate fixed artifact content.
    Output is a markdown file with repaired artifacts (does not modify source files).
    """
```

**Command Behavior:**

1. Load config, resolve LLM provider
2. Locate report file (latest or `--report` specified)
3. Parse artifact paths from report
4. Call `RepairAgent.repair_sync()`
5. Write results to `.sanityops/repairs/repair-<timestamp>.md`
6. Print summary

## Output Format

**Path:** `.sanityops/repairs/repair-<timestamp>.md`

**All content in English.**

```markdown
# Repair Report

**Generated:** 2026-09-20 14:30:00
**Source Report:** .sanityops/results/inspect-20260920-143000.md
**Artifacts Repaired:** 3
**Defects Addressed:** 5

---

## Repaired Artifacts

### Artifact 1: `prompts/system_prompt.md`

**Defects Fixed:** D001, D002, D003

**Fix Description:**
- Fixed ambiguous pronoun references in paragraph 2
- Added missing error handling documentation
- Clarified timeout behavior

**Repaired Content:**
```markdown
[Full repaired artifact content]
```

---

### Artifact 2: `skills/data_analysis/skill.md`
...
```

**Format Notes:**
- Header with metadata (generation time, source report, statistics)
- Separate section for each artifact
- Includes defect references, fix description, full content
- Does not include original content (already in source report)

## System Prompt

**File:** `agents/repair_agent/prompts.py`

```python
REPAIR_AGENT_PROMPT = """
You are an expert artifact repair agent. Your task is to fix defects in AI artifacts
(system prompts, skills, tool schemas) based on an inspection report.

## Process
1. Read the inspection report to identify defects
2. Read each defective artifact
3. Generate repaired content that addresses all reported defects
4. Use store_repairs tool to save each repaired artifact

## Output Language
- All fix descriptions and repaired content must be in English

## Rules
- Preserve the original structure and format of artifacts
- Only fix the reported defects, do not make unnecessary changes
- If a defect cannot be fixed, document why in fix_description
- Each artifact should be stored once with all its fixes combined

## Tools Available
- read: Read file contents
- store_repairs: Store repaired artifact content

## Output
Use the store_repairs tool with operation "add" for each repaired artifact:
{
  "operation": "add",
  "repair": {
    "artifact_path": "path/to/artifact",
    "original_content": "original content here",
    "repaired_content": "fixed content here",
    "defect_ids": ["D001", "D002"],
    "fix_description": "Description of fixes applied"
  }
}
"""
```

## Migration Approach

**Method:** Direct migration with import path adjustment

1. Copy `RepairAgent` from deeplogic-cli
2. Copy `StoreRepairsTool` from deeplogic-cli
3. Change imports: `aidynamic_agent` → `sanityops_agent`
4. Add `repair` subcommand to `inspect.py`
5. Reuse existing utilities:
   - `FileReadTool` from scanner_agent
   - `ProgressHook` from scanner_agent (optional)
   - `resolve_llm_config` from defect_checker

## Dependencies

- `sanityops-agent` - Agent framework (already installed)
- `anyio` - Async/sync bridging (already installed)
- `rich` - Console output (already installed)

No new external dependencies required.

## Tests

- Unit tests for `RepairAgent`
- Unit tests for `StoreRepairsTool`
- Integration test for `inspect repair` command
- Test report parsing and artifact extraction
- Test output format validation

## Exit Codes

Reuse existing exit codes from `constants/exit_codes.py`:
- `EXIT_SUCCESS = 0`
- `EXIT_FAILURE = 2`

Add new exit code if needed:
- `EXIT_REPAIR_FAILED = 3` (optional)
