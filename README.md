# Sanityops CLI

A command-line tool for static defect inspection of AI logical artifacts (System Prompts, Skills, Tool Schemas). Designed for local development and CI/CD integration.

**[Documentation](https://sanityops.org)** | **[Report Bug](https://github.com/sanityops-org/sanityops-cli/issues)** | **[Request Feature](https://github.com/sanityops-org/sanityops-cli/issues)**

## Features

- **Skill-based two-stage inspection** — an extraction stage segments the documents into inspectable artifacts, then a seven-stage inspection flow checks them against the SanityOps Framework checklists
- **Multiple artifact types** — Inspect System Prompts, Skills, and Tool Schemas
- **Code Contract (QC) lint** — a zero-token program check runs before any LLM spend
- **CI/CD friendly** — Non-interactive runs, configuration via environment variables, dated markdown reports for pipeline artifacts, `--strict` exit gates
- **Configurable rules** — Customize inspection behavior via YAML configuration

## Prerequisites

- **Python >= 3.11** — only needed when installing from PyPI or source; the curl/PowerShell installers ship a standalone binary with no Python requirement.
- **An LLM API key** — artifact extraction and inspection are LLM-powered. Use Anthropic, OpenAI, or any compatible provider, configured either in the `model:` section of the config file or via `LLM_*` environment variables (see [Environment Variables](#environment-variables)).
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
  - file: skills/code_review.md   # a file or a directory of SKILL.md files
```

### 3. Run Inspection

```bash
# Standard run: extraction + seven-stage inspection
sanityops-cli inspect

# Skip the extraction stage (inject configured files verbatim, no upload)
sanityops-cli inspect --skip-extract

# Use custom config file
sanityops-cli inspect --config path/to/config.yaml

# CI gate: exit 1 on QC gate failure, P0 defects, or missing stages
sanityops-cli inspect --strict
```

> **Data upload notice:** if a Sanityops server API key is configured (`server.api_key` or `SANITYOPS_API_KEY`), `inspect` automatically uploads the extracted artifacts to the Sanityops server after extraction (`--skip-extract` never uploads). Without an API key, everything stays on your machine. See [Data Handling](#data-handling).

`inspect` exit codes:

- `0` — run completed (defects, if any, are in the report)
- `1` — `--strict` and the QC gate failed, Inspect P0 defects were found, or report stages are missing
- `2` — configuration/manifest errors, extraction failure, or an unparseable inspection summary

Without `--strict`, the run exits `0` even when defects are found; CI pipelines should either pass `--strict` or gate on the generated report (`.sanityops/results/inspect-*.md`).

## Data Handling

What leaves your machine, and when:

- **Local by default.** Artifact extraction and inspection run on your machine and send artifact content only to the LLM provider you configure (`model:` section or `LLM_*` environment variables). Without a Sanityops server API key, nothing is uploaded to the Sanityops server.
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
| `LLM_API_KEY` | LLM API key for extraction and inspection |
| `LLM_MODEL_ID` | LLM model ID (e.g., `claude-sonnet-4-20250514`) |
| `LLM_BASE_URL` | Custom LLM base URL |

## Advanced Configuration

### Agent Settings

You can tune the inspect agents in `.sanityops/inspect_config.yaml`:

```yaml
agent:
  max_loops: 60          # Maximum agent execution loops per stage
  token_budget: 200000   # Token budget per agent (inspect stage floors at 300000)
  timeout: 1800          # Timeout in seconds per stage (default: 1800 = 30min)

# Pipeline settings
report_language: en        # Report language for extraction IR and inspection report
attribution: auto          # auto | single | collection — cross-artifact gating
context_window: 200000     # LLM context window used to derive the injection budget
qc_lint:
  declared_dependencies: []  # External modules declared for QC-1.2 import checks
```

CLI flags (`--timeout`, `--token-budget`) override these values when explicitly set.

### Inspect Skills

The inspection rules are maintained in the [`sanityops-inspect-lite`](https://github.com/sanityops-org/sanityops-inspect-lite) repository and vendored into this package (`src/sanityops_cli/skills/`). The vendored copy records its upstream commit in `src/sanityops_cli/skills/VERSION.json`; a scheduled GitHub Actions workflow updates it and opens a pull request when upstream changes.

### Logging

All CLI operations are logged to `~/.sanityops/logs/sanityops-cli-<YYYY-MM-DD>.log`. Logs include timestamps, log levels, and redacted API keys for security.

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
