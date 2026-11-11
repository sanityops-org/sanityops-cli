---
name: pre-inspect-extract
version: 1.3.1
owner: Sanity AI Labs
description: Trigger words: pre-inspect-extract / sanityops-extract / artifact extraction / 工件提取 / 只提取. Pre-inspection extraction layer that runs before sanityops-inspect-lite. Finds logic artifacts (System Prompt / Skill / Tool Schema) in any user-submitted document, segments them one by one, strips the code/markup shell that carries them, reconstructs the schema field-by-field from source when necessary, labels each artifact's completeness level with verbatim evidence, and determines each artifact's L (AC-L / OR-L). Extract-only, never judges defects. Outputs a two-layer IR (objects + references) for the inspection stage. Use when you need to first extract logic artifacts from a document before inspecting them.
license: CC BY-SA 4.0
changelog: https://github.com/sanityops-org/sanityops-inspect-lite/releases
---

# Pre-Inspection Extraction Layer (pre-inspect-extract)

## 0. Glossary (read this first)

The words in this file mean exactly the following. Nothing else.

| Term | Meaning |
|---|---|
| **artifact** | One of the three things an Agent runtime can load: System Prompt, Skill, Tool Schema |
| **carrier** | Code or markup that wraps an artifact, e.g. `f"""..."""`, backtick template strings, ``` fences |
| **scaffolding** | Non-artifact content in a document: Metadata, Evaluation Dimensions, Notes, etc. |
| **verbatim copy** | Copy the original text word-for-word, dropping only the outer code shell |
| **assembly** | There is no schema in loadable JSON form; copy fields out of the source one by one and assemble a JSON Schema |
| **full original** | Obtained by verbatim copy, complete, directly inspectable |
| **original · variable unexpanded** | Obtained by verbatim copy, but the prompt has unexpanded variables that expand into rules |
| **assembled** | A schema assembled from code, not the verbatim original |
| **incomplete** | The artifact is missing a base field its type requires — a Tool without `inputSchema`, a Skill without a body, a Prompt that cannot form a complete instruction |
| **summary** | Summarized / transcribed / truncated; cannot be matched to the original in full |
| **not inspectable** | Cannot be extracted; skip and record the reason |
| **completeness level** | The umbrella term for the six labels above |
| **skip a check** | Because the data is unreliable, a specific check is not judged this time (this is not a FAIL) |
| **AC-L** | Agent Complexity Level — how complex the agent is (L1 single-turn / L2 multi-turn / L3 complex; L4 multi-agent reserved). Feeds the Prompt-domain severity (P). |
| **OR-L** | Operation Risk Level — how risky the operations are (L1 read-only / L2 reversible write / L3 irreversible). Feeds the Skill/Tool-domain severity (P). |
| **extraction class** | E1 directly readable / E2 wrapped in code / E3 assembly-needed / EX unrecognizable — how the artifact is carried, decided in §5. |
| **L determination** | The per-artifact classification into AC-L / OR-L, done once here and handed down. It feeds severity (P) only, never "whether to check". |
| **IR** | Intermediate Representation — this layer's structured output: two layers (object + reference) plus L tagging, materialized to a file when the host can write one and also kept in-context. |
| **object layer** | One of the two IR layers — artifacts actually extracted with a full signature (how many P / S / T). |
| **reference layer** | One of the two IR layers — things mentioned / depended on but not formed as an extracted object. |

## 1. What this is

A pure-prompt, zero-dependency **pre-inspection extraction** skill that runs before `sanityops-inspect-lite`. It turns any user-submitted document into "inspectable artifacts + verbatim evidence".

It only extracts, only classifies, only labels completeness. **It does not judge defects** — PASS/FAIL is the job of the seven-stage inspection that follows.

Three inviolable principles:

1. **The source document is read-only.** Never rewrite the input.
2. **Rather not inspect than force a verdict.** If something is unrecognizable, label it "not inspectable" and record the reason; never fabricate fields, never guess missing content, never mistake a carrier for an artifact.
3. **Reliability comes from verbatim copy and self-evidence against the original**, not from a parser (this skill has no scripts).
4. **Determinism first.** E1 (directly readable) must be extracted word-for-word with no ambiguity; only E2/E3 allow model judgment, and every judgment must be recorded as evidence. The same input must be reproduced by faithful verbatim copy, self-checked against the source evidence; byte-level determinism is not claimed (no checksums, no line numbers — §9).

## 2. Input and output

**Input**: one user-submitted document; document size is bounded by the same run-total budget as the inspection stage — up to 200,000 tokens (an estimate, since a model cannot count tokens exactly; scale down proportionally on smaller host windows). If over the limit, split the extraction across rounds, or extract only the fully-readable part and label it "summary".

**Output**: a two-layer Intermediate Representation (IR), sized in proportion to the number of input artifacts (one block per artifact), with no extra inflation. The IR is **materialized to a file** when the host can write one (for audit and reuse by CLI / platform; §11 defines the no-write fallback) and also **kept in-context** (for the chained inspection to read immediately).

When a document contains **zero artifacts** (all reference files / scaffolding), output an empty object layer plus the full reference layer, mark the summary `no artifact extracted`, and set `ir-core.objects = []`. This is a normal result, not a failure.

- **Extraction summary** (top): agent membership declaration (single agent / pending confirmation), total artifact count, count by type, not-inspectable count and per-item reasons, completeness-level distribution, and L distribution.
- **Object layer**: one block per extracted artifact, each carrying type, name, completeness level, **L**, extraction class, source location, extraction method, and verbatim evidence.
- **Reference layer**: the things mentioned / depended on but not formed as extracted objects.
- **`ir-core` block**: the machine-readable core of the object + reference layers, in the frozen ir-core v1 shape (§11: `ir_version`, `objects[].{type,name,completeness,L,source,mismatch}`, `not_inspectable[]`, `references[].{name,referenced_by,relationship}`), carried in a fixed JSON block so CLI / platform can parse it directly.

## 3. Things in a document fall into four categories

| Category | What it is | What to do |
|---|---|---|
| **artifact** | Itself a Prompt / Skill / Tool Schema | Send to inspection |
| **carrier** | Code or markup that wraps an artifact | Strip the shell, copy the content verbatim |
| **scaffolding** | Metadata, Evaluation Dimensions, Scoring Criteria, Test Suggestions, Notes, etc. | Discard |
| **reference file** | Pure code or pure data, contains no extractable artifact | Skip |

> A carrier is not an artifact. `def f(...): return f"""..."""` is a carrier; the string inside is the artifact.

## 4. Seven-step flow

```
Segment → classify type → classify extraction class → extract → determine completeness → determine level (L) → record evidence
```

### 4.1 Segmentation

Cut into candidate objects, discard scaffolding.

- Scaffolding headings (match by meaning, not by exact English string — `## 元数据` equals `## Metadata`, etc.): `## Metadata`, `## Evaluation Dimensions`, `## Scoring Criteria`, `## Test Suggestions`, `## Notes`, `## Source Profile`.
- Each `### N. xxx`, each text passage with a structural signature, and each top-level code fence block is one candidate object. **A single fence may still hold multiple artifacts** (a JSON array with several tools, a `.py` with several `Tool(...)` calls): after cutting out the fence, re-split by element when it contains more than one independent artifact, and report each in the summary count.

**"Structural signature" — the minimal definition.** A text block is a candidate object when it shows at least one of:
  - instructional semantics (imperatives / rules / role instructions) → Prompt;
  - `name` + `description`, or `parameters` / `inputSchema` / `input_schema` / `function.parameters` → Tool;
  - front matter with `name` + `description` followed by a body → Skill.

Documentation-style text is **not** a candidate object: a `## Skills` list (e.g. `- browser: search docs`) only *describes* a capability, and a bare function call (e.g. `await fetchTickets({...})`) only *invokes* a tool — neither is loadable as an artifact. Record such text as an input note and skip it; never segment it into a Prompt.

**Must report the artifact count**: after segmentation, state explicitly "this file has N candidate objects" and name each one. A file often contains multiple artifacts (two `Tool(...)` in one `.py`, two prompt constants in one `.ts`, are two artifacts). **A missed segment is a missed inspection.** Do not accept "several" or "multiple".

**Detect cross-object references (reference layer)** while segmenting: record every named thing a prompt / skill mentions as a dependency but that is not itself present as a formed object. Four reference kinds are recorded:
  1. **tool call** — a prompt/skill calls a verbatim tool name with no tool schema present (e.g. `call search_tool`);
  2. **skill dep** — a prompt/skill invokes another verbatim skill name with no skill present;
  3. **prompt var** — a variable that expands into rules (see §5 E2) whose definition lives in the input;
  4. **file ref** — a named file the artifact depends on (e.g. "see rules.md").
These go to the **reference layer** (output in §11) so the downstream cross-object checks can catch "referenced but missing". Generic prose like "query the database" is **not** a reference-layer entry — only a concrete, named dependency counts.

### 4.2 Classify type, then extraction class (this subsection carries two of the seven steps)

For each candidate object, first determine its **type** (Prompt / Skill / Tool Schema) by structural signature (§4.1), then determine its **extraction class** (E1 / E2 / E3 / EX, §5), and state the basis (the structural feature you saw) for each.

When a block matches more than one signature, apply them in this order and record which one decided it: front matter (`---`) carrying `name` + `description` and followed by a body → Skill; a schema form (`parameters` / `inputSchema` / `input_schema` / `function.parameters` / `type: object` + `properties`) → Tool; otherwise instructional prose → Prompt. The first match wins.

### 4.3 Extraction

Two methods: **verbatim copy** and **assembly**, see §6.

### 4.4 Determine completeness

Decide whether it can be sent to inspection and which label to apply, see §7.

### 4.5 Determine level (L)

For each extracted artifact, determine its L (AC-L for Prompt, OR-L for Skill/Tool), see §8. Only artifacts with a usable extraction get an L; "not inspectable" objects get none.

### 4.6 Record evidence

See §9.

## 5. Extraction classes

### E1 — directly readable

The artifact exists in a loadable form:

- A complete artifact inside ` ```markdown ` / ` ```text ` / ` ```json ` fences.
- No fence but structurally complete **by type**: a Skill = `name` + `description` front matter **followed by a body**; a Tool = `type: object` + `properties` + `required` (or `parameters` / `inputSchema` / `input_schema` / `function.parameters`).
- JS/TS object literal `{ name: "...", description: "...", inputSchema: {...} }` or `input_schema: {...}` or `parameters: {...}` **whose values are already JSON literals** (double-quoted strings, `true` / `false` / `null`).
- A pure JSON Schema (no `name` → record `name = (unnamed)`, note "source has no name"; never invent one).
- A YAML-form schema, or a `"system": "..."` string field inside a JSON object (the field value is the artifact).

A Python `Tool(name=..., description=..., inputSchema={...})` call or a bare Python dict literal is **not** E1: Python literal syntax (`'...'`, `True` / `None`, trailing commas) is not JSON, so the dict must go through the field-by-field transcription in §6.1 — that is E3, not verbatim copy.

**Skill body boundary.** A Skill's body is everything after the front matter, up to the end of the file or the next front-matter block. A front matter alone (no body) is an **incomplete** Skill, not a full original.

→ **verbatim copy**.

### E2 — wrapped in code

A string carried by code is an artifact **only if it is recognizable as one of the three types** (§4.1 structural signature): instructional semantics → Prompt; `name`+`description` / `parameters` / `inputSchema` / `input_schema` / `function.parameters` → Tool; front matter + body → Skill. Log strings, error messages, config strings, and ordinary return values are **reference files** — skip them. Carrier presence ≠ artifact presence.

When the carried text is an artifact, it is complete text wrapped in code. **Do not enumerate syntax; only judge whether the text is carried by code**:

- Python: `f"""..."""`, `"""..."""`, plain `"..."`, **docstring** (e.g. a `dspy.Signature` class docstring), **a string returned by a function**.
- TypeScript / JavaScript: backtick template strings, plain quoted strings, a string returned by an arrow function, a string in an object property.
- Jinja templates (`{{ }}` is runtime interpolation; the template text itself is the artifact).
- Go raw strings (backticks), Ruby heredocs, Java text blocks — same rule: the string content is the artifact, the shell is stripped.

→ **verbatim copy**: take the string content, drop the assignment statement, function signature, `return`, backticks; unescape; keep variables as-is.

> Do not enumerate syntax case by case. `f"""`, backticks, `"..."`, docstring, `return` differ only in which shell to strip, not in whether this is E2. Enumerating syntax once caused docstring and plain-string cases to be missed.

**Examine each variable** (Jinja `{{ }}` included). The test is **not the variable name** — it is whether the variable's definition is locatable in the input and whether its content is instructional:

| Situation | How to handle |
|---|---|
| The content is runtime data (`{local_tz}`, `{date.today()}`, `{context}`, `{question}`) — whether or not its definition is locatable | Keep as-is, label "full original" |
| Definition **locatable** and the content is a rule sentence (`{reference_prompt}`, `{tone_prompt}`) | Trace the definition; record it as a "rule to expand" in the **reference layer** (§4.1). The artifact itself was copied verbatim and in full, so its completeness stays **full original** — the expansion lives in the reference layer, not in the label |
| Definition **not locatable** but the name observably signals rules — the name contains `rule` / `policy` / `instruction` / `prompt`, or the variable is interpolated directly into an instruction sentence | Label "original · variable unexpanded", state which variable and how many instructions it expands into |
| Definition **not locatable** and nothing signals rules | Keep as-is, label "full original" |

Rules written inside a variable are absent from the literal string. Trace the definition when you can (completeness stays "full original"); only when you cannot and the name observably signals rules (the keyword test above), downgrade to "original · variable unexpanded". Labeling "full original" without tracing would wrongly fail checks like "reference specification not declared" even though the source did declare it.

### E3 — schema exists only as code

Needs **assembly** to become a loadable artifact. **One rule decides E3**: an object qualifies for assembly when its parameter types, descriptions, and constraints all exist as literals in the source. If they do, assemble; if they are inferred at runtime or hidden in a tag you cannot transcribe, it is EX.

| Source form | Characteristic |
|---|---|
| Zod `z.object({...})` | Constraints written in chained calls; `.refine()` cannot be converted to JSON Schema |
| Python `Tool(...)` + `inputSchema={...}` / `parameters={...}` dict literal | The schema exists only as a Python literal, not as JSON — literal field-by-field transcription per §6.2 |
| Python decorator `@mcp.tool()` + type annotations + docstring | Types from annotations, defaults from the signature, descriptions from the `Args:` section |
| Go builder `mcp.NewTool(...)` + `WithString/Required/DefaultString/Description` | Parameters are all literals |

→ **assembly**, see §6.2.

### EX — unrecognizable

- No structural signature, no fence, cannot tell whether it contains an artifact.
- Dynamic registration, no literal schema (`server.tool(func, name=..., output_schema=...)`).
- Only a registration list (`{"fn": "...", "tags": [...]}`, `manifest.json` entries), no `inputSchema` / `parameters`.
- Go `type Xxx struct` + tags — assembly **if** the field types and the validate tags are literal and their forms are listed in §6.2; EX (not inspectable) only when types are inferred or the tags cannot be transcribed.

→ label "not inspectable", record the reason.

**Exception**: a candidate with `name` + `description` but missing the rest of its type's base field is not "unrecognizable" — it is an **incomplete** artifact. Label "incomplete", extract the available fields, and state what is missing ("schema not provided with the document" for a Tool; "no body" for a Skill). A candidate with `name` but missing `description` is likewise **incomplete** — a Tool must carry `description` before the QD-T checks can run. A pure JSON Schema with no `name` is not incomplete: it stays a full original with `name = (unnamed)` (§5 E1). The missing base field is recorded only as a document-level fact, not judged as a product defect. For a Prompt, "incomplete" means the text carries no instruction at all (e.g. a bare placeholder or variable) or is assembled from several fragments whose assembly logic is absent from the input (§10).

## 6. Extraction rules

### 6.1 Verbatim copy

Applies to E1 and E2.

**Target format.** Verbatim copy preserves the source's own syntax and drops only the shell; it does **not** promise valid JSON. When the target is a JSON Schema but the source is not already JSON (a Python dict or JS object literal with single-quoted keys, `True`/`None`, or trailing commas), that source form is extraction class E3 — go to §6.2 for the literal field-by-field transcription.

1. Copy word-for-word; do not rewrite, polish, or complete.
2. Drop only the shell (assignment statement, function definition line, `return`, fence markers, `export const X =`, backticks); the content inside the shell is untouched. For a Python multiline string, strip the common indentation (dedent). For nested fences, strip only the outermost layer and keep the inner fence markers as artifact text.
3. Unescape (`\n` → newline) **only** where string-literal semantics call for it; in a raw string / regex keep `\n` literal. Variables (`{var}`, `{{ var }}`) are kept as-is, not substituted.
4. The result must match the original in full. If it does not → label "summary".
5. Check every placeholder per the "examine each variable" rule in §5 E2.

### 6.2 Assembly

Applies to E3. **Reorganize only, do not translate.**

**Literal field-by-field transcription (non-JSON literals).** When the target is a JSON Schema but the source is a Python dict or JS object literal that is not already JSON (`inputSchema={...}` written with single-quoted keys, `True`/`None`, or trailing commas), transcribe it field by field into JSON: single quotes → double quotes, `True`/`None` → `true`/`null`, drop trailing commas; a non-literal value is marked "in source, not a schema value". Record `method = assembly`, not `verbatim copy`.

1. Copy, field by field, everything already literal in the source: `name`, `description` / `.describe("...")`, each parameter's key and description, `enum` values, the `required` list, `default` values.
2. Convert constraints by rule:

| Source form | JSON Schema |
|---|---|
| Zod `.max(n)` / `.min(n)` on a string | `maxLength` / `minLength` |
| Zod `.max(n)` / `.min(n)` on a number | `maximum` / `minimum` |
| Zod `.max(n)` / `.min(n)` on an array | `maxItems` / `minItems` |
| Zod `.int()` | `type: integer` |
| Zod `.enum([...])` | `enum` |
| Zod `.optional()` | not in `required` |
| Zod `.default(v)` | `default` |
| Zod `.regex(re)` | `pattern` |
| Zod `.email()` / `.url()` / `.uuid()` | `format: email` / `uri` / `uuid` |
| Zod `z.record(k, v)` | `type: object` + `additionalProperties` |
| Zod `z.tuple([...])` | `type: array` + fixed `items` |
| Zod `z.union([...])` / `z.literal(v)` | `enum` / `const` when all alternatives are literals; otherwise "union not expressible, in source only" |
| Zod `z.any()` / `z.unknown()` | no `type` keyword |
| Nested `z.object({...})` inside a field | recurse: the field becomes a nested `type: object` with its own `properties` |
| Python `str/int/float/bool` annotation | `string/integer/number/boolean` |
| Python `List[X]` annotation | `type: array` + `items` |
| Python `= None` default | not in `required` |
| Python `Optional[X]` without default | in `required` (nullable) |
| Python `Literal[a, b]` | `enum` |
| Python `Dict[str, X]` | `type: object` + `additionalProperties` |
| Python `Set[X]` | `type: array` + `uniqueItems: true` |
| Python `Tuple[X, Y]` | `type: array` + fixed `items` |
| Python `Union[X, Y]` / `X \| Y` | `anyOf` when simple; otherwise "union not expressible, in source only" |
| Python `Any` | no `type` keyword |
| Python no default / has default | in `required` / record `default` |
| Python docstring first paragraph (before `Args:`) | the Tool's top-level `description` |
| Python docstring `Args:` section | the corresponding parameter's `description` |
| Go `WithString/WithNumber/WithBoolean` | `type` |
| Go `WithArray(...)` / `WithEnum(...)` / `WithObject(...)` | `type: array` / `enum` / `type: object` |
| Go `WithArray(WithString(...))` | `type: array` + `items: { type: string }` (element type follows the inner builder) |
| Go `WithObject(...)` child fields | a nested `type: object` with its own `properties` |
| Go `Required()` | in `required` |
| Go `DefaultString/DefaultNumber` | `default` |
| Go `Description(...)` | `description` |
| Go `json:"name"` tag | the property key |
| Go `validate:"required"` / `validate:"omitempty"` | in `required` / not in `required` |
| Go `validate:"min=N,max=N"` | `minimum` / `maximum` on a numeric field, `minLength` / `maxLength` on a string field (decide by the field's literal Go type) |
| Go `validate:"oneof=a b"` | `enum` |
| Go `validate:"email"` / `validate:"url"` | `format: email` / `format: uri` |
| Go field type `string/int/int64/float64/bool` | `string/integer/integer/number/boolean` |
| Go field type `[]T` / `map[string]T` | `type: array` + `items` / `type: object` + `additionalProperties` |
| Go pointer field `*T` | not in `required` unless the tag says `validate:"required"` |

> Any source constraint not listed above stays **out of the schema** — record it as evidence, never invent a keyword for it.

3. Wrap into `{ "type": "object", "properties": {...}, "required": [...] }`.
4. **Add no field-level constraint that is absent from the source.** If the source does not write a `type` for a property, do not add a `type` keyword for that property. (The root `"type": "object"` in rule 3 is the assembly wrapper, not a source field.)
5. `.refine()` / `.superRefine()` / custom validation cannot be converted to JSON Schema; **do not fabricate an equivalent constraint** — write "implemented in source via refine, not entered into the schema".
6. Framework-injected parameters are not user parameters and **must be removed**: Python MCP `ctx: Context`, FastAPI `Depends(...)`, LangChain `InjectedToolArg`, `self` / `cls`, and runtime config objects.
7. Attach the source fragment for each field.

### 6.3 The description field must not be lost

`description` / `.describe()` / docstring is the core basis of Tool Schema inspection, and is the easiest thing to lose during assembly.

- Source has a description, result does not → label the whole thing "assembled" and write "description field at risk of loss".
- Source has no description → the result must not have one either; **do not write one**.

## 7. Completeness levels

Six labels, applied to the whole artifact, not subdivided by field. They form a total order (top = most inspectable):

```
full original  >  original · variable unexpanded  >  assembled  >  incomplete  >  summary  >  not inspectable
```

"Drop the completeness level by one" (§9) means move down this order by one step.

| Label | Meaning | Which checks can run |
|---|---|---|
| **full original** | Verbatim copy, complete | All |
| **original · variable unexpanded** | Verbatim copy, but has unexpanded variables that expand into rules | All except checks that depend on those variables |
| **assembled** | Schema assembled from code | Structure and contradiction checks all run; "a field is missing some constraint" is judged per field (see below) |
| **incomplete** | Artifact incomplete, missing base fields | Only checks on the fields actually provided |
| **summary** | Summarized / transcribed / does not match the original | Only contradiction checks, not "what is missing" |
| **not inspectable** | Cannot be extracted | No checks; only record the reason |

**How "assembled" judges a missing constraint**: look at the evidence.

| Evidence situation | Conclusion |
|---|---|
| The source fragment covers the field's complete writing (whole chained call / full signature / full builder call / full struct definition) | Judgeable. The source really did not write it → truly missing |
| The source fragment covers only part, or the boundary is unclear | Skip that check, mark "uncertain" |

Whether a check runs depends on whether that field was copied fully, not on whether it is an assembled artifact.

**`.refine()` is looked at separately**: `.refine()` generally does not enter the runtime-generated JSON Schema. So when the description promises a constraint (e.g. "at most 50 words") but the schema has no corresponding keyword, this is a **candidate QD-T-4.5 check to hand off** (recorded as evidence for the inspection stage — this layer never emits PASS/FAIL) and must not be erased as "cannot be assembled". Wording: "description declares X, schema has no corresponding constraint; in source X is implemented via refine, which usually does not enter the JSON Schema."

## 8. L determination

This layer determines **L** — the complexity / operation-risk level of each artifact — once, and hands it down. L is a classification, not a defect grade. It feeds only the severity (P) of the downstream checks; it does **not** decide whether a check runs (that is the downstream structural-fact gate's job, not L's).

### 8.1 Two dimensions, kept separate

| Dimension | Judges | Levels | Applies to |
|---|---|---|---|
| **AC-L** | how complex the agent is | L1 single-turn / L2 multi-turn / L3 complex (L4 multi-agent reserved) | System Prompt |
| **OR-L** | how risky the operations are | L1 read-only / L2 reversible write / L3 irreversible | Skill, Tool Schema |

The two dimensions are **kept separate at the engine level** — they are never merged into one number, because merging would break severity lookup (e.g. "AC-L1 + OR-L3" cannot be expressed as a single level).

### 8.2 AC-L determination (Prompt)

Read the prompt content and judge its complexity. Multi-turn vs. single-turn is often **not visible in a static prompt** — judge by observable signals only:

- **AC-L1 (single-turn)**: one question, one answer; no tools, no multi-turn state.
- **AC-L2 (multi-turn)**: a multi-turn dialogue; each turn is self-contained. Observable signals: variables for `history` / `turn` / `session`, a "previous messages" field, or a stated back-and-forth contract.
- **AC-L3 (complex)**: planning / reflection / tool orchestration across steps. Observable signals: a tool-call loop, plan→execute→reflect instructions, or explicit multi-step orchestration.
- **L4 (multi-agent)** is reserved; do not emit L4 until the multi-agent scale is finalized.
- **No observable signal** for multi-turn / complexity → emit `L = undetermined`; do not guess.

### 8.3 OR-L determination (Skill / Tool)

Read the skill/tool content and judge its operation risk by the most dangerous operation it can perform:

- **OR-L1 (read-only)**: query / search / read; no write.
- **OR-L2 (reversible write)**: create / update / send that can be corrected or undone.
- **OR-L3 (irreversible)**: delete / transfer / irreversible external notification.

**Never silently downgrade to OR-L1.** A Skill/Tool with no declared tool invocation is **not** automatically OR-L1: first scan its prose and schema semantics for write verbs (delete / transfer / send / overwrite / deploy / write). Any write hit → judge by the highest such operation. Only a positive read verb (query / search / read) with **no** write verb is OR-L1. A Skill/Tool with no verb of any kind stays `undetermined` (§8.5).

### 8.4 Product layer: one unified label

For the user-facing output, collapse the two dimensions into **one unified label per artifact** (the merged view happens in how it is shown, not in how it is computed):

- Prompt → show its AC-L.
- Skill / Tool → show its OR-L.
- (Permission, a cross-cutting concern, is handled downstream per permission item — not here.)

### 8.5 When uncertain

- If L cannot be judged from the available content (e.g. "summary" fidelity), emit `L = undetermined` and let the downstream structural-fact gate decide "whether to check"; the downstream then reports severity as `—` (reference level) per `_meta.md` §4, and records "L undetermined" in the report rather than picking an L column.
- L does **not** decide "whether to check", but it **does** decide whether a result enters the defect grade: `∅` (this L assigns no P) and `undetermined` (reported as `—` downstream) both drop a finding to reference level. A wrong L therefore **can** suppress a defect — an L1 misjudgment can turn a P0/P1 finding into a non-graded reference note. Never present a wrong L as harmless.

## 9. Evidence

Do not use line numbers (models cite them unreliably) or checksums (no scripts). Use **excerpt self-evidence**.

Each output carries:

- **Location**: source file + section heading (e.g. `## Original Artifact Content` / `### 2. Input schema`).
- **Method**: verbatim copy / assembly / summary.
- **Verbatim excerpt**: verbatim-copy cases give the head and tail fragments; assembly cases give the source fragment per field (`name` → source, `description` → source, each parameter → source).

Self-evidence standard: a person who does not know the context can find every point in the original using only the evidence. If not, drop the completeness level by one (down the §7 order).

**Correctness mark (independent of completeness).** Completeness says *how much* was extracted; correctness says *whether the extraction may be wrong*. When the evidence cannot be matched field-by-field to the original, attach a correctness mark — `verbatim mismatch` (a verbatim copy that drifts) or `assembly mismatch` (an assembled field that does not match its source) — even if the completeness label stays `full original`. This is what lets an audit tell "extraction error" apart from "inspection error".

## 10. Agent membership within a document

**By default, one document = one agent's artifact set.**

- One document may contain multiple artifacts of the same agent (one prompt + several tools).
- If multiple agent forms are detected (e.g. a suite of 6 roles), **do not auto-split and do not auto-bounce**: label "agent membership pending confirmation", state the detection basis, and output two options for the user to confirm — (a) confirm they are one agent → continue; (b) declare them an unrelated artifact collection → hand to inspect in collection mode for per-artifact single checks. pre-inspect does not decide for the user.

### How to handle the remaining cases

| Case | Handling |
|---|---|
| Fence not closed | Do not guess the ending; label "summary" |
| Variable is runtime data (`{local_tz}`) | Keep the variable, label "full original" |
| Variable expands into rules, definition locatable (`{reference_prompt}` defined in the input) | Keep "full original", trace the definition, list the variable, and add it to the reference layer as `prompt var` |
| Variable expands into rules, definition not locatable (`{reference_prompt}` undefined in the input) | Label "original · variable unexpanded", list the variable |
| Multiple fragments assembled by code into a final prompt | Label "incomplete", write "assembly logic not provided" |
| A field does not match the source during assembly | Label the whole thing "assembled", attach the `assembly mismatch` correctness mark, and note the field |
| Description field suspected lost | The related checks do not run, evidence noted |
| Suspected multiple agents | Label "agent membership pending confirmation", output confirmation options |
| Summarized / transcribed / cannot cut cleanly | Label "summary" or "not inspectable" |

## 11. Output format

One Markdown inventory, structured as a two-layer IR:

1. **Extraction summary** (top): agent membership declaration (single agent / pending confirmation), total artifact count, count by type, not-inspectable count and per-item reasons, completeness-level distribution, and L distribution. The membership declaration uses a fixed phrasing so downstream consumers can read it reliably: `agent membership: single agent` or `agent membership: pending confirmation` (never a free-form paraphrase).
2. **Object layer** — one block per extracted artifact: artifact name, type, completeness level, **L**, extraction class, source location, extraction method, verbatim evidence. "original · variable unexpanded" must list the unexpanded variables and a content summary.
3. **Reference layer** — every cross-object reference detected in §4.1: `referenced name | referenced by | relationship (tool call / skill dep / prompt var / file ref)`; generic prose does not enter here. A `prompt var` entry whose definition is locatable (§5 E2) additionally carries the **expanded rules** — the traced definition text, or a location anchor pointing to where it is defined — so the inspection stage can read the expanded content, not just the variable name.
4. **Not-inspectable list** — listed separately, each with a reason, producing no defect conclusion.
5. **`ir-core` JSON block** — the machine-readable core of layers 2, 3 and 4 — objects, references, and the not-inspectable list (see below), for CLI / platform to parse.

### ir-core block (machine-readable core)

Materialize the IR to a file and, inside it, embed one `<!-- ir-core -->` JSON block carrying only the machine-readable fields, so a program engine can parse the IR without reading the human evidence.

**ir-core v1 contract.** `ir_version` is `"1"`. `completeness` is one of the six labels (§7); `L` is one of `AC-L1` / `AC-L2` / `AC-L3` / `OR-L1` / `OR-L2` / `OR-L3` / `undetermined`. `objects[]` carries `type` / `name` / `completeness` / `L` / `source` / `mismatch`; `source` is the section heading (§9 Location), `mismatch` is a correctness mark or null. "not inspectable" objects are **not** in `objects[]` — they go in a separate `not_inspectable[].{name,reason}`. `references[].relationship` is one of `tool call` / `skill dep` / `prompt var` / `file ref`.

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

**Materialization**: the host model (this skill has no scripts) writes the IR as a Markdown file (default name `{input_basename}.ir.md`, next to the input or in the user-specified output directory) **and** keeps a copy in-context for the chained inspection. The file is the durable audit checkpoint; the in-context copy is the working handoff. If the host cannot write the file (no write permission / no filesystem), keep only the in-context copy and mark the summary `not materialized` — materialization is **not** a precondition for a successful extraction.

## 12. What this does NOT do

- Do not rewrite, repair, or normalize artifact text.
- Do not judge PASS / FAIL / severity (P0/P1/P2). Determining L (AC-L / OR-L) is an L classification, not a defect grade.
- Do not split or mix across agents.
- Do not fabricate fields, invent constraints, or write missing descriptions.
- Do not treat a carrier as an artifact, or scaffolding as an artifact.
- Do not write framework-injected parameters (Python MCP `ctx: Context`, FastAPI `Depends(...)`, LangChain `InjectedToolArg`, `self` / `cls`) as tool parameters.

## 13. Handoff to sanityops-inspect-lite

```
Original document → [pre-inspection extraction layer] → two-layer IR (objects + references, each object tagged with L) → [seven-stage inspection]
```

The pre-inspection layer does not change the seven-stage logic; it only changes what is fed into it — the two-layer IR (with L tagging) replaces the flat artifact list. The IR is handed down both in-context and as a materialized file. "Not inspectable" objects are listed in the final report as input notes, producing no defect conclusion.
