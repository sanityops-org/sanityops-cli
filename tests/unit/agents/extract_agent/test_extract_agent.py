"""End-to-end ExtractAgent tests with a scripted fake provider (no real LLM)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from sanityops_agent.core.message import FinishReason, TextBlock, ToolUseBlock
from sanityops_agent.llm.base import LLMProvider, LLMResponse

from sanityops_cli.agents.extract_agent.agent import (
    ExtractAgent,
    ExtractionFailedError,
    IncompleteExtractionError,
)
from sanityops_cli.inspect_pipeline.skill_runtime import materialize_skills

SRC_SKILLS = Path(__file__).resolve().parents[4] / "src" / "sanityops_cli" / "skills"


def tool_call(call_id: str, tool_name: str, **tool_input) -> ToolUseBlock:
    return ToolUseBlock(tool_call_id=call_id, tool_name=tool_name, tool_input=tool_input)


def response(*blocks, stop=FinishReason.TOOL_USE, tokens=100):
    return LLMResponse(
        content=list(blocks), stop_reason=stop, model="fake", usage={"total_tokens": tokens}
    )


class ScriptedProvider(LLMProvider):
    """Replays a fixed response sequence; records create() calls."""

    def __init__(self, script: list[LLMResponse]):
        self.script = list(script)
        self.calls: list[list] = []
        self.seen_messages: list[list] = []

    async def create(self, messages, tools=None, **kwargs):
        self.calls.append(tools or [])
        self.seen_messages.append(list(messages))
        if not self.script:
            raise AssertionError("provider script exhausted")
        return self.script.pop(0)

    def stream(self, messages, tools=None, **kwargs):  # pragma: no cover
        raise NotImplementedError


@pytest.fixture()
def project(tmp_path: Path):
    docs = tmp_path / "proj"
    docs.mkdir()
    (docs / "system.md").write_text("You are a helpful assistant.", encoding="utf-8")
    return docs


def happy_script(project: Path) -> list[LLMResponse]:
    prompt_path = str(project / "system.md")
    return [
        response(
            TextBlock(text="loading skill"),
            tool_call("t1", "skill", operation="load", name="pre-inspect-extract"),
        ),
        response(TextBlock(text="reading file"), tool_call("t2", "read", file_path=prompt_path)),
        response(
            TextBlock(text="storing"),
            tool_call(
                "t3",
                "store_artifacts",
                operation="add_artifact",
                artifact={
                    "type": "prompt",
                    "name": "system",
                    "content": "You are a helpful assistant.",
                    "completeness": "full original",
                    "L": "AC-L1",
                    "evidence": "You are a helpful … assistant.",
                    "source": prompt_path,
                    "total_chunks": 1,
                    "seq": 0,
                    "final": True,
                },
            ),
        ),
        response(
            TextBlock(text="references"),
            tool_call(
                "t4",
                "store_artifacts",
                operation="add_reference",
                reference={
                    "name": "system",
                    "referenced_by": "system",
                    "relationship": "includes_prompt",
                },
            ),
            tool_call(
                "t5",
                "store_artifacts",
                operation="set_attribution",
                attribution={"status": "single", "note": "one config"},
            ),
        ),
        response(TextBlock(text="done: 1 prompt extracted."), stop=FinishReason.END_TURN),
    ]


@pytest.fixture()
def skills_dir(tmp_path: Path):
    return materialize_skills(cache_root=tmp_path / "cache")


class TestHappyPath:
    def test_extracts_artifact_reference_attribution(self, project, skills_dir):
        provider = ScriptedProvider(happy_script(project))
        agent = ExtractAgent(provider, skills_dir=skills_dir, verbose=False)
        result = asyncio.run(
            agent.extract(prompts=[str(project / "system.md")], tools=[], skills=[])
        )

        assert [a.name for a in result.artifacts] == ["system"]
        record = result.artifacts[0]
        assert record.content == "You are a helpful assistant."
        assert record.completeness == "full original"
        assert record.extraction_method == "agent"
        assert result.references[0].relationship == "includes_prompt"
        assert result.attribution.status == "single"
        assert result.meta.loops_used == 5
        assert result.meta.tokens_used == 500

    def test_tools_registered(self, project, skills_dir):
        provider = ScriptedProvider(happy_script(project))
        agent = ExtractAgent(provider, skills_dir=skills_dir)
        asyncio.run(agent.extract(prompts=[str(project / "system.md")], tools=[], skills=[]))
        tool_names = {td.name for tools in provider.calls for td in tools}
        assert {"read", "store_artifacts", "skill"} <= tool_names

    def test_system_prompt_has_appendix_and_skill_list(self, project, skills_dir):
        provider = ScriptedProvider(happy_script(project))
        agent = ExtractAgent(provider, skills_dir=skills_dir, report_language="zh")
        asyncio.run(agent.extract(prompts=[str(project / "system.md")], tools=[], skills=[]))

        first_call_messages = provider.seen_messages[0]
        system = first_call_messages[0]
        assert system.role.value == "system"
        text = "".join(getattr(b, "text", "") for b in system.content)
        assert "CLI Contract Appendix" in text
        assert "pre-inspect-extract" in text  # mandatory-first-step mandate
        assert "zh" in text  # report language propagated
        # Factory injected the Available Skills manifest after the appendix.
        assert "Available Skills" in text
        assert "sanityops-inspect-lite" in text
        # The task message follows as the user turn.
        assert first_call_messages[1].role.value == "user"

    def test_read_scoping_in_registry(self, project, skills_dir):
        provider = ScriptedProvider(happy_script(project))
        agent = ExtractAgent(provider, skills_dir=skills_dir)
        asyncio.run(agent.extract(prompts=[str(project / "system.md")], tools=[], skills=[]))


class TestFailureModes:
    def test_non_end_turn_raises(self, project, skills_dir):
        # token_budget=10 with 100-token responses: the loop terminates with
        # TOKEN_BUDGET on its second iteration — a deterministic non-END_TURN.
        provider = ScriptedProvider(happy_script(project))
        agent = ExtractAgent(provider, skills_dir=skills_dir, token_budget=10)
        with pytest.raises(ExtractionFailedError, match="token_budget"):
            asyncio.run(agent.extract(prompts=[str(project / "system.md")], tools=[], skills=[]))

    def test_incomplete_chunk_stream_raises(self, project, skills_dir):
        prompt_path = str(project / "system.md")
        script = [
            response(
                TextBlock(text="store"),
                tool_call(
                    "t1",
                    "store_artifacts",
                    operation="add_artifact",
                    artifact={
                        "type": "prompt",
                        "name": "p",
                        "content": "half",
                        "total_chunks": 2,
                        "seq": 0,
                    },
                ),
            ),
            response(TextBlock(text="done"), stop=FinishReason.END_TURN),
        ]
        provider = ScriptedProvider(script)
        agent = ExtractAgent(provider, skills_dir=skills_dir)
        with pytest.raises(IncompleteExtractionError, match="prompt/p"):
            asyncio.run(agent.extract(prompts=[prompt_path], tools=[], skills=[]))

    def test_manifest_size_cap(self, project, skills_dir):
        provider = ScriptedProvider([])
        agent = ExtractAgent(provider, skills_dir=skills_dir)
        huge = [str(project / "system.md")] * 101
        with pytest.raises(ExtractionFailedError, match="limit 100"):
            asyncio.run(agent.extract(prompts=huge, tools=[], skills=[]))


class TestDeterministicCandidates:
    def test_uncovered_candidate_synthesized(self, project, skills_dir, tmp_path):
        registry = tmp_path / "proj" / "tools.json"
        registry.write_text(
            json.dumps(
                {
                    "tools": [
                        {"name": "covered", "description": "d", "parameters": {}},
                        {"name": "uncovered", "description": "d2", "parameters": {}},
                    ]
                }
            ),
            encoding="utf-8",
        )
        script = [
            response(
                TextBlock(text="load"),
                tool_call("t1", "skill", operation="load", name="pre-inspect-extract"),
            ),
            response(
                TextBlock(text="store covered only"),
                tool_call(
                    "t2",
                    "store_artifacts",
                    operation="add_artifact",
                    artifact={
                        "type": "tool",
                        "name": "covered",
                        "schema": {"name": "covered", "description": "d", "parameters": {}},
                        "completeness": "full original",
                        "L": "OR-L1",
                        "evidence": "registry",
                        "source": str(registry),
                        "total_chunks": 1,
                        "seq": 0,
                        "final": True,
                    },
                ),
            ),
            response(TextBlock(text="done"), stop=FinishReason.END_TURN),
        ]
        provider = ScriptedProvider(script)
        agent = ExtractAgent(provider, skills_dir=skills_dir)
        result = asyncio.run(agent.extract(prompts=[], tools=[str(registry)], skills=[]))

        by_name = {a.name: a for a in result.artifacts}
        assert by_name["covered"].extraction_method == "agent"
        assert by_name["covered"].L == "OR-L1"
        uncovered = by_name["uncovered"]
        assert uncovered.extraction_method == "deterministic"
        assert uncovered.L == "undetermined"
        assert uncovered.completeness == "full original"
        assert uncovered.schema_object["description"] == "d2"
        assert result.meta.deterministic_candidates == 2

    def test_ambiguous_registry_goes_to_llm_path(self, project, skills_dir, tmp_path):
        bad = tmp_path / "proj" / "bad.json"
        bad.write_text("{broken json", encoding="utf-8")
        ExtractAgent(ScriptedProvider([]), skills_dir=skills_dir)
        # candidates extraction happens before run; provider script empty would
        # fail on run — we only exercise the candidate split via the tool fn.
        from sanityops_cli.agents.extract_agent.tools.tool_registry import extract_tool_candidates

        candidates, unresolved = extract_tool_candidates([str(bad)])
        assert candidates == []
        assert unresolved == [str(bad)]


class TestContextGuard:
    def test_estimate_includes_tool_input(self, project, skills_dir):
        from sanityops_agent.core.context import AgentContext
        from sanityops_agent.core.message import Message, Role

        from sanityops_cli.inspect_pipeline.context_guard import ArtifactAwareContext

        context = ArtifactAwareContext()
        payload = {"artifact": {"type": "prompt", "name": "big", "content": "x" * 4000}}
        context.messages.append(
            Message(
                role=Role.ASSISTANT,
                content=[
                    ToolUseBlock(tool_call_id="c1", tool_name="store_artifacts", tool_input=payload)
                ],
            )
        )
        plain = AgentContext()
        plain.messages.append(
            Message(
                role=Role.ASSISTANT,
                content=[
                    ToolUseBlock(tool_call_id="c1", tool_name="store_artifacts", tool_input=payload)
                ],
            )
        )
        assert context.estimate_tokens() > plain.estimate_tokens()
        # Cached: second estimate identical (no double serialization drift).
        assert context.estimate_tokens() == context.estimate_tokens()
