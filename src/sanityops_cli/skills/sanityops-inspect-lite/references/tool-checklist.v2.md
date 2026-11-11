---
title: Tool Schema Checklist (v2 统一引擎版)
---

# Tool Schema Checklist (QD-T, v2)

> **状态**：v2 统一引擎版。
>
> **规则语义**源自 `inspect/tool.md` v1.1：ID、名称、严重度取值、合并/转移记录均保持不变；变化的是**组织方式**——改为"全字段 + 正文表格（模型项）+ 程序块（程序项）"。
>
> 全局判定口径（缺失声明即缺陷、N/A 必带依据、失效安全默认查、程序项全量枚举）见 `_meta.md`。本文件不重复。

## 1. 域内说明

> 共享定义（字段模型 / check_engine 映射 / applicability 结构事实门 / severity 记号 / 打分规则）见 [_meta.md](_meta.md)，本文件不重复。本文件只承载 Tool 域检查项本身。

**`check_engine` 重分类说明**（相对源 `Method` 列）：基线映射 `Automated→program`、`Human→model`、`Semi-automated→hybrid`；以下 4 处偏离源 Method，动因是源 Method 列与自身定义矛盾，按设计 §2.8「优先收敛」纠正：

- `QD-T-1.4`：源标 Automated，但定义是"策略恰当性**判断**" → hybrid
- `QD-T-4.1`：源标 Semi-automated，但纯语义（缺 ≥2 要素） → model
- `QD-T-4.6`：源标 Semi-automated，但纯语义（"是否敏感"） → model
- `QD-T-5.2`：源标 Semi-automated，但纯语义（影响评估缺失/矛盾） → model

## 2. 检查项索引（28 活跃项 + 3 tombstone）

| ID | name | check_engine | applicability.fact | severity OR-L1/OR-L2/OR-L3 | 计入打分 |
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
| QD-T-5.1 | Breaking Change Determination | hybrid | has_version_change | §4.3.1 matrix | ✗（change-check） |
| QD-T-5.2 | Change Impact Assessment Missing/Wrong | model | has_change_note | P1 / P1 / P0 | ✗（change-check） |
| QD-T-5.3 | Semantic Change | hybrid | has_version_change | P1 / P1 / P0 | ✗（change-check） |

> **5.x 说明**：QD-T-5.x 属 Schema 变更管理，仅在有 old/new Schema 对比对象时触发，**不计入静态检查分母**（源规范 §5.2.1）。tombstone 见 §5。

## 3. 模型推理项（正文表格）

> 以下为 `check_engine = model` 的项（5 个）。hybrid 项的"模型确认要点"也在此列出（见 §3.2）。

### 3.1 纯 model 项

| ID | definition（凝练） | model_prompt（判定要点） |
|---|---|---|
| QD-T-3.1 | 名称/描述读作只读，但实际有写/副作用未声明；或副作用（不可逆/外部/资金）完全未声明 | 判工具名称是否读作只读（verify/query/get）而 body 存在写语义；或写语义与名称一致但不可逆性未声明 |
| QD-T-3.4 | 暴露应由系统控制的参数（tenantId / admin / token） | 判是否存在授权上下文参数，且该参数可由调用方自由填写 |
| QD-T-4.1 | 描述缺少必需要素（动作、对象、范围/时效、关键参数语义、返回摘要），且缺 ≥2 个 | 逐项核对描述是否覆盖五个要素，缺 ≥2 判 FAIL |
| QD-T-4.6 | 密码/密钥/身份证号等敏感输入未声明 writeOnly / 加密 / 不落日志 | 判参数是否敏感，且未声明敏感处理 |
| QD-T-5.2 | 变更说明未声明调用方/数据/系统影响，或声明与事实矛盾 | 对照 change note 与 schema diff，判影响声明是否缺失或矛盾 |

### 3.2 hybrid 项的模型确认部分

> **skill 端：本节即完整判定要点，无程序初筛前置。**「程序仅检…／程序仅做…」描述的是 CLI / platform 的初筛路径；skill 全模型推理、不执行 §4，必须自行完成语义判定，不得视为"已筛过"，也不得据此判 N/A。

| ID | model_prompt（确认要点） |
|---|---|
| QD-T-1.2 | 确认 required 中的字段是否本就不该存在 / 违背业务契约（源 P1 子项：字段必要性，各档 P1） |
| QD-T-1.4 | 确认 additionalProperties 策略是否恰当：封闭契约字段应为 false，tags/metadata 开放字典可省略 |
| QD-T-2.2 | 确认该字符串是否"需要特定格式"（如日期、URL、编码），从而需要 pattern |
| QD-T-2.5 | 确认参数是否金额/时间/货币/比例，从而需要 unit/currency/precision/timezone |
| QD-T-2.7 | 确认参数间是否存在成对必填/互斥/条件必填/至少其一关系 |
| QD-T-3.2 | 确认是否已参数化/有白名单/有沙箱，从而可豁免 |
| QD-T-3.3 | 确认批量写是否有上限（maxItems、分页、拒绝空过滤） |
| QD-T-3.6 | 确认 default/scope 是否为危险值（force=true、dry_run=false、scope=ALL） |
| QD-T-3.7 | 确认开放式工具（sql/exec/http/eval）是否声明了操作白名单（表/命令/域名） |
| QD-T-4.5 | 确认 description 声明与 schema 约束是否语义一致（如"max 10" vs schema 允许 100） |
| QD-T-4.7 | 确认 outputSchema 缺失是否在跨工具数据流场景下升级 P0 |
| QD-T-5.1 | 确认 old/new schema 差异是否破坏既有调用（breaking） |
| QD-T-5.3 | 确认结构未变但语义是否变化（name/default/unit/scope/side-effect） |

## 4. 程序判定项（program-check 代码块）

> **CLI / platform 专用：skill 不解析、不执行本代码块**（skill 全模型推理，不消费 `check_engine` 与 `program_rule`）。程序引擎只 parse 本代码块。`rule` 字段为**判定语义示意**（非最终可执行定义，程序级实现后续补）。
> 涵盖纯 program 项 + hybrid 项的初筛规则。

<!-- program-check -->
```json
{
  "domain": "tool",
  "version": "v2-sample",
  "note": "程序判定项 + hybrid 初筛规则。rule 为语义示意。",
  "checks": [
    { "id": "QD-T-1.1", "summary": "顶层缺少 name / description / inputSchema 之一" },
    { "id": "QD-T-1.2", "summary": "required 引用了 properties 未定义的字段" },
    { "id": "QD-T-1.3", "summary": "enum 重复值，或 enum 值与声明 type 冲突" },
    { "id": "QD-T-1.4", "summary": "检测 additionalProperties 设置（策略恰当性由模型确认）" },
    { "id": "QD-T-1.5", "summary": "name 不匹配 ^[a-zA-Z0-9_-]{1,64}$ 或非唯一" },
    { "id": "QD-T-1.6", "summary": "minimum>maximum / minLength>maxLength / minItems>maxItems / default 违反约束" },
    { "id": "QD-T-1.7", "summary": "缺 type / 多类型数组 / 嵌套>4 / 参数>30 / oneOf 滥用" },
    { "id": "QD-T-2.1", "summary": "string 参数缺 maxLength（enum/const/pattern 固定长豁免）" },
    { "id": "QD-T-2.2", "summary": "需特定格式的 string 缺 pattern（是否需格式由模型确认）" },
    { "id": "QD-T-2.3", "summary": "number/integer 缺 minimum/maximum" },
    { "id": "QD-T-2.4", "summary": "array 参数缺 maxItems" },
    { "id": "QD-T-2.5", "summary": "金额/时间类 number 缺 multipleOf 或单位（语义由模型确认）" },
    { "id": "QD-T-2.6", "summary": "list_*/search_* 工具缺 limit/page_size 或 limit 缺 maximum" },
    { "id": "QD-T-2.7", "summary": "依赖/互斥未用 dependentRequired/oneOf 表达（语义由模型确认）" },
    { "id": "QD-T-3.2", "summary": "参数命中 SQL/shell/code/template/URL/path 可执行特征（豁免由模型确认）" },
    { "id": "QD-T-3.3", "summary": "批量写参数（ids/过滤条件）无上限（是否有 cap 由模型确认）" },
    { "id": "QD-T-3.6", "summary": "default 命中 force=true / dry_run=false / scope=ALL（危险性由模型确认）" },
    { "id": "QD-T-3.7", "summary": "开放式工具（sql_query/exec/http_request/eval）缺操作白名单" },
    { "id": "QD-T-4.4", "summary": "property 缺 description" },
    { "id": "QD-T-4.5", "summary": "description 字面量与 schema 约束不一致（语义由模型确认）" },
    { "id": "QD-T-4.7", "summary": "缺 outputSchema（cross-flow 升级由模型确认）" },
    { "id": "QD-T-5.1", "summary": "old/new schema 存在破坏性差异（是否 breaking 由模型确认）" },
    { "id": "QD-T-5.3", "summary": "name/default/unit/scope 变更（是否语义变更由模型确认）" }
  ]
}
```
<!-- /program-check -->

## 5. Tombstone 记录（合并 / 转移，不参与判定）

| ID | name | 状态 | 指向 |
|---|---|---|---|
| QD-T-4.2 | Side Effect Undeclared | merged | → QD-T-3.1（编号保留，不再独立使用） |
| QD-T-3.5 | Cross-Tool Data Flow | transferred | → cross QD-TT-5.1（P2 lead 保留） |
| QD-T-4.3 | Multi-Tool Semantic Competition | transferred | → cross QD-TT-5.2（P2 lead 保留） |

## 6. 打分字段说明（platform 专用）

- 全局权重规则（`_meta.md`）：`P0 : P1 : P2 = 5 : 3 : 1`，按项最高严重度扣一次。
- `计入打分` 列 = `✓` 的项进入静态分母（20/25/25）；`✗`（5.x change-check）与 tombstone 不计入。
- skill / CLI 不激活打分，但 `score_weight` 信息在索引表「计入打分」列保留，供 platform 使用。

