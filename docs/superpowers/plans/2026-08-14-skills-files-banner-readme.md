# Skills-as-Files, Run Banner, and README Sync — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align the `skills` section of `inspect_config.yaml` with `prompts`/`tools` so it accepts only explicitly-specified files, print a run banner (version + Python + platform) right before the `Project ID:` line in Step 1, and update README's "Configure Artifacts" example to match the current template.

**Architecture:** Three independent, small changes. (1) `InspectConfigLoader._process_skills` is simplified to delegate to the existing `_process_file_entries`, deleting the recursive directory-walking machinery (`_find_skill_files_in_dir`, `_is_skill_file`, `_SKILL_FRONTMATTER_RE`) and the now-unused `EXCLUDED_DIRS` import; the template drops the `- file: skills/` example and the "file or directory" wording. (2) A module-level `_banner_line()` helper in `commands/inspect.py` builds `sanityops-cli v0.0.2 | Python 3.12.5 | darwin/arm64` from `__version__` + `platform` + `sys`, printed in `[dim]` immediately before the `Project ID:` line. (3) README's config example is rewritten to `file:` syntax, the optional `model:` section, and skills as `.md` files.

**Tech Stack:** Python 3.11+, Typer, Rich, PyYAML (existing); stdlib `platform`, `sys`.

## Global Constraints

- Python `>=3.11`; dependencies unchanged.
- Ruff: `line-length = 100`; lint select `E, W, F, I, B, UP`; isort `known-first-party = ["sanityops_cli"]`.
- All user-facing text is **English**.
- `skills`, like `prompts` and `tools`, accepts a YAML list of entries that are either a bare string path or a dict with a `file:` key; each must resolve to an **existing file**. A directory raises `ValidationError`.
- `EXCLUDED_DIRS` **stays** defined in `src/sanityops_cli/utils/validators.py` (still used by `validate_inspect_directory`); only its import is removed from `config_loader.py`.
- The `re` import in `config_loader.py` is **kept** (still used for UUID validation).
- Banner format is exactly: `sanityops-cli v{__version__} | Python {platform.python_version()} | {sys.platform}/{platform.machine()}`.
- The banner prints in `[dim]` style, directly before the existing `Project ID:` line.
- Run tests with `python -m pytest <path>`; full-suite baseline is **90 passing**.
- Test config uses `monkeypatch.setenv("HOME", str(tmp_path))` and the `runner`/`Console(file=io.StringIO())` patterns already in `tests/unit/commands/test_inspect.py`.

---

### Task 1: Skills accept files only (loader + template)

**Files:**
- Modify: `src/sanityops_cli/utils/config_loader.py:1-12` (imports), `:219-247` (`_process_skills`), delete `:249-284` (`_find_skill_files_in_dir`, `_is_skill_file`, `_SKILL_FRONTMATTER_RE` is at `:19-28`)
- Modify: `src/sanityops_cli/templates/inspect_config.yaml:36-40`
- Modify: `tests/unit/utils/test_config_loader.py` (add new test class)

**Interfaces:**
- Consumes: existing `_process_file_entries(entries, label) -> list[str]` (unchanged).
- Produces: `InspectConfigLoader.load()` behavior — `skills` now files-only; `load()` signature and return shape unchanged, so Tasks 2–3 and all downstream callers are unaffected.

- [ ] **Step 1: Write the failing tests**

Append a new test class to `tests/unit/utils/test_config_loader.py` (after `TestModelSectionValidation`):

```python
class TestSkillsSectionFilesOnly:
    """Skills entries must be existing files, not directories."""

    def _write_config(self, tmp_path: Path, skills_entries: list) -> Path:
        config_dir = tmp_path / ".sanityops"
        config_dir.mkdir()
        config_file = config_dir / "inspect_config.yaml"
        config_content = {
            "project": {"id": "00000000-0000-0000-0000-0000000000aa"},
            "skills": skills_entries,
        }
        with open(config_file, "w") as f:
            yaml.dump(config_content, f)
        return config_file

    def test_skills_file_resolves_absolute_path(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        skill_file = tmp_path / "code_review.md"
        skill_file.write_text("# code review\n")
        config_file = self._write_config(tmp_path, [{"file": "code_review.md"}])
        loader = InspectConfigLoader(str(config_file))
        result = loader.load()
        assert result["skills"] == [str(skill_file.resolve())]

    def test_skills_directory_raises_error(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "skills_dir").mkdir()
        config_file = self._write_config(tmp_path, [{"file": "skills_dir"}])
        loader = InspectConfigLoader(str(config_file))
        with pytest.raises(ValidationError) as excinfo:
            loader.load()
        assert "not a file" in str(excinfo.value).lower()

    def test_skills_missing_file_raises_error(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        config_file = self._write_config(tmp_path, [{"file": "missing.md"}])
        loader = InspectConfigLoader(str(config_file))
        with pytest.raises(ValidationError) as excinfo:
            loader.load()
        assert "not found" in str(excinfo.value).lower()
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `python -m pytest tests/unit/utils/test_config_loader.py -q`
Expected: the three new tests in `TestSkillsSectionFilesOnly` FAIL; `test_skills_directory_raises_error` fails because the current `_process_skills` walks directories instead of raising. (Existing `TestModelSectionValidation` tests still pass.)

- [ ] **Step 3: Implement the loader change**

In `src/sanityops_cli/utils/config_loader.py`:

1. Remove the `EXCLUDED_DIRS` import (line 12) and the `_SKILL_FRONTMATTER_RE` block (lines 19-28):

```python
import re
from pathlib import Path
from typing import Any

import yaml

from sanityops_cli.exceptions.base_exceptions import ValidationError
```

(Keep `import re` — it is used by `_validate_structure` for UUID validation.)

2. Replace the entire `_process_skills` method (lines 219-247) **and** delete `_find_skill_files_in_dir` (lines 249-260) and `_is_skill_file` (lines 262-284), leaving the `# Entry parsing helper` section header and `_extract_file_value` untouched. The new `_process_skills`:

```python
    def _process_skills(self) -> list[str]:
        """Validate skill files and return absolute paths (files only)."""
        entries = self._config.get("skills", [])
        if entries is None:
            entries = []
        return self._process_file_entries(entries, "skills")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/utils/test_config_loader.py -q`
Expected: all pass (3 model-section-independent new tests + existing `TestModelSectionValidation`).

- [ ] **Step 5: Update the template**

In `src/sanityops_cli/templates/inspect_config.yaml`, replace the `skills:` block (lines 36-40):

```yaml
# Skills file list (supports any plaintext file format)
skills:
  - file: skills/code_review.md
  - file: skills/code_fix/skill.md
```

- [ ] **Step 6: Verify template does not break init tests**

Run: `python -m pytest tests/commands/test_init.py -q`
Expected: all pass (init tests assert on `project`/`model` comments, not the `skills` section).

- [ ] **Step 7: Commit**

```bash
git add src/sanityops_cli/utils/config_loader.py src/sanityops_cli/templates/inspect_config.yaml tests/unit/utils/test_config_loader.py
git commit -m "fix(config): skills accept only files, like prompts/tools"
```

---

### Task 2: Run banner before `Project ID:`

**Files:**
- Modify: `src/sanityops_cli/commands/inspect.py:1-23` (imports), `:99` (call site)
- Modify: `tests/unit/commands/test_inspect.py` (add banner tests)

**Interfaces:**
- Produces: `_banner_line() -> str` — module-level helper in `commands/inspect.py`, used by the command and imported by tests.
- Consumes: `__version__` from `sanityops_cli` (already exported), stdlib `platform`, `sys`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/commands/test_inspect.py`:

```python
def test_banner_line_contains_version_python_and_platform():
    import platform

    from sanityops_cli import __version__
    from sanityops_cli.commands.inspect import _banner_line

    line = _banner_line()
    assert f"sanityops-cli v{__version__}" in line
    assert platform.python_version() in line
    assert "|" in line


def test_inspect_prints_banner_before_project_id(monkeypatch, tmp_path):
    """The run banner should appear directly before the Project ID line."""
    monkeypatch.setenv("HOME", str(tmp_path))
    skill_file = tmp_path / "skill.md"
    skill_file.write_text("---\nname: s\ndescription: d\n---\n# X\n")
    cfg = tmp_path / "inspect_config.yaml"
    cfg.write_text(
        "project:\n  id: 00000000-0000-0000-0000-000000000000\n"
        f"skills:\n  - file: {skill_file}\n"
    )

    class FakeAgent:
        def analyze_files_sync(self, prompts, tools, skills):
            return _findings()

    monkeypatch.setattr(
        "sanityops_cli.commands.inspect.ScannerAgent",
        lambda *a, **k: FakeAgent(),
    )

    output = io.StringIO()
    test_console = Console(file=output, record=True)
    monkeypatch.setattr("sanityops_cli.commands.inspect.console", test_console)

    result = runner.invoke(app, ["inspect", "--config", str(cfg), "--skip-defect-check"])
    assert result.exit_code == 0
    text = output.getvalue()
    assert "sanityops-cli v0.0.2" in text
    assert "Project ID: 00000000-0000-0000-0000-000000000000" in text
    # banner line precedes the Project ID line
    assert text.index("sanityops-cli v0.0.2") < text.index("Project ID:")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/commands/test_inspect.py -q`
Expected: FAIL with `ImportError: cannot import name '_banner_line' from 'sanityops_cli.commands.inspect'`.

- [ ] **Step 3: Implement the change**

In `src/sanityops_cli/commands/inspect.py`:

1. Update the imports:

```python
import anyio
import platform
import sys
import typer
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from sanityops_cli import __version__
from sanityops_cli.agents.scanner_agent.agent import ScannerAgent
from sanityops_cli.constants.exit_codes import EXIT_FAILURE
from sanityops_cli.defect_checker.checker import DefectChecker
from sanityops_cli.defect_checker.llm_config import resolve_llm_config
from sanityops_cli.defect_checker.renderer import DefectRenderer
from sanityops_cli.exceptions.base_exceptions import ValidationError
from sanityops_cli.logging.logger import Logger
from sanityops_cli.progress.tracker import ProgressTracker
from sanityops_cli.utils.config_loader import InspectConfigLoader
```

2. Add the `_banner_line` helper after the module docstring/imports (before `_report_program_error`):

```python
def _banner_line() -> str:
    """Return a one-line run banner: program version, Python version, platform."""
    return (
        f"sanityops-cli v{__version__} | Python {platform.python_version()} "
        f"| {sys.platform}/{platform.machine()}"
    )
```

3. At the artifact-display call site, before the `Project ID:` line (line 99):

```python
    console.print(f"[dim]{_banner_line()}[/dim]")
    console.print(f"[dim]Project ID: {project_id}[/dim]")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/commands/test_inspect.py -q`
Expected: all pass (2 new banner tests + existing inspect tests; the added line doesn't break existing substring assertions).

- [ ] **Step 5: Commit**

```bash
git add src/sanityops_cli/commands/inspect.py tests/unit/commands/test_inspect.py
git commit -m "feat(inspect): print version/Python/platform banner before Project ID"
```

---

### Task 3: Sync README with the inspect_config.yaml template

**Files:**
- Modify: `README.md:54-108` (Quick Start section)

**Interfaces:**
- Consumes: the finalized template shape from Task 1 (skills as files, `file:` syntax, optional `model:` section).
- Produces: README "Configure Artifacts" example and surrounding prose that match what `sanityops-cli init` generates.

- [ ] **Step 1: Update the Configure Artifacts example**

In `README.md`, replace the "### 2. Configure Artifacts" block (lines 64-80):

```markdown
### 2. Configure Artifacts

Edit `.sanityops/inspect_config.yaml` to specify your artifacts:

```yaml
project:
  id: <your-project-id>          # required: UUID

# Optional: omit to use LLM_* environment variables
# model:
#   provider: anthropic
#   api_key: sk-ant-...
#   model_id: claude-sonnet-4-20250514
#   base_url: ""

prompts:
  - file: prompts/system_prompt.md

tools:
  - file: tools/search_tools.json

skills:
  - file: skills/code_review.md   # file only, not directories
```
```

- [ ] **Step 2: Add the init note to Quick Start step 1**

In `README.md`, replace the "### 1. Initialize Configuration" block (lines 56-62):

```markdown
### 1. Initialize Configuration

```bash
sanityops-cli init
```

This creates `.sanityops/inspect_config.yaml` in your current directory with a
freshly generated project UUID. The generated file matches the template below —
edit the artifact paths to point at your prompts, tools, and skills.
```

- [ ] **Step 3: Verify the README references match the template**

Run:

```bash
grep -n "file: prompts/\|file: tools/\|file: skills/\|file only" README.md
```

Expected: three `file:` lines and one "file only" comment in the Configure Artifacts example. Also run `python -m pytest -q` to confirm the full suite is still green (90 passing).

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs(readme): sync config example with inspect_config.yaml template"
```

---

## Self-Review

- **Spec coverage:**
  - Fix 1 (skills files-only): Task 1 — `_process_skills` delegates to `_process_file_entries` (directory raises `[skills] path is not a file`), dead machinery removed, template comment + example updated. Tests: directory → error, file → resolved path, missing file → error.
  - Fix 2 (banner before `Project ID:`): Task 2 — `_banner_line()` (version + `platform.python_version()` + `sys.platform`/`platform.machine()`) printed in `[dim]` directly before the `Project ID:` line. Tests: direct `_banner_line()` unit test + CLI presence/ordering assertion.
  - Fix 3 (README sync): Task 3 — `file:` syntax, optional `model:` section, skills as `.md` files only, plus a note that `init` generates the file with a fresh UUID.
- **Placeholder scan:** every step has concrete code, exact file paths, runnable commands, and expected output. No TBD/TODO.
- **Type consistency:** `_process_file_entries(entries, "skills")` matches the existing signature (Task 1). `_banner_line() -> str` is defined in Task 2 Step 3 and used/imported in Task 2 Steps 1 and 3 identically. `load()` return shape (`project_id`, `prompts`, `tools`, `skills`) is unchanged across all tasks. `EXCLUDED_DIRS` stays in `validators.py`; only the `config_loader.py` import is removed — verified consistent with `validators.py:45`.
