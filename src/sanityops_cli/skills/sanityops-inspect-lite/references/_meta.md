---
title: Unified Checklist shared meta document (_meta)
---

# Unified Checklist Shared Meta Document

> This file is the **shared definition** for the 8 domain checklists: field model, check_engine mapping, applicability structural-fact gate, severity expression, scoring rules, and domain file organization conventions. **Load once, reuse across domains.** Domain files carry only "the check items themselves" and do not repeat this file.
>
> Status: v2 unified engine edition (finalized). Design decision records are in the repo root `checklist-unification-design.md` (not distributed with the package, for in-repo reference only).

## 1. Field model (all fields, shared by the three consumers)

> Principle: fields take the most complete consumer (platform) as the ceiling; "whether to use" trimming happens on the consumer side, not on the field side.

| Field | Meaning | skill | CLI | platform |
|---|---|---|---|---|
| `id` / `name` / `definition` | Traceability anchor + judgment definition | ✓ | ✓ | ✓ |
| `check_engine` | `program` / `model` / `hybrid` | **Not consumed** (full model reasoning) | ✓ routing | ✓ routing |
| `applicability` | Structural facts (decide "whether a check runs", do not write L) | ✓ | ✓ | ✓ |
| `severity` | Full mapping by L (decides "how severe") | ✓ | ✓ | ✓ |
| `program_rule` | Program judgment rules (pre-screening for program/hybrid) | **Not consumed** (no program execution environment) | ✓ | ✓ |
| `model_prompt` | Model judgment points (confirmation for model/hybrid) | ✓ | ✓ | ✓ |
| `score_weight` | Scoring weight / whether counted in the denominator | ignored | ignored | ✓ |
| `examples` | Positive / counter-examples (suspended, to be added) | ✓ | ✓ | ✓ |
| `cross_refs` | Same-source dedup / merge / transfer relationships | ✓ | ✓ | ✓ |

> **skill consumption boundary (hard)**: the skill side does not read `check_engine`, does not parse the `program-check` block in §4, and does not execute `program_rule`. Phrases in domain files such as "the program only checks… / the program only does… / the program engine only parses…" describe the pre-screening path of CLI / platform and **do not constitute a judgment precondition for the skill**: the skill must complete full semantic reasoning per the judgment points in §3, must not lower judgment strength because "the program has already screened", and must not treat "the program pre-screening found no hit" as a basis for N/A.

## 2. check_engine three values and mapping

- `program`: deterministic rules, executable by the program engine (e.g. missing fields, syntax parsing).
- `model`: semantic judgment, requires model reasoning (e.g. contradictory instructions, description quality).
- `hybrid`: program pre-screening + model confirmation.

**Source `Method` column → check_engine baseline mapping**: `Automated→program`, `Human→model`, `Semi-automated→hybrid`.

**Source correction principle (prioritize convergence)**: if pure model is possible, use pure model; screening rules go into the program block, confirmation points go into the main text. When the source Method column contradicts its own definition, correct it per this principle and leave a reclassification log in the domain file.

## 3. applicability (structural-fact gate)

- "Whether a check runs" is decided by **observable structural facts** (`has_tool` / `has_workflow` / `has_write_semantics` / `is_tool_schema`, etc.), **not by L**.
- **Point-1 paradox (mandatory)**: structural facts judge "what the artifact claims to do / what signs appear", and **cannot** judge "whether a declaration is complete". Otherwise it cancels its own item — if "tool not declared" is judged by "is a tool declared", it can never catch anything.
  - Therefore "missing X field / X not declared" checks use `is_*` (type facts, always true) rather than `has_X` (which self-cancels). Example: `QD-T-1.1 Base Field Missing` uses `is_tool_schema`, not `has_schema`.
- **Fail-safe defaults**:
  - `on_absent` → N/A (the structural fact does not exist; the basis must be written)
  - `on_unknown` → judge (cannot be determined; default to checking)
- **N/A discipline**: N/A is the exit for "structurally not applicable", **not** "missing"; the basis must be stated.
- **Judging authority (who judges structural facts)**: on the skill side, structural facts are judged by the host model through full semantic reasoning (the skill does not consume `check_engine` / `program_rule`, see §1); on the CLI / platform side, by program initial screening + model confirmation. On either side, the basis for a structural-fact judgment must be traceable — especially "the fact does not exist" (`on_absent → N/A`) must record the search scope and the basis for the non-hit; when the basis is insufficient, mark `uncertain` rather than N/A. The fact source of conditional items (e.g. `has_pii` / `has_side_effect_op` / `is_regulated_domain`) is determined by the same judging authority, and a fact hit that "triggers → P0" must record its basis.

## 4. severity expression conventions

- `P0/P1/P2` = fixed value under that L
- `∅` = the original spec assigns no P under that L → **reference level** (still checked, but not counted in that L's severity); N/A is decided solely by `applicability.fact`, independent of L.
- `P1→P0(conditional)` = default P1, upgraded to P0 when the condition in parentheses is hit
- `P1·P2` = two sub-defects within the same item split into different grades
- `P0(style P2)` = main defect P0, stylistic sub-item P2
- The semantics of `*` (by-feature, triggered by feature) in the source spec is merged into `applicability.fact`; severity stores only "the value after a hit".
- `undetermined` (cannot be graded at the pre layer) = do not map severity; judge as `—` (reference level: still checked, not scored), and state "L undetermined" in the report; do not guess an L column to fill in.

**Domain-specific L naming**: the Prompt domain uses AC-L, the Skill/Tool domain uses OR-L, Permission uses max; the severity table header explicitly marks the prefix.

## 5. Scoring (platform only)

- Global weight: `P0 : P1 : P2 = 5 : 3 : 1`, deducted once by the item's highest severity.
- The `score_weight` field is retained; skill/CLI do not activate scoring (behavior trimming happens on the consumer side).
- change-check (e.g. QD-T-5.x change management) and tombstone are not counted in the static denominator.
- **Denominator** = the number of active items hit by `applicability.fact` under that L; the fixed L1/L2/L3 counts in each domain file's §6 are historical reference values from the original tier-scoped spec; the platform implementation is governed by applicability hits.

## 6. Domain file organization conventions

Each domain file (e.g. `prompt-checklist.v2.md`) has this structure:

1. Status header (source + this file carries only check items; shared definitions see `_meta.md`)
2. **§1 Domain notes (including the check_engine reclassification log)**: L naming for this domain, judgment conventions, item classification notes; check_engine deviations from the source `Method` column must be logged here; when there is no deviation, write "no reclassification"
3. §2 Check item index (ID / name / check_engine / applicability.fact / severity / counted in scoring)
4. §3 Model judgment points (§3.1 pure model / §3.2 hybrid confirmation)
5. §4 Program-judgment items (`<!-- program-check -->` JSON block, only program + hybrid pre-screening; **the skill does not execute**)
6. §5 tombstone (merged / transferred)
7. §6 Scoring field notes (domain-specific denominator)

**Variants (not considered drift)**:

- Domains with ungraded advisory items (currently the prompt domain) add a "§6 Advisory items" section between §5 and the scoring section, and the scoring section shifts to §7.
- The last section of `explicit-checklist.v2.md` is "Grading and disposition notes" (no numeric scoring), corresponding to item 7 of this convention.
- `relevance-map.v2.md` is a mapping table rather than a check item list, so this organization convention does not apply.

**Rule-table consistency constraints (horizontal, mandatory)**: index, judgment, scoring, dedup, and examples must not diverge; the governance run (S0) auto-validates domain files against these.

- **Numbering**: the ID sets in the §2 index / §3 judgment points / §4 program block are identical; tombstoned IDs in §5 and merged / transferred / deprecated IDs in `cross_refs` must not reappear as active items in the index table.
- **Applicability level**: `applicability.fact` decides "whether a check runs" and does not write L; the L prefix shown in the index table's severity column matches this domain's naming (Prompt=AC-L, Skill/Tool=OR-L, Permission=max), never mixed.
- **Severity**: the index table's severity column (AC-L default), §1's OR-L3 escalation table and instance escalations, and §3 rule-body "→P0" branches are mutually consistent; the same rule must not show a default-severity divergence between the body and the index/escalation table.
- **Counted-in-scoring**: the index table's "Counted in scoring" column matches the §6 denominator convention; `∅` (reference level), tombstone, change-check, and candidate/unlanded numbers are not counted in the denominator.
- **Primary item**: the primary flagged by `cross_refs` is unique within a same-source dedup group and consistent with the §6 dedup note; dedup merges only "the same fact", never a blanket merge by ID combination alone.
- **Examples**: every active check item's `examples` should contain "should-hit / should-not-hit / boundary" three cases; currently "suspended, to be added", and this constraint takes effect once they are filled in.
