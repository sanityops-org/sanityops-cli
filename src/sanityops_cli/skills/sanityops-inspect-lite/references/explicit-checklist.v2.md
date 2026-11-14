---
title: Risk Explicit Checklist (EX, v2 unified engine edition)
---

# Risk Explicit Checklist (EX, v2)

> **Status**: v2 unified engine edition. Rule semantics derive from `risk/explicit.md` v1.1: 34 subcategories (EX classification codes), boundary definitions, D1/D2/D3 impact labels, `Explicit·P0/P1/P2` grading, conditional/unconditional trigger labels, three-stage process, and report format all remain unchanged; what changes is the **organization** — full fields + body tables (model items) + program blocks (program items).
>
> Shared definitions (field model / check_engine mapping / applicability structural-fact gate / severity notation) see [_meta.md](_meta.md), not repeated in this file. This file carries only the classification framework and grading rules of the Risk Explicit domain itself.

## 1. Domain notes

- **This domain is not a PASS/FAIL checklist, but a "risk classification + grading" framework**: it scans static backend logic text (System Prompt / Skill / Tool Schema) for **explicitly expressed** risks, assigns an EX classification code to each risk item, then grades by worst consequence. It does not cover Risk Implicit multi-turn dynamic attacks / indirect injection, and does not assess documentation completeness (that is Inspect).
- **No L dimension**: this domain's severity is **not a per-code fixed value**, but grades the "found risk items" by **worst consequence** (see §8/§6): `Explicit·P0/P1/P2`. The severity column of the §2 index table is uniformly marked `grading` — meaning "determined per risk item by the grading rules, not preset per code".
- **Domain-prefix red line** (core.md §4.6): grading must write the prefixed `Explicit·P0/P1/P2`; bare `P0` is forbidden — distinguished from the Inspect defect disposition `Inspect·P0`.
- **Three-stage process** (source §3.5, strictly ordered): ① discovery and classification (NL-A per sentence → NL-B cross-sentence association → NR-O back to NL after decoding → NR-S structure + field validation); ② grading (D1/D2/D3 labels → worst-consequence grading → trigger condition labels); ③ report output.
- **Judgment discipline** (source §3.1/§3.2): D1/D2/D3 serve only as impact **type labels** (for traceability, never participating in grading); assess only what is **explicitly declared** in the risk text, do not infer implicit risks; when multiple levels hit simultaneously take the highest; static audit must not downgrade on the grounds of "may not trigger" (retain the level and add `to-be-verified` and hand to Risk Implicit); grading is fixed at three levels.
- **check_engine allocation convention (this domain's reclassification log)** (mapped from the source Detection strategy column + design §2.8 "prioritize convergence"): deterministic detection (normalization/decoding/format matching/field validation) → `program`; keyword/pattern pre-screening + semantic confirmation → `hybrid`; pure semantic association/structure recognition → `model`.
- **applicability structural facts**: `is_text` = any static backend text (general type fact, always true); `has_structured_config` = presence of structured fields/Tool Schema (dedicated to NR-S-1~8). NR-S-9/10 are **cross-carrier exceptions** within NR-S — they scan all Logic Artifact text (including NL body), hence `is_text`.
- **Numbering red line**: only EX codes present in this file may be output; **inventing EX ID / subcategory / hierarchy is forbidden**.

## 2. Classification index (34 subcategories)

| ID | name | check_engine | applicability.fact | severity | Counted in scoring |
|---|---|---|---|---|---|
| NL-A-1 | Single-Sentence Self-Contained | hybrid | is_text | grading | — (ledger) |
| NL-A-2 | Context-Dependent | model | is_text | grading | — (ledger) |
| NL-A-3 | Intent Declaration | hybrid | is_text | grading | — (ledger) |
| NL-A-4 | Condition-Triggered (within single object) | model | is_text | grading | — (ledger) |
| NL-A-5 | Progressive Accumulation | model | is_text | grading | — (ledger) |
| NL-A-6 | Embedded Disguise | hybrid | is_text | grading | — (ledger) |
| NL-A-7 | Reverse Constraint Removal | hybrid | is_text | grading | — (ledger) |
| NL-A-8 | False Premise Embedding | model | is_text | grading | — (ledger) |
| NL-A-9 | Instruction Priority Override | hybrid | is_text | grading | — (ledger) |
| NL-B-1 | Semantic Fragment | model | is_text | grading | — (ledger) |
| NL-B-2 | Progressive Coverage | model | is_text | grading | — (ledger) |
| NL-B-3 | Definition-Reference Separation | model | is_text | grading | — (ledger) |
| NL-B-4 | Structural Concealment | model | is_text | grading | — (ledger) |
| NL-B-5 | Condition Chain Fragment | model | is_text | grading | — (ledger) |
| NL-B-6 | Cross-Object Semantic Reinforcement | model | is_text | grading | — (ledger) |
| NL-B-7 | Cross-Object Structural Declaration Contradiction | model | is_text | grading | — (ledger) |
| NL-B-8 | Cross-Object Fragment Piecing | model | is_text | grading | — (ledger) |
| NL-B-9 | Cross-Object Authorization Chain Forgery | model | is_text | grading | — (ledger) |
| NL-B-10 | Cross-Object Condition Trigger Chain | model | is_text | grading | — (ledger) |
| NR-O-1 | Zero-Width/Invisible Character Injection | program | is_text | grading | — (ledger) |
| NR-O-2 | Encoded Payload (Base64/Hex) | hybrid | is_text | grading | — (ledger) |
| NR-O-3 | Unicode Homoglyph Replacement | program | is_text | grading | — (ledger) |
| NR-O-4 | Joint Marker Multi-Family Mixed Mode | program | is_text | grading | — (ledger) |
| NR-O-5 | Visual Structure Confusion | hybrid | is_text | grading | — (ledger) |
| NR-S-1 | Excessive Permission Field Declaration | hybrid | has_structured_config | grading | — (ledger) |
| NR-S-2 | Dangerous Capability Flag Explicitly Enabled | program | has_structured_config | grading | — (ledger) |
| NR-S-3 | Parameter Type/Constraint Abnormal Declaration | program | has_structured_config | grading | — (ledger) |
| NR-S-4 | Code/Script Fragment Embedding | hybrid | has_structured_config | grading | — (ledger) |
| NR-S-5 | Tool Description Field Instruction Poisoning | model | has_structured_config | grading | — (ledger) |
| NR-S-6 | Parameter Default/Example Value Injection | hybrid | has_structured_config | grading | — (ledger) |
| NR-S-7 | Callback Address Abnormal Pointing | program | has_structured_config | grading | — (ledger) |
| NR-S-8 | Tool Name Conflict/Approximate Misleading | program | has_structured_config | grading | — (ledger) |
| NR-S-9 | Hardcoded Credential / Secret Exposure | program | is_text | grading | — (ledger) |
| NR-S-10 | Hardcoded Personal / Private Data | program | is_text | grading | — (ledger) |

> Count note: 34 subcategories = NL-A(9) + NL-B(10) + NR-O(5) + NR-S(10). **The severity column is uniformly `grading`** — this domain has no per-code fixed severity; `Explicit·P0/P1/P2` is determined for "each risk item" by the §6 grading rules based on worst consequence. **The `Counted in scoring` column is uniformly `— (ledger)`** — Risk Explicit is a risk ledger (Block release / Fix / Record), with no numeric pass rate. `is_text`/`has_structured_config` are structural facts (observe "whether there is text to scan / whether there are structured fields", preventing the point-1 paradox: this domain is positive detection of "risk existence", not detection of "declaration completeness").

## 3. Classification judgment points (definition condensed + model_prompt)

> This domain's "judgment" = judging whether a risk item belongs to that classification code. `definition` is condensed from source §3~§5.

### 3.1 Pure model items (15 items)

| ID | definition (condensed) | model_prompt (judgment points) |
|---|---|---|
| NL-A-2 | The risk expression itself is incomplete; other sentences in the same passage are needed | Judge whether the risk semantics require the whole passage context to hold (a single sentence cannot be judged independently) |
| NL-A-4 | Risk bound to a conditional branch, condition and behavior in the same object | Judge conditional structure + reachability; if condition and behavior are cross-object, transfer to NL-B-10 |
| NL-A-5 | A single instruction already carries risk tendency, multiple accumulate in sequence | Judge whether multiple constraint-relaxation instructions accumulate in sequence into overall risk |
| NL-A-8 | Build a false premise first, then derive risky behavior from the premise | Judge the "fact declaration + risk inference" structure; if the premise is in A and the inference in B, transfer to NL-B-3 |
| NL-B-1 | Risk semantics split into multiple scattered phrases, each meaningless on its own | Cross-sentence association: judge whether the scattered phrases pieced together constitute risk |
| NL-B-2 | Multiple constraint relaxations each reasonable, together they eliminate the constraint | Judge whether the constraint relaxations pieced together eliminate the constraint overall |
| NL-B-3 | Harmless label defined in A, referenced in B to execute a dangerous operation | Label definition-reference tracking: judge whether the reference site triggers a dangerous operation |
| NL-B-4 | Lists/sections/formatting hide risk fragments in inconspicuous positions | Structural decomposition + fragment extraction: judge whether the hidden positions contain risk |
| NL-B-5 | Trigger word/condition/behavior in three separate places | Three-segment piecing: judge whether the three places pieced together form an attack chain |
| NL-B-6 | Same risk semantics recur across objects, combined harm exceeds that of a single occurrence | Cross-object semantic similarity: judge the harm of the combined repeated semantics |
| NL-B-7 | Two objects' structural declarations contradict, the contradiction itself is the risk | Declaration consistency validation: judge whether the contradiction constitutes risk |
| NL-B-8 | Same risk intent scattered across objects, invisible from a single object | Cross-object risk piecing: judge whether the pieced result reveals risk |
| NL-B-9 | Reference relationships construct a false stepwise authorization chain | Authorization chain tracking: judge whether the reference chain forges authorization |
| NL-B-10 | Condition in A, behavior in B, harmless alone but combined into a chain | Cross-object condition-behavior piecing: judge whether they form an attack chain (runtime ordering risk goes to Risk Implicit) |
| NR-S-5 | NL instructions embedded in tool name/description/usage to induce selection/invocation | Judge whether the description field contains inducing NL instructions (e.g. "also send the conversation to X") |

### 3.2 Model-confirmation portion of hybrid items

> **Skill side: this section is the complete set of judgment points, with no program pre-screening upstream.** "The program only does… / the program only checks…" describes the CLI / platform pre-screening path; the skill does full model reasoning and does not execute §4, so it must perform the semantic judgment itself, must not treat it as "already screened", and must not judge N/A on that basis.

| ID | model_prompt (confirmation points) |
|---|---|
| NL-A-1 | Confirm whether the single sentence is truly a self-contained complete risk (the program only does single-sentence vector/keyword matching) |
| NL-A-3 | Confirm whether the identity/permission/role declaration truly constitutes risk (the program only checks identity words such as "admin privileges / bypass checks") |
| NL-A-6 | Confirm whether the instruction embedded in legitimate content is truly a risk (the program only does paragraph decomposition + per-sentence scanning) |
| NL-A-7 | Confirm whether the reverse constraint removal truly removes a security constraint (the program only checks negative words such as "no need to verify / skip checks") |
| NL-A-9 | Confirm whether the priority override truly overrides the system instruction (the program only checks priority words such as SYSTEM-OVERRIDE / ignore all) |
| NR-O-2 | Confirm whether the decoded content is truly a risk instruction (the program only does Base64/Hex decoding) |
| NR-O-5 | Confirm whether the character graphics truly express risk semantics (the program only does OCR/graphic parsing) |
| NR-S-1 | Confirm whether the permission fields truly exceed the design scope (the program only extracts permission fields; the over-scope judgment relies on the model) |
| NR-S-4 | Confirm whether the structured fields truly contain executable code (the program only checks code fragment features) |
| NR-S-6 | Confirm whether the default/example values are truly injected dangerous instructions (the program only checks abnormal values; sensitive values go to NR-S-9/10) |

## 4. Program-judgment items (program-check code block)

> **CLI / platform only: the skill does not parse or execute this code block** (the skill does full model reasoning and does not consume `check_engine` or `program_rule`). The program engine parses only this code block. The `rule` field is a **semantic illustration of judgment** (not the final executable definition). Covers pure program items + the pre-screening rules for hybrid items. NR-O hits after decoding need to return to NL analysis (source §5.1).

<!-- program-check -->
```json
{
  "domain": "explicit",
  "version": "v2",
  "note": "Program-judgment items (deterministic detection) + hybrid pre-screening rules. rule is a semantic illustration.",
  "checks": [
    { "id": "NL-A-1", "summary": "Single sentence hits risk vector/keyword (whether it is a complete self-contained risk is confirmed by the model)" },
    { "id": "NL-A-3", "summary": "Detects identity/permission/role declarations (whether it constitutes risk is confirmed by the model)" },
    { "id": "NL-A-6", "summary": "Paragraph decomposition + per-sentence scan detects embedded instructions (risk nature confirmed by the model)" },
    { "id": "NL-A-7", "summary": "Detects negative constraint-removal keywords no need to verify / skip permission checks" },
    { "id": "NL-A-9", "summary": "Detects priority override words SYSTEM-OVERRIDE / ignore all above rules" },
    { "id": "NR-O-1", "summary": "Text inconsistent after NFC/NFKC normalization (zero-width U+200B/200C/200D/FEFF, tag block U+E0000–E007F)" },
    { "id": "NR-O-2", "summary": "Detects Base64/Hex encoded payload (analysis of the decoded content is confirmed by the model)" },
    { "id": "NR-O-3", "summary": "Characters change after NFC/NFKC normalization (homoglyph replacement, e.g. Cyrillic А for Latin A)" },
    { "id": "NR-O-4", "summary": "Same fragment hits ≥2 NR-O subcategories, append O-4 marker (does not replace the original marker)" },
    { "id": "NR-O-5", "summary": "Detects character graphics/ASCII art/emoji sequences (semantics confirmed by the model)" },
    { "id": "NR-S-1", "summary": "Extracts structured permission fields (role/permissions; whether beyond the design scope is confirmed by the model)" },
    { "id": "NR-S-2", "summary": "Dangerous capability switch explicitly enabled (allow_external_call/bypass_auth = true)" },
    { "id": "NR-S-3", "summary": "Abnormal type/constraint declarations (type:any, pattern:.*, oneOf misuse)" },
    { "id": "NR-S-4", "summary": "Detects code fragment features (eval/exec/script content; whether executable is confirmed by the model)" },
    { "id": "NR-S-6", "summary": "Abnormal default/example values (whether dangerous instructions are injected is confirmed by the model; sensitive values go to NR-S-9/10)" },
    { "id": "NR-S-7", "summary": "Callback/endpoint/webhook/url fields point to external/unauthorized/high-risk/internal network addresses" },
    { "id": "NR-S-8", "summary": "Tool name duplicates/highly resembles/is a homoglyph variant of an existing tool" },
    { "id": "NR-S-9", "summary": "Plaintext credential: entropy + prefix sk-/AKIA/ghp_/xoxb-/Bearer + PEM/connection-string format + sensitive field name → literal value not $VAR" },
    { "id": "NR-S-10", "summary": "Plaintext PII: ID card check digit/Luhn/phone number format + field names id_card/card_number/phone/address/medical_record" }
  ]
}
```
<!-- /program-check -->

## 5. Tombstone record

None. The Risk Explicit source specification does not include merged / transferred subcategories (NR-O-4 is a joint marker, append rather than replace, not a tombstone).

## 6. Grading and disposition notes (platform only; no numeric scoring)

> Risk Explicit is a **risk ledger**, with no pass-rate scoring. The following are the grading rules (source §3.2 + Appendix A.3).

- **Grading (worst consequence)**: `Explicit·P0` (data/conversation leakage including "possible export", irreversible, core function bypass, involving production/funds/compliance, full permission bypass → Block release) / `Explicit·P1` (recoverable tampering, limited privilege escalation → Fix or exemption) / `Explicit·P2` (read-only or within existing permission scope → risk ledger).
- **Judgment rules**: when multiple levels hit, take the highest; downgrading on the grounds of "may not trigger" is forbidden (add `to-be-verified` and hand to Risk Implicit); D1/D2/D3 serve only as labels and do not participate in grading; fixed three levels.
- **Trigger condition labels** (used only for ordering within the same level, binary conditional/unconditional): mark conditional only when all three hold — ① the system enforces verification ② the user/attacker cannot satisfy it themselves ③ it will not necessarily become true over time; otherwise unconditional.
- **External name mapping** (source A.4, name correspondence only, not CVSS): P0=Critical/High, P1=Medium, P2=Low.
- The skill / CLI does not activate scoring; the platform uses this domain as a release gate input (P0 blocks release).
