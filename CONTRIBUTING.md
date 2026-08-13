# Contributing to Sanityops CLI

Thank you for your interest in contributing to Sanityops CLI! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Development Setup](#development-setup)
- [Development Workflow](#development-workflow)
- [Code Style](#code-style)
- [Pull Request Process](#pull-request-process)
- [Commit Message Convention](#commit-message-convention)

## Code of Conduct

This project and everyone participating in it is governed by our [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## Development Setup

### Prerequisites

- Python 3.11 or higher
- Git
- A GitHub account

### Setup Steps

1. **Fork and clone the repository**

   ```bash
   git clone https://github.com/<your-username>/sanityops-cli.git
   cd sanityops-cli
   ```

2. **Create a virtual environment**

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install development dependencies**

   ```bash
   pip install -e ".[dev,test]"
   ```

4. **Verify the setup**

   ```bash
   pytest
   ruff check .
   ```

## Development Workflow

We follow **GitHub Flow**:

1. Create a feature branch from `main`
2. Make your changes
3. Submit a pull request
4. After review and approval, merge to `main`

### Creating a Feature Branch

```bash
git checkout main
git pull origin main
git checkout -b feature/your-feature-name
```

## Code Style

We use [Ruff](https://docs.astral.sh/ruff/) for code quality enforcement.

### Run Linting

```bash
ruff check .
```

### Run Formatting

```bash
ruff format .
```

### Fix Auto-fixable Issues

```bash
ruff check --fix .
```

### Style Guidelines

- Line length: 100 characters
- Use [isort](https://pycqa.github.io/isort/) for import sorting
- Follow PEP 8 conventions
- Write docstrings for public functions and classes

## Pull Request Process

1. **Ensure tests pass**

   ```bash
   pytest
   ruff check .
   ```

2. **Add tests for new features**

   - Place tests in the `tests/` directory
   - Follow the existing test structure
   - Use pytest fixtures where appropriate

3. **Update documentation**

   - Update README.md if you change user-facing behavior
   - Update docstrings for modified functions/classes

4. **Submit your PR**

   - Fill out the PR template completely
   - Link any related issues
   - Request review from maintainers

5. **Address review feedback**

   - Make requested changes
   - Push new commits (avoid force-pushing during review)

## Commit Message Convention

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

### Types

| Type | Description |
|------|-------------|
| `feat` | A new feature |
| `fix` | A bug fix |
| `docs` | Documentation changes |
| `style` | Code style changes (formatting, etc.) |
| `refactor` | Code refactoring |
| `test` | Adding or updating tests |
| `chore` | Maintenance tasks |

### Examples

```
feat(inspect): add support for custom check levels
fix(config): resolve path resolution on Windows
docs: update installation instructions
test(commands): add tests for init command
```

## Questions?

- Open a [GitHub Discussion](https://github.com/sanityops/sanityops-cli/discussions) for general questions
- Open an [Issue](https://github.com/sanityops/sanityops-cli/issues) for bug reports or feature requests

Thank you for contributing!
