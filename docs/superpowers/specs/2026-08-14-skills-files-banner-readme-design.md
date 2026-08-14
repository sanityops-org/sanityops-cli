# Skills-as-Files, Run Banner, and README Sync - Design Spec

## Overview

Three small, independent fixes to the `inspect` command surface and its documentation:

1. **Skills accept files only** — align the `skills` section of `inspect_config.yaml` with `prompts`/`tools`, which already accept only explicitly-specified files. Remove directory support from the loader and the template.
2. **Run banner before `Project ID:`** — print a one-line banner (program version + Python version + platform) immediately before the `Project ID:` line in Step 1's artifact display.
3. **README sync with template** — update the README's "Configure Artifacts" example to match the current `inspect_config.yaml` template (`file:` key syntax, optional `model:` section, skills as `.md` files).

## Goals

1. Consistent artifact-type semantics: `prompts`, `tools`, and `skills` all accept only explicitly-listed files.
2. Users can see at a glance which program version and runtime environment produced a run (useful for bug reports / CI logs).
3. README example matches what `sanityops-cli init` actually generates, so users aren't misled by stale syntax.

## Non-Goals

- No change to `ScannerAgent` behavior or the defect-check pipeline.
- No change to `prompts`/`tools` handling (already file-only).
- No change to the `model:` section validation rules.
- No new config options.

---

## Fix 1 — Skills accept files only

### Template changes

File: `src/sanityops_cli/templates/inspect_config.yaml`

- Comment on the `skills:` block changes from `# Skills file list (file or directory)` to `# Skills file list`.
- Remove the directory example `- file: skills/`; keep the two file examples.

### Loader changes

File: `src/sanityops_cli/utils/config_loader.py`

- `_process_skills` is simplified to delegate to the existing `_process_file_entries(entries, "skills")`, which already validates that each entry exists and is a file, and raises `ValidationError("[skills] path is not a file: ...")` for a directory.
- Delete the now-unused directory machinery:
  - `_find_skill_files_in_dir`
  - `_is_skill_file`
  - `_SKILL_FRONTMATTER_RE`
  - the `EXCLUDED_DIRS` import (the constant remains defined in `utils/validators.py`, which still uses it)
- `re` import stays (still used for UUID validation in `_validate_structure`).

Result: one shared validation path for all three artifact types; passing a directory to `skills` is a clear error rather than a silent recursive scan.

### Tests

File: `tests/unit/utils/test_config_loader.py` (new test class alongside the existing model-section tests)

- `skills` entry pointing to a directory → raises `ValidationError` with a "not a file" message.
- `skills` entry pointing to an existing file → resolved absolute path is included in the result.
- `skills` entry pointing to a missing file → raises `ValidationError`.

---

## Fix 2 — Run banner before `Project ID:`

### Behavior

In `src/sanityops_cli/commands/inspect.py`, immediately before the existing `Project ID:` line, print one banner line in `[dim]` style:

```
sanityops-cli v0.0.2 | Python 3.12.5 | darwin/arm64
Project ID: ...
```

### Implementation

- New module-level helper `_banner_line() -> str` in `inspect.py` producing the string above.
- Components:
  - `__version__` imported from `sanityops_cli` (already exported)
  - `platform.python_version()`
  - `sys.platform` + `platform.machine()` (compact form, e.g. `darwin/arm64`)
- Call site: `console.print(f"[dim]{_banner_line()}[/dim]")` right before the `Project ID:` print in the artifact display block (Step 1 output).

### Tests

- Unit test `_banner_line()` directly (assert it contains the version and `python`/platform fragments).
- CLI test: assert the banner line appears in inspect output (existing tests substring-match specific strings, so the added line does not break them).

---

## Fix 3 — README sync with template

File: `README.md`, "Configure Artifacts" example (currently bare paths, e.g. `- path/to/system_prompt.md`).

Update the YAML example to match the current template:

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

Additionally:

- Add one sentence noting that `sanityops-cli init` generates this exact file (`.sanityops/inspect_config.yaml`) with a fresh project UUID.
- The skills comment reflects that only files are accepted (consistent with Fix 1).

---

## Design Decisions

- **Reuse `_process_file_entries` for skills** rather than duplicating validation: single code path, consistent error messages, less code. The trade-off — a generic "path is not a file" message instead of a skills-specific "directories not supported" message — is acceptable; the message names the section (`[skills]`) and the resolved path.
- **Compact platform string** (`darwin/arm64`) rather than the verbose `platform.platform()` output (`macOS-15.5-arm64-arm-64bit`) to keep the banner readable on one line.
- **Banner placed in Step 1 output** (right before `Project ID:`) as requested, rather than at the very top of the run — avoids duplicating the step progress display and keeps the requested position.

## Testing

- Loader: new `ValidationError` cases for directory/missing skill paths; happy-path file resolution.
- Banner: direct unit test of `_banner_line()` plus a CLI-level presence assertion.
- Regression: full `pytest` suite must stay green; existing CLI tests only substring-match output, so the added banner line is safe.

## Risks / Open Questions

- None identified. The three changes are isolated and low-risk.
