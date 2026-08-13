# Model Config Comments in Init Template - Design

## Problem

When users run `sanityops-cli init`, the generated `.sanityops/inspect_config.yaml` file contains no comments. This happens because `init.py` uses `yaml.safe_load()` + `yaml.dump()` to process the template, which strips all YAML comments.

Users receive a bare configuration file without guidance on:
- The `model` section being optional
- What each field means
- When to configure model vs. using environment variables

## Solution

Change the template processing from YAML parse/serialize to string-based replacement:

1. Read template file as raw string (preserving comments)
2. Replace UUID placeholder with generated UUID
3. Write the string directly to output file

## Changes

### 1. Update Template Comments

File: `src/sanityops_cli/templates/inspect_config.yaml`

Improve the model section comments for clarity:

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

Changes from current:
- Split into three clear lines: optional status, fallback behavior, how to enable
- Mark each field as Required/Optional
- Inline provider examples in the Required comment

### 2. Update init.py

File: `src/sanityops_cli/commands/init.py`

Change `_load_template()` to return string instead of dict:

```python
def _load_template() -> str:
    """Load the inspect_config.yaml template as a string.

    Returns:
        Template content with placeholder UUID.
    """
    import sys

    # PyInstaller bundles resources in sys._MEIPASS
    if hasattr(sys, "_MEIPASS"):
        template_path = Path(sys._MEIPASS) / "sanityops_cli" / "templates" / "inspect_config.yaml"
    else:
        import importlib.resources
        template_path = importlib.resources.files("sanityops_cli.templates") / "inspect_config.yaml"
        return template_path.read_text(encoding="utf-8")

    return Path(template_path).read_text(encoding="utf-8")
```

Update `init_config()` to use string replacement:

```python
# Before:
template = _load_template()
template["project"]["id"] = str(uuid.uuid4())
yaml.dump(template, f)

# After:
template_content = _load_template()
template_content = template_content.replace(
    "00000000-0000-0000-0000-000000000000",
    str(uuid.uuid4())
)
with open(config_file, "w", encoding="utf-8") as f:
    f.write(template_content)
```

### 3. Update Tests

File: `tests/commands/test_init.py`

Verify the generated config contains comments:
- Check that "# Model configuration" appears in output
- Check that "# provider:" comment line appears
- Ensure UUID replacement works correctly

## Implementation Scope

- Minimal change: only affects `init.py` and template file
- No new dependencies
- Backward compatible: existing config files unchanged
- Tests updated to verify comment preservation

## Files Changed

| File | Change |
|------|--------|
| `src/sanityops_cli/templates/inspect_config.yaml` | Improve model section comments |
| `src/sanityops_cli/commands/init.py` | String-based template processing |
| `tests/commands/test_init.py` | Add tests for comment preservation |
