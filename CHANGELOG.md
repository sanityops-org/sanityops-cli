# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Skill-based two-agent inspect pipeline: an ExtractAgent (vendored
  `pre-inspect-extract` skill) segments configured documents into inspectable
  artifacts with per-artifact completeness, tier (L), and verbatim evidence,
  then an InspectAgent (vendored `sanityops-inspect-lite` skill) runs the
  seven-stage SanityOps Framework inspection flow and emits the markdown
  report plus a machine-readable summary block
- Vendored inspect skills under `src/sanityops_cli/skills/` with recorded
  upstream provenance (`VERSION.json`), materialized at runtime and loaded
  lazily through the agent skill tool
- `scripts/sync_skills.py` and `scripts/ci_sync_skills.py` plus a scheduled
  GitHub Actions workflow that updates the vendored skills and opens a pull
  request when upstream changes
- New `inspect` options: `--skip-extract` (inject configured files verbatim,
  no upload) and `--strict`/`--fail-on-defect` (exit 1 on QC gate failure,
  Inspect P0 defects, or missing report stages)
- New config keys: `report_language`, `attribution`, `context_window`, and
  `qc_lint.declared_dependencies`
- Per-document IR audit files written to
  `.sanityops/results/ir/<run-id>/` for every inspection run
- QC lint rules QC-0.4 (Fence Integrity), QC-0.5 (Language-Content Mismatch),
  QC-1.2 (Invalid Import), QC-1.3 (Deprecated API Usage), QC-4.1
  (Snippet-Artifact Declaration Mismatch), and QC-4.2 (Snippet-Body
  Version/API Drift), bringing the program checker to the 17-item checklist
  v2; hybrid items pre-screen deterministically and emit candidates for the
  inspection agent to confirm instead of failing outright

### Changed

- **Breaking**: `inspect` no longer accepts `--skip-defect-check`; the
  pipeline now always runs extraction followed by inspection
- `inspect` exit codes: `2` for configuration/manifest errors, extraction
  failure, or an unparseable summary; `1` only under `--strict`
- Auto-upload now packs the extracted artifacts (not the previous scan
  result); `--skip-extract` never uploads
- Project auto-creation during upload preserves the configured `project.name`
  and writes the binding back to the exact config file passed via `--config`

### Removed

- **Breaking**: the `defect-check` SDK dependency and the local
  `defect_checker/` module; inspection rules now come from the vendored
  `sanityops-inspect-lite` skill
- The ScannerAgent (`agents/scanner_agent/`); extraction is performed by the
  skill-driven ExtractAgent

### Fixed

- Tool schema uploads emit the provider-neutral flat format
  `{name, description, parameters}` for all extracted tools
- Failed module inspections render a CAUTION callout instead of a misleading
  "No defects found" in the seven-stage report
## [0.0.8] - 2026-09-21

### Added

- `inspect repair` subcommand to generate repaired artifacts from inspection reports
- Cross-artifact result rendering with aggregate CROSS score in markdown reports
- Getting Started and Advanced Usage help panels migrated from sanityops-cli

## [0.0.7] - 2026-09-10

### Added

- Init command alignment with sanityops-cli: placeholder UUID, project.name, model block
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