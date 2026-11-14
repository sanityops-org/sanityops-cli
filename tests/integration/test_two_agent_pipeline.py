"""End-to-end pipeline integration test with a scripted LLM (design §3).

Runs the real QC lint → ExtractAgent → IR/payload → InspectAgent → parse →
persist chain against a scripted provider (no network): extraction reports
one prompt via store_artifacts, inspection emits a Stage A section plus the
tail JSON, and the QC program channel (QC-3.3) merges into the summary.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from sanityops_agent.core.agent import TerminationReason
from sanityops_agent.core.message import FinishReason, TextBlock, ToolUseBlock
from sanityops_agent.llm.base import LLMProvider, LLMResponse

from sanityops_cli.agents.extract_agent.agent import ExtractAgent
from sanityops_cli.agents.inspect_agent.agent import InspectAgent
from sanityops_cli.code_contract_checker.checker import CodeContractChecker
from sanityops_cli.commands.inspect import _merge_qc_findings, _qc_payload_block
from sanityops_cli.inspect_pipeline.ir_writer import render_injection_payload
from sanityops_cli.inspect_pipeline.markdown_reporter import save_inspection_report
from sanityops_cli.inspect_pipeline.report_parser import extract_tail_block, parse_summary
from sanityops_cli.inspect_pipeline.skill_runtime import materialize_skills


class ScriptedProvider(LLMProvider):
    """Replays a fixed list of LLMResponse objects in create() order."""

    def __init__(self, responses: list[LLMResponse]):
        self.responses = list(responses)

    async def create(self, messages=None, tools=None, **kwargs) -> LLMResponse:
        return self.responses.pop(0)

    def stream(self, messages, tools=None, **kwargs):  # pragma: no cover
        raise NotImplementedError


def response(*blocks, stop=FinishReason.TOOL_USE, tokens: int = 200) -> LLMResponse:
    return LLMResponse(
        content=list(blocks), stop_reason=stop, model="fake", usage={"total_tokens": tokens}
    )


def tool_call(call_id: str, tool_name: str, **tool_input) -> ToolUseBlock:
    return ToolUseBlock(tool_call_id=call_id, tool_name=tool_name, tool_input=tool_input)


def tail_json() -> str:
    payload = {
        "status": "completed",
        "stages": {s: "executed" for s in "ABCDEFG"},
        "counts": {
            "inspect": {"p0": 0, "p1": 0, "p2": 1},
            "risk_explicit": {"p0": 0, "p1": 0, "p2": 0},
        },
        "findings": [
            {
                "stage": "A",
                "module": "QD-P",
                "artifact": "system",
                "id": "QD-P-1.1",
                "severity": "P2",
                "description": "conflicting instruction",
            }
        ],
    }
    return "<!-- inspect-summary -->\n" + json.dumps(payload) + "\n<!-- /inspect-summary -->"


def extract_script(prompt_path: str) -> list[LLMResponse]:
    return [
        response(
            TextBlock(text="loading skill"),
            tool_call("e1", "skill", operation="load", name="pre-inspect-extract"),
        ),
        response(TextBlock(text="reading"), tool_call("e2", "read", file_path=prompt_path)),
        response(
            TextBlock(text="storing"),
            tool_call(
                "e3",
                "store_artifacts",
                operation="add_artifact",
                artifact={
                    "type": "prompt",
                    "name": "system",
                    "content": PROMPT_BODY,
                    "completeness": "full original",
                    "L": "AC-L2",
                    "evidence": "demo password marker",
                    "source": prompt_path,
                    "total_chunks": 1,
                    "seq": 0,
                    "final": True,
                },
            ),
        ),
        response(
            TextBlock(text="attribution"),
            tool_call(
                "e4",
                "store_artifacts",
                operation="set_attribution",
                attribution={"status": "single", "note": "one prompt, one agent"},
            ),
        ),
        response(TextBlock(text="done."), stop=FinishReason.END_TURN),
    ]


def inspect_script() -> list[LLMResponse]:
    # One write_report call per stage section (A-G), then the exec summary,
    # then the tail JSON on END_TURN — mirroring the vendored skill's flow.
    stage_content = {
        "A": "[P2] QD-P-1.1 system: conflicting instruction",
        "B": "Cross-artifact contracts reviewed; no new defects.",
        "C": "Cross-artifact logic reviewed; no new defects.",
        "D": "QC program-channel findings assessed.",
        "E": "Explicit risk statements reviewed.",
        "F": "No repair required (demo run).",
        "G": "Inspection metadata assembled.",
    }
    script: list[LLMResponse] = [
        response(
            TextBlock(text="loading skill"),
            tool_call("i1", "skill", operation="load", name="sanityops-inspect-lite"),
        )
    ]
    for stage, line in stage_content.items():
        script.append(
            response(
                TextBlock(text=f"stage {stage}"),
                tool_call(
                    "i2", "write_report", section=stage, content=f"## Stage {stage}\n\n{line}"
                ),
            )
        )
    script.append(
        response(
            TextBlock(text="summary"),
            tool_call("i4", "write_report", section="exec_summary", content="Clean-ish run."),
        )
    )
    script.append(response(TextBlock(text=tail_json()), stop=FinishReason.END_TURN))
    return script


PROMPT_BODY = (
    "# System Prompt\n\nYou are a helpful assistant.\n\n"
    "```python\nimport os\npassword = '123456'\n```\n"
)


def test_two_agent_pipeline_end_to_end(tmp_path: Path):
    project = tmp_path / "proj"
    project.mkdir()
    prompt_file = project / "system.md"
    prompt_file.write_text(PROMPT_BODY, encoding="utf-8")
    results_dir = tmp_path / "results"

    # Step 1: QC lint (program channel — finds the demo password)
    qc_result = CodeContractChecker().check_from_paths(
        prompts=[str(prompt_file)], tools=[], skills=[]
    )
    assert qc_result.gate_result.value == "PASS"
    assert any(d.rule_id.value == "QC-3.3" for a in qc_result.all_artifacts for d in a.defects)

    # Step 2: ExtractAgent (scripted LLM, real tools + vendored skill)
    skills_dir = materialize_skills(cache_root=tmp_path / "cache")
    extractor = ExtractAgent(
        ScriptedProvider(extract_script(str(prompt_file))),
        skills_dir=skills_dir,
    )
    extraction_result = asyncio.run(
        extractor.extract(prompts=[str(prompt_file)], tools=[], skills=[])
    )
    assert [a.name for a in extraction_result.artifacts] == ["system"]
    assert extraction_result.attribution is not None
    assert extraction_result.attribution.status == "single"

    # Step 3: Injection payload + QC block (CLI boundary)
    injection_payload = (
        render_injection_payload(extraction_result)
        + "\n\n"
        + _qc_payload_block(qc_result, qc_skipped=False)
    )
    assert "system" in injection_payload
    assert "QC gate: PASS" in injection_payload

    # Step 4: InspectAgent (scripted LLM, real tools + vendored skill)
    inspector = InspectAgent(
        ScriptedProvider(inspect_script()),
        skills_dir=skills_dir,
        injection_payload=injection_payload,
        header_data={
            "model": "scripted",
            "skill": "sanityops-inspect-lite v1",
            "date": "2026-11-06",
        },
        attribution="single",
        attribution_note="one agent set",
        qc_candidates=[],
        token_budget=300_000,
    )
    outcome = asyncio.run(inspector.inspect())

    assert outcome.termination_reason == TerminationReason.END_TURN.value
    assert outcome.section_parts["A"]
    assert outcome.missing_stages == []

    # Step 5: Fail-closed parse + QC merge
    parsed = parse_summary(outcome.tail_text, outcome.section_parts, outcome.missing_stages)
    assert parsed.source == "tail"
    assert parsed.status == "completed"

    _merge_qc_findings(parsed, qc_result)
    qc_ids = [f["id"] for f in parsed.findings if f["module"] == "QC"]
    assert {"QC-3.1", "QC-3.3"} <= set(qc_ids)  # demo import + hardcoded secret
    # 1 tail finding (QD-P-1.1) + 2 merged QC program-channel P2s
    assert parsed.counts["inspect"]["p2"] == 3
    assert parsed.inspect_p0 == 0

    # Step 6: Persist the report (best-effort in production, asserted here)
    report_path = save_inspection_report(
        outcome.section_parts,
        outcome.missing_stages,
        extract_tail_block(outcome.tail_text),
        results_dir,
        meta={"model": "scripted", "date": "2026-11-06"},
    )
    saved = report_path.read_text(encoding="utf-8")
    assert "Stage A" in saved
    assert "QD-P-1.1" in saved  # tail JSON persisted (markers stripped)
    assert "- model: scripted" in saved
