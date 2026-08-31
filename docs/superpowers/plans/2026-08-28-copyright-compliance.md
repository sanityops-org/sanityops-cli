# Copyright & License Compliance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Apache 2.0 copyright headers to all Python source files, create a NOTICE file, and update `--version` output to include copyright and license info.

**Architecture:** Mechanical addition of standardized copyright headers across the codebase, plus a targeted change to the `--version` callback in `main.py` and a new `NOTICE` file at the repo root.

**Tech Stack:** Python, Typer, pytest, CliRunner

## Global Constraints

- Copyright holder: `zipsonken` / `Sanity AI Labs`
- Year: `2026`
- License: Apache License, Version 2.0
- All `.py` files under `src/` and `entry.py` must have the copyright header
- `NOTICE` file created at repo root
- `--version` output must include version, copyright, and license on separate lines
- No copyright text in regular command output (only `--version`)
- Do NOT modify the existing `LICENSE` file

---

### Task 1: Create NOTICE File

**Files:**
- Create: `NOTICE`

**Interfaces:**
- Consumes: None (new file)
- Produces: `NOTICE` file at repo root

- [ ] **Step 1: Create the NOTICE file**

Write `NOTICE` at the repo root with this exact content:

```
SanityOps Inspect CLI
Copyright 2026 zipsonken / Sanity AI Labs

This product includes software developed under the SanityOps Framework.
SanityOps Framework is licensed under Apache License 2.0.
```

- [ ] **Step 2: Verify the file**

Run: `cat NOTICE`

Expected output:
```
SanityOps Inspect CLI
Copyright 2026 zipsonken / Sanity AI Labs

This product includes software developed under the SanityOps Framework.
SanityOps Framework is licensed under Apache License 2.0.
```

- [ ] **Step 3: Commit**

```bash
git add NOTICE
git commit -m "chore(legal): add NOTICE file for Apache 2.0 attribution"
```

---

### Task 2: Add Copyright Headers — Core Package Files

**Files:**
- Modify: `src/sanityops_cli/__init__.py`
- Modify: `src/sanityops_cli/main.py`
- Modify: `entry.py`

**Interfaces:**
- Consumes: None
- Produces: All modified files start with the Apache 2.0 copyright header

The copyright header to prepend (use `#` comment style):

```python
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
```

**Note:** The final line is a blank `#` to separate the header from the file's first meaningful line.

- [ ] **Step 1: Add header to `src/sanityops_cli/__init__.py`**

Current content:
```python
__version__ = "0.0.3"
```

After modification:
```python
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

__version__ = "0.0.3"
```

- [ ] **Step 2: Add header to `src/sanityops_cli/main.py`**

Current first line is a docstring: `"""Sanityops CLI Entrance — Typer Application"""`

The header goes BEFORE the docstring. After modification, the file starts with:

```python
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

"""Sanityops CLI Entrance — Typer Application"""
```

- [ ] **Step 3: Add header to `entry.py`**

Current content:
```python
from sanityops_cli.main import app

app()
```

After modification:
```python
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

from sanityops_cli.main import app

app()
```

- [ ] **Step 4: Run a quick syntax check**

```bash
python -m py_compile src/sanityops_cli/__init__.py src/sanityops_cli/main.py entry.py
```

Expected: No output (success)

- [ ] **Step 5: Commit**

```bash
git add src/sanityops_cli/__init__.py src/sanityops_cli/main.py entry.py
git commit -m "chore(legal): add Apache 2.0 copyright headers to core package files"
```

---

### Task 3: Add Copyright Headers — Commands

**Files:**
- Modify: `src/sanityops_cli/commands/__init__.py`
- Modify: `src/sanityops_cli/commands/inspect.py`
- Modify: `src/sanityops_cli/commands/init.py`

**Interfaces:**
- Consumes: None
- Produces: All modified files start with the copyright header

- [ ] **Step 1: Add header to `src/sanityops_cli/commands/__init__.py`**

Prepend the copyright header (same format as Task 2).

- [ ] **Step 2: Add header to `src/sanityops_cli/commands/inspect.py`**

This file starts with a docstring `"""inspect command — Sanityops CLI Tool"""`. Insert the copyright header BEFORE the docstring, with a blank line between the header and the docstring.

- [ ] **Step 3: Add header to `src/sanityops_cli/commands/init.py`**

Check the first line. If it's a docstring, insert the header before it. Otherwise, prepend the header at the very top.

- [ ] **Step 4: Syntax check**

```bash
python -m py_compile src/sanityops_cli/commands/__init__.py src/sanityops_cli/commands/inspect.py src/sanityops_cli/commands/init.py
```

Expected: No output (success)

- [ ] **Step 5: Commit**

```bash
git add src/sanityops_cli/commands/
git commit -m "chore(legal): add Apache 2.0 copyright headers to commands"
```

---

### Task 4: Add Copyright Headers — Agents

**Files:**
- Modify: `src/sanityops_cli/agents/__init__.py`
- Modify: `src/sanityops_cli/agents/scanner_agent/agent.py`
- Modify: `src/sanityops_cli/agents/scanner_agent/hooks/progress_hook.py`
- Modify: `src/sanityops_cli/agents/scanner_agent/models/finding.py`
- Modify: `src/sanityops_cli/agents/scanner_agent/prompts.py`
- Modify: `src/sanityops_cli/agents/scanner_agent/tools/grep_tool.py`
- Modify: `src/sanityops_cli/agents/scanner_agent/tools/listfiles_tool.py`
- Modify: `src/sanityops_cli/agents/scanner_agent/tools/readfile_tool.py`
- Modify: `src/sanityops_cli/agents/scanner_agent/tools/storefindings_tool.py`

**Interfaces:**
- Consumes: None
- Produces: All modified files start with the copyright header

- [ ] **Step 1: Add headers to all agent files**

For each file in the list above, prepend the copyright header. Check each file's first line:
- If it starts with `"""` (docstring), insert the header before it with a blank line separating them.
- Otherwise, prepend the header at the top.

- [ ] **Step 2: Syntax check**

```bash
python -m py_compile src/sanityops_cli/agents/__init__.py src/sanityops_cli/agents/scanner_agent/agent.py src/sanityops_cli/agents/scanner_agent/hooks/progress_hook.py src/sanityops_cli/agents/scanner_agent/models/finding.py src/sanityops_cli/agents/scanner_agent/prompts.py src/sanityops_cli/agents/scanner_agent/tools/grep_tool.py src/sanityops_cli/agents/scanner_agent/tools/listfiles_tool.py src/sanityops_cli/agents/scanner_agent/tools/readfile_tool.py src/sanityops_cli/agents/scanner_agent/tools/storefindings_tool.py
```

Expected: No output (success)

- [ ] **Step 3: Commit**

```bash
git add src/sanityops_cli/agents/
git commit -m "chore(legal): add Apache 2.0 copyright headers to agents"
```

---

### Task 5: Add Copyright Headers — Utils, Constants, Exceptions

**Files:**
- Modify: `src/sanityops_cli/utils/__init__.py`
- Modify: `src/sanityops_cli/utils/config_loader.py`
- Modify: `src/sanityops_cli/utils/validators.py`
- Modify: `src/sanityops_cli/constants/__init__.py`
- Modify: `src/sanityops_cli/constants/exit_codes.py`
- Modify: `src/sanityops_cli/exceptions/__init__.py`
- Modify: `src/sanityops_cli/exceptions/base_exceptions.py`
- Modify: `src/sanityops_cli/exceptions/api_exceptions.py`

**Interfaces:**
- Consumes: None
- Produces: All modified files start with the copyright header

- [ ] **Step 1: Add headers to all files**

For each file, prepend the copyright header. Handle docstring-first files by inserting the header before the docstring.

- [ ] **Step 2: Syntax check**

```bash
python -m py_compile src/sanityops_cli/utils/__init__.py src/sanityops_cli/utils/config_loader.py src/sanityops_cli/utils/validators.py src/sanityops_cli/constants/__init__.py src/sanityops_cli/constants/exit_codes.py src/sanityops_cli/exceptions/__init__.py src/sanityops_cli/exceptions/base_exceptions.py src/sanityops_cli/exceptions/api_exceptions.py
```

Expected: No output (success)

- [ ] **Step 3: Commit**

```bash
git add src/sanityops_cli/utils/ src/sanityops_cli/constants/ src/sanityops_cli/exceptions/
git commit -m "chore(legal): add Apache 2.0 copyright headers to utils, constants, and exceptions"
```

---

### Task 6: Add Copyright Headers — Renderers, Progress, Templates, Defect Checker, Logging

**Files:**
- Modify: `src/sanityops_cli/renderers/__init__.py`
- Modify: `src/sanityops_cli/renderers/command_renderer/inspect_command_renderer.py`
- Modify: `src/sanityops_cli/progress/__init__.py`
- Modify: `src/sanityops_cli/progress/tracker.py`
- Modify: `src/sanityops_cli/templates/__init__.py`
- Modify: `src/sanityops_cli/defect_checker/__init__.py`
- Modify: `src/sanityops_cli/defect_checker/checker.py`
- Modify: `src/sanityops_cli/defect_checker/llm_config.py`
- Modify: `src/sanityops_cli/defect_checker/renderer.py`
- Modify: `src/sanityops_cli/logging/__init__.py`
- Modify: `src/sanityops_cli/logging/logger.py`

**Interfaces:**
- Consumes: None
- Produces: All modified files start with the copyright header

- [ ] **Step 1: Add headers to all files**

For each file, prepend the copyright header. Handle docstring-first files by inserting the header before the docstring.

- [ ] **Step 2: Syntax check**

```bash
python -m py_compile src/sanityops_cli/renderers/__init__.py src/sanityops_cli/renderers/command_renderer/inspect_command_renderer.py src/sanityops_cli/progress/__init__.py src/sanityops_cli/progress/tracker.py src/sanityops_cli/templates/__init__.py src/sanityops_cli/defect_checker/__init__.py src/sanityops_cli/defect_checker/checker.py src/sanityops_cli/defect_checker/llm_config.py src/sanityops_cli/defect_checker/renderer.py src/sanityops_cli/logging/__init__.py src/sanityops_cli/logging/logger.py
```

Expected: No output (success)

- [ ] **Step 3: Commit**

```bash
git add src/sanityops_cli/renderers/ src/sanityops_cli/progress/ src/sanityops_cli/templates/ src/sanityops_cli/defect_checker/ src/sanityops_cli/logging/
git commit -m "chore(legal): add Apache 2.0 copyright headers to renderers, progress, templates, defect checker, and logging"
```

---

### Task 7: Update `--version` Output

**Files:**
- Modify: `src/sanityops_cli/main.py:19-22`
- Test: `tests/unit/commands/test_version.py` (new)

**Interfaces:**
- Consumes: `__version__` from `sanityops_cli.__init__` (already imported)
- Produces: Updated `version_callback` that outputs three lines: version, copyright, license

- [ ] **Step 1: Write the test**

Create `tests/unit/commands/test_version.py`:

```python
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

"""Unit tests for --version output."""

from typer.testing import CliRunner

from sanityops_cli.main import app

runner = CliRunner()


def test_version_outputs_version_line():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "sanityops-cli v" in result.output


def test_version_outputs_copyright_line():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "Copyright (C) 2026 zipsonken / Sanity AI Labs" in result.output


def test_version_outputs_license_line():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "License: Apache 2.0" in result.output


def test_version_does_not_output_on_other_commands():
    """Copyright should NOT appear in regular command help output."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Copyright" not in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/commands/test_version.py -v
```

Expected: FAIL on `test_version_outputs_copyright_line` and `test_version_outputs_license_line` because the current `version_callback` only outputs the version line.

- [ ] **Step 3: Update `version_callback` in `main.py`**

Current code in `src/sanityops_cli/main.py` lines 19-22:

```python
def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"sanityops-cli version {__version__}")
        raise typer.Exit()
```

Replace with:

```python
def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"sanityops-cli v{__version__}")
        typer.echo("Copyright (C) 2026 zipsonken / Sanity AI Labs")
        typer.echo("License: Apache 2.0 (https://www.apache.org/licenses/LICENSE-2.0)")
        raise typer.Exit()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/unit/commands/test_version.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Run full test suite to ensure no regressions**

```bash
pytest -x
```

Expected: All existing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add src/sanityops_cli/main.py tests/unit/commands/test_version.py
git commit -m "feat(cli): include copyright and license in --version output

- Update version_callback to output three lines:
  1. Version string
  2. Copyright notice
  3. License reference
- Add unit tests verifying --version output"
```

---

### Task 8: Final Verification

**Files:**
- All files under `src/sanityops_cli/` and `entry.py`

- [ ] **Step 1: Verify all .py files have copyright headers**

```bash
find src -name "*.py" -exec head -1 {} \; -print | grep -B1 "^# Copyright"
```

Expected: Every `.py` file's first line should be `# Copyright 2026 zipsonken`. If any file is missing the header, go back and fix it.

Also verify `entry.py`:
```bash
head -1 entry.py
```

Expected: `# Copyright 2026 zipsonken`

- [ ] **Step 2: Verify NOTICE file exists**

```bash
ls -la NOTICE && cat NOTICE
```

- [ ] **Step 3: Verify --version output**

```bash
cd /Users/a1234/Documents/project/sanityops-cli && python -m sanityops_cli.main --version
```

Expected:
```
sanityops-cli v0.0.3
Copyright (C) 2026 zipsonken / Sanity AI Labs
License: Apache 2.0 (https://www.apache.org/licenses/LICENSE-2.0)
```

- [ ] **Step 4: Verify --help does NOT show copyright**

```bash
python -m sanityops_cli.main --help
```

Expected: Help text without any "Copyright" or "License" lines.

- [ ] **Step 5: Final commit (if any uncommitted changes)**

```bash
git status
```

If there are uncommitted changes, commit them. Otherwise, no action needed.

---

## Self-Review Checklist

### 1. Spec Coverage

| Spec Requirement | Task |
|---|---|
| Add copyright headers to all `.py` source files | Tasks 2-6 (covers all 33+ files) |
| Create `NOTICE` file at repo root | Task 1 |
| Update `--version` output with copyright/license | Task 7 |
| No copyright in regular command output | Task 7, test `test_version_does_not_output_on_other_commands` |
| Do not modify `LICENSE` file | Not touched in any task |

### 2. Placeholder Scan

- No "TBD", "TODO", "implement later" found.
- All code blocks contain actual content.
- All test code is complete with assertions.
- No "similar to Task N" references.

### 3. Type Consistency

- `version_callback` signature unchanged (`def version_callback(value: bool) -> None`)
- `__version__` import unchanged
- No cross-task type mismatches.

---

## Summary of Files Modified

| File | Action | Task |
|------|--------|------|
| `NOTICE` | Create | 1 |
| `src/sanityops_cli/__init__.py` | Add header | 2 |
| `src/sanityops_cli/main.py` | Add header + update `version_callback` | 2, 7 |
| `entry.py` | Add header | 2 |
| `src/sanityops_cli/commands/__init__.py` | Add header | 3 |
| `src/sanityops_cli/commands/inspect.py` | Add header | 3 |
| `src/sanityops_cli/commands/init.py` | Add header | 3 |
| `src/sanityops_cli/agents/__init__.py` | Add header | 4 |
| `src/sanityops_cli/agents/scanner_agent/agent.py` | Add header | 4 |
| `src/sanityops_cli/agents/scanner_agent/hooks/progress_hook.py` | Add header | 4 |
| `src/sanityops_cli/agents/scanner_agent/models/finding.py` | Add header | 4 |
| `src/sanityops_cli/agents/scanner_agent/prompts.py` | Add header | 4 |
| `src/sanityops_cli/agents/scanner_agent/tools/grep_tool.py` | Add header | 4 |
| `src/sanityops_cli/agents/scanner_agent/tools/listfiles_tool.py` | Add header | 4 |
| `src/sanityops_cli/agents/scanner_agent/tools/readfile_tool.py` | Add header | 4 |
| `src/sanityops_cli/agents/scanner_agent/tools/storefindings_tool.py` | Add header | 4 |
| `src/sanityops_cli/utils/__init__.py` | Add header | 5 |
| `src/sanityops_cli/utils/config_loader.py` | Add header | 5 |
| `src/sanityops_cli/utils/validators.py` | Add header | 5 |
| `src/sanityops_cli/constants/__init__.py` | Add header | 5 |
| `src/sanityops_cli/constants/exit_codes.py` | Add header | 5 |
| `src/sanityops_cli/exceptions/__init__.py` | Add header | 5 |
| `src/sanityops_cli/exceptions/base_exceptions.py` | Add header | 5 |
| `src/sanityops_cli/exceptions/api_exceptions.py` | Add header | 5 |
| `src/sanityops_cli/renderers/__init__.py` | Add header | 6 |
| `src/sanityops_cli/renderers/command_renderer/inspect_command_renderer.py` | Add header | 6 |
| `src/sanityops_cli/progress/__init__.py` | Add header | 6 |
| `src/sanityops_cli/progress/tracker.py` | Add header | 6 |
| `src/sanityops_cli/templates/__init__.py` | Add header | 6 |
| `src/sanityops_cli/defect_checker/__init__.py` | Add header | 6 |
| `src/sanityops_cli/defect_checker/checker.py` | Add header | 6 |
| `src/sanityops_cli/defect_checker/llm_config.py` | Add header | 6 |
| `src/sanityops_cli/defect_checker/renderer.py` | Add header | 6 |
| `src/sanityops_cli/logging/__init__.py` | Add header | 6 |
| `src/sanityops_cli/logging/logger.py` | Add header | 6 |
| `tests/unit/commands/test_version.py` | Create | 7 |
