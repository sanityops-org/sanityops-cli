# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Open source essentials: CONTRIBUTING.md, CODE_OF_CONDUCT.md, SECURITY.md
- Issue and PR templates
- CI workflow with ruff and pytest
- Dependabot configuration for weekly dependency updates
- Ruff configuration for code quality (E, W, F, I, B, UP rules)

### Changed

- Upgraded sanityops-agent dependency to >=0.0.3 (fixes package structure)
- Modernized type annotations to Python 3.11+ style (list/dict instead of List/Dict, X | None instead of Optional[X])
- Moved pyinstaller from runtime dependencies to dev-only (release workflow installs it explicitly)
- Committed uv.lock for reproducible builds

### Fixed

- License identifier in pyproject.toml (MIT → Apache-2.0)
- Typo in README.md ("Form Curl" → "From Curl")
- Type annotation `dict[str, any]` → `dict[str, Any]` in config_loader.py

## [0.1.4] - 2025-08-13

### Added

- CI release workflow for automated binary builds
- PyInstaller configuration for macOS ARM64

### Changed

- Bump version to 0.1.4

## [0.1.3] - 2025-08-12

### Added

- CI release workflow improvements

### Changed

- Bump version to 0.1.3

## [0.1.2] - 2025-08-12

### Fixed

- Install script paths in release workflow

### Changed

- Bump version to 0.1.2

## [0.1.1] - 2025-08-11

### Added

- Initial release with inspect and init commands
- Support for System Prompts, Skills, and Tool Schemas inspection
- Three-level check depth (L1, L2, L3)
- Configuration via YAML files
