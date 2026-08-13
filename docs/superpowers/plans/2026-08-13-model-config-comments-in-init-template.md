# Model Config Comments in Init Template Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve YAML comments in the generated config file when users run `sanityops-cli init`, so they can see model configuration options.

**Architecture:** Switch from YAML parse/serialize to string-based template processing. Read template as raw string, replace UUID placeholder, write directly to file.

**Tech Stack:** Python 3.11+, PyYAML (existing), importlib.resources (stdlib)

## Global Constraints

- No new dependencies
- Backward compatible - existing config files unchanged
- Preserve all comments in template file
- UUID placeholder format: `00000000-0000-0000-0000-000000000000`

---

## File Structure

| File | Responsibility |
|------|----------------|
| `src/sanityops_cli/templates/inspect_config.yaml` | Template with improved model comments |
| `src/sanityops_cli/commands/init.py` | String-based template processing |
| `tests/commands/test_init.py` | Test comment preservation |

---

### Task 1: Write failing tests for comment preservation

**Files:**
- Modify: `tests/commands/test_init.py`

**Interfaces:**
- Consumes: `init_config()` from `sanityops_cli.commands.init`
- Produces: Test assertions that will drive implementation

- [ ] **Step 1: Write test for model configuration comment**

Add to `tests/commands/test_init.py` after the existing test class:

```python
class TestInitConfigPreservesComments:
    """Test that init preserves YAML comments in template."""

    def test_generated_config_contains_model_comment(self, tmp_path: Path, monkeypatch):
        """Should preserve '# Model configuration' comment in output."""
        # Arrange
        monkeypatch.chdir(tmp_path)

        from sanityops_cli.commands.init import init_config

        # Act
        init_config()

        # Assert
        config_file = tmp_path / ".sanityops" / "inspect_config.yaml"
        content = config_file.read_text()
        assert "# Model configuration" in content, "Model configuration header comment should be preserved"

    def test_generated_config_contains_provider_comment(self, tmp_path: Path, monkeypatch):
        """Should preserve provider field comment with examples."""
        # Arrange
        monkeypatch.chdir(tmp_path)

        from sanityops_cli.commands.init import init_config

        # Act
        init_config()

        # Assert
        config_file = tmp_path / ".sanityops" / "inspect_config.yaml"
        content = config_file.read_text()
        assert "# provider:" in content or "provider:" in content, "Provider field comment should be preserved"

    def test_generated_config_contains_required_optional_labels(self, tmp_path: Path, monkeypatch):
        """Should preserve Required/Optional labels in comments."""
        # Arrange
        monkeypatch.chdir(tmp_path)

        from sanityops_cli.commands.init import init_config

        # Act
        init_config()

        # Assert
        config_file = tmp_path / ".sanityops" / "inspect_config.yaml"
        content = config_file.read_text()
        assert "Required:" in content or "# Required" in content, "Required labels should be in comments"

    def test_generated_config_has_valid_uuid_not_placeholder(self, tmp_path: Path, monkeypatch):
        """Should replace placeholder UUID with real UUID."""
        # Arrange
        monkeypatch.chdir(tmp_path)

        from sanityops_cli.commands.init import init_config

        # Act
        init_config()

        # Assert
        config_file = tmp_path / ".sanityops" / "inspect_config.yaml"
        content = config_file.read_text()
        assert "00000000-0000-0000-0000-000000000000" not in content, "Placeholder UUID should be replaced"

        # Verify the actual UUID is valid
        data = yaml.safe_load(content)
        uuid.UUID(data["project"]["id"])  # raises if invalid
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/commands/test_init.py::TestInitConfigPreservesComments -v`

Expected: FAIL - tests should fail because comments are stripped by current yaml.dump()

```bash
pytest tests/commands/test_init.py::TestInitConfigPreservesComments -v
```

- [ ] **Step 3: Commit failing tests**

```bash
git add tests/commands/test_init.py
git commit -m "test: add failing tests for comment preservation in init"
```

---

### Task 2: Update template with improved model comments

**Files:**
- Modify: `src/sanityops_cli/templates/inspect_config.yaml`

**Interfaces:**
- Consumes: None
- Produces: Template string with improved comments

- [ ] **Step 1: Replace model section comments**

Replace lines 14-21 in `src/sanityops_cli/templates/inspect_config.yaml`:

**Before:**
```yaml
# Model configuration (optional). If this section is present, its values
# take precedence over the LLM_* environment variables. If omitted, the
# CLI falls back to environment-variable configuration.
# model:
#   provider: anthropic       # e.g. anthropic, openai, azure
#   api_key: sk-ant-...       # direct value; keep this file out of git
#   model_id: claude-sonnet-4-20250514
#   base_url: ""              # optional; for custom/self-hosted endpoints
```

**After:**
```yaml
# Model configuration (optional).
# If omitted, the CLI uses LLM_* environment variables.
# Uncomment and fill in to override:
#
# model:
#   provider: anthropic            # Required: anthropic, openai, azure, etc.
#   api_key: sk-ant-...            # Required: your API key (keep this file out of git)
#   model_id: claude-sonnet-4-20250514  # Required: model identifier
#   base_url: ""                   # Optional: custom endpoint URL
```

- [ ] **Step 2: Commit template changes**

```bash
git add src/sanityops_cli/templates/inspect_config.yaml
git commit -m "feat(template): improve model configuration comments with Required/Optional labels"
```

---

### Task 3: Change init.py to string-based template processing

**Files:**
- Modify: `src/sanityops_cli/commands/init.py`

**Interfaces:**
- Consumes: Template file from `src/sanityops_cli/templates/inspect_config.yaml`
- Produces: `_load_template() -> str` returning raw template string

- [ ] **Step 1: Update `_load_template()` return type and implementation**

Replace the `_load_template()` function (lines 79-99) in `src/sanityops_cli/commands/init.py`:

**Before:**
```python
def _load_template() -> dict:
    """Load the inspect_config.yaml template.

    Returns:
        Template as dictionary with placeholder UUID.
    """
    import sys

    # PyInstaller bundles resources in sys._MEIPASS
    if hasattr(sys, "_MEIPASS"):
        template_path = Path(sys._MEIPASS) / "sanityops_cli" / "templates" / "inspect_config.yaml"
    else:
        # Standard importlib.resources for normal Python environments
        import importlib.resources

        template_path = importlib.resources.files("sanityops_cli.templates") / "inspect_config.yaml"
        with template_path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    with open(template_path, encoding="utf-8") as f:
        return yaml.safe_load(f)
```

**After:**
```python
def _load_template() -> str:
    """Load the inspect_config.yaml template as a string.

    Returns:
        Template content with placeholder UUID. Returns as string
        to preserve YAML comments.
    """
    import sys

    # PyInstaller bundles resources in sys._MEIPASS
    if hasattr(sys, "_MEIPASS"):
        template_path = Path(sys._MEIPASS) / "sanityops_cli" / "templates" / "inspect_config.yaml"
    else:
        # Standard importlib.resources for normal Python environments
        import importlib.resources

        template_path = importlib.resources.files("sanityops_cli.templates") / "inspect_config.yaml"
        return template_path.read_text(encoding="utf-8")

    return Path(template_path).read_text(encoding="utf-8")
```

- [ ] **Step 2: Update `init_config()` to use string replacement**

Replace the template processing section in `init_config()` (lines 58-73):

**Before:**
```python
    # Load template and generate UUID
    try:
        template = _load_template()
    except (FileNotFoundError, ModuleNotFoundError, OSError) as e:
        console.print(f"[red]✗ Internal error: template not found ({e})[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None

    template["project"]["id"] = str(uuid.uuid4())

    # Write config file
    try:
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(template, f)
    except OSError as e:
        console.print(f"[red]✗ Cannot write config file: {e}[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None
```

**After:**
```python
    # Load template and generate UUID
    try:
        template_content = _load_template()
    except (FileNotFoundError, ModuleNotFoundError, OSError) as e:
        console.print(f"[red]✗ Internal error: template not found ({e})[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None

    # Replace placeholder UUID with generated one
    template_content = template_content.replace(
        "00000000-0000-0000-0000-000000000000",
        str(uuid.uuid4())
    )

    # Write config file
    try:
        with open(config_file, "w", encoding="utf-8") as f:
            f.write(template_content)
    except OSError as e:
        console.print(f"[red]✗ Cannot write config file: {e}[/red]")
        raise typer.Exit(code=EXIT_FAILURE) from None
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `pytest tests/commands/test_init.py -v`

Expected: PASS - all tests including new comment preservation tests

```bash
pytest tests/commands/test_init.py -v
```

- [ ] **Step 4: Run full test suite**

```bash
pytest -v
```

- [ ] **Step 5: Commit implementation**

```bash
git add src/sanityops_cli/commands/init.py
git commit -m "fix(init): preserve YAML comments by using string-based template processing"
```

---

### Task 4: Final verification

**Files:**
- None (verification only)

- [ ] **Step 1: Run full test suite**

```bash
pytest -v
```

Expected: All tests pass

- [ ] **Step 2: Manual smoke test**

```bash
# Create temp dir and run init
cd $(mktemp -d)
python -m sanityops_cli.main init
cat .sanityops/inspect_config.yaml
```

Expected: Output shows full template with comments including:
- `# Model configuration (optional).`
- `# provider:` comment line
- `# Required:` and `# Optional:` labels
- Real UUID (not placeholder)

- [ ] **Step 3: Final commit (if any fixes needed)**

```bash
git status
# If clean, nothing to commit
# If changes, commit with appropriate message
```