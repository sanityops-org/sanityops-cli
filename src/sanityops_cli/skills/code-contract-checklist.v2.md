---
title: Code Contract Inspection Checklist (QC, v2 统一引擎版)
---

# Code Contract Inspection Checklist (QC, v2)

> **状态**：v2 统一引擎版。规则语义源自 `quality/code-contract.md` v1.0：ID、名称、严重度取值均保持不变；变化的是**组织方式**——全字段 + 正文表格（模型项）+ 程序块（程序项）。
>
> 共享定义（字段模型 / check_engine 映射 / applicability 结构事实门 / severity 记号 / 打分规则）见 [_meta.md](_meta.md)，本文件不重复。本文件只承载 Code Contract 域检查项本身。

## 1. 域内说明

- **范围**（源 §1）：仅检 Logic Artifact 内嵌的代码片段（System Prompt / Skill 描述与步骤 / Tool Schema 的 description·default·example 字段）。**不检完整源码文件**（用标准 linter）。
- **L 维度**：无。本域 severity 为**扁平 P0/P1/P2**（无 OR-L / AC-L 维度），索引表 severity 列仅一档。
- **基线门 QC-0**（5 项）：entry gate，QC-1~4 检查前 MUST 通过。
- **依赖上下文规则**（源 §1）：QC-1.2（Invalid Import）、QC-1.3（Deprecated API）依赖**外部输入**（声明依赖清单 + API 版本库），不在 Logic Artifact 内。外部输入缺失（lite 默认）时记 `Not Executed`，**绝不记 FAIL**；仅当片段内自证缺陷（如 import 明显不存在的模块）或自相矛盾时才记 FAIL。
- **示意片段规则**（源 §1）：外层文本标记为示意/伪码（"example"/"pseudo"、用 `...` 省略）的片段，豁免 QC-0.1 / QC-0.3 的解析完整性要求；省略或缺 import 不构成 FAIL。
- **check_engine 分配口径（本域重分类日志）**：源 Method 列 `Automated`→program、`Semi-automated`→hybrid、`Pattern match`→program（确定性模式匹配，程序可执行）；QC-0 无 Method 列，按 Appendix 检测策略映射（0.4 fence 匹配→program，0.5 语言-内容关键词匹配→hybrid）。本域**无纯 model 项**（lint 型）。
- **跨域交叉引用**（源 §5 注）：QC-3.3（Hardcoded Demo Value）与 NR-S-9（Hardcoded Credential）重叠——真实凭证由 NR-S-9 优先；QC-3.3 覆盖弱/演示模式（"123456"、"xxx"、"changeme"、本地路径、内网 IP），不匹配凭证检测器。

## 2. 检查项索引（17 项 = 5 基线门 + 12 检查项）

| ID | name | check_engine | applicability.fact | severity | 计入打分 |
|---|---|---|---|---|---|
| QC-0.1 | Syntax Parsability | program | has_code_snippet | P0 | ✗（基线） |
| QC-0.2 | Language Declaration | program | has_code_snippet | P1 | ✗（基线） |
| QC-0.3 | Structural Completeness | program | has_code_snippet | P1 | ✗（基线） |
| QC-0.4 | Fence Integrity | program | has_code_snippet | P1 | ✗（基线） |
| QC-0.5 | Language-Content Mismatch | hybrid | has_code_snippet | P2 | ✗（基线） |
| QC-1.1 | Undefined Name Reference | program | has_code_snippet | P1 | ✓ |
| QC-1.2 | Invalid Import | program | has_import | P2 | ✓ |
| QC-1.3 | Deprecated API Usage | hybrid | has_api_call | P2 | ✓ |
| QC-1.4 | Type Mismatch | program | has_code_snippet | P2 | ✓ |
| QC-2.1 | Unclosed File Handle | program | has_file_handle | P1 | ✓ |
| QC-2.2 | Unreleased Network Connection | program | has_network_conn | P2 | ✓ |
| QC-2.3 | Missing Exception Handling | program | has_high_risk_op | P2 | ✓ |
| QC-3.1 | Unused Import | program | has_import | P2 | ✓ |
| QC-3.2 | Missing Import | program | has_code_snippet | P1 | ✓ |
| QC-3.3 | Hardcoded Demo Value | program | has_literal | P2 | ✓ |
| QC-4.1 | Snippet-Artifact Declaration Mismatch | hybrid | has_code_snippet | P1 | ✓ |
| QC-4.2 | Snippet-Body Version/API Drift | hybrid | has_code_snippet | P2 | ✓ |

> 计数说明：5 基线门（QC-0，entry gate）+ 12 检查项（QC-1~4）。`has_code_snippet` = 工件内嵌代码片段（本域存在性前提）；`has_import`/`has_api_call`/`has_file_handle`/`has_network_conn`/`has_high_risk_op`/`has_literal` 为片段内构造事实（观察"片段里有没有该构造"，非"是否已声明"，防点1悖论）。QC-1.2/1.3 受依赖上下文规则约束（外部输入缺→Not Executed）。

## 3. 模型判定要点

> 本域**无纯 model 项**。hybrid 项的模型确认部分见下。

### 3.1 纯 model 项

无。

### 3.2 hybrid 项的模型确认部分

> **skill 端：本节即完整判定要点，无程序初筛前置。**「关键词匹配是模糊信号」等描述的是 CLI / platform 的初筛路径；skill 全模型推理、不执行 §4，必须自行完成语义判定，不得视为"已筛过"，也不得据此判 N/A。

| ID | model_prompt（确认要点） |
|---|---|
| QC-0.5 | 确认 fence 声明语言与片段内容语法是否真不匹配（关键词匹配是模糊信号，需语义核实） |
| QC-1.3 | 对照 API 版本库确认该调用是否确属 deprecated/removed；版本库缺失时记 Not Executed |
| QC-4.1 | 确认片段调用/参数与所属工件自身声明（Tool properties/required、Skill/Prompt 字段名）是否真矛盾 |
| QC-4.2 | 确认片段与所属工件声明的 version/dependency/API 是否真漂移（陈旧示例） |

## 4. 程序判定项（program-check 代码块）

> **CLI / platform 专用：skill 不解析、不执行本代码块**（skill 全模型推理，不消费 `check_engine` 与 `program_rule`）。程序引擎只 parse 本代码块。`rule` 字段为**判定语义示意**（非最终可执行定义，程序级实现后续补）。涵盖纯 program 项 + hybrid 项的初筛规则。

<!-- program-check -->
```json
{
  "domain": "code-contract",
  "version": "v2",
  "note": "程序判定项 + hybrid 初筛规则。rule 为语义示意。",
  "checks": [
    { "id": "QC-0.1", "summary": "片段无法按声明语言解析（语法错误）" },
    { "id": "QC-0.2", "summary": "代码块缺语言标识（如 ```python）" },
    { "id": "QC-0.3", "summary": "片段缺必要 import 或函数体被 ... 截断（示意片段豁免）" },
    { "id": "QC-0.4", "summary": "代码围栏开/闭不匹配，或被代码内容吞掉闭合围栏" },
    { "id": "QC-0.5", "summary": "围栏声明语言与内容关键词不符（是否真不匹配由模型确认）" },
    { "id": "QC-1.1", "summary": "AST 解析 + 名称解析：引用未定义名称" },
    { "id": "QC-1.2", "summary": "import 语句引用的模块不在标准库/依赖清单（依赖清单缺失→Not Executed）" },
    { "id": "QC-1.3", "summary": "API 签名命中 deprecated 版本库（版本库缺失→Not Executed，确认由模型）" },
    { "id": "QC-1.4", "summary": "字面量类型推断：参数类型明显不兼容" },
    { "id": "QC-2.1", "summary": "open()/plumber.open() 无 with 或 close()" },
    { "id": "QC-2.2", "summary": "连接构造器（HTTPSConnection 等）无 context manager 或 close()" },
    { "id": "QC-2.3", "summary": "高风险调用（file/network/DB）无 try/except 块" },
    { "id": "QC-3.1", "summary": "import 提取 vs 引用计数：import 了但从未引用" },
    { "id": "QC-3.2", "summary": "引用提取 vs import 匹配：引用了但未 import" },
    { "id": "QC-3.3", "summary": "弱凭证/机器特定值模式（连续数字/xxx/changeme/本地路径/内网IP）" },
    { "id": "QC-4.1", "summary": "片段符号提取 vs 所属工件字段/property 匹配（是否矛盾由模型确认）" },
    { "id": "QC-4.2", "summary": "片段 API/版本引用 vs 工件正文声明匹配（是否漂移由模型确认）" }
  ]
}
```
<!-- /program-check -->

## 5. Tombstone 记录

无。Code Contract 域源规范未包含 merged / transferred 项。

## 6. 打分字段说明（platform 专用）

- 本域源规范**无显式打分章节**；severity 为扁平 P0/P1/P2，沿用 `_meta.md` 全局权重 `P0:P1:P2 = 5:3:1`。
- `计入打分` 列 = ✓ 的检查项进入分母；✗（QC-0 基线门）不计入。
- skill / CLI 不激活打分，但 score_weight 信息在索引表保留，供 platform 使用。
