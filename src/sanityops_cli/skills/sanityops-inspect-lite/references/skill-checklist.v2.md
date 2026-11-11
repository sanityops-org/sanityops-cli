---
title: Skill Inspection Checklist (QD-S, v2 统一引擎版)
---

# Skill Inspection Checklist (QD-S, v2)

> **状态**：v2 统一引擎版。规则语义源自 `inspect/skill.md` v1.1（2026-10）：ID、名称、严重度取值均保持不变；变化的是**组织方式**——全字段 + 正文表格（模型项）+ 程序块（程序项）。
>
> 共享定义（字段模型 / check_engine 映射 / applicability 结构事实门 / severity 记号 / 打分规则）见 [_meta.md](_meta.md)，本文件不重复。本文件只承载 Skill 域检查项本身。

## 1. 域内说明

- **L 命名**：本域 severity 表头用 **OR-L1/OR-L2/OR-L3**（operation risk：L1 read-only / L2 reversible write / L3 irreversible；Skill 无工具调用 → L1，有工具调用 → 按所执行操作的最高风险）。Skill 域无 AC-L 维度。
- **基线门 QD-S-0**（9 项）：平台最小结构校验（能否解析、可检），**pass/fail，不计分**（源 §11.3）。QD-S-0.9 为 SHOULD 级，不计入门。放宽失败处理（v1.1）：仅 QD-S-0.3 完全不可解析才阻断 QD-S-1~5 检查；其余 0 缺陷标记 "baseline not passed" 并继续，结论记 "assessment incomplete (NEEDS_REVIEW)"。
- **check_engine 分配口径（本域重分类日志）**（源 §6 六步流程 + 设计 §2.8「优先收敛」）：
  - QD-S-0 结构校验（0.1–0.4、0.6–0.9）→ `program`；0.5（冲突判定，需人审）→ `hybrid`。
  - 数量边界/无界措辞扫描类（1.1–1.3、2.1–2.4，源 §6 步骤 4 的 keyword scanning）→ `hybrid`（程序关键词初筛 + 模型确认）。
  - 语义/声明充分性类（1.4–1.5、3.x、4.x、5.x，源 §6 步骤 5）→ `model`。
- **"缺失声明即缺陷"口径**（源 §1）：规则定义的声明缺位即 FAIL，定义尾部的 "allowing / leading-to …" 是**风险机制**而非附加前提。**QD-S-2.x 例外**：它们检测"已写出的无界措辞"，缺陷是措辞的**存在**（正向检测）。
- **有效约束与补偿控制**（源 §7.5，跨项 severity 原则）：工件内可追溯约束（Tool Schema 字段、`allowed_operations`、声明 scope/service-account）可影响 severity；外部 Harness/RBAC/platform 控制仅作 `compensating_controls`（影响处置不影响缺陷存在）；证据不足输出 "to-be-verified"，不强制定级。
- **五态结果**（源 §7.4）：Pass / Defect / N/A / Insufficient Evidence / Not Checked；N/A 必写依据；"Insufficient Evidence" 输出 "to-be-verified"，不评分。
- **建议/可选项**：QD-S-3.2、3.7 在 L1 为 optional（推荐非必须）；本文件仍列入活跃项，L1 severity 标 ∅（参考级，可追溯 L2/L3 原始 P）。

## 2. 检查项索引（33 项 = 9 基线门 + 24 语义项）

| ID | name | check_engine | applicability.fact | severity OR-L1/L2/L3 | 计入打分 |
|---|---|---|---|---|---|
| QD-S-0.1 | Required Field Presence | program | is_skill | gate | ✗（基线） |
| QD-S-0.2 | Field Content Non-Empty | program | is_skill | gate | ✗（基线） |
| QD-S-0.3 | Syntax Parsability | program | is_skill | gate | ✗（基线） |
| QD-S-0.4 | Field Type Validity | program | is_skill | gate | ✗（基线） |
| QD-S-0.5 | No Conflicting Declarations | hybrid | is_skill | gate | ✗（基线） |
| QD-S-0.6 | Minimum Structural Completeness | program | is_skill | gate | ✗（基线） |
| QD-S-0.7 | Dependency & Resource Existence | program | is_skill | gate | ✗（基线） |
| QD-S-0.8 | Metadata Completeness | program | is_skill | gate | ✗（基线） |
| QD-S-0.9 | description Length Budget | program | is_skill | gate (SHOULD) | ✗（基线） |
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

> 计数说明：9 基线门（QD-S-0，pass/fail 不计分）+ 24 语义项。语义项 severity 为 OR-L 三档（L1=8 项 / L2=23 项 / L3=24 项，源 §4 累计）。`∅` = 该 L 下原规范不分配 P（参考级展示；N/A 由 `applicability.fact` 单独决定，与 L 无关）。`has_tool_invocation`/`has_data_access`/`has_write_semantics`/`has_irreversible_op`/`has_environment_access`/`has_skill_chaining` 为结构事实（观察"工件实际做不做"，非"是否已声明"——防点1悖论）。

## 3. 模型判定要点（definition 凝练 + model_prompt）

> skill 全模型一次推理；CLI 的 model 项 / hybrid 项确认阶段也读此处。`definition` 取自源 §2 / §5。

### 3.1 纯 model 项（17 项）

| ID | definition（凝练） | model_prompt（判定要点） |
|---|---|---|
| QD-S-1.4 | 无 read/write/delete 区分、无 prohibited-operation 声明 | 判工件是否有数据操作，且未区分读/改/删作用域、未声明禁止操作 |
| QD-S-1.5 | 无 permitted/prohibited 数据源；LLM 可从 history/外部系统取数 | 判工件是否访问数据源（history/外部），且未声明允许/禁止来源 |
| QD-S-3.1 | 触发条件过宽；多个无关意图可触发 | 判 allowed_when/forbidden_when 是否过宽、是否存在歧义触发 |
| QD-S-3.2 | 未声明 Skill 何时不应触发 | 判是否缺 forbidden_when / 停用条件 |
| QD-S-3.3 | 未声明对不完整/畸形输入的处理；LLM 自动补全 | 判缺 on_empty_input/on_insufficient_input，是否默认自动补全或推断 |
| QD-S-3.4 | 缺 non_goals；LLM 自行扩展边界 | 判缺 non_goals、任务范围是否被过度声明 |
| QD-S-3.5 | 关键分支（空输入/格式错/数据不足）无定义处理 | 判关键分支是否无默认行为定义 |
| QD-S-3.6 | name/description 过宽、不准、与 body 不一致 | 判元数据是否夸大/偏离/矛盾于正文实际行为 |
| QD-S-3.7 | 输出格式/必填字段/空结果表示未声明；LLM 自选结构 | 判缺输出结构契约（格式、字段、空结果表示），注意与 1.2（尺寸）、2.3（开放枚举）区分 |
| QD-S-4.1 | 未声明执行失败处理；LLM 探索替代路径 | 判缺失败处理策略，是否允许模型自行改道 |
| QD-S-4.2 | 未声明"部分完成是否可接受" | 判缺 partial_result_allowed 声明 |
| QD-S-4.3 | 未声明失败后禁止的行为 | 判缺 forbidden_behaviors（禁止自动补全/推断/扩界） |
| QD-S-4.4 | 未定义逐异常恢复路径 | 判缺 per-exception 恢复路径；"safe-terminate-and-report" 是合法处置 |
| QD-S-5.1 | 操作数据未区分 read/modify/delete 作用域 | 判数据操作是否混淆读/改/删 |
| QD-S-5.2 | 不可逆操作（删/覆写/外泄/支付）无确认门 | 判不可逆操作是否缺 require_user_confirmation_for 确认门 |
| QD-S-5.3 | 未声明是否禁止生产、允许哪些环境 | 判缺环境边界声明（禁止 production / 允许环境清单） |
| QD-S-5.4 | 调用其他 Skill 未声明允许/禁止下游范围 | 判链式调用是否缺 allowed_downstream_skills / 范围声明 |

### 3.2 hybrid 项的模型确认部分

> **skill 端：本节即完整判定要点，无程序初筛前置。**「程序仅检…／程序仅做…」描述的是 CLI / platform 的初筛路径；skill 全模型推理、不执行 §4，必须自行完成语义判定，不得视为"已筛过"，也不得据此判 N/A。

| ID | model_prompt（确认要点） |
|---|---|
| QD-S-0.5 | 确认 body/examples/failure/permission 声明间冲突是否真实存在，并同时报告冲突双方（不偏袒宽松或严格侧） |
| QD-S-1.1 | 确认输入数量/尺寸上限是否真缺失（关键词命中 ≠ 已声明；需语义核实） |
| QD-S-1.2 | 确认输出尺寸上限是否真缺失 |
| QD-S-1.3 | 确认重试/调用次数/超时边界是否真缺失 |
| QD-S-2.1 | 确认无界量词（all/every/entire/complete）是否确无数量上限 |
| QD-S-2.2 | 确认 keep trying/until success 等措辞是否确无终止条件 |
| QD-S-2.3 | 确认 etc./and others/such as 是否确实放任模型自行添加条目 |
| QD-S-2.4 | 确认 manage/handle 等宽泛动词是否确无 non_goals 约束 |

## 4. 程序判定项（program-check 代码块）

> **CLI / platform 专用：skill 不解析、不执行本代码块**（skill 全模型推理，不消费 `check_engine` 与 `program_rule`）。程序引擎只 parse 本代码块。`rule` 字段为**判定语义示意**（非最终可执行定义，程序级实现后续补）。涵盖纯 program 项（QD-S-0 基线）+ hybrid 项的初筛规则。

<!-- program-check -->
```json
{
  "domain": "skill",
  "version": "v2",
  "note": "程序判定项（QD-S-0 基线）+ hybrid 初筛规则。rule 为语义示意。",
  "checks": [
    { "id": "QD-S-0.1", "summary": "必需字段（name/description 等）缺失" },
    { "id": "QD-S-0.2", "summary": "必需字段为空或纯空白" },
    { "id": "QD-S-0.3", "summary": "YAML frontmatter / Markdown 结构不可解析" },
    { "id": "QD-S-0.4", "summary": "字段值类型不符（enum/boolean/number/list）" },
    { "id": "QD-S-0.5", "summary": "检测 body/examples/failure/permission 潜在冲突（真实性由模型确认）" },
    { "id": "QD-S-0.6", "summary": "无可定位最小结构（可引用位置/可检单元）" },
    { "id": "QD-S-0.7", "summary": "引用脚本/模板/下游 Skill 不存在或不解析（凭证/异常URL/PII→EX 交叉引用）" },
    { "id": "QD-S-0.8", "summary": "version/owner/changelog 缺失或不可追溯" },
    { "id": "QD-S-0.9", "summary": "description 超出 token 预算（SHOULD）" },
    { "id": "QD-S-1.1", "summary": "未检出输入上限关键词（max_items/max_chars/limit，真缺失由模型确认）" },
    { "id": "QD-S-1.2", "summary": "未检出输出上限关键词（max_total_chars，真缺失由模型确认）" },
    { "id": "QD-S-1.3", "summary": "未检出执行边界（max_tool_calls/max_retries/timeout_seconds）" },
    { "id": "QD-S-2.1", "summary": "检出无界量词 all/every/entire/complete（是否配 cap 由模型确认）" },
    { "id": "QD-S-2.2", "summary": "检出 keep trying/until success/ensure complete/persist until（有无终止由模型确认）" },
    { "id": "QD-S-2.3", "summary": "检出 etc./and others/such as" },
    { "id": "QD-S-2.4", "summary": "检出 manage/handle/coordinate/automate/process/address（是否配 non_goals 由模型确认）" }
  ]
}
```
<!-- /program-check -->

## 5. Tombstone 记录

无。Skill 域源规范未包含 merged / transferred 项（QD-S-3.2、3.7 为 L1 可选，仍为活跃项，非 tombstone）。

## 6. 打分字段说明（platform 专用）

- 源 §8 **固定扣分**：P0=25、P1=15、P2=5（保持 5:3:1，不随项数变化）。Score = max(100 − 总扣分, 0)；**存在任一 P0 时封顶 60 且 Gate=FAIL**。同源去重（§11.6）：同一根因/同一危害路径只记一次。
- 分母为 tier 相关（L1=8 / L2=23 / L3=24）；`计入打分` 列 = ✓ 的语义项进入对应 tier 分母，✗（QD-S-0 基线）与 tombstone 不计入。
- skill / CLI 不激活打分，但 score_weight 信息在索引表保留，供 platform 使用；Gate 是 Inspect 局部结论（非框架级发布决策）。
