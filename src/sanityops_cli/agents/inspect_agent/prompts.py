# Copyright 2026 zipsonken
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""Prompts for the InspectAgent (design §6.1–§6.4).

Thin CLI contract appendix (~3KB): the inspection rules live in the vendored
``sanityops-inspect-lite`` skill and its domain checklists, loaded on demand.
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

Before any check, call `skill(operation="load", name="sanityops-inspect-lite")`.
It defines the seven-stage flow, severities, Gate-0, and output norms.
Then load ONLY the domain checklists the artifact set needs (per the skill's
§8): e.g. with prompts only, load `_meta` guidance + `prompt-checklist` — do
not load tool/cross/permission checklists that nothing in the set requires.
Producing report sections without loading the skill first is a contract
violation; your report would be malformed and fail the stage gate.

## Output channel — `write_report` (the only report channel)

- Sections: {section_list}. They assemble in this fixed order regardless of
  call order.
- Stages A–G each need **at least one part**. When a stage does not run,
  write a part saying so and why (e.g. "Stage B: Not Executed — collection
  mode"). A stage with no part becomes "NOT RECEIVED" and fails --strict.
- One part ≤ ~6000 chars; write several parts per stage for long sections.
- `replace_part=true` rewrites your most recent part of that section
  (self-correction); use it instead of re-sending whole sections.

## Report header data (section `header`)

Render these facts verbatim in the header table:

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
 "stages": {{"A": "executed", "B": "not executed — <reason>", "...": "..."}},
 "counts": {{"inspect": {{"p0": 0, "p1": 0, "p2": 0}},
            "risk_explicit": {{"p0": 0, "p1": 0, "p2": 0}}}},
 "findings": [{{"stage": "A", "module": "QD-P", "artifact": "system",
               "id": "QD-P-2.2.1", "severity": "P0", "description": "<=120 chars"}}]}}
<!-- /inspect-summary -->

- `findings[]` is the COMPLETE machine-readable set (terminal rendering
  truncates, the array must not): ≤ 20 entries, ordered by severity; each
  `description` ≤ 120 characters; full findings live in the sections.
- Stage B findings set `artifact` to a two-element array naming both sides.
- `module` vocabulary: QD-P/QD-S/QD-T/QC/QD-PS/QD-PT/QD-ST/QD-SS/QD-TT/
  QD-CYC/QD-PM/EX/AS-FM.
- Count `Explicit·P0` under `risk_explicit`, never under `inspect` —
  explicit risk is not a defect verdict.
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
