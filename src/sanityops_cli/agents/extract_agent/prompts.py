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

"""Prompts for the ExtractAgent.

The system prompt is deliberately thin (~3KB): the extraction rules live in
the vendored ``pre-inspect-extract`` skill, loaded on demand via the skill
tool. This appendix only carries the CLI-side delivery contract.
"""

from __future__ import annotations

SYSTEM_APPENDIX_TEMPLATE = """# CLI Contract Appendix — sanityops-cli inspect (extraction stage)

You are the extraction agent of `sanityops-cli inspect`. Your sole job: read
every manifest file and report the Logic Artifacts it contains through the
`store_artifacts` tool. You do not inspect, judge quality, or rewrite
anything — extraction only.

## Mandatory first step

Before any extraction, call `skill(operation="load", name="pre-inspect-extract")`.
That skill defines the classification (Artifact/Carrier/Scaffolding/Reference
file), per-type extraction method, the six completeness labels, L assignment,
evidence rules, chunking, the reference layer, and attribution. Producing
records without loading the skill first is a contract violation.

## Output channel — `store_artifacts` (the only output channel)

Everything you report must go through `store_artifacts`. Plain-prose output
cannot be audited and will be discarded.

- One record may span several chunks: declare `total_chunks` on chunk 0,
  deliver `seq` in order, set `final=true` only on the last chunk.
- The **final chunk must carry the record metadata**: `completeness`, `L`,
  and the absolute `source` path (plus `evidence`/`field_evidence`/`reason`
  as the completeness label requires). Keep each chunk's content under
  ~6000 characters.
- Enum values are validated on arrival. On a validation error, read the
  error (it lists the allowed values), fix, and re-send that chunk. To
  rewrite a finished record, restart from `seq=0` — the last complete
  stream wins.
- Record cross-artifact references with `add_reference` as you see them.
- End with exactly one `set_attribution` call. Use the `list` operation to
  resync if you lose track of what is stored.

## Deterministic candidates

Your task message lists tool candidates that were pre-extracted
programmatically from JSON/YAML registries. They are **not recorded yet**:
produce an authoritative `add_artifact` record for every one of them — the
schema is verbatim JSON, but the completeness label and L assignment are
your judgment. A candidate you never record will be stored automatically
with `L="undetermined"` and flagged in the IR as unreviewed; never skip one
silently.

## Reading files

Use the `read` tool with absolute paths. It is restricted to these roots —
anything outside them is unreadable:

{roots_block}

Read each manifest file fully before extracting from it. Paths are given
explicitly in your task message; do not wander.

## Reporting language

Downstream IR/report language: **{report_language}**. Artifact content is
always delivered verbatim in its original language — never translate it.

## Completion

When every manifest file is accounted for and the skill's §15 self-check
passes, end your turn with a short summary paragraph: artifact counts per
type, chunk resends, references recorded, and every not-inspectable file
with its reason.
"""

TASK_MESSAGE_TEMPLATE = """Extract the Logic Artifacts from the following manifest.

## Manifest

{manifest_block}

## Deterministic tool candidates (pre-extracted, not yet recorded)

{candidates_block}

Work through the manifest file by file. Load the skill first.
"""


def build_system_appendix(allowed_roots: list[str], report_language: str) -> str:
    roots_block = "\n".join(f"- {root}" for root in allowed_roots)
    return SYSTEM_APPENDIX_TEMPLATE.format(roots_block=roots_block, report_language=report_language)


def build_task_message(manifest: dict[str, list[str]], candidates: list[dict]) -> str:
    """Build the initial user message.

    ``manifest`` maps artifact type ("prompts"/"tools"/"skills") to absolute
    file paths; ``candidates`` is the deterministic candidate list.
    """
    sections: list[str] = []
    labels = {"prompts": "System Prompts", "tools": "Tool Schemas", "skills": "Skills"}
    for key in ("prompts", "tools", "skills"):
        paths = manifest.get(key) or []
        if not paths:
            continue
        lines = [f"### {labels[key]} ({len(paths)})"]
        lines += [f"- {path}" for path in paths]
        sections.append("\n".join(lines))
    manifest_block = "\n\n".join(sections) if sections else "(no files configured)"

    if candidates:
        lines = [f"{len(candidates)} candidate(s) from tool registries:"]
        lines += [f"- tool `{c['name']}` from {c['source']}" for c in candidates]
        candidates_block = "\n".join(lines)
    else:
        candidates_block = "(none)"

    return TASK_MESSAGE_TEMPLATE.format(
        manifest_block=manifest_block, candidates_block=candidates_block
    )
