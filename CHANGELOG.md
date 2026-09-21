# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.0.8] - 2026-09-21

### Added

- `inspect repair` subcommand to generate repaired artifacts from inspection reports
- Cross-artifact result rendering with aggregate CROSS score in markdown reports
- Getting Started and Advanced Usage help panels migrated from deeplogic-cli

## [0.0.7] - 2026-09-10

### Added

- Init command alignment with deeplogic-cli: placeholder UUID, project.name, model block
- Nested `.gitignore` in `.sanityops` directory to prevent accidental secret commits

### Changed

- Made empty model field errors actionable with clear guidance

## [0.0.6] - 2026-09-09

### Added

- Artifact scan-and-upload feature: auto-create projects and push artifacts on first inspect
- Markdown report saving for defect check results

## [0.0.5] - 2026-09-09

### Added

- `config` subcommand for managing server URL and API key
- Secure temp file creation with `mkstemp`
- Explicit `--global`/`--local` mutual exclusion for config operations

### Fixed

- Config file deletion when last key is removed
- Permissions enforcement after atomic config file replace

## [0.0.4] - 2026-08-31

### Added

- Apache 2.0 copyright headers on all source files
- Copyright and license information in `--version` output

## [0.0.3] - 2026-08-14

### Changed

- Skills now accept files only (like prompts and tools)
- Run banner showing version, Python version, and platform before inspection
- README synchronized with inspect_config.yaml template

### Fixed

- Bumped `sanityops-agent` dependency to >=0.0.4

## [0.0.2] - 2026-08-14

### Added

- YAML comment preservation in init template
- Loading animations and file logging for async inspect operations
- Step progress tracking with timing information

### Fixed

- Rich markup escaping for dynamic agent output in progress lines

## [0.0.1] - 2026-08-13

### Added

- Initial project setup for sanityops-cli
- `init` command to create `.sanityops/inspect_config.yaml` template
- `inspect` command for static defect inspection of logical artifacts
- Support for System Prompts, Skills, and Tool Schemas inspection
- Three-level check depth (L1, L2, L3)

[Unreleased]: https://github.com/sanityops-org/sanityops-cli/compare/v0.0.8...HEAD
[0.0.8]: https://github.com/sanityops-org/sanityops-cli/compare/v0.0.7...v0.0.8
[0.0.7]: https://github.com/sanityops-org/sanityops-cli/compare/v0.0.6...v0.0.7
[0.0.6]: https://github.com/sanityops-org/sanityops-cli/compare/v0.0.5...v0.0.6
[0.0.5]: https://github.com/sanityops-org/sanityops-cli/compare/v0.0.4...v0.0.5
[0.0.4]: https://github.com/sanityops-org/sanityops-cli/compare/v0.0.3...v0.0.4
[0.0.3]: https://github.com/sanityops-org/sanityops-cli/compare/v0.0.2...v0.0.3
[0.0.2]: https://github.com/sanityops-org/sanityops-cli/compare/v0.0.1...v0.0.2
[0.0.1]: https://github.com/sanityops-org/sanityops-cli/releases/tag/v0.0.1