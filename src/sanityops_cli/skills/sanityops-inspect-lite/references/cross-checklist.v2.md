---
title: Cross-Artifact Consistency Checklist (v2 统一引擎版)
---

# Cross-Artifact Consistency Checklist (QD-PS/PT/ST/SS/TT/CYC, v2)

> **状态**：v2 统一引擎版。规则语义源自 `inspect/cross.md` v1.1：ID、名称、默认严重度、AC-L 适用性、OR-L3/实例升级、去重组均保持不变；变化的是**组织方式**——全字段 + 正文表格（模型项）+ 程序块（程序项）。
>
> 共享定义（字段模型 / check_engine 映射 / applicability 结构事实门 / severity 记号 / 打分规则）见 [_meta.md](_meta.md)，本文件不重复。本文件只承载 Cross 域检查项本身。

## 1. 域内说明

- **双 L 维度**：本域 severity 由 **AC-L**（决定 default P 取值）与 **OR-L**（升级：OR-L3 → P0/P1）共同决定。哪些项适用由 `applicability.fact` 决定，**不由 AC-L**（原 tier-scoped 规格的 L1=7 / L2=20 / L3=29 范围仅作历史参考，不再决定"考不考"）。索引表 severity 列标 **AC-L1/L2/L3 的 default 取值**（`∅` = 该 L 下原规范不分配 P，参考级展示）；OR-L3 升级与实例升级见下方表格。
- **非阻塞模式**（源 §How to Use）：上游单工件 P0 不阻断本清单执行，聚合 P0 而非 halt。开始前确认 Prompt/Skill/Tool 版本号、时间戳、来源一致，不一致先问用户。
- **仅检跨工件关系**（六组：QD-PS / QD-PT / QD-ST / QD-SS / QD-TT / QD-CYC），不复检 QD-P/QS/QD-T 的单工件内部缺陷。
- **每项证据须引双方工件位置**（三级定位：关系→工件→字段）。
- **N/A 纪律**：N/A 必写依据（如"无 Tool Schema""Agent 仅 1 个 Skill"）；无依据的 N/A 视为未检，按默认级计失败。
- **check_engine 分配口径（本域重分类日志）**：跨工件一致性本质是语义推理 → 绝大多数 `model`；存在性/唯一性/竞争（2.1、3.1、4.2、5.2）有程序初筛（名称匹配）→ `hybrid`。本域**无纯 program 项**。

**OR-L3 升级表（源 Appendix C.2，跨项）**：

| 升级 | 项 |
|---|---|
| P1 → P0 | QD-PS-1.2, 1.4, 1.5, 1.7 · QD-PT-2.3, 2.7 · QD-ST-3.5 · QD-SS-4.1 · QD-TT-5.1, 5.2 · QD-CYC-1.1, 1.2, 1.3 |
| P2 → P1（→P0 当会误触发 OR-L3 Skill） | QD-SS-4.2 |
| 无升级（P1 保持） | QD-PT-2.5, QD-ST-3.7 |
| P2 无 OR-L3 升级（保持 P2） | QD-PS-1.6, QD-PT-2.6, QD-ST-3.4, QD-TT-5.3 |

**实例升级（各规则体 `→P0` 分支）**：QD-CYC 确定的闭环 → P0；QD-TT-5.1 敏感输出+危险消费并存 → P0；QD-TT-5.2 行为差异大 → P0；QD-SS-4.1 涉及 OR-L3 Skill → P0。

## 2. 检查项索引（29 项，六组）

| ID | name | check_engine | applicability.fact | severity AC-L1/L2/L3 | 计入打分 |
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

> 计数说明：29 项 = QD-PS(7) + QD-PT(7) + QD-ST(7) + QD-CYC(3) + QD-SS(2) + QD-TT(3)。severity 为 AC-L 三档 default（L1=7 项全 P0 / L2=20 / L3=29）；`∅` = 该 L 下原规范不分配 P（参考级展示）。`has_*` 为结构关系事实（工件间是否存在该关系），非"是否已声明一致"（防点1悖论）。QD-CYC-1.2 仅当 Prompt 编排声明 ≥2 Agent 角色，否则 N/A。

> **存在性检查的 applicability 例外（防点1悖论在跨工件存在性检查上的应用）**：QD-PS-1.1 / QD-PT-2.1 / QD-ST-3.1 检查"声明的 X 是否真的存在"，其 applicability 用**引用事实**而非"双方都存在"的关系事实——`has_skill_reference`（Prompt 声明了 Skill 名，含 IR reference layer 条目）、`has_tool_reference`（Prompt/Skill 声明了 Tool 名，含 IR reference layer 条目）。这样当被引用对象缺失（"referenced but missing"）时检查仍运行并命中，而不是因 `has_prompt_and_tool` 等为假而自锁 N/A。

## 3. 模型判定要点（definition 凝练 + model_prompt）

### 3.1 纯 model 项（25 项）

| ID | definition（凝练） | model_prompt（判定要点） |
|---|---|---|
| QD-PS-1.1 | Prompt 声明的 Skill 与已定义 Skill 匹配（授权范围外） | 核对 Prompt 声明的 Skill 列表与已定义 Skill，判是否越权/缺声明 |
| QD-PS-1.2 | Prompt 工作流触发条件匹配 Skill 的 allowed_when/forbidden_when | 比对 Prompt 触发与 Skill TRIGGER 维度 |
| QD-PS-1.3 | Prompt 授权权限覆盖 Skill 的 allowed_operations | 判 Prompt 权限是否覆盖 Skill 允许操作 |
| QD-PS-1.4 | Prompt 声明资源对齐 Skill 的 allowed_resources | 比对资源声明 |
| QD-PS-1.5 | Prompt 异常处理对齐 Skill FAILURE 维度 | 比对 on_empty/on_insufficient/forbidden_behaviors |
| QD-PS-1.6 | Prompt 输出要求由 Skill OUTPUT 维度满足 | 比对 max_total_chars/format/partial_result_allowed |
| QD-PS-1.7 | Skill 声明前置条件由前一 Prompt 步骤满足 | 判调用前前置条件是否已满足 |
| QD-PT-2.2 | Prompt 工具调用规范匹配 Tool Schema（name/description/inputSchema） | 比对调用规范与 schema |
| QD-PT-2.3 | Prompt 参数约束对齐 Tool inputSchema（required/properties/maxLength/pattern） | 比对参数约束 |
| QD-PT-2.4 | Prompt 权限声明匹配 Tool 风险级（OR-L3 需安全边界） | 判高风险 Tool 是否有 Prompt 安全边界声明 |
| QD-PT-2.5 | Prompt 异常处理覆盖 Tool 所有关键错误类型 | 判错误类型覆盖 |
| QD-PT-2.6 | Prompt 声明合理的业务级调用频率/批量期望 | 判频率/批量期望合理性 |
| QD-PT-2.7 | Prompt 参数语义/单位（名称/单位/货币/时区）匹配 inputSchema | 比对语义与单位 |
| QD-ST-3.2 | Skill INPUT 约束由 Tool inputSchema 支持（maxLength/pattern/maxItems） | 比对输入约束支持性 |
| QD-ST-3.3 | Tool 必填参数在 Skill 中有来源声明（用户输入或其他工具输出） | 判必填参数是否有来源 |
| QD-ST-3.4 | Skill 调用频率/批量期望与 Tool 能力组合合理 | 判频率合理性 |
| QD-ST-3.5 | Skill OUTPUT 期望匹配 Tool 返回结构 | 比对输出结构 |
| QD-ST-3.6 | Skill 权限声明覆盖 Tool 副作用（写/敏感数据） | 判权限覆盖副作用 |
| QD-ST-3.7 | Skill FAILURE 维度覆盖 Tool 所有关键错误类型 | 判错误覆盖 |
| QD-CYC-1.1 | Prompt/Skill/Tool 调用关系形成闭环 | 判是否存在跨工件调用环；确定闭环→P0 |
| QD-CYC-1.2 | 多 Agent 角色间形成闭环 | 判 Agent 间闭环（仅 ≥2 Agent 角色） |
| QD-CYC-1.3 | 多 Skill 经 handoff 互指形成不终止循环 | 判 Skill 间 handoff 环 |
| QD-SS-4.1 | 多 Skill 触发重叠，同一输入激活多个 Skill | 判触发冲突 |
| QD-TT-5.1 | 一 Tool 敏感输出被另一 Tool 用于危险操作，形成数据泄漏链 | 判敏感输出+危险消费链；并存→P0 |
| QD-TT-5.3 | 一 Tool 输出/输入类型不兼容且 Skill 无转换步骤 | 判类型桥接缺失 |

### 3.2 hybrid 项的模型确认部分

> **skill 端：本节即完整判定要点，无程序初筛前置。**「程序仅做…」描述的是 CLI / platform 的初筛路径；skill 全模型推理、不执行 §4，必须自行完成语义判定，不得视为"已筛过"，也不得据此判 N/A。

| ID | model_prompt（确认要点） |
|---|---|
| QD-PT-2.1 | 确认 Prompt 声明 Tool 名是否真存在于已知 Tool Schema 列表且语义一致（程序仅做名称匹配） |
| QD-ST-3.1 | 确认 Skill 声明 Tool 名是否真存在于已知 Tool Schema 列表且语义一致 |
| QD-SS-4.2 | 确认名称相同/近似是否真导致误调用（程序仅做名称相似度） |
| QD-TT-5.2 | 确认 name/description 近似是否真导致误调用（程序仅做名称/描述相似度） |

## 4. 程序判定项（program-check 代码块）

> **CLI / platform 专用：skill 不解析、不执行本代码块**（skill 全模型推理，不消费 `check_engine` 与 `program_rule`）。程序引擎只 parse 本代码块。`rule` 字段为**判定语义示意**。本域仅 hybrid 项有初筛规则，无纯 program 项。

<!-- program-check -->
```json
{
  "domain": "cross",
  "version": "v2",
  "note": "hybrid 项初筛规则。rule 为语义示意。",
  "checks": [
    { "id": "QD-PT-2.1", "summary": "Prompt 声明 Tool 名与已知 Tool Schema 列表名称匹配（语义一致性由模型确认）" },
    { "id": "QD-ST-3.1", "summary": "Skill 声明 Tool 名与已知 Tool Schema 列表名称匹配（语义一致性由模型确认）" },
    { "id": "QD-SS-4.2", "summary": "多 Skill 名称相同或近似（误调用风险由模型确认）" },
    { "id": "QD-TT-5.2", "summary": "多 Tool name/description 近似（误调用风险由模型确认）" }
  ]
}
```
<!-- /program-check -->

## 5. Tombstone 记录

无。Cross 域源规范未包含 merged / transferred 项。

## 6. 打分字段说明（platform 专用）

- 权重 `P0:P1:P2 = 5:3:1`；base = 100 / 总权重；每失败项按 default 级扣 base×5/3/1（每项一次，不论实例数）。
- 分母为 tier 相关（AC-L1=7 / L2=20 / L3=29）；`计入打分` 列全部 ✓。
- 同源去重（源 §8.5.2）：同一事实命中同组多 ID 时按最高级记一次，保留全部 ID 与证据，标 primary；分母不变。去重组：Tool 存在性（PT-2.1↔ST-3.1）、权限边界（PS-1.3↔1.4↔ST-3.6）、参数约束（PT-2.3↔ST-3.2）、输出契约（PS-1.6↔ST-3.5，primary ST-3.5）、错误处理（PT-2.5↔ST-3.7）。PT-2.7 无 Skill 侧对应，不去重。
- skill / CLI 不激活打分，但 score_weight 信息在索引表保留，供 platform 使用。
