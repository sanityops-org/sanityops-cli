# CLI Copyright & License Compliance Design

## Problem Statement

Currently, the project does not fully comply with Apache 2.0 license best practices. While a `LICENSE` file exists at the repository root, the following are missing:

1. **No copyright headers in source files** — Apache 2.0 requires retaining copyright notices in distributed source code.
2. **No `NOTICE` file** — Required when distributing derivative works or when additional attribution is needed.
3. **`--version` output lacks copyright and license info** — The document's best practice recommends including copyright and license info in the CLI `--version` output.

## Goals

1. Add Apache 2.0 copyright headers to all `.py` source files.
2. Create a `NOTICE` file at the repository root.
3. Update `--version` output to include copyright and license info.
4. Ensure all changes are consistent with the guidance in `CLI-copyright.md`.

## Non-Goals

- Adding copyright info to every execution output (intentionally avoided per document's "Not Recommended" section, to avoid breaking CI/CD pipelines).
- Adding `--quiet` flag for copyright suppression (out of scope; can be added later if needed).
- Modifying the `LICENSE` file itself (already present and correct).

## Design

### 1. Copyright Headers in Source Files

All 33 `.py` files under `src/` will receive a standard Apache 2.0 header at the top.

The header format (matching the document's recommended template):

```python
# Copyright 2026 zipsonken
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
```

**Special cases:**
- Files that start with a docstring (like `main.py`) will have the header inserted before the docstring.
- `__init__.py` files that only contain `__version__` or re-exports will also get the header.

### 2. NOTICE File

Create `NOTICE` at the repository root with the following content:

```
SanityOps Inspect CLI
Copyright 2026 zipsonken / Sanity AI Labs

This product includes software developed under the SanityOps Framework.
SanityOps Framework is licensed under Apache License 2.0.
```

### 3. `--version` Output Update

Update `src/sanityops_cli/main.py` so that the `--version` callback outputs:

```
sanityops-cli v0.0.3
Copyright (C) 2026 zipsonken / Sanity AI Labs
License: Apache 2.0 (https://www.apache.org/licenses/LICENSE-2.0)
```

The change is in the `version_callback` function in `main.py`.

## Files to Modify

| File | Action |
|------|--------|
| `src/sanityops_cli/__init__.py` | Add copyright header |
| `src/sanityops_cli/main.py` | Add copyright header + update `version_callback` |
| `src/sanityops_cli/commands/inspect.py` | Add copyright header |
| `src/sanityops_cli/commands/init.py` | Add copyright header |
| `src/sanityops_cli/agents/__init__.py` | Add copyright header |
| `src/sanityops_cli/renderers/__init__.py` | Add copyright header |
| `src/sanityops_cli/progress/__init__.py` | Add copyright header |
| `src/sanityops_cli/progress/tracker.py` | Add copyright header |
| `src/sanityops_cli/constants/__init__.py` | Add copyright header |
| `src/sanityops_cli/constants/exit_codes.py` | Add copyright header |
| `src/sanityops_cli/utils/__init__.py` | Add copyright header |
| `src/sanityops_cli/utils/config_loader.py` | Add copyright header |
| `src/sanityops_cli/utils/validators.py` | Add copyright header |
| `src/sanityops_cli/exceptions/__init__.py` | Add copyright header |
| `src/sanityops_cli/exceptions/base_exceptions.py` | Add copyright header |
| `src/sanityops_cli/exceptions/api_exceptions.py` | Add copyright header |
| `src/sanityops_cli/templates/__init__.py` | Add copyright header |
| `src/sanityops_cli/defect_checker/renderer.py` | Add copyright header |
| `src/sanityops_cli/defect_checker/__init__.py` | Add copyright header |
| `NOTICE` | Create new file |

| `entry.py` | Add copyright header |

(Additional `.py` files discovered during implementation will also be updated.)

## Verification

After implementation, verify:

1. All `.py` files under `src/` start with the copyright header.
2. `NOTICE` file exists at the repo root with correct content.
3. Running `sanityops-cli --version` outputs the three-line version/copyright/license message.
4. No other CLI command outputs copyright text (only `--version`).

## References

- `CLI-copyright.md` — Source document specifying compliance requirements and best practices.
- Apache License 2.0 — https://www.apache.org/licenses/LICENSE-2.0
