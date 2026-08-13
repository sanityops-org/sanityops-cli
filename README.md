# Sanityops CLI

A command-line tool for static defect inspection of AI logical artifacts (System Prompts, Skills, Tool Schemas). Designed for local development and CI/CD integration.

**[Documentation](https://sanityops.org)** | **[Report Bug](https://github.com/sanityops-org/sanityops-cli/issues)** | **[Request Feature](https://github.com/sanityops-org/sanityops-cli/issues)**

## Features

- **Multi-level inspection depth** — Choose between L1 (fast), L2 (standard), or L3 (deep) check levels
- **Multiple artifact types** — Inspect System Prompts, Skills, and Tool Schemas
- **CI/CD ready** — Designed for automated pipeline integration
- **Configurable rules** — Customize inspection behavior via YAML configuration

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

This creates `.sanityops/inspect_config.yaml` in your current directory.

### 2. Configure Artifacts

Edit `.sanityops/inspect_config.yaml` to specify your artifacts:

```yaml
project:
  id: <your-project-id>

prompts:
  - path/to/system_prompt.md

tools:
  - path/to/tool_schema.json

skills:
  - path/to/skill.yaml
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

### Check Levels

| Level | Description | Use Case |
|-------|-------------|----------|
| L1 | Fast | Quick validation during development |
| L2 | Standard | Default, balanced depth for regular use |
| L3 | Deep | Comprehensive analysis for production releases |

## Documentation

Full documentation is available at [sanityops.org](https://sanityops.org).

## Requirements

- Python >= 3.11
- OpenAI API key (or compatible LLM provider) for defect checking

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
