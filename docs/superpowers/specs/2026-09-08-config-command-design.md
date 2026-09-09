# Config Subcommand Migration Design

**Date:** 2026-09-08
**Status:** Approved
**Source:** deeplogic-cli → sanityops-cli

## Overview

Migrate the `config` subcommand from deeplogic-cli to sanityops-cli. This provides CLI-based configuration management for the sanityops server backend URL and API key.

## Architecture

### Files

```
src/sanityops_cli/
├── commands/
│   └── config.py           # NEW: config subcommand (Typer app)
├── utils/
│   ├── config_loader.py    # EXISTING: InspectConfigLoader (unchanged)
│   └── config_resolver.py  # NEW: ConfigResolver class
├── constants/
│   ├── exit_codes.py       # EXISTING (unchanged)
│   └── config_defaults.py  # NEW: DEFAULT_SERVER_BASE_URL
└── main.py                 # MODIFIED: register config_app
```

### Component Responsibilities

| Component | Responsibility |
|-----------|----------------|
| `commands/config.py` | CLI interface: parse args, display results, call resolver |
| `utils/config_resolver.py` | Core logic: read/write YAML, precedence chain, nested key handling |
| `constants/config_defaults.py` | Default server URL constant |

`config_loader.py` (`InspectConfigLoader`) remains unchanged — it handles the project's `inspect_config.yaml` for artifact paths, which is a different concern.

## Config Keys

| Key | Env Var | Default | Sensitive |
|-----|---------|---------|-----------|
| `server.base_url` | `SANITYOPS_BASE_URL` | `https://www.sanityops.org/demo` | No |
| `server.api_key` | `SANITYOPS_API_KEY` | None | Yes |

## Config File Locations

| Scope | Path |
|-------|------|
| Project-level | `.sanityops/inspect_config.yaml` |
| Global | `~/.sanityops/config` |

## Precedence Chain

```
project-level > global > environment variable > default
```

When reading a config value:
1. Check `.sanityops/inspect_config.yaml` (project-level)
2. Check `~/.sanityops/config` (global)
3. Check environment variable (`SANITYOPS_BASE_URL` or `SANITYOPS_API_KEY`)
4. Return default value

## ConfigResolver Class

### Public API

```python
class ConfigResolver:
    def __init__(self, config_key: str, env_var: str | None, default: str | None):
        """Initialize resolver with key metadata."""

    def resolve(self) -> str | None:
        """Resolve value following precedence chain."""

    def resolve_all_sources(self) -> dict[str, str | None]:
        """Return dict with 'project', 'global', 'env', 'default' keys."""

    @staticmethod
    def set_global(key: str, value: str) -> None:
        """Write to ~/.sanityops/config."""

    @staticmethod
    def set_project(key: str, value: str) -> None:
        """Write to .sanityops/inspect_config.yaml."""

    @staticmethod
    def unset_global(key: str) -> bool:
        """Remove key from global config."""

    @staticmethod
    def unset_project(key: str) -> bool:
        """Remove key from project config."""

    @staticmethod
    def list_global() -> dict[str, Any]:
        """List all global config values."""

    @staticmethod
    def list_project() -> dict[str, Any]:
        """List all project config values."""
```

### File Operations

- **Read**: UTF-8 with GBK fallback for Windows compatibility
- **Write**: Atomic write via temp file + rename to prevent corruption
- **Nested keys**: Dot notation support (`server.base_url` → `{"server": {"base_url": ...}}`)

## CLI Interface

### Usage Examples

```bash
sanityops-cli config server.base_url                    # Read value
sanityops-cli config server.base_url https://...        # Set (global, default)
sanityops-cli config server.base_url https://... --local  # Set project-level
sanityops-cli config server.api_key                     # Read value (masked display)
sanityops-cli config server.api_key <key>               # Set API key
sanityops-cli config --list                             # List all values
sanityops-cli config --unset server.base_url            # Remove from global
sanityops-cli config --unset server.base_url --local    # Remove from project
```

### CLI Options

| Option | Description |
|--------|-------------|
| `key` (arg) | Config key, e.g. `server.base_url` |
| `value` (arg) | Config value (omit to read) |
| `--list`, `-l` | List all config values |
| `--unset <key>` | Remove a config key |
| `--global` | Operate on global config (default, implicit) |
| `--local` | Operate on project-level config |

### Sensitive Value Handling

- `server.api_key` is marked as sensitive in `CONFIG_SCHEMA`
- Display: masked as `abc***wxyz` (first 3 + `***` + last 4)
- Values shorter than 8 characters are fully masked as `***`
- Reading a sensitive key displays the masked value (same as `--list`)
- Setting a sensitive key requires passing the value as an argument

### List Output

```
┏━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┓
┃ Key                 ┃ Global               ┃ Project              ┃
┡━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━┩
│ server.base_url     │ https://...          │                      │
│ server.api_key      │ abc***wxyz           │                      │
└─────────────────────┴──────────────────────┴──────────────────────┘

Environment variables set:
  SANITYOPS_API_KEY=abc***wxyz
```

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Config file not found | Return empty dict (treat as no config) |
| Unreadable file (encoding) | Return empty dict |
| Invalid YAML | Return empty dict |
| Write failure | Display error message, exit with `EXIT_FAILURE` |
| Unset non-existent key | Display "key was not set", exit success |

## Edge Cases

| Case | Behavior |
|------|----------|
| No config files exist | `--list` shows hint message with setup commands |
| Both global and project set | Display both, project takes precedence on read |
| Empty string value | Stored and displayed as empty (valid) |
| Key not in schema | Works, but no sensitive masking or env var lookup |

## Testing Strategy

### Tests to Add

**`tests/commands/test_config.py`** — CLI behavior:
- Read config value (set → read success)
- Read unset key (shows "not set")
- Set global config (creates `~/.sanityops/config`)
- Set project config (creates `.sanityops/inspect_config.yaml`)
- Unset global/project key
- `--list` output (empty and populated)
- Sensitive key masking (api_key not shown in full)
- Invalid key handling

**`tests/utils/test_config_resolver.py`** — Resolver logic:
- Precedence: project > global > env > default
- Nested key get/set/unset (dot notation)
- Atomic write (temp file cleanup)
- Encoding fallback (GBK)

### Test Utilities Needed

- **Monkeypatch config paths** — tests must not touch real `~/.sanityops/` or cwd. Use fixture to redirect paths via tmp paths and monkeypatch.