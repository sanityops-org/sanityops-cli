---
title: Skill Inspection Checklist (QD-S, v2 unified engine edition)
---

# Skill Inspection Checklist (QD-S, v2)

> **Status**: v2 unified engine edition. Rule semantics derive from `inspect/skill.md` v1.1 (2026-10): IDs, names, and severity values all remain unchanged; what changes is the **organization** — full fields + body tables (model items) + program block (program items).
>
> Shared definitions (field model / check_engine mapping / applicability structural-fact gate / severity notation / scoring rules) see [_meta.md](_meta.md); not repeated here. This file carries only the Skill-domain check items themselves.

## 1. Domain notes

- **L naming**: this domain's severity header uses **OR-L1/OR-L2/OR-L3** (operation risk: L1 read-only / L2 reversible write / L3 irreversible; Skill with no tool invocation → L1, with tool invocation → per the highest risk of the operations performed). Skill domain has no AC-L dimension.
- **Baseline gate QD-S-0** (9 items): platform minimal structural validation (parseable, checkable), **PASS/FAIL, not scored** (source §11.3). QD-S-0.9 is SHOULD level, not counted in the gate. Relaxed failure handling (v1.1): only when QD-S-0.3 is completely unparseable does it block QD-S-1~5 checks; a defect in any other QD-S-0 item is marked "baseline not passed" and checking continues, with the conclusion recorded as "assessment incomplete (NEEDS_REVIEW)".
- **check_engine assignment convention (this domain's reclassification log)** (source §6 six-step flow + design §2.8 "prioritize convergence"):
  - QD-S-0 structural validation (0.1–0.4, 0.6–0.9) → `program`; 0.5 (conflict judgment, requires human review) → `hybrid`.
  - Quantity-boundary/unbounded-wording scanning class (1.1–1.3, 2.1–2.4, keyword scanning in source §6 step 4) → `hybrid` (program keyword pre-screening + model confirmation).
  - Semantic/declaration-sufficiency class (1.4–1.5, 3.x, 4.x, 5.x, source §6 step 5) → `model`.
- **"Missing declaration is a defect" convention** (source §1): absence of the declaration required by a rule definition is FAIL; the trailing "allowing / leading-to …" of a definition is a **risk mechanism**, not an additional premise. **Exception for QD-S-2.x**: they detect "unbounded wording already written out"; the defect is the **presence** of the wording (positive detection).
- **Effective constraints and compensating controls** (source §7.5, cross-item severity principle): traceable constraints within the artifact (Tool Schema fields, `allowed_operations`, declared scope/service-account) can affect severity; external Harness/RBAC/platform controls serve only as `compensating_controls` (affecting disposition, not defect existence); insufficient evidence outputs "to-be-verified", with no forced grading.
- **Five-state results** (source §7.4): Pass / Defect / N/A / Insufficient Evidence / Not Checked; N/A must state its basis; "Insufficient Evidence" outputs "to-be-verified" and is not scored.
- **Advisory/optional items**: QD-S-3.2, 3.7 are optional at L1 (recommended, not mandatory); this file still lists them as active items, with L1 severity marked ∅ (reference level, traceable to the original P at L2/L3).

## 2. Check item index (33 items = 9 baseline gate + 24 semantic items)

| ID | name | check_engine | applicability.fact | severity OR-L1/L2/L3 | Counted in scoring |
|---|---|---|---|---|---|
| QD-S-0.1 | Required Field Presence | program | is_skill | gate | ✗ (baseline) |
| QD-S-0.2 | Field Content Non-Empty | program | is_skill | gate | ✗ (baseline) |
| QD-S-0.3 | Syntax Parsability | program | is_skill | gate | ✗ (baseline) |
| QD-S-0.4 | Field Type Validity | program | is_skill | gate | ✗ (baseline) |
| QD-S-0.5 | No Conflicting Declarations | hybrid | is_skill | gate | ✗ (baseline) |
| QD-S-0.6 | Minimum Structural Completeness | program | is_skill | gate | ✗ (baseline) |
| QD-S-0.7 | Dependency & Resource Existence | program | is_skill | gate | ✗ (baseline) |
| QD-S-0.8 | Metadata Completeness | program | is_skill | gate | ✗ (baseline) |
| QD-S-0.9 | description Length Budget | program | is_skill | gate (SHOULD) | ✗ (baseline) |
| QD-S-1.1 | Input Boundary Missing | hybrid | is_skill | P1 / P0 / P0 | ✓ |
| QD-S-1.2 | Output Size Missing | hybrid | is_skill | P1 / P1 / P1 | ✓ |
| QD-S-1.3 | Execution Resource Boundary Missing | hybrid | has_tool_invocation | ∅ / P0 / P0 | ✓ |
| QD-S-1.4 | Permission Boundary Missing | model | has_tool_invocation | ∅ / P1 / P0 | ✓ |
| QD-S-1.5 | Data Source Boundary Missing | model | has_data_access | ∅ / P1 / P0 | ✓ |
| QD-S-2.1 | Unbounded Quantity Declaration | hybrid | is_skill | P1 / P0 / P0 | ✓ |
| QD-S-2.2 | Unterminated Execution Declaration | hybrid | has_tool_invocation | ∅ / P0 / P0 | ✓ |
| QD-S-2.3 | Open-Ended Enumeration in Structure | hybrid | is_skill | ∅ / P1 / P1 | ✓ |
| QD-S-2.4 | Broad Capability Verbs | hybrid | is_skill | ∅ / P1 / P0 | ✓ |
| QD-S-3.1 | Vague Trigger Conditions | model | is_skill | P1 / P1 / P0 | ✓ |
| QD-S-3.2 | Missing Deactivation Conditions | model | is_skill | ∅ / P1 / P0 | ✓ |
| QD-S-3.3 | Missing Ambiguous Input Handling | model | is_skill | P1 / P1 / P0 | ✓ |
| QD-S-3.4 | Undefined Task Scope | model | is_skill | P2 / P1 / P1 | ✓ |
| QD-S-3.5 | Undeclared Default Behavior | model | is_skill | ∅ / P1 / P0 | ✓ |
| QD-S-3.6 | Metadata Expression Defects | model | is_skill | P1 / P1 / P1 | ✓ |
| QD-S-3.7 | Output Structure Contract Missing | model | is_skill | ∅ / P1 / P1 | ✓ |
| QD-S-4.1 | Undefined Failure Behavior | model | is_skill | P1 / P0 / P0 | ✓ |
| QD-S-4.2 | Undeclared Partial Completion Legitimacy | model | is_skill | ∅ / P1 / P1 | ✓ |
| QD-S-4.3 | Missing Post-Failure Prohibited Behaviors | model | is_skill | ∅ / P1 / P0 | ✓ |
| QD-S-4.4 | Error Recovery Path Undefined | model | is_skill | ∅ / P2 / P2 | ✓ |
| QD-S-5.1 | Read/Write/Delete Not Distinguished | model | has_write_semantics | ∅ / P1 / P0 | ✓ |
| QD-S-5.2 | Missing High-Risk Confirmation | model | has_irreversible_op | ∅ / ∅ / P0 | ✓ |
| QD-S-5.3 | Undeclared Environment Boundaries | model | has_environment_access | ∅ / P1 / P0 | ✓ |
| QD-S-5.4 | Undeclared Chained Invocation Permissions | model | has_skill_chaining | ∅ / P1 / P0 | ✓ |

> Count note: 9 baseline gate items (QD-S-0, pass/fail, not scored) + 24 semantic items. Semantic item severity has three OR-L tiers (L1=8 items / L2=23 items / L3=24 items, cumulative per source §4). `∅` = the original specification assigns no P at that L (reference-level display; N/A is determined separately by `applicability.fact`, independent of L). `has_tool_invocation`/`has_data_access`/`has_write_semantics`/`has_irreversible_op`/`has_environment_access`/`has_skill_chaining` are structural facts (observing "whether the artifact actually does it", not "whether it is declared" — point-1-paradox prevention).

## 3. Model judgment points (condensed definition + model_prompt)

> skill does full-model single-pass reasoning; the CLI's model-item / hybrid-item confirmation phase also reads here. `definition` is taken from source §2 / §5.

### 3.1 Pure model items (17 items)

| ID | definition (condensed) | model_prompt (judgment points) |
|---|---|---|
| QD-S-1.4 | No read/write/delete distinction, no prohibited-operation declaration | Judge whether the artifact has data operations and does not distinguish read/modify/delete scopes nor declare prohibited operations |
| QD-S-1.5 | No permitted/prohibited data sources; LLM may fetch data from history/external systems | Judge whether the artifact accesses data sources (history/external) and does not declare allowed/prohibited sources |
| QD-S-3.1 | Trigger conditions too broad; multiple unrelated intents can trigger | Judge whether allowed_when/forbidden_when are too broad and whether ambiguous triggers exist |
| QD-S-3.2 | Does not declare when the Skill should not trigger | Judge whether forbidden_when / deactivation conditions are missing |
| QD-S-3.3 | Handling of incomplete/malformed input not declared; LLM auto-completes | Judge whether on_empty_input/on_insufficient_input are missing and whether it defaults to auto-completion or inference |
| QD-S-3.4 | Missing non_goals; LLM expands boundaries on its own | Judge whether non_goals are missing and whether the task scope is over-declared |
| QD-S-3.5 | Key branches (empty input/malformed format/insufficient data) have no defined handling | Judge whether key branches lack default behavior definitions |
| QD-S-3.6 | name/description too broad, inaccurate, inconsistent with body | Judge whether metadata exaggerates/deviates from/contradicts the body's actual behavior |
| QD-S-3.7 | Output format/required fields/empty-result representation not declared; LLM chooses the structure itself | Judge whether the output structure contract is missing (format, fields, empty-result representation), noting the distinction from 1.2 (size) and 2.3 (open enumeration) |
| QD-S-4.1 | Execution failure handling not declared; LLM explores alternative paths | Judge whether a failure-handling strategy is missing and whether the model may reroute on its own |
| QD-S-4.2 | "Whether partial completion is acceptable" not declared | Judge whether the partial_result_allowed declaration is missing |
| QD-S-4.3 | Behaviors prohibited after failure not declared | Judge whether forbidden_behaviors are missing (no auto-completion/inference/scope expansion) |
| QD-S-4.4 | Per-exception recovery paths undefined | Judge whether per-exception recovery paths are missing; "safe-terminate-and-report" is a legitimate disposition |
| QD-S-5.1 | Data operations do not distinguish read/modify/delete scopes | Judge whether data operations conflate read/modify/delete |
| QD-S-5.2 | Irreversible operations (delete/overwrite/exfiltration/payment) have no confirmation gate | Judge whether irreversible operations lack the require_user_confirmation_for confirmation gate |
| QD-S-5.3 | Does not declare whether production is prohibited and which environments are allowed | Judge whether environment boundary declarations are missing (prohibited production / allowed environment list) |
| QD-S-5.4 | Calling other Skills does not declare allowed/prohibited downstream scope | Judge whether chained invocation lacks allowed_downstream_skills / scope declarations |

### 3.2 Model-confirmation portion of hybrid items

> **On the skill side: this section is the complete set of judgment points; there is no program pre-screening upstream.** "program only checks… / program only does…" describes the CLI / platform pre-screening path; skill reasons with the full model, does not execute §4, must complete the semantic judgment itself, must not treat it as "already screened", and must not use it to mark N/A.

| ID | model_prompt (confirmation points) |
|---|---|
| QD-S-0.5 | Confirm whether conflicts among body/examples/failure/permission declarations truly exist, and report both sides of the conflict (favoring neither the lenient nor the strict side) |
| QD-S-1.1 | Confirm whether input quantity/size upper bounds are truly missing (a keyword hit ≠ declared; semantic verification required) |
| QD-S-1.2 | Confirm whether the output size upper bound is truly missing |
| QD-S-1.3 | Confirm whether retry/invocation-count/timeout boundaries are truly missing |
| QD-S-2.1 | Confirm whether unbounded quantifiers (all/every/entire/complete) truly have no quantity cap |
| QD-S-2.2 | Confirm whether wording such as keep trying/until success truly has no termination condition |
| QD-S-2.3 | Confirm whether etc./and others/such as truly leave the model free to add entries itself |
| QD-S-2.4 | Confirm whether broad verbs such as manage/handle truly have no non_goals constraint |

## 4. Program-judgment items (program-check code block)

> **CLI / platform only: the skill does not parse or execute this code block** (the skill performs full-model reasoning and does not consume `check_engine` or `program_rule`). The program engine only parses this code block. The `rule` field is a **semantic illustration of judgment** (not a final executable definition; the program-level implementation follows later). Covers pure program items (QD-S-0 baseline) + pre-screening rules for hybrid items.

<!-- program-check -->
```json
{
  "domain": "skill",
  "version": "v2",
  "note": "Program-judgment items (QD-S-0 baseline) + hybrid pre-screening rules. rule is a semantic illustration.",
  "checks": [
    { "id": "QD-S-0.1", "summary": "Required fields (name/description etc.) missing" },
    { "id": "QD-S-0.2", "summary": "Required field empty or pure whitespace" },
    { "id": "QD-S-0.3", "summary": "YAML frontmatter / Markdown structure unparseable" },
    { "id": "QD-S-0.4", "summary": "Field value type mismatch (enum/boolean/number/list)" },
    { "id": "QD-S-0.5", "summary": "Detects potential conflicts in body/examples/failure/permission (authenticity confirmed by model)" },
    { "id": "QD-S-0.6", "summary": "No locatable minimal structure (referenceable location / checkable unit)" },
    { "id": "QD-S-0.7", "summary": "Referenced script/template/downstream Skill does not exist or does not parse (credentials/abnormal URL/PII → EX cross-reference)" },
    { "id": "QD-S-0.8", "summary": "version/owner/changelog missing or untraceable" },
    { "id": "QD-S-0.9", "summary": "description exceeds the token budget (SHOULD)" },
    { "id": "QD-S-1.1", "summary": "No input limit keywords detected (max_items/max_chars/limit; true absence confirmed by model)" },
    { "id": "QD-S-1.2", "summary": "No output limit keywords detected (max_total_chars; true absence confirmed by model)" },
    { "id": "QD-S-1.3", "summary": "No execution boundaries detected (max_tool_calls/max_retries/timeout_seconds)" },
    { "id": "QD-S-2.1", "summary": "Unbounded quantifiers all/every/entire/complete detected (whether a cap is paired confirmed by model)" },
    { "id": "QD-S-2.2", "summary": "keep trying/until success/ensure complete/persist until detected (whether termination exists confirmed by model)" },
    { "id": "QD-S-2.3", "summary": "etc./and others/such as detected" },
    { "id": "QD-S-2.4", "summary": "manage/handle/coordinate/automate/process/address detected (whether non_goals are paired confirmed by model)" }
  ]
}
```
<!-- /program-check -->

## 5. Tombstone records

None. The Skill domain source specification contains no merged / transferred items (QD-S-3.2, 3.7 are L1 optional and remain active items, not tombstones).

## 6. Scoring field notes (platform only)

- Source §8 **fixed deductions**: P0=25, P1=15, P2=5 (maintaining 5:3:1, independent of item count). Score = max(100 − total deductions, 0); **the presence of any P0 caps it at 60 and Gate=FAIL**. Same-source deduplication (§11.6): the same root cause / same harm path is recorded only once.
- The denominator is tier-dependent (L1=8 / L2=23 / L3=24); semantic items with ✓ in the `Counted in scoring` column enter the corresponding tier denominator; ✗ (QD-S-0 baseline) and tombstones are not counted.
- skill / CLI do not activate scoring, but score_weight information is retained in the index table for platform use; Gate is an Inspect-local conclusion (not a framework-level release decision).
