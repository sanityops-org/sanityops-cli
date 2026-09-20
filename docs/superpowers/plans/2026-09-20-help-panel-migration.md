# Help Panel Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate Getting Started and Advanced Usage help panels from deeplogic-cli to sanityops-cli.

**Architecture:** Copy `help_panel.py` verbatim, add `--help` interception logic in `main.py`, update entry points (`entry.py`, `pyproject.toml`) to call `main()` instead of `app()`, and add tests.

**Tech Stack:** Python 3.11+, Typer, Rich, pytest

## Global Constraints

- Copy `help_panel.py` verbatim — text still references `deeplogic-cli` (localization deferred)
- UTF-8 stream reconfiguration added for Windows GBK/cp936 compatibility
- Entry point in `pyproject.toml` must change from `:app` to `:main`
- Remove CJK assertion tests (to be re-added when text is localized)
- All 7 final tests must pass
- Existing tests must continue to pass

---

### Task 1: Create `help_panel.py`

**Files:**
- Create: `src/sanityops_cli/help_panel.py`

**Interfaces:**
- Produces: `GETTING_STARTED_TEXT` (str), `ADVANCED_USAGE_TEXT` (str), `get_getting_started_panel()` → `Panel`, `get_advanced_usage_panel()` → `Panel`

- [ ] **Step 1: Create `help_panel.py` with verbatim copy from deeplogic-cli**

```python
"""Getting Started panel for CLI help output."""

from rich.panel import Panel
from rich.text import Text

GETTING_STARTED_TEXT = """\
  1. Run 'deeplogic-cli init' to create the default configuration
  2. Edit .deeplogic/inspect_config.yaml to configure your project
  3. Run 'deeplogic-cli inspect' to start the inspection
  4. Run 'deeplogic-cli inspect repair' to generate fixes (optional)
  5. Run 'deeplogic-cli inspect cover' to apply fixes (optional)\
"""

ADVANCED_USAGE_TEXT = """\
  CI/CD Integration:
    1. Commit .deeplogic/inspect_config.yaml to the repository
    2. Set LLM API keys via environment variables (never commit sensitive keys)
    3. Run 'deeplogic-cli inspect' in the pipeline

  Config Command (deeplogic-cli config --help):
    View detailed configuration options and usage examples\
"""


def get_getting_started_panel() -> Panel:
    """Create the Getting Started panel for help output.

    Returns:
        A Rich Panel containing the 5-step Getting Started workflow.
    """
    return Panel(
        Text(GETTING_STARTED_TEXT, justify="left"),
        title="Getting Started",
        border_style="blue",
        padding=(0, 1),
    )


def get_advanced_usage_panel() -> Panel:
    """Create the Advanced Usage panel for help output.

    Returns:
        A Rich Panel containing CI/CD integration and config reference.
    """
    return Panel(
        Text(ADVANCED_USAGE_TEXT, justify="left"),
        title="Advanced Usage",
        border_style="cyan",
        padding=(0, 1),
    )
```

- [ ] **Step 2: Verify file is importable**

Run:
```bash
python -c "from sanityops_cli.help_panel import get_getting_started_panel, get_advanced_usage_panel; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/sanityops_cli/help_panel.py
git commit -m "feat(help): add Getting Started and Advanced Usage panels from deeplogic-cli"
```

---

### Task 2: Write tests for help panel and main() interception

**Files:**
- Create: `tests/test_help_panel.py`

**Interfaces:**
- Consumes: `help_panel.py` from Task 1, `main()` from Task 3 (tests will fail until Task 3 complete)
- Produces: Test coverage for panels and entry point behavior

- [ ] **Step 1: Create `tests/test_help_panel.py` with adapted tests**

```python
"""Tests for the Getting Started and Advanced Usage help panels."""

import subprocess
import sys
from pathlib import Path

from rich.panel import Panel

from sanityops_cli.help_panel import (
    ADVANCED_USAGE_TEXT,
    GETTING_STARTED_TEXT,
    get_advanced_usage_panel,
    get_getting_started_panel,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_getting_started_text_content():
    """Verify the Getting Started text contains all 5 steps."""
    assert "deeplogic-cli init" in GETTING_STARTED_TEXT
    assert "inspect_config.yaml" in GETTING_STARTED_TEXT
    assert "deeplogic-cli inspect" in GETTING_STARTED_TEXT
    assert "deeplogic-cli inspect repair" in GETTING_STARTED_TEXT
    assert "deeplogic-cli inspect cover" in GETTING_STARTED_TEXT
    assert "(optional)" in GETTING_STARTED_TEXT


def test_getting_started_panel_returns_panel():
    """Verify the function returns a Rich Panel."""
    panel = get_getting_started_panel()
    assert isinstance(panel, Panel)


def test_getting_started_panel_has_correct_title():
    """Verify the panel has the correct title."""
    panel = get_getting_started_panel()
    assert panel.title is not None
    assert "Getting Started" in str(panel.title)


def test_advanced_usage_text_content():
    """Verify the Advanced Usage text contains CI/CD integration."""
    assert "CI/CD" in ADVANCED_USAGE_TEXT
    assert "inspect_config.yaml" in ADVANCED_USAGE_TEXT
    assert "environment variables" in ADVANCED_USAGE_TEXT
    assert "deeplogic-cli config --help" in ADVANCED_USAGE_TEXT


def test_advanced_usage_panel_returns_panel():
    """Verify the function returns a Rich Panel."""
    panel = get_advanced_usage_panel()
    assert isinstance(panel, Panel)


def test_advanced_usage_panel_has_correct_title():
    """Verify the panel has the correct title."""
    panel = get_advanced_usage_panel()
    assert panel.title is not None
    assert "Advanced Usage" in str(panel.title)


def test_entry_point_shows_getting_started_on_help():
    """Verify the PyInstaller entry point (entry.py) shows the Getting Started panel.

    Regression test: entry.py used to call app() directly, bypassing the
    Getting Started panel logic in main(), so the packaged binary's --help
    output was missing the panel while pip-installed runs showed it.
    """
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "entry.py"), "--help"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=60,
    )
    assert result.returncode == 0
    assert "Getting Started" in result.stdout


def test_entry_point_shows_advanced_usage_on_help():
    """Verify the entry point shows the Advanced Usage panel."""
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "entry.py"), "--help"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=60,
    )
    assert result.returncode == 0
    assert "Advanced Usage" in result.stdout


def test_entry_point_shows_getting_started_with_no_args():
    """Verify the PyInstaller entry point shows the panel with no arguments."""
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "entry.py")],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=60,
    )
    assert result.returncode == 0
    assert "Getting Started" in result.stdout
    assert "Advanced Usage" in result.stdout
```

- [ ] **Step 2: Run unit tests (panel functions) — should pass**

Run:
```bash
pytest tests/test_help_panel.py -v -k "not entry_point"
```

Expected: 4 PASS (panel tests)

- [ ] **Step 3: Run entry point tests — should FAIL (main() not yet updated)**

Run:
```bash
pytest tests/test_help_panel.py -v -k "entry_point"
```

Expected: 3 FAIL — entry.py still calls `app()`, panels not shown

- [ ] **Step 4: Commit test file**

```bash
git add tests/test_help_panel.py
git commit -m "test(help): add tests for help panels and entry point behavior"
```

---

### Task 3: Update `main.py` with help interception logic

**Files:**
- Modify: `src/sanityops_cli/main.py`

**Interfaces:**
- Consumes: `help_panel.py` from Task 1
- Produces: `main()` with `--help` interception that prints panels

- [ ] **Step 1: Add UTF-8 reconfiguration block after imports**

Insert after line 18 (after `import sys`), before `import typer`:

```python
# Windows consoles default to GBK/cp936 in zh-CN locales, which cannot encode
# symbols like ✓/✗/⚠ used throughout the CLI output. Force UTF-8 streams early
# so output never crashes regardless of terminal code page.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass
```

- [ ] **Step 2: Add new imports after existing imports**

Add after the `from sanityops_cli.exceptions.base_exceptions import ValidationError` line:

```python
from rich.console import Console

from sanityops_cli.help_panel import (
    get_advanced_usage_panel,
    get_getting_started_panel,
)
```

- [ ] **Step 3: Replace the `main()` function with interception logic**

Replace lines 65-78 (the entire `main()` function) with:

```python
def main():
    """Entrance function for the Sanityops CLI application."""
    # Check if --help is requested for the main app only (no subcommand)
    is_help = "--help" in sys.argv or "-h" in sys.argv
    is_version = "--version" in sys.argv or "-V" in sys.argv
    has_subcommand = any(arg and not arg.startswith("-") for arg in sys.argv[1:])
    is_no_args_help = len(sys.argv) == 1

    if (is_help or is_no_args_help) and not is_version and not has_subcommand:
        console = Console()
        try:
            app()
        except SystemExit as e:
            if e.code not in (0, 2):
                raise
        console.print()
        console.print(get_getting_started_panel())
        console.print()
        console.print(get_advanced_usage_panel())
        return

    try:
        app()
    except ValidationError as e:
        print(f"Validation Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unknown Error: {e}", file=sys.stderr)
        sys.exit(1)
```

- [ ] **Step 4: Run entry point tests — should now PASS**

Run:
```bash
pytest tests/test_help_panel.py -v
```

Expected: 7 PASS

- [ ] **Step 5: Verify existing tests still pass**

Run:
```bash
pytest tests/ -v
```

Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add src/sanityops_cli/main.py
git commit -m "feat(help): add --help interception to show Getting Started and Advanced Usage panels"
```

---

### Task 4: Update `entry.py` to call `main()`

**Files:**
- Modify: `entry.py`

**Interfaces:**
- Consumes: `main()` from Task 3

- [ ] **Step 1: Replace `entry.py` content**

Replace the entire file with:

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

from sanityops_cli.main import main

# Use main() (not app()) so the packaged binary matches the pip-installed
# entry point, including the Getting Started panel on --help / no-args.
main()
```

- [ ] **Step 2: Verify entry point tests still pass**

Run:
```bash
pytest tests/test_help_panel.py::test_entry_point_shows_getting_started_on_help tests/test_help_panel.py::test_entry_point_shows_advanced_usage_on_help tests/test_help_panel.py::test_entry_point_shows_getting_started_with_no_args -v
```

Expected: 3 PASS

- [ ] **Step 3: Commit**

```bash
git add entry.py
git commit -m "fix(entry): call main() instead of app() to include help panels"
```

---

### Task 5: Update `pyproject.toml` entry point

**Files:**
- Modify: `pyproject.toml`

**Interfaces:**
- None (build configuration)

- [ ] **Step 1: Update entry point from `:app` to `:main`**

Change line 41 from:
```toml
sanityops-cli = "sanityops_cli.main:app"
```

To:
```toml
sanityops-cli = "sanityops_cli.main:main"
```

- [ ] **Step 2: Verify all tests pass**

Run:
```bash
pytest tests/ -v
```

Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "fix(pyproject): use main entry point for help panel support"
```

---

### Task 6: Final verification

**Files:**
- None (verification only)

- [ ] **Step 1: Run full test suite**

Run:
```bash
pytest tests/ -v
```

Expected: All tests pass

- [ ] **Step 2: Manual verification of `--help` output**

Run:
```bash
python entry.py --help
```

Expected: Shows Typer help followed by Getting Started panel and Advanced Usage panel

- [ ] **Step 3: Manual verification of no-args behavior**

Run:
```bash
python entry.py
```

Expected: Same as `--help` — shows help plus both panels

- [ ] **Step 4: Verify subcommand help does NOT show panels**

Run:
```bash
python entry.py inspect --help
```

Expected: Shows only `inspect` subcommand help, no panels

- [ ] **Step 5: Verify `--version` does NOT show panels**

Run:
```bash
python entry.py --version
```

Expected: Shows version info only, no panels

- [ ] **Step 6: Final commit (if any verification fixes needed)**

If any issues found and fixed, commit. Otherwise, no action needed.