# Cross-Artifact Result Rendering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate cross-artifact result rendering from deeplogic-cli to sanityops-cli, enabling terminal and markdown display of CROSS module defects.

**Architecture:** Add helper functions to resolve artifact names from defect references and aggregate multiple CROSS sub-results into a unified section. The terminal renderer uses Rich panels with artifact names in titles; the markdown reporter merges PS/PT/ST sub-results and calculates a unified score via SDK.

**Tech Stack:** Python 3.11+, Rich (terminal UI), defect-check SDK (CrossScoringCalculator), pytest (testing)

## Global Constraints

- Python >= 3.11
- Use existing `_MODULE_LABELS` pattern in both renderer.py and markdown_reporter.py
- Graceful fallback on SDK exceptions (return None, don't crash)
- All new functions must have unit tests before implementation
- Follow existing code style (Apache 2.0 license header, type hints, docstrings)

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `src/sanityops_cli/defect_checker/renderer.py` | Modify | Add cross-artifact rendering support |
| `src/sanityops_cli/defect_checker/markdown_reporter.py` | Modify | Add cross-artifact aggregation and scoring |
| `tests/unit/defect_checker/test_renderer.py` | Modify | Add tests for new renderer functions |
| `tests/unit/defect_checker/test_markdown_reporter.py` | Modify | Add tests for new reporter functions |

---

## Task 1: Update renderer.py constants and add `_resolve_artifact_names()`

**Files:**
- Modify: `src/sanityops_cli/defect_checker/renderer.py`
- Modify: `tests/unit/defect_checker/test_renderer.py`

**Interfaces:**
- Consumes: SDK response dict with `results[].artifacts[]` and `results[].defects[].artifact_refs`
- Produces: `_resolve_artifact_names(result: dict[str, Any]) -> str | None`

- [ ] **Step 1: Write failing tests for `_resolve_artifact_names()`**

```python
# Add to tests/unit/defect_checker/test_renderer.py

class TestResolveArtifactNames:
    def test_single_artifact_with_ref(self):
        """Returns artifact name when artifact_refs matches one artifact."""
        from sanityops_cli.defect_checker.renderer import _resolve_artifact_names
        result = {
            "artifacts": [{"id": "skill-1", "name": "morning-report"}],
            "defects": [{"artifact_refs": ["skill-1"]}],
        }
        assert _resolve_artifact_names(result) == "morning-report"

    def test_multiple_artifacts_with_refs(self):
        """Returns comma-separated names when multiple artifact_refs."""
        from sanityops_cli.defect_checker.renderer import _resolve_artifact_names
        result = {
            "artifacts": [
                {"id": "skill-1", "name": "morning-report"},
                {"id": "skill-2", "name": "daily-summary"},
            ],
            "defects": [
                {"artifact_refs": ["skill-1", "skill-2"]},
            ],
        }
        assert _resolve_artifact_names(result) == "morning-report, daily-summary"

    def test_fallback_single_artifact_no_refs(self):
        """Returns single artifact name when no artifact_refs but only one artifact."""
        from sanityops_cli.defect_checker.renderer import _resolve_artifact_names
        result = {
            "artifacts": [{"id": "skill-1", "name": "morning-report"}],
            "defects": [{"artifact_refs": []}],
        }
        assert _resolve_artifact_names(result) == "morning-report"

    def test_returns_none_no_refs_multiple_artifacts(self):
        """Returns None when no artifact_refs and multiple artifacts."""
        from sanityops_cli.defect_checker.renderer import _resolve_artifact_names
        result = {
            "artifacts": [
                {"id": "skill-1", "name": "morning-report"},
                {"id": "skill-2", "name": "daily-summary"},
            ],
            "defects": [{"artifact_refs": []}],
        }
        assert _resolve_artifact_names(result) is None

    def test_deduplicates_refs(self):
        """Deduplicates artifact_refs pointing to same artifact."""
        from sanityops_cli.defect_checker.renderer import _resolve_artifact_names
        result = {
            "artifacts": [{"id": "skill-1", "name": "morning-report"}],
            "defects": [
                {"artifact_refs": ["skill-1"]},
                {"artifact_refs": ["skill-1"]},
            ],
        }
        assert _resolve_artifact_names(result) == "morning-report"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/a1234/Documents/project/sanityops-cli/.claude/worktrees/model-config-comments-in-init-template-e55c19
python -m pytest tests/unit/defect_checker/test_renderer.py::TestResolveArtifactNames -v
```
Expected: FAIL with "ImportError: cannot import name '_resolve_artifact_names'"

- [ ] **Step 3: Add `_MODULE_TYPE_LABELS` constant to renderer.py**

Add after `_MODULE_LABELS` definition (around line 35):

```python
#: Map module names to singular type labels for panel titles.
_MODULE_TYPE_LABELS: dict[str, str] = {
    "QDS": "Skill",
    "QDT": "Tool",
    "QDP": "Prompt",
}
```

- [ ] **Step 4: Add `_resolve_artifact_names()` function to renderer.py**

Add after `_MODULE_TYPE_LABELS`:

```python
def _resolve_artifact_names(result: dict[str, Any]) -> str | None:
    """Resolve artifact names from defect's artifact_refs.

    1. Collects artifact_refs from all defects
    2. Maps refs to artifact names via artifacts[].id -> artifacts[].name
    3. Returns comma-separated names or None
    """
    artifacts = [a for a in result.get("artifacts") or [] if isinstance(a, dict)]
    by_id = {a.get("id"): a for a in artifacts if isinstance(a.get("id"), str)}

    names: list[str] = []
    refs: list[str] = []
    for defect in result.get("defects") or []:
        for ref in defect.get("artifact_refs") or []:
            if isinstance(ref, str) and ref not in refs:
                refs.append(ref)

    seen: set[str] = set()
    for ref in refs:
        artifact = by_id.get(ref)
        name = artifact.get("name") if artifact else None
        if isinstance(name, str) and name and name not in seen:
            names.append(name)
            seen.add(name)

    if names:
        return ", ".join(names)
    if len(artifacts) == 1:
        return artifacts[0].get("name")
    return None
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/unit/defect_checker/test_renderer.py::TestResolveArtifactNames -v
```
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/sanityops_cli/defect_checker/renderer.py tests/unit/defect_checker/test_renderer.py
git commit -m "feat(renderer): add _resolve_artifact_names for cross-artifact support"
```

---

## Task 2: Add `resolve_artifact_title()` and update `_render_artifact_groups()`

**Files:**
- Modify: `src/sanityops_cli/defect_checker/renderer.py`
- Modify: `tests/unit/defect_checker/test_renderer.py`

**Interfaces:**
- Consumes: `_resolve_artifact_names()`, `_MODULE_LABELS`, `_MODULE_TYPE_LABELS`
- Produces: `resolve_artifact_title(result: dict[str, Any]) -> str | None`

- [ ] **Step 1: Write failing tests for `resolve_artifact_title()`**

Add to `tests/unit/defect_checker/test_renderer.py`:

```python
class TestResolveArtifactTitle:
    def test_qds_with_resolvable_names(self):
        """Returns 'Skill <name>' when QDS module with resolvable artifact."""
        from sanityops_cli.defect_checker.renderer import resolve_artifact_title
        result = {
            "module": "QDS",
            "artifacts": [{"id": "skill-1", "name": "morning-report"}],
            "defects": [{"artifact_refs": ["skill-1"]}],
        }
        assert resolve_artifact_title(result) == "Skill morning-report"

    def test_qdt_without_resolvable_names(self):
        """Returns plural label when QDT module without resolvable names."""
        from sanityops_cli.defect_checker.renderer import resolve_artifact_title
        result = {
            "module": "QDT",
            "artifacts": [],
            "defects": [],
        }
        assert resolve_artifact_title(result) == "Tools"

    def test_cross_module(self):
        """Returns 'Cross' for CROSS module."""
        from sanityops_cli.defect_checker.renderer import resolve_artifact_title
        result = {"module": "CROSS"}
        assert resolve_artifact_title(result) == "Cross"

    def test_unknown_module(self):
        """Returns None for unknown modules."""
        from sanityops_cli.defect_checker.renderer import resolve_artifact_title
        result = {"module": "UNKNOWN"}
        assert resolve_artifact_title(result) is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/unit/defect_checker/test_renderer.py::TestResolveArtifactTitle -v
```
Expected: FAIL with "ImportError: cannot import name 'resolve_artifact_title'"

- [ ] **Step 3: Add `resolve_artifact_title()` function to renderer.py**

Add after `_resolve_artifact_names()`:

```python
def resolve_artifact_title(result: dict[str, Any]) -> str | None:
    """Generate panel title for QDS/QDT/QDP/CROSS results.

    Returns:
        - "Skill morning-report" (type + name) if artifacts resolvable
        - "Skills" (plural label) if not resolvable
        - "Cross" for CROSS module
        - None for unknown modules
    """
    module = result.get("module")

    if module == "CROSS":
        return "Cross"

    fallback_label = _MODULE_LABELS.get(module)
    if fallback_label is None:
        return None

    artifact_names = _resolve_artifact_names(result)
    type_label = _MODULE_TYPE_LABELS.get(module)
    if type_label and artifact_names:
        return f"{type_label} {artifact_names}"
    return fallback_label
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/unit/defect_checker/test_renderer.py::TestResolveArtifactTitle -v
```
Expected: PASS

- [ ] **Step 5: Update `_MODULE_LABELS` to include CROSS**

Modify the `_MODULE_LABELS` dictionary (around line 31):

```python
_MODULE_LABELS: dict[str, str] = {
    "QDS": "Skills",
    "QDT": "Tools",
    "QDP": "Prompts",
    "CROSS": "Cross",
}
```

- [ ] **Step 6: Update `_render_artifact_groups()` to use `resolve_artifact_title()`**

Replace the existing `_render_artifact_groups()` method (lines 78-89):

```python
def _render_artifact_groups(self, results: list[dict[str, Any]]) -> None:
    for result in results:
        title = resolve_artifact_title(result)
        if title is None:
            continue
        defects = result.get("defects", [])
        if not defects:
            continue
        self._render_group(title, defects)
        self.console.print()
```

- [ ] **Step 7: Update existing test `test_cross_module_ignored` to expect CROSS rendering**

Change the test in `tests/unit/defect_checker/test_renderer.py`:

```python
def test_cross_module_rendered(self):
    """CROSS module defects are now rendered."""
    console = Console(record=True, width=80)
    result = _result([
        {"module": "CROSS", "status": "completed", "artifacts": [], "defects": [_qds_defect("c1", "P0")]}
    ])
    DefectRenderer(console).render(result)
    out = console.export_text()
    assert "c1" in out
    assert "Cross" in out
```

- [ ] **Step 8: Run all renderer tests to verify they pass**

```bash
python -m pytest tests/unit/defect_checker/test_renderer.py -v
```
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add src/sanityops_cli/defect_checker/renderer.py tests/unit/defect_checker/test_renderer.py
git commit -m "feat(renderer): add resolve_artifact_title and enable CROSS rendering"
```

---

## Task 3: Add `_aggregate_cross_defects()` to markdown_reporter.py

**Files:**
- Modify: `src/sanityops_cli/defect_checker/markdown_reporter.py`
- Modify: `tests/unit/defect_checker/test_markdown_reporter.py`

**Interfaces:**
- Consumes: SDK response with multiple CROSS sub-results
- Produces: `_aggregate_cross_defects(cross_results: list[dict]) -> list[dict]`

- [ ] **Step 1: Write failing tests for `_aggregate_cross_defects()`**

Add to `tests/unit/defect_checker/test_markdown_reporter.py`:

```python
class TestAggregateCrossDefects:
    def test_empty_input(self):
        """Returns empty list for empty input."""
        from sanityops_cli.defect_checker.markdown_reporter import _aggregate_cross_defects
        assert _aggregate_cross_defects([]) == []

    def test_single_cross_result(self):
        """Aggregates defects from a single CROSS result."""
        from sanityops_cli.defect_checker.markdown_reporter import _aggregate_cross_defects
        cross_results = [
            {
                "defects": [
                    {"id": "QD-PT-1", "severity": "P0", "category": "QD-PT"},
                ]
            }
        ]
        result = _aggregate_cross_defects(cross_results)
        assert len(result) == 1
        assert result[0] == {
            "defect_id": "QD-PT-1",
            "defect_level": "P0",
            "relation": "QD-PT",
        }

    def test_multiple_cross_results(self):
        """Aggregates defects from multiple CROSS results (PS/PT/ST)."""
        from sanityops_cli.defect_checker.markdown_reporter import _aggregate_cross_defects
        cross_results = [
            {
                "defects": [
                    {"id": "QD-PS-1", "severity": "P1", "category": "QD-PS"},
                ]
            },
            {
                "defects": [
                    {"id": "QD-PT-2", "severity": "P0", "category": "QD-PT"},
                ]
            },
        ]
        result = _aggregate_cross_defects(cross_results)
        assert len(result) == 2
        assert result[0]["defect_id"] == "QD-PS-1"
        assert result[1]["defect_id"] == "QD-PT-2"

    def test_skips_non_dict_defects(self):
        """Skips defects that are not dicts."""
        from sanityops_cli.defect_checker.markdown_reporter import _aggregate_cross_defects
        cross_results = [
            {
                "defects": [
                    {"id": "QD-PT-1", "severity": "P0", "category": "QD-PT"},
                    "invalid",
                    None,
                ]
            }
        ]
        result = _aggregate_cross_defects(cross_results)
        assert len(result) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/unit/defect_checker/test_markdown_reporter.py::TestAggregateCrossDefects -v
```
Expected: FAIL with "ImportError: cannot import name '_aggregate_cross_defects'"

- [ ] **Step 3: Add `_aggregate_cross_defects()` function to markdown_reporter.py**

Add after `_format_score()` function (around line 54):

```python
def _aggregate_cross_defects(cross_results: list[dict]) -> list[dict]:
    """Aggregate defects from all CROSS sub-results (PS/PT/ST) into one list.

    Maps SDK DefectItem format to CrossScoringCalculator format:
        id -> defect_id
        severity -> defect_level
        category -> relation (QD-PS, QD-PT, QD-ST)
    """
    defects = []
    for result in cross_results:
        for d in result.get("defects") or []:
            if not isinstance(d, dict):
                continue
            defects.append({
                "defect_id": d.get("id"),
                "defect_level": d.get("severity"),
                "relation": d.get("category"),
            })
    return defects
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/unit/defect_checker/test_markdown_reporter.py::TestAggregateCrossDefects -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/sanityops_cli/defect_checker/markdown_reporter.py tests/unit/defect_checker/test_markdown_reporter.py
git commit -m "feat(markdown_reporter): add _aggregate_cross_defects for cross-artifact support"
```

---

## Task 4: Add `_calculate_cross_score()` to markdown_reporter.py

**Files:**
- Modify: `src/sanityops_cli/defect_checker/markdown_reporter.py`
- Modify: `tests/unit/defect_checker/test_markdown_reporter.py`

**Interfaces:**
- Consumes: Aggregated cross defects, `defect_check.cross.scoring.CrossScoringCalculator`
- Produces: `_calculate_cross_score(defects: list[dict], check_level: str) -> dict | None`

- [ ] **Step 1: Write failing tests for `_calculate_cross_score()`**

Add to `tests/unit/defect_checker/test_markdown_reporter.py`:

```python
class TestCalculateCrossScore:
    def test_empty_input(self):
        """Returns None for empty input."""
        from sanityops_cli.defect_checker.markdown_reporter import _calculate_cross_score
        assert _calculate_cross_score([], "L2") is None

    def test_valid_defects(self):
        """Returns score dict for valid defects."""
        from sanityops_cli.defect_checker.markdown_reporter import _calculate_cross_score
        defects = [
            {"defect_id": "QD-PT-1", "defect_level": "P1", "relation": "QD-PT"},
        ]
        result = _calculate_cross_score(defects, "L2")
        # Should return a dict with total_score and gate_result
        assert isinstance(result, dict)
        assert "total_score" in result
        assert "gate_result" in result

    def test_sdk_exception_returns_none(self):
        """Returns None gracefully when SDK raises exception."""
        from unittest.mock import patch
        from sanityops_cli.defect_checker.markdown_reporter import _calculate_cross_score

        defects = [{"defect_id": "x", "defect_level": "P0", "relation": "QD-PT"}]
        
        # Patch CrossScoringCalculator to raise an exception
        with patch(
            "defect_check.cross.scoring.CrossScoringCalculator.calculate_score",
            side_effect=RuntimeError("SDK error"),
        ):
            result = _calculate_cross_score(defects, "L2")
            assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/unit/defect_checker/test_markdown_reporter.py::TestCalculateCrossScore -v
```
Expected: FAIL with "ImportError: cannot import name '_calculate_cross_score'"

- [ ] **Step 3: Add `_calculate_cross_score()` function to markdown_reporter.py**

Add after `_aggregate_cross_defects()`:

```python
def _calculate_cross_score(
    defects: list[dict],
    check_level: str,
) -> dict | None:
    """Compute merged CROSS score using SDK's CrossScoringCalculator.

    The SDK uses weighted deductions per PS/PT/ST group:
        P0:P1:P2 = 5:3:1 deduction weights
        Gate FAIL when any group has P0 defect
    """
    if not defects:
        return None
    try:
        from defect_check.cross.scoring import CrossScoringCalculator
        scoring = CrossScoringCalculator().calculate_score(defects, check_level, mode=None)
    except Exception:
        return None
    return {
        "total_score": scoring.get("total_score"),
        "gate_result": scoring.get("gate_result", "PASS"),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/unit/defect_checker/test_markdown_reporter.py::TestCalculateCrossScore -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/sanityops_cli/defect_checker/markdown_reporter.py tests/unit/defect_checker/test_markdown_reporter.py
git commit -m "feat(markdown_reporter): add _calculate_cross_score for cross-artifact scoring"
```

---

## Task 5: Update `_build_report()` to merge CROSS sub-results

**Files:**
- Modify: `src/sanityops_cli/defect_checker/markdown_reporter.py`
- Modify: `tests/unit/defect_checker/test_markdown_reporter.py`

**Interfaces:**
- Consumes: `_aggregate_cross_defects()`, `_calculate_cross_score()`, SDK response
- Produces: Merged CROSS section in markdown report

- [ ] **Step 1: Write failing integration test for CROSS merging**

Add to `tests/unit/defect_checker/test_markdown_reporter.py`:

```python
class TestCrossArtifactReport:
    def test_cross_module_merged_in_report(self, tmp_path):
        """CROSS sub-results are merged into single section."""
        response = _response(
            results=[
                {
                    "module": "QDS",
                    "status": "completed",
                    "defects": [_defect(defect_id="QDS-1", severity="P1")],
                },
                {
                    "module": "CROSS",
                    "status": "completed",
                    "defects": [
                        {"id": "QD-PT-1", "name": "cross1", "severity": "P0", 
                         "description": "d", "location": "l", "impact": "i", 
                         "fix_suggestion": "f", "category": "QD-PT"},
                    ],
                },
            ]
        )
        path = save_markdown_report(response, tmp_path)
        content = path.read_text(encoding="utf-8")
        # Should contain CROSS section with merged results
        assert "## Cross (CROSS)" in content
        assert "QD-PT-1" in content

    def test_multiple_cross_subresults_merged(self, tmp_path):
        """Multiple CROSS sub-results (PS/PT/ST) are merged."""
        response = _response(
            results=[
                {
                    "module": "CROSS",
                    "status": "completed",
                    "defects": [
                        {"id": "QD-PS-1", "name": "ps1", "severity": "P1",
                         "description": "d", "location": "l", "impact": "i",
                         "fix_suggestion": "f", "category": "QD-PS"},
                    ],
                },
                {
                    "module": "CROSS",
                    "status": "completed",
                    "defects": [
                        {"id": "QD-PT-1", "name": "pt1", "severity": "P0",
                         "description": "d", "location": "l", "impact": "i",
                         "fix_suggestion": "f", "category": "QD-PT"},
                    ],
                },
            ]
        )
        path = save_markdown_report(response, tmp_path)
        content = path.read_text(encoding="utf-8")
        # Should contain only one CROSS section
        assert content.count("## Cross (CROSS)") == 1
        assert "QD-PS-1" in content
        assert "QD-PT-1" in content
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/unit/defect_checker/test_markdown_reporter.py::TestCrossArtifactReport -v
```
Expected: FAIL - CROSS section not found or not merged

- [ ] **Step 3: Update `_build_report()` to merge CROSS sub-results**

Modify the `_build_report()` function. Find the results processing section (around line 101) and replace the loop with:

```python
def _build_report(
    response: dict[str, Any],
    *,
    project_id: str | None,
    check_level: str,
    generated_at: datetime,
) -> str:
    """Render the full markdown report body."""
    summary = response.get("summary", {})
    results = response.get("results", [])
    errors = response.get("errors", [])
    metadata = response.get("metadata", {})
    status = response.get("status", "unknown")

    lines: list[str] = []
    lines.append("# Inspect Report")
    lines.append("")

    # Meta
    lines.append(f"- **Generated**: {generated_at.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- **Check level**: {check_level}")
    lines.append(f"- **Status**: {status}")
    if project_id:
        lines.append(f"- **Project ID**: {project_id}")
    exec_time = metadata.get("execution_time_seconds")
    if exec_time is not None:
        lines.append(f"- **Execution time**: {exec_time:.2f}s")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    total = summary.get("total_defects", 0)
    p0 = summary.get("p0_count", 0)
    p1 = summary.get("p1_count", 0)
    p2 = summary.get("p2_count", 0)
    gate = summary.get("gate_result", "PASS")
    lines.append(f"| Total defects | {total} |")
    lines.append(f"| Severity | P0: {p0} / P1: {p1} / P2: {p2} |")
    lines.append(f"| Gate | {gate} |")
    lines.append("")

    # Separate CROSS from other modules and merge
    module_results = [r for r in results if r.get("module") != "CROSS"]
    cross_results = [r for r in results if r.get("module") == "CROSS"]

    if cross_results:
        # Merge all CROSS sub-results into single section
        cross_defects = [d for r in cross_results for d in (r.get("defects") or [])]
        mapped_defects = _aggregate_cross_defects(cross_results)
        cross_score = _calculate_cross_score(mapped_defects, check_level)

        module_results.append({
            "module": "CROSS",
            "status": "completed",
            "defects": cross_defects,
            "score": cross_score,
        })

    # Per-module results
    for result in module_results:
        module = result.get("module", "")
        label = _MODULE_LABELS.get(module, module)
        result_status = result.get("status", "unknown")
        score = result.get("score")
        defects = result.get("defects", [])

        score_str = _format_score(score)
        header = f"## {label} ({module}) — {result_status}"
        if score_str:
            header += f", {score_str}"
        lines.append(header)
        lines.append("")

        if not defects:
            lines.append("No defects found.")
            lines.append("")
            continue

        lines.append("| ID | Name | Severity | Description | Location | Impact | Fix |")
        lines.append("|---|---|---|---|---|---|---|")
        for defect in defects:
            defect_id = _esc_md_cell(defect.get("id"))
            name = _esc_md_cell(defect.get("name"))
            severity = _esc_md_cell(defect.get("severity"))
            description = _esc_md_cell(defect.get("description"))
            location = _esc_md_cell(defect.get("location"))
            impact = _esc_md_cell(defect.get("impact"))
            fix = _esc_md_cell(defect.get("fix_suggestion"))
            lines.append(
                f"| {defect_id} | {name} | {severity} | {description} |"
                f" {location} | {impact} | {fix} |"
            )
        lines.append("")

    # Errors section
    if errors:
        lines.append("## Errors")
        lines.append("")
        for err in errors:
            code = err.get("code", "unknown")
            message = err.get("message", "")
            retryable = err.get("retryable", False)
            lines.append(f"- **{code}** (retryable={retryable}): {message}")
        lines.append("")

    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/unit/defect_checker/test_markdown_reporter.py::TestCrossArtifactReport -v
```
Expected: PASS

- [ ] **Step 5: Run all markdown_reporter tests**

```bash
python -m pytest tests/unit/defect_checker/test_markdown_reporter.py -v
```
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/sanityops_cli/defect_checker/markdown_reporter.py tests/unit/defect_checker/test_markdown_reporter.py
git commit -m "feat(markdown_reporter): merge CROSS sub-results in report"
```

---

## Task 6: Run full test suite and verify

**Files:**
- No new files

- [ ] **Step 1: Run all tests**

```bash
python -m pytest tests/ -v
```
Expected: All tests PASS

- [ ] **Step 2: Run ruff lint and format**

```bash
ruff check src/ tests/
ruff format --check src/ tests/
```
Expected: No errors

- [ ] **Step 3: Final commit if any fixes needed**

```bash
git add -A
git commit -m "chore: fix lint and format issues"
```

---

## Task 7: Update renderer import in markdown_reporter.py

**Files:**
- Modify: `src/sanityops_cli/defect_checker/markdown_reporter.py`

**Note:** The markdown_reporter imports `_MODULE_LABELS` from renderer.py. After adding CROSS to the dict, the markdown reporter will automatically use it. Verify the import still works.

- [ ] **Step 1: Verify import statement**

Check that line 25 in `markdown_reporter.py` reads:
```python
from sanityops_cli.defect_checker.renderer import _MODULE_LABELS
```

If it doesn't, update it.

- [ ] **Step 2: Run markdown_reporter tests again**

```bash
python -m pytest tests/unit/defect_checker/test_markdown_reporter.py -v
```
Expected: PASS