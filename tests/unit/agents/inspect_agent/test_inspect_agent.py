"""End-to-end InspectAgent tests with a scripted fake provider."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from sanityops_agent.core.message import FinishReason, TextBlock, ToolUseBlock
from sanityops_agent.llm.base import LLMProvider, LLMResponse

from sanityops_cli.agents.inspect_agent.agent import (
    InspectAgent,
    InspectionFailedError,
)
from sanityops_cli.inspect_pipeline.skill_runtime import materialize_skills

SRC_SKILLS = Path(__file__).resolve().parents[4] / "src" / "sanityops_cli" / "skills"

TAIL_JSON = (
    "<!-- inspect-summary -->\n"
    '{"status": "completed", "stages": {"A": "executed", "B": "not executed — collection mode"},'
    ' "counts": {"inspect": {"p0": 1, "p1": 0, "p2": 0}, "risk_explicit": {"p0": 0, "p1": 1, "p2": 0}},'
    ' "findings": [{"stage": "A", "module": "QD-P", "artifact": "system",'
    ' "id": "QD-P-2.2.1", "severity": "P0", "description": "contradiction"}]}\n'
    "<!-- /inspect-summary -->"
)


def tool_call(call_id: str, tool_name: str, **tool_input) -> ToolUseBlock:
    return ToolUseBlock(tool_call_id=call_id, tool_name=tool_name, tool_input=tool_input)


def response(*blocks, stop=FinishReason.TOOL_USE, tokens=100):
    return LLMResponse(
        content=list(blocks), stop_reason=stop, model="fake", usage={"total_tokens": tokens}
    )


class ScriptedProvider(LLMProvider):
    def __init__(self, script: list[LLMResponse]):
        self.script = list(script)
        self.seen_messages: list[list] = []
        self.seen_tools: list[list] = []

    async def create(self, messages, tools=None, **kwargs):
        self.seen_messages.append(list(messages))
        self.seen_tools.append(tools or [])
        if not self.script:
            raise AssertionError("provider script exhausted")
        return self.script.pop(0)

    def stream(self, messages, tools=None, **kwargs):  # pragma: no cover
        raise NotImplementedError


def full_script() -> list[LLMResponse]:
    return [
        response(
            TextBlock(text="loading skill"),
            tool_call("t1", "skill", operation="load", name="sanityops-inspect-lite"),
        ),
        response(
            TextBlock(text="checklists"),
            tool_call(
                "t2", "skill", operation="load", name="sanityops-inspect-lite"
            ),  # domain file stand-in
        ),
        response(
            TextBlock(text="header"),
            tool_call("t3", "write_report", section="header", content="# Report"),
            tool_call("t4", "write_report", section="A", content="## Stage A\nQD-P findings"),
        ),
        response(
            TextBlock(text="stage B"),
            tool_call(
                "t5", "write_report", section="B", content="Stage B: Not Executed — collection mode"
            ),
        ),
        response(
            TextBlock(text="stages C-G"),
            tool_call("t6", "write_report", section="C", content="C"),
            tool_call("t7", "write_report", section="D", content="D"),
            tool_call("t8", "write_report", section="E", content="E"),
            tool_call("t9", "write_report", section="F", content="F"),
            tool_call("t10", "write_report", section="G", content="G"),
            tool_call("t11", "write_report", section="status_board", content="board"),
            tool_call("t12", "write_report", section="self_verification", content="verified"),
        ),
        response(TextBlock(text=TAIL_JSON), stop=FinishReason.END_TURN),
    ]


@pytest.fixture()
def skills_dir(tmp_path: Path):
    return materialize_skills(cache_root=tmp_path / "cache")


def make_agent(provider, skills_dir, **overrides) -> InspectAgent:
    defaults = dict(
        injection_payload="# Extraction IR payload\n- artifacts: 1",
        header_data={"model": "fake-model", "date": "2026-11-06"},
        attribution="pending",
        attribution_note="mixed registries",
        qc_candidates=[
            {
                "rule_id": "QC-3.3",
                "artifact": "system",
                "location": "$.content[0]",
                "model_prompt": "confirm weak credential",
            }
        ],
        report_language="en",
    )
    defaults.update(overrides)
    return InspectAgent(provider, skills_dir=skills_dir, **defaults)


class TestHappyPath:
    def test_full_report_and_tail(self, skills_dir):
        provider = ScriptedProvider(full_script())
        agent = make_agent(provider, skills_dir)
        outcome = asyncio.run(agent.inspect())

        assert outcome.termination_reason == "end_turn"
        assert outcome.missing_stages == []
        assert outcome.report_markdown.index("# Report") < outcome.report_markdown.index("C")
        assert "Not Executed — collection mode" in outcome.report_markdown
        assert outcome.tail_text == TAIL_JSON

    def test_tools_registered(self, skills_dir):
        provider = ScriptedProvider(full_script())
        agent = make_agent(provider, skills_dir)
        asyncio.run(agent.inspect())
        names = {td.name for tools in provider.seen_tools for td in tools}
        assert {"skill", "read", "write_report"} <= names

    def test_appendix_carries_contract(self, skills_dir):
        provider = ScriptedProvider(full_script())
        agent = make_agent(provider, skills_dir)
        asyncio.run(agent.inspect())

        system = provider.seen_messages[0][0]
        text = "".join(getattr(b, "text", "") for b in system.content)
        assert "sanityops-inspect-lite" in text
        assert "Attribution and cross-check gating" in text
        assert "pending" in text
        assert "inspect-summary" in text
        assert "QC-3.3" in text
        assert "en" in text
        # Injection payload reached the agent as the user turn.
        user = provider.seen_messages[0][1]
        assert "Extraction IR payload" in "".join(getattr(b, "text", "") for b in user.content)

    def test_token_budget_floor_enforced(self, skills_dir):
        provider = ScriptedProvider(full_script())
        agent = make_agent(provider, skills_dir, token_budget=1000)
        assert agent.token_budget == 300_000


class TestFailureModes:
    def test_non_end_turn_raises(self, skills_dir):
        script = full_script()[:2]  # ends mid-run
        provider = ScriptedProvider(script)
        agent = make_agent(provider, skills_dir, token_budget=300_000, max_loops=2)
        with pytest.raises(InspectionFailedError, match="max_loops"):
            asyncio.run(agent.inspect())

    def test_missing_stages_detected(self, skills_dir):
        script = full_script()
        # Drop the calls that wrote stages C-G + scaffolding (turn 5).
        del script[4]
        script.append(response(TextBlock(text=TAIL_JSON), stop=FinishReason.END_TURN))
        provider = ScriptedProvider(script)
        agent = make_agent(provider, skills_dir)
        outcome = asyncio.run(agent.inspect())
        assert "C" in outcome.missing_stages
        assert "status_board" not in outcome.missing_stages  # not a stage


class TestAttributionGating:
    def test_single_attribution_directive(self, skills_dir):
        provider = ScriptedProvider(full_script())
        agent = make_agent(provider, skills_dir, attribution="single")
        asyncio.run(agent.inspect())
        system = provider.seen_messages[0][0]
        text = "".join(getattr(b, "text", "") for b in system.content)
        assert "cross-artifact stages (B" in text

    def test_pending_attribution_directive(self, skills_dir):
        provider = ScriptedProvider(full_script())
        agent = make_agent(provider, skills_dir, attribution="pending")
        asyncio.run(agent.inspect())
        system = provider.seen_messages[0][0]
        text = "".join(getattr(b, "text", "") for b in system.content)
        assert "MUST NOT silently run cross-artifact" in text
