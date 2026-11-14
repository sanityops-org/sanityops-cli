---
title: Tool Schema Checklist (v2 unified engine edition)
---

# Tool Schema Checklist (QD-T, v2)

> **Status**: v2 unified engine edition.
>
> The rule semantics originate from `inspect/tool.md` v1.1: IDs, names, severity values, and merge/transfer records all remain unchanged; what changes is the **organization** — switched to "all fields + body tables (model items) + program blocks (program items)".
>
> Global judgment conventions (a missing declaration is a defect, N/A must carry a basis, fail-safe defaults apply — when in doubt, check, program items are enumerated in full) are in `_meta.md`. This file does not repeat them.

## 1. Domain notes

> Shared definitions (field model / check_engine mapping / applicability structural-fact gate / severity notation / scoring rules) are in [_meta.md](_meta.md); this file does not repeat them. This file only carries the Tool domain check items themselves.

**`check_engine` reclassification log** (relative to the source `Method` column): baseline mapping `Automated→program`, `Human→model`, `Semi-automated→hybrid`; the following 4 deviations from the source Method are driven by contradictions between the source Method column and its own definitions, corrected per design §2.8 "prioritize convergence":

- `QD-T-1.4`: source marked Automated, but the definition is a "policy appropriateness **judgment**" → hybrid
- `QD-T-4.1`: source marked Semi-automated, but purely semantic (missing ≥2 elements) → model
- `QD-T-4.6`: source marked Semi-automated, but purely semantic ("whether sensitive") → model
- `QD-T-5.2`: source marked Semi-automated, but purely semantic (impact assessment missing/contradictory) → model

## 2. Check item index (28 active items + 3 tombstones)

| ID | name | check_engine | applicability.fact | severity OR-L1/OR-L2/OR-L3 | Counted in scoring |
|---|---|---|---|---|---|
| QD-T-1.1 | Base Field Missing | program | is_tool_schema | P0 / P0 / P0 | ✓ |
| QD-T-1.2 | Required References Undefined Field | hybrid | has_required | P0 / P0 / P0 | ✓ |
| QD-T-1.3 | Enum type conflict / duplicate values | program | has_enum | P1·P2 / P1·P2 / P1·P2 | ✓ |
| QD-T-1.4 | additionalProperties Policy Inappropriate | hybrid | has_properties | P2 / P1 / P1 | ✓ |
| QD-T-1.5 | name Validity & Uniqueness | program | has_name | P0(style P2) | ✓ |
| QD-T-1.6 | Constraint Self-Consistency & default | program | has_constraint | P1 / P1 / P1→P0(high-risk) | ✓ |
| QD-T-1.7 | Type Missing / Over-Broad / Complexity | program | has_schema | P2 / P1 / P1 | ✓ |
| QD-T-2.1 | String Without maxLength | program | has_string_param | P2 / P1 / P1→P0(executable) | ✓ |
| QD-T-2.2 | Format Contract Missing | hybrid | has_string_param | P2 / P1 / P1 | ✓ |
| QD-T-2.3 | Number/Integer Without Boundary | program | has_number_param | P2 / P1 / P1→P0(amount) | ✓ |
| QD-T-2.4 | Array Without maxItems | program | has_array_param | P2 / P1 / P1 | ✓ |
| QD-T-2.5 | Unit / Precision / Timezone / Currency Missing | hybrid | has_amount_or_time_param | P2 / P1 / P0 | ✓ |
| QD-T-2.6 | Query Tool Without Pagination / Result Cap | program | is_query_tool | P1 / P1 / P1 | ✓ |
| QD-T-2.7 | Parameter Dependency / Mutual Exclusion Unexpressed | hybrid | has_param_dependency | P1 / P1 / P1 | ✓ |
| QD-T-3.1 | State Change & Material Side Effect Undeclared | model | has_write_semantics | ∅ / P1 / P0 | ✓ |
| QD-T-3.2 | Untrusted Input into Executable Context | hybrid | has_executable_param | P1 / P0 / P0 | ✓ |
| QD-T-3.3 | Batch / Range Write Without Cap | hybrid | has_batch_write | ∅ / P1 / P0 | ✓ |
| QD-T-3.4 | Authorization Context Parameter Exposure | model | has_authz_param | P0 / P0 / P0 | ✓ |
| QD-T-3.6 | Dangerous Default / Scope Precondition | hybrid | has_dangerous_default | ∅ / P1 / P0 | ✓ |
| QD-T-3.7 | Parameterized-Tool Operation Whitelist Undeclared | hybrid | is_openended_tool | P0 / P0 / P0 | ✓ |
| QD-T-4.1 | Insufficient Description Quality | model | has_description | P2 / P1 / P1 | ✓ |
| QD-T-4.4 | Parameter-Level description Missing | program | has_properties | P2 / P1 / P1 | ✓ |
| QD-T-4.5 | description Inconsistent with Schema | hybrid | has_description | P1 / P1 / P1 | ✓ |
| QD-T-4.6 | Sensitive Input Handling Undeclared | model | has_sensitive_param | ∅ / P1 / P1 | ✓ |
| QD-T-4.7 | Output Contract Missing (outputSchema) | hybrid | has_output | ∅ / P1 / P1→P0(cross-flow) | ✓ |
| QD-T-5.1 | Breaking Change Determination | hybrid | has_version_change | §4.3.1 matrix | ✗ (change-check) |
| QD-T-5.2 | Change Impact Assessment Missing/Wrong | model | has_change_note | P1 / P1 / P0 | ✗ (change-check) |
| QD-T-5.3 | Semantic Change | hybrid | has_version_change | P1 / P1 / P0 | ✗ (change-check) |

> **5.x note**: QD-T-5.x belongs to Schema change management, triggered only when an old/new Schema comparison object exists, and is **not counted in the static check denominator** (source specification §5.2.1). See §5 for tombstones.

## 3. Model-reasoning items (body tables)

> The following are the items with `check_engine = model` (5 items). The "model-confirmation points" of hybrid items are also listed here (see §3.2).

### 3.1 Pure model items

| ID | definition (condensed) | model_prompt (judgment points) |
|---|---|---|
| QD-T-3.1 | The name/description reads as read-only, but writes/side effects are actually present and undeclared; or the side effect (irreversible/external/financial) is not declared at all | Determine whether the tool name reads as read-only (verify/query/get) while the body has write semantics; or the write semantics match the name but irreversibility is undeclared |
| QD-T-3.4 | Exposes parameters that should be controlled by the system (tenantId / admin / token) | Determine whether an authorization context parameter exists and whether the caller can fill it freely |
| QD-T-4.1 | The description lacks required elements (action, object, scope/timeliness, key parameter semantics, return summary), and ≥2 are missing | Check element by element whether the description covers the five elements; judge FAIL if ≥2 are missing |
| QD-T-4.6 | Sensitive inputs such as passwords/keys/ID numbers are not declared as writeOnly / encrypted / not logged | Determine whether the parameter is sensitive and whether sensitive handling is undeclared |
| QD-T-5.2 | The change note does not declare caller/data/system impact, or the declaration contradicts the facts | Compare the change note with the schema diff and judge whether the impact declaration is missing or contradictory |

### 3.2 Model-confirmation portion of hybrid items

> **Skill side: this section is the complete judgment points, with no program pre-screening upstream.** "Program only checks... / program only does..." describes the CLI / platform pre-screen path; the skill performs full model reasoning, does not execute §4, must complete the semantic judgment itself, and must not treat it as "already screened" nor judge N/A on that basis.

| ID | model_prompt (confirmation points) |
|---|---|
| QD-T-1.2 | Confirm whether a field in required should not exist in the first place / violates the business contract (source P1 sub-item: field necessity, P1 at all levels) |
| QD-T-1.4 | Confirm whether the additionalProperties policy is appropriate: closed-contract fields should be false, tags/metadata open dictionaries may omit it |
| QD-T-2.2 | Confirm whether the string needs a specific format (e.g., date, URL, encoding) and therefore needs a pattern |
| QD-T-2.5 | Confirm whether the parameter is an amount/time/currency/ratio and thus needs unit/currency/precision/timezone |
| QD-T-2.7 | Confirm whether the parameters have paired-required/mutually-exclusive/conditionally-required/at-least-one relationships |
| QD-T-3.2 | Confirm whether it is already parameterized / has a whitelist / has a sandbox, and thus can be exempted |
| QD-T-3.3 | Confirm whether batch writes have a cap (maxItems, pagination, rejecting empty filters) |
| QD-T-3.6 | Confirm whether default/scope is a dangerous value (force=true, dry_run=false, scope=ALL) |
| QD-T-3.7 | Confirm whether an open-ended tool (sql/exec/http/eval) declares an operation whitelist (table/command/domain) |
| QD-T-4.5 | Confirm whether the description statements and schema constraints are semantically consistent (e.g., "max 10" vs schema allowing 100) |
| QD-T-4.7 | Confirm whether the missing outputSchema should be escalated to P0 in cross-tool data flow scenarios |
| QD-T-5.1 | Confirm whether the old/new schema differences break existing calls (breaking) |
| QD-T-5.3 | Confirm whether semantics changed despite unchanged structure (name/default/unit/scope/side-effect) |

## 4. Program-judgment items (program-check code block)

> **CLI / platform only: the skill does not parse or execute this code block** (the skill performs full model reasoning and does not consume `check_engine` or `program_rule`). The program engine only parses this code block. The `rule` field is a **semantic illustration of judgment** (not the final executable definition; program-level implementation to be added later).
> Covers pure program items + the pre-screen rules for hybrid items.

<!-- program-check -->
```json
{
  "domain": "tool",
  "version": "v2-sample",
  "note": "Program-judgment items + hybrid pre-screen rules. rule is illustrative semantics.",
  "checks": [
    { "id": "QD-T-1.1", "summary": "One of name / description / inputSchema is missing at the top level" },
    { "id": "QD-T-1.2", "summary": "required references a field not defined in properties" },
    { "id": "QD-T-1.3", "summary": "Duplicate enum values, or enum value conflicts with the declared type" },
    { "id": "QD-T-1.4", "summary": "Detects the additionalProperties setting (policy appropriateness confirmed by the model)" },
    { "id": "QD-T-1.5", "summary": "name does not match ^[a-zA-Z0-9_-]{1,64}$ or is not unique" },
    { "id": "QD-T-1.6", "summary": "minimum>maximum / minLength>maxLength / minItems>maxItems / default violates constraint" },
    { "id": "QD-T-1.7", "summary": "Missing type / multi-type array / nesting >4 / params >30 / oneOf misuse" },
    { "id": "QD-T-2.1", "summary": "string parameter missing maxLength (enum/const/pattern fixed-length exempt)" },
    { "id": "QD-T-2.2", "summary": "string requiring a specific format missing pattern (whether a format is needed confirmed by the model)" },
    { "id": "QD-T-2.3", "summary": "number/integer missing minimum/maximum" },
    { "id": "QD-T-2.4", "summary": "array parameter missing maxItems" },
    { "id": "QD-T-2.5", "summary": "amount/time type number missing multipleOf or unit (semantics confirmed by the model)" },
    { "id": "QD-T-2.6", "summary": "list_*/search_* tool missing limit/page_size, or limit missing maximum" },
    { "id": "QD-T-2.7", "summary": "dependency/mutual exclusion not expressed via dependentRequired/oneOf (semantics confirmed by the model)" },
    { "id": "QD-T-3.2", "summary": "parameter matches SQL/shell/code/template/URL/path executable characteristics (exemption confirmed by the model)" },
    { "id": "QD-T-3.3", "summary": "batch write parameters (ids/filter conditions) without a cap (whether a cap exists confirmed by the model)" },
    { "id": "QD-T-3.6", "summary": "default matches force=true / dry_run=false / scope=ALL (dangerousness confirmed by the model)" },
    { "id": "QD-T-3.7", "summary": "open-ended tool (sql_query/exec/http_request/eval) missing operation whitelist" },
    { "id": "QD-T-4.4", "summary": "property missing description" },
    { "id": "QD-T-4.5", "summary": "description literal inconsistent with schema constraint (semantics confirmed by the model)" },
    { "id": "QD-T-4.7", "summary": "missing outputSchema (cross-flow escalation confirmed by the model)" },
    { "id": "QD-T-5.1", "summary": "old/new schema has breaking differences (whether breaking confirmed by the model)" },
    { "id": "QD-T-5.3", "summary": "name/default/unit/scope changed (whether a semantic change confirmed by the model)" }
  ]
}
```
<!-- /program-check -->

## 5. Tombstone record (merged / transferred, not part of judgment)

| ID | name | Status | Points to |
|---|---|---|---|
| QD-T-4.2 | Side Effect Undeclared | merged | → QD-T-3.1 (numbering retained, no longer used independently) |
| QD-T-3.5 | Cross-Tool Data Flow | transferred | → cross QD-TT-5.1 (P2 lead retained) |
| QD-T-4.3 | Multi-Tool Semantic Competition | transferred | → cross QD-TT-5.2 (P2 lead retained) |

## 6. Scoring field notes (platform only)

- Global weight rule (`_meta.md`): `P0 : P1 : P2 = 5 : 3 : 1`, deducted once at the item's highest severity.
- Items with `✓` in the `Counted in scoring` column enter the static denominator (20/25/25); `✗` (5.x change-check) and tombstones are not counted.
- skill / CLI do not activate scoring, but the `score_weight` information is retained in the index table's "Counted in scoring" column for platform use.

