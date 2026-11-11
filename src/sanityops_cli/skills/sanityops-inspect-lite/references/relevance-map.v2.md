---
title: Relevance Map (v2 统一引擎版)
---

# Relevance Map (Stage F Impact Outlook, v2)

> **状态**：v2 统一引擎版。本文件是**映射（查找）文档，不是规则清单**：无新增检查项、无 `check_engine`、无 `applicability.fact`、无逐项 `severity`（`strength` ≠ `severity`）。规则语义源自 `framework/relevance.md` v1.1，映射方向 / 攻击面 / 候选失效模式 / 验证建议均保持不变。
>
> 共享定义见 [_meta.md](_meta.md)。本文件在 Stage F（影响展望）使用：对 Stage A/B/D 已产生的 **FAIL** 逐条查 QD ID，输出候选 Impact Card。本文件**消费**各 v2 checklist 的统一 QD ID（单一事实源 = prompt/skill/tool/cross/permission 的 v2 检查项），不定义新 ID。

## 1. 域内说明

- **性质**：L2 跨域映射文档，从属于九个 L1 子规范。任何冲突（编号/定义/severity/发布要求）**以源子规范为准**（relevance.md §0.3.1）。映射强度/攻击面/候选失效模式不改变源子规范的原始判定。
- **只映射实际 FAIL 的缺陷**：禁止预映射、推测映射、映射已修复/PASS 项。
- **候选语言红线**：每行输出必须是"候选关联"——用 "may / candidate association / needs dynamic verification"；禁写因果断言 "will cause / guarantees / ensures / inevitably / proves"（相关性≠因果，relevance.md §0.4-1）。
- **strength ≠ severity**（§1.3）：Strength 只描述"关联置信度 / 测试优先级"，绝不替代 P0/P1/P2；两者显式分列。
- **无 check_engine / applicability.fact / 逐项 severity**：本域是查找表，行键是 QD ID（源锚点），列是 AS/Impact/Strength/Validation 元数据。`Applies` 列保留源规范作用域（AC-L/OR-L），非统一 applicability 结构事实。
- **显式记录"未运行"**：每个影响区须声明 Risk Implicit 与运行时 Quality 子集**未运行**（动态可利用性未验证），且按 §1.4 不得假设工件外补偿控制缺失；Risk Explicit 不在本展望重分类（Stage E 已跑，Stage F 只做候选映射）。
- **禁止自动推断 EX**（§2.3.1）：`QD-P-2.5.2` ≠ 自动命中 `NL-A-7`；`QD-T-1.4` ≠ `NR-S-3`；`QD-PS-1.3` ≠ `NL-B-9`。EX 码只在 Stage E 由 Risk Explicit 独立判定。
- **缺陷链出 lite 范围**（§1.5）：仅支持单缺陷候选映射，不构造/断言/报告缺陷链（SC-*/QC-TA-*/QC-RA-*）。
- **物理隔离**：影响展望与 Gate/verdict 结论分离，是建议性上下文，不得改变/软化/升级任何 Inspect 结论。

## 2. 映射强度（strength，非 severity，§1.3）

| Strength | 含义（verbatim） | 全框架 platform 行为 |
|---|---|---|
| Strong | 缺陷直接扩大攻击入口，或极可能导致指定失效模式 | 自动推荐相关 Risk/Quality 测试用例 |
| Medium | 在特定权限/数据/Tool/流程条件下可能有影响 | 按适用条件推荐 |
| Conditional | 需外部知识库/运行时环境/模型行为/业务规则 | 作为候选调查方向，无自动结论 |
| Not Applicable | 当前 Agent 类型/工件类型/运行时条件缺乏关联前提 | 不输出该推荐 |

> lite 口径：源 Appendix A 已有逐行 strength，下表照录；输出 Impact Card 时复制该行 strength 并标 "provisional (lite)"。

## 3. 攻击面图例（AS-*，§2.2）

| ID | 攻击面 | 定义 |
|---|---|---|
| AS-01 | Instruction and Context Boundary Confusion | 误把不可信输入/文档/历史/外部返回当作高优先级指令 |
| AS-02 | Input and Parameter Injection | 无约束用户/外部输入进入 Tool/后端/下游解释器 |
| AS-03 | Output Handling and Sensitive Data Exfiltration | 敏感信息被输出/拼接/引用/转发/写到外部 |
| AS-04 | Permission, Identity, and Delegation Expansion | 宽泛能力/错误授权/链式调用导致越界操作 |
| AS-05 | Tool Misuse and High-Risk Side Effects | 错误 Tool 选择/意外写/批量操作/未确认不可逆动作 |
| AS-06 | Resource Exhaustion and Runaway Execution | 输入/输出/调用/重试/递归无上限导致资源失控 |
| AS-07 | Anomaly Propagation and Cascading Failures | Tool/依赖失败后 Agent 采无定义扩张/重试/降级 |
| AS-08 | Configuration, Naming, and Supply Chain Confusion | 相似 Tool 名/Schema 变更/危险默认值/异常回调地址 |
| AS-09 | Cross-Artifact Contract Breach | Prompt/Skill/Tool 间授权/参数/输出/权限/错误策略不一致 |

> 影响维度码：`D1`=机密性损害、`D2`=完整性损害、`D3`=授权损害（§0.5）。"Availability/Auditability/Integrity" 在源表中为普通词。

## 4. 缺陷→影响映射表（源 Appendix A）

### A.1 Prompt（QD-P-*）

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

> 注：推荐项（无 P 级）统一 `Conditional`。已弃用/删除/合并规则不映射：`QD-P-2.5.5`（弃用）、`QD-P-2.1.1`（删除，注入点并入 2.5.6）、`QD-P-2.3.3`（编号空位）、`QD-P-2.1.4`（并入 1.4.1）。

### A.2 Skill（QD-S-*）

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

> 注：QD-S-0.x 为入口门（无 P 级、不计分），统一映射 AS-09。同源去重：QD-S-1.4/2.4 并入 5.1；QD-S-2.1/2.2 是 1.1/1.3 的自动触发词表；QD-S-4.3 并入 4.1。

### A.3 Tool（QD-T-*）

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

> 注：已转移（跨 Tool 语义 → Cross 命名空间）：`QD-T-3.5`→`QD-TT-5.1`；`QD-T-4.3`→`QD-TT-5.2`。已合并：`QD-T-4.2`→`QD-T-3.1`。`QD-T-5.x` 为 change-check 项，统一 `Conditional`。

### A.4 Cross（QD-PS/PT/ST/CYC/SS/TT-*）

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

> 注：QD-PS-1.6 与 QD-ST-3.5 同源（primary：QD-ST-3.5）。QD-TT-5.1/5.2 是 QD-T-3.5/4.3 的 Cross 命名空间后继。

### A.5 Permission（QD-PM-*）

> 源注：QD-PM 由 Inspect Permission Governance 子集产出，本表只定义映射方向，不自动判定权限缺陷为 EX 风险；EX 分类仍由 Risk Explicit 独立判定。Gate-0 未满足时无 QD-PM 缺陷，本表不适用。

| QD ID | Name | Applies | AS | Impact | Strength |
|---|---|---|---|---|---|
| QD-PM-1.1~1.7 | Permission Alignment (1.7 fixed P2) | AC-L1~4 (1.6 conditional) | AS-04 | D2, D3, Availability | Strong |
| QD-PM-2.1~2.8 | Permission Scope (resource/data/env/condition) | AC-L1~4 (2.5/2.6/2.7 conditional) | AS-04, AS-03 | D1, D2, D3 | Strong |
| QD-PM-3.1~3.6 | Permission Granularity (3.3 role substitution, 3.4 fixed P0) | AC-L1~4 (3.4/3.5/3.6 conditional) | AS-04, AS-05 | D2, D3 | Strong |
| QD-PM-4.1~4.8 | Permission Propagation (4.2/4.4/4.8 + INHERITED) | AC-L1~4 (4.3~4.6 AC-L4; 4.7 AC-L2+; 4.8 conditional) | AS-04, AS-07, AS-08 | D1, D2, D3 | Strong |
| QD-PM-5.1~5.7 | Permission Boundary (5.4 fixed P0, 5.7 exemption) | AC-L1~4 (5.4 unconditional; 5.5/5.7 conditional) | AS-04, AS-05 | D2, D3 | Strong |
| QD-PM-6.1~6.7 | Permission Auditability (6.3/6.5 fixed P0, 6.7 fixed P1) | AC-L1~4 (6.6 AC-L2+; others conditional) | AS-05, AS-09 | D2, D3, Auditability | Medium |

> 注：QD-PM 全规范 43 项，此处按 6 组映射；组级 strength 表示整体测试优先级，非成员 severity。

## 5. 候选失效模式（FM-*，源 Appendix B.1）

> FM-* 码定义在 `quality/tool-agent.md`（L1），B.1 使用 FM-01~FM-10。此处按 QD 类别组粒度映射。若某 QD ID 无法归入任一组，写 "no category-level FM association defined in Appendix B.1"，不猜测。

| QD 类别组（verbatim） | 候选失效模式 |
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

> 通配约定（Appendix B）：类别通配（如 `QD-P-1.x`）只指**当前活跃**成员，排除删除/弃用/合并/转移 ID；权威活跃成员清单见 §4 上表。

## 6. 候选 RAG-Agent 质量指标（源 Appendix C.1）

> RAG-Agent 质量评估"用户可见内容输出与边界处理"，不直接评分 Prompt/检索/知识库/模型/Tool 内部组件。映射为**候选**："may affect" = 值得优先设计补充测试，非必然丢分。lite 从不运行 Quality 子集。

| QD 类别 | 候选影响指标 | 推荐补充测试（凝练） |
|---|---|---|
| Prompt logic contradiction, mismatch, implication defects | Correctness, Relevance, Consistency, Format Compliance | 规则冲突、角色边界、多约束 Q&A |
| Prompt gray zone defects | Consistency, Robustness, Boundary Recognition, Safety Response | 模糊措辞、多轮追问、冲突规则、知识更新 |
| Prompt input definition defects | Relevance, Robustness, Decomposition Capability, Boundary Recognition | 口语改写、缺条件、多意图、异常格式 |
| Prompt output definition defects | Completeness, Traceability, Format Compliance, Consistency | 引用、结构、免责声明、JSON/Markdown |
| Prompt workflow, resource, and Tool defects | Correctness, Traceability, Timeliness | 知识源选择、检索 Tool、引用链、失败回退 |
| Prompt security, permission, and exception boundary defects | Boundary Recognition, Safety Response, Coherence | 未授权、敏感、无命中、需转接、依赖失败 |
| Prompt example design defects | Correctness, Robustness, Consistency, Format Compliance | 正/反例、边界表达、对抗改写 |
| Skill resource and unbounded declaration defects | Completeness, Timeliness, Robustness | 大输入、多文档、超限、部分完成 |
| Skill trigger, scope, and ambiguity defects | Relevance, Decomposition Capability, Boundary Recognition | 意图边界、不激活、澄清转接 |
| Skill failure expansion defects | Completeness, Coherence, Safety Response | 无命中、低置信源、源冲突、检索失败 |
| Skill permission and environment boundary defects | Boundary Recognition, Safety Response, Traceability | 敏感数据、用户身份、生产数据、外部资源 |
| Tool parameter and semantic defects | Correctness, Relevance, Traceability, Format Compliance | 检索参数、源返回、引用解析、相似 Tool |
| Cross contract defects | Correctness, Completeness, Consistency, Traceability, Safety Response | 端到端检索、引用、错误处理、权限、输出契约 |
| Inter-Skill trigger conflict and name similarity (QD-SS) | Relevance, Correctness, Boundary Recognition | 重叠触发、相似名误选、应澄清却直答 |
| Cross-Tool data structure incompatibility (QD-TT-5.3) | Correctness, Traceability, Format Compliance | 字段类型不匹配、缺序列化、引用解析失败 |
| Skill-to-Skill handoff loop (QD-CYC-1.3) | Timeliness, Coherence | 无终止转接、重复路由、响应超时 |
| Permission proportionality defects (QD-PM) | Boundary Recognition, Safety Response, Traceability | 未授权检索、跨租户访问、应拒绝却直答 |

> 出范围：Appendix C.2（RAG 失败反向诊断）与 D.3（缺陷链）不复现。

## 7. 禁止的自动推断（verbatim，§2.3.1）

以下推断均无效：

- `QD-P-2.5.2` ≠ 自动命中 `NL-A-7`
- `QD-T-1.4` ≠ 自动命中 `NR-S-3`
- `QD-PS-1.3` ≠ 自动命中 `NL-B-9`

源收尾规则："仅当工件中存在满足 EX 定义的显式表达，Risk Explicit 才能独立判定相应 EX 分类。" Stage F 从不推导 EX 码。

## 8. Impact Card 模板（单缺陷 lite 形，§5.5）

```markdown
### Impact Card: <QD-ID> | <短缺陷名> | <P0/P1/P2> (scope)

**Static Discovery**
- Artifact: <prompt|skill|tool>:<name>
- Version: <version label / hash>
- Evidence: <rule hit and location, one line>

**Potential Security Associations**  <!-- 候选关联，非确认影响 -->
- Candidate Attack Surface: AS-xx <name> [, AS-yy ...]
- Potential Impact: D1 / D2 / D3 / Availability / Integrity / Auditability
- Mapping Strength: <Strong|Medium|Conditional> "provisional (lite)" — 仅关联置信度，非 severity
- Note: 本结论指示验证优先级，尚未指示后端可利用。

**Recommended Validation — NOT run by this lite inspector**
- Risk Explicit: Stage E 已跑，此处不重分类。
- Risk Implicit: 未运行——动态可利用性未验证。
- External controls: 存在性未知；按 §1.4 不得假设工件外补偿控制缺失。

**Potential Quality Associations**
- Tool-Agent: FM-xx, FM-yy（类别级，B.1）
- RAG-Agent: <metrics>（候选，C.1；非质量结果）

**Current Evidence Status**
- Static Defect: Confirmed
- Dynamic Exploitability: Not verified
- Quality Association: Not verified
- Compensating Control: To be confirmed

**Remediation and Regression**
- Recommendation: <per the owning L1 sub-specification>
- Minimum Regression: Inspect re-scan of the updated artifact passing the same rule ID
```

**措辞红线（verbatim，§5.5.1）**：

| 允许 | 禁止 |
|---|---|
| "May expand the attack surface" | "Has already been attacked" |
| "Recommended to prioritize validation" | "Vulnerability necessarily exists" |
| "Candidate quality root cause" | "Quality failure is caused by this defect" |
| "Relies on compensating controls" | "Completely secure" |
| "Not reproduced under current test conditions" | "Absolutely unexploitable" |

### 8.1 Compact 模板（按影响类别分组，lite 可选用）

当缺陷较多、缩写密度影响可读性时，可用下表的**分组形态**替代逐缺陷卡片（§8 完整模板仍可用于需详述的单缺陷）。硬要求不变：候选语言、Strength ≠ severity、Risk Implicit / 运行时 Quality 未运行、与 verdict 物理隔离。

**术语表（必带，只列本表实际用到的编码）**

| 编码 | 含义 |
|---|---|
| AS-xx | <攻击面中文名，取自 §3 图例> |
| D1 / D2 / D3 | 机密性 / 完整性 / 授权损害 |
| Strong / Medium / Conditional | 关联强度（=验证优先级，非严重度） |
| FM 类别组 | <组名，取自 §5>（逐码定义未随包分发，不展开） |

**分组表（每行一个影响类别）**

| 影响类别 | 缺陷（内联归属，逐缺陷不可合并） | 可能后果（人话） | 建议先测 |
|---|---|---|---|
| <类别名>（AS-xx/…） | `<QD-ID>`（AS-… · impact · strength · FM-…）、`<QD-ID>`（…） | … | … |

> 约束：每行内每个缺陷必须内联自己的 `AS / impact / strength / FM`；strength 组内可能不同（如 Strong 与 Conditional 并存），不得因分组丢失；P0 缺陷加粗。

## 9. 缺陷链——出 lite 范围（§1.5）

缺陷链用于识别多缺陷组合形成的候选利用/失败路径，需唯一 `chain_id`、保留成员缺陷与跨工件关系、端到端 Risk Implicit 验证等。**lite inspector v1 出范围**：本参考仅支持单缺陷候选映射，不构造/断言/报告缺陷链（SC-*/QC-TA-*/QC-RA-*），不把分离的单缺陷候选关联升级为链路径。
