---
title: Relevance Map (v2 unified engine edition)
---

# Relevance Map (Stage F Impact Outlook, v2)

> **Status**: v2 unified engine edition. This file is a **mapping (lookup) document, not a rule checklist**: no new check items, no `check_engine`, no `applicability.fact`, no per-item `severity` (`strength` ≠ `severity`). Rule semantics derive from `framework/relevance.md` v1.1; the mapping direction / attack surfaces / candidate failure modes / validation recommendations all remain unchanged.
>
> Shared definitions see [_meta.md](_meta.md). This file is used at Stage F (impact outlook): for each **FAIL** already produced by Stage A/B/D, look up the QD ID and output candidate Impact Cards. This file **consumes** the unified QD IDs of each v2 checklist (single source of truth = the v2 check items of prompt/skill/tool/cross/permission), and does not define new IDs.

## 1. Domain notes

- **Nature**: L2 cross-domain mapping document, subordinate to the nine L1 sub-specifications. In any conflict (numbering/definition/severity/release requirement) **the source sub-specification prevails** (relevance.md §0.3.1). Mapping strength / attack surface / candidate failure mode do not change the original judgment of the source sub-specification.
- **Map only defects that actually FAIL**: pre-mapping, speculative mapping, and mapping of already fixed/PASS items are prohibited.
- **Candidate language red line**: each output line must be a "candidate association" — use "may / candidate association / needs dynamic verification"; causal assertions "will cause / guarantees / ensures / inevitably / proves" are forbidden (correlation ≠ causation, relevance.md §0.4-1).
- **strength ≠ severity** (§1.3): Strength describes only "association confidence / test priority", never replaces P0/P1/P2; the two are explicitly separate columns.
- **No check_engine / applicability.fact / per-item severity**: this domain is a lookup table, the row key is the QD ID (source anchor), the columns are AS/Impact/Strength/Validation metadata. The `Applies` column retains the source specification scope (AC-L/OR-L), not a unified applicability structural fact.
- **Explicitly record "not run"**: each impact area must declare that the Risk Implicit and runtime Quality subsets are **not run** (dynamic exploitability not verified), and per §1.4 must not assume compensating controls outside the artifact are missing; Risk Explicit is not reclassified in this outlook (already run in Stage E, Stage F only does candidate mapping).
- **Automatic inference of EX is forbidden** (§2.3.1): `QD-P-2.5.2` ≠ automatic hit of `NL-A-7`; `QD-T-1.4` ≠ `NR-S-3`; `QD-PS-1.3` ≠ `NL-B-9`. EX codes are judged only independently by Risk Explicit in Stage E.
- **Defect chain out of lite scope** (§1.5): only single-defect candidate mapping is supported; no defect chains are constructed/asserted/reported (SC-*/QC-TA-*/QC-RA-*).
- **Physical separation**: the impact outlook is separated from Gate/verdict conclusions, is advisory context, and must not change/soften/upgrade any Inspect conclusion.

## 2. Mapping strength (strength, not severity, §1.3)

| Strength | Meaning (verbatim) | Framework-wide platform behavior |
|---|---|---|
| Strong | The defect directly expands the attack entry point, or is highly likely to cause the specified failure mode | Automatically recommends related Risk/Quality test cases |
| Medium | May have impact under specific permission/data/Tool/process conditions | Recommend per applicable conditions |
| Conditional | Requires external knowledge base/runtime environment/model behavior/business rules | As a candidate investigation direction, no automatic conclusion |
| Not Applicable | The current Agent type/artifact type/runtime conditions lack the prerequisite for association | Do not output this recommendation |

> lite convention: the source Appendix A already has per-row strength; the table below copies it verbatim. When outputting an Impact Card, copy that row's strength and mark "provisional (lite)".

## 3. Attack surface legend (AS-*, §2.2)

| ID | Attack surface | Definition |
|---|---|---|
| AS-01 | Instruction and Context Boundary Confusion | Mistaking untrusted input/documents/history/external returns as high-priority instructions |
| AS-02 | Input and Parameter Injection | Unconstrained user/external input enters Tool/backend/downstream interpreter |
| AS-03 | Output Handling and Sensitive Data Exfiltration | Sensitive information is output/concatenated/referenced/forwarded/written externally |
| AS-04 | Permission, Identity, and Delegation Expansion | Broad capability/incorrect authorization/chained invocation leads to out-of-scope operations |
| AS-05 | Tool Misuse and High-Risk Side Effects | Wrong Tool selection/accidental write/batch operations/unconfirmed irreversible actions |
| AS-06 | Resource Exhaustion and Runaway Execution | Unbounded input/output/invocation/retry/recursion leads to runaway resources |
| AS-07 | Anomaly Propagation and Cascading Failures | After Tool/dependency failure the Agent escalates, retries, or degrades in undefined ways |
| AS-08 | Configuration, Naming, and Supply Chain Confusion | Similar Tool names/Schema change/dangerous default values/abnormal callback addresses |
| AS-09 | Cross-Artifact Contract Breach | Inconsistency of authorization/parameters/output/permissions/error policy among Prompt/Skill/Tool |

> Impact dimension codes: `D1`=confidentiality damage, `D2`=integrity damage, `D3`=authorization damage (§0.5). "Availability/Auditability/Integrity" are ordinary words in the source table.

## 4. Defect→impact mapping table (source Appendix A)

### A.1 Prompt (QD-P-*)

| QD ID | Name | Applies | AS | Impact | Strength |
|---|---|---|---|---|---|
| QD-P-1.1.1 | Direct Contradiction | AC-L1~3 | AS-01, AS-05 | D2, D3 | Strong |
| QD-P-1.1.2 | Priority Conflict | AC-L1~3 | AS-01, AS-05 | D2, D3 | Strong |
| QD-P-1.1.3 | Example-Rule Contradiction | AC-L1~3 | AS-01 | D2, D3 | Strong |
| QD-P-1.2.1 | Role-Responsibility Mismatch | AC-L1~3 | AS-04, AS-09 | D2, D3, Availability | Strong |
| QD-P-1.2.2 | Role-Output Style Mismatch | AC-L1~3 | AS-03 | Auditability | Medium |
| QD-P-1.2.3 | Constraint-Responsibility Mismatch | AC-L1~3 | AS-04, AS-09 | D2, D3 | Strong |
| QD-P-1.2.4 | Identity & Anthropomorphism Boundary | AC-L1~3 | AS-01, AS-04 | D1, D3 | Medium |
| QD-P-1.3.1 | Quantifier Misuse | AC-L1~3 | AS-01, AS-04 | D2, D3 | Medium |
| QD-P-1.3.2 | Vague Qualifiers | AC-L1~3 | AS-01, AS-04 | D2, D3 | Medium |
| QD-P-1.3.3 | Undefined Boundaries | AC-L1~3 | AS-01, AS-04 | D1, D2, D3 | Strong |
| QD-P-1.4.1 | Redundant Constraints (rec.) | AC-L1~3 | AS-06 | Availability, Auditability | Conditional |
| QD-P-1.4.3 | Invalid Skill Definitions | AC-L2/3 | AS-05, AS-09 | D2, D3, Availability | Strong |
| QD-P-1.5.1 | Responsibilities Not Supporting Objective | AC-L1~3 | AS-05, AS-07, AS-09 | D2, D3, Availability | Strong |
| QD-P-1.5.2 | Resources Not Supporting Workflow | AC-L2/3 | AS-05, AS-07, AS-09 | D2, D3, Availability | Strong |
| QD-P-1.6.1 | Critical Decision Word Vagueness | AC-L1~3 | AS-01, AS-04 | D1, D2, D3 | Strong |
| QD-P-1.6.2 | Rules Depending on Model Internal State | AC-L1~3 | AS-01, AS-07 | D1, D2, D3, Availability | Conditional |
| QD-P-1.6.3 | Soft Rule Interweaving Without Arbitration | AC-L1~3 | AS-01, AS-07 | D1, D2, D3, Availability | Strong |
| QD-P-1.6.4 | Reasoning Method Constraints | AC-L1~3 | AS-01 | Availability | Conditional |
| QD-P-1.6.5 | Self-Referential/Recursive Constraints | AC-L1~3 | AS-06, AS-07 | Availability | Medium |
| QD-P-1.6.6 | Implicit Assumption Dependency | AC-L1~3 | AS-01, AS-07 | D2, Availability | Conditional |
| QD-P-1.6.7 | Non-Monotonic Reasoning Defects | AC-L1~3 (single-turn N/A) | AS-07 | D2, Availability | Conditional |
| QD-P-1.6.8 | Rule Followability | AC-L1~3 | AS-01 | Availability | Conditional |
| QD-P-2.1.2 | Reference Clarity | AC-L2/3 | AS-09 | Availability, Auditability | Medium |
| QD-P-2.1.3 | Structural Hierarchy (rec.) | AC-L1~3 | AS-01 | Availability, Auditability | Conditional |
| QD-P-2.1.5 | Context Budget Squeeze (rec.) | AC-L1~3 | AS-06 | Availability | Conditional |
| QD-P-2.2.1 | Undeclared Input Source | AC-L1~3 (self-evident N/A) | AS-01, AS-03 | D1, D2, D3 | Strong |
| QD-P-2.2.2 | Unconstrained Input Format | AC-L1~3 | AS-02, AS-07 | D2, D3, Availability | Strong |
| QD-P-2.2.3 | Required/Optional Not Distinguished | AC-L1~3 (free-text N/A) | AS-02, AS-07 | D2, D3, Availability | Strong |
| QD-P-2.2.4 | Undefined Missing-Input Handling | AC-L1~3 | AS-02, AS-07 | D2, D3, Availability | Strong |
| QD-P-2.3.1 | Undefined Output Format | AC-L1~3 (machine-consumed) | AS-03, AS-09 | D1, D2, Auditability | Strong |
| QD-P-2.3.2 | Incomplete Output Schema | AC-L1~3 (structured-output N/A) | AS-03, AS-09 | D1, D2, Auditability | Strong |
| QD-P-2.3.4 | Missing Security/Privacy Filtering | AC-L1~3 (else N/A) | AS-03 | D1 | Conditional |
| QD-P-2.3.5 | Factuality & Hallucination Control | AC-L2/3 (no retrieval/tool N/A) | AS-03 | D2, Auditability | Conditional |
| QD-P-2.3.6 | Output Length & Truncation | AC-L1~3 | AS-03 | D2, Availability | Medium |
| QD-P-2.3.7 | Output Localization & Conventions | AC-L1~3 (single-region N/A) | AS-03 | D2, Auditability | Conditional |
| QD-P-2.4.1 | Incomplete Workflow Steps | AC-L2/3 | AS-05, AS-07, AS-09 | D2, D3, Availability | Strong |
| QD-P-2.4.2 | Undeclared Resources/Tools | AC-L2/3 | AS-05, AS-09 | D2, D3, Availability | Strong |
| QD-P-2.4.3 | Tool Invocation Parameter/Order Error | AC-L2/3 | AS-05, AS-09 | D2, D3, Availability | Medium |
| QD-P-2.4.4 | Multi-turn Context & Memory Boundary | AC-L2/3 (stateless N/A) | AS-01, AS-07 | D1, D2, D3 | Medium |
| QD-P-2.5.1 | Missing Termination Constraints | AC-L2/3 | AS-06 | Availability | Strong |
| QD-P-2.5.2 | Missing Security Boundary Constraints | AC-L1~3 | AS-01, AS-03, AS-04 | D1, D2, D3 | Strong |
| QD-P-2.5.3 | Missing Permission Control Boundaries | AC-L2/3 | AS-04, AS-05 | D2, D3 | Strong |
| QD-P-2.5.4 | Undefined Constraint Priority | AC-L2/3 | AS-01, AS-07 | D1, D2, D3 | Strong |
| QD-P-2.5.6 | Instruction-Data Trust Boundary | AC-L2/3 | AS-01, AS-02 | D1, D2, D3 | Strong |
| QD-P-2.5.7 | High-Risk Operation Human Confirmation | AC-L2/3 (no such op N/A) | AS-05 | D2, D3 | Conditional |
| QD-P-2.5.8 | System Prompt Confidentiality & Leakage | AC-L2/3 | AS-01, AS-03 | D1 | Strong |
| QD-P-2.5.9 | Industry Compliance & Disclaimer | AC-L1~3 (else N/A) | AS-05 | D2, Auditability | Conditional |
| QD-P-2.6.1 | Runtime Exceptions Not Covered | AC-L2/3 | AS-07 | D1, D2, D3, Availability | Strong |
| QD-P-2.6.2 | Missing Degradation & Recovery | AC-L3 | AS-07 | Availability | Medium |
| QD-P-2.6.3 | Unreasonable Retry Mechanism | AC-L3 | AS-06, AS-07 | Availability | Medium |
| QD-P-2.6.4 | Out-of-scope Rejection & Escalation | AC-L1~3 | AS-01, AS-04 | D2, D3 | Strong |
| QD-P-2.7.1 | Positive-Example Representativeness (rec.) | AC-L1~3 | AS-01, AS-05 | D2 | Conditional |
| QD-P-2.7.2 | Counter-Example Coverage (rec.) | AC-L1~3 | AS-01, AS-05 | D2 | Conditional |
| QD-P-2.7.3 | Boundary-Case Examples Missing (rec.) | AC-L1~3 | AS-01, AS-05 | D2 | Conditional |

> Note: Recommended items (no P level) are uniformly `Conditional`. Deprecated/deleted/merged rules are not mapped: `QD-P-2.5.5` (deprecated), `QD-P-2.1.1` (deleted, injection point merged into 2.5.6), `QD-P-2.3.3` (numbering gap), `QD-P-2.1.4` (merged into 1.4.1).

### A.2 Skill (QD-S-*)

| QD ID | Name | Applies | AS | Impact | Strength |
|---|---|---|---|---|---|
| QD-S-0.1~0.9 | Basic Compliance (entry gate) | OR-L1~3 | AS-09 | Availability, Auditability | Medium |
| QD-S-1.1 | Input Boundary Missing | OR-L1~3 (platform budget N/A) | AS-06 | Availability | Strong |
| QD-S-1.2 | Output Size Missing | OR-L1~3 | AS-06 | Availability | Strong |
| QD-S-1.3 | Execution Resource Boundary Missing | OR-L1~3 (config evidence → SHOULD/N/A) | AS-06 | Availability | Strong |
| QD-S-1.4 | Permission Boundary Missing | OR-L1~3 | AS-04, AS-05 | D2, D3 | Strong |
| QD-S-1.5 | Data Source Boundary Missing | OR-L1~3 | AS-01, AS-03, AS-04 | D1, D3 | Medium |
| QD-S-2.1 | Unbounded Quantity Declaration | OR-L1~3 | AS-06 | Availability | Conditional |
| QD-S-2.2 | Unterminated Execution Declaration | OR-L1~3 | AS-06 | Availability | Conditional |
| QD-S-2.3 | Open-Ended Enumeration in Structure | OR-L1~3 | AS-06, AS-07 | Availability, D2 | Medium |
| QD-S-2.4 | Broad Capability Verbs | OR-L1~3 | AS-04, AS-05 | D2, D3 | Conditional |
| QD-S-3.1 | Vague Trigger Conditions | OR-L1~3 | AS-01, AS-04 | D1, D2, D3 | Medium |
| QD-S-3.2 | Missing Deactivation Conditions | OR-L1~3 (positive trigger suffices → exempt) | AS-01, AS-04 | D2, D3 | Medium |
| QD-S-3.3 | Missing Ambiguous Input Handling | OR-L1~3 | AS-01 | D2 | Medium |
| QD-S-3.4 | Undefined Task Scope | OR-L1~3 | AS-01, AS-05 | D2, D3 | Strong |
| QD-S-3.5 | Undeclared Default Behavior | OR-L1~3 | AS-05, AS-09 | D2, Availability | Medium |
| QD-S-3.6 | Metadata Expression Defects | OR-L1~3 | AS-08 | D2, Availability | Medium |
| QD-S-3.7 | Output Structure Contract Missing | OR-L1~3 | AS-03, AS-09 | D2, Availability, Auditability | Medium |
| QD-S-4.1 | Undefined Failure Behavior | OR-L1~3 | AS-07 | Availability | Strong |
| QD-S-4.2 | Undeclared Partial Completion | OR-L1~3 | AS-07 | D2, Availability | Medium |
| QD-S-4.3 | Missing Post-Failure Prohibited Behaviors | OR-L1~3 | AS-05, AS-07 | D2, D3 | Medium |
| QD-S-4.4 | Error Recovery Path Undefined | OR-L1~3 (no-tool L1 N/A) | AS-07 | Availability | Medium |
| QD-S-5.1 | Read/Write/Delete Not Distinguished | OR-L1~3 | AS-04, AS-05 | D2, D3 | Strong |
| QD-S-5.2 | Missing High-Risk Confirmation | OR-L3 | AS-05 | D2, D3 | Strong |
| QD-S-5.3 | Environment Boundary Not Declared | OR-L1~3 (multi-env else N/A) | AS-04, AS-05 | D2, D3 | Medium |
| QD-S-5.4 | Chained Invocation Permissions Undeclared | OR-L1~3 (chaining=false N/A) | AS-04, AS-05, AS-07 | D1, D2, D3 | Medium |

> Note: QD-S-0.x are entry gates (no P level, not counted in scoring), uniformly mapped to AS-09. Same-source deduplication: QD-S-1.4/2.4 merged into 5.1; QD-S-2.1/2.2 are the automatic trigger word lists of 1.1/1.3; QD-S-4.3 merged into 4.1.

### A.3 Tool (QD-T-*)

| QD ID | Name | Applies | AS | Impact | Strength |
|---|---|---|---|---|---|
| QD-T-1.1 | Base Field Missing | OR-L1~3 | AS-05, AS-09 | D2, Availability | Medium |
| QD-T-1.2 | Required References Undefined Field | OR-L1~3 | AS-02, AS-09 | D2, Availability | Medium |
| QD-T-1.3 | Enum type conflict / duplicate values | OR-L1~3 | AS-02, AS-09 | D2, Availability | Medium |
| QD-T-1.4 | additionalProperties Policy Inappropriate | OR-L1~3 | AS-02, AS-04 | D1, D2, D3 | Strong |
| QD-T-1.5 | name Validity & Uniqueness | OR-L1~3 | AS-05, AS-08 | D2, Availability | Medium |
| QD-T-1.6 | Constraint Self-Consistency & default | OR-L1~3 | AS-02, AS-09 | D2, Availability | Medium |
| QD-T-1.7 | Type Missing / Over-Broad | OR-L1~3 | AS-02, AS-09 | D2, Availability | Medium |
| QD-T-2.1 | String Without maxLength | OR-L1~3 | AS-02, AS-06 | D2, D3, Availability | Medium |
| QD-T-2.2 | String Format Contract Missing | OR-L1~3 | AS-02, AS-07 | D2, D3, Availability | Medium |
| QD-T-2.3 | Number/Integer Without Boundary | OR-L1~3 | AS-02, AS-06 | D2, D3, Availability | Medium |
| QD-T-2.4 | Array Without maxItems | OR-L1~3 | AS-02, AS-06 | D2, D3, Availability | Medium |
| QD-T-2.5 | Unit/Precision/Timezone/Currency Missing | OR-L1~3 | AS-02, AS-09 | D2, Availability | Medium |
| QD-T-2.6 | Query Without Pagination / Cap | OR-L1~3 | AS-06 | D2, Availability | Medium |
| QD-T-2.7 | Parameter Dependency / Mutual Exclusion Unexpressed | OR-L1~3 | AS-02, AS-07 | D2, Availability | Medium |
| QD-T-3.1 | State Change & Material Side Effect Undeclared | OR-L2/3 | AS-05 | D2, D3 | Strong |
| QD-T-3.2 | Untrusted Input into Executable Context | OR-L1~3 | AS-02 | D1, D2, D3 | Strong |
| QD-T-3.3 | Batch / Range Write Without Cap | OR-L2/3 | AS-05, AS-06 | D2, Availability | Medium |
| QD-T-3.4 | Authorization Context Parameter Exposure | OR-L1~3 | AS-04 | D1, D2, D3 | Strong |
| QD-T-3.6 | Dangerous Default / Scope Precondition | OR-L2/3 | AS-05 | D2, D3 | Medium |
| QD-T-3.7 | Parameterized-Tool Operation Whitelist Undeclared | OR-L1~3 | AS-02, AS-04, AS-05 | D1, D2, D3 | Strong |
| QD-T-4.1 | Insufficient Description Quality | OR-L1~3 | AS-05, AS-08 | D2, D3, Availability | Medium |
| QD-T-4.4 | Parameter-Level description Missing | OR-L1~3 | AS-05, AS-08 | D2, Availability | Medium |
| QD-T-4.5 | description Inconsistent with Schema | OR-L1~3 | AS-05, AS-08 | D2, Availability | Medium |
| QD-T-4.6 | Sensitive Input Handling Undeclared | OR-L2/3 | AS-03 | D1 | Conditional |
| QD-T-4.7 | Output Contract Missing (outputSchema) | OR-L2/3 | AS-03, AS-09 | D1, D2, Availability | Medium |
| QD-T-5.1 | Breaking Change Determination | change-check | AS-08, AS-09 | D2, D3, Availability | Conditional |
| QD-T-5.2 | Change Impact Assessment | change-check | AS-08, AS-09 | D2, D3, Availability | Conditional |
| QD-T-5.3 | Semantic Change | change-check | AS-08, AS-09 | D2, D3, Availability | Conditional |

> Note: Transferred (cross-Tool semantics → Cross namespace): `QD-T-3.5`→`QD-TT-5.1`; `QD-T-4.3`→`QD-TT-5.2`. Merged: `QD-T-4.2`→`QD-T-3.1`. `QD-T-5.x` are change-check items, uniformly `Conditional`.

### A.4 Cross (QD-PS/PT/ST/CYC/SS/TT-*)

| QD ID | Name | Applies | AS | Impact | Strength |
|---|---|---|---|---|---|
| QD-PS-1.1 | Skill Authorization Consistency | AC-L1~3 | AS-04, AS-09 | D2, D3 | Strong |
| QD-PS-1.2 | Trigger Condition Consistency | AC-L2/3 | AS-01, AS-05 | D2, D3 | Medium |
| QD-PS-1.3 | Permission Boundary Consistency | AC-L1~3 | AS-04, AS-09 | D2, D3 | Strong |
| QD-PS-1.4 | Resource Access Consistency | AC-L2/3 | AS-03, AS-04 | D1, D2, D3 | Medium |
| QD-PS-1.5 | Failure Handling Consistency | AC-L3 | AS-07, AS-09 | D2, Availability | Medium |
| QD-PS-1.6 | Output Constraint Consistency | AC-L3 | AS-03, AS-09 | D1, D2, Auditability | Medium |
| QD-PS-1.7 | Orchestration Order & Precondition Consistency | AC-L2/3 | AS-05, AS-09 | D2, Availability | Medium |
| QD-PT-2.1 | Tool Existence | AC-L1~3 | AS-05, AS-09 | D2, Availability | Strong |
| QD-PT-2.2 | Invocation Specification Consistency | AC-L1~3 | AS-02, AS-09 | D2, Availability | Strong |
| QD-PT-2.3 | Parameter Constraint Consistency | AC-L2/3 | AS-02, AS-09 | D2, Availability | Medium |
| QD-PT-2.4 | Permission Granularity Consistency | AC-L1~3 | AS-04, AS-05 | D2, D3 | Strong |
| QD-PT-2.5 | Key Error Handling Coverage | AC-L3 | AS-07 | D2, Availability | Medium |
| QD-PT-2.6 | Business-Level Frequency Expectation | AC-L3 | AS-06 | Availability | Medium |
| QD-PT-2.7 | Parameter Semantics & Unit Consistency | AC-L2/3 | AS-02, AS-09 | D2, Availability | Medium |
| QD-ST-3.1 | Tool Existence | AC-L1~3 | AS-05, AS-09 | D2, Availability | Strong |
| QD-ST-3.2 | Input Constraint Consistency | AC-L2/3 | AS-02, AS-09 | D2, Availability | Medium |
| QD-ST-3.3 | Required Parameter Preparation | AC-L2/3 | AS-02, AS-09 | D2, Availability | Medium |
| QD-ST-3.4 | Business-Level Frequency Expectation | AC-L3 | AS-06 | Availability | Medium |
| QD-ST-3.5 | Output Structure Match | AC-L3 | AS-03, AS-09 | D1, D2, Auditability | Medium |
| QD-ST-3.6 | Permission Scope Match | AC-L1~3 | AS-04, AS-05 | D2, D3 | Strong |
| QD-ST-3.7 | Key Error Handling Coverage | AC-L3 | AS-07, AS-09 | D1, D2, Availability | Medium |
| QD-CYC-1.1 | Cross-Artifact Circular Invocation | AC-L2/3 | AS-06 | Availability | Medium |
| QD-CYC-1.2 | Multi-Agent Circular Invocation | AC-L3 | AS-06 | Availability | Medium |
| QD-CYC-1.3 | Inter-Skill Handoff Loop | AC-L2/3 | AS-06 | Availability | Medium |
| QD-SS-4.1 | Trigger Condition Conflict | AC-L2/3 | AS-01, AS-05 | D2, D3 | Medium |
| QD-SS-4.2 | Name Uniqueness / Near-Misleading | AC-L2/3 | AS-05, AS-08 | D2, D3 | Medium |
| QD-TT-5.1 | Cross-Tool Data Flow | AC-L2/3 | AS-03, AS-05 | D1, D2, D3 | Strong |
| QD-TT-5.2 | Multi-Tool Semantic Competition | AC-L2/3 | AS-05, AS-08 | D2, D3 | Strong |
| QD-TT-5.3 | Cross-Tool Data Structure Bridging | AC-L3 | AS-03, AS-09 | D2, Availability | Medium |

> Note: QD-PS-1.6 and QD-ST-3.5 are same-source (primary: QD-ST-3.5). QD-TT-5.1/5.2 are the Cross namespace successors of QD-T-3.5/4.3.

### A.5 Permission (QD-PM-*)

> Source note: QD-PM is produced by the Inspect Permission Governance subset; this table defines only the mapping direction and does not automatically judge permission defects as EX risks; EX classification is still judged independently by Risk Explicit. When Gate-0 is not satisfied there are no QD-PM defects, and this table does not apply.

| QD ID | Name | Applies | AS | Impact | Strength |
|---|---|---|---|---|---|
| QD-PM-1.1~1.7 | Permission Alignment (1.7 fixed P2) | AC-L1~4 (1.6 conditional) | AS-04 | D2, D3, Availability | Strong |
| QD-PM-2.1~2.8 | Permission Scope (resource/data/env/condition) | AC-L1~4 (2.5/2.6/2.7 conditional) | AS-04, AS-03 | D1, D2, D3 | Strong |
| QD-PM-3.1~3.6 | Permission Granularity (3.3 role substitution, 3.4 fixed P0) | AC-L1~4 (3.4/3.5/3.6 conditional) | AS-04, AS-05 | D2, D3 | Strong |
| QD-PM-4.1~4.8 | Permission Propagation (4.2/4.4/4.8 + INHERITED) | AC-L1~4 (4.3~4.6 AC-L4; 4.7 AC-L2+; 4.8 conditional) | AS-04, AS-07, AS-08 | D1, D2, D3 | Strong |
| QD-PM-5.1~5.7 | Permission Boundary (5.4 fixed P0, 5.7 exemption) | AC-L1~4 (5.4 unconditional; 5.5/5.7 conditional) | AS-04, AS-05 | D2, D3 | Strong |
| QD-PM-6.1~6.7 | Permission Auditability (6.3/6.5 fixed P0, 6.7 fixed P1) | AC-L1~4 (6.6 AC-L2+; others conditional) | AS-05, AS-09 | D2, D3, Auditability | Medium |

> Note: QD-PM has 43 items in the full specification; here mapped in 6 groups; group-level strength indicates the overall test priority, not member severity.

## 5. Candidate failure modes (FM-*, source Appendix B.1)

> FM-* codes are defined in `quality/tool-agent.md` (L1); B.1 uses FM-01~FM-10. Here mapped at QD category group granularity. If a QD ID cannot be assigned to any group, write "no category-level FM association defined in Appendix B.1" and do not guess.

| QD category group (verbatim) | Candidate failure modes |
|---|---|
| Prompt logic contradiction, mismatch, implication defects | FM-01, FM-02, FM-07, FM-09 |
| Prompt input definition defects | FM-01, FM-04 |
| Prompt output definition defects | FM-06 |
| Prompt workflow and resource defects | FM-03, FM-04, FM-05 |
| Prompt boundary, frequency, and termination defects | FM-08, FM-09, FM-10 |
| Prompt exception handling defects | FM-08, FM-10 |
| Prompt example design defects | FM-01, FM-07, FM-09 |
| Skill resource or unbounded declaration defects | FM-08, FM-10 |
| Skill trigger, ambiguity, scope defects | FM-02, FM-07, FM-09 |
| Skill failure expansion defects | FM-08, FM-09 |
| Skill permission and environment boundary defects | FM-05, FM-09 |
| Tool structure and parameter defects | FM-03, FM-04, FM-05 |
| Tool high-risk operation defects | FM-08, FM-09, FM-10 |
| Tool semantic competition defects | FM-03, FM-05 |
| Tool Schema change defects | FM-04, FM-05, FM-06 |
| Cross contract defects | FM-04, FM-05, FM-06, FM-08 |
| Inter-Skill trigger conflict and name similarity (QD-SS) | FM-02, FM-03, FM-07 |
| Cross-Tool data structure incompatibility (QD-TT-5.3) | FM-05, FM-06 |
| Skill-to-Skill handoff loop (QD-CYC-1.3) | FM-08, FM-10 |
| Permission proportionality defects (QD-PM) | FM-05, FM-09, FM-10 |

> Wildcard convention (Appendix B): a category wildcard (e.g. `QD-P-1.x`) refers only to **currently active** members, excluding deleted/deprecated/merged/transferred IDs; the authoritative active member list is in the table above in §4.

## 6. Candidate RAG-Agent quality metrics (source Appendix C.1)

> RAG-Agent quality assessment evaluates "user-visible content output and boundary handling", and does not directly score Prompt/retrieval/knowledge base/model/Tool internal components. Mapping is **candidate**: "may affect" = worth prioritizing the design of additional tests, not necessarily a score loss. lite never runs the Quality subset.

| QD category | Candidate affected metrics | Recommended additional tests (condensed) |
|---|---|---|
| Prompt logic contradiction, mismatch, implication defects | Correctness, Relevance, Consistency, Format Compliance | Rule conflicts, role boundaries, multi-constraint Q&A |
| Prompt gray zone defects | Consistency, Robustness, Boundary Recognition, Safety Response | Vague wording, multi-turn follow-up, conflicting rules, knowledge update |
| Prompt input definition defects | Relevance, Robustness, Decomposition Capability, Boundary Recognition | Colloquial rewriting, missing conditions, multi-intent, abnormal formats |
| Prompt output definition defects | Completeness, Traceability, Format Compliance, Consistency | Citations, structure, disclaimers, JSON/Markdown |
| Prompt workflow, resource, and Tool defects | Correctness, Traceability, Timeliness | Knowledge source selection, retrieval Tool, citation chain, failure fallback |
| Prompt security, permission, and exception boundary defects | Boundary Recognition, Safety Response, Coherence | Unauthorized, sensitive, no hit, needs handoff, dependency failure |
| Prompt example design defects | Correctness, Robustness, Consistency, Format Compliance | Positive/negative examples, boundary expression, adversarial rewriting |
| Skill resource and unbounded declaration defects | Completeness, Timeliness, Robustness | Large input, multiple documents, over-limit, partial completion |
| Skill trigger, scope, and ambiguity defects | Relevance, Decomposition Capability, Boundary Recognition | Intent boundaries, non-activation, clarification handoff |
| Skill failure expansion defects | Completeness, Coherence, Safety Response | No hit, low-confidence sources, source conflict, retrieval failure |
| Skill permission and environment boundary defects | Boundary Recognition, Safety Response, Traceability | Sensitive data, user identity, production data, external resources |
| Tool parameter and semantic defects | Correctness, Relevance, Traceability, Format Compliance | Retrieval parameters, source returns, citation parsing, similar Tools |
| Cross contract defects | Correctness, Completeness, Consistency, Traceability, Safety Response | End-to-end retrieval, citations, error handling, permissions, output contract |
| Inter-Skill trigger conflict and name similarity (QD-SS) | Relevance, Correctness, Boundary Recognition | Overlapping triggers, wrong selection of similar names, direct answer when clarification is due |
| Cross-Tool data structure incompatibility (QD-TT-5.3) | Correctness, Traceability, Format Compliance | Field type mismatch, missing serialization, citation parsing failure |
| Skill-to-Skill handoff loop (QD-CYC-1.3) | Timeliness, Coherence | Non-terminating handoff, repeated routing, response timeout |
| Permission proportionality defects (QD-PM) | Boundary Recognition, Safety Response, Traceability | Unauthorized retrieval, cross-tenant access, direct answer when refusal is due |

> Out of scope: Appendix C.2 (RAG failure reverse diagnosis) and D.3 (defect chains) are not reproduced.

## 7. Forbidden automatic inference (verbatim, §2.3.1)

The following inferences are all invalid:

- `QD-P-2.5.2` ≠ automatic hit of `NL-A-7`
- `QD-T-1.4` ≠ automatic hit of `NR-S-3`
- `QD-PS-1.3` ≠ automatic hit of `NL-B-9`

Source closing rule: "Only when an explicit expression satisfying the EX definition exists in the artifact can Risk Explicit independently judge the corresponding EX classification." Stage F never derives EX codes.

## 8. Impact Card template (single-defect lite form, §5.5)

```markdown
### Impact Card: <QD-ID> | <short defect name> | <P0/P1/P2> (scope)

**Static Discovery**
- Artifact: <prompt|skill|tool>:<name>
- Version: <version label / hash>
- Evidence: <rule hit and location, one line>

**Potential Security Associations**  <!-- candidate association, not confirmed impact -->
- Candidate Attack Surface: AS-xx <name> [, AS-yy ...]
- Potential Impact: D1 / D2 / D3 / Availability / Integrity / Auditability
- Mapping Strength: <Strong|Medium|Conditional> "provisional (lite)" — association confidence only, not severity
- Note: This conclusion indicates validation priority, and does not yet indicate backend exploitability.

**Recommended Validation — NOT run by this lite inspector**
- Risk Explicit: Stage E already run, not reclassified here.
- Risk Implicit: not run — dynamic exploitability not verified.
- External controls: existence unknown; per §1.4 must not assume compensating controls outside the artifact are missing.

**Potential Quality Associations**
- Tool-Agent: FM-xx, FM-yy (category level, B.1)
- RAG-Agent: <metrics> (candidate, C.1; not a quality result)

**Current Evidence Status**
- Static Defect: Confirmed
- Dynamic Exploitability: Not verified
- Quality Association: Not verified
- Compensating Control: To be confirmed

**Remediation and Regression**
- Recommendation: <per the owning L1 sub-specification>
- Minimum Regression: Inspect re-scan of the updated artifact passing the same rule ID
```

**Wording red line (verbatim, §5.5.1)**:

| Allowed | Forbidden |
|---|---|
| "May expand the attack surface" | "Has already been attacked" |
| "Recommended to prioritize validation" | "Vulnerability necessarily exists" |
| "Candidate quality root cause" | "Quality failure is caused by this defect" |
| "Relies on compensating controls" | "Completely secure" |
| "Not reproduced under current test conditions" | "Absolutely unexploitable" |

### 8.1 Compact template (grouped by impact category, optional in lite)

When defects are numerous and the abbreviation density affects readability, the **grouped form** in the table below may replace per-defect cards (the full template in §8 can still be used for single defects that need detail). Hard requirements unchanged: candidate language, Strength ≠ severity, Risk Implicit / runtime Quality not run, physical separation from the verdict.

**Terminology table (required, only lists the codes actually used in this table)**

| Code | Meaning |
|---|---|
| AS-xx | <attack surface name in the report language, from the §3 legend> |
| D1 / D2 / D3 | Confidentiality / Integrity / Authorization damage |
| Strong / Medium / Conditional | Association strength (= validation priority, not severity) |
| FM category group | <group name, taken from §5> (per-code definitions are not distributed with the package, not expanded) |

**Grouped table (one impact category per row)**

| Impact category | Defect (inline attribution, per-defect must not be merged) | Possible consequence (plain language) | Suggest testing first |
|---|---|---|---|
| <category name> (AS-xx/…) | `<QD-ID>` (AS-… · impact · strength · FM-…), `<QD-ID>` (…) | … | … |

> Constraint: within each row each defect must inline its own `AS / impact / strength / FM`; strengths may differ within a group (e.g. Strong and Conditional coexist) and must not be lost due to grouping; P0 defects are bolded.

## 9. Defect chain — out of lite scope (§1.5)

Defect chains are used to identify candidate exploitation/failure paths formed by combinations of multiple defects, requiring a unique `chain_id`, retained member defects and cross-artifact relations, end-to-end Risk Implicit validation, etc. **Out of scope for lite inspector v1**: this reference supports only single-defect candidate mapping, does not construct/assert/report defect chains (SC-*/QC-TA-*/QC-RA-*), and does not upgrade separate single-defect candidate associations into chain paths.
