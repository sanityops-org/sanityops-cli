---
title: Code Contract Inspection Checklist (QC, v2 unified engine edition)
---

# Code Contract Inspection Checklist (QC, v2)

> **Status**: v2 unified engine edition. Rule semantics originate from `quality/code-contract.md` v1.0: IDs, names, and severity values all remain unchanged; what changes is the **organization** — all fields + body tables (model items) + program blocks (program items).
>
> Shared definitions (field model / check_engine mapping / applicability structural-fact gate / severity notation / scoring rules) are in [_meta.md](_meta.md); this file does not repeat them. This file only carries the Code Contract domain check items themselves.

## 1. Domain notes

- **Scope** (source §1): only code snippets embedded in Logic Artifacts are checked (System Prompt / Skill description and steps / Tool Schema's description·default·example fields). **Complete source files are not checked** (use a standard linter).
- **L dimension**: none. Severity in this domain is **flat P0/P1/P2** (no OR-L / AC-L dimensions); the severity column in the index table has only one tier.
- **Baseline gate QC-0** (5 items): entry gate; MUST pass before the QC-1 through QC-4 checks.
- **Context-dependent rules** (source §1): QC-1.2 (Invalid Import) and QC-1.3 (Deprecated API) depend on **external input** (declared dependency list + API version database), which is not in the Logic Artifact. When external input is missing (the lite default), record `Not Executed`, **never FAIL**; record FAIL only when a defect is self-evident within the snippet (e.g., importing a clearly nonexistent module) or the snippet contradicts itself.
- **Illustrative snippet rules** (source §1): snippets whose outer text marks them as illustrative/pseudocode ("example"/"pseudo", omission via `...`) are exempt from the parse-completeness requirements of QC-0.1 / QC-0.3; omissions or missing imports do not constitute FAIL.
- **check_engine assignment convention (reclassification log for this domain)**: source Method column `Automated`→program, `Semi-automated`→hybrid, `Pattern match`→program (deterministic pattern matching, executable by a program); QC-0 has no Method column and is mapped per the Appendix detection strategy (0.4 fence matching→program, 0.5 language-content keyword matching→hybrid). This domain has **no pure model items** (lint type).
- **Cross-domain cross-references** (source §5 note): QC-3.3 (Hardcoded Demo Value) overlaps NR-S-9 (Hardcoded Credential) — NR-S-9 takes precedence for actual credentials; QC-3.3 covers weak/demo patterns ("123456", "xxx", "changeme", local paths, internal IPs) that fall outside credential detectors.

## 2. Check item index (17 items = 5 baseline gates + 12 check items)

| ID | name | check_engine | applicability.fact | severity | Counted in scoring |
|---|---|---|---|---|---|
| QC-0.1 | Syntax Parsability | program | has_code_snippet | P0 | ✗ (baseline) |
| QC-0.2 | Language Declaration | program | has_code_snippet | P1 | ✗ (baseline) |
| QC-0.3 | Structural Completeness | program | has_code_snippet | P1 | ✗ (baseline) |
| QC-0.4 | Fence Integrity | program | has_code_snippet | P1 | ✗ (baseline) |
| QC-0.5 | Language-Content Mismatch | hybrid | has_code_snippet | P2 | ✗ (baseline) |
| QC-1.1 | Undefined Name Reference | program | has_code_snippet | P1 | ✓ |
| QC-1.2 | Invalid Import | program | has_import | P2 | ✓ |
| QC-1.3 | Deprecated API Usage | hybrid | has_api_call | P2 | ✓ |
| QC-1.4 | Type Mismatch | program | has_code_snippet | P2 | ✓ |
| QC-2.1 | Unclosed File Handle | program | has_file_handle | P1 | ✓ |
| QC-2.2 | Unreleased Network Connection | program | has_network_conn | P2 | ✓ |
| QC-2.3 | Missing Exception Handling | program | has_high_risk_op | P2 | ✓ |
| QC-3.1 | Unused Import | program | has_import | P2 | ✓ |
| QC-3.2 | Missing Import | program | has_code_snippet | P1 | ✓ |
| QC-3.3 | Hardcoded Demo Value | program | has_literal | P2 | ✓ |
| QC-4.1 | Snippet-Artifact Declaration Mismatch | hybrid | has_code_snippet | P1 | ✓ |
| QC-4.2 | Snippet-Body Version/API Drift | hybrid | has_code_snippet | P2 | ✓ |

> Count note: 5 baseline gates (QC-0, entry gate) + 12 check items (QC-1 through QC-4). `has_code_snippet` = code snippet embedded in the artifact (the existence precondition for this domain); `has_import`/`has_api_call`/`has_file_handle`/`has_network_conn`/`has_high_risk_op`/`has_literal` are construction facts within the snippet (observing "whether the snippet contains that construct", not "whether it has been declared" — point-1-paradox prevention). QC-1.2/1.3 are constrained by the context-dependent rules (external input missing → Not Executed).

## 3. Model judgment points

> This domain has **no pure model items**. The model-confirmation portion of hybrid items is below.

### 3.1 Pure model items

None.

### 3.2 Model-confirmation portion of hybrid items

> **Skill side: this section is the complete judgment points, with no program pre-screening upstream.** Descriptions such as "keyword matching is a fuzzy signal" describe the CLI / platform pre-screen path; the skill performs full model reasoning, does not execute §4, must complete the semantic judgment itself, and must not treat it as "already screened" nor judge N/A on that basis.

| ID | model_prompt (confirmation points) |
|---|---|
| QC-0.5 | Confirm whether the fence-declared language truly mismatches the snippet content syntax (keyword matching is a fuzzy signal and requires semantic verification) |
| QC-1.3 | Check against the API version database whether the call is indeed deprecated/removed; record Not Executed when the version database is missing |
| QC-4.1 | Confirm whether the snippet's calls/parameters truly contradict the owning artifact's own declarations (Tool properties/required, Skill/Prompt field names) |
| QC-4.2 | Confirm whether the snippet truly drifts from the version/dependency/API declared by the owning artifact (stale example) |

## 4. Program-judgment items (program-check code block)

> **CLI / platform only: the skill does not parse or execute this code block** (the skill performs full model reasoning and does not consume `check_engine` or `program_rule`). The program engine only parses this code block. The `rule` field is **a semantic illustration of judgment** (not the final executable definition; program-level implementation to be added later). Covers pure program items + the pre-screen rules for hybrid items.

<!-- program-check -->
```json
{
  "domain": "code-contract",
  "version": "v2",
  "note": "Program-judgment items + hybrid pre-screen rules. rule is a semantic illustration of the judgment.",
  "checks": [
    { "id": "QC-0.1", "summary": "The snippet cannot be parsed as the declared language (syntax error)" },
    { "id": "QC-0.2", "summary": "The code block lacks a language identifier (e.g., ```python)" },
    { "id": "QC-0.3", "summary": "The snippet lacks necessary imports or the function body is truncated by ... (illustrative snippets exempt)" },
    { "id": "QC-0.4", "summary": "Code fence open/close mismatch, or the closing fence is swallowed by code content" },
    { "id": "QC-0.5", "summary": "The fence-declared language does not match content keywords (whether it truly mismatches is confirmed by the model)" },
    { "id": "QC-1.1", "summary": "AST parsing + name resolution: reference to an undefined name" },
    { "id": "QC-1.2", "summary": "The module referenced by the import statement is not in the standard library/dependency list (dependency list missing → Not Executed)" },
    { "id": "QC-1.3", "summary": "The API signature matches the deprecated version database (version database missing → Not Executed; confirmation by the model)" },
    { "id": "QC-1.4", "summary": "Literal type inference: parameter types are clearly incompatible" },
    { "id": "QC-2.1", "summary": "open()/plumber.open() without with or close()" },
    { "id": "QC-2.2", "summary": "Connection constructor (HTTPSConnection etc.) without a context manager or close()" },
    { "id": "QC-2.3", "summary": "High-risk call (file/network/DB) without a try/except block" },
    { "id": "QC-3.1", "summary": "import extraction vs reference counting: imported but never referenced" },
    { "id": "QC-3.2", "summary": "reference extraction vs import matching: referenced but not imported" },
    { "id": "QC-3.3", "summary": "Weak credential/machine-specific value patterns (consecutive digits/xxx/changeme/local path/internal IP)" },
    { "id": "QC-4.1", "summary": "Snippet symbol extraction vs owning artifact field/property matching (the model confirms whether they are contradictory)" },
    { "id": "QC-4.2", "summary": "Snippet API/version references vs artifact body declarations matching (the model confirms whether it has drifted)" }
  ]
}
```
<!-- /program-check -->

## 5. Tombstone records

None. The Code Contract domain source specification contains no merged / transferred items.

## 6. Scoring field notes (platform only)

- This domain's source specification has **no explicit scoring section**; severity is flat P0/P1/P2, following the global weight `P0:P1:P2 = 5:3:1` in `_meta.md`.
- Check items with `✓` in the `Counted in scoring` column enter the denominator; `✗` (QC-0 baseline gates) are not counted.
- skill / CLI do not activate scoring, but the score_weight information is retained in the index table for platform use.
