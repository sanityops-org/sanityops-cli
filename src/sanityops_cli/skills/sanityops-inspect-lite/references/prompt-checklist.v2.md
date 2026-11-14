---
title: System Prompt Checklist (v2 unified engine edition)
---

# System Prompt Checklist (QD-P, v2)

> **Status**: v2 unified engine edition. Rule semantics derive from `inspect/prompt.md` v1.1 (2026-10): IDs, names, severity values, and merge/transfer/deprecation records all remain unchanged; what changes is the **organization** — full fields + body tables (model items) + program block (program items).
>
> Shared definitions (field model / check_engine mapping / applicability structural-fact gate / severity notation / scoring rules) see [_meta.md](_meta.md); not repeated here. This file carries only the Prompt-domain check items themselves.

## 1. Domain notes

- **L naming**: this domain's severity header uses **AC-L1/AC-L2/AC-L3** (Agent complexity level), not OR-L. System Prompt has no operation-risk dimension.
- **check_engine assignment convention (this domain's reclassification log)** (source has no Method column; mapped by the source "detection nature"):
  - **Part 1 (QD-P-1.x, logic defects, detectable by semantic reading) → `model`**.
  - **Part 2 (QD-P-2.x, completeness/security gaps, requiring an explicit checklist)**: missing-declaration class ("X not declared/missing") → `hybrid` (program pre-screens declaration presence + model confirms sufficiency); pure semantic-quality class → `model`.
- **Conditional items**: QD-P-2.3.4 / 2.3.7 / 2.5.7 / 2.5.9 have no fixed tier severity; triggered → P0 (2.3.7 is P1), not triggered → N/A, **not counted in the static denominator**.
- **Advisory items (ungraded, 6)**: QD-P-1.4.1 / 2.1.3 / 2.1.5 / 2.7.1 / 2.7.2 / 2.7.3, see §6; not scored, not counted, not blocking.
- **primary-defect merging** (source §4.6): when the same fact hits multiple semantically overlapping IDs, record only the primary and mark the rest "related". Overlap groups see source; not re-derived here.

## 2. Check item index (48 items = 44 counted + 4 conditional; plus 6 advisory items + 4 tombstones)

| ID | name | check_engine | applicability.fact | severity AC-L1/L2/L3 | Counted in scoring |
|---|---|---|---|---|---|
| QD-P-1.1.1 | Direct Contradiction | model | is_prompt | P0 / P0 / P0 | ✓ |
| QD-P-1.1.2 | Priority Conflict | model | is_prompt | P1 / P1 / P0 | ✓ |
| QD-P-1.1.3 | Example-Rule Contradiction | model | is_prompt | P0 / P0 / P0 | ✓ |
| QD-P-1.2.1 | Role-Responsibility Mismatch | model | is_prompt | P0 / P0 / P0 | ✓ |
| QD-P-1.2.2 | Role-Output Style Mismatch | model | is_prompt | P1 / P1 / P1 | ✓ |
| QD-P-1.2.3 | Constraint-Responsibility Mismatch | model | is_prompt | P0 / P0 / P0 | ✓ |
| QD-P-1.2.4 | Identity & Anthropomorphism Boundary | model | is_prompt | P1 / P1 / P1→P0(C-end) | ✓ |
| QD-P-1.3.1 | Quantifier Misuse | model | is_prompt | P1 / P1 / P1 | ✓ |
| QD-P-1.3.2 | Vague Qualifiers | model | is_prompt | P1 / P1 / P1 | ✓ |
| QD-P-1.3.3 | Undefined Boundaries | model | is_prompt | P1 / P0 / P0 | ✓ |
| QD-P-1.4.3 | Invalid Skill Definitions | model | has_skill | ∅ / P1 / P0 | ✓ |
| QD-P-1.5.1 | Responsibilities Do Not Support Objective | model | is_prompt | P0 / P0 / P0 | ✓ |
| QD-P-1.5.2 | Resources Do Not Support Workflow | model | has_workflow | ∅ / P0 / P0 | ✓ |
| QD-P-1.6.1 | Critical Decision Word Vagueness | model | is_prompt | P1 / P1 / P1→P0(security) | ✓ |
| QD-P-1.6.2 | Rules Depending on Model Internal State | model | is_prompt | P1 / P1 / P1 | ✓ |
| QD-P-1.6.3 | Soft Rule Interweaving Without Arbitration | model | is_prompt | P1 / P1 / P1→P0(security) | ✓ |
| QD-P-1.6.4 | Reasoning Method Constraints | model | is_prompt | P1 / P1 / P1 | ✓ |
| QD-P-1.6.5 | Self-Referential or Recursive Constraints | model | is_prompt | P1 / P1 / P1 | ✓ |
| QD-P-1.6.6 | Implicit Assumption Dependency | model | is_prompt | P1 / P1 / P1 | ✓ |
| QD-P-1.6.7 | Non-Monotonic Reasoning Defects | model | has_cross_turn_state | P1 / P1 / P1 | ✓ |
| QD-P-1.6.8 | Rule Followability | model | is_prompt | P1 / P1 / P1 | ✓ |
| QD-P-2.1.2 | Reference Clarity | model | has_tool_reference | ∅ / P1 / P1 | ✓ |
| QD-P-2.2.1 | Undeclared Input Source | hybrid | is_prompt | P0 / P0 / P0 | ✓ |
| QD-P-2.2.2 | Unconstrained Input Format | hybrid | has_structured_input | P1 / P0 / P0 | ✓ |
| QD-P-2.2.3 | Required/Optional Not Distinguished | hybrid | has_structured_input | P1 / P0 / P0 | ✓ |
| QD-P-2.2.4 | Undefined Missing-Input Handling | hybrid | is_prompt | P1 / P0 / P0 | ✓ |
| QD-P-2.3.1 | Undefined Output Format | hybrid | has_machine_consumed_output | P1 / P0 / P0 | ✓ |
| QD-P-2.3.2 | Incomplete Output Schema | hybrid | has_structured_output | P1 / P0 / P0 | ✓ |
| QD-P-2.3.4 | Missing Security/Privacy Filtering | model | has_pii | P0 (conditional) | ✗ (conditional) |
| QD-P-2.3.5 | Factuality & Hallucination Control | model | has_retrieval_or_tool | ∅ / P0 / P0 | ✓ |
| QD-P-2.3.6 | Output Length & Truncation | hybrid | is_prompt | P2 / P2 / P2 | ✓ |
| QD-P-2.3.7 | Output Localization & Conventions | model | is_multi_region | P1 (conditional) | ✗ (conditional) |
| QD-P-2.4.1 | Incomplete Workflow Steps | model | has_workflow | ∅ / P1 / P0 | ✓ |
| QD-P-2.4.2 | Undeclared Resources/Tools | hybrid | has_tool_usage | ∅ / P0 / P0 | ✓ |
| QD-P-2.4.3 | Tool Invocation Parameter/Order Error | model | has_tool_invocation | ∅ / P1 / P1 | ✓ |
| QD-P-2.4.4 | Multi-turn Context & Memory Boundary | model | has_multiturn | ∅ / P1 / P1 | ✓ |
| QD-P-2.5.1 | Missing Termination Constraints | model | has_retry_or_loop | ∅ / P1 / P0 | ✓ |
| QD-P-2.5.2 | Missing Security Boundary Constraints | hybrid | is_prompt | P0 / P0 / P0 | ✓ |
| QD-P-2.5.3 | Missing Permission Control Boundaries | hybrid | has_permission_control | ∅ / P1 / P0 | ✓ |
| QD-P-2.5.4 | Undefined Constraint Priority | model | has_conflicting_constraints | ∅ / P1 / P0 | ✓ |
| QD-P-2.5.6 | Instruction-Data Trust Boundary | model | has_external_data | ∅ / P0 / P0 | ✓ |
| QD-P-2.5.7 | High-Risk Operation Human Confirmation | model | has_side_effect_op | P0 (conditional) | ✗ (conditional) |
| QD-P-2.5.8 | System Prompt Confidentiality & Leakage | model | has_confidential_content | ∅ / P1 / P1 | ✓ |
| QD-P-2.5.9 | Industry Compliance & Disclaimer Boundary | model | is_regulated_domain | P0 (conditional) | ✗ (conditional) |
| QD-P-2.6.1 | Runtime Exceptions Not Covered | hybrid | has_tool_usage | ∅ / P1 / P0 | ✓ |
| QD-P-2.6.2 | Missing Degradation & Recovery Strategy | model | is_complex_agent | ∅ / ∅ / P1 | ✓ |
| QD-P-2.6.3 | Unreasonable Retry Mechanism | model | has_retry_or_loop | ∅ / ∅ / P1 | ✓ |
| QD-P-2.6.4 | Out-of-scope Rejection & Human Escalation | model | is_prompt | P1 / P1 / P0 | ✓ |

> Count note: of the 48 rows, 44 items are counted in the static denominator (L1=28 / L2=42 / L3=44, source §3.3.3); the 4 conditional items (2.3.4/2.3.7/2.5.7/2.5.9) are not counted in the fixed denominator. Advisory items see §6, tombstones see §5.

## 3. Model judgment points (condensed definition + model_prompt)

> skill does full-model single-pass reasoning; the CLI's model-item / hybrid-item confirmation phase also reads here. `definition` is taken from source §3.3.2's Severity Variation Notes + minimal-set Definition.

### 3.1 Pure model items (37 items)

| ID | definition (condensed) | model_prompt (judgment points) |
|---|---|---|
| QD-P-1.1.1 | The same object is given mutually exclusive attributes/instructions within the same context | Check whether two attributes/instructions for the same object directly contradict |
| QD-P-1.1.2 | Multiple MUST constraints conflict in a scenario without priority/arbitration | Find the conflicting scenario, and whether priority or arbitration is undefined |
| QD-P-1.1.3 | Body rules contradict the examples | Compare rule definitions with the given examples for conflict |
| QD-P-1.2.1 | Role identity/capability scope does not match the required responsibilities | Judge whether the role identity supports the responsibilities it is asked to bear |
| QD-P-1.2.2 | Role does not match the output style requirements | Mark FAIL only when the style requirement is explicitly incompatible |
| QD-P-1.2.3 | Constraint scope conflicts/mismatches the responsibility behavior scope | Judge whether constraints land on the wrong responsibility scope |
| QD-P-1.2.4 | Impersonating a real person/organization, or missing AI identity disclosure | Judge whether impersonation is allowed, or AI identity disclosure is missing; P0 for C-end users |
| QD-P-1.3.1 | Quantifier misuse creates a logical conflict with another rule | Judge only when quantifier misuse causes a logical conflict ("over-absolute" does not count) |
| QD-P-1.3.2 | Vague wording blurs a critical decision boundary | Judge only when vague wording blurs a critical decision boundary |
| QD-P-1.3.3 | Critical behavior boundaries (authorization / prohibition / handoff) undefined | Judge whether authorization / prohibition / handoff boundaries are missing |
| QD-P-1.4.3 | Defined Skill trigger/usage unclear or conflicting, causing it never to be invoked | Judge whether the Skill definition is clear, triggerable, and conflict-free |
| QD-P-1.5.1 | Defined behaviors cannot achieve the role's overall objective | Judge whether the responsibility set supports the overall objective |
| QD-P-1.5.2 | Workflow steps reference undefined/unauthorized resources | Judge whether resources/tools referenced by the workflow are defined |
| QD-P-1.6.1 | Critical decision wording is vague, and that wording is the decision basis | Judge whether the vague wording serves as the security/permission decision basis (distinct from 1.3.2) |
| QD-P-1.6.2 | Critical decisions rely solely on model self-assessment, with no observable trigger | Judge whether critical decisions uniquely depend on model internal state |
| QD-P-1.6.3 | Soft rules interweave without arbitration | Judge only when a concrete incompatible scenario can be given; security/permission involvement → P0 |
| QD-P-1.6.4 | Unverifiable internal reasoning methods used as compliance assurance | Judge whether unverifiable reasoning methods are used as assurance |
| QD-P-1.6.5 | Self-referential/recursive constraints | Judge only non-terminating / unsatisfiable / cyclic recursion |
| QD-P-1.6.6 | Critical, non-obvious implicit assumptions not guaranteed externally | Judge whether it depends on undeclared critical external assumptions |
| QD-P-1.6.7 | Cross-turn state / already committed conclusions have non-monotonic defects | Judge whether cross-turn state or already committed conclusions are overturned; N/A for a single turn |
| QD-P-1.6.8 | Rules require unreliable model capabilities (counting/timing/arithmetic) | Judge whether rules force unreliable capabilities such as counting/timing/arithmetic |
| QD-P-2.1.2 | Tool/resource references unclear | Judge whether references are ambiguous and unlocatable |
| QD-P-2.3.4 | Sensitive-data redaction / minimal-field output not declared (PII involved) | Judge whether PII is involved and filtering is undeclared |
| QD-P-2.3.5 | Anti-hallucination rules (no fabricated tool results / no citing uncalled tools / no invented references) not declared | Judge whether anti-hallucination declarations are missing (RAG/Tool agent) |
| QD-P-2.3.7 | Multi-region localization/conventions not declared | Judge whether it is multi-region and localization conventions are undeclared |
| QD-P-2.4.1 | Workflow step dependencies/order undefined or references undefined steps | Judge whether workflow steps are complete and dependencies are defined |
| QD-P-2.4.3 | Tool invocation parameters/order written in the body are wrong | Judge whether the parameters/order of tool invocations in the body are written wrong |
| QD-P-2.4.4 | Cross-turn/cross-session context and memory boundaries undefined | Judge whether memory boundaries for multi-turn context are missing |
| QD-P-2.5.1 | Completion/abandon conditions, partial-success reporting, and "must not claim success" steps undefined | Judge whether termination constraints are missing |
| QD-P-2.5.4 | Arbitration rules for potentially conflicting SHOULD constraints undefined | Judge whether constraint priority/arbitration is missing |
| QD-P-2.5.6 | Instruction vs external data trust boundary not declared (injection prevention) | Judge whether the instruction-data trust boundary declaration is missing |
| QD-P-2.5.7 | High-risk/irreversible operations not declared as requiring user confirmation | Judge whether side-effect operations (funds/deletion/sending/production changes) lack confirmation declarations |
| QD-P-2.5.8 | System prompt confidentiality and leakage response not declared | Judge whether the confidentiality/leakage response declaration is missing |
| QD-P-2.5.9 | Industry compliance constraints, disclaimers, and qualification boundaries not declared | Judge whether medical/financial/legal domains lack compliance declarations |
| QD-P-2.6.2 | Degradation and recovery strategy missing ("stop and report" is legitimate) | Judge whether a degradation/recovery strategy exists |
| QD-P-2.6.3 | Unreasonable retry (no cap / blind retry / timeout state not queried) | Judge whether the retry mechanism is reasonable; "stop and report" belongs to 2.6.2, do not double-deduct |
| QD-P-2.6.4 | Rejection templates, referral targets, and escalation conditions undefined | Judge whether out-of-scope rejection / human escalation is missing |

### 3.2 Model-confirmation portion of hybrid items (11 items)

> **On the skill side: this section is the complete set of judgment points; there is no program pre-screening upstream.** "program only checks… / program only does…" describes the CLI / platform pre-screening path; skill reasons with the full model, does not execute §4, must complete the semantic judgment itself, must not treat it as "already screened", and must not use it to mark N/A.

| ID | model_prompt (confirmation points) |
|---|---|
| QD-P-2.2.1 | Confirm whether input source declarations are truly missing (program only checks for missing source keywords such as user/system/external) |
| QD-P-2.2.2 | Confirm whether structured input truly lacks format/encoding/size constraints (program only checks for missing constraint declarations) |
| QD-P-2.2.3 | Confirm whether required/optional is truly undistinguished (program only checks for missing required declarations) |
| QD-P-2.2.4 | Confirm whether missing/abnormal input handling is truly undefined (program only checks for missing handling declarations) |
| QD-P-2.3.1 | Applicable only when output is machine-consumed (free-text chat answers are N/A); confirm whether format/structure/encoding are truly undefined (program only checks for missing format declarations) |
| QD-P-2.3.2 | Confirm whether the output schema truly lacks critical fields (program only checks for missing outputSchema fields) |
| QD-P-2.3.6 | Confirm whether output length/truncation is truly undeclared (program only checks for missing length declarations) |
| QD-P-2.4.2 | Confirm whether resources/tools actually used in the body are truly undeclared (program only compares the reference layer) |
| QD-P-2.5.2 | Confirm whether security boundaries are truly missing (program only checks for missing prohibited-operation/sensitive-access/external-system declarations) |
| QD-P-2.5.3 | Confirm whether permission control boundaries are truly missing (program only checks for missing permission-scope/privilege-escalation/unauthorized-access declarations) |
| QD-P-2.6.1 | Confirm whether runtime exception handling is truly undefined (program only checks for missing exception-handling declarations) |

## 4. Program-judgment items (program-check code block)

> **CLI / platform only: skill does not parse or execute this code block** (skill does full-model reasoning, does not consume `check_engine` or `program_rule`). The program engine only parses this code block. Covers pre-screening rules for hybrid items (declaration presence / field absence). `rule` is a semantic illustration.

<!-- program-check -->
```json
{
  "domain": "prompt",
  "version": "v2",
  "note": "Pre-screening rules for hybrid items (declaration presence / field absence). rule is a semantic illustration.",
  "checks": [
    { "id": "QD-P-2.2.1", "summary": "No input source declaration appears (user/system/external)" },
    { "id": "QD-P-2.2.2", "summary": "Structured input does not declare format/encoding/size limits" },
    { "id": "QD-P-2.2.3", "summary": "Structured input does not distinguish required/optional" },
    { "id": "QD-P-2.2.4", "summary": "Handling of missing/abnormal input not declared" },
    { "id": "QD-P-2.3.1", "summary": "Machine-consumed output does not declare format/structure/encoding (free-text chat N/A)" },
    { "id": "QD-P-2.3.2", "summary": "Structured output lacks critical outputSchema fields" },
    { "id": "QD-P-2.3.6", "summary": "Output length/truncation not declared" },
    { "id": "QD-P-2.4.2", "summary": "Body uses tools/DB/API but does not declare them (compared with reference layer)" },
    { "id": "QD-P-2.5.2", "summary": "Security boundary not declared (prohibited operations/sensitive access/external systems)" },
    { "id": "QD-P-2.5.3", "summary": "Permission scope/privilege-escalation conditions/unauthorized-access handling not declared" },
    { "id": "QD-P-2.6.1", "summary": "Runtime exception handling not declared" }
  ]
}
```
<!-- /program-check -->

## 5. Tombstone records (deprecated / merged / transferred)

| ID | name | Status | Points to |
|---|---|---|---|
| QD-P-2.1.1 | (injection point) | deleted | Injection point merged into QD-P-2.5.6 |
| QD-P-2.1.4 | (redundant constraints) | merged | → QD-P-1.4.1 (advisory item) |
| QD-P-2.5.5 | Resource-Call Frequency Limit | deprecated | Frequency/batch expectations carried by cross QD-PT-2.6 / QD-ST-3.4 |
| QD-P-2.3.3 | (numbering gap) | gap | No status note; numbering gap only |

## 6. Advisory items (ungraded, 6)

> Optimization value only: not scored, not counted in the denominator, not blocking, no waiver. applicability is always `is_prompt`.

| ID | name | Description |
|---|---|---|
| QD-P-1.4.1 | Redundant Constraints | Redundant constraints (absorbs 2.1.4) |
| QD-P-2.1.3 | Structural Hierarchy | Structural hierarchy clarity |
| QD-P-2.1.5 | Context Budget Squeeze | Context budget squeeze |
| QD-P-2.7.1 | Positive-Example Representativeness | Positive-example representativeness |
| QD-P-2.7.2 | Counter-Example Coverage | Counter-example coverage |
| QD-P-2.7.3 | Boundary-Case Examples | Boundary-case coverage |

## 7. Scoring field notes (platform only)

- Global weights (`_meta.md`): P0 : P1 : P2 = 5 : 3 : 1, deducted once at the item's highest severity.
- Denominator: 44 items counted (L1=28 / L2=42 / L3=44); 4 conditional items, 6 advisory items, and tombstones are not counted.
- skill / CLI do not activate scoring; `score_weight` information is retained in the index table's "Counted in scoring" column for platform.
