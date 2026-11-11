---
title: System Prompt Checklist (v2 统一引擎版)
---

# System Prompt Checklist (QD-P, v2)

> **状态**：v2 统一引擎版。规则语义源自 `inspect/prompt.md` v1.1（2026-10）：ID、名称、严重度取值、合并/转移/废弃记录均保持不变；变化的是**组织方式**——全字段 + 正文表格（模型项）+ 程序块（程序项）。
>
> 共享定义（字段模型 / check_engine 映射 / applicability 结构事实门 / severity 记号 / 打分规则）见 [_meta.md](_meta.md)，本文件不重复。本文件只承载 Prompt 域检查项本身。

## 1. 域内说明

- **L 命名**：本域 severity 表头用 **AC-L1/AC-L2/AC-L3**（Agent complexity level），非 OR-L。System Prompt 无 operation-risk 维度。
- **check_engine 分配口径（本域重分类日志）**（源无 Method 列，按源"detection nature"映射）：
  - **Part 1（QD-P-1.x，逻辑缺陷，可语义阅读检出）→ `model`**。
  - **Part 2（QD-P-2.x，完整性/安全缺口，需显式 checklist）**：缺声明类（"未声明/缺失 X"）→ `hybrid`（程序初筛声明存在 + 模型确认充分性）；纯语义质量类 → `model`。
- **条件项**：QD-P-2.3.4 / 2.3.7 / 2.5.7 / 2.5.9 无固定 tier severity，触发→P0（2.3.7 为 P1），不触发→N/A，**不计入静态分母**。
- **建议项（ungraded，6）**：QD-P-1.4.1 / 2.1.3 / 2.1.5 / 2.7.1 / 2.7.2 / 2.7.3，见 §6，不评分、不计入、不阻断。
- **primary-defect 合并**（源 §4.6）：同一事实命中多个语义重叠 ID 时只记 primary，其余标"related"。重叠组见源，不在此重推导。

## 2. 检查项索引（48 项 = 44 计入 + 4 条件；另有 6 建议项 + 4 tombstone）

| ID | name | check_engine | applicability.fact | severity AC-L1/L2/L3 | 计入打分 |
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
| QD-P-2.3.4 | Missing Security/Privacy Filtering | model | has_pii | P0(条件) | ✗（条件） |
| QD-P-2.3.5 | Factuality & Hallucination Control | model | has_retrieval_or_tool | ∅ / P0 / P0 | ✓ |
| QD-P-2.3.6 | Output Length & Truncation | hybrid | is_prompt | P2 / P2 / P2 | ✓ |
| QD-P-2.3.7 | Output Localization & Conventions | model | is_multi_region | P1(条件) | ✗（条件） |
| QD-P-2.4.1 | Incomplete Workflow Steps | model | has_workflow | ∅ / P1 / P0 | ✓ |
| QD-P-2.4.2 | Undeclared Resources/Tools | hybrid | has_tool_usage | ∅ / P0 / P0 | ✓ |
| QD-P-2.4.3 | Tool Invocation Parameter/Order Error | model | has_tool_invocation | ∅ / P1 / P1 | ✓ |
| QD-P-2.4.4 | Multi-turn Context & Memory Boundary | model | has_multiturn | ∅ / P1 / P1 | ✓ |
| QD-P-2.5.1 | Missing Termination Constraints | model | has_retry_or_loop | ∅ / P1 / P0 | ✓ |
| QD-P-2.5.2 | Missing Security Boundary Constraints | hybrid | is_prompt | P0 / P0 / P0 | ✓ |
| QD-P-2.5.3 | Missing Permission Control Boundaries | hybrid | has_permission_control | ∅ / P1 / P0 | ✓ |
| QD-P-2.5.4 | Undefined Constraint Priority | model | has_conflicting_constraints | ∅ / P1 / P0 | ✓ |
| QD-P-2.5.6 | Instruction-Data Trust Boundary | model | has_external_data | ∅ / P0 / P0 | ✓ |
| QD-P-2.5.7 | High-Risk Operation Human Confirmation | model | has_side_effect_op | P0(条件) | ✗（条件） |
| QD-P-2.5.8 | System Prompt Confidentiality & Leakage | model | has_confidential_content | ∅ / P1 / P1 | ✓ |
| QD-P-2.5.9 | Industry Compliance & Disclaimer Boundary | model | is_regulated_domain | P0(条件) | ✗（条件） |
| QD-P-2.6.1 | Runtime Exceptions Not Covered | hybrid | has_tool_usage | ∅ / P1 / P0 | ✓ |
| QD-P-2.6.2 | Missing Degradation & Recovery Strategy | model | is_complex_agent | ∅ / ∅ / P1 | ✓ |
| QD-P-2.6.3 | Unreasonable Retry Mechanism | model | has_retry_or_loop | ∅ / ∅ / P1 | ✓ |
| QD-P-2.6.4 | Out-of-scope Rejection & Human Escalation | model | is_prompt | P1 / P1 / P0 | ✓ |

> 计数说明：48 行中 44 项计入静态分母（L1=28 / L2=42 / L3=44，源 §3.3.3）；4 项条件项（2.3.4/2.3.7/2.5.7/2.5.9）不计入固定分母。建议项见 §6，tombstone 见 §5。

## 3. 模型判定要点（definition 凝练 + model_prompt）

> skill 全模型一次推理；CLI 的 model 项 / hybrid 项确认阶段也读此处。`definition` 取自源 §3.3.2 的 Severity Variation Notes + 最小集 Definition。

### 3.1 纯 model 项（37 项）

| ID | definition（凝练） | model_prompt（判定要点） |
|---|---|---|
| QD-P-1.1.1 | 同一对象在同一上下文被赋予互斥属性/指令 | 找同一对象的两处属性/指令是否直接矛盾 |
| QD-P-1.1.2 | 多条 MUST 约束在无优先级/仲裁的场景下冲突 | 找冲突场景，且未定义优先级或仲裁 |
| QD-P-1.1.3 | 正文规则与示例相矛盾 | 对照规则定义与所给示例是否冲突 |
| QD-P-1.2.1 | 角色身份/能力范围与职责要求不匹配 | 判角色身份是否支撑其被要求承担的职责 |
| QD-P-1.2.2 | 角色与输出风格要求不匹配 | 仅当风格要求显式不兼容时判 FAIL |
| QD-P-1.2.3 | 约束范围与职责行为范围冲突/错配 | 判约束是否落到错误的职责范围上 |
| QD-P-1.2.4 | 冒充真人/组织，或漏 AI 身份声明 | 判是否允许冒充，或漏 AI 身份声明；C 端用户 P0 |
| QD-P-1.3.1 | 量词误用产生与他条规则的逻辑冲突 | 仅当量词误用导致逻辑冲突时判（"过度绝对"不算） |
| QD-P-1.3.2 | 模糊词模糊了关键决策边界 | 仅当模糊词模糊关键决策边界时判 |
| QD-P-1.3.3 | 关键行为边界（授权/禁止/交接）未定义 | 判授权/禁止/交接边界是否缺失 |
| QD-P-1.4.3 | 定义的 Skill 触发/用法不清或冲突导致永不调用 | 判 Skill 定义是否清晰、可触发、无冲突 |
| QD-P-1.5.1 | 定义的行为无法达成角色总体目标 | 判职责集合能否支撑总体目标 |
| QD-P-1.5.2 | 工作流步骤引用了未定义/未授权的资源 | 判工作流引用的资源/工具是否已定义 |
| QD-P-1.6.1 | 关键决策词模糊，且该词是决策依据 | 判模糊词是否充当安全/权限决策依据（区别于 1.3.2） |
| QD-P-1.6.2 | 关键决策仅靠模型自我评估，无可观测触发 | 判关键决策是否唯一依赖模型内部状态 |
| QD-P-1.6.3 | 软规则交织无仲裁 | 仅当能给出具体不兼容场景判；涉安全/权限 P0 |
| QD-P-1.6.4 | 用不可验证的内部推理方法作合规保证 | 判是否以不可验证推理方法作为保证 |
| QD-P-1.6.5 | 自指/递归约束 | 仅非终止/不可满足/循环递归判 |
| QD-P-1.6.6 | 关键、非显然、外部不保证的隐含假设 | 判是否依赖未声明的关键外部假设 |
| QD-P-1.6.7 | 跨轮状态/已承诺结论存在非单调缺陷 | 判跨轮状态或已承诺结论是否被推翻；单轮 N/A |
| QD-P-1.6.8 | 规则要求模型不可靠能力（计数/计时/算术） | 判规则是否强求计数/计时/算术等不可靠能力 |
| QD-P-2.1.2 | 工具/资源引用不清晰 | 判引用是否含糊、无法定位 |
| QD-P-2.3.4 | 敏感数据脱敏/最小字段输出未声明（涉 PII） | 判是否涉 PII 且未声明过滤 |
| QD-P-2.3.5 | 未声明不捏造工具结果/不引用未调用工具/不编造参考 | 判是否缺反幻觉声明（RAG/Tool agent） |
| QD-P-2.3.7 | 多区域本地化/约定未声明 | 判是否多区域且未声明本地化约定 |
| QD-P-2.4.1 | 工作流步骤依赖/顺序未定义或引用未定义步骤 | 判工作流步骤是否完整、依赖是否定义 |
| QD-P-2.4.3 | 正文写的工具调用参数/顺序错误 | 判正文内工具调用的参数/顺序是否写错 |
| QD-P-2.4.4 | 跨轮/跨会话上下文与记忆边界未定义 | 判多轮上下文的记忆边界是否缺失 |
| QD-P-2.5.1 | 完成/放弃条件、部分成功上报、"不得声称成功"步骤未定义 | 判终止约束是否缺失 |
| QD-P-2.5.4 | 可能冲突的 SHOULD 约束的仲裁规则未定义 | 判约束优先级/仲裁是否缺失 |
| QD-P-2.5.6 | 指令与外部数据的信任边界未声明（防注入） | 判是否缺指令-数据信任边界声明 |
| QD-P-2.5.7 | 高风险/不可逆操作未声明需用户确认 | 判有副作用操作（资金/删除/发送/生产变更）是否缺确认声明 |
| QD-P-2.5.8 | 系统提示机密性与泄漏响应未声明 | 判是否缺机密性/泄漏响应声明 |
| QD-P-2.5.9 | 行业合规约束、免责、资质边界未声明 | 判医疗/金融/法律域是否缺合规声明 |
| QD-P-2.6.2 | 降级与恢复策略缺失（"停并报告"合法） | 判是否有降级/恢复策略 |
| QD-P-2.6.3 | 不合理重试（无上限/盲写重试/未查询超时态） | 判重试机制是否合理；"停并报告"归 2.6.2 勿双扣 |
| QD-P-2.6.4 | 拒绝模板、转介目标、升级条件未定义 | 判越界拒绝/人工升级是否缺失 |

### 3.2 hybrid 项的模型确认部分（11 项）

> **skill 端：本节即完整判定要点，无程序初筛前置。**「程序仅检…／程序仅做…」描述的是 CLI / platform 的初筛路径；skill 全模型推理、不执行 §4，必须自行完成语义判定，不得视为"已筛过"，也不得据此判 N/A。

| ID | model_prompt（确认要点） |
|---|---|
| QD-P-2.2.1 | 确认输入来源声明是否真缺失（程序仅检 user/system/external 等来源关键词缺失） |
| QD-P-2.2.2 | 确认结构化输入是否真缺格式/编码/大小约束（程序仅检约束声明缺失） |
| QD-P-2.2.3 | 确认 required/optional 是否真未区分（程序仅检 required 声明缺失） |
| QD-P-2.2.4 | 确认缺失/异常输入处理是否真未定义（程序仅检处理声明缺失） |
| QD-P-2.3.1 | 仅当输出被机器消费时适用（自由文本聊天回答 N/A）；确认格式/结构/编码是否真未定义（程序仅检格式声明缺失） |
| QD-P-2.3.2 | 确认输出 schema 是否真缺关键字段（程序仅检 outputSchema 字段缺失） |
| QD-P-2.3.6 | 确认输出长度/截断是否真未声明（程序仅检长度声明缺失） |
| QD-P-2.4.2 | 确认正文实际用到的资源/工具是否真未声明（程序仅做引用层比对） |
| QD-P-2.5.2 | 确认安全边界是否真缺失（程序仅检禁操作/敏感访问/外部系统声明缺失） |
| QD-P-2.5.3 | 确认权限控制边界是否真缺失（程序仅检权限范围/提权/越权声明缺失） |
| QD-P-2.6.1 | 确认运行时异常处理是否真未定义（程序仅检异常处理声明缺失） |

## 4. 程序判定项（program-check 代码块）

> **CLI / platform 专用：skill 不解析、不执行本代码块**（skill 全模型推理，不消费 `check_engine` 与 `program_rule`）。程序引擎只 parse 本代码块。覆盖 hybrid 项的初筛规则（声明存在性 / 字段缺失）。`rule` 为语义示意。

<!-- program-check -->
```json
{
  "domain": "prompt",
  "version": "v2",
  "note": "hybrid 项初筛规则（声明存在性/字段缺失）。rule 为语义示意。",
  "checks": [
    { "id": "QD-P-2.2.1", "summary": "未出现输入来源声明（user/system/external）" },
    { "id": "QD-P-2.2.2", "summary": "结构化输入未声明格式/编码/大小限制" },
    { "id": "QD-P-2.2.3", "summary": "结构化输入未区分 required/optional" },
    { "id": "QD-P-2.2.4", "summary": "未声明缺失/异常输入处理" },
    { "id": "QD-P-2.3.1", "summary": "机器消费的输出未声明格式/结构/编码（自由文本聊天 N/A）" },
    { "id": "QD-P-2.3.2", "summary": "结构化输出缺 outputSchema 关键字段" },
    { "id": "QD-P-2.3.6", "summary": "未声明输出长度/截断" },
    { "id": "QD-P-2.4.2", "summary": "正文使用工具/DB/API 但未声明（与引用层比对）" },
    { "id": "QD-P-2.5.2", "summary": "未声明安全边界（禁操作/敏感访问/外部系统）" },
    { "id": "QD-P-2.5.3", "summary": "未声明权限范围/提权条件/越权处理" },
    { "id": "QD-P-2.6.1", "summary": "未声明运行时异常处理" }
  ]
}
```
<!-- /program-check -->

## 5. Tombstone 记录（废弃 / 合并 / 转移）

| ID | name | 状态 | 指向 |
|---|---|---|---|
| QD-P-2.1.1 | (injection point) | deleted | 注入点并入 QD-P-2.5.6 |
| QD-P-2.1.4 | (redundant constraints) | merged | → QD-P-1.4.1（建议项） |
| QD-P-2.5.5 | Resource-Call Frequency Limit | deprecated | 频率/批量期望由 cross QD-PT-2.6 / QD-ST-3.4 承接 |
| QD-P-2.3.3 | (numbering gap) | gap | 无状态说明，仅编号空位 |

## 6. 建议项（ungraded，6）

> 仅优化价值：不评分、不计入分母、不阻断、无 waiver。applicability 均为 `is_prompt`。

| ID | name | 说明 |
|---|---|---|
| QD-P-1.4.1 | Redundant Constraints | 冗余约束（吸收 2.1.4） |
| QD-P-2.1.3 | Structural Hierarchy | 结构层级清晰度 |
| QD-P-2.1.5 | Context Budget Squeeze | 上下文预算挤压 |
| QD-P-2.7.1 | Positive-Example Representativeness | 正例代表性 |
| QD-P-2.7.2 | Counter-Example Coverage | 反例覆盖 |
| QD-P-2.7.3 | Boundary-Case Examples | 边界例覆盖 |

## 7. 打分字段说明（platform 专用）

- 全局权重（`_meta.md`）：P0 : P1 : P2 = 5 : 3 : 1，按项最高严重度扣一次。
- 分母：44 项计入（L1=28 / L2=42 / L3=44）；4 条件项、6 建议项、tombstone 不计入。
- skill / CLI 不激活打分；`score_weight` 信息在索引表「计入打分」列保留供 platform。
