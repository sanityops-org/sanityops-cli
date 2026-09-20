# Cross-Artifact Result Rendering Migration Design

**Date**: 2026-09-20
**Status**: Approved
**Scope**: Terminal rendering + Markdown report generation

## Background

sanityops-cli currently skips rendering of cross-artifact defects (module type "CROSS") in both terminal and markdown outputs. The defect-check SDK returns cross-artifact analysis results, but the CLI explicitly skips them.

This design migrates the cross-artifact rendering functionality from deeplogic-cli to sanityops-cli.

## Migration Scope

| Component | Status | Action |
|-----------|--------|--------|
| Terminal rendering (`renderer.py`) | Missing CROSS support | Migrate |
| Markdown report (`markdown_reporter.py`) | Missing CROSS support | Migrate |
| Repair agent (`repair_agent/`) | Already complete | No changes |

## File Changes

### 1. `src/sanityops_cli/defect_checker/renderer.py`

#### 1.1 Update `_MODULE_LABELS`

Add CROSS mapping:

```python
_MODULE_LABELS: dict[str, str] = {
    "QDS": "Skills",
    "QDT": "Tools",
    "QDP": "Prompts",
    "CROSS": "Cross",  # NEW
}
```

#### 1.2 Add `_MODULE_TYPE_LABELS`

Singular form for panel titles:

```python
_MODULE_TYPE_LABELS: dict[str, str] = {
    "QDS": "Skill",
    "QDT": "Tool",
    "QDP": "Prompt",
}
```

#### 1.3 Add `_resolve_artifact_names()`

Resolve artifact names from defect's `artifact_refs` array:

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

#### 1.4 Add `resolve_artifact_title()`

Generate panel title for rendering:

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

#### 1.5 Update `_render_artifact_groups()`

Use `resolve_artifact_title()` instead of direct label lookup:

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

---

### 2. `src/sanityops_cli/defect_checker/markdown_reporter.py`

#### 2.1 Add `_aggregate_cross_defects()`

Aggregate defects from multiple CROSS sub-results:

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

#### 2.2 Add `_calculate_cross_score()`

Calculate unified score using SDK's CrossScoringCalculator:

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

#### 2.3 Update `_build_report()`

Merge CROSS sub-results before rendering:

```python
def _build_report(...):
    # ... existing code ...

    results = response.get("results", [])

    # Separate CROSS from other modules
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

    # Render each module section (loop over module_results instead of results)
    for result in module_results:
        # ... existing rendering code ...
```

---

## Data Flow

```
SDK Response
    │
    ├── QDS/QDT/QDP modules
    │       │
    │       └── resolve_artifact_title() → "Skill morning-report"
    │               │
    │               └── Render with artifact name in title
    │
    └── CROSS modules (multiple: PS/PT/ST)
            │
            ├── _aggregate_cross_defects() → Unified defect list
            │
            └── _calculate_cross_score() → Unified score
                    │
                    └── Merge into single CROSS result for rendering
```

---

## Cross-Artifact Defect Types

| ID Prefix | Name | Description |
|-----------|------|-------------|
| QD-PS | Prompt-Skill | Inconsistencies between prompts and skills |
| QD-PT | Prompt-Tool | Inconsistencies between prompts and tools |
| QD-ST | Skill-Tool | Inconsistencies between skills and tools |

---

## Dependencies

- `defect_check.cross.scoring.CrossScoringCalculator` — SDK class for cross-artifact scoring
- No new external dependencies required

---

## Testing Strategy

### Unit Tests

1. **`test_resolve_artifact_names()`**
   - Single artifact with refs
   - Multiple artifacts with refs
   - No refs but single artifact (fallback)
   - No refs and multiple artifacts (None)

2. **`test_resolve_artifact_title()`**
   - QDS/QDT/QDP with resolvable names
   - QDS/QDT/QDP without resolvable names
   - CROSS module
   - Unknown module

3. **`test_aggregate_cross_defects()`**
   - Empty input
   - Single CROSS result
   - Multiple CROSS results

4. **`test_calculate_cross_score()`**
   - Empty input
   - Valid defects
   - SDK exception handling

### Integration Tests

- Full rendering with mock SDK response containing CROSS results
- Verify markdown output contains merged CROSS section

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| SDK `CrossScoringCalculator` API changes | Low | Medium | Graceful fallback to None on exception |
| Missing artifact_refs in SDK response | Low | Low | Fallback to plural label ("Skills") |

---

## Implementation Checklist

- [ ] Update `renderer.py` with new constants and functions
- [ ] Update `markdown_reporter.py` with aggregation and scoring
- [ ] Add unit tests for new functions
- [ ] Add integration test for full rendering flow
- [ ] Verify existing tests still pass