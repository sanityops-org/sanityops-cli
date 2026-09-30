# Sanityops CLI

A command-line tool for static defect inspection of AI logical artifacts (System Prompts, Skills, Tool Schemas). Designed for local development and CI/CD integration.

**[Documentation](https://sanityops.org)** | **[Report Bug](https://github.com/sanityops-org/sanityops-cli/issues)** | **[Request Feature](https://github.com/sanityops-org/sanityops-cli/issues)**

## Features

- **Multi-level inspection depth** — Choose between L1 (fast), L2 (standard), or L3 (deep) check levels
- **Multiple artifact types** — Inspect System Prompts, Skills, and Tool Schemas
- **CI/CD friendly** — Non-interactive runs, configuration via environment variables, dated markdown reports for pipeline artifacts
- **Configurable rules** — Customize inspection behavior via YAML configuration

## Prerequisites

- **Python >= 3.11** — only needed when installing from PyPI or source; the curl/PowerShell installers ship a standalone binary with no Python requirement.
- **An LLM API key** — artifact analysis and defect checking are LLM-powered. Use Anthropic, OpenAI, or any compatible provider, configured either in the `model:` section of the config file or via `LLM_*` environment variables (see [Environment Variables](#environment-variables)).
- **Optional: a Sanityops server API key** — only if you want scanned artifacts uploaded to the Sanityops web dashboard. See [Data Handling](#data-handling) before enabling this.

## Installation

### From Curl (Recommended)

**macOS and Linux:**

```bash
curl -fsSL https://downloads.sanityops.org/sanityops-cli/install.sh | bash
```

**Windows PowerShell:**

```powershell
irm https://downloads.sanityops.org/sanityops-cli/install.ps1 | iex
```

For a reviewable PowerShell installation, download the script first:

```powershell
irm https://downloads.sanityops.org/sanityops-cli/install.ps1 -OutFile install.ps1
Get-Content .\install.ps1
.\install.ps1
```

Both installers verify the downloaded binary against `checksums.txt` before installing. They default to user-writable locations (`~/.local/bin` on macOS/Linux and `%USERPROFILE%\.sanityops\bin` on Windows), then add the Windows directory to the user PATH if needed.

### From PyPI

```bash
pip install sanityops-cli
```

### From Source

```bash
git clone https://github.com/sanityops-org/sanityops-cli.git
cd sanityops-cli
pip install -e .
```

## Quick Start

### 1. Initialize Configuration

```bash
sanityops-cli init
```

This creates `.sanityops/inspect_config.yaml` in your current directory from the built-in template. The `project.id` starts as a placeholder UUID (`00000000-0000-0000-0000-000000000000`); on the first `inspect` run with a server API key configured, the project is created on the Sanityops server and the real id/name are written back to this file. `init` also writes a `.gitignore` inside `.sanityops/` so the config file (which may hold API keys) and scan results never get committed.

Edit the artifact paths to point at your prompts, tools, and skills.

### 2. Configure Artifacts

Edit `.sanityops/inspect_config.yaml` to specify your artifacts:

```yaml
project:
  # id starts as a placeholder; on the first inspect run with a server API key,
  # the project is created automatically and the real id/name are written back.
  id: 00000000-0000-0000-0000-000000000000
  name: ""

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

### 3. Run Inspection

```bash
# Standard inspection (L2 depth)
sanityops-cli inspect

# Fast inspection (L1 depth)
sanityops-cli inspect --check-level L1

# Deep inspection (L3 depth)
sanityops-cli inspect --check-level L3

# Skip defect check, only analyze artifacts
sanityops-cli inspect --skip-defect-check

# Use custom config file
sanityops-cli inspect --config path/to/config.yaml
```

> **Data upload notice:** if a Sanityops server API key is configured (`server.api_key` or `SANITYOPS_API_KEY`), `inspect` automatically uploads the scanned artifacts to the Sanityops server after analysis. Without an API key, everything stays on your machine. See [Data Handling](#data-handling).

`inspect` exits `0` when the run completes — including when defects are found — and non-zero on failure. CI pipelines should therefore gate on the generated report (`.sanityops/results/inspect-*.md`), not on the exit code.

### 4. Generate Repairs (Optional)

After inspection, generate repaired artifacts from the report:

```bash
# Use the latest inspection report
sanityops-cli inspect repair

# Use a specific report
sanityops-cli inspect repair --report .sanityops/results/inspect-20250115-120000.md

# Specify timeout and token budget for large projects
sanityops-cli inspect repair --timeout 3600 --token-budget 500000
```

Repairs are written to `.sanityops/repairs/repair-<timestamp>.md` without modifying source files.

## Data Handling

What leaves your machine, and when:

- **Local by default.** Artifact analysis and defect checking run on your machine and send artifact content only to the LLM provider you configure (`model:` section or `LLM_*` environment variables). Without a Sanityops server API key, nothing is uploaded to the Sanityops server.
- **Auto-upload is keyed to the server API key.** If `server.api_key` (or `SANITYOPS_API_KEY`) is set, `inspect` uploads the scanned artifacts — System Prompts, Tool Schemas, Skills — to the Sanityops server after analysis, so they appear in the web dashboard. The first such run also creates the project on the server and binds `project.id`.
- **Server destination.** `server.base_url` defaults to the Sanityops SaaS service (`https://demo.sanityops.org`). Only change it if you run a private deployment:

  ```bash
  sanityops-cli config server.base_url https://api.your-deployment.com
  ```

- **Secrets are protected locally.** API keys are masked in CLI output and redacted from logs, and the `.sanityops/` directory is excluded from git by the `.gitignore` that `init` writes.

## Configuration

### Config Command

Manage server-side configuration (base URL, API key) using the `config` command:

```bash
# Read a config value
sanityops-cli config server.base_url

# Set a global config value
sanityops-cli config server.base_url https://api.sanityops.org

# Set a project-level config value
sanityops-cli config server.base_url https://api.sanityops.org --local

# Set API key (prompts for masked input if no value provided)
sanityops-cli config server.api_key

# List all config values
sanityops-cli config --list

# Remove a config key
sanityops-cli config --unset server.base_url
```

`server.base_url` defaults to the Sanityops SaaS service (`https://demo.sanityops.org`). Change it only if you use a private deployment.

### Configuration Precedence

Values are resolved in this priority order (highest to lowest):

1. **Environment Variable** — e.g., `SANITYOPS_BASE_URL`
2. **Project-level** — `.sanityops/inspect_config.yaml`
3. **Global** — `~/.sanityops/config`
4. **Default** — built-in fallback

This ordering ensures CI/CD pipelines can override any project config by injecting environment variables.

### Environment Variables

| Variable | Description |
|----------|-------------|
| `SANITYOPS_BASE_URL` | Override `server.base_url` (default: `https://demo.sanityops.org`) |
| `SANITYOPS_API_KEY` | Override `server.api_key`; when set, `inspect` auto-uploads artifacts to the server |
| `LLM_PROVIDER` | LLM provider (e.g., `anthropic`, `openai`) |
| `LLM_API_KEY` | LLM API key for defect checking |
| `LLM_MODEL_ID` | LLM model ID (e.g., `claude-sonnet-4-20250514`) |
| `LLM_BASE_URL` | Custom LLM base URL |

## Advanced Configuration

### Agent Settings

You can tune the scanner agent behavior in `.sanityops/inspect_config.yaml`:

```yaml
agent:
  max_loops: 60          # Maximum agent execution loops
  token_budget: 200000   # Token budget for agent execution
  timeout: 1800          # Timeout in seconds (default: 1800 = 30min)
```

CLI flags (`--timeout`, `--token-budget`) override these values when explicitly set.

### Logging

All CLI operations are logged to `~/.sanityops/logs/sanityops-cli-<YYYY-MM-DD>.log`. Logs include timestamps, log levels, and redacted API keys for security.

### Check Levels

| Level | Description | Use Case |
|-------|-------------|----------|
| L1 | Fast | Quick validation during development |
| L2 | Standard | Default, balanced depth for regular use |
| L3 | Deep | Comprehensive analysis for production releases |

## Documentation

Full documentation is available at [sanityops.org](https://sanityops.org).

## Development

### Setup

```bash
# Clone the repository
git clone https://github.com/sanityops-org/sanityops-cli.git
cd sanityops-cli

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev,test]"
```

### Run Tests

```bash
pytest
```

### Code Style

This project uses [Ruff](https://docs.astral.sh/ruff/) for linting. Run:

```bash
ruff check .
```

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details on:

- Development setup
- Code style guidelines
- Pull request process
- Commit message conventions

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

Built with [Typer](https://typer.tiangolo.com/) and [Rich](https://github.com/Textualize/rich).
