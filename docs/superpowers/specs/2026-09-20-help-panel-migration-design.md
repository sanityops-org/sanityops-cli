# Help Panel Migration — Design Spec

**Date:** 2026-09-20
**Source:** `/Users/a1234/Documents/project/gitlab/deeplogic-cli`
**Target:** `/Users/a1234/Documents/project/sanityops-cli`

## Summary

Migrate the Getting Started and Advanced Usage help panels from deeplogic-cli to sanityops-cli. The panels appear when users run `sanityops-cli --help` or `sanityops-cli` with no arguments, providing a 5-step quick start workflow and CI/CD integration guidance.

## Files Changed

| File | Action |
|------|--------|
| `src/sanityops_cli/help_panel.py` | Create (copy from deeplogic-cli) |
| `src/sanityops_cli/main.py` | Modify (add help interception logic) |
| `entry.py` | Modify (call `main()` instead of `app()`) |
| `pyproject.toml` | Modify (entry point `:app` → `:main`) |
| `tests/test_help_panel.py` | Create (copy, adapted imports, CJK tests removed) |

## Component Details

### 1. `help_panel.py` (new)

Copy verbatim from deeplogic-cli. Contains:

- `GETTING_STARTED_TEXT` — 5-step workflow string
- `ADVANCED_USAGE_TEXT` — CI/CD integration guidance string
- `get_getting_started_panel()` — Returns Rich `Panel` with blue border
- `get_advanced_usage_panel()` — Returns Rich `Panel` with cyan border

Text references `deeplogic-cli` (to be localized later per user decision).

### 2. `main.py` (modify)

Add at top of file (after imports):

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

Add imports:

```python
from rich.console import Console
from sanityops_cli.help_panel import (
    get_advanced_usage_panel,
    get_getting_started_panel,
)
```

Replace `main()` function with interception logic:

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

### 3. `entry.py` (modify)

Change:

```python
from sanityops_cli.main import app

app()
```

To:

```python
from sanityops_cli.main import main

# Use main() (not app()) so the packaged binary matches the pip-installed
# entry point, including the Getting Started panel on --help / no-args.
main()
```

### 4. `pyproject.toml` (modify)

Change entry point from `:app` to `:main`:

```toml
[project.scripts]
sanityops-cli = "sanityops_cli.main:main"
```

### 5. `tests/test_help_panel.py` (new)

Copy from deeplogic-cli with these changes:
- Import path `deeplogic_cli` → `sanityops_cli`
- **Remove** `test_getting_started_text_is_english()` and `test_advanced_usage_text_is_english()` (CJK assertion tests — will be added back when text is localized)

Tests included:
- `test_getting_started_text_content()` — verifies 5 steps present
- `test_getting_started_panel_returns_panel()` — verifies return type
- `test_getting_started_panel_has_correct_title()` — verifies title
- `test_advanced_usage_text_content()` — verifies CI/CD content
- `test_advanced_usage_panel_returns_panel()` — verifies return type
- `test_advanced_usage_panel_has_correct_title()` — verifies title
- `test_entry_point_shows_getting_started_on_help()` — subprocess test against entry.py
- `test_entry_point_shows_advanced_usage_on_help()` — subprocess test
- `test_entry_point_shows_getting_started_with_no_args()` — subprocess test

## Data Flow

```
sanityops-cli --help (or no args)
  → console_scripts entry point → main()
  → sys.argv inspection:
     - is_help=True (or is_no_args_help=True)
     - has_subcommand=False
     - is_version=False
  → app() runs, exits with SystemExit(0) or (2)
  → except SystemExit: code in (0,2) → swallow; else re-raise
  → console.print(getting_started_panel)
  → console.print(advanced_usage_panel)
  → return (implicit exit 0)

sanityops-cli inspect --help
  → has_subcommand=True
  → falls through to plain app()
  → panels correctly NOT shown (subcommand help only)
```

## Out of Scope

- Localizing text from `deeplogic-cli` to `sanityops-cli` (deferred)
- Adding `project` command (does not exist in sanityops-cli)
- Migrating other deeplogic-cli features

## Acceptance Criteria

1. `sanityops-cli --help` shows Getting Started panel followed by Advanced Usage panel
2. `sanityops-cli` (no args) shows both panels
3. `sanityops-cli inspect --help` does NOT show panels (subcommand help only)
4. `sanityops-cli --version` does NOT show panels
5. `python entry.py --help` shows both panels (PyInstaller binary behavior)
6. All 7 tests in `test_help_panel.py` pass
7. Existing tests continue to pass