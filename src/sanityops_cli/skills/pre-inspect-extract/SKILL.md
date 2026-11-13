---
name: pre-inspect-extract
version: 1.3.1
owner: DeepLogic AI Labs
description: 触发词：pre-inspect-extract / deeplogic-extract / artifact extraction / 工件提取 / 只提取。运行于 deeplogic-inspect-lite 之前的预检查提取层。在用户提交的任意文档中查找逻辑工件（System Prompt / Skill / Tool Schema），逐一切分，剥离承载它们的代码或标记外壳，必要时从源码逐字段重建 Schema，使用逐字证据标注每个工件的完整度，并判定每个工件的 L（AC-L / OR-L）。只提取，不判断缺陷。输出两层 IR（对象 + 引用）供检查阶段使用。当你需要先从文档中提取逻辑工件再进行缺陷检查时使用。
license: CC BY-SA 4.0
changelog: http://192.168.1.199:8080/deeplogic/deeplogic-inspect-lite/releases
---

# 预检查提取层（pre-inspect-extract）

## 0. 术语表（先读本节）

本文件中的词语严格采用以下含义，不作其他解释。

| 术语 | 含义 |
|---|---|
| **工件（artifact）** | Agent 运行时可以加载的三类对象之一：System Prompt、Skill、Tool Schema |
| **载体（carrier）** | 包裹工件的代码或标记，例如 `f"""..."""`、反引号模板字符串、``` 围栏 |
| **脚手架（scaffolding）** | 文档中的非工件内容：元数据、评估维度、备注等 |
| **逐字复制（verbatim copy）** | 逐字复制原文，只去掉外层代码壳 |
| **组装（assembly）** | 没有以可加载 JSON 形式存在的 Schema；从源码逐字段复制并组装 JSON Schema |
| **完整原文（full original）** | 通过逐字复制得到的完整文本，可直接检查 |
| **原文 · 变量未展开** | 通过逐字复制得到，但 Prompt 中存在会展开为规则的未展开变量 |
| **组装件（assembled）** | 从代码组装出的 Schema，不是逐字原文 |
| **不完整件（incomplete）** | 工件缺少其类型所需的基础字段——Tool 缺少 `inputSchema`、Skill 缺少正文，或 Prompt 无法形成完整指令 |
| **摘要（summary）** | 经过总结 / 转写 / 截断，无法与原文完整匹配 |
| **不可检查（not inspectable）** | 无法提取；跳过并记录原因 |
| **完整度层级** | 上述六个标签的统称 |
| **跳过检查** | 因数据不可靠，本次不判定某项检查（不是 FAIL） |
| **AC-L** | Agent 复杂度等级——Agent 有多复杂（L1 单轮 / L2 多轮 / L3 复杂；L4 多 Agent 保留）。决定 Prompt 域的严重度（P）。 |
| **OR-L** | 操作风险等级——操作风险有多高（L1 只读 / L2 可恢复写入 / L3 不可逆）。决定 Skill/Tool 域的严重度（P）。 |
| **提取类别（extraction class）** | E1 直接可读 / E2 包裹在代码中 / E3 需要组装 / EX 无法识别——表示工件如何被承载，由 §5 判定。 |
| **L 判定** | 逐工件分类为 AC-L / OR-L，在此一次性完成并向下传递。L 只决定严重度（P），绝不决定“是否检查”。 |
| **IR** | 中间表示（Intermediate Representation）——本层结构化输出：对象层 + 引用层，并带 L 标签；宿主可写文件时落盘，同时保留在上下文中。 |
| **对象层** | IR 两层之一——实际提取出且带完整签名的工件（多少个 P / S / T）。 |
| **引用层** | IR 两层之一——被提及 / 依赖但尚未形成提取对象的引用。 |

## 1. 本 Skill 的定位

这是一个纯 Prompt、零依赖的**预检查提取** Skill，运行于 `deeplogic-inspect-lite` 之前。它将用户提交的任意文档转换为“可检查工件 + 逐字证据”。

它只提取、只分类、只标注完整度。**不判断缺陷**——PASS/FAIL 属于后续七阶段检查的职责。

四项不可违反的原则：

1. **来源文档只读。** 绝不重写输入。
2. **宁可检查不了，也不强行判定。** 无法识别时标为“不可检查”并记录原因；绝不编造字段、猜测缺失内容，绝不把载体误当成工件。
3. **可靠性来自逐字复制与对照原文自证**，而不是解析器（本 Skill 无脚本）。
4. **确定性优先。** E1（直接可读）必须无歧义地逐字提取；只有 E2/E3 允许模型判断，且每次判断都必须记录为证据。相同输入必须能通过忠实逐字复制复现，并对照来源证据自检；不声称字节级确定性（无校验和、无行号——§9）。

## 2. 输入与输出

**输入**：用户提交的一份文档；文档大小受与检查阶段相同的单次运行总预算约束——最多 200,000 tokens（这是估算值，模型无法精确计数；宿主窗口较小时按比例缩减）。超限时应拆成多轮提取，或只提取完整可读部分并标记为“摘要”。

**输出**：两层中间表示（IR），规模与输入工件数量成正比（每个工件一个块），不得额外膨胀。宿主可写文件时，IR **落盘为文件**（供审计及 CLI / platform 复用；无写权限时的降级方式见 §11），同时**保留在上下文中**（供串联检查立即读取）。

当文档中**没有任何工件**（全部为引用文件 / 脚手架）时，输出空对象层与完整引用层，将摘要标记为 `no artifact extracted`，并令 `ir-core.objects = []`。这是正常结果，不是失败。

- **提取摘要**（顶部）：Agent 归属声明（单 Agent / 待确认）、工件总数、按类型计数、不可检查数量及逐项原因、完整度分布、L 分布。
- **对象层**：每个提取工件一个块，包含类型、名称、完整度、**L**、提取类别、来源位置、提取方法、逐字证据。
- **引用层**：被提及 / 依赖但未形成提取对象的内容。
- **`ir-core` 块**：对象层与引用层的机器可读核心，采用冻结的 ir-core v1 结构（§11：`ir_version`、`objects[].{type,name,completeness,L,source,mismatch}`、`not_inspectable[]`、`references[].{name,referenced_by,relationship}`），以固定 JSON 块承载，便于 CLI / platform 直接解析。

## 3. 文档内容的四种类别

| 类别 | 是什么 | 如何处理 |
|---|---|---|
| **工件** | 本身是 Prompt / Skill / Tool Schema | 送入检查 |
| **载体** | 包裹工件的代码或标记 | 剥离外壳，逐字复制内容 |
| **脚手架** | 元数据、评估维度、评分标准、测试建议、备注等 | 丢弃 |
| **引用文件** | 纯代码或纯数据，不含可提取工件 | 跳过 |

> 载体不是工件。`def f(...): return f"""..."""` 是载体；其中的字符串才是工件。

## 4. 七步流程

```text
切分 → 判定类型 → 判定提取类别 → 提取 → 判定完整度 → 判定层级（L）→ 记录证据
```

### 4.1 切分

切分为候选对象，丢弃脚手架。

- 脚手架标题按**语义**匹配，而非精确英文串——`## 元数据` 等同于 `## Metadata`，其余同理：`## Metadata`、`## Evaluation Dimensions`、`## Scoring Criteria`、`## Test Suggestions`、`## Notes`、`## Source Profile`。
- 每个 `### N. xxx`、每段具有结构签名的文本、每个顶层代码围栏块，都是一个候选对象。**单个围栏仍可能承载多个工件**（包含多个工具的 JSON 数组、包含多个 `Tool(...)` 调用的 `.py`）：切出围栏后，若其中存在多个独立工件，按元素再次切分，并在摘要计数中逐一报告。

**“结构签名”的最小定义。** 文本块至少出现以下一项时，才是候选对象：
  - 指令语义（祈使句 / 规则 / 角色指令）→ Prompt；
  - `name` + `description`，或 `parameters` / `inputSchema` / `input_schema` / `function.parameters` → Tool；
  - 带 `name` + `description` 的 front matter，且其后有正文 → Skill。

文档式文本**不是**候选对象：`## Skills` 列表（例如 `- browser: search docs`）只是*描述*能力，裸函数调用（例如 `await fetchTickets({...})`）只是*调用*工具——二者都不是可加载工件。将此类文本记录为输入说明并跳过，绝不切分成 Prompt。

**必须报告工件数量**：切分后明确说明“本文件有 N 个候选对象”，并逐一命名。一个文件经常包含多个工件（一个 `.py` 中两个 `Tool(...)`、一个 `.ts` 中两个 prompt 常量，都是两个工件）。**漏掉一个片段就是漏掉一次检查。** 不得使用“若干”或“多个”含糊表述。

**切分时检测跨对象引用（引用层）**：记录 Prompt / Skill 提及为依赖、但自身没有形成对象的每个具名内容。记录四类引用：
  1. **tool call**——Prompt/Skill 调用逐字工具名，但未提供该 Tool Schema（例如 `call search_tool`）；
  2. **skill dep**——Prompt/Skill 调用另一个逐字 Skill 名，但未提供该 Skill；
  3. **prompt var**——会展开为规则的变量（见 §5 E2），且其定义位于输入中；
  4. **file ref**——工件依赖的具名文件（例如“参见 rules.md”）。
这些内容进入**引用层**（§11 输出），供后续跨对象检查捕获“被引用但缺失”。像“query the database”这样的泛化文本**不**进入引用层——只有具体、具名的依赖才算。

### 4.2 先判类型，再判提取类别（本小节承载七步中的两步）

对每个候选对象，先按结构签名（§4.1）判定其**类型**（Prompt / Skill / Tool Schema），再判定其**提取类别**（E1 / E2 / E3 / EX，§5），并分别说明依据（观察到的结构特征）。

当一个文本块命中多个签名时，按以下顺序处理并记录最终决定者：带 `name` + `description` 且有正文的 front matter（`---`）→ Skill；schema 形态（`parameters` / `inputSchema` / `input_schema` / `function.parameters` / `type: object` + `properties`）→ Tool；否则为指令性文本 → Prompt。首个匹配者生效。

### 4.3 提取

两种方法：**逐字复制**与**组装**，见 §6。

### 4.4 判定完整度

判断是否可送入检查，以及应标记为哪个完整度标签，见 §7。

### 4.5 判定层级（L）

对每个成功提取的工件判定其 L（Prompt 用 AC-L，Skill/Tool 用 OR-L），见 §8。只有具备可用提取结果的工件才获得 L；“不可检查”对象不获得 L。

### 4.6 记录证据

见 §9。

## 5. 提取类别

### E1——可直接读取

工件以可加载形式存在：

- ` ```markdown ` / ` ```text ` / ` ```json ` 围栏中的完整工件。
- 无围栏但**按类型**结构完整：Skill = `name` + `description` front matter，**且其后有正文**；Tool = `type: object` + `properties` + `required`（或 `parameters` / `inputSchema` / `input_schema` / `function.parameters`）。
- JS/TS 对象字面量 `{ name: "...", description: "...", inputSchema: {...} }`、`input_schema: {...}` 或 `parameters: {...}`，且其值已是 **JSON 字面量**（双引号字符串、`true` / `false` / `null`）。
- 纯 JSON Schema（无 `name` → 记录 `name = (unnamed)`，注明“来源未提供名称”；绝不编造名称）。
- YAML 形式 Schema，或 JSON 对象中的 `"system": "..."` 字符串字段（字段值才是工件）。

Python `Tool(name=..., description=..., inputSchema={...})` 调用或裸 Python dict 字面量**不属于** E1：Python 字面量语法（`'...'`、`True` / `None`、尾随逗号）不是 JSON，因此该 dict 必须按 §6.1 的逐字段转写处理——那属于 E3，不是逐字复制。

**Skill 正文边界。** Skill 正文是 front matter 之后的全部内容，直到文件末尾或下一个 front matter 块。只有 front matter（无正文）属于**不完整** Skill，不是完整原文。

→ **逐字复制**。

### E2——包裹在代码中

由代码承载的字符串，**只有**可识别为三类工件之一时才是工件（§4.1 结构签名）：指令语义 → Prompt；`name`+`description` / `parameters` / `inputSchema` / `input_schema` / `function.parameters` → Tool；front matter + 正文 → Skill。日志字符串、错误消息、配置字符串和普通返回值属于**引用文件**——跳过。存在载体 ≠ 存在工件。

当承载文本确为工件时，它是被代码包裹的完整文本。**不要枚举语法；只判断文本是否由代码承载**：

- Python：`f"""..."""`、`"""..."""`、普通 `"..."`、**docstring**（如 `dspy.Signature` 类 docstring）、**函数返回的字符串**。
- TypeScript / JavaScript：反引号模板字符串、普通引号字符串、箭头函数返回的字符串、对象属性中的字符串。
- Jinja 模板（`{{ }}` 是运行时插值；模板文本本身才是工件）。
- Go raw string（反引号）、Ruby heredoc、Java text block——同一规则：字符串内容才是工件，外壳应剥离。

→ **逐字复制**：取字符串内容，去掉赋值语句、函数签名、`return`、反引号；反转义；变量保持原样。

> 不要逐种语法枚举。`f"""`、反引号、`"..."`、docstring、`return` 的区别只在外壳如何剥离，而不在是否属于 E2。此前枚举语法曾导致 docstring 与普通字符串情形被漏掉。

**检查每个变量**（包括 Jinja `{{ }}`）。判断依据**不是变量名**，而是变量定义能否在输入中定位，以及其内容是否为指令：

| 情形 | 处理方式 |
|---|---|
| 内容是运行时数据（`{local_tz}`、`{date.today()}`、`{context}`、`{question}`）——无论定义能否定位 | 原样保留，标记“完整原文” |
| 定义**可定位**，且内容是规则句（`{reference_prompt}`、`{tone_prompt}`） | 追踪定义；将其作为“待展开规则”记录到**引用层**（§4.1）。工件本身已逐字完整复制，因此完整度保持**完整原文**——展开内容位于引用层，不进入完整度标签 |
| 定义**不可定位**，但变量名可观察地表示规则——名称包含 `rule` / `policy` / `instruction` / `prompt`，或变量直接插值进指令句 | 标记“原文 · 变量未展开”，说明是哪个变量以及会展开成多少条指令 |
| 定义**不可定位**，且没有任何规则信号 | 原样保留，标记“完整原文” |

写在变量内的规则不存在于字面字符串中。能追踪定义时就追踪（完整度保持“完整原文”）；只有无法追踪且名称可观察地表示规则时（上述关键词测试），才降级为“原文 · 变量未展开”。未追踪却标为“完整原文”，会让“未声明参考规范”等检查错误失败，尽管来源文档实际已声明。

### E3——Schema 只存在于代码中

需要**组装**后才能成为可加载工件。**E3 只有一个判定规则**：参数类型、描述与约束全部以字面量形式存在于来源中时，才可组装；若它们在运行时推断，或藏在无法转写的标签中，则属于 EX。

| 来源形式 | 特征 |
|---|---|
| Zod `z.object({...})` | 约束写在链式调用中；`.refine()` 无法转换为 JSON Schema |
| Python `Tool(...)` + `inputSchema={...}` / `parameters={...}` dict 字面量 | Schema 只以 Python 字面量存在，不是 JSON——按 §6.2 逐字段转写 |
| Python 装饰器 `@mcp.tool()` + 类型注解 + docstring | 类型来自注解、默认值来自签名、描述来自 `Args:` 段 |
| Go builder `mcp.NewTool(...)` + `WithString/Required/DefaultString/Description` | 参数均为字面量 |

→ **组装**，见 §6.2。

### EX——无法识别

- 没有结构签名、没有围栏，无法判断是否包含工件。
- 动态注册，没有字面 Schema（`server.tool(func, name=..., output_schema=...)`）。
- 只有注册列表（`{"fn": "...", "tags": [...]}`、`manifest.json` 条目），没有 `inputSchema` / `parameters`。
- Go `type Xxx struct` + tags——若字段类型与 validate tags 均为字面量且形式已在 §6.2 列出，则可**组装**；只有类型靠推断或标签无法转写时，才是 EX（不可检查）。

→ 标记“不可检查”，记录原因。

**例外**：候选对象有 `name` + `description`，但缺少其类型其余基础字段时，不属于“无法识别”，而是**不完整**工件。标记“不完整件”，提取已有字段，并说明缺失内容（Tool：“文档未提供 schema”；Skill：“无正文”）。有 `name` 但缺 `description` 的候选对象同样属于**不完整件**——Tool 必须先有 `description` 才能运行 QD-T 检查。没有 `name` 的纯 JSON Schema 不是不完整件：它仍是完整原文，且 `name = (unnamed)`（§5 E1）。缺失的基础字段只记录为文档层面事实，不判为产品缺陷。对 Prompt 而言，“不完整件”表示文本完全不含指令（例如仅有裸占位符或变量），或由多个片段组装而成但输入中缺少组装逻辑（§10）。

## 6. 提取规则

### 6.1 逐字复制

适用于 E1 与 E2。

**目标格式。** 逐字复制保留来源自身语法，只去掉外壳；它**不**承诺结果一定是合法 JSON。当目标为 JSON Schema、但来源尚非 JSON（带单引号键的 Python dict 或 JS 对象字面量、`True`/`None`、尾随逗号等）时，该来源形式属于提取类别 E3——转到 §6.2 做逐字段字面量转写。

1. 逐字复制；不重写、不润色、不补全。
2. 只去外壳（赋值语句、函数定义行、`return`、围栏标记、`export const X =`、反引号）；外壳内部内容保持不变。Python 多行字符串应去除公共缩进（dedent）。嵌套围栏只剥最外层，内层围栏标记作为工件文本保留。
3. **仅在字符串字面量语义要求时**反转义（`\n` → 换行）；在 raw string / regex 中保留字面 `\n`。变量（`{var}`、`{{ var }}`）原样保留，不替换。
4. 结果必须与原文完整匹配；不匹配 → 标记“摘要”。
5. 按 §5 E2 的“检查每个变量”规则检查每个占位符。

### 6.2 组装

适用于 E3。**只重组，不翻译。**

**非 JSON 字面量的逐字段转写。** 当目标为 JSON Schema、但来源是 Python dict 或 JS 对象字面量且尚非 JSON（例如使用单引号键的 `inputSchema={...}`、`True`/`None`、尾随逗号）时，逐字段转写为 JSON：单引号 → 双引号，`True`/`None` → `true`/`null`，去掉尾随逗号；非字面量值标记为“来源值，非 schema 值”。记录 `method = assembly`，不是 `verbatim copy`。

1. 逐字段复制源码中所有已有字面内容：`name`、`description` / `.describe("...")`、每个参数的键与描述、`enum` 值、`required` 列表、`default` 值。
2. 按下列规则转换约束：

| 来源形式 | JSON Schema |
|---|---|
| 字符串上的 Zod `.max(n)` / `.min(n)` | `maxLength` / `minLength` |
| 数字上的 Zod `.max(n)` / `.min(n)` | `maximum` / `minimum` |
| 数组上的 Zod `.max(n)` / `.min(n)` | `maxItems` / `minItems` |
| Zod `.int()` | `type: integer` |
| Zod `.enum([...])` | `enum` |
| Zod `.optional()` | 不放入 `required` |
| Zod `.default(v)` | `default` |
| Zod `.regex(re)` | `pattern` |
| Zod `.email()` / `.url()` / `.uuid()` | `format: email` / `uri` / `uuid` |
| Zod `z.record(k, v)` | `type: object` + `additionalProperties` |
| Zod `z.tuple([...])` | `type: array` + 固定 `items` |
| Zod `z.union([...])` / `z.literal(v)` | 所有备选均为字面量时转为 `enum` / `const`；否则标记“union 无法表达，仅存在于来源” |
| Zod `z.any()` / `z.unknown()` | 不写 `type` 关键字 |
| 字段内的嵌套 `z.object({...})` | 递归处理：该字段成为带自身 `properties` 的嵌套 `type: object` |
| Python `str/int/float/bool` 注解 | `string/integer/number/boolean` |
| Python `List[X]` 注解 | `type: array` + `items` |
| Python `= None` 默认值 | 不放入 `required` |
| 无默认值的 Python `Optional[X]` | 放入 `required`（可为 null） |
| Python `Literal[a, b]` | `enum` |
| Python `Dict[str, X]` | `type: object` + `additionalProperties` |
| Python `Set[X]` | `type: array` + `uniqueItems: true` |
| Python `Tuple[X, Y]` | `type: array` + 固定 `items` |
| Python `Union[X, Y]` / `X \| Y` | 简单情形用 `anyOf`；否则标记“union 无法表达，仅存在于来源” |
| Python `Any` | 不写 `type` 关键字 |
| Python 无默认值 / 有默认值 | 放入 `required` / 记录 `default` |
| Python docstring 首段（`Args:` 之前） | Tool 顶层 `description` |
| Python docstring 的 `Args:` 段 | 对应参数的 `description` |
| Go `WithString/WithNumber/WithBoolean` | `type` |
| Go `WithArray(...)` / `WithEnum(...)` / `WithObject(...)` | `type: array` / `enum` / `type: object` |
| Go `WithArray(WithString(...))` | `type: array` + `items: { type: string }`（元素类型跟随内层 builder） |
| Go `WithObject(...)` 子字段 | 带自身 `properties` 的嵌套 `type: object` |
| Go `Required()` | 放入 `required` |
| Go `DefaultString/DefaultNumber` | `default` |
| Go `Description(...)` | `description` |
| Go `json:"name"` 标签 | 属性键 |
| Go `validate:"required"` / `validate:"omitempty"` | 放入 `required` / 不放入 `required` |
| Go `validate:"min=N,max=N"` | 数值字段 → `minimum` / `maximum`；字符串字段 → `minLength` / `maxLength`（按字段的 Go 字面类型判断） |
| Go `validate:"oneof=a b"` | `enum` |
| Go `validate:"email"` / `validate:"url"` | `format: email` / `format: uri` |
| Go 字段类型 `string/int/int64/float64/bool` | `string/integer/integer/number/boolean` |
| Go 字段类型 `[]T` / `map[string]T` | `type: array` + `items` / `type: object` + `additionalProperties` |
| Go 指针字段 `*T` | 不放入 `required`，除非标签为 `validate:"required"` |

> 上表未列出的来源约束一律**不进入 schema**——记录为证据，绝不为它编造关键字。

3. 包装为 `{ "type": "object", "properties": {...}, "required": [...] }`。
4. **不得添加源码中不存在的字段级约束。** 若源码未为某属性写 `type`，不得为该属性添加 `type` 关键字。（规则 3 中的根 `"type": "object"` 是组装外壳，不是来源字段。）
5. `.refine()` / `.superRefine()` / 自定义校验无法转换为 JSON Schema；**不得编造等价约束**——写明“源码中通过 refine 实现，未进入 schema”。
6. 框架注入参数不是用户参数，**必须移除**：Python MCP `ctx: Context`、FastAPI `Depends(...)`、LangChain `InjectedToolArg`、`self` / `cls`，以及运行时配置对象。
7. 为每个字段附上来源片段。

### 6.3 description 字段不得丢失

`description` / `.describe()` / docstring 是 Tool Schema 检查的核心依据，也是组装过程中最容易丢失的内容。

- 来源有描述、结果没有 → 将整个工件标为“组装件”，并写明“description 字段有丢失风险”。
- 来源无描述 → 结果也不得有描述；**不得自行编写**。

## 7. 完整度层级

六个标签作用于整个工件，不按字段细分。它们构成全序（越靠前越可检查）：

```text
完整原文  >  原文 · 变量未展开  >  组装件  >  不完整件  >  摘要  >  不可检查
```

“将完整度下降一级”（§9）表示沿此顺序向下移动一步。

| 标签 | 含义 | 可执行检查 |
|---|---|---|
| **完整原文** | 逐字复制且完整 | 全部 |
| **原文 · 变量未展开** | 逐字复制，但存在会展开为规则的未展开变量 | 除依赖这些变量的检查外全部执行 |
| **组装件** | 从代码组装的 Schema | 结构与矛盾检查全部执行；“字段缺少某约束”逐字段判断（见下文） |
| **不完整件** | 工件缺少基础字段 | 只检查实际提供的字段 |
| **摘要** | 经过总结 / 转写 / 与原文不匹配 | 只检查矛盾，不检查“缺少什么” |
| **不可检查** | 无法提取 | 不检查，仅记录原因 |

**“组装件”如何判断缺失约束**：查看证据。

| 证据情况 | 结论 |
|---|---|
| 来源片段覆盖字段的完整写法（完整链式调用 / 完整签名 / 完整 builder 调用 / 完整 struct 定义） | 可判定。来源确实没写 → 真正缺失 |
| 来源片段只覆盖部分，或边界不清晰 | 跳过该检查，标记“不确定” |

是否执行检查取决于该字段是否被完整复制，而不是是否属于组装件。

**`.refine()` 单独观察**：`.refine()` 通常不会进入运行时生成的 JSON Schema。因此，若 description 承诺某约束（例如“最多 50 个词”）但 schema 中没有对应关键字，这是**候选 QD-T-4.5，应移交检查阶段**（仅记录证据——本层绝不输出 PASS/FAIL），不得以“无法组装”为由抹除。措辞示例：“description 声明 X，schema 无对应约束；源码中 X 通过 refine 实现，通常不会进入 JSON Schema。”

## 8. 层级判定（L）

本层一次性判定**每个工件的 L**（复杂度 / 操作风险层级）并向下传递。L 是分类，不是缺陷等级。它只决定后续检查的严重度（P），**不决定是否执行检查**（后者由后续结构事实门决定，而非 L）。

### 8.1 两个维度保持独立

| 维度 | 判断内容 | 层级 | 适用对象 |
|---|---|---|---|
| **AC-L** | Agent 有多复杂 | L1 单轮 / L2 多轮 / L3 复杂（L4 多 Agent 保留） | System Prompt |
| **OR-L** | 操作风险有多高 | L1 只读 / L2 可恢复写入 / L3 不可逆 | Skill、Tool Schema |

两个维度**在引擎层保持独立**——绝不合并为一个数字，因为合并会破坏严重度查询（例如“AC-L1 + OR-L3”无法表达为单一层级）。

### 8.2 AC-L 判定（Prompt）

读取 Prompt 内容并判断复杂度。多轮与单轮在静态 Prompt 中往往**不可见**——只依据可观察信号判断：

- **AC-L1（单轮）**：一问一答；无工具、无多轮状态。
- **AC-L2（多轮）**：多轮对话；每轮可独立理解。可观察信号：`history` / `turn` / `session` 变量、“previous messages”字段，或明确的往返交互契约。
- **AC-L3（复杂）**：跨步骤规划 / 反思 / 工具编排。可观察信号：工具调用循环、plan→execute→reflect 指令，或显式多步骤编排。
- **L4（多 Agent）**保留；多 Agent 规模确定前不得输出 L4。
- **无可观察信号**表明多轮 / 复杂度 → 输出 `L = undetermined`；不得猜测。

### 8.3 OR-L 判定（Skill / Tool）

读取 Skill/Tool 内容，按其可执行的最危险操作判断操作风险：

- **OR-L1（只读）**：查询 / 搜索 / 读取；无写入。
- **OR-L2（可恢复写入）**：创建 / 更新 / 发送，且可纠正或撤销。
- **OR-L3（不可逆）**：删除 / 转移 / 不可逆的外部通知。

**绝不静默降级为 OR-L1。** 未声明工具调用的 Skill/Tool **不会自动**成为 OR-L1：先扫描其正文与 schema 语义中的写操作动词（delete / transfer / send / overwrite / deploy / write）。任何写命中 → 按其中最高风险操作判定。只有存在正向读动词（query / search / read）且**没有**写动词时，才是 OR-L1。完全没有任何动词的 Skill/Tool 保持 `undetermined`（§8.5）。

### 8.4 产品层：一个统一标签

面向用户输出时，将两个维度折叠为**每个工件一个统一标签**（合并只发生在展示层，不发生在计算层）：

- Prompt → 展示其 AC-L。
- Skill / Tool → 展示其 OR-L。
- （Permission 是横切关注点，由后续流程逐权限项处理——不在本层处理。）

### 8.5 不确定时

- 若无法从现有内容判断 L（例如“摘要”保真度），输出 `L = undetermined`，由后续结构事实门决定“是否检查”；后续按 `_meta.md` §4 将严重度报告为 `—`（参考级），并记录“L 未定”，不得随意选择 L 列。
- L **不**决定“是否检查”，但**会**决定结果是否进入缺陷分级：`∅`（该 L 不分配 P）与 `undetermined`（后续报告为 `—`）都会将发现降为参考级。因此错误的 L **可能压制缺陷**——L1 误判可把 P0/P1 发现变成不参与分级的参考备注。绝不把错误 L 描述为无害。

## 9. 证据

不要使用行号（模型引用不可靠）或校验和（无脚本）。使用**摘录自证**。

每项输出包含：

- **位置**：来源文件 + 章节标题（如 `## Original Artifact Content` / `### 2. Input schema`）。
- **方法**：逐字复制 / 组装 / 摘要。
- **逐字摘录**：逐字复制情形给出首尾片段；组装情形给出每个字段的来源片段（`name` → 来源、`description` → 来源、每个参数 → 来源）。

自证标准：不了解上下文的人仅凭证据就能在原文中找到每个要点。做不到时，将完整度下降一级（按 §7 顺序）。

**正确性标记（独立于完整度）。** 完整度说明*提取了多少*；正确性说明*提取结果是否可能出错*。当证据无法逐字段与原文匹配时，附加正确性标记——`verbatim mismatch`（逐字复制发生漂移）或 `assembly mismatch`（组装字段与来源不一致）——即使完整度标签仍为“完整原文”。这样审计才能区分“提取错误”与“检查错误”。

## 10. 文档内的 Agent 归属

**默认：一份文档 = 一个 Agent 的工件集。**

- 一份文档可包含同一 Agent 的多个工件（一个 Prompt + 多个 Tool）。
- 检测到多个 Agent 形态时（例如 6 个角色的套件），**不自动拆分，也不自动退回**：标记“Agent 归属待确认”，说明检测依据，并给用户两个确认选项——(a) 确认属于同一 Agent → 继续；(b) 声明它们是一组无关工件 → 交给检查阶段以集合模式逐个执行单工件检查。pre-inspect 不为用户做决定。

### 其余情形的处理

| 情形 | 处理 |
|---|---|
| 围栏未闭合 | 不猜结尾；标记“摘要” |
| 变量是运行时数据（`{local_tz}`） | 保留变量，标记“完整原文” |
| 变量会展开为规则，且定义可定位（输入中已定义 `{reference_prompt}`） | 保持“完整原文”，追踪定义，列出变量，并作为 `prompt var` 加入引用层 |
| 变量会展开为规则，且定义不可定位（输入中未定义 `{reference_prompt}`） | 标记“原文 · 变量未展开”，列出变量 |
| 多个片段由代码组装成最终 Prompt | 标记“不完整件”，写明“未提供组装逻辑” |
| 组装时字段与来源不匹配 | 将整体标为“组装件”，附加 `assembly mismatch` 正确性标记，并注明字段 |
| 怀疑 description 字段丢失 | 不执行相关检查，记录证据 |
| 怀疑存在多个 Agent | 标记“Agent 归属待确认”，输出确认选项 |
| 已总结 / 转写 / 无法干净切分 | 标记“摘要”或“不可检查” |

## 11. 输出格式

输出一份 Markdown 清单，结构为两层 IR：

1. **提取摘要**（顶部）：Agent 归属声明（单 Agent / 待确认）、工件总数、按类型计数、不可检查数量及逐项原因、完整度分布、L 分布。归属声明使用固定措辞，便于后续消费者可靠读取：`agent membership: single agent` 或 `agent membership: pending confirmation`（绝不使用自由改写）。
2. **对象层**：每个提取工件一个块：工件名称、类型、完整度、**L**、提取类别、来源位置、提取方法、逐字证据。“原文 · 变量未展开”必须列出未展开变量及内容摘要。
3. **引用层**：§4.1 检测到的每个跨对象引用：`引用名称 | 被谁引用 | 关系（tool call / skill dep / prompt var / file ref）`；泛化文本不进入此层。定义可定位的 `prompt var` 条目还必须携带**展开后的规则**——追踪到的定义文本，或指向其定义位置的锚点——使检查阶段能读取展开内容，而不只是变量名。
4. **不可检查列表**：单独列出，每项写明原因，不产生缺陷结论。
5. **`ir-core` JSON 块**：对象层、引用层与不可检查列表的机器可读核心（见下文），供 CLI / platform 解析。

### ir-core 块（机器可读核心）

将 IR 落盘为文件，并在文件中嵌入一个 `<!-- ir-core -->` JSON 块，只包含机器可读字段，使程序引擎无需读取人类证据即可解析 IR。

**ir-core v1 契约。** `ir_version` 为 `"1"`。`completeness` 是 §7 六个标签之一；`L` 是 `AC-L1` / `AC-L2` / `AC-L3` / `OR-L1` / `OR-L2` / `OR-L3` / `undetermined` 之一。`objects[]` 携带 `type` / `name` / `completeness` / `L` / `source` / `mismatch`；`source` 是章节标题（§9 位置），`mismatch` 是正确性标记或 null。“不可检查”对象**不**放入 `objects[]`——它们进入独立的 `not_inspectable[].{name,reason}`。`references[].relationship` 为 `tool call` / `skill dep` / `prompt var` / `file ref` 之一。

<!-- ir-core -->
```json
{
  "ir_version": "1",
  "objects": [
    { "type": "prompt", "name": "main_prompt", "completeness": "full original", "L": "AC-L2", "source": "## Original Artifact Content", "mismatch": null },
    { "type": "tool", "name": "delete_customer", "completeness": "full original", "L": "OR-L3", "source": "### 2. Input schema", "mismatch": null }
  ],
  "not_inspectable": [],
  "references": [
    { "name": "search_tool", "referenced_by": "main_prompt", "relationship": "tool call" }
  ]
}
```
<!-- /ir-core -->

**落盘**：由宿主模型（本 Skill 无脚本）将 IR 写为 Markdown 文件（默认名 `{input_basename}.ir.md`，放在输入文件旁或用户指定的输出目录），**同时**在上下文中保留副本供串联检查使用。文件是持久审计检查点；上下文副本是工作交接载体。若宿主无法写文件（无写权限 / 无文件系统），只保留上下文副本并将摘要标记为 `not materialized`——落盘**不是**成功提取的前置条件。

## 12. 本 Skill 不做什么

- 不重写、不修复、不规范化工件文本。
- 不判断 PASS / FAIL / 严重度（P0/P1/P2）。判定 L（AC-L / OR-L）是 L 分类，不是缺陷等级。
- 不跨 Agent 拆分或混合。
- 不编造字段、不编造约束、不编写缺失描述。
- 不把载体当工件，也不把脚手架当工件。
- 不将框架注入参数写成 Tool 参数（Python MCP `ctx: Context`、FastAPI `Depends(...)`、LangChain `InjectedToolArg`、`self` / `cls`）。

## 13. 交接给 deeplogic-inspect-lite

```text
原始文档 → [预检查提取层] → 两层 IR（对象 + 引用，每个对象带 L 标签）→ [七阶段检查]
```

预检查层不改变七阶段逻辑，只改变送入检查的内容——两层 IR（带 L 标签）替代扁平工件列表。IR 同时以上下文和工作区文件两种形式交接。“不可检查”对象会在最终报告中列为输入说明，不产生缺陷结论。
