---
title: Cross-Artifact Consistency Checklist (v2 unified engine edition)
---

# Cross-Artifact Consistency Checklist (QD-PS/PT/ST/SS/TT/CYC, v2)

> **Status**: v2 unified engine edition. Rule semantics originate from `inspect/cross.md` v1.1: IDs, names, default severities, AC-L applicability, OR-L3/instance escalation, and dedup groups all remain unchanged; what changes is the **organization** — all fields + body tables (model items) + program blocks (program items).
>
> Shared definitions (field model / check_engine mapping / applicability structural-fact gate / severity notation / scoring rules) are in [_meta.md](_meta.md); this file does not repeat them. This file only carries the Cross domain check items themselves.

## 1. Domain notes

- **Dual L dimension**: severity in this domain is determined jointly by **AC-L** (decides the default P value) and **OR-L** (escalation: OR-L3 → P0/P1). Which items apply is decided by `applicability.fact`, **not by AC-L** (the L1=7 / L2=20 / L3=29 ranges in the original tier-scoped specification are for historical reference only and no longer decide whether a check runs). The severity column in the index table shows **the default values for AC-L1/L2/L3** (`∅` = the original specification assigns no P under that L, shown for reference only); OR-L3 escalation and instance escalation are in the table below.
- **Non-blocking mode** (source §How to Use): an upstream single-artifact P0 does not block execution of this checklist; aggregate P0s rather than halt. Before starting, confirm that Prompt/Skill/Tool version numbers, timestamps, and provenance are consistent; if inconsistent, ask the user first.
- **Only cross-artifact relationships are checked** (six groups: QD-PS / QD-PT / QD-ST / QD-SS / QD-TT / QD-CYC); single-artifact internal defects of QD-P/QS/QD-T are not re-checked.
- **Each item's evidence must cite positions in both artifacts** (three-level location: relationship→artifact→field).
- **N/A discipline**: N/A must state a basis (e.g., "no Tool Schema", "Agent has only 1 Skill"); a basis-less N/A is treated as not checked and counted as a failure at the default level.
- **check_engine assignment convention (reclassification log for this domain)**: cross-artifact consistency is essentially semantic reasoning → the vast majority are `model`; existence/uniqueness/competition (2.1, 3.1, 4.2, 5.2) have a program pre-screen (name matching) → `hybrid`. This domain has **no pure program items**.

**OR-L3 escalation table (source Appendix C.2, cross items)**:

| Escalation | Items |
|---|---|
| P1 → P0 | QD-PS-1.2, 1.4, 1.5, 1.7 · QD-PT-2.3, 2.7 · QD-ST-3.5 · QD-SS-4.1 · QD-TT-5.1, 5.2 · QD-CYC-1.1, 1.2, 1.3 |
| P2 → P1 (→P0 when it would mistakenly trigger an OR-L3 Skill) | QD-SS-4.2 |
| No escalation (P1 stays) | QD-PT-2.5, QD-ST-3.7 |
| P2 with no OR-L3 escalation (stays P2) | QD-PS-1.6, QD-PT-2.6, QD-ST-3.4, QD-TT-5.3 |

**Instance escalation (`→P0` branches in the rule bodies)**: QD-CYC confirmed closed loop → P0; QD-TT-5.1 sensitive output plus dangerous consumption coexist → P0; QD-TT-5.2 large behavioral difference → P0; QD-SS-4.1 involves an OR-L3 Skill → P0.

## 2. Check item index (29 items, six groups)

| ID | name | check_engine | applicability.fact | severity AC-L1/L2/L3 | Counted in scoring |
|---|---|---|---|---|---|
| QD-PS-1.1 | Skill Authorization Consistency | model | has_skill_reference | P0 / P0 / P0 | ✓ |
| QD-PS-1.2 | Trigger Condition Consistency | model | has_prompt_and_skill | ∅ / P1 / P1 | ✓ |
| QD-PS-1.3 | Permission Boundary Consistency | model | has_prompt_and_skill | P0 / P0 / P0 | ✓ |
| QD-PS-1.4 | Resource Access Consistency | model | has_prompt_and_skill | ∅ / P1 / P1 | ✓ |
| QD-PS-1.5 | Failure Handling Consistency | model | has_prompt_and_skill | ∅ / ∅ / P1 | ✓ |
| QD-PS-1.6 | Output Constraint Consistency | model | has_prompt_and_skill | ∅ / ∅ / P2 | ✓ |
| QD-PS-1.7 | Orchestration Order & Precondition Consistency | model | has_prompt_and_skill | ∅ / P1 / P1 | ✓ |
| QD-PT-2.1 | Tool Existence | hybrid | has_tool_reference | P0 / P0 / P0 | ✓ |
| QD-PT-2.2 | Invocation Specification Consistency | model | has_prompt_and_tool | P0 / P0 / P0 | ✓ |
| QD-PT-2.3 | Parameter Constraint Consistency | model | has_prompt_and_tool | ∅ / P1 / P1 | ✓ |
| QD-PT-2.4 | Permission Granularity Consistency | model | has_prompt_and_tool | P0 / P0 / P0 | ✓ |
| QD-PT-2.5 | Key Error Handling Coverage | model | has_prompt_and_tool | ∅ / ∅ / P1 | ✓ |
| QD-PT-2.6 | Business-Level Frequency Expectation | model | has_prompt_and_tool | ∅ / ∅ / P2 | ✓ |
| QD-PT-2.7 | Parameter Semantics & Unit Consistency | model | has_prompt_and_tool | ∅ / P1 / P1 | ✓ |
| QD-ST-3.1 | Tool Existence | hybrid | has_tool_reference | P0 / P0 / P0 | ✓ |
| QD-ST-3.2 | Input Constraint Consistency | model | has_skill_and_tool | ∅ / P0 / P0 | ✓ |
| QD-ST-3.3 | Required Parameter Preparation | model | has_skill_and_tool | ∅ / P0 / P0 | ✓ |
| QD-ST-3.4 | Business-Level Frequency Expectation | model | has_skill_and_tool | ∅ / ∅ / P2 | ✓ |
| QD-ST-3.5 | Output Structure Match | model | has_skill_and_tool | ∅ / ∅ / P1 | ✓ |
| QD-ST-3.6 | Permission Scope Match | model | has_skill_and_tool | P0 / P0 / P0 | ✓ |
| QD-ST-3.7 | Key Error Handling Coverage | model | has_skill_and_tool | ∅ / ∅ / P1 | ✓ |
| QD-CYC-1.1 | Cross-Artifact Circular Invocation | model | has_invocation_graph | ∅ / P1 / P1 | ✓ |
| QD-CYC-1.2 | Multi-Agent Circular Invocation | model | has_multi_agent | ∅ / ∅ / P1 | ✓ |
| QD-CYC-1.3 | Inter-Skill Handoff Loop | model | has_skill_handoff | ∅ / P1 / P1 | ✓ |
| QD-SS-4.1 | Trigger Condition Conflict | model | has_multiple_skills | ∅ / P1 / P1 | ✓ |
| QD-SS-4.2 | Name Uniqueness | hybrid | has_multiple_skills | ∅ / P2 / P2 | ✓ |
| QD-TT-5.1 | Cross-Tool Data Flow | model | has_multiple_tools | ∅ / P1 / P1 | ✓ |
| QD-TT-5.2 | Multi-Tool Semantic Competition | hybrid | has_multiple_tools | ∅ / P1 / P1 | ✓ |
| QD-TT-5.3 | Cross-Tool Data Structure Bridging | model | has_multiple_tools | ∅ / ∅ / P2 | ✓ |

> Count note: 29 items = QD-PS(7) + QD-PT(7) + QD-ST(7) + QD-CYC(3) + QD-SS(2) + QD-TT(3). severity is the default for the three AC-L tiers (L1=7 items all P0 / L2=20 / L3=29); `∅` = the original specification assigns no P under that L (shown for reference only). `has_*` are structural relationship facts (whether that relationship exists between artifacts), not "whether it has been declared consistent" (point-1-paradox prevention). QD-CYC-1.2 applies only when the Prompt orchestration declares ≥2 Agent roles; otherwise N/A.

> **applicability exception for existence checks (application of point-1-paradox prevention to cross-artifact existence checks)**: QD-PS-1.1 / QD-PT-2.1 / QD-ST-3.1 check "whether the declared X actually exists"; their applicability uses a **reference fact** rather than the relationship fact "both exist" — `has_skill_reference` (the Prompt declares a Skill name, including IR reference layer entries), `has_tool_reference` (the Prompt/Skill declares a Tool name, including IR reference layer entries). This way, when the referenced object is missing ("referenced but missing") the check still runs and hits, instead of self-locking to N/A because `has_prompt_and_tool` etc. is false.

## 3. Model judgment points (definition condensed + model_prompt)

### 3.1 Pure model items (25 items)

| ID | definition (condensed) | model_prompt (judgment points) |
|---|---|---|
| QD-PS-1.1 | Skills declared by the Prompt match the defined Skills (outside the authorized scope) | Compare the Skill list declared by the Prompt with the defined Skills; judge whether there is unauthorized access / a missing declaration |
| QD-PS-1.2 | The Prompt workflow trigger conditions match the Skill's allowed_when/forbidden_when | Compare Prompt triggering with the Skill TRIGGER dimensions |
| QD-PS-1.3 | The Prompt authorization permissions cover the Skill's allowed_operations | Judge whether Prompt permissions cover the operations the Skill allows |
| QD-PS-1.4 | Resources declared by the Prompt align with the Skill's allowed_resources | Compare resource declarations |
| QD-PS-1.5 | Prompt exception handling aligns with the Skill FAILURE dimensions | Compare on_empty/on_insufficient/forbidden_behaviors |
| QD-PS-1.6 | Prompt output requirements are satisfied by the Skill OUTPUT dimensions | Compare max_total_chars/format/partial_result_allowed |
| QD-PS-1.7 | Prerequisites declared by the Skill are satisfied by the preceding Prompt step | Judge whether prerequisites are satisfied before invocation |
| QD-PT-2.2 | The Prompt's tool invocation specification matches the Tool Schema (name/description/inputSchema) | Compare the invocation specification with the schema |
| QD-PT-2.3 | Prompt parameter constraints align with Tool inputSchema (required/properties/maxLength/pattern) | Compare parameter constraints |
| QD-PT-2.4 | Prompt permission declarations match the Tool risk level (OR-L3 needs a security boundary) | Judge whether a high-risk Tool has a Prompt security boundary declaration |
| QD-PT-2.5 | Prompt exception handling covers all critical error types of the Tool | Judge error type coverage |
| QD-PT-2.6 | The Prompt declares a reasonable business-level invocation frequency/batch expectation | Judge the reasonableness of the frequency/batch expectation |
| QD-PT-2.7 | Prompt parameter semantics/units (name/unit/currency/timezone) match inputSchema | Compare semantics and units |
| QD-ST-3.2 | Skill INPUT constraints are supported by Tool inputSchema (maxLength/pattern/maxItems) | Compare input constraint supportability |
| QD-ST-3.3 | The Tool's required parameters have a source declaration in the Skill (user input or another tool's output) | Judge whether required parameters have a source |
| QD-ST-3.4 | Skill invocation frequency/batch expectation is reasonable given the Tool's capability combination | Judge frequency reasonableness |
| QD-ST-3.5 | Skill OUTPUT expectations match the Tool return structure | Compare output structures |
| QD-ST-3.6 | Skill permission declarations cover the Tool's side effects (writes/sensitive data) | Judge whether permissions cover side effects |
| QD-ST-3.7 | Skill FAILURE dimensions cover all critical error types of the Tool | Judge error coverage |
| QD-CYC-1.1 | Prompt/Skill/Tool invocation relationships form a closed loop | Judge whether a cross-artifact invocation cycle exists; a confirmed closed loop → P0 |
| QD-CYC-1.2 | Multiple Agent roles form a closed loop among themselves | Judge the Agent-to-Agent closed loop (only with ≥2 Agent roles) |
| QD-CYC-1.3 | Multiple Skills reference each other via handoff forming a non-terminating loop | Judge the Skill-to-Skill handoff cycle |
| QD-SS-4.1 | Multiple Skill triggers overlap so that the same input activates multiple Skills | Judge trigger conflict |
| QD-TT-5.1 | One Tool's sensitive output is used by another Tool for a dangerous operation, forming a data leakage chain | Judge the sensitive-output plus dangerous-consumption chain; coexistence → P0 |
| QD-TT-5.3 | One Tool's output/input types are incompatible and the Skill has no conversion step | Judge the missing type bridging |

### 3.2 Model-confirmation portion of hybrid items

> **Skill side: this section is the complete judgment points, with no program pre-screening upstream.** "The program only does..." describes the CLI / platform pre-screen path; the skill performs full model reasoning, does not execute §4, must complete the semantic judgment itself, and must not treat it as "already screened" nor judge N/A on that basis.

| ID | model_prompt (confirmation points) |
|---|---|
| QD-PT-2.1 | Confirm whether the Tool name declared by the Prompt really exists in the known Tool Schema list and is semantically consistent (the program only does name matching) |
| QD-ST-3.1 | Confirm whether the Tool name declared by the Skill really exists in the known Tool Schema list and is semantically consistent |
| QD-SS-4.2 | Confirm whether identical/similar names really cause misinvocation (the program only does name similarity) |
| QD-TT-5.2 | Confirm whether similar name/description really causes misinvocation (the program only does name/description similarity) |

## 4. Program-judgment items (program-check code block)

> **CLI / platform only: the skill does not parse or execute this code block** (the skill performs full model reasoning and does not consume `check_engine` or `program_rule`). The program engine only parses this code block. The `rule` field is a **semantic illustration of judgment**. This domain has pre-screen rules only for hybrid items; there are no pure program items.

<!-- program-check -->
```json
{
  "domain": "cross",
  "version": "v2",
  "note": "Pre-screen rules for hybrid items. rule is illustrative semantics.",
  "checks": [
    { "id": "QD-PT-2.1", "summary": "The Tool name declared by the Prompt matches a name in the known Tool Schema list (semantic consistency confirmed by the model)" },
    { "id": "QD-ST-3.1", "summary": "The Tool name declared by the Skill matches a name in the known Tool Schema list (semantic consistency confirmed by the model)" },
    { "id": "QD-SS-4.2", "summary": "Multiple Skill names identical or similar (misinvocation risk confirmed by the model)" },
    { "id": "QD-TT-5.2", "summary": "Multiple Tool name/description similar (misinvocation risk confirmed by the model)" }
  ]
}
```
<!-- /program-check -->

## 5. Tombstone records

None. The Cross domain source specification contains no merged / transferred items.

## 6. Scoring field notes (platform only)

- Weight `P0:P1:P2 = 5:3:1`; base = 100 / total weight; each failed item deducts base×5/3/1 at the default level (once per item, regardless of instance count).
- The denominator is tier-dependent (AC-L1=7 / L2=20 / L3=29); the `Counted in scoring` column is ✓ for all.
- Same-source deduplication (source §8.5.2): when the same fact hits multiple IDs in the same group, record it once at the highest level, retain all IDs and evidence, and mark the primary; the denominator is unchanged. Dedup groups: Tool existence (PT-2.1↔ST-3.1), permission boundary (PS-1.3↔1.4↔ST-3.6), parameter constraints (PT-2.3↔ST-3.2), output contract (PS-1.6↔ST-3.5, primary ST-3.5), error handling (PT-2.5↔ST-3.7). PT-2.7 has no Skill-side counterpart and is not deduplicated.
- skill / CLI do not activate scoring, but the score_weight information is retained in the index table for platform use.
