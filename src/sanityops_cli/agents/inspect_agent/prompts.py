"""Prompts for the InspectAgent (design §6.1–§6.4).

Thin CLI contract appendix (~3KB): the inspection rules live in the vendored
``sanityops-inspect-only`` skill and its domain checklists, loaded on demand.
The appendix carries the delivery contract, the tail-JSON schema, the
attribution decision, and the QC hybrid-candidate confirmation duty.
"""

from __future__ import annotations

import json

SYSTEM_APPENDIX_TEMPLATE = """# CLI Contract Appendix — sanityops-cli inspect (inspection stage)

You are the inspection agent of `sanityops-cli inspect`. The extraction IR of
the artifacts under inspection is in your task message. Apply the
SanityOps Framework checks and emit the seven-stage report.

## Mandatory first step

Before any check, call `skill(operation="load", name="sanityops-inspect-only")`.
It defines the seven-stage flow, severities, Gate-0, and output norms.
Then load the references the flow needs (per the skill's §8). Always load
`_meta` once, plus `permission-checklist` (Stage D), `explicit-checklist`
(Stage E), and `relevance-map` when Stage F has a FAIL to map. Add
`prompt-checklist` / `skill-checklist` / `tool-checklist` only for the
artifact types present, `cross-checklist` when the set has at least two
artifacts, and `code-contract-checklist` when embedded code snippets appear.
Do not load a domain checklist that nothing in the set requires. Producing
report sections without loading the skill first is a contract violation; your
report would be malformed and fail the stage gate.

The extraction IR in your task message is the confirmed artifact set. Do not
run the skill's §2 directory/glob scope gate; inspect the supplied IR.

## Output channel — `write_report` (the only report channel)

- Sections: {section_list}. They assemble in this fixed order regardless of
  call order.
- Stages A–G each need **at least one part**. When a stage does not run,
  write a part saying so and why (e.g. "Stage B: Not Executed — collection
  mode"). A stage with no part becomes "NOT RECEIVED" and fails --strict.
- One part ≤ ~6000 chars; write several parts per stage for long sections.
- Always pass a `findings` array in each `write_report` call. Include the
  confirmed, graded defects or explicit risks described in that part.
  Use `[]` for sections without findings and for parts containing only
  PASS, N/A, or ungraded outcomes. Use each finding once, even if it is discussed
  in a later section or summary. In Stage F, mappings of earlier findings
  are references and do not add to the counts. Split large batches across parts.
- If a part is rejected, correct the call and resend that part before
  moving on. When correcting the findings array, keep the same Markdown content.
- The skill's folded PASS/N/A presentation is allowed: keep the detailed
  FAIL / uncertain / related / advisory lines and one compact per-stage tally
  line in the body, and deliver the full verdict-tally appendix in
  `self_verification`.
- The CLI summary counts graded P0/P1/P2 only. Never present ungraded verdicts
  as "0": state the ungraded totals (reference level, undetermined, uncertain,
  N/A) and the related/advisory counts in the `exec_summary` and
  `status_board` prose, per the skill's §6.1.
- The CLI fixes the section order. Put the skill's reader lead-in at the top
  of `header` (before the provenance table); deliver the status board in the
  `status_board` section and the verdict-tally appendix in `self_verification`.
- Each finding has `module`, `artifact`, `id`, `severity` and `description`
  (≤ 120 characters). Stage B uses an artifact array naming both sides.
  Use the module associated with the stage: A (QD-P/QD-S/QD-T/QC),
  B (QD-PS/QD-PT/QD-ST/QD-SS/QD-TT/QD-CYC), D (QD-PM), E (EX), F (AS-FM).
- `replace_part=true` rewrites your most recent part of that section
  including its findings; pass the replacement list in the same call.

## Report header data (section `header`)

Render these CLI provenance facts verbatim in the header table (do not emit
unofficial-skill disclaimers, host-model labels, or upgrade prompts):

{header_block}

## Attribution and cross-check gating

Attribution from extraction: **{attribution}**{attribution_note}
{attribution_directive}

## QC hybrid candidates (confirm or reject)

The QC lint pre-screen flagged the candidate snippets below (program channel,
zero tokens). For each, follow the checklist's model_prompt guidance: a real
defect → report it as a QC finding in Stage A with its rule ID; a false
positive → record it as a pre-screen false positive inside Stage A's QC
subsection, do not invent a defect.

{qc_candidates_block}

## Tail JSON — final message, exactly this shape

After your last `write_report` call, end your turn with a single message
containing ONLY this block (no prose around it):

<!-- inspect-summary -->
{{"status": "completed|failed",
 "stages": {{"A": "executed", "B": "not executed — <reason>", "...": "..."}}}}
<!-- /inspect-summary -->

- The CLI computes the summary counts from the findings in report parts.
- In the report prose, keep Explicit Risk counts separate from defects.
- `stages` must state every stage A–G: "executed" or "not executed — reason".

## Reporting language

Report language: **{report_language}**. Quote artifact content verbatim in
its original language; do not translate evidence.

## Completion

Finish in this order: all sections A–G + scaffolding → `status_board` →
`self_verification` → final message with the tail JSON block and nothing
else.
"""

TASK_MESSAGE_TEMPLATE = """Inspect the following extracted artifacts.

{injection_payload}
"""


def build_system_appendix(
    *,
    header_data: dict[str, str],
    attribution: str,
    attribution_note: str,
    qc_candidates: list[dict],
    report_language: str,
) -> str:
    section_list = ", ".join(
        f"`{s}`"
        for s in (
            "header",
            "exec_summary",
            "glossary",
            "input_notes",
            "A",
            "B",
            "C",
            "D",
            "E",
            "F",
            "G",
            "status_board",
            "self_verification",
        )
    )
    header_block = "\n".join(f"- {key}: {value}" for key, value in header_data.items())

    if attribution == "single":
        attribution_directive = (
            "The set binds to one Agent: cross-artifact stages (B, and the "
            "cross portions of C–D) run normally."
        )
    else:
        attribution_directive = (
            "Attribution is pending: you MUST NOT silently run cross-artifact "
            "checks. Stage B, the cross portions of C–D, and Stage E NL-B are "
            "'Not Executed — attribution pending'. Say this in their parts and "
            "in the tail JSON stages."
        )
    note = f" — {attribution_note}" if attribution_note else ""

    if qc_candidates:
        lines = [f"{len(qc_candidates)} candidate(s):"]
        for candidate in qc_candidates:
            lines.append(
                f"- {candidate.get('rule_id')} @ {candidate.get('artifact')} "
                f"({candidate.get('location')}): {candidate.get('model_prompt', '')}"
            )
        qc_candidates_block = "\n".join(lines)
    else:
        qc_candidates_block = "(none — QC lint passed clean or was skipped)"

    return SYSTEM_APPENDIX_TEMPLATE.format(
        section_list=section_list,
        header_block=header_block,
        attribution=attribution,
        attribution_note=note,
        attribution_directive=attribution_directive,
        qc_candidates_block=qc_candidates_block,
        report_language=report_language,
    )


def build_task_message(injection_payload: str) -> str:
    return TASK_MESSAGE_TEMPLATE.format(injection_payload=injection_payload)


def qc_candidates_payload(candidates: list[dict]) -> str:
    """Canonical JSON rendering for candidate injection (logging/debug)."""
    return json.dumps(candidates, ensure_ascii=False, indent=2)
